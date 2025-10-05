from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx
from fastapi import HTTPException, status
from ossapi import BeatmapPackType, Ossapi
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from beatmapr.app.config import get_settings
from beatmapr.app.database import SessionLocal
from beatmapr.app.logging import log
from beatmapr.app.models import Beatmap, Pack, PackBeatmap, User, UserScore

logger = logging.getLogger()

PACK_BATCH_SIZE = 10
USERS_PAGE_LIMIT = 100
USERS_BATCH_SIZE = 10
USERS_MAX_RETRIES = 3
TOTAL_SCORES_PATTERN = re.compile(r"Total scores:\s*([\d.,]+)")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON_ROOTS: tuple[Path, ...] = tuple(dict.fromkeys((PROJECT_ROOT, PROJECT_ROOT / "data")))


class MissingCredentialsError(RuntimeError):
    """Raised when required API credentials are not configured."""


@dataclass
class PackUpdateSummary:
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    files: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def accumulate(self, other: PackUpdateSummary) -> None:
        self.processed += other.processed
        self.inserted += other.inserted
        self.updated += other.updated
        self.skipped += other.skipped
        self.files.extend(other.files)
        self.errors.update(other.errors)


@dataclass
class UserImportSummary:
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    files: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def accumulate(self, other: UserImportSummary) -> None:
        self.processed += other.processed
        self.inserted += other.inserted
        self.updated += other.updated
        self.skipped += other.skipped
        self.files.extend(other.files)
        self.errors.update(other.errors)


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


def _ensure_osu_client() -> Ossapi:
    settings = get_settings()
    if settings.osu_client_id is None or settings.osu_client_secret is None:
        raise MissingCredentialsError(
            "OSU client credentials are required. Set BEATMAPR_OSU_CLIENT_ID and BEATMAPR_OSU_CLIENT_SECRET in your environment."
        )
    return Ossapi(settings.osu_client_id, settings.osu_client_secret)


