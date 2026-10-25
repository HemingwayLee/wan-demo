#!/usr/bin/env bash
# Install ComfyUI natively on the Mac (Docker can't use the Apple GPU), with the custom nodes Wan-Animate needs.
# Re-running is safe: it skips what is already there.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY="$ROOT/comfyui"
COMFY_VERSION="${COMFY_VERSION:-v0.42.5}"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.11}"

if [ ! -d "$COMFY/.git" ]; then
  git clone --depth 1 --branch "$COMFY_VERSION" https://github.com/comfyanonymous/ComfyUI "$COMFY"
fi

if [ ! -x "$COMFY/venv/bin/python" ]; then
  "$PYTHON" -m venv "$COMFY/venv"
fi
PIP="$COMFY/venv/bin/pip"
"$PIP" install --upgrade pip
"$PIP" install -r "$COMFY/requirements.txt"

# GGUF loaders (UnetLoaderGGUF, CLIPLoaderGGUF) for the quantized Wan-Animate model and text encoder.
if [ ! -d "$COMFY/custom_nodes/ComfyUI-GGUF" ]; then
  git clone --depth 1 https://github.com/city96/ComfyUI-GGUF "$COMFY/custom_nodes/ComfyUI-GGUF"
fi
"$PIP" install -r "$COMFY/custom_nodes/ComfyUI-GGUF/requirements.txt"

# ViTPose + YOLO pose/face extraction from the driving video, as in the official Wan-Animate preprocessing.
if [ ! -d "$COMFY/custom_nodes/ComfyUI-WanAnimatePreprocess" ]; then
  git clone --depth 1 https://github.com/kijai/ComfyUI-WanAnimatePreprocess "$COMFY/custom_nodes/ComfyUI-WanAnimatePreprocess"
fi
# Its requirements.txt asks for onnxruntime-gpu (CUDA only); the plain package runs on the Mac CPU.
"$PIP" install onnx onnxruntime opencv-python matplotlib

echo "ComfyUI is ready. Next: scripts/download_models.sh, then scripts/run_comfyui.sh"
