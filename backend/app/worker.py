"""Background worker: runs one job at a time through ComfyUI and tracks its progress.

Job state lives in Postgres, so a backend restart (e.g. a hot reload) picks up where it left off:
a job already queued in ComfyUI is watched again rather than started twice.
"""

import json
import logging
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import select
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from app import comfy, media
from app.config import settings
from app.db import SessionLocal
from app.models import Job

logger = logging.getLogger(__name__)

POLL_SECONDS = 2
# ComfyUI sends progress events to the client that queued the prompt; a fixed id keeps
# them flowing to a restarted backend that resumes watching the job.
CLIENT_ID = "wan-demo-backend"


def job_dir(job_id: int) -> Path:
    return Path(settings.data_dir) / "jobs" / str(job_id)


def update(job_id: int, **fields) -> Job:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()
        return job


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_job() -> Job | None:
    with SessionLocal() as db:
        # A job that was already sent to ComfyUI comes first: resume watching it.
        running = db.scalars(select(Job).where(Job.status == "running").order_by(Job.id)).first()
        if running:
            return running
        # One that was mid-preparation when the backend stopped starts over.
        return db.scalars(
            select(Job).where(Job.status.in_(("preparing", "queued"))).order_by(Job.id)
        ).first()


def _prepare_and_queue(job: Job) -> Job:
    update(job.id, status="preparing", started_at=_now(), message="Preparing video and image", error=None)
    folder = job_dir(job.id)
    opts = job.options
    info = media.probe_video(folder / job.video_name)
    width, height = media.generation_size(info["width"], info["height"], opts["resolution"])
    frames = media.prepare_driving_video(
        folder / job.video_name, folder / "driving.mp4", width, height, opts["max_seconds"]
    )
    media.prepare_reference_image(folder / job.image_name, folder / "reference.png", width, height, opts["fit"])
    segment_frames, segments = media.plan_segments(frames)

    update(job.id, message="Uploading to ComfyUI", width=width, height=height, frames=frames, segments=segments)
    image = comfy.upload(folder / "reference.png", f"job{job.id}_reference.png")
    video = comfy.upload(folder / "driving.mp4", f"job{job.id}_driving.mp4")
    workflow, samplers = comfy.build_animate_workflow(
        job_id=job.id, image=image, video=video, prompt=job.prompt, width=width, height=height,
        frames=frames, segment_frames=segment_frames, segments=segments, steps=opts["steps"],
        seed=opts["seed"], retarget=opts["retarget"],
    )
    (folder / "workflow.json").write_text(json.dumps(workflow, indent=2, ensure_ascii=False))
    prompt_id = comfy.queue_prompt(workflow, CLIENT_ID)
    return update(
        job.id, status="running", comfy_prompt_id=prompt_id, sampler_nodes=samplers,
        message="Queued in ComfyUI", progress=0.02,
    )


def _progress_message(job: Job, event: dict) -> tuple[float, str] | None:
    """Overall progress from a ComfyUI `progress` event: pose detection is the first 5%,
    sampling the segments 5–95%, decoding and saving the rest."""
    node, value, maximum = event["node"], event["value"], max(1, event["max"])
    if node in job.sampler_nodes:
        index = job.sampler_nodes.index(node)
        count = len(job.sampler_nodes)
        overall = 0.05 + 0.9 * (index + value / maximum) / count
        return overall, f"Segment {index + 1}/{count} · step {value}/{maximum}"
    if node == "detect":
        return 0.05 * value / maximum, f"Detecting pose {value}/{maximum} frames"
    return None


_NODE_MESSAGES = {
    "unet": "Loading Wan-Animate model",
    "clip": "Loading text encoder",
    "detect": "Detecting pose",
    "save_result": "Saving video",
}


