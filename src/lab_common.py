"""Shared UTF-8 artifact helpers; no credentials in public artifacts."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    path = Path(path)
    return json.loads((path if path.is_absolute() else ROOT / path).read_text(encoding="utf-8-sig"))

def write_json(path, value):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path

def read_jsonl(path):
    path=Path(path)
    if not path.is_absolute(): path=ROOT/path
    return [json.loads(s) for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()]

def write_jsonl(path, rows):
    path=Path(path)
    if not path.is_absolute(): path=ROOT/path
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8',newline='\n')
    return path
