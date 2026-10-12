"""Shared consent gate: every voice-clone script calls require_consent(name) before touching audio."""
import sys
from pathlib import Path


def require_consent(name: str) -> Path:
    f = Path('voice/consent') / f'{name}.md'
    if not f.is_file() or '<full name>' in f.read_text():
        sys.exit(f'refusing: {f} is missing or still the unfilled template — no consent on file, no clone. '
                 f'Fill it from what the voice owner agreed to (see consent-template.md).')
    return f
