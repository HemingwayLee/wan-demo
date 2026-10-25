from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# queued → preparing → running → done | error | cancelled
ACTIVE_STATUSES = ("queued", "preparing", "running")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    # Generation options: max_seconds, resolution, steps, seed, retarget, fit
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    image_name: Mapped[str] = mapped_column(String(255))
    video_name: Mapped[str] = mapped_column(String(255))

    # Filled in while preparing: generation size and frame count at 16 fps.
    width: Mapped[int | None]
    height: Mapped[int | None]
    frames: Mapped[int | None]
    segments: Mapped[int | None]

    comfy_prompt_id: Mapped[str | None] = mapped_column(String(64))
    # Node ids of each segment's sampler, so progress events map to a segment.
    sampler_nodes: Mapped[list[str]] = mapped_column(JSON, default=list)
    progress: Mapped[float] = mapped_column(default=0.0)
    message: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
