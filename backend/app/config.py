from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    cors_origins: list[str] = ["http://localhost:5175"]

    # Uploads, intermediate files and results, one folder per job.
    data_dir: str = "/data"

    # ComfyUI runs natively on the Mac (Docker has no access to the Apple GPU).
    comfyui_url: str = "http://host.docker.internal:8188"

    # Model files, as named in comfyui/models (see scripts/download_models.sh).
    animate_model: str = "Wan2.2-Animate-14B-Q4_K_M.gguf"
    text_encoder: str = "umt5-xxl-encoder-Q5_K_M.gguf"
    vae: str = "wan_2.1_vae.safetensors"
    distill_lora: str = "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
    vitpose_model: str = "vitpose-l-wholebody.onnx"
    yolo_model: str = "yolov10m.onnx"

    # Wan generates at 16 fps, in segments of `segment_frames` (4n+1); later segments
    # continue from the last `overlap_frames` of the previous one.
    fps: int = 16
    segment_frames: int = 77
    overlap_frames: int = 5
    max_seconds: int = 20


settings = Settings()
