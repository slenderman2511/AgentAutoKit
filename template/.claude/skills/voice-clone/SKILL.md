---
name: voice-clone
description: Clone a consenting person's voice locally — speech (text → their voice, viXTTS/XTTS) or singing (swap the vocal of an existing song to their voice, Seed-VC) — and score the result without listening. Use when the user asks to "clone a voice", "đổi giọng", "lồng tiếng bằng giọng của X", make a voiceover or a song in a specific real person's voice, or to pick clean reference clips from a recording. Covers the consent gate, license check, reference selection (Demucs + Whisper), synthesis with best-of-N, singing voice conversion, objective checks (Whisper word match, speaker similarity, LUFS) and the Apple Silicon patches. Not for celebrity or unconsented voices — the scripts refuse without a consent file.
---
# Voice clone (local, consent-gated)

Two pipelines that share the same first two steps. Everything runs locally; nothing is uploaded.

```
consent file ──► reference clips ──┬─► speech:  text ──► tts_clone.py ──► wav      (viXTTS)
(step 0)         (step 1)          └─► singing: song ──► sing_swap.sh ──► wav+mp3  (Seed-VC)
                                                   └────► check.py (word match · similarity)
```

All commands below run from the project root. `$SKILL` = this skill's directory
(`.claude/skills/voice-clone` in a template install).

## 0. Gates — do these before any audio work

1. **Consent.** The voice must belong to a person who agreed to it. Copy
   `$SKILL/consent-template.md` to `voice/consent/<name>.md` and fill it with what the user tells
   you (who, date, form of consent, scope: internal / public / commercial, how to withdraw). Every
   script takes `--voice <name>` and **exits if `voice/consent/<name>.md` is missing**. Never write
   the consent file on your own assumption — ask the user, and record exactly the scope they state.
   Refuse: public figures, anyone the user cannot confirm agreed, impersonation meant to deceive.
2. **Scope follows the consent file.** "Internal demo" consent → output stays local; do not publish,
   commit or upload it. Label AI-generated voice as such wherever the output is shown, unless the
   user (who owns that decision) says otherwise.
3. **License** (check upstream again before shipping — licenses change):

   | Tool | Used for | License | Commercial output |
   |---|---|---|---|
   | Demucs `htdemucs` | split vocals / music | MIT | yes |
   | faster-whisper | pick refs, score words | MIT | yes |
   | Resemblyzer | speaker similarity | Apache-2.0 | yes |
   | Seed-VC | singing voice conversion | GPL-3.0 (run as a separate tool, do not link into product code) | yes |
   | viXTTS / XTTS-v2 | Vietnamese + multilingual speech | **Coqui CPML — non-commercial** | **no**: demos only; for commercial speech use a licensed service (e.g. ElevenLabs with the speaker's consent) or a real recording |

   Tell the user the license class of whatever you are about to use; the decision to accept a
   license risk is theirs, and gets written into the project's notes.
4. **Never commit** voice samples, model weights or generated audio. Add to `.gitignore`:
   `voice/samples/ voice/refs/ vendor/ out/ *.wav *.mp3`.

## 1. Setup (once per project)

```bash
bash $SKILL/scripts/setup.sh tools      # .venv-voice: demucs, faster-whisper, resemblyzer (always)
bash $SKILL/scripts/setup.sh speech     # vendor/vixtts: coqui-tts + capleaf/viXTTS weights (~2 GB)
bash $SKILL/scripts/setup.sh singing    # vendor/seed-vc: clone + deps + Apple Silicon patches
```
Needs `uv`, `ffmpeg`, Python 3.10/3.11. Tested on an M1 Max 32 GB; works on CUDA without the patches.

## 2. Reference clips

Put the person's recordings in `voice/samples/<name>/` (wav/mp3/mp4; speech, ideally 1–5 min, one
speaker). Clean studio speech can be used as is. For recordings with music or noise:

