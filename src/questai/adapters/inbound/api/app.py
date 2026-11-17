from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import SecretStr

from questai.adapters.inbound.api.routes import router
from questai.application.ports.inbound.agent_port import AgentPort
from questai.application.ports.outbound.mcp_port import ToolProviderError


def create_app(
    agent_service_factory: Callable[[SecretStr], AbstractAsyncContextManager[AgentPort]],
    integration_token: SecretStr,
    readiness_probe: Callable[[SecretStr], Awaitable[bool]],
) -> FastAPI:
    """Recebe a composição por requisição; nenhuma sessão é compartilhada."""
    app = FastAPI(title="QuestAI")
    app.state.agent_service_factory = agent_service_factory
    app.state.integration_token = integration_token
    app.state.readiness_probe = readiness_probe
    app.include_router(router)

    @app.exception_handler(ToolProviderError)
    async def tool_provider_error_handler(request: Request, exc: ToolProviderError) -> JSONResponse:
        """Falha de conexão/transporte/sessão do MCP → 502 estruturado, sem
        traceback. Erros de ferramenta (`isError=True`) não passam por aqui."""
        return JSONResponse(
            status_code=502,
            content={"error": {"type": "tool_provider_error", "message":
                "Não foi possível consultar o MCP com sua sessão. Entre novamente no DisplayQuest ou tente mais tarde."}},
        )

    @app.exception_handler(Exception)
    async def agent_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": {
            "type": "agent_error", "message": "Não foi possível concluir a resposta do agente. Tente novamente.",
        }})

    return app
