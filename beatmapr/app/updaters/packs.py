from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from ossapi import BeatmapPackType, Ossapi
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from beatmapr.app.config import get_settings
from beatmapr.app.database import SessionLocal
from beatmapr.app.logging import Ansi, log
from beatmapr.app.models import Beatmap, Pack, PackBeatmap

from .common import PACK_BATCH_SIZE, discover_json_files, parse_datetime, safe_float, safe_int

__all__ = [
    "PACK_BATCH_SIZE",
    "MissingCredentialsError",
    "PackUpdateSummary",
    "PackUpdater",
]

logger = logging.getLogger(__name__)


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


class PackUpdater:
    """Persist beatmap packs from remote APIs or local JSON payloads."""

    def __init__(self, session_factory: type[Session] | Any = SessionLocal) -> None:
        self._session_factory = session_factory

    # determine the next standard pack index by finding the largest numeric
    # suffix of existing standard pack slugs (format: <letter><number>, e.g. S123)
    def find_largest_index(self, type: str = "standard", prefix: str = "S") -> int:
        start_index = 1
        with self._session_factory() as session:  # type: ignore[call-arg]
            rows = session.scalars(select(Pack.slug).where(Pack.pack_type == type, Pack.slug.like(f"{prefix}%")))
            max_idx = 0
            for slug in rows:
                try:
                    num = int(str(slug)[1:])
                except Exception:
                    continue
                if num > max_idx:
                    max_idx = num

            if max_idx >= 1:
                start_index = max_idx + 1
        return start_index

    def update_standard(self, batch_size: int = PACK_BATCH_SIZE, tag_index: int = 1) -> PackUpdateSummary:
        client = _ensure_osu_client()

        log(f"Starting standard pack update (batch size={batch_size}, tag_index={tag_index})", Ansi.LGREEN)

        summary = PackUpdateSummary()
        pending: list[dict[str, Any]] = []
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
                batch_summary = self._persist_pack_batch(pending, f"batch-{batch_index}")
                summary.accumulate(batch_summary)
                pending.clear()
                batch_index += 1

            tag_index += 1

        if pending:
            batch_summary = self._persist_pack_batch(pending, f"batch-{batch_index}")
            summary.accumulate(batch_summary)

        log(f"Standard pack update complete; {summary.processed} packs processed", Ansi.LGREEN)
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

        log(f"Fetching pack '{pack_tag}' data from osu! API ({len(getattr(pack, 'beatmapsets', []) or [])} beatmapsets)")

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
            released_at = parse_datetime(released_raw)

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
                    pack_type_value = payload.get("pack_type", "other")
                    category = payload.get("category", pack_type_value)

                    pack = session.execute(select(Pack).where(Pack.slug == payload["slug"])).scalar_one_or_none()
                    if pack is None:
                        pack = Pack(slug=payload["slug"], name=payload["name"], pack_type=pack_type_value)
                        session.add(pack)
                        summary.inserted += 1
                    else:
                        summary.updated += 1
                        pack.name = payload["name"]
                        pack.pack_type = pack_type_value

                    pack.category = category
                    pack.released_at = payload.get("released_at")

                    _upsert_pack_beatmaps(session, pack, payload.get("beatmaps", []))

                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
                logger.exception("Failed to persist pack batch %s; rolled back", batch_label)
                raise
            else:
                log(f"Completed {batch_label}, {summary.processed} packs committed", Ansi.LYELLOW)

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

        released_at = parse_datetime(record.get("released_at") or record.get("date"))

        return {
            "slug": slug,
            "name": name,
            "pack_type": pack_type,
            "category": category,
            "released_at": released_at,
            "beatmaps": beatmaps,
        }


def _ensure_osu_client() -> Ossapi:
    settings = get_settings()
    if settings.osu_client_id is None or settings.osu_client_secret is None:
        raise MissingCredentialsError(
            "OSU client credentials are required. Set BEATMAPR_OSU_CLIENT_ID and BEATMAPR_OSU_CLIENT_SECRET in your environment."
        )
    return Ossapi(settings.osu_client_id, settings.osu_client_secret)


def _upsert_pack_beatmaps(session: Session, pack: Pack, beatmaps: Iterable[dict[str, Any]]) -> None:
    beatmap_list = list(beatmaps)

    session.flush()

    # Snapshot manually-managed flags so a pack refresh keeps them on the recreated rows.
    existing_flags = {
        beatmap_id: (effective, autocomplete)
        for beatmap_id, effective, autocomplete in session.execute(
            select(PackBeatmap.beatmap_id, PackBeatmap.effective, PackBeatmap.autocomplete).where(PackBeatmap.pack_id == pack.id)
        )
    }

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

        default_autocomplete = (pack.pack_type != 'standard')  # 非标准包默认自动完成
        effective, autocomplete = existing_flags.get(beatmap.beatmap_id, (True, default_autocomplete))
        
        session.add(
            PackBeatmap(
                pack_id=pack.id,
                beatmap_id=beatmap.beatmap_id,
                position=position,
                effective=effective,
                autocomplete=autocomplete,
            )
        )


def _normalise_json_beatmap(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    beatmap_id = safe_int(payload.get("beatmap_id") or payload.get("id"))
    if beatmap_id is None:
        return None

    mode = safe_int(payload.get("mode") or payload.get("mode_int")) or 0
    if mode != 0:
        return None

    return {
        "beatmap_id": beatmap_id,
        "beatmapset_id": safe_int(payload.get("beatmapset_id") or payload.get("set_id")),
        "title": payload.get("title"),
        "artist": payload.get("artist"),
        "version": payload.get("version"),
        "mode": mode,
        "hit_length": safe_int(payload.get("time_duration_seconds") or payload.get("hit_length") or payload.get("length")),
        "total_length": safe_int(payload.get("total_length_seconds") or payload.get("total_length")),
        "bpm": safe_float(payload.get("bpm")),
        "cs": safe_float(payload.get("cs")),
        "ar": safe_float(payload.get("ar")),
        "od": safe_float(payload.get("od")),
        "hp": safe_float(payload.get("hp")),
        "star_rating": safe_float(payload.get("star_rating") or payload.get("difficulty_rating")),
        "ranked_status": payload.get("ranked_status") or payload.get("status"),
    }
