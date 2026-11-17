from abc import ABC, abstractmethod
from collections.abc import Sequence


class ToolProviderError(RuntimeError):
    """Falha de infraestrutura do provedor de ferramentas.

    Representa exclusivamente falhas de conexão/transporte/sessão (ex.: o
    servidor MCP está indisponível). NÃO representa erros de ferramenta
    reportados pelo próprio servidor MCP (`isError=True`): esses seguem como
    resultado para o modelo se autocorrigir.
    """


class ToolProviderPort(ABC):
    """Contrato do provedor de ferramentas (servidor MCP externo).

    O catálogo de ferramentas é carregado uma única vez (no startup, via
    `connect()`) e reutilizado pelas chamadas subsequentes de `get_tools()`.
    As ferramentas devolvidas são tipos opacos (`Sequence[object]`).
    """

    @abstractmethod
    async def connect(self) -> None:
        """Estabelece a conexão e carrega o catálogo de ferramentas.

        Falhas de conexão/transporte/sessão devem ser levantadas como
        `ToolProviderError`.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Encerra a conexão e libera recursos do provedor."""
        raise NotImplementedError

    @abstractmethod
    def get_tools(self) -> Sequence[object]:
        """Retorna o catálogo já carregado, sem reconectar por chamada."""
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        """Reflete o estado real do ciclo de vida da conexão."""
        raise NotImplementedError
