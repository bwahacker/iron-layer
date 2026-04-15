"""
JSONL writer — appends one Detonation record per line to an output file.
"""
from __future__ import annotations

import json
from pathlib import Path

from iron_layer.signals.schema import Detonation


def write_detonation(det: Detonation, out_path: Path) -> None:
    """Append a single detonation record as a JSONL line."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as fh:
        fh.write(json.dumps(det.to_dict()) + "\n")
