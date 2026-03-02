"""JSONL trajectory logger for MVP."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class TrajectoryLogger:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
