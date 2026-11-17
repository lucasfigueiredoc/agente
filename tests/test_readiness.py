import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from questai.bootstrap import create_app
from questai.config.settings import Settings


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token = "a" * 48
        settings = Settings(
            _env_file=None, llm_model="test-model", llm_base_url="http://model/v1",
            mcp_server_url="http://mcp/mcp", questai_integration_token=self.token,
            openai_api_key="test-key",
        )
        self.enterContext(patch("questai.bootstrap.get_settings", return_value=settings))
        self.enterContext(patch("questai.bootstrap.build_chat_model", return_value=object()))
        self.engine = MagicMock(run=AsyncMock())
        self.enterContext(patch("questai.bootstrap.LangChainAgentEngine", return_value=self.engine))
        self.provider = MagicMock(connect=AsyncMock(), close=AsyncMock())
        self.provider_factory = self.enterContext(patch("questai.bootstrap.MCPToolProvider", return_value=self.provider))
        self.app = create_app()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://agent")
        self.addAsyncCleanup(self.client.aclose)
        self.probe_client = MagicMock()
        self.probe_client.__aenter__ = AsyncMock(return_value=self.probe_client)
        self.probe_client.__aexit__ = AsyncMock(return_value=False)
        self.probe_client.get = AsyncMock(return_value=httpx.Response(
            200, json={"data": [{"id": "test-model"}]}, request=httpx.Request("GET", "http://model/v1/models"),
        ))
        self.enterContext(patch("questai.bootstrap.httpx.AsyncClient", return_value=self.probe_client))
        self.headers = {"Authorization": f"Bearer {self.token}", "X-DisplayQuest-Session": "next-auth.session-token=test"}

    async def test_requires_service_auth_and_user_session(self):
        for headers in ({}, {"Authorization": f"Bearer {self.token}"}):
            response = await self.client.get("/ready", headers=headers)
            self.assertEqual(response.status_code, 401)
        self.provider_factory.assert_not_called()
        self.probe_client.get.assert_not_called()

    async def test_ready_without_generating_or_calling_tools(self):
        response = await self.client.get("/ready", headers=self.headers)
        self.assertEqual(response.json(), {"available": True})
        self.provider.close.assert_awaited_once()
        self.engine.run.assert_not_called()
        self.assertEqual(self.provider_factory.call_args.kwargs["session"].get_secret_value(), self.headers["X-DisplayQuest-Session"])
        self.assertEqual(self.probe_client.get.call_args.args, ("http://model/v1/models",))

    async def test_model_offline_is_unavailable(self):
        self.probe_client.get.side_effect = httpx.ConnectError("offline")
        response = await self.client.get("/ready", headers=self.headers)
        self.assertEqual(response.json(), {"available": False})
        self.provider.close.assert_awaited_once()

    async def test_configured_model_must_be_served(self):
        self.probe_client.get.return_value = httpx.Response(
            200, json={"data": [{"id": "other-model"}]}, request=httpx.Request("GET", "http://model/v1/models"),
        )
        self.assertEqual((await self.client.get("/ready", headers=self.headers)).json(), {"available": False})

    async def test_mcp_failure_is_unavailable_and_always_closed(self):
        self.provider.connect.side_effect = RuntimeError("offline")
        response = await self.client.get("/ready", headers=self.headers)
        self.assertEqual(response.json(), {"available": False})
        self.provider.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
