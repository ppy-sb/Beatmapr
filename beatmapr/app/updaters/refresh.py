from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal

import httpx
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from beatmapr.app.config import get_settings
from beatmapr.app.models import Beatmap, PackBeatmap, User, UserScore

from .common import parse_datetime, safe_float, safe_int

__all__ = [
    "RefreshProgressEvent",
    "RefreshProgressBroker",
]


REFRESH_MAX_RETRIES = 4
SCORES_PAGE_LIMIT = 100


@dataclass(slots=True)
class RefreshProgressEvent:
    """Structured message describing the refresh pipeline state."""

    user_id: int
    stage: str
    message: str
    status: Literal["info", "success", "warning", "error"] = "info"
    sequence: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "stage": self.stage,
            "message": self.message,
            "status": self.status,
            "sequence": self.sequence,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class RefreshProgressBroker:
    """Manage websocket subscribers for refresh progress events."""

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[RefreshProgressEvent]]] = defaultdict(set)
        self._latest_event: dict[int, RefreshProgressEvent] = {}
        self._lock = asyncio.Lock()
        self._active: set[int] = set()

    async def publish(self, event: RefreshProgressEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(event.user_id, ()))
            self._latest_event[event.user_id] = event
            if event.stage == "refresh:complete" or event.stage == "refresh:error" or event.status == "error":
                self._active.discard(event.user_id)
        for queue in queues:
            await queue.put(event)

    async def last_event(self, user_id: int) -> RefreshProgressEvent | None:
        async with self._lock:
            return self._latest_event.get(user_id)

    async def is_active(self, user_id: int) -> bool:
        async with self._lock:
            return user_id in self._active

    async def reset(self, user_id: int) -> None:
        async with self._lock:
            self._latest_event.pop(user_id, None)
            self._active.add(user_id)

    async def _add_subscriber(self, user_id: int, queue: asyncio.Queue[RefreshProgressEvent]) -> RefreshProgressEvent | None:
        async with self._lock:
            self._subscribers[user_id].add(queue)
            return self._latest_event.get(user_id)

    async def _remove_subscriber(self, user_id: int, queue: asyncio.Queue[RefreshProgressEvent]) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(user_id)
            if not subscribers:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(user_id, None)

    @asynccontextmanager
    async def connect(self, user_id: int) -> AsyncIterator[asyncio.Queue[RefreshProgressEvent]]:
        queue: asyncio.Queue[RefreshProgressEvent] = asyncio.Queue()
        snapshot = await self._add_subscriber(user_id, queue)
        if snapshot is not None:
            await queue.put(snapshot)
        try:
            yield queue
        finally:
            await self._remove_subscriber(user_id, queue)


def _should_retry(exc: BaseException) -> bool:  # pragma: no cover - small predicate
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code >= 500 or status_code in {408, 425, 429}
    return isinstance(exc, httpx.RequestError)


