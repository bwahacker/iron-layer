"""
iron-layer CLI

Commands:
  detonate --text "..."         one-shot detonation from a string
  detonate --file path.txt      one-shot detonation from a file
  batch --corpus DIR --out FILE batch detonation over a corpus
  replay --id sha256:...        replay a single input from a prior batch
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="iron-layer",
    help="Prompt-injection honeypot labeler — generate (prompt → signal) pairs for Featrix.",
    add_completion=False,
)

detonate_app = typer.Typer(help="Run a single detonation.")
app.add_typer(detonate_app, name="detonate")


@app.command("detonate")
def cmd_detonate(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Inline text to detonate."),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to a text file to detonate."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Detonate a single untrusted text and print the detonation record."""
    if text is None and file is None:
        typer.echo("Error: provide --text or --file.", err=True)
        raise typer.Exit(1)
    if text is None:
        if not file.exists():
            typer.echo(f"Error: file not found: {file}", err=True)
            raise typer.Exit(1)
        text = file.read_text(encoding="utf-8", errors="replace")

    from iron_layer.canary.runner import detonate

    typer.echo(f"Detonating ({len(text)} chars) …", err=True)
    det = detonate(text)

    record = det.to_dict()
    if pretty:
        typer.echo(json.dumps(record, indent=2))
    else:
        typer.echo(json.dumps(record))

    # Summary to stderr
    typer.echo(
        f"\nResult: {det.n_tool_calls} tool calls, "
        f"{len(det.signals)} signals, "
        f"stop={det.stop_reason}",
        err=True,
    )
    if det.signals:
        typer.echo("Signals:", err=True)
        for s in det.signals:
            typer.echo(f"  [{s.bucket}] {s.tool}({s.target!r})", err=True)
    if det.markdown_urls:
        typer.echo(f"Markdown URLs: {det.markdown_urls}", err=True)


@app.command("batch")
def cmd_batch(
    corpus: Path = typer.Option(..., "--corpus", "-c", help="Directory or JSONL file of inputs."),
    out: Path = typer.Option(..., "--out", "-o", help="Output JSONL file for detonation records."),
    concurrency: int = typer.Option(5, "--concurrency", "-j", help="Max parallel detonations."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output."),
) -> None:
    """Batch-detonate a corpus and write labelled JSONL for Featrix."""
    if not corpus.exists():
        typer.echo(f"Error: corpus path not found: {corpus}", err=True)
        raise typer.Exit(1)

    from iron_layer.pipeline.batch import run_batch

    typer.echo(f"Batch detonation: corpus={corpus}  out={out}  concurrency={concurrency}", err=True)
    n = run_batch(corpus, out, max_concurrent=concurrency, progress=not quiet)
    typer.echo(f"Done. {n} detonations written to {out}", err=True)


@app.command("replay")
def cmd_replay(
    id: str = typer.Option(..., "--id", help="sha256:... ID of the input to replay."),
    source: Path = typer.Option(..., "--source", "-s", help="JSONL batch file to find the input in."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Re-detonate a single input from a prior batch output file."""
    if not source.exists():
        typer.echo(f"Error: source file not found: {source}", err=True)
        raise typer.Exit(1)

    target_text: str | None = None
    with source.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("id") == id:
                    target_text = obj.get("input_text", "")
                    break
            except json.JSONDecodeError:
                continue

    if target_text is None:
        typer.echo(f"Error: ID {id!r} not found in {source}", err=True)
        raise typer.Exit(1)

    from iron_layer.canary.runner import detonate

    typer.echo(f"Replaying {id} ({len(target_text)} chars) …", err=True)
    det = detonate(target_text)
    record = det.to_dict()
    if pretty:
        typer.echo(json.dumps(record, indent=2))
    else:
        typer.echo(json.dumps(record))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
