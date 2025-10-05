from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from beatmapr.app.database import get_db
from beatmapr.app.models import Beatmap, Pack, PackBeatmap, UserScore
from beatmapr.app.schemas import BeatmapDetail, PackDetailResponse, PackSummary

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("/summary", response_model=dict[str, List[PackSummary]])
def list_pack_summary(db: Session = Depends(get_db)) -> dict[str, List[PackSummary]]:
    stmt = (
        select(
            Pack.id,
            Pack.slug,
            Pack.name,
            Pack.pack_type,
            Pack.category,
            Pack.released_at,
            func.count(PackBeatmap.beatmap_id).label("beatmap_count"),
        )
        .join(PackBeatmap, PackBeatmap.pack_id == Pack.id)
        .group_by(Pack.id)
        .order_by(Pack.pack_type.asc(), Pack.slug.asc())
    )
    rows = db.execute(stmt).all()

    grouped: dict[str, list[PackSummary]] = defaultdict(list)
    for row in rows:
        grouped[row.pack_type].append(
            PackSummary(
                id=row.id,
                slug=row.slug,
                name=row.name,
                pack_type=row.pack_type,
                category=row.category,
                beatmap_count=row.beatmap_count,
                released_at=row.released_at,
            )
        )

    return grouped


@router.get("/{pack_id}", response_model=PackDetailResponse)
def get_pack_detail(
    pack_id: int,
    user_id: int | None = Query(default=None, description="Optional user id to include completion flags"),
    db: Session = Depends(get_db),
) -> PackDetailResponse:
    pack = db.get(Pack, pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pack not found")

    beatmap_ids = [
        row.beatmap_id
        for row in db.execute(select(PackBeatmap.beatmap_id).where(PackBeatmap.pack_id == pack_id).order_by(PackBeatmap.position.asc()))
    ]

    beatmaps = db.execute(select(Beatmap).where(Beatmap.beatmap_id.in_(beatmap_ids))).scalars().all()
    beatmap_map = {bm.beatmap_id: bm for bm in beatmaps}

    user_grades: Dict[int, str] = {}
    if user_id is not None:
        grade_rows = db.execute(
            select(UserScore.beatmap_id, UserScore.grade).where(
                UserScore.user_id == user_id,
                UserScore.beatmap_id.in_(beatmap_ids),
            )
        )
        user_grades = {beatmap_id: (grade or "") for beatmap_id, grade in grade_rows}

    beatmap_details: list[BeatmapDetail] = []
    for beatmap_id in beatmap_ids:
        beatmap = beatmap_map.get(beatmap_id)
        if beatmap is None:
            continue
        beatmap_details.append(
            BeatmapDetail(
                beatmap_id=beatmap.beatmap_id,
                beatmapset_id=beatmap.beatmapset_id,
                title=beatmap.title,
                artist=beatmap.artist,
                version=beatmap.version,
                star_rating=beatmap.star_rating,
                hit_length=beatmap.hit_length,
                total_length=beatmap.total_length,
                bpm=beatmap.bpm,
                cs=beatmap.cs,
                ar=beatmap.ar,
                od=beatmap.od,
                hp=beatmap.hp,
                ranked_status=beatmap.ranked_status,
                cleared=beatmap_id in user_grades,
                grade=user_grades.get(beatmap_id),
            )
        )

    pack_summary = PackSummary(
        id=pack.id,
        slug=pack.slug,
        name=pack.name,
        pack_type=pack.pack_type,
        category=pack.category,
        beatmap_count=len(beatmap_ids),
        released_at=pack.released_at,
    )

    return PackDetailResponse(pack=pack_summary, beatmaps=beatmap_details)
