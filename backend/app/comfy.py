"""ComfyUI HTTP client and the Wan2.2-Animate workflow (API format)."""

from pathlib import Path

import requests

from app.config import settings

NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
    "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
    "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)

# ComfyUI model folder of each configured model file, for the readiness check.
# ComfyUI-GGUF lists .gguf files under its own keys (unet_gguf, clip_gguf).
REQUIRED_MODELS = {
    "unet_gguf": "animate_model",
    "clip_gguf": "text_encoder",
    "vae": "vae",
    "loras": "distill_lora",
    "detection": "vitpose_model",
}


def url(path: str) -> str:
    return f"{settings.comfyui_url.rstrip('/')}{path}"


def ws_url(client_id: str) -> str:
    return url(f"/ws?clientId={client_id}").replace("http", "ws", 1)


def system_stats() -> dict:
    res = requests.get(url("/system_stats"), timeout=5)
    res.raise_for_status()
    return res.json()


def missing_models() -> list[str]:
    missing = []
    for folder, key in REQUIRED_MODELS.items():
        res = requests.get(url(f"/models/{folder}"), timeout=5)
        available = set(res.json()) if res.ok else set()
        names = [getattr(settings, key)] + ([settings.yolo_model] if folder == "detection" else [])
        missing += [f"{folder}/{name}" for name in names if name not in available]
    return missing


def upload(path: Path, name: str) -> str:
    """Copy a file into ComfyUI's input folder; returns the name nodes refer to it by."""
    with path.open("rb") as f:
        res = requests.post(
            url("/upload/image"),
            files={"image": (name, f)},
            data={"overwrite": "true", "subfolder": "wan-demo"},
            timeout=300,
        )
    res.raise_for_status()
    body = res.json()
    return f"{body['subfolder']}/{body['name']}" if body.get("subfolder") else body["name"]


def queue_prompt(prompt: dict, client_id: str) -> str:
    res = requests.post(url("/prompt"), json={"prompt": prompt, "client_id": client_id}, timeout=30)
    if not res.ok:
        raise RuntimeError(f"ComfyUI rejected the workflow: {res.text[:1000]}")
    return res.json()["prompt_id"]


def history(prompt_id: str) -> dict | None:
    res = requests.get(url(f"/history/{prompt_id}"), timeout=10)
    res.raise_for_status()
    return res.json().get(prompt_id)


def is_queued(prompt_id: str) -> bool:
    res = requests.get(url("/queue"), timeout=10)
    res.raise_for_status()
    body = res.json()
    return any(item[1] == prompt_id for item in body["queue_running"] + body["queue_pending"])


def cancel(prompt_id: str) -> None:
    # Drop it from the pending queue, and interrupt it if it is the one running.
    requests.post(url("/queue"), json={"delete": [prompt_id]}, timeout=10)
    requests.post(url("/interrupt"), json={"prompt_id": prompt_id}, timeout=10)


def download_output(file: dict, dest: Path) -> None:
    params = {"filename": file["filename"], "subfolder": file.get("subfolder", ""), "type": file.get("type", "output")}
    with requests.get(url("/view"), params=params, stream=True, timeout=300) as res:
        res.raise_for_status()
        with dest.open("wb") as f:
            for chunk in res.iter_content(1 << 20):
                f.write(chunk)


