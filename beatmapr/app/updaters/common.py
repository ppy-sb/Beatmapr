from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "PACK_BATCH_SIZE",
    "USERS_PAGE_LIMIT",
    "USERS_BATCH_SIZE",
    "USERS_MAX_RETRIES",
    "PROJECT_ROOT",
    "DEFAULT_JSON_ROOTS",
    "discover_json_files",
    "chunked",
    "parse_datetime",
    "safe_float",
    "safe_int",
]


PACK_BATCH_SIZE = 10
USERS_PAGE_LIMIT = 100
USERS_BATCH_SIZE = 10
USERS_MAX_RETRIES = 3

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON_ROOTS: tuple[Path, ...] = tuple(dict.fromkeys((PROJECT_ROOT, PROJECT_ROOT / "data")))


def discover_json_files(candidates: Sequence[str], search_roots: Sequence[Path] | None = None) -> list[Path]:
    roots = list(search_roots) if search_roots is not None else list(DEFAULT_JSON_ROOTS)
    seen: dict[Path, Path] = {}

    for root in roots:
        try:
            resolved_root = root.resolve()
        except FileNotFoundError:
            resolved_root = root
        if not resolved_root.exists():
            continue

        for name in candidates:
            candidate = resolved_root / name
            if candidate.exists() and candidate.suffix.lower() == ".json":
                seen[candidate.resolve()] = candidate

    return sorted(seen.values())


def chunked(sequence: Sequence[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(sequence), size):
        yield list(sequence[index : index + size])


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
