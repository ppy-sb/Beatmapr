from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from beatmapr.app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Pack(Base, TimestampMixin):
    __tablename__ = "packs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    pack_type: Mapped[str] = mapped_column(String(32), default="standard")
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    beatmaps: Mapped[List["Beatmap"]] = relationship(
        secondary="pack_beatmaps",
        back_populates="packs",
        lazy="selectin",
    )


class Beatmap(Base, TimestampMixin):
    __tablename__ = "beatmaps"

    beatmap_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    beatmapset_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    artist: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mode: Mapped[int] = mapped_column(Integer, default=0)
    hit_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cs: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    od: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    star_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ranked_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    packs: Mapped[List[Pack]] = relationship(
        secondary="pack_beatmaps",
        back_populates="beatmaps",
        lazy="selectin",
    )
    scores: Mapped[List["UserScore"]] = relationship(back_populates="beatmap", cascade="all, delete-orphan")


class PackBeatmap(Base):
    __tablename__ = "pack_beatmaps"
    __table_args__ = (UniqueConstraint("pack_id", "beatmap_id", name="uq_pack_beatmap"),)

    pack_id: Mapped[int] = mapped_column(ForeignKey("packs.id", ondelete="CASCADE"), primary_key=True)
    beatmap_id: Mapped[int] = mapped_column(ForeignKey("beatmaps.beatmap_id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ranked_score: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    global_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_scores: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cleared_beatmaps: Mapped[int] = mapped_column(Integer, default=0)
    completion_percent: Mapped[float] = mapped_column(Float, default=0.0)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    scores: Mapped[List["UserScore"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserScore(Base, TimestampMixin):
    __tablename__ = "user_scores"
    __table_args__ = (UniqueConstraint("user_id", "beatmap_id", name="uq_user_score"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    beatmap_id: Mapped[int] = mapped_column(ForeignKey("beatmaps.beatmap_id", ondelete="CASCADE"), index=True)
    grade: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    score: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_combo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mods: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    achieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="scores")
    beatmap: Mapped[Beatmap] = relationship(back_populates="scores")
