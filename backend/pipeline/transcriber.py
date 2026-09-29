"""Whisper-based offline transcription with word-level timestamps and keyword tagging."""

import json
import re
from pathlib import Path
from typing import TypedDict

import whisper


class Word(TypedDict):
    text: str
    start: float
    end: float
    is_keyword: bool


class TranscriptResult(TypedDict):
    text: str
    language: str
    words: list[Word]


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).strip().lower()


def transcribe(video_path: str, model_name: str = "base", keyword_list: list[str] | None = None) -> TranscriptResult:
    """
    Transcribes `video_path` with OpenAI Whisper (offline, word-level
    timestamps) and flags each word as a keyword moment if it (normalized)
    appears in `keyword_list`. The result is a plain dict, JSON-serializable
    as-is, so callers can cache it to disk between pipeline runs instead of
    re-running Whisper on every render.
    """
    keyword_set = {k.lower() for k in (keyword_list or [])}

    model = whisper.load_model(model_name)
    result = model.transcribe(video_path, word_timestamps=True, verbose=False)

    words: list[Word] = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            text = w["word"].strip()
            if not text:
                continue
            words.append(
                {
                    "text": text,
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "is_keyword": _normalize(text) in keyword_set,
                }
            )

    return {"text": result.get("text", "").strip(), "language": result.get("language", "en"), "words": words}


def save_transcript(transcript: TranscriptResult, out_path: str) -> None:
    Path(out_path).write_text(json.dumps(transcript, indent=2), encoding="utf-8")


def load_transcript(path: str) -> TranscriptResult:
    return json.loads(Path(path).read_text(encoding="utf-8"))
