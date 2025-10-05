from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from beatmapr.app.database import get_db
from beatmapr.app.models import User
from beatmapr.app.schemas import LeaderboardEntry, LeaderboardResponse, SearchUserItem

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> LeaderboardResponse:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()

    stmt = select(User).order_by(User.cleared_beatmaps.desc()).offset((page - 1) * page_size).limit(page_size)
    users = db.execute(stmt).scalars().all()

    entries = [
        LeaderboardEntry(
            user=SearchUserItem(id=user.id, username=user.username, country=user.country),
            cleared_beatmaps=user.cleared_beatmaps,
            completion_percent=user.completion_percent,
            last_refreshed_at=user.last_refreshed_at,
        )
        for user in users
    ]

    return LeaderboardResponse(total=total, page=page, page_size=page_size, results=entries)
