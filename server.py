import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

mcp = FastMCP("universal-mcp-server")
CONFIG_PATH = Path(__file__).with_name("mcp_routing_config.json")
DASHBOARD_DIR = Path(__file__).with_name("dashboard")
ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
SENSITIVE_ARG = re.compile(r"(?i)^--?(?:api[-_]?key|access[-_]?token|password|secret|token)(?:=|$)")
SERVER_STATS: dict[str, dict[str, Any]] = {}
STATS_LOCK = threading.Lock()


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


def configured_env(value: str) -> bool:
    references = ENV_REFERENCE.findall(value)
    if references:
        return all(os.environ.get(name) for name in references)
    return bool(value)


def display_args(args: list[str]) -> list[str]:
    redacted_args = []
    redact_next = False
    for arg in args:
        if redact_next:
            redacted_args.append("[redacted]")
            redact_next = False
        elif SENSITIVE_ARG.match(arg):
            if "=" in arg:
                redacted_args.append(f"{arg.split('=', 1)[0]}=[redacted]")
            else:
                redacted_args.append(arg)
                redact_next = True
        else:
            redacted_args.append(arg)
    return redacted_args


def record_call(server_name: str, succeeded: bool, latency_ms: float) -> None:
    with STATS_LOCK:
        stats = SERVER_STATS.setdefault(
            server_name,
            {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "total_latency_ms": 0.0,
                "last_latency_ms": None,
                "last_call_at": None,
            },
        )
        stats["calls"] += 1
        stats["successes" if succeeded else "failures"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["last_latency_ms"] = round(latency_ms, 1)
        stats["last_call_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def dashboard_data() -> dict[str, Any]:
    servers = load_managed_servers()
    with STATS_LOCK:
        stats_snapshot = {name: values.copy() for name, values in SERVER_STATS.items()}

    server_rows = []
    for name, spec in servers.items():
        stats = stats_snapshot.get(name, {})
        env_vars = [
            {"name": key, "configured": configured_env(value)}
            for key, value in spec.get("env", {}).items()
        ]
        calls = stats.get("calls", 0)
        server_rows.append(
            {
                "name": name,
                "command": spec["command"],
                "args": display_args(spec.get("args", [])),
                "env": env_vars,
                "stats": {
                    "calls": calls,
                    "successes": stats.get("successes", 0),
                    "failures": stats.get("failures", 0),
                    "average_latency_ms": round(stats["total_latency_ms"] / calls, 1)
                    if calls
                    else None,
                    "last_latency_ms": stats.get("last_latency_ms"),
                    "last_call_at": stats.get("last_call_at"),
                },
            }
        )

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "servers": server_rows,
        "totals": {
            "servers": len(server_rows),
            "calls": sum(row["stats"]["calls"] for row in server_rows),
            "failures": sum(row["stats"]["failures"] for row in server_rows),
        },
    }


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
    started_at = time.perf_counter()
    try:
        process_env = os.environ.copy()
        process_env.update(
            {key: resolve_env_value(value) for key, value in spec.get("env", {}).items()}
        )
        transport = StdioTransport(
            command=spec["command"],
            args=spec.get("args", []),
            env=process_env,
        )

        async with Client(transport) as client:
            result = await client.call_tool(tool_name, arguments or {})
    except Exception:
        record_call(server_name, False, (time.perf_counter() - started_at) * 1000)
        raise

    succeeded = not bool(getattr(result, "isError", False))
    record_call(server_name, succeeded, (time.perf_counter() - started_at) * 1000)
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def dashboard_index(request: Request) -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@mcp.custom_route("/dashboard.css", methods=["GET"], include_in_schema=False)
async def dashboard_styles(request: Request) -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "dashboard.css")


@mcp.custom_route("/dashboard.js", methods=["GET"], include_in_schema=False)
async def dashboard_script(request: Request) -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "dashboard.js")


@mcp.custom_route("/api/dashboard", methods=["GET"], include_in_schema=False)
async def dashboard_api(request: Request) -> JSONResponse:
    try:
        return JSONResponse(dashboard_data())
    except (RuntimeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    mcp.run()