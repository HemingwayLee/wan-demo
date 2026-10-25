#!/usr/bin/env bash
# Run ComfyUI on the Mac GPU (MPS). The backend container reaches it at host.docker.internal:8188.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY="$ROOT/comfyui"

# Fall back to the CPU for the few operators MPS doesn't implement instead of failing.
export PYTORCH_ENABLE_MPS_FALLBACK=1

cd "$COMFY"
# --bf16-unet: on MPS ComfyUI defaults the Wan model to fp16, which overflows to NaN and
# decodes as an all-black video. bf16 has fp32's range.
exec "$COMFY/venv/bin/python" main.py --listen 127.0.0.1 --port "${COMFY_PORT:-8188}" --bf16-unet "$@"
