from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Canonical intent buckets — these become the label columns Featrix trains on.
BUCKET_FILESYSTEM_READ = "filesystem-read"
BUCKET_FILESYSTEM_WRITE = "filesystem-write"
BUCKET_FILESYSTEM_ENUM = "filesystem-enum"
BUCKET_CODE_EXEC = "code-exec"
BUCKET_NETWORK_EGRESS = "network-egress"
BUCKET_EXFIL_EMAIL = "exfil-email"
BUCKET_DATA_ACCESS = "data-access"
BUCKET_SECRET_ACCESS = "secret-access"
BUCKET_CRED_ENUM = "cred-enum"
BUCKET_CRED_ACCESS = "cred-access"

# Tool name → bucket mapping (used by normalize.py)
TOOL_BUCKETS: dict[str, str] = {
    "read_file": BUCKET_FILESYSTEM_READ,
    "write_file": BUCKET_FILESYSTEM_WRITE,
    "list_directory": BUCKET_FILESYSTEM_ENUM,
    "execute": BUCKET_CODE_EXEC,
    "bash": BUCKET_CODE_EXEC,
    "fetch": BUCKET_NETWORK_EGRESS,
    "send_email": BUCKET_EXFIL_EMAIL,
    "db_query": BUCKET_DATA_ACCESS,
    "read_env": BUCKET_SECRET_ACCESS,
    "list_users": BUCKET_CRED_ENUM,
    "get_api_key": BUCKET_CRED_ACCESS,
}


@dataclass
class Signal:
    """One normalised tool-call signal from a detonation."""
    bucket: str           # intent bucket, e.g. "filesystem-read"
    tool: str             # exact tool name invoked
    target: str           # canonicalised primary argument
    raw_args: dict[str, Any]  # full args for debugging
    turn: int             # which conversation turn (0-indexed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "tool": self.tool,
            "target": self.target,
            "turn": self.turn,
        }


@dataclass
class Detonation:
    """Full result of running one untrusted input through the honeypot."""
    id: str                          # sha256 hex of input_text
    input_text: str
    signals: list[Signal] = field(default_factory=list)
    markdown_urls: list[str] = field(default_factory=list)
    n_tool_calls: int = 0
    stop_reason: str = "unknown"
    canary_model: str = ""
    detonated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "input_text": self.input_text,
            "signals": [s.to_dict() for s in self.signals],
            "markdown_urls": self.markdown_urls,
            "n_tool_calls": self.n_tool_calls,
            "stop_reason": self.stop_reason,
            "canary_model": self.canary_model,
            "detonated_at": self.detonated_at,
        }
