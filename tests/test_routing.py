import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import server


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "mcp_routing_config.json"
        self.config_patcher = patch.object(server, "CONFIG_PATH", self.config_path)
        self.config_patcher.start()
        self.addCleanup(self.config_patcher.stop)

    def write_config(self, managed_servers: dict[str, object]) -> None:
        self.config_path.write_text(
            json.dumps({"managed_servers": managed_servers}),
            encoding="utf-8",
        )

    def test_lists_configured_server_names(self) -> None:
        self.write_config({"weather-service": {"command": "uv", "args": []}})

        self.assertEqual(server.list_available_sub_tools(), ["weather-service"])

    async def test_routes_call_with_configured_stdio_transport(self) -> None:
        self.write_config(
            {
                "weather-service": {
                    "command": "uv",
                    "args": ["run", "weather-mcp-server"],
                    "env": {"WEATHER_API_KEY": "${WEATHER_API_KEY}"},
                }
            }
        )
        downstream_result = {"content": [{"type": "text", "text": "sunny"}]}
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.call_tool = AsyncMock(
            return_value=SimpleNamespace(
                model_dump=lambda **kwargs: downstream_result,
            )
        )

        with (
            patch.dict(os.environ, {"WEATHER_API_KEY": "test-key"}),
            patch.object(server, "StdioTransport") as transport_factory,
            patch.object(server, "Client", return_value=client),
        ):
            result = await server.route_mcp_call(
                "weather-service",
                "get_forecast",
                {"city": "Reykjavik"},
            )

        transport_factory.assert_called_once()
        transport_options = transport_factory.call_args.kwargs
        self.assertEqual(transport_options["command"], "uv")
        self.assertEqual(transport_options["args"], ["run", "weather-mcp-server"])
        self.assertEqual(transport_options["env"]["WEATHER_API_KEY"], "test-key")
        client.call_tool.assert_awaited_once_with("get_forecast", {"city": "Reykjavik"})
        self.assertEqual(result, downstream_result)

    async def test_rejects_unconfigured_server(self) -> None:
        self.write_config({"weather-service": {"command": "uv"}})

        with self.assertRaisesRegex(ValueError, "Unknown managed server"):
            await server.route_mcp_call("unknown", "some_tool")


if __name__ == "__main__":
    unittest.main()