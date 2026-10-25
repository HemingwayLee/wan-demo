#!/usr/bin/env bash
# Download the Wan-Animate models (~18 GB) into comfyui/models. Interrupted downloads resume.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS="$ROOT/comfyui/models"
HF="https://huggingface.co"

# Quantization of the 14B Animate model: Q4_K_M (11.5 GB) fits 36 GB of unified memory comfortably.
ANIMATE_QUANT="${ANIMATE_QUANT:-Q4_K_M}"

download() {  # <url> <dest>
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ]; then
    echo "✓ $(basename "$dest")"
    return
  fi
  echo "↓ $(basename "$dest")"
  curl -fL --retry 5 -C - -o "$dest.part" "$url"
  mv "$dest.part" "$dest"
}

download "$HF/QuantStack/Wan2.2-Animate-14B-GGUF/resolve/main/Wan2.2-Animate-14B-$ANIMATE_QUANT.gguf" \
  "$MODELS/unet/Wan2.2-Animate-14B-$ANIMATE_QUANT.gguf"
download "$HF/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q5_K_M.gguf" \
  "$MODELS/text_encoders/umt5-xxl-encoder-Q5_K_M.gguf"
download "$HF/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
  "$MODELS/vae/wan_2.1_vae.safetensors"
# 4-step distillation LoRA: cuts sampling from ~20 steps with CFG to 4-6 steps without.
download "$HF/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" \
  "$MODELS/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
download "$HF/JunkyByte/easy_ViTPose/resolve/main/onnx/wholebody/vitpose-l-wholebody.onnx" \
  "$MODELS/detection/vitpose-l-wholebody.onnx"
download "$HF/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx" \
  "$MODELS/detection/yolov10m.onnx"

echo "All models downloaded."
