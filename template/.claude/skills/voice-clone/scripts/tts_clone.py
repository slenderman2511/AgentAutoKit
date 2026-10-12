"""Read a script in a consenting person's voice with viXTTS/XTTS (local, CPU). Coqui CPML: non-commercial.
  vendor/vixtts/.venv/bin/python tts_clone.py --voice <name> --text script.txt --out out/vo.wav [--lang vi] [--best 4]
script.txt: one paragraph per line. Refs: voice/refs/<name>/ref*.wav (pick_refs.py) or clean clips you put there.
"""
import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _gate import require_consent

ap = argparse.ArgumentParser()
ap.add_argument('--voice', required=True)
ap.add_argument('--text', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--lang', default='vi')
ap.add_argument('--best', type=int, default=1, help='takes per sentence; Whisper keeps the closest to the text')
ap.add_argument('--model', default='vendor/vixtts/model')
ap.add_argument('--gap', type=float, default=0.28, help='silence between sentences (s)')
a = ap.parse_args()
require_consent(a.voice)

import soundfile as sf
import torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts

refs = sorted(str(p) for p in (Path('voice/refs') / a.voice).glob('ref*.wav'))
if not refs:
    sys.exit(f'no reference clips in voice/refs/{a.voice}/ — run pick_refs.py')

norm = lambda t: re.sub(r'[^\w\s]', ' ', t.lower()).split()
if a.best > 1:
    from faster_whisper import WhisperModel
    judge = WhisperModel('small', device='cpu', compute_type='int8')

    def score(path, text):
        segs, _ = judge.transcribe(str(path), language=a.lang)
        return difflib.SequenceMatcher(None, norm(text), norm(' '.join(x.text for x in segs))).ratio()

cfg = XttsConfig()
cfg.load_json(f'{a.model}/config.json')
model = Xtts.init_from_config(cfg)
model.load_checkpoint(cfg, checkpoint_dir=a.model, use_deepspeed=False)
model.to('cpu')  # MPS: conv1d above 65536 channels is unsupported
if a.lang not in model.tokenizer.char_limits:  # coqui-tts does not declare 'vi' (viXTTS adds it)
    model.tokenizer.char_limits[a.lang] = 250
    _pre = model.tokenizer.preprocess_text
    model.tokenizer.preprocess_text = lambda txt, lang: (
        re.sub(r'\s+', ' ', txt.lower()).strip() if lang == a.lang else _pre(txt, lang))
gpt_lat, spk = model.get_conditioning_latents(audio_path=refs, gpt_cond_len=30, max_ref_length=60, sound_norm_refs=False)


def sentences(text: str) -> list[str]:
    # XTTS garbles very short inputs (< ~10 words) → merge short sentences with the next one.
    merged, buf = [], ''
    for p in (p.strip() for p in re.split(r'(?<=[.?!:])\s+', text) if p.strip()):
        buf = f'{buf} {p}'.strip()
        if len(buf.split()) >= 10:
            merged.append(buf)
            buf = ''
    if buf:
        if merged:
            merged[-1] = f'{merged[-1]} {buf}'
        else:
            merged.append(buf)
    return merged


out = Path(a.out)
tmp = out.parent / f'.{out.stem}-takes'
tmp.mkdir(parents=True, exist_ok=True)
TRIM = ('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,'
        'areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse')
ff = ['ffmpeg', '-y', '-loglevel', 'error']
gap = tmp / 'gap.wav'
subprocess.run(ff + ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', str(a.gap), str(gap)], check=True)

seq, idx = [], 0
for para in (l.strip() for l in Path(a.text).read_text().splitlines() if l.strip()):
    for text in sentences(para):
        best, keep = -1.0, tmp / f's{idx:03d}.wav'
        for k in range(a.best):
            torch.manual_seed(1000 * idx + k)
            r = model.inference(text, a.lang, gpt_lat, spk, temperature=[0.3, 0.45, 0.6, 0.75][k % 4],
                                length_penalty=1.0, repetition_penalty=10.0, top_k=30, top_p=0.85,
                                enable_text_splitting=False)
            take = tmp / f's{idx:03d}-c{k}.wav'
            sf.write(take, r['wav'], 24000)
            sc = score(take, text) if a.best > 1 else 1.0
            if sc > best:
                best = sc
                subprocess.run(['cp', str(take), str(keep)], check=True)
            if sc >= 0.97:
                break
        trimmed = tmp / f's{idx:03d}-t.wav'
        subprocess.run(ff + ['-i', str(keep), '-af', TRIM, '-ar', '48000', '-ac', '1', str(trimmed)], check=True)
        seq += ([gap] if seq else []) + [trimmed]
        print(f'  s{idx:03d}' + (f' match {best:.2f}' if a.best > 1 else ''), flush=True)
        idx += 1

lst = tmp / 'list.txt'
lst.write_text(''.join(f"file '{p.resolve()}'\n" for p in seq))
subprocess.run(ff + ['-f', 'concat', '-safe', '0', '-i', str(lst), '-af', 'loudnorm=I=-18:TP=-1.5',
                     '-ar', '48000', '-ac', '1', str(out)], check=True)
print(f'wrote {out} ({idx} sentences)')
