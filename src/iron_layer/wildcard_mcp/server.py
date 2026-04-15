"""
Wildcard MCP server.

Runs as a stdio MCP process. Advertises the fixed toolbelt, handles every
tool call by:
  1. Appending the call to an event log written to a temp file
  2. Returning a plausible fake result

The canary runner reads the event log file after the detonation completes.

Usage (subprocess):
    python -m iron_layer.wildcard_mcp.server --log-file /tmp/some.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types as mcp_types

from iron_layer.wildcard_mcp.tools import TOOL_DEFINITIONS
from iron_layer.wildcard_mcp.fake_results import get_fake_result


def _make_server(log_path: Path) -> Server:
    server = Server("iron-layer-wildcard")

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[mcp_types.TextContent]:
        # 1. Log the call
        record = {"tool": name, "args": arguments}
        with log_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

        # 2. Return fake result
        result_text = get_fake_result(name, arguments)
        return [mcp_types.TextContent(type="text", text=result_text)]

    return server


async def _run(log_path: Path) -> None:
    server = _make_server(log_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Iron Layer wildcard MCP server")
    parser.add_argument(
        "--log-file",
        required=True,
        help="Path to the JSONL file where tool calls are logged",
    )
    args = parser.parse_args()
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Clear any previous log for this run
    log_path.write_text("")

    asyncio.run(_run(log_path))


if __name__ == "__main__":
    main()
