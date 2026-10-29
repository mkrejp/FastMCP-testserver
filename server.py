import json
import os
import re
from pathlib import Path
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport

mcp = FastMCP("universal-mcp-server")
CONFIG_PATH = Path(__file__).with_name("mcp_routing_config.json")
ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_managed_servers() -> dict[str, dict[str, Any]]:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Routing config not found: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in routing config: {exc}") from exc

    if not isinstance(config, dict) or not isinstance(config.get("managed_servers"), dict):
        raise ValueError("Routing config must contain a 'managed_servers' object.")

    servers = config["managed_servers"]
    for name, spec in servers.items():
        if not isinstance(name, str) or not name:
            raise ValueError("Managed server names must be non-empty strings.")
        if not isinstance(spec, dict) or not isinstance(spec.get("command"), str):
            raise ValueError(f"Managed server '{name}' must define a command string.")
        if not spec["command"]:
            raise ValueError(f"Managed server '{name}' command cannot be empty.")
        args = spec.get("args", [])
        env = spec.get("env", {})
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError(f"Managed server '{name}' args must be a list of strings.")
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in env.items()
        ):
            raise ValueError(f"Managed server '{name}' env must map strings to strings.")

    return servers


def resolve_env_value(value: str) -> str:
    def replace_reference(match: re.Match[str]) -> str:
        variable = match.group(1)
        resolved = os.environ.get(variable)
        if resolved is None:
            raise ValueError(f"Environment variable '{variable}' is required by routing config.")
        return resolved

    return ENV_REFERENCE.sub(replace_reference, value)


@mcp.tool()
def list_available_sub_tools() -> list[str]:
    """List the configured downstream MCP server names."""
    return list(load_managed_servers())


@mcp.tool()
async def route_mcp_call(
    server_name: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a tool on a configured downstream MCP server over stdio."""
    servers = load_managed_servers()
    if server_name not in servers:
        available = ", ".join(servers) or "none"
        raise ValueError(f"Unknown managed server '{server_name}'. Available servers: {available}.")

    spec = servers[server_name]
    process_env = os.environ.copy()
    process_env.update({key: resolve_env_value(value) for key, value in spec.get("env", {}).items()})
    transport = StdioTransport(
        command=spec["command"],
        args=spec.get("args", []),
        env=process_env,
    )

    async with Client(transport) as client:
        result = await client.call_tool(tool_name, arguments or {})
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


if __name__ == "__main__":
    mcp.run()