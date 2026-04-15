"""
Batch runner — fans out detonations over a corpus of input texts.

Inputs can be:
  - A directory of .txt files
  - A JSONL file where each line is {"id": ..., "text": ...}
  - A plain text file (treated as a single input)

Concurrency is bounded by MAX_CONCURRENT to avoid hammering the API.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Iterator

from iron_layer.canary.runner import detonate
from iron_layer.pipeline.writer import write_detonation
from iron_layer.signals.schema import Detonation

MAX_CONCURRENT = 5


# ---------------------------------------------------------------------------
# Corpus readers
# ---------------------------------------------------------------------------

def _iter_corpus(corpus_path: Path) -> Iterator[tuple[str, str]]:
    """
    Yield (id, text) pairs from a corpus path.

    - Directory → each *.txt file is one item
    - *.jsonl file → each line must be {"text": ..., "id": ...} (id optional)
    - Any other file → single item (whole file content)
    """
    if corpus_path.is_dir():
        for txt_file in sorted(corpus_path.glob("*.txt")):
            text = txt_file.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                yield txt_file.stem, text
        return

    if corpus_path.suffix == ".jsonl":
        with corpus_path.open() as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    text = obj.get("text", obj.get("input_text", ""))
                    item_id = obj.get("id", str(i))
                    if text:
                        yield item_id, text
                except json.JSONDecodeError:
                    # Treat the raw line as the text
                    yield str(i), line
        return

    # Single file
    text = corpus_path.read_text(encoding="utf-8", errors="replace").strip()
    if text:
        yield corpus_path.stem, text


# ---------------------------------------------------------------------------
# Async batch runner
# ---------------------------------------------------------------------------

async def _detonate_async(text: str) -> Detonation:
    """Run detonate() in a thread pool so the async loop stays responsive."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, detonate, text)


async def _run_batch(
    corpus_path: Path,
    out_path: Path,
    max_concurrent: int,
    progress: bool,
) -> int:
    """Return the number of detonations completed."""
    items = list(_iter_corpus(corpus_path))
    if not items:
        return 0

    sem = asyncio.Semaphore(max_concurrent)
    completed = 0

    async def _bounded(item_id: str, text: str) -> None:
        nonlocal completed
        async with sem:
            if progress:
                print(f"  detonating {item_id!r} …", file=sys.stderr)
            det = await _detonate_async(text)
            write_detonation(det, out_path)
            completed += 1
            if progress:
                sig_summary = ", ".join(
                    f"{s.bucket}:{s.target}" for s in det.signals[:3]
                )
                print(
                    f"  → {item_id}: {det.n_tool_calls} calls, "
                    f"signals=[{sig_summary}{'…' if len(det.signals) > 3 else ''}]",
                    file=sys.stderr,
                )

    await asyncio.gather(*[_bounded(iid, txt) for iid, txt in items])
    return completed


def run_batch(
    corpus_path: Path,
    out_path: Path,
    max_concurrent: int = MAX_CONCURRENT,
    progress: bool = True,
) -> int:
    """Synchronous entry point for the CLI."""
    return asyncio.run(
        _run_batch(corpus_path, out_path, max_concurrent, progress)
    )
