from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from beatmapr.app.database import get_db
from beatmapr.app.models import Pack, PackBeatmap, User, UserScore
from beatmapr.app.schemas import (
    PackProgress,
    RankCounts,
    RefreshProgressEventPayload,
    RefreshStatusResponse,
    SearchUserItem,
    TotalsSummary,
    UserProfileResponse,
    UserSummary,
)
from beatmapr.app.updaters.refresh import RefreshProgressBroker, UserDataRefresher

router = APIRouter(prefix="/users", tags=["users"])
progress_broker = RefreshProgressBroker()


@router.get("/search", response_model=list[SearchUserItem])
def search_users(
    query: str = Query(..., min_length=1, description="Partial username or numeric id"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[SearchUserItem]:
    expressions: list[Any] = [User.username.ilike(f"%{query}%")]
    if query.isdigit():
        expressions.append(User.id == int(query))

    stmt = select(User).where(or_(*expressions)).order_by(User.username.asc()).limit(limit)
    users = db.execute(stmt).scalars().all()
    return [SearchUserItem(id=user.id, username=user.username, country=user.country) for user in users]


@router.post("/{user_id}/refresh", response_model=RankCounts)
async def refresh_user(user_id: int, db: Session = Depends(get_db)) -> RankCounts:
    await progress_broker.reset(user_id)
    refresher = UserDataRefresher(db, user_id, broker=progress_broker)
    counts = await refresher.run()
    return RankCounts(**{k: counts.get(k, 0) for k in ["SSH", "SS", "SH", "S", "A", "B", "C", "D"]})


@router.get("/{user_id}/refresh/status", response_model=RefreshStatusResponse)
async def get_refresh_status(user_id: int) -> RefreshStatusResponse:
    event = await progress_broker.last_event(user_id)
    active = await progress_broker.is_active(user_id)

    if event is None:
        return RefreshStatusResponse(active=active)

    if not active and event.stage not in {"refresh:complete", "refresh:error"} and event.status not in {"success", "error"}:
        active = True

    payload = RefreshProgressEventPayload(
        user_id=event.user_id,
        stage=event.stage,
        message=event.message,
        status=event.status,
        sequence=event.sequence,
        payload=event.payload,
        timestamp=event.timestamp,
    )

    return RefreshStatusResponse(active=active, last_event=payload)


@router.get("/{user_id}/refresh/stream")
async def subscribe_refresh_progress(user_id: int) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async with progress_broker.connect(user_id) as queue:
            try:
                yield "retry: 2000\n\n"
                while True:
                    event = await queue.get()
                    payload = json.dumps(event.to_dict(), ensure_ascii=False)
                    yield f"id: {event.sequence}\ndata: {payload}\n\n"
            except asyncio.CancelledError:  # client disconnected
                raise

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)) -> UserProfileResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    rank_counts = _get_rank_counts(db, user_id)
    standard_progress, other_progress, totals = _collect_progress(db, user_id)
    totals.overall_completion_percent = user.completion_percent

    summary = UserSummary(
        id=user.id,
        username=user.username,
        country=user.country,
        avatar_url=user.avatar_url,
        ranked_score=user.ranked_score,
        global_rank=user.global_rank,
        total_scores=user.total_scores,
        cleared_beatmaps=user.cleared_beatmaps,
        completion_percent=user.completion_percent,
        last_refreshed_at=user.last_refreshed_at,
        rank_counts=rank_counts,
    )

    return UserProfileResponse(user=summary, standard=standard_progress, other=other_progress, totals=totals)


def _get_rank_counts(db: Session, user_id: int) -> RankCounts:
    rows = db.execute(select(UserScore.grade, func.count()).where(UserScore.user_id == user_id).group_by(UserScore.grade))
    counts_dict = {grade or "": count for grade, count in rows}
    return RankCounts(**{k: counts_dict.get(k, 0) for k in ["SSH", "SS", "SH", "S", "A", "B", "C", "D"]})


def _collect_progress(db: Session, user_id: int) -> tuple[list[PackProgress], list[PackProgress], TotalsSummary]:
    stmt = (
        select(
            Pack.id,
            Pack.slug,
            Pack.name,
            Pack.pack_type,
            Pack.category,
            func.count(PackBeatmap.beatmap_id).label("total"),
            func.count(UserScore.id).label("cleared"),
        )
        .join(PackBeatmap, PackBeatmap.pack_id == Pack.id)
        .outerjoin(
            UserScore,
            (UserScore.beatmap_id == PackBeatmap.beatmap_id) & (UserScore.user_id == user_id),
        )
        .group_by(Pack.id)
        .order_by(Pack.pack_type.asc(), Pack.slug.asc())
    )

    rows = db.execute(stmt).all()

    standard: list[PackProgress] = []
    other: list[PackProgress] = []

    totals = TotalsSummary()

    for row in rows:
        cleared = int(row.cleared)
        total = int(row.total)
        completion = (cleared / total) if total else 0.0
        progress = PackProgress(
            id=row.id,
            slug=row.slug,
            name=row.name,
            pack_type=row.pack_type,
            category=row.category,
            cleared=cleared,
            total=total,
            completion=completion,
        )

        section = totals.standard if row.pack_type == "standard" else totals.other
        bucket = standard if row.pack_type == "standard" else other
        bucket.append(progress)

        section.beatmaps.cleared += cleared
        section.beatmaps.total += total
        section.packs.total += 1
        if cleared == total and total > 0:
            section.packs.cleared += 1

    return standard, other, totals
