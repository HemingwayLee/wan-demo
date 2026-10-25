import logging
import mimetypes
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import comfy, schemas, worker
from app.config import settings
from app.db import Base, engine, get_db
from app.models import ACTIVE_STATUSES, Job

logging.basicConfig(level=logging.INFO)

# Files a job folder can hold, by the name the API serves them under.
JOB_FILES = {"pose": "pose.mp4", "result": "result.mp4"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience: create tables on startup. Swap for Alembic migrations later.
    Base.metadata.create_all(bind=engine)
    stop = worker.start()
    yield
    stop.set()


app = FastAPI(title="wan-demo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _job_files(job: Job) -> dict[str, Path]:
    folder = worker.job_dir(job.id)
    files = {"image": folder / job.image_name, "video": folder / job.video_name}
    files |= {key: folder / name for key, name in JOB_FILES.items()}
    return files


def _read(job: Job) -> schemas.JobRead:
    read = schemas.JobRead.model_validate(job)
    read.files = [key for key, path in _job_files(job).items() if path.exists()]
    return read


def _media_type(upload: UploadFile) -> str:
    """"image" / "video" from the upload's content type, or its extension when the client
    sent a generic type such as application/octet-stream."""
    content_type = upload.content_type or ""
    if not content_type.startswith(("image/", "video/")):
        content_type = mimetypes.guess_type(upload.filename or "")[0] or ""
    return content_type.split("/")[0]


def _get_job(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@app.get("/api/comfyui")
def comfyui_status():
    """Whether ComfyUI is reachable and has every model the workflow needs."""
    try:
        stats = comfy.system_stats()
        missing = comfy.missing_models()
    except requests.RequestException:
        return {"online": False, "url": settings.comfyui_url, "missing_models": []}
    device = (stats.get("devices") or [{}])[0]
    return {
        "online": True,
        "url": settings.comfyui_url,
        "version": stats["system"].get("comfyui_version"),
        "device": device.get("type"),
        "ram_total": stats["system"].get("ram_total"),
        "missing_models": missing,
        "model": settings.animate_model,
    }


@app.get("/api/jobs", response_model=list[schemas.JobRead])
def list_jobs(db: Session = Depends(get_db)):
    return [_read(job) for job in db.scalars(select(Job).order_by(Job.id.desc())).all()]


@app.post("/api/jobs", response_model=schemas.JobRead, status_code=201)
def create_job(
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    prompt: str = Form("a person is dancing"),
    max_seconds: float = Form(5),
    # A plain int: form values arrive as strings, which Literal[480, ...] won't coerce.
    resolution: int = Form(480),
    steps: int = Form(4),
    seed: int | None = Form(None),
    retarget: bool = Form(False),
    fit: Literal["pad", "crop"] = Form("pad"),
    db: Session = Depends(get_db),
):
    if _media_type(image) != "image":
        raise HTTPException(status_code=422, detail="The character must be an image file")
    if _media_type(video) != "video":
        raise HTTPException(status_code=422, detail="The motion must be a video file")
    if not 1 <= max_seconds <= settings.max_seconds:
        raise HTTPException(status_code=422, detail=f"Length must be 1–{settings.max_seconds} seconds")
    if resolution not in (480, 576, 720):
        raise HTTPException(status_code=422, detail="Resolution must be 480, 576 or 720")
    if not 1 <= steps <= 20:
        raise HTTPException(status_code=422, detail="Steps must be 1–20")

    job = Job(
        prompt=prompt.strip() or "a person is dancing",
        options={
            "max_seconds": max_seconds, "resolution": resolution, "steps": steps,
            "seed": seed if seed is not None else worker.random_seed(), "retarget": retarget, "fit": fit,
        },
        image_name="source_image" + Path(image.filename or "").suffix.lower(),
        video_name="source_video" + Path(video.filename or "").suffix.lower(),
        message="Waiting in queue",
    )
    db.add(job)
    db.flush()
    folder = worker.job_dir(job.id)
    folder.mkdir(parents=True, exist_ok=True)
    for upload, name in ((image, job.image_name), (video, job.video_name)):
        with (folder / name).open("wb") as f:
            shutil.copyfileobj(upload.file, f)
    db.commit()
    return _read(job)


@app.get("/api/jobs/{job_id}", response_model=schemas.JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    return _read(_get_job(db, job_id))


@app.post("/api/jobs/{job_id}/cancel", response_model=schemas.JobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = _get_job(db, job_id)
    if job.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="The job has already finished")
    # The worker stops it (and tells ComfyUI) on its next check.
    job.cancel_requested = True
    job.message = "Cancelling"
    db.commit()
    return _read(job)


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = _get_job(db, job_id)
    if job.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Cancel the job before deleting it")
    shutil.rmtree(worker.job_dir(job.id), ignore_errors=True)
    db.delete(job)
    db.commit()


@app.get("/api/jobs/{job_id}/files/{kind}")
def job_file(job_id: int, kind: str, download: bool = False, db: Session = Depends(get_db)):
    job = _get_job(db, job_id)
    path = _job_files(job).get(kind)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    filename = f"wan-demo-{job.id}-{kind}{path.suffix}" if download else None
    return FileResponse(path, filename=filename)
