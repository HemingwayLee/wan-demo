# wan-demo

Web app to play with [Wan2.2-Animate](https://huggingface.co/Wan-AI/Wan2.2-Animate-14B): upload a photo of a person and a dance video, and the person in the photo performs the dance.

- **Frontend:** React + MUI (Vite), http://localhost:5175
- **Backend:** FastAPI + Postgres, http://localhost:8002/docs
- **Inference:** ComfyUI running natively on the Mac (Apple GPU via MPS) with the `Q4_K_M` GGUF of Wan2.2-Animate-14B

```
browser ─▶ frontend (Docker) ─▶ backend (Docker) ─▶ ComfyUI (native, :8188, MPS)
                                    │
                                    └─▶ Postgres (Docker)
```

ComfyUI can't run in Docker here: containers on macOS have no access to the Apple GPU.

## Setup (once)

```bash
scripts/setup_comfyui.sh     # ComfyUI v0.42.5 + ComfyUI-GGUF + WanAnimatePreprocess into ./comfyui
scripts/download_models.sh   # ~18 GB into ./comfyui/models
```

| Model | File | Size |
|---|---|---|
| Wan2.2-Animate-14B | `unet/Wan2.2-Animate-14B-Q4_K_M.gguf` | 11.5 GB |
| Text encoder | `text_encoders/umt5-xxl-encoder-Q5_K_M.gguf` | 4.2 GB |
| VAE | `vae/wan_2.1_vae.safetensors` | 0.25 GB |
| 4-step distill LoRA | `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | 0.74 GB |
| Pose / person detection | `detection/vitpose-l-wholebody.onnx`, `detection/yolov10m.onnx` | 1.3 GB |

To try another quantization: `ANIMATE_QUANT=Q5_K_M scripts/download_models.sh`, then set `ANIMATE_MODEL=Wan2.2-Animate-14B-Q5_K_M.gguf` in `.env`.

## Run

```bash
scripts/run_comfyui.sh                               # terminal 1: ComfyUI on the GPU
docker compose -f docker-compose.dev.yml up          # terminal 2: db + backend + frontend, hot reload
```

Open http://localhost:5175. The chip in the top bar shows whether ComfyUI is reachable and has all models.

The backend and frontend run on the prebuilt `video2text-demo-backend` / `video2text-demo-frontend` images (`pull_policy: never`), which already contain FastAPI, ffmpeg, React, MUI and Vite, so nothing is downloaded or built. If those images are removed, rebuild them from `../video2text-demo`.

## How a job runs

1. **Prepare (backend, ffmpeg + Pillow):** the video is cut to the chosen length, converted to 16 fps (Wan's native rate) and scaled to a size with the video's aspect ratio (short side 480/576/720, multiples of 16). The image is fitted to the same size (pad with edge pixels, or crop).
2. **ComfyUI workflow** (built in `backend/app/comfy.py`; saved per job as `data/jobs/<id>/workflow.json`):
   ViTPose + YOLO extract the skeleton and face crops from the video → `WanAnimateToVideo` + `KSampler` (4 steps, CFG 1, with the lightx2v LoRA) → VAE decode.
   Videos longer than 77 frames (~4.8 s) are generated in chained segments; each continues from the last 5 frames of the previous one.
3. **Finish:** the result is downloaded from ComfyUI and the driving video's audio is muxed back in.

Jobs live in Postgres and run one at a time. A backend restart (hot reload) resumes watching a job that ComfyUI is already running.
