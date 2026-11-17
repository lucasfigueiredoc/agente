from typing import Literal

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    """Mensagem do histórico enviado pelo cliente."""

    role: ChatRole
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    """Contrato de entrada: histórico completo, com pelo menos uma mensagem.

    A API é stateless: o histórico viaja integralmente no request. Nenhum campo
    de sessão, usuário autenticado ou persistência.
    """

    messages: list[ChatMessage] = Field(min_length=1, max_length=80)


class ChatResponse(BaseModel):
    """Contrato de saída: apenas a resposta textual do assistente, sem estado
    interno."""

    content: str
