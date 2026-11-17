from fastapi import FastAPI
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pydantic import SecretStr

from questai.adapters.inbound.api.app import create_app as build_api_app
from questai.adapters.outbound.agent.langchain_agent_engine import LangChainAgentEngine
from questai.adapters.outbound.llm.llm_factory import build_chat_model
from questai.adapters.outbound.mcp.mcp_adapter import MCPToolProvider
from questai.application.services.agent_service import AgentService
from questai.config.settings import get_settings


def create_app() -> FastAPI:
    """Composição raiz: único ponto que conhece todas as implementações concretas.

    Compatível com `uvicorn "questai.bootstrap:create_app" --factory`.
    """
    settings = get_settings()
    model = build_chat_model(settings)
    engine = LangChainAgentEngine(model)

    @asynccontextmanager
    async def service_for_session(session: SecretStr) -> AsyncIterator[AgentService]:
        provider = MCPToolProvider(
            server_url=settings.mcp_server_url,
            token=settings.questai_integration_token,
            session=session,
        )
        try:
            await provider.connect()
            yield AgentService(tool_provider=provider, engine=engine)
        finally:
            await provider.close()

    return build_api_app(
        agent_service_factory=service_for_session,
        integration_token=settings.questai_integration_token,
    )
