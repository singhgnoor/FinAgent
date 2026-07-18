"""Small transactional JSON-list store used by the demo's file-backed state.

The lock is process-safe on Windows (and uses ``fcntl`` on POSIX), while the
write path uses atomic replace so readers never observe partial JSON.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List


@contextmanager
def _exclusive_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lock_file:
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0)
            lock_file.write(b"0")
            lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def update_json_list(path: Path, mutator: Callable[[List[Any]], None]) -> List[Any]:
    """Apply a read-modify-write update under a process lock and return it."""
    with _exclusive_lock(path):
        try:
            items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if not isinstance(items, list):
                items = []
        except (json.JSONDecodeError, OSError):
            items = []
        mutator(items)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")
        os.replace(temporary, path)
        return items


def read_json_list(path: Path) -> List[Any]:
    with _exclusive_lock(path):
        if not path.exists():
            return []


def update_json_object(path: Path, mutator: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    """Atomic, process-safe read-modify-write for JSON object state."""
    with _exclusive_lock(path):
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not isinstance(value, dict):
                value = {}
        except (json.JSONDecodeError, OSError):
            value = {}
        mutator(value)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        os.replace(temporary, path)
        return value
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            return items if isinstance(items, list) else []
        except (json.JSONDecodeError, OSError):
            return []
