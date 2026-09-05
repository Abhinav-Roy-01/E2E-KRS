"""Ground-truth logger for intentionally planted data issues.

All seed scripts append to conflicts_seeded.json so the ETL/dedup layer built
later can be validated against exactly what was planted (and it doubles as the
"proof of detection" slide for judges).

Sections:
  - cross_source_conflicts  : same institute contradicts itself across sources
  - within_source_duplicates: duplicate / near-duplicate rows inside one source
  - orphaned_records        : rows referencing institutes that don't exist anywhere
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SECTIONS = ("cross_source_conflicts", "within_source_duplicates", "orphaned_records")


def _path(p: str | Path) -> Path:
    return Path(p)


def reset(path: str | Path) -> dict:
    data = {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "note": "ground truth of deliberately planted issues"},
        "cross_source_conflicts": [],
        "within_source_duplicates": [],
        "orphaned_records": [],
    }
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _load(path: str | Path) -> dict:
    p = _path(path)
    if not p.exists():
        return reset(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return reset(path)
    for s in SECTIONS:
        data.setdefault(s, [])
    return data


def add(path: str | Path, entry: dict) -> None:
    data = _load(path)
    etype = entry.get("type")
    if etype == "cross_source_conflict":
        data["cross_source_conflicts"].append(entry)
    elif etype == "within_source_duplicate":
        data["within_source_duplicates"].append(entry)
    elif etype == "orphaned_record":
        data["orphaned_records"].append(entry)
    else:
        data.setdefault("other", []).append(entry)
    _path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load(path: str | Path) -> dict:
    return _load(path)
