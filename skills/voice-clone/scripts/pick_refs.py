"""Pick clean reference clips for cloning from voice/samples/<name>/ → voice/refs/<name>/refNN.wav + refs.json.
Demucs separates the voice, Whisper finds 5–12 s sentences with high confidence, ranked by voice/background ratio.
  .venv-voice/bin/python pick_refs.py --voice <name> [--lang vi] [--keep 6]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gate import require_consent

ap = argparse.ArgumentParser()
ap.add_argument('--voice', required=True)
ap.add_argument('--lang', default='vi')
ap.add_argument('--keep', type=int, default=6)
a = ap.parse_args()
require_consent(a.voice)

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

src_dir, out = Path('voice/samples') / a.voice, Path('voice/refs') / a.voice
work = out / 'work'
work.mkdir(parents=True, exist_ok=True)
inputs = sorted(p for p in src_dir.iterdir() if p.suffix.lower() in {'.wav', '.mp3', '.m4a', '.mp4', '.flac', '.ogg'})
if not inputs:
    sys.exit(f'no recordings in {src_dir}')
for p in inputs:  # normalize to wav, then split voice / background on CPU (MPS fails silently on long files)
    wav = work / f'{p.stem}.wav'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(p), '-vn', '-ar', '44100', '-ac', '2', str(wav)], check=True)
    if not (work / 'htdemucs' / p.stem / 'vocals.wav').exists():
        subprocess.run([sys.executable, '-m', 'demucs', '-d', 'cpu', '--two-stems', 'vocals', '-o', str(work), str(wav)], check=True)

model = WhisperModel('small', device='cpu', compute_type='int8')
cands = []
for d in sorted((work / 'htdemucs').iterdir()):
    voc, sr = sf.read(d / 'vocals.wav')
    bg, _ = sf.read(d / 'no_vocals.wav')
    voc = voc.mean(axis=1) if voc.ndim > 1 else voc
    bg = bg.mean(axis=1) if bg.ndim > 1 else bg
    segs, _ = model.transcribe(str(d / 'vocals.wav'), language=a.lang, vad_filter=True)
    for s in segs:
        dur = s.end - s.start
        if not 5.0 <= dur <= 12.0 or s.avg_logprob < -0.45 or s.no_speech_prob > 0.2:
            continue
        i, j = int(s.start * sr), int(s.end * sr)
        rv = float(np.sqrt(np.mean(voc[i:j] ** 2)) + 1e-9)
        rb = float(np.sqrt(np.mean(bg[i:j] ** 2)) + 1e-9)
        cands.append({'src': d.name, 'start': round(s.start, 2), 'end': round(s.end, 2), 'dur': round(dur, 2),
                      'logprob': round(s.avg_logprob, 3), 'snr_db': round(20 * np.log10(rv / rb), 1)})

cands.sort(key=lambda c: (-c['snr_db'], -c['logprob']))
picked = cands[:a.keep]
for n, c in enumerate(picked):
    dst = out / f'ref{n:02d}.wav'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(c['start']), '-to', str(c['end']),
                    '-i', str(work / 'htdemucs' / c['src'] / 'vocals.wav'),
                    '-af', 'highpass=f=70,loudnorm=I=-20', '-ar', '22050', '-ac', '1', str(dst)], check=True)
    c['file'] = dst.name
# refs.json holds no transcript: the words may be personal, and nothing downstream needs them.
(out / 'refs.json').write_text(json.dumps({'candidates': len(cands), 'picked': picked}, indent=1))
print(f'{len(cands)} candidates, kept {len(picked)} → {out}')
for c in picked:
    print(f"  {c['file']}  {c['dur']} s  voice/bg {c['snr_db']} dB  logprob {c['logprob']}")
if len(picked) < 3:
    print('fewer than 3 clean clips — ask for a cleaner recording rather than loosening the thresholds', file=sys.stderr)
