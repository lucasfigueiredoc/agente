from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant"]


class AgentMessage(BaseModel):
    """Mensagem do histórico de conversa enviado pelo cliente.

    A aplicação é stateless: o histórico completo viaja no request e cada
    chamada processa a conversa inteira, sem estado persistente no servidor.
    """

    role: MessageRole
    content: str = Field(min_length=1)


class AgentReply(BaseModel):
    """Resposta textual final do assistente a uma sequência de mensagens."""

    content: str


class AgentPort(ABC):
    """Contrato de entrada da camada de aplicação.

    Não expõe tipos de framework ou de provedor: recebe apenas mensagens da
    aplicação e devolve a resposta do assistente.
    """

    @abstractmethod
    async def handle_message(self, messages: Sequence[AgentMessage]) -> AgentReply:
        """Processa o histórico completo de conversa e produz a resposta."""
        raise NotImplementedError
