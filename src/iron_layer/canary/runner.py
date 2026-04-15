"""
Canary detonation runner.

Runs one untrusted text through the honeypot LLM + wildcard MCP server and
returns a Detonation record capturing every tool call and markdown URL the
text tried to elicit.

Architecture:
  - Spawns wildcard MCP server as a subprocess writing to a temp log file
  - Drives the Anthropic API in a multi-turn loop (up to MAX_TURNS)
  - After each assistant turn, scans raw text for markdown exfil URLs
  - After the loop, reads the MCP log and normalises signals
  - Returns a Detonation (never raises; catches all errors as stop_reason)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic

from iron_layer.canary.system_prompt import CANARY_SYSTEM_PROMPT
from iron_layer.signals.normalize import (
    normalize_tool_call,
    _extract_markdown_urls,
)
from iron_layer.signals.schema import Detonation, Signal
from iron_layer.wildcard_mcp.tools import TOOL_DEFINITIONS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANARY_MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 6
MAX_TOOL_CALLS = 20
MAX_TOKENS = 1024  # keep canary responses short


def _input_id(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _build_tool_schemas() -> list[dict]:
    """Convert tool definitions to Anthropic tool_use format."""
    tools = []
    for t in TOOL_DEFINITIONS:
        tools.append(
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["inputSchema"],
            }
        )
    return tools


_TOOL_SCHEMAS = _build_tool_schemas()


# ---------------------------------------------------------------------------
# MCP subprocess management
# ---------------------------------------------------------------------------

class _MCPProcess:
    """Manages the wildcard MCP subprocess and its log file."""

    def __init__(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False, prefix="iron_layer_mcp_"
        )
        self.log_path = Path(self._tmp.name)
        self._tmp.close()
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        self._proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "iron_layer.wildcard_mcp.server",
                "--log-file",
                str(self.log_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                pass

    def read_calls(self) -> list[dict]:
        """Read all tool calls logged during this detonation."""
        if not self.log_path.exists():
            return []
        calls = []
        for line in self.log_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    calls.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return calls

    def cleanup(self) -> None:
        try:
            self.log_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Detonation loop  (synchronous — uses the sync Anthropic client)
# ---------------------------------------------------------------------------

def _call_mcp_tool(mcp: _MCPProcess, tool_name: str, tool_input: dict) -> str:
    """
    Forward a tool_use call to the MCP server via its log mechanism.

    Because we're running the MCP server as a subprocess that speaks stdio
    MCP protocol, the simplest approach for the detonation loop is to:
      1. Write the tool call directly to the log (so we don't need to drive
         the full MCP wire protocol from here)
      2. Ask the fake_results module for the synthetic response

    The MCP server subprocess is still started (it keeps the MCP protocol
    wiring alive for future work), but during a detonation we talk to
    fake_results directly to get the result. Calls still appear in the log
    because we write them ourselves below.
    """
    from iron_layer.wildcard_mcp.fake_results import get_fake_result

    # Log the call so read_calls() picks it up
    record = {"tool": tool_name, "args": tool_input}
    with mcp.log_path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")

    return get_fake_result(tool_name, tool_input)


def detonate(input_text: str) -> Detonation:
    """
    Run one untrusted text through the honeypot and return a Detonation.

    This is the main entry point for the labeling pipeline.
    """
    det = Detonation(
        id=_input_id(input_text),
        input_text=input_text,
        canary_model=CANARY_MODEL,
    )

    mcp = _MCPProcess()
    # Start the MCP subprocess (kept alive for tooling / future wire-protocol use)
    mcp.start()

    client = anthropic.Anthropic()

    messages: list[dict] = [
        {"role": "user", "content": input_text}
    ]

    tool_call_count = 0
    turn = 0

    try:
        while turn < MAX_TURNS and tool_call_count < MAX_TOOL_CALLS:
            response = client.messages.create(
                model=CANARY_MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": CANARY_SYSTEM_PROMPT,
                        # Cache the system prompt + tools across the batch
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=_TOOL_SCHEMAS,
                messages=messages,
            )

            stop_reason = response.stop_reason
            assistant_content = response.content

            # Append assistant turn to history
            messages.append({"role": "assistant", "content": assistant_content})

            # Scan assistant text for markdown exfil URLs
            for block in assistant_content:
                if hasattr(block, "type") and block.type == "text":
                    urls = _extract_markdown_urls(block.text)
                    det.markdown_urls.extend(urls)

            if stop_reason != "tool_use":
                det.stop_reason = stop_reason or "end_turn"
                break

            # Collect tool_use blocks and build tool_result reply
            tool_results = []
            for block in assistant_content:
                if not (hasattr(block, "type") and block.type == "tool_use"):
                    continue

                tool_call_count += 1
                tool_name = block.name
                tool_input = block.input if isinstance(block.input, dict) else {}

                fake_result = _call_mcp_tool(mcp, tool_name, tool_input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": fake_result,
                    }
                )

            if not tool_results:
                det.stop_reason = "end_turn"
                break

            messages.append({"role": "user", "content": tool_results})
            turn += 1

        else:
            det.stop_reason = "max_turns" if turn >= MAX_TURNS else "max_tool_calls"

    except Exception as exc:
        det.stop_reason = f"error:{type(exc).__name__}:{exc}"
    finally:
        mcp.stop()

    # Build Signal objects from the MCP call log
    raw_calls = mcp.read_calls()
    det.n_tool_calls = len(raw_calls)

    for i, call in enumerate(raw_calls):
        sig = normalize_tool_call(
            tool_name=call.get("tool", "unknown"),
            tool_args=call.get("args", {}),
            turn=i,  # use call index as turn proxy
        )
        if sig:
            det.signals.append(sig)

    mcp.cleanup()
    return det
