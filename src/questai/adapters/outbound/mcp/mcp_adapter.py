import asyncio
import json
from collections.abc import Sequence
from contextlib import AsyncExitStack

from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool, ToolException
from langgraph.errors import GraphBubbleUp
from pydantic import SecretStr

from questai.application.ports.outbound.mcp_port import ToolProviderError, ToolProviderPort


def _guard_transport_errors(tool: BaseTool) -> BaseTool:
    """Converte falhas de conexão/transporte/sessão em `ToolProviderError`.

    Preserva o fluxo oficial da integração `langchain.mcp`: erros reportados
    pelo servidor MCP (`isError=True`) chegam como `ToolException` e continuam
    convertidos em `ToolMessage(status="error")` para o modelo se autocorrigir;
    interrupções (`GraphBubbleUp`) e cancelamentos seguem intactos.
    """
    original = tool.coroutine

    async def guarded(**arguments: object) -> object:
        try:
            return await original(**arguments)
        except (ToolException, GraphBubbleUp, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise ToolProviderError(
                f"Falha de comunicação com o servidor MCP ao chamar {tool.name}."
            ) from exc

    tool.coroutine = guarded
    return tool


def _expose_structured_content(tool: BaseTool) -> BaseTool:
    """Torna o `structuredContent` do servidor visível ao modelo.

    O `MCPAdapter` devolve `(content_blocks, {"structured_content": ...})` e o
    ToolNode injeta no modelo apenas os blocos de `content` — que no servidor
    Display Quest são somente o resumo ("users: 31 item(ns)"). O JSON completo
    do `structured_content` é anexado como bloco de texto, preservando o
    resumo e mantendo o artefato original intacto.
    """
    original = tool.coroutine

    async def with_structured(**arguments: object) -> object:
        result = await original(**arguments)
        if isinstance(result, tuple) and len(result) == 2:
            blocks, artifact = result
            structured = artifact.get("structured_content") if isinstance(artifact, dict) else None
            if structured is not None and isinstance(blocks, list):
                payload = json.dumps(structured, ensure_ascii=False, default=str)
                return ([*blocks, {"type": "text", "text": payload}], artifact)
        return result

    tool.coroutine = with_structured
    return tool


def _authenticated_target(server_url: str, token: SecretStr, session: SecretStr) -> Client:
    """Encaminha a sessão somente ao transporte, nunca ao modelo."""
    transport = StreamableHttpTransport(
        server_url,
        headers={
            "Authorization": f"Bearer {token.get_secret_value()}",
            "X-DisplayQuest-Session": session.get_secret_value(),
        },
    )
    return Client(transport)


class MCPToolProvider(ToolProviderPort):
    """Provedor isolado por conversa HTTP, via MCPAdapter oficial.

    Bootstrap compõe uma instância por requisição autenticada e encerra seu
    contexto ao final. Cookies NextAuth ficam no transporte; nunca são argumentos
    de ferramenta, mensagens do modelo ou estado compartilhado entre usuários.
    """

    def __init__(self, server_url: str, token: SecretStr, session: SecretStr) -> None:
        self._server_url = server_url
        self._token = token
        self._session = session
        self._exit_stack: AsyncExitStack | None = None
        self._tools: list[BaseTool] = []
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        exit_stack = AsyncExitStack()
        try:
            adapter = MCPAdapter(
                _authenticated_target(self._server_url, self._token, self._session)
            )
            await exit_stack.enter_async_context(adapter)
            tools = await adapter.list_tools()
        except Exception as exc:
            await exit_stack.aclose()
            raise ToolProviderError(
                "Não foi possível conectar ao MCP com a sessão do DisplayQuest."
            ) from exc
        except BaseException:
            await exit_stack.aclose()
            raise

        self._exit_stack = exit_stack
        self._tools = [_guard_transport_errors(_expose_structured_content(tool)) for tool in tools]
        self._connected = True

    async def close(self) -> None:
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception as exc:
                raise ToolProviderError(
                    "Erro ao encerrar a conexão com o servidor MCP."
                ) from exc
            finally:
                self._exit_stack = None
        self._tools = []
        self._connected = False

    def get_tools(self) -> Sequence[object]:
        if not self._connected:
            raise ToolProviderError("O provedor de ferramentas não está conectado.")
        return tuple(self._tools)

    def is_connected(self) -> bool:
        return self._connected