def _finish(job: Job, outputs: dict) -> None:
    folder = job_dir(job.id)
    for node, name in (("save_pose", "pose.mp4"), ("save_result", "result_silent.mp4")):
        files = outputs.get(node, {}).get("images", [])
        if files:
            comfy.download_output(files[0], folder / name)
    silent = folder / "result_silent.mp4"
    if not silent.exists():
        raise RuntimeError("ComfyUI finished without saving a video")
    if media.is_black(silent):
        raise RuntimeError(
            "The generated video is all black (the model produced NaNs). Start ComfyUI with "
            "scripts/run_comfyui.sh, which runs the model in bf16 instead of fp16."
        )
    if media.probe_video(folder / job.video_name)["has_audio"]:
        media.add_audio(silent, folder / job.video_name, folder / "result.mp4", job.frames / settings.fps)
        silent.unlink()
    else:
        silent.rename(folder / "result.mp4")
    update(job.id, status="done", progress=1.0, message=None, finished_at=_now())


def _watch(job: Job) -> None:
    """Follow the job's ComfyUI execution until it ends, cancels or fails."""
    prompt_id = job.comfy_prompt_id
    last_check = 0.0
    try:
        ws = connect(comfy.ws_url(CLIENT_ID), open_timeout=10, max_size=None)
    except OSError:
        ws = None  # Progress detail is lost, but polling below still finishes the job.
    try:
        while True:
            if ws is not None:
                try:
                    raw = ws.recv(timeout=POLL_SECONDS)
                except TimeoutError:
                    raw = None
                except ConnectionClosed:
                    ws, raw = None, None
            else:
                time.sleep(POLL_SECONDS)
                raw = None

            if isinstance(raw, str):
                event = json.loads(raw)
                data = event.get("data", {})
                if data.get("prompt_id") == prompt_id:
                    if event["type"] == "progress":
                        result = _progress_message(job, data)
                        if result:
                            update(job.id, progress=result[0], message=result[1])
                    elif event["type"] == "executing" and data.get("node") in _NODE_MESSAGES:
                        update(job.id, message=_NODE_MESSAGES[data["node"]])

            if time.monotonic() - last_check < POLL_SECONDS:
                continue
            last_check = time.monotonic()

            with SessionLocal() as db:
                if db.get(Job, job.id).cancel_requested:
                    comfy.cancel(prompt_id)
                    update(job.id, status="cancelled", message=None, finished_at=_now())
                    return

            entry = comfy.history(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("status_str") == "success":
                    update(job.id, message="Downloading result")
                    _finish(job, entry.get("outputs", {}))
                    return
                if status.get("completed") is False or status.get("status_str") == "error":
                    raise RuntimeError(_execution_error(status))
            elif not comfy.is_queued(prompt_id):
                raise RuntimeError("ComfyUI lost the job (was it restarted?)")
    finally:
        if ws is not None:
            ws.close()


def _execution_error(status: dict) -> str:
    for kind, data in status.get("messages", []):
        if kind == "execution_error":
            return f"{data.get('node_type')}: {data.get('exception_message', '').strip()}"
        if kind == "execution_interrupted":
            return "Interrupted in ComfyUI"
    return "ComfyUI reported an error"


def _run_once() -> bool:
    """Process the next job; returns False when there was nothing to do."""
    job = _next_job()
    if job is None:
        return False
    try:
        if job.cancel_requested:
            update(job.id, status="cancelled", message=None, finished_at=_now())
            return True
        if job.status != "running":
            job = _prepare_and_queue(job)
        _watch(job)
    except requests.ConnectionError:
        # ComfyUI isn't up: leave the job as it is and try again shortly.
        update(job.id, message="Waiting for ComfyUI (run scripts/run_comfyui.sh)")
        time.sleep(5)
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        update(job.id, status="error", error=str(exc), message=None, finished_at=_now())
    return True


def _loop(stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            if not _run_once():
                stop.wait(POLL_SECONDS)
        except Exception:
            logger.exception("Worker loop error")
            stop.wait(5)


def start() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=_loop, args=(stop,), name="job-worker", daemon=True).start()
    return stop


def random_seed() -> int:
    return random.randint(0, 2**32 - 1)
