"""
Parses a user-supplied transcript into word-level timestamps, as an
alternative to running Whisper -- for callers who already have (or want to
hand-write) an exact transcript and don't want ASR guessing at it.

Accepts two formats, auto-detected:
  1. Real SRT (numbered cues with `HH:MM:SS,mmm --> HH:MM:SS,mmm`).
  2. A simpler paste-friendly format: `(mm:ss) sentence text` per marker,
     for anyone typing or pasting a rough transcript by hand rather than
     exporting one from a captioning tool.
"""

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
_MARKER_RE = re.compile(r"\((?:(\d+):)?(\d{1,2}):(\d{2})\)")


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


def parse_marker_format(content: str) -> list[dict]:
    """
    Parses `(0:04) some sentence here (0:08) next sentence` style text --
    each marker's cue runs until the next marker's start. The last cue has
    no following marker to bound it, so its end is estimated from word
    count (~0.4s/word) instead.
    """
    matches = list(_MARKER_RE.finditer(content))
    if not matches:
        return []

    cues = []
    for i, m in enumerate(matches):
        hours = int(m.group(1)) if m.group(1) else 0
        minutes, seconds = int(m.group(2)), int(m.group(3))
        start = hours * 3600 + minutes * 60 + seconds

        text_start = m.end()
        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[text_start:text_end].strip()
        if not text:
            continue

        is_last = i == len(matches) - 1
        # Non-final cues get their real end overwritten below once every
        # cue's start is known; this placeholder only matters for the last one.
        end = start + max(1.0, len(text.split()) * 0.4) if is_last else start
        cues.append({"start": start, "end": end, "text": text})

    # Non-final cues borrow their end from the next cue's start, now that
    # every cue's start is known.
    for i in range(len(cues) - 1):
        cues[i]["end"] = cues[i + 1]["start"]

    return cues


def parse_transcript(content: str) -> list[dict]:
    if "-->" in content:
        return parse_srt(content)
    return parse_marker_format(content)


def cues_to_words(cues: list[dict], keyword_set: set[str]) -> list[dict]:
    """
    Expands each cue into word-level timestamps by spreading its words
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
    cues = parse_transcript(content)
    if not cues:
        raise ValueError(
            "Could not parse this transcript -- expected SRT (00:00:01,000 --> 00:00:04,000) or (mm:ss) marker format."
        )
    keyword_set = {k.lower() for k in (keyword_list or [])}
    return cues_to_words(cues, keyword_set)
