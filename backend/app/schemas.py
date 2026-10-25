from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    prompt: str
    options: dict[str, Any]
    width: int | None
    height: int | None
    frames: int | None
    segments: int | None
    progress: float
    message: str | None
    error: str | None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    # Which of the job's files exist: image, video, pose, result
    files: list[str] = []
