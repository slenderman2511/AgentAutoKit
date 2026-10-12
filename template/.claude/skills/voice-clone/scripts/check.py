"""Score cloned audio without listening: Whisper word match vs the script, speaker similarity vs the refs, LUFS.
  .venv-voice/bin/python check.py --audio out/vo.wav [--text script.txt] [--voice <name>] [--lang vi]
For a song pass the separated vocal (…/vocals.wav) — full mixes score low on both metrics.
"""
import argparse
import difflib
import re
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--audio', required=True)
ap.add_argument('--text')
ap.add_argument('--voice')
ap.add_argument('--lang', default='vi')
a = ap.parse_args()

r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', a.audio, '-af', 'ebur128', '-f', 'null', '-'],
                   capture_output=True, text=True).stderr
m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r)
print(f'LUFS        {m[-1] if m else "?"}')

if a.text:
    from faster_whisper import WhisperModel
    norm = lambda t: re.sub(r'[^\w\s]', ' ', re.sub(r'\[[^\]]*\]', ' ', t.lower())).split()  # drops [Verse] tags
    segs, _ = WhisperModel('small', device='cpu', compute_type='int8').transcribe(a.audio, language=a.lang)
    got = ' '.join(s.text for s in segs)
    ratio = difflib.SequenceMatcher(None, norm(Path(a.text).read_text()), norm(got)).ratio()
    print(f'word match  {ratio:.2f}')
    print(f'heard       {got.strip()[:300]}')

if a.voice:
    import numpy as np
    from resemblyzer import VoiceEncoder, preprocess_wav
    enc = VoiceEncoder('cpu', verbose=False)
    refs = sorted((Path('voice/refs') / a.voice).glob('ref*.wav'))
    ref = np.mean([enc.embed_utterance(preprocess_wav(p)) for p in refs], axis=0)
    emb = enc.embed_utterance(preprocess_wav(Path(a.audio)))
    print(f'similarity  {float(np.dot(ref, emb) / (np.linalg.norm(ref) * np.linalg.norm(emb))):.2f}  (vs {len(refs)} refs)')
