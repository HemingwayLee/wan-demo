"""Prepare uploads for Wan-Animate with ffmpeg and Pillow, and add the source audio to the result."""

import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.config import settings


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]} failed: {proc.stderr.strip()[-500:]}")
    return proc.stdout


def probe_video(path: Path) -> dict:
    """Displayed width/height (rotation applied), duration in seconds, and whether it has audio."""
    info = json.loads(
        _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    )
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValueError("The uploaded file has no video stream")
    width, height = int(video["width"]), int(video["height"])
    rotation = next(
        (int(d.get("rotation", 0)) for d in video.get("side_data_list", []) if "rotation" in d), 0
    )
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {
        "width": width,
        "height": height,
        "duration": float(info["format"].get("duration") or video.get("duration") or 0),
        "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def generation_size(src_width: int, src_height: int, short_side: int) -> tuple[int, int]:
    """Keep the source aspect ratio with the short side at `short_side`; both sides multiples of 16."""
    aspect = max(src_width, src_height) / min(src_width, src_height)
    long_side = max(short_side, round(short_side * min(aspect, 2.0) / 16) * 16)
    return (short_side, long_side) if src_width <= src_height else (long_side, short_side)


def prepare_driving_video(src: Path, dest: Path, width: int, height: int, max_seconds: float) -> int:
    """Re-encode at 16 fps and the generation size (center crop). Returns the frame count."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(max_seconds),
        "-vf", f"fps={settings.fps},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-an", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(dest),
    ])
    out = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
        "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(dest),
    ])
    return int(out.strip())


def prepare_reference_image(src: Path, dest: Path, width: int, height: int, fit: str) -> None:
    """Fit the character image to the generation size: `crop` fills the frame, `pad` keeps the whole
    image and extends its edge pixels, which blends better than solid bars."""
    image = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if fit == "crop":
        # Bias the crop upwards so a portrait keeps the head.
        ImageOps.fit(image, (width, height), Image.LANCZOS, centering=(0.5, 0.35)).save(dest)
        return
    scale = min(width / image.width, height / image.height)
    w, h = max(1, round(image.width * scale)), max(1, round(image.height * scale))
    pixels = np.asarray(image.resize((w, h), Image.LANCZOS))
    left, top = (width - w) // 2, (height - h) // 2
    padded = np.pad(pixels, ((top, height - h - top), (left, width - w - left), (0, 0)), mode="edge")
    Image.fromarray(padded).save(dest)


def plan_segments(frames: int) -> tuple[int, int]:
    """(frames per segment, segment count) to cover `frames`; segment lengths are 4n+1."""
    seg, overlap = settings.segment_frames, settings.overlap_frames
    if frames <= seg:
        return max(5, math.ceil((frames - 1) / 4) * 4 + 1), 1
    return seg, 1 + math.ceil((frames - seg) / (seg - overlap))


def is_black(video: Path) -> bool:
    """True when every frame is (near) black: what NaNs in the diffusion model decode to."""
    out = _run([
        "ffmpeg", "-v", "error", "-i", str(video), "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YMAX:file=-",
        "-f", "null", "-",
    ])
    peaks = [float(line.split("=")[1]) for line in out.splitlines() if "YMAX=" in line]
    return bool(peaks) and max(peaks) <= 20


def add_audio(video: Path, audio_src: Path, dest: Path, seconds: float) -> None:
    """Mux the driving video's audio (from its start, as the frames were) into the result.
    The audio is cut to the video's length; -shortest would instead cut the video's last
    frames when the audio is a little shorter."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(video), "-t", f"{seconds:.3f}", "-i", str(audio_src),
        "-map", "0:v", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", str(dest),
    ])
