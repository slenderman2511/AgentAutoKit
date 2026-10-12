#!/usr/bin/env bash
# Swap the vocal of a finished song to a consenting person's voice (Seed-VC, local, GPL-3.0), remix with the backing.
#   sing_swap.sh --voice <name> --song out/song.wav [--semi 0] [--steps 40]      (run from the project root)
# Needs: voice/consent/<name>.md · voice/refs/<name>/ref*.wav · setup.sh tools + singing. Output next to the song:
#   <song>-<name>.wav + .mp3   (work files in <song dir>/swap-<name>/)
set -euo pipefail
voice=""; song=""; semi=0; steps=40
while [ $# -gt 0 ]; do case "$1" in
  --voice) voice=$2; shift 2 ;; --song) song=$2; shift 2 ;; --semi) semi=$2; shift 2 ;; --steps) steps=$2; shift 2 ;;
  *) echo "unknown arg $1" >&2; exit 2 ;; esac; done
[ -n "$voice" ] && [ -f "$song" ] || { echo "usage: sing_swap.sh --voice <name> --song <file>" >&2; exit 2; }
consent="voice/consent/$voice.md"
{ [ -f "$consent" ] && ! grep -q '<full name>' "$consent"; } \
  || { echo "refusing: $consent is missing or still the unfilled template — no consent on file, no clone" >&2; exit 1; }
ls voice/refs/"$voice"/ref*.wav >/dev/null 2>&1 || { echo "no reference clips in voice/refs/$voice/ — run pick_refs.py" >&2; exit 1; }
[ -x vendor/seed-vc/.venv/bin/python ] || { echo "run setup.sh singing first" >&2; exit 1; }

root=$PWD; dir=$(cd "$(dirname "$song")" && pwd); base=$(basename "${song%.*}")
work="$dir/swap-$voice"; mkdir -p "$work"
sep="$work/htdemucs/$base"
[ -f "$sep/vocals.wav" ] || .venv-voice/bin/python -m demucs -d cpu --two-stems vocals -o "$work" "$song"   # MPS fails silently
# Seed-VC reads at most 30 s of reference → concatenate the clips up to that.
for f in voice/refs/"$voice"/ref*.wav; do echo "file '$root/$f'"; done > "$work/refs.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$work/refs.txt" -t 30 -ar 44100 -ac 1 "$work/target.wav"
(cd vendor/seed-vc && .venv/bin/python inference.py --source "$sep/vocals.wav" --target "$work/target.wav" \
  --output "$work" --diffusion-steps "$steps" --length-adjust 1.0 --inference-cfg-rate 0.7 \
  --f0-condition True --auto-f0-adjust False --semi-tone-shift "$semi" --fp16 False) 2>&1 | grep -viE 'warn' | tail -3
conv=$(ls -t "$work"/vc_*.wav | head -1)
final="$dir/$base-$voice"
ffmpeg -y -loglevel error -i "$sep/no_vocals.wav" -i "$conv" -filter_complex \
  "[1:a]aresample=44100,highpass=f=80[v];[0:a]aresample=44100[m];[m][v]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.2:LRA=11" \
  -ar 44100 "$final.wav"
ffmpeg -y -loglevel error -i "$final.wav" -c:a libmp3lame -q:a 2 "$final.mp3"
echo "wrote $final.wav + $final.mp3 (converted vocal: $conv)"
