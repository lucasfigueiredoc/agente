from collections.abc import Sequence

from questai.application.ports.inbound.agent_port import (
    AgentMessage,
    AgentPort,
    AgentReply,
)
from questai.application.ports.outbound.llm_port import AgentEnginePort
from questai.application.ports.outbound.mcp_port import (
    ToolProviderError,
    ToolProviderPort,
)


class AgentService(AgentPort):
    """Serviço de aplicação: orquestra provedor de ferramentas e motor do agente.

    Stateless: o histórico recebido é repassado integralmente ao motor, sem
    mutação e sem estado entre chamadas. Não conhece implementações concretas,
    provedores de LLM ou bibliotecas de framework.
    """

    def __init__(self, tool_provider: ToolProviderPort, engine: AgentEnginePort) -> None:
        self._tool_provider = tool_provider
        self._engine = engine

    async def handle_message(self, messages: Sequence[AgentMessage]) -> AgentReply:
        if not self._tool_provider.is_connected():
            raise ToolProviderError("Provedor de ferramentas não está conectado.")

        tools = self._tool_provider.get_tools()
        content = await self._engine.run(messages, tools)
        return AgentReply(content=content)
