from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RankCounts(BaseModel):
    SSH: int = 0
    SS: int = 0
    SH: int = 0
    S: int = 0
    A: int = 0
    B: int = 0
    C: int = 0
    D: int = 0


class UserSummary(BaseModel):
    id: int
    username: str
    country: Optional[str]
    avatar_url: Optional[str]
    ranked_score: Optional[int]
    global_rank: Optional[int]
    total_scores: Optional[int]
    cleared_beatmaps: int
    completion_percent: float
    last_refreshed_at: Optional[datetime]
    rank_counts: RankCounts


class PackSummary(BaseModel):
    id: int
    slug: str
    name: str
    pack_type: str
    category: Optional[str]
    beatmap_count: int
    released_at: Optional[datetime]


class PackProgress(BaseModel):
    pack_id: int = Field(alias="id")
    slug: str
    name: str
    pack_type: str
    category: Optional[str]
    cleared: int
    total: int
    completion: float

    class Config:
        populate_by_name = True


class BeatmapDetail(BaseModel):
    beatmap_id: int
    beatmapset_id: Optional[int]
    title: Optional[str]
    artist: Optional[str]
    version: Optional[str]
    star_rating: Optional[float]
    hit_length: Optional[int]
    total_length: Optional[int]
    bpm: Optional[float]
    cs: Optional[float]
    ar: Optional[float]
    od: Optional[float]
    hp: Optional[float]
    ranked_status: Optional[str]
    cleared: bool = False
    grade: Optional[str] = None


class PackDetailResponse(BaseModel):
    pack: PackSummary
    beatmaps: List[BeatmapDetail]


class CountPair(BaseModel):
    cleared: int = 0
    total: int = 0


class TotalsSection(BaseModel):
    beatmaps: CountPair = Field(default_factory=CountPair)
    packs: CountPair = Field(default_factory=CountPair)


class TotalsSummary(BaseModel):
    standard: TotalsSection = Field(default_factory=TotalsSection)
    other: TotalsSection = Field(default_factory=TotalsSection)
    overall_completion_percent: float = 0.0


class UserProfileResponse(BaseModel):
    user: UserSummary
    standard: List[PackProgress]
    other: List[PackProgress]
    totals: TotalsSummary


class SearchUserItem(BaseModel):
    id: int
    username: str
    country: Optional[str]


class LeaderboardEntry(BaseModel):
    user: SearchUserItem
    cleared_beatmaps: int
    completion_percent: float
    last_refreshed_at: Optional[datetime]


class LeaderboardResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[LeaderboardEntry]
