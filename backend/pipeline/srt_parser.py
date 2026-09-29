"""Parses a user-supplied SRT subtitle file into word-level timestamps, as an alternative to running Whisper -- for callers who already have (or want to hand-write) an exact transcript and don't want ASR guessing at it."""

import re
from pathlib import Path

_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
_CUE_RE = re.compile(
    r"(?:\d+\s*\n)?"  # optional numeric index line
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n"
    r"((?:.+\n?)+?)"  # cue text, possibly multiple lines
    r"(?=\n\s*\n|\Z)",
    re.MULTILINE,
)


def _time_to_seconds(t: str) -> float:
    m = _TIME_RE.match(t)
    if not m:
        raise ValueError(f"Unrecognized SRT timestamp: {t!r}")
    h, mi, s, ms = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_srt(content: str) -> list[dict]:
    """Returns a list of {start, end, text} cues in file order."""
    normalized = content.replace("\r\n", "\n").strip() + "\n\n"
    cues = []
    for m in _CUE_RE.finditer(normalized):
        start = _time_to_seconds(m.group(1))
        end = _time_to_seconds(m.group(2))
        text = " ".join(line.strip() for line in m.group(3).strip().splitlines() if line.strip())
        if text:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def cues_to_words(cues: list[dict], keyword_set: set[str]) -> list[dict]:
    """
    Expands each SRT cue into word-level timestamps by spreading its words
    evenly across the cue's [start, end] window -- the same even-distribution
    approach used when no better timing signal exists, so the existing
    word-by-word animation engine (which needs a start/end per word) keeps
    working the same as it does with real Whisper timestamps.
    """
    words: list[dict] = []
    for cue_id, cue in enumerate(cues):
        tokens = cue["text"].split()
        if not tokens:
            continue
        span = max(cue["end"] - cue["start"], 0.1)
        per_word = span / len(tokens)
        for i, token in enumerate(tokens):
            w_start = cue["start"] + i * per_word
            w_end = cue["start"] + (i + 1) * per_word
            clean = re.sub(r"[^\w]", "", token).lower()
            # cue_id lets the compositor show exactly this cue's words together
            # instead of an arbitrary sliding time window that can straddle
            # two unrelated cues and overflow the frame.
            words.append({"text": token, "start": w_start, "end": w_end, "is_keyword": clean in keyword_set, "cue_id": cue_id})
    return words


def load_words_from_srt(path: str, keyword_list: list[str] | None = None) -> list[dict]:
    content = Path(path).read_text(encoding="utf-8-sig")
    cues = parse_srt(content)
    if not cues:
        raise ValueError("Could not parse any subtitle cues from this SRT file -- check its format.")
    keyword_set = {k.lower() for k in (keyword_list or [])}
    return cues_to_words(cues, keyword_set)
