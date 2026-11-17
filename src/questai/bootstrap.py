from fastapi import FastAPI
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pydantic import SecretStr
import asyncio
import httpx

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

    async def readiness_probe(session: SecretStr) -> bool:
        async def check_mcp() -> None:
            async with service_for_session(session):
                pass

        async def check_model() -> None:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    settings.llm_models_url,
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                )
                response.raise_for_status()
                models = response.json().get("data")
                if not isinstance(models, list) or not any(
                    isinstance(item, dict) and item.get("id") == settings.llm_model
                    for item in models
                ):
                    raise ValueError("Modelo configurado indisponível")

        try:
            async with asyncio.timeout(4.0):
                # TaskGroup cancela a outra sondagem quando uma dependência falha.
                async with asyncio.TaskGroup() as checks:
                    checks.create_task(check_mcp())
                    checks.create_task(check_model())
            return True
        except Exception:
            return False

    return build_api_app(
        agent_service_factory=service_for_session,
        integration_token=settings.questai_integration_token,
        readiness_probe=readiness_probe,
    )