class UserDataRefresher:
    def __init__(
        self,
        session: Session,
        user_id: int,
        broker: RefreshProgressBroker | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self._broker = broker
        settings = get_settings()
        self._base_url = settings.akatsuki_base_url.rstrip("/")
        self._timeout = settings.request_timeout_seconds
        self._sequence = 0

    async def run(self) -> dict[str, int]:
        try:
            await self._emit("refresh:start", "Starting user data refresh")
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                profile = await self._fetch_profile(client)
                scores = await self._fetch_scores(client)
            counts = await self._persist(profile, scores)
            await self._emit(
                "refresh:complete",
                "Refresh complete",
                status="success",
                counts=counts,
                total_scores=len(scores),
            )
            return counts
        except HTTPException as exc:
            message = exc.detail if isinstance(exc.detail, str) else "Refresh failed"
            await self._emit(
                "refresh:error",
                message,
                status="error",
                status_code=exc.status_code,
            )
            raise
        except Exception as exc:
            await self._emit(
                "refresh:error",
                "Unexpected error during refresh",
                status="error",
                error=str(exc),
            )
            raise

    async def _fetch_profile(self, client: httpx.AsyncClient) -> dict[str, Any]:
        await self._emit("profile:fetch", "Fetching user profile")
        response = await self._request(
            client,
            f"{self._base_url}/users/full",
            params={"id": self.user_id},
            stage="profile:request",
            retry_payload={"resource": "profile"},
        )
        if response.status_code == status.HTTP_404_NOT_FOUND:
            detail = "User not found"
            await self._emit("profile:not_found", detail, status="error")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        profile = response.json()
        await self._emit("profile:complete", "User profile retrieved", username=profile.get("username"))
        return profile

    async def _fetch_scores(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        scores: list[dict[str, Any]] = []
        page = 1

        while True:
            await self._emit(
                "scores:fetch",
                f"Fetching scores page {page}",
                page=page,
            )
            response = await self._request(
                client,
                f"{self._base_url}/users/scores/best",
                params={"mode": 0, "p": page, "l": SCORES_PAGE_LIMIT, "rx": 1, "id": self.user_id},
                stage="scores:request",
                retry_payload={"page": page},
            )

            if response.status_code == status.HTTP_404_NOT_FOUND:
                await self._emit(
                    "scores:not_found",
                    "Scores endpoint returned 404",
                    status="warning",
                    page=page,
                )
                break

            payload = response.json()
            page_scores = payload.get("scores") or []
            scores.extend(page_scores)

            if not page_scores or len(page_scores) < SCORES_PAGE_LIMIT:
                break
            page += 1

        await self._emit("scores:complete", "Score fetching complete", total=len(scores), pages=page)
        return scores

    async def _persist(self, profile: dict[str, Any], scores: list[dict[str, Any]]) -> dict[str, int]:
        await self._emit("persist:start", "Saving user data")

        raw_user_id = profile.get("id")
        try:
            user_id = int(raw_user_id) if raw_user_id is not None else None
        except (TypeError, ValueError):
            user_id = None
        if user_id is None:
            await self._emit("persist:error", "Profile payload missing user ID", status="error")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Profile payload missing user id",
            )

        session = self.session
        user = session.get(User, user_id)
        if user is None:
            user = User(id=user_id, username=profile.get("username", str(user_id)))
            session.add(user)

        user.username = profile.get("username", user.username)
        user.country = profile.get("country") or user.country
        user.avatar_url = profile.get("avatar_url") or f"https://a.akatsuki.gg/{user_id}.png"

        std_stats = _extract_standard_stats(profile.get("stats"))
        user.ranked_score = safe_int(std_stats.get("ranked_score"))
        user.global_rank = safe_int(std_stats.get("global_leaderboard_rank"))
        user.total_scores = safe_int(profile.get("total_scores")) or len(scores)
        user.last_refreshed_at = datetime.now(timezone.utc)

        session.execute(delete(UserScore).where(UserScore.user_id == user_id))

        grades: list[str] = []
        seen: set[int] = set()
        for index, score in enumerate(scores, start=1):
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
                score=safe_int(score.get("score")),
                accuracy=safe_float(accuracy),
                max_combo=safe_int(score.get("max_combo")),
                mods=mods_value,
                pp=safe_float(score.get("pp")),
                achieved_at=parse_datetime(score.get("play_time") or score.get("created_at")),
            )
            session.add(user_score)

            if index % 50 == 0:
                await self._emit(
                    "persist:progress",
                    "Writing scores",
                    total=len(scores),
                    processed=index,
                )

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
        await self._emit("persist:complete", "User data saved", counts=counts)
        return counts

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, Any] | None,
        stage: str,
        retry_payload: dict[str, Any] | None = None,
        retry_on_404: bool = False,
    ) -> httpx.Response:
        payload = retry_payload or {}

        async def _before_sleep(retry_state) -> None:  # pragma: no cover - simple notifier
            exc = retry_state.outcome.exception() if retry_state.outcome else None
            await self._emit(
                f"{stage}:retry",
                "Request failed, retrying",
                status="warning",
                attempt=retry_state.attempt_number,
                error=str(exc) if exc else None,
                wait=retry_state.next_action.sleep if retry_state.next_action else None,
                **payload,
            )

        retryer = AsyncRetrying(
            retry=retry_if_exception(_should_retry),
            stop=stop_after_attempt(REFRESH_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            reraise=True,
            before_sleep=_before_sleep,
        )

        async for attempt in retryer:
            with attempt:
                response = await client.get(url, params=params)
                if response.status_code == status.HTTP_404_NOT_FOUND and not retry_on_404:
                    return response
                response.raise_for_status()
                return response

        raise RuntimeError("request retry loop exited unexpectedly")

    async def _emit(
        self,
        stage: str,
        message: str,
        *,
        status: Literal["info", "success", "warning", "error"] = "info",
        **payload: Any,
    ) -> None:
        if self._broker is None:
            return
        self._sequence += 1
        event = RefreshProgressEvent(
            user_id=self.user_id,
            stage=stage,
            message=message,
            status=status,
            sequence=self._sequence,
            payload=payload,
        )
        await self._broker.publish(event)


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
            if int(candidate["std"].get("playcount") or 0) == 0:
                continue
            return candidate["std"]
        if candidate.get("mode") in {"std", "standard", 0}:
            if int(candidate.get("playcount") or 0) == 0:
                continue
            return candidate
        if candidate.get("ruleset") in {"osu"}:
            if int(candidate.get("playcount") or 0) == 0:
                continue
            return candidate
    return candidates[1] if candidates else {}