def build_animate_workflow(
    *,
    job_id: int,
    image: str,
    video: str,
    prompt: str,
    width: int,
    height: int,
    frames: int,
    segment_frames: int,
    segments: int,
    steps: int,
    seed: int,
    retarget: bool,
) -> tuple[dict, list[str]]:
    """Returns (workflow, sampler node ids in segment order).

    Animate mode: the character from `image` performs the motion of `video`, in the image's own scene.
    Longer videos are generated as chained segments, each continuing from the end of the previous one.
    """
    nodes: dict[str, dict] = {}

    def add(node_id: str, class_type: str, **inputs) -> str:
        nodes[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id

    # Models: quantized Animate 14B + 4-step distill LoRA.
    add("unet", "UnetLoaderGGUF", unet_name=settings.animate_model)
    add("lora", "LoraLoaderModelOnly", model=["unet", 0], lora_name=settings.distill_lora, strength_model=1.0)
    add("model", "ModelSamplingSD3", model=["lora", 0], shift=8.0)
    add("clip", "CLIPLoaderGGUF", clip_name=settings.text_encoder, type="wan")
    add("vae", "VAELoader", vae_name=settings.vae)
    add("positive", "CLIPTextEncode", text=prompt, clip=["clip", 0])
    # With the distill LoRA, CFG is 1 and the negative has no effect, so skip encoding one.
    add("negative", "ConditioningZeroOut", conditioning=["positive", 0])

    # Inputs: the reference image and the driving video, both already at the generation size.
    add("ref", "LoadImage", image=image)
    add("video", "LoadVideo", file=video)
    add("frames", "GetVideoComponents", video=["video", 0])

    # Pose skeletons and face crops from the driving video (ViTPose + YOLO on the CPU via ONNX).
    add("pose_model", "OnnxDetectionModelLoader", vitpose_model=settings.vitpose_model,
        yolo_model=settings.yolo_model, onnx_device="CPUExecutionProvider")
    detect = dict(model=["pose_model", 0], images=["frames", 0], width=width, height=height)
    if retarget:
        # Rescale the skeleton to the reference character's body proportions.
        detect["retarget_image"] = ["ref", 0]
    add("detect", "PoseAndFaceDetection", **detect)
    add("pose", "DrawViTPose", pose_data=["detect", 0], width=width, height=height, retarget_padding=16,
        body_stick_width=-1, hand_stick_width=-1, draw_head=True)
    add("pose_video", "CreateVideo", images=["pose", 0], fps=float(settings.fps))
    add("save_pose", "SaveVideo", video=["pose_video", 0], filename_prefix=f"wan-demo/job{job_id}_pose",
        format="auto", **{"format.codec": "auto"})

    samplers, combined = [], None
    for i in range(segments):
        animate = dict(
            positive=["positive", 0], negative=["negative", 0], vae=["vae", 0], width=width, height=height,
            length=segment_frames, batch_size=1, reference_image=["ref", 0], face_video=["detect", 1],
            pose_video=["pose", 0], continue_motion_max_frames=settings.overlap_frames, video_frame_offset=0,
        )
        if i > 0:
            animate["continue_motion"] = [f"new{i - 1}", 0]
            animate["video_frame_offset"] = [f"animate{i - 1}", 5]
        add(f"animate{i}", "WanAnimateToVideo", **animate)
        add(f"sample{i}", "KSampler", model=["model", 0], seed=seed, steps=steps, cfg=1.0, sampler_name="euler",
            scheduler="simple", positive=[f"animate{i}", 0], negative=[f"animate{i}", 1],
            latent_image=[f"animate{i}", 2], denoise=1.0)
        # Drop the reference-image latent, decode, then drop the frames repeated from the previous segment.
        add(f"trim{i}", "TrimVideoLatent", samples=[f"sample{i}", 0], trim_amount=[f"animate{i}", 3])
        add(f"decode{i}", "VAEDecode", samples=[f"trim{i}", 0], vae=["vae", 0])
        add(f"new{i}", "ImageFromBatch", image=[f"decode{i}", 0], batch_index=[f"animate{i}", 4], length=4096)
        combined = f"new{i}" if combined is None else add(f"concat{i}", "ImageBatch", image1=[combined, 0], image2=[f"new{i}", 0])
        samplers.append(f"sample{i}")

    # The last segment pads past the end of the driving video; cut back to its length.
    add("result_frames", "ImageFromBatch", image=[combined, 0], batch_index=0, length=frames)
    add("result_video", "CreateVideo", images=["result_frames", 0], fps=float(settings.fps))
    add("save_result", "SaveVideo", video=["result_video", 0], filename_prefix=f"wan-demo/job{job_id}_result",
        format="auto", **{"format.codec": "auto"})
    return nodes, samplers