```bash
.venv-voice/bin/python $SKILL/scripts/pick_refs.py --voice <name> [--lang vi]
```
It separates vocals (Demucs, CPU), transcribes with Whisper, keeps 5–12 s sentences with high
confidence and the best voice-to-background ratio, and writes `voice/refs/<name>/ref00..05.wav`
plus `refs.json` (what was picked and why). Read `refs.json`; if fewer than 3 clips pass, ask for
a cleaner recording instead of lowering the thresholds.

## 3a. Speech — text in the person's voice

```bash
vendor/vixtts/.venv/bin/python $SKILL/scripts/tts_clone.py --voice <name> \
  --text script.txt --out out/vo.wav [--lang vi] [--best 4]
```
- `script.txt`: one paragraph per line. Write numbers and abbreviations as words.
- `--best N`: synthesizes each sentence N times at different temperatures, has Whisper transcribe
  each take and keeps the closest match (stops early at ≥ 0.97). Use 4 for final output.
- Sentences shorter than ~10 words are merged with the next one — XTTS garbles very short inputs.
- Runs on CPU (≈ 1–2× real time on M1 Max); MPS fails on a conv1d size limit.

## 3b. Singing — swap a song's vocal to the person's voice

Input is a finished song with any singer (AI-generated or recorded, and yours to use).
```bash
bash $SKILL/scripts/sing_swap.sh --voice <name> --song out/song.wav [--semi 0]
```
Demucs splits `vocals` / `no_vocals` → Seed-VC converts the vocal with `--f0-condition True`
(keeps the melody) → remix with the backing track → loudness-normalize to −14 LUFS → wav + mp3.
- Pick the source singer in the same register as the target (a female voice onto a female lead);
  otherwise shift with `--semi ±N` semitones.
- Seed-VC uses at most 30 s of reference; the script concatenates the refs up to that.
- Slow on Mac: ≈ 9× real time (a 3-minute song ≈ 30 min). Run it in the background with a
  2-hour timeout.

## 4. Check — you cannot hear, so measure

```bash
.venv-voice/bin/python $SKILL/scripts/check.py --audio out/vo.wav --text script.txt [--voice <name>] [--lang vi]
```
| Metric | Meaning | Rough bar |
|---|---|---|
| word match (Whisper vs script) | intelligibility | speech ≥ 0.85 · singing ≥ 0.7 (singing over music scores lower even when fine) |
| similarity (Resemblyzer cosine vs refs, with `--voice`) | sounds like the person | ≥ 0.75; compare with the unconverted source to see the gain |
| LUFS | loudness | −14 for music/streaming, −18…−16 for voiceover |

For a song pass the separated vocal (`…/vocals.wav`), not the full mix. These numbers are
screening only — **a human must listen before the result is called done**; say so in the hand-off,
and report the numbers as measured (never "sounds good").

## Known failures

| Symptom | Fix |
|---|---|
| `KeyError: 'vi'` / "language not supported" in coqui-tts | handled in `tts_clone.py` (adds `char_limits['vi']`, lowercases text itself) |
| `torchaudio` wants `torchcodec` | keep `torch==2.5.1 torchaudio==2.5.1` (setup.sh pins them) |
| MPS: float64 / `conv_transpose1d` errors in Seed-VC | `setup.sh singing` patches `inference.py`: F0 → float32, BigVGAN vocoder on CPU |
| Demucs on MPS writes nothing | always `-d cpu` (the scripts do) |
| Resemblyzer: `No module named pkg_resources` | `setuptools<81` (setup.sh pins it) |
| Cloned speech drops or repeats words | raise `--best`, split long sentences, spell out numbers |
| Converted vocal sounds strained | wrong register → `--semi`, or choose a source singer closer to the target |

## Hand-off

Report: whose voice + consent scope, tools and their license class, the measured numbers, where
the files are (local paths), and that a human still has to listen. Do not publish, upload or
commit audio unless the consent scope covers it and the user asks.
