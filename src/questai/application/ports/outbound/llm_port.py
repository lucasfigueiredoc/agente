from abc import ABC, abstractmethod
from collections.abc import Sequence

from questai.application.ports.inbound.agent_port import AgentMessage


class AgentEnginePort(ABC):
    """Contrato do motor de agente (orquestração de LLM + ferramentas).

    As ferramentas são tipos opacos (`Sequence[object]`): a camada de
    aplicação nunca conhece tipos de LangChain, MCP ou de qualquer SDK.
    """

    @abstractmethod
    async def run(
        self,
        messages: Sequence[AgentMessage],
        tools: Sequence[object],
    ) -> str:
        """Executa o agente sobre o histórico completo e as ferramentas.

        Retorna o texto final da resposta do assistente. Erros de ferramenta
        reportados pelo provedor (`isError=True`) são fluxo normal de correção
        pelo modelo, não exceção deste contrato.
        """
        raise NotImplementedError
