from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from beatmapr.app.config import get_settings
from beatmapr.app.database import SessionLocal
from beatmapr.app.models import User

from .common import (
    DEFAULT_JSON_ROOTS,
    PROJECT_ROOT,
    USERS_BATCH_SIZE,
    USERS_MAX_RETRIES,
    USERS_PAGE_LIMIT,
    chunked,
    discover_json_files,
    parse_datetime,
    safe_int,
)

__all__ = [
    "USERS_PAGE_LIMIT",
    "USERS_BATCH_SIZE",
    "USERS_MAX_RETRIES",
    "UserImportSummary",
    "UserUpdater",
]

logger = logging.getLogger(__name__)

TOTAL_SCORES_PATTERN = re.compile(r"Total scores:\s*([\d.,]+)")


@dataclass
class UserImportSummary:
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    files: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def accumulate(self, other: "UserImportSummary") -> None:
        self.processed += other.processed
        self.inserted += other.inserted
        self.updated += other.updated
        self.skipped += other.skipped
        self.files.extend(other.files)
        self.errors.update(other.errors)


class UserUpdater:
    """Handle user data synchronisation and imports."""

    def __init__(self, session_factory: type[Session] | Any = SessionLocal) -> None:
        self._session_factory = session_factory

    async def sync_from_akatsuki(
        self,
        limit: int = USERS_PAGE_LIMIT,
        batch_size: int = USERS_BATCH_SIZE,
        max_retries: int = USERS_MAX_RETRIES,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("'limit' must be a positive integer")
        if batch_size <= 0:
            raise ValueError("'batch_size' must be a positive integer")
        if max_retries < 0:
            raise ValueError("'max_retries' cannot be negative")

        settings = get_settings()
        base_url = settings.akatsuki_base_url.rstrip("/")
        endpoint = f"{base_url}/users"

        summary: dict[str, Any] = {
            "start_page": 1,
            "pages_requested": 0,
            "processed_users": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed_pages": [],
            "retries": 0,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            with self._session_factory() as session:  # type: ignore[call-arg]
                existing_ids = set(session.execute(select(User.id)).scalars())
                existing_count = len(existing_ids)
                current_page = max(1, (existing_count // limit) + 1)
                summary["start_page"] = current_page

                failed_pages: set[int] = set()
                pages_consumed = 0
                finished = False

                while not finished:
                    pages_to_fetch: list[int] = []
                    for index in range(batch_size):
                        if max_pages is not None and pages_consumed >= max_pages:
                            break
                        pages_to_fetch.append(current_page + index)
                        pages_consumed += 1

                    if not pages_to_fetch:
                        break

                    results = await asyncio.gather(*(_fetch_user_page(client, endpoint, pg, limit) for pg in pages_to_fetch))
                    any_full = False

                    try:
                        for page_number, users_payload, error in results:
                            if error or users_payload is None:
                                failed_pages.add(page_number)
                                continue

                            if not users_payload:
                                continue

                            inserted, updated, skipped = _persist_user_batch(session, users_payload, existing_ids)
                            summary["inserted"] += inserted
                            summary["updated"] += updated
                            summary["skipped"] += skipped
                            summary["processed_users"] += len(users_payload)

                            if len(users_payload) >= limit:
                                any_full = True

                        session.commit()
                    except Exception:  # noqa: BLE001
                        session.rollback()
                        raise

                    summary["pages_requested"] += len(pages_to_fetch)

                    if not any_full:
                        finished = True
                    elif max_pages is not None and pages_consumed >= max_pages:
                        finished = True
                    else:
                        current_page += batch_size

                retries = 0
                while failed_pages and retries < max_retries:
                    retries += 1
                    summary["retries"] = retries

                    retry_results = await asyncio.gather(*(_fetch_user_page(client, endpoint, pg, limit) for pg in sorted(failed_pages)))

                    succeeded: set[int] = set()
                    try:
                        for page_number, users_payload, error in retry_results:
                            if error or users_payload is None:
                                continue

                            if not users_payload:
                                succeeded.add(page_number)
                                continue

                            inserted, updated, skipped = _persist_user_batch(session, users_payload, existing_ids)
                            summary["inserted"] += inserted
                            summary["updated"] += updated
                            summary["skipped"] += skipped
                            summary["processed_users"] += len(users_payload)
                            succeeded.add(page_number)

                        session.commit()
                    except Exception:  # noqa: BLE001
                        session.rollback()
                        raise

                    failed_pages.difference_update(succeeded)

                if failed_pages:
                    summary["failed_pages"] = sorted(failed_pages)

        return summary

    def update_totals_from_files(
        self,
        data_directory: str | Path | None = None,
        batch_size: int = 200,
    ) -> dict[str, Any]:
        if batch_size <= 0:
            raise ValueError("'batch_size' must be a positive integer")

        base_path = self._resolve_scores_directory(data_directory)

        summary: dict[str, Any] = {
            "data_directory": str(base_path),
            "users_considered": 0,
            "files_read": 0,
            "users_updated": 0,
            "missing_files": 0,
            "no_total_scores": 0,
        }

        if not base_path.exists():
            summary["error"] = "Data directory does not exist"
            return summary

        with self._session_factory() as session:  # type: ignore[call-arg]
            user_ids = list(session.execute(select(User.id).order_by(User.id.asc())).scalars())
            summary["users_considered"] = len(user_ids)

            for chunk in chunked(user_ids, batch_size):
                updated_in_chunk = False
                for user_id in chunk:
                    file_path = base_path / f"{user_id}_scores.txt"
                    if not file_path.exists():
                        summary["missing_files"] += 1
                        continue

                    try:
                        content = file_path.read_text(encoding="utf-8")
                    except OSError as exc:  # noqa: PERF203
                        logger.warning("Unable to read %s: %s", file_path, exc)
                        summary["no_total_scores"] += 1
                        continue

                    summary["files_read"] += 1
                    match = TOTAL_SCORES_PATTERN.search(content)
                    if not match:
                        summary["no_total_scores"] += 1
                        continue

                    numeric_text = match.group(1).replace(",", "")
                    total_scores = safe_int(float(numeric_text)) if numeric_text else None
                    if total_scores is None:
                        summary["no_total_scores"] += 1
                        continue

                    user = session.get(User, user_id)
                    if user is None:
                        summary["no_total_scores"] += 1
                        continue

                    if user.total_scores != total_scores:
                        user.total_scores = total_scores
                        updated_in_chunk = True
                        summary["users_updated"] += 1

                if updated_in_chunk:
                    try:
                        session.commit()
                    except Exception:  # noqa: BLE001
                        session.rollback()
                        raise

        return summary

    def import_from_json(
        self,
        file_path: Path,
    ) -> UserImportSummary:
        summary = UserImportSummary()
        summary.files.append(str(file_path))

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            summary.errors[str(file_path)] = str(exc)
            return summary

        if isinstance(data, dict):
            records = data.get("users") or data.get("data") or []
        else:
            records = data

        if not isinstance(records, list):
            summary.errors[str(file_path)] = "Unsupported JSON structure for user import"
            return summary

        with self._session_factory() as session:  # type: ignore[call-arg]
            for record in records:
                summary.processed += 1
                if not isinstance(record, dict):
                    summary.skipped += 1
                    continue

                user_id = safe_int(record.get("id"))
                if user_id is None:
                    summary.skipped += 1
                    continue

                user = session.get(User, user_id)
                if user is None:
                    user = User(id=user_id, username=str(record.get("username") or user_id))
                    session.add(user)
                    summary.inserted += 1
                else:
                    summary.updated += 1

                username = record.get("username")
                if username:
                    user.username = username

                country = record.get("country") or record.get("country_code")
                if country:
                    user.country = str(country)[:4]

                avatar_url = record.get("avatar_url") or record.get("avatar")
                if avatar_url:
                    user.avatar_url = str(avatar_url)

                total_scores = safe_int(record.get("total_scores"))
                if total_scores is not None:
                    user.total_scores = total_scores

                ranked_score = safe_int(record.get("ranked_score"))
                if ranked_score is not None:
                    user.ranked_score = ranked_score

                global_rank = safe_int(record.get("global_rank"))
                if global_rank is not None:
                    user.global_rank = global_rank

                last_activity = record.get("latest_activity") or record.get("last_refreshed_at")
                timestamp = parse_datetime(last_activity)
                if timestamp is not None:
                    user.last_refreshed_at = timestamp

            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
                raise

        return summary

    def import_from_path(self, location: Path | None, recursive: bool = False) -> UserImportSummary:
        summary = UserImportSummary()

        if location is None:
            candidates = discover_json_files(["users.json"])
        else:
            resolved = location.expanduser().resolve()
            if resolved.is_file():
                candidates = [resolved]
            elif resolved.is_dir():
                pattern = "**/*.json" if recursive else "*.json"
                candidates = sorted(p for p in resolved.glob(pattern) if p.is_file())
            else:
                summary.errors[str(resolved)] = "Specified path does not exist"
                return summary

        if not candidates:
            if location is None:
                summary.errors["auto"] = "No user JSON files found in default directories"
            else:
                summary.errors[str(location)] = "No JSON files found at the specified path"
            return summary

        for candidate in candidates:
            summary.accumulate(self.import_from_json(candidate))

        return summary

    @staticmethod
    def _resolve_scores_directory(target: str | Path | None) -> Path:
        if target is not None:
            return Path(target).expanduser().resolve()

        data_roots = [root / "scores" for root in DEFAULT_JSON_ROOTS]
        for candidate in data_roots:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                resolved = candidate
            if resolved.exists():
                return resolved

        fallback = PROJECT_ROOT / "data"
        return fallback.resolve() if fallback.exists() else fallback


async def _fetch_user_page(
    client: httpx.AsyncClient,
    endpoint: str,
    page: int,
    limit: int,
) -> tuple[int, list[dict[str, Any]] | None, Exception | None]:
    params = {"p": page, "l": limit}
    try:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        payload = response.json() or {}
        users_payload = payload.get("users") or payload.get("data") or []
        if not isinstance(users_payload, list):
            users_payload = []
        return page, users_payload, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch Akatsuki users page %s: %s", page, exc)
        return page, None, exc


def _persist_user_batch(
    session: Session,
    users_payload: Iterable[dict[str, Any]],
    seen_ids: set[int],
) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    skipped = 0

    for user_data in users_payload:
        raw_user_id = user_data.get("id")
        user_id = safe_int(raw_user_id)
        if user_id is None:
            skipped += 1
            continue

        user = session.get(User, user_id) if user_id in seen_ids else None
        if user is None:
            user = User(id=user_id, username=user_data.get("username") or str(user_id))
            session.add(user)
            seen_ids.add(user_id)
            inserted += 1
        else:
            updated += 1

        username = user_data.get("username")
        if username:
            user.username = username

        country = user_data.get("country") or user_data.get("country_code")
        if country:
            user.country = country

        avatar_url = user_data.get("avatar_url") or user_data.get("avatar") or user.avatar_url or f"https://a.akatsuki.gg/{user_id}.png"
        user.avatar_url = avatar_url

        total_scores = _extract_total_scores(user_data)
        if total_scores is not None:
            user.total_scores = total_scores

        ranked_score = _extract_from_nested_stats(user_data, ["ranked_score"])
        if ranked_score is not None:
            user.ranked_score = safe_int(ranked_score)

        global_rank = _extract_from_nested_stats(user_data, ["global_rank", "global_leaderboard_rank"])
        if global_rank is not None:
            user.global_rank = safe_int(global_rank)

    return inserted, updated, skipped


def _extract_total_scores(user_data: dict[str, Any]) -> int | None:
    candidates = [user_data.get("total_scores")]
    stats = user_data.get("stats") or user_data.get("statistics")
    if isinstance(stats, dict):
        candidates.append(stats.get("total_scores"))
        std_stats = stats.get("std")
        if isinstance(std_stats, dict):
            candidates.append(std_stats.get("total_scores"))

    for candidate in candidates:
        value = safe_int(candidate)
        if value is not None:
            return value
    return None


def _extract_from_nested_stats(user_data: dict[str, Any], keys: list[str]) -> Any:
    stats = user_data.get("stats") or user_data.get("statistics")
    if isinstance(stats, dict):
        for key in keys:
            if key in stats:
                return stats[key]
        std = stats.get("std")
        if isinstance(std, dict):
            for key in keys:
                if key in std:
                    return std[key]
    for key in keys:
        if key in user_data:
            return user_data[key]
    return None