class PackUpdater:
    """Persist beatmap packs from remote APIs or local JSON payloads."""

    def __init__(self, session_factory: type[Session] | Any = SessionLocal) -> None:
        self._session_factory = session_factory

    def update_standard(self, batch_size: int = PACK_BATCH_SIZE) -> PackUpdateSummary:
        client = _ensure_osu_client()

        log(f"Starting standard pack update (batch size={batch_size})")

        summary = PackUpdateSummary()
        pending: list[dict[str, Any]] = []
        tag_index = 1
        batch_index = 1

        while True:
            tag = f"S{tag_index}"
            try:
                payload = self._build_pack_payload(client, tag)
            except Exception as exc:  # noqa: BLE001
                log(f"Stopping standard pack discovery at {tag} ({exc})")
                logger.debug("Standard pack discovery error", exc_info=True)
                break

            pending.append({**payload, "pack_type": "standard", "category": "standard"})

            if len(pending) >= batch_size:
                batch_summary = self._persist_pack_batch(pending, f"standard-{batch_index}")
                summary.accumulate(batch_summary)
                pending.clear()
                batch_index += 1

            tag_index += 1

        if pending:
            batch_summary = self._persist_pack_batch(pending, f"standard-{batch_index}")
            summary.accumulate(batch_summary)

        log(f"Standard pack update complete; {summary.processed} packs processed")
        return summary

    def update_other(self, batch_size: int = PACK_BATCH_SIZE) -> PackUpdateSummary:
        client = _ensure_osu_client()

        log(f"Starting non-standard pack update (batch size={batch_size})")

        summary = PackUpdateSummary()

        for category in BeatmapPackType:
            category_value = getattr(category, "value", None)
            if category_value == "standard":
                continue

            log("Processing category '%s'", category_value)

            cursor: str | None = None
            page = 1
            batch_index = 1
            pending: list[dict[str, Any]] = []

            while True:
                batch = client.beatmap_packs(type=category, cursor_string=cursor)
                remote_packs = getattr(batch, "beatmap_packs", []) or []
                if not remote_packs:
                    log("No remote packs returned for category '%s' at cursor %s", category_value, cursor)
                    break

                log(f"Fetched {len(remote_packs)} remote packs for category '{category_value}' (page={page})")

                for remote_pack in remote_packs:
                    try:
                        payload = self._build_pack_payload(client, remote_pack.tag)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Skipping pack %s in category '%s' due to error: %s",
                            getattr(remote_pack, "tag", "unknown"),
                            category_value,
                            exc,
                        )
                        logger.debug("Pack fetch error", exc_info=True)
                        continue

                        # loop continues

                    pending.append({**payload, "pack_type": "other", "category": category_value})

                    if len(pending) >= batch_size:
                        batch_summary = self._persist_pack_batch(pending, f"{category_value}-{batch_index}")
                        summary.accumulate(batch_summary)
                        pending.clear()
                        batch_index += 1

                batch_cursor = getattr(batch, "cursor", None)
                if not batch_cursor:
                    break

                cursor = str(batch_cursor)
                page += 1

            if pending:
                batch_summary = self._persist_pack_batch(pending, f"{category_value}-{batch_index}")
                summary.accumulate(batch_summary)
                pending.clear()

        log(f"Non-standard pack update complete; {summary.processed} packs processed")
        return summary

    def import_from_json(self, file_path: Path, pack_type: str | None = None, category_hint: str | None = None) -> PackUpdateSummary:
        summary = PackUpdateSummary(files=[str(file_path)])

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            summary.errors[str(file_path)] = str(exc)
            return summary

        derived_type = self._infer_pack_type(file_path, data, pack_type)

        payloads: list[dict[str, Any]] = []
        skipped = 0

        if isinstance(data, list):
            parsed, skipped = self._parse_standard_records(data, derived_type, category_hint)
            payloads.extend(parsed)
        elif isinstance(data, dict):
            parsed, skipped = self._parse_mapping_records(data, derived_type, category_hint)
            payloads.extend(parsed)
        else:
            summary.errors[str(file_path)] = "Unsupported JSON structure: expected list or object"
            return summary

        summary.skipped += skipped

        if not payloads:
            summary.errors[str(file_path)] = "No valid pack payloads found"
            return summary

        batch_summary = self._persist_pack_batch(payloads, file_path.stem)
        summary.accumulate(batch_summary)
        return summary

    def import_from_path(
        self,
        location: Path | None,
        pack_type: str | None = None,
        category_hint: str | None = None,
        recursive: bool = False,
    ) -> PackUpdateSummary:
        summary = PackUpdateSummary()

        candidates: list[Path]
        if location is None:
            candidates = discover_json_files(["packs.json", "other_packs.json"])
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
                summary.errors["auto"] = "No available JSON files found in default directories"
            else:
                summary.errors[str(location)] = "No JSON files found at the specified path"
            return summary

        for candidate in candidates:
            summary.accumulate(self.import_from_json(candidate, pack_type=pack_type, category_hint=category_hint))

        return summary

    @staticmethod
    def _build_pack_payload(client: Ossapi, pack_tag: str) -> dict[str, Any]:
        pack = client.beatmap_pack(pack_tag)
        beatmaps: list[dict[str, Any]] = []

        for beatmapset in getattr(pack, "beatmapsets", []) or []:
            set_data = client.beatmapset(beatmapset.id)
            for beatmap in getattr(set_data, "beatmaps", []) or []:
                if beatmap.mode_int != 0:
                    continue
                beatmaps.append(
                    {
                        "beatmap_id": beatmap.id,
                        "beatmapset_id": beatmap.beatmapset_id,
                        "title": set_data.title,
                        "artist": set_data.artist,
                        "version": beatmap.version,
                        "mode": beatmap.mode_int,
                        "hit_length": beatmap.hit_length,
                        "total_length": beatmap.total_length,
                        "bpm": beatmap.bpm,
                        "cs": beatmap.cs,
                        "ar": beatmap.ar,
                        "od": beatmap.accuracy,
                        "hp": beatmap.drain,
                        "star_rating": float(beatmap.difficulty_rating),
                        "ranked_status": beatmap.status.name,
                    }
                )

        released_raw = getattr(pack, "date", None)
        released_at: datetime | None = None
        if isinstance(released_raw, datetime):
            released_at = released_raw
        elif released_raw:
            try:
                released_at = datetime.fromisoformat(str(released_raw).replace("Z", "+00:00"))
            except ValueError:
                released_at = None

        return {
            "slug": pack.tag,
            "name": pack.name,
            "released_at": released_at,
            "beatmaps": beatmaps,
        }

    def _persist_pack_batch(self, payloads: Iterable[dict[str, Any]], batch_label: str) -> PackUpdateSummary:
        payload_list = list(payloads)
        summary = PackUpdateSummary(processed=len(payload_list))

        if not payload_list:
            return summary

        with self._session_factory() as session:  # type: ignore[call-arg]
            try:
                for payload in payload_list:
                    pack_type = payload.get("pack_type", "other")
                    category = payload.get("category", pack_type)

                    pack = session.execute(select(Pack).where(Pack.slug == payload["slug"])).scalar_one_or_none()
                    if pack is None:
                        pack = Pack(slug=payload["slug"], name=payload["name"], pack_type=pack_type)
                        session.add(pack)
                        summary.inserted += 1
                    else:
                        summary.updated += 1
                        pack.name = payload["name"]
                        pack.pack_type = pack_type

                    pack.category = category
                    pack.released_at = payload.get("released_at")

                    _upsert_pack_beatmaps(session, pack, payload.get("beatmaps", []))

                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
                logger.exception("Failed to persist pack batch %s; rolled back", batch_label)
                raise
            else:
                log(f"Completed pack batch {batch_label}, {summary.processed} packs committed")

        return summary

    @staticmethod
    def _infer_pack_type(file_path: Path, data: Any, explicit: str | None) -> str:
        if explicit and explicit != "auto":
            return explicit
        if isinstance(data, list):
            return "standard"
        if isinstance(data, dict):
            if file_path.name.lower().startswith("pack"):
                return "standard"
            return "other"
        return "standard"

    def _parse_standard_records(
        self,
        records: Sequence[Any],
        pack_type: str,
        category_hint: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        payloads: list[dict[str, Any]] = []
        skipped = 0

        for record in records:
            payload = self._convert_json_pack(record, pack_type, category_hint or pack_type)
            if payload is None:
                skipped += 1
            else:
                payloads.append(payload)

        return payloads, skipped

    def _parse_mapping_records(
        self,
        mapping: dict[str, Any],
        pack_type: str,
        category_hint: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        payloads: list[dict[str, Any]] = []
        skipped = 0

        for category_key, records in mapping.items():
            if not isinstance(records, list):
                skipped += 1
                continue
            category = category_hint or str(category_key)
            parsed, input_skipped = self._parse_standard_records(records, pack_type or "other", category)
            payloads.extend(parsed)
            skipped += input_skipped

        return payloads, skipped

    @staticmethod
    def _convert_json_pack(record: Any, pack_type: str, category: str | None) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None

        slug = str(record.get("packtag") or record.get("packName") or record.get("slug") or "").strip()
        if not slug:
            return None

        name = str(record.get("packName") or slug).strip() or slug

        beatmaps_raw = record.get("beatmaps")
        if not isinstance(beatmaps_raw, list):
            beatmaps_raw = []

        beatmaps: list[dict[str, Any]] = []
        for item in beatmaps_raw:
            normalised = _normalise_json_beatmap(item)
            if normalised is not None:
                beatmaps.append(normalised)

        if not beatmaps:
            return None

        released_at = _parse_datetime(record.get("released_at") or record.get("date"))

        return {
            "slug": slug,
            "name": name,
            "pack_type": pack_type,
            "category": category,
            "released_at": released_at,
            "beatmaps": beatmaps,
        }


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

            for chunk in _chunked(user_ids, batch_size):
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
                    total_scores = _safe_int(float(numeric_text)) if numeric_text else None
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
        summary = UserImportSummary(files=[str(file_path)])

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

                user_id = _safe_int(record.get("id"))
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

                total_scores = _safe_int(record.get("total_scores"))
                if total_scores is not None:
                    user.total_scores = total_scores

                ranked_score = _safe_int(record.get("ranked_score"))
                if ranked_score is not None:
                    user.ranked_score = ranked_score

                global_rank = _safe_int(record.get("global_rank"))
                if global_rank is not None:
                    user.global_rank = global_rank

                last_activity = record.get("latest_activity") or record.get("last_refreshed_at")
                timestamp = _parse_datetime(last_activity)
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

        # fall back to project_root/data
        fallback = PROJECT_ROOT / "data"
        return fallback.resolve() if fallback.exists() else fallback


def update_standard_packs(batch_size: int = PACK_BATCH_SIZE) -> int:
    """Fetch and store standard osu! beatmap packs in batches."""

    summary = PackUpdater().update_standard(batch_size=batch_size)
    return summary.processed


def update_other_packs(batch_size: int = PACK_BATCH_SIZE) -> int:
    summary = PackUpdater().update_other(batch_size=batch_size)
    return summary.processed


async def sync_akatsuki_users(
    limit: int = USERS_PAGE_LIMIT,
    batch_size: int = USERS_BATCH_SIZE,
    max_retries: int = USERS_MAX_RETRIES,
    max_pages: int | None = None,
) -> dict[str, Any]:
    return await UserUpdater().sync_from_akatsuki(limit=limit, batch_size=batch_size, max_retries=max_retries, max_pages=max_pages)


def update_user_totals_from_files(
    data_directory: str | Path | None = None,
    batch_size: int = 200,
) -> dict[str, Any]:
    return UserUpdater().update_totals_from_files(data_directory=data_directory, batch_size=batch_size)


def import_packs_from_path(
    location: Path | None,
    pack_type: str | None = None,
    category_hint: str | None = None,
    recursive: bool = False,
) -> PackUpdateSummary:
    return PackUpdater().import_from_path(location, pack_type=pack_type, category_hint=category_hint, recursive=recursive)


def import_users_from_path(location: Path | None, recursive: bool = False) -> UserImportSummary:
    return UserUpdater().import_from_path(location, recursive=recursive)


def _upsert_pack_beatmaps(session: Session, pack: Pack, beatmaps: Iterable[dict[str, Any]]) -> None:
    beatmap_list = list(beatmaps)

    session.flush()  # ensure pack.id exists

    session.execute(delete(PackBeatmap).where(PackBeatmap.pack_id == pack.id))

    for position, beatmap_data in enumerate(beatmap_list, start=1):
        beatmap = session.get(Beatmap, beatmap_data["beatmap_id"])
        if beatmap is None:
            beatmap = Beatmap(beatmap_id=beatmap_data["beatmap_id"])
            session.add(beatmap)

        beatmap.beatmapset_id = beatmap_data.get("beatmapset_id")
        beatmap.title = beatmap_data.get("title")
        beatmap.artist = beatmap_data.get("artist")
        beatmap.version = beatmap_data.get("version")
        beatmap.mode = beatmap_data.get("mode", 0)
        beatmap.hit_length = beatmap_data.get("hit_length")
        beatmap.total_length = beatmap_data.get("total_length")
        beatmap.bpm = beatmap_data.get("bpm")
        beatmap.cs = beatmap_data.get("cs")
        beatmap.ar = beatmap_data.get("ar")
        beatmap.od = beatmap_data.get("od")
        beatmap.hp = beatmap_data.get("hp")
        beatmap.star_rating = beatmap_data.get("star_rating")
        beatmap.ranked_status = beatmap_data.get("ranked_status")

        session.add(PackBeatmap(pack_id=pack.id, beatmap_id=beatmap.beatmap_id, position=position))


def _normalise_json_beatmap(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    beatmap_id = _safe_int(payload.get("beatmap_id") or payload.get("id"))
    if beatmap_id is None:
        return None

    mode = _safe_int(payload.get("mode") or payload.get("mode_int")) or 0
    if mode != 0:
        return None

    return {
        "beatmap_id": beatmap_id,
        "beatmapset_id": _safe_int(payload.get("beatmapset_id") or payload.get("set_id")),
        "title": payload.get("title"),
        "artist": payload.get("artist"),
        "version": payload.get("version"),
        "mode": mode,
        "hit_length": _safe_int(payload.get("time_duration_seconds") or payload.get("hit_length") or payload.get("length")),
        "total_length": _safe_int(payload.get("total_length_seconds") or payload.get("total_length")),
        "bpm": _safe_float(payload.get("bpm")),
        "cs": _safe_float(payload.get("cs")),
        "ar": _safe_float(payload.get("ar")),
        "od": _safe_float(payload.get("od")),
        "hp": _safe_float(payload.get("hp")),
        "star_rating": _safe_float(payload.get("star_rating") or payload.get("difficulty_rating")),
        "ranked_status": payload.get("ranked_status") or payload.get("status"),
    }


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
        user_id = _safe_int(raw_user_id)
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
            user.ranked_score = _safe_int(ranked_score)

        global_rank = _extract_from_nested_stats(user_data, ["global_rank", "global_leaderboard_rank"])
        if global_rank is not None:
            user.global_rank = _safe_int(global_rank)

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
        value = _safe_int(candidate)
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


def _chunked(sequence: list[int], size: int) -> Iterable[list[int]]:
    for index in range(0, len(sequence), size):
        yield sequence[index : index + size]


async def refresh_user_data(session: Session, user_id: int) -> dict[str, int]:
    settings = get_settings()
    base_url = settings.akatsuki_base_url.rstrip("/")
    timeout = settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout) as client:
        profile_resp = await client.get(f"{base_url}/users/full", params={"id": user_id})
        if profile_resp.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        profile_resp.raise_for_status()
        profile_data = profile_resp.json()

        scores: list[dict[str, Any]] = []
        page = 1
        while True:
            score_resp = await client.get(
                f"{base_url}/users/scores/best",
                params={"mode": 0, "p": page, "l": 100, "rx": 1, "id": user_id},
            )
            score_resp.raise_for_status()
            payload = score_resp.json()
            page_scores = payload.get("scores") or []
            if not page_scores:
                break
            scores.extend(page_scores)
            if len(page_scores) < 100:
                break
            page += 1

    return _persist_user_data(session, profile_data, scores)


def _persist_user_data(session: Session, profile: dict[str, Any], scores: list[dict[str, Any]]) -> dict[str, int]:
    raw_user_id = profile.get("id")
    try:
        user_id = int(raw_user_id) if raw_user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Profile payload missing user id",
        )

    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=profile.get("username", str(user_id)))
        session.add(user)

    user.username = profile.get("username", user.username)
    user.country = profile.get("country") or user.country
    user.avatar_url = profile.get("avatar_url") or f"https://a.akatsuki.gg/{user_id}.png"

    std_stats = _extract_standard_stats(profile.get("stats"))
    user.ranked_score = _safe_int(std_stats.get("ranked_score"))
    user.global_rank = _safe_int(std_stats.get("global_leaderboard_rank"))
    user.total_scores = _safe_int(profile.get("total_scores")) or len(scores)
    user.last_refreshed_at = datetime.now(timezone.utc)

    session.execute(delete(UserScore).where(UserScore.user_id == user_id))

    grades: list[str] = []
    seen = set()
    for score in scores:
        beatmap_info = score.get("beatmap") or {}
        beatmap_id = beatmap_info.get("beatmap_id") or beatmap_info.get("id")
        if beatmap_id is None:
            continue
        beatmap_id = int(beatmap_id)
        if beatmap_id in seen:
            continue
        seen.add(beatmap_id)

        beatmap = session.get(Beatmap, beatmap_id)
        if beatmap is None:
            beatmap = Beatmap(beatmap_id=beatmap_id)
            session.add(beatmap)

        beatmapset_id = beatmap_info.get("beatmapset_id") or beatmap_info.get("parent_set_id")
        beatmap.beatmapset_id = beatmapset_id or beatmap.beatmapset_id
        beatmap.title = beatmap_info.get("title") or beatmap.title
        beatmap.artist = beatmap_info.get("artist") or beatmap.artist
        beatmap.version = beatmap_info.get("version") or beatmap.version
        beatmap.mode = beatmap_info.get("mode_int") or beatmap.mode or 0
        beatmap.hit_length = beatmap_info.get("hit_length") or beatmap.hit_length
        beatmap.total_length = beatmap_info.get("total_length") or beatmap.total_length
        beatmap.bpm = beatmap_info.get("bpm") or beatmap.bpm
        beatmap.cs = beatmap_info.get("cs") or beatmap.cs
        beatmap.ar = beatmap_info.get("ar") or beatmap.ar
        beatmap.od = beatmap_info.get("accuracy") or beatmap.od
        beatmap.hp = beatmap_info.get("drain") or beatmap.hp
        beatmap.star_rating = beatmap_info.get("difficulty_rating") or beatmap.star_rating
        beatmap.ranked_status = beatmap_info.get("status") or beatmap.ranked_status

        grade = (score.get("rank") or "").upper()
        grades.append(grade)

        mods = score.get("mods")
        if isinstance(mods, list):
            mods_value = ",".join(str(m) for m in mods)
        else:
            mods_value = str(mods) if mods else None

        accuracy = score.get("accuracy")
        if accuracy is not None and accuracy > 1:
            accuracy = accuracy / 100.0

        user_score = UserScore(
            user_id=user_id,
            beatmap_id=beatmap_id,
            grade=grade,
            score=_safe_int(score.get("score")),
            accuracy=_safe_float(accuracy),
            max_combo=_safe_int(score.get("max_combo")),
            mods=mods_value,
            pp=_safe_float(score.get("pp")),
            achieved_at=_parse_datetime(score.get("play_time") or score.get("created_at")),
        )
        session.add(user_score)

    grade_counter = Counter(grade for grade in grades if grade)
    counts = {rank: grade_counter.get(rank, 0) for rank in ["SSH", "SS", "SH", "S", "A", "B", "C", "D"]}

    session.commit()

    total_available = session.execute(select(func.count(func.distinct(PackBeatmap.beatmap_id)))).scalar_one()
    cleared_total = session.execute(
        select(func.count(func.distinct(UserScore.beatmap_id)))
        .join(PackBeatmap, PackBeatmap.beatmap_id == UserScore.beatmap_id)
        .where(UserScore.user_id == user_id)
    ).scalar_one()

    user.cleared_beatmaps = int(cleared_total or 0)
    user.completion_percent = (float(cleared_total) / float(total_available) if total_available and cleared_total is not None else 0.0) * 100

    session.commit()
    return counts


def _extract_standard_stats(stats: Any) -> dict[str, Any]:
    if stats is None:
        return {}
    candidates: list[dict[str, Any]] = []

    if isinstance(stats, dict):
        for value in stats.values():
            if isinstance(value, dict):
                candidates.append(value)
    elif isinstance(stats, list):
        for item in stats:
            if isinstance(item, dict):
                candidates.append(item)

    for candidate in candidates:
        if "std" in candidate and isinstance(candidate["std"], dict):
            return candidate["std"]
        if candidate.get("mode") in {"std", "standard", 0}:
            return candidate
        if candidate.get("ruleset") in {"osu"}:
            return candidate
    return candidates[0] if candidates else {}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
