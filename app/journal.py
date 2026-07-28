"""Append-only JSONL event log per call, so a crash mid-call doesn't lose
context about what had already happened (matches Ascolto's crash-safety design)."""

import json
from datetime import datetime, timezone
from pathlib import Path


def append_event(out_dir: Path, event: str, **fields):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    journal_path = out_dir / "journal.jsonl"
    with open(journal_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
