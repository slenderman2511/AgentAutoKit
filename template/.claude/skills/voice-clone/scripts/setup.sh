#!/usr/bin/env bash
# voice-clone setup. Usage: setup.sh tools|speech|singing   (run from the project root)
#   tools   → .venv-voice      demucs, faster-whisper, resemblyzer (reference picking + checks)
#   speech  → vendor/vixtts    coqui-tts 0.24.2 + capleaf/viXTTS weights (Coqui CPML: NON-COMMERCIAL)
#   singing → vendor/seed-vc   Seed-VC (GPL-3.0) + Apple Silicon patches
set -euo pipefail
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
[ -x "$UV" ] || { echo "uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not found (brew install ffmpeg / apt install ffmpeg)" >&2; exit 1; }
TORCH=("torch==2.5.1" "torchaudio==2.5.1")   # newer torchaudio pulls torchcodec and breaks loading

case "${1:-}" in
tools)
  [ -d .venv-voice ] || "$UV" venv -q --python 3.11 .venv-voice
  "$UV" pip install -q --python .venv-voice/bin/python "${TORCH[@]}" demucs faster-whisper soundfile \
    "numpy==1.26.4" resemblyzer "setuptools<81"
  echo "OK — .venv-voice" ;;
speech)
  mkdir -p vendor/vixtts
  [ -d vendor/vixtts/.venv ] || "$UV" venv -q --python 3.11 vendor/vixtts/.venv
  "$UV" pip install -q --python vendor/vixtts/.venv/bin/python "${TORCH[@]}" "coqui-tts==0.24.2" \
    "transformers==4.42.4" faster-whisper soundfile click "numpy==1.26.4" huggingface_hub
  vendor/vixtts/.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('capleaf/viXTTS', local_dir='vendor/vixtts/model',
                  allow_patterns=['config.json', 'model.pth', 'vocab.json', 'LICENSE*', 'README*'])
PY
  echo "OK — vendor/vixtts (weights are Coqui CPML: non-commercial use only)" ;;
singing)
  [ -d vendor/seed-vc ] || git clone --depth 1 https://github.com/Plachtaa/seed-vc.git vendor/seed-vc
  cd vendor/seed-vc
  grep -q "GNU GENERAL PUBLIC LICENSE" LICENSE || { echo "Seed-VC license changed — re-check before use" >&2; exit 1; }
  [ -d .venv ] || "$UV" venv -q --python 3.10 .venv
  "$UV" pip install -q --python .venv/bin/python "${TORCH[@]}" "torchvision==0.20.1" accelerate scipy==1.13.1 \
    librosa==0.10.2 "huggingface-hub>=0.28.1" munch==4.0.0 einops==0.8.0 descript-audio-codec==1.0.0 pydub \
    resemblyzer transformers==4.46.3 soundfile numpy==1.26.4 pyyaml python-dotenv hydra-core==1.3.2 "setuptools<81"
  if [ "$(uname -s)" = Darwin ]; then
    # MPS has no float64 and no conv_transpose1d above 65536 channels → F0 as float32, BigVGAN vocoder on CPU.
    sed -i '' -E 's/torch\.from_numpy\((F0_[a-z]+)\)\.to\(device\)/torch.from_numpy(\1).float().to(device)/' inference.py
    sed -i '' -E 's/bigvgan_model = bigvgan_model\.eval\(\)\.to\(device\)$/bigvgan_model = bigvgan_model.eval().to("cpu")/' inference.py
    sed -i '' -E 's/^        vocoder_fn = bigvgan_model$/        vocoder_fn = lambda x: bigvgan_model(x.cpu()).to(device)/' inference.py
    grep -q 'bigvgan_model(x.cpu())' inference.py && grep -q 'from_numpy(F0_ori).float()' inference.py \
      || { echo "Apple Silicon patch did not apply — upstream inference.py changed; patch by hand" >&2; exit 1; }
  fi
  echo "OK — vendor/seed-vc" ;;
*) echo "usage: setup.sh tools|speech|singing" >&2; exit 2 ;;
esac
