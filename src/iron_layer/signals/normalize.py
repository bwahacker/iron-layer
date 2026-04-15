"""
Convert raw tool_use blocks (name + args dict) into canonical Signal records.

Design goals:
- Stable label space: different argument shapes for the same intent → same target string
- Canonicalised paths: collapse //, resolve .., lowercase
- URLs: extract host+path only (drop query/fragment to avoid noise)
- Commands: extract argv[0] only
"""
from __future__ import annotations

import posixpath
import re
from urllib.parse import urlparse

from iron_layer.signals.schema import TOOL_BUCKETS, Signal


def _canon_path(raw: str) -> str:
    """Normalise a filesystem path for use as a signal target."""
    if not raw:
        return ""
    # Expand ~ and resolve .. segments
    p = raw.strip()
    p = p.replace("\\", "/")
    # Collapse duplicate slashes, resolve ..
    parts = p.split("/")
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if resolved:
                resolved.pop()
        elif part not in ("", "."):
            resolved.append(part)
    # Preserve leading slash
    canon = ("/" if p.startswith("/") else "") + "/".join(resolved)
    return canon.lower()


def _canon_url(raw: str) -> str:
    """Extract scheme+host+path from a URL for use as a signal target."""
    if not raw:
        return ""
    try:
        p = urlparse(raw if "://" in raw else "https://" + raw)
        host = (p.hostname or "").lower()
        path = posixpath.normpath(p.path or "/")
        return f"{host}{path}"
    except Exception:
        return raw[:200].lower()


def _canon_cmd(raw: str) -> str:
    """Extract the first token (argv[0]) from a shell command string."""
    if not raw:
        return ""
    # Strip leading shell operators, env-var assignments
    cmd = raw.strip().lstrip("$").strip()
    # Drop env var assignments like FOO=bar COMMAND ...
    cmd = re.sub(r'^(\w+=\S+\s+)+', '', cmd)
    first = cmd.split()[0] if cmd.split() else cmd
    return first.lower()


def _extract_markdown_urls(text: str) -> list[str]:
    """Pull URLs from markdown image and link syntax in assistant text output."""
    urls: list[str] = []
    # ![alt](url) and [text](url)
    for m in re.finditer(r'\]\(([^)]+)\)', text):
        u = m.group(1).strip()
        if u.startswith("http"):
            urls.append(_canon_url(u))
    # Bare http(s):// URLs
    for m in re.finditer(r'https?://\S+', text):
        u = re.sub(r'[)\]>.,;!?\'\"]+$', '', m.group(0))
        urls.append(_canon_url(u))
    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def normalize_tool_call(
    tool_name: str,
    tool_args: dict,
    turn: int,
) -> Signal | None:
    """
    Turn a single tool_use block into a Signal, or None if the tool is unknown.
    """
    bucket = TOOL_BUCKETS.get(tool_name)
    if bucket is None:
        # Unknown tool: create a catch-all signal under "unknown"
        bucket = "unknown"

    # Derive a canonical target from the most meaningful argument
    target = _derive_target(tool_name, tool_args)

    return Signal(
        bucket=bucket,
        tool=tool_name,
        target=target,
        raw_args=tool_args,
        turn=turn,
    )


def _derive_target(tool_name: str, args: dict) -> str:
    """Pick and canonicalise the primary argument for a tool call."""
    if tool_name in ("read_file", "write_file", "list_directory"):
        raw = args.get("path", args.get("file", ""))
        return _canon_path(str(raw))

    if tool_name in ("execute", "bash"):
        raw = args.get("cmd", args.get("command", args.get("code", "")))
        return _canon_cmd(str(raw))

    if tool_name == "fetch":
        raw = args.get("url", "")
        return _canon_url(str(raw))

    if tool_name == "send_email":
        return str(args.get("to", "")).lower()

    if tool_name == "db_query":
        q = str(args.get("query", "")).lower().strip()
        # Just first 120 chars to keep label readable
        return q[:120]

    if tool_name == "read_env":
        return str(args.get("var", args.get("name", ""))).upper()

    if tool_name in ("get_api_key",):
        return str(args.get("service", args.get("name", ""))).lower()

    if tool_name == "list_users":
        return "(all)"

    # Fallback: stringify first arg value
    if args:
        first_val = next(iter(args.values()), "")
        return str(first_val)[:120].lower()

    return ""
