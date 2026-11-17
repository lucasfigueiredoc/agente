from collections.abc import AsyncIterator
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import SecretStr

from questai.adapters.inbound.api.schemas import ChatRequest, ChatResponse
from questai.application.ports.inbound.agent_port import AgentMessage, AgentPort

router = APIRouter()


def require_session(request: Request) -> SecretStr:
    expected = f"Bearer {request.app.state.integration_token.get_secret_value()}"
    supplied = request.headers.get("authorization", "")
    if not compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Origem não autorizada.")
    session = request.headers.get("x-displayquest-session", "")
    if not session or len(session) > 32768 or "\r" in session or "\n" in session:
        raise HTTPException(status_code=401, detail="Sessão do DisplayQuest obrigatória.")
    return SecretStr(session)


async def get_agent_service(request: Request) -> AsyncIterator[AgentPort]:
    async with request.app.state.agent_service_factory(require_session(request)) as service:
        yield service


@router.post("/agent/messages", response_model=ChatResponse)
async def handle_message(
    payload: ChatRequest,
    service: AgentPort = Depends(get_agent_service),
) -> ChatResponse:
    """Processa o histórico completo enviado no request (API stateless).

    `ToolProviderError` propaga para o handler registrado na aplicação.
    """
    messages = [AgentMessage(role=m.role, content=m.content) for m in payload.messages]
    reply = await service.handle_message(messages)
    return ChatResponse(content=reply.content)


@router.get("/health")
async def health() -> dict[str, object]:
    """Estado da API e conectividade do MCP, sem dados sensíveis."""
    return {"status": "ok", "mcp_mode": "user_session"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, bool]:
    """Sondagem autenticada sem gerar resposta nem executar ferramentas."""
    session = require_session(request)
    return {"available": await request.app.state.readiness_probe(session)}
