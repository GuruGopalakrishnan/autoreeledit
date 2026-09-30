"""Shared pipeline orchestration used by both a CLI entry point and the FastAPI app -- one place that owns 'transcribe, then render' so front ends can't drift apart."""

import hashlib
from pathlib import Path
from typing import Callable

from .compositor import run_compositor
from .srt_parser import load_words_from_srt
from .transcriber import load_transcript, save_transcript, transcribe


class PipelineError(Exception):
    """Raised for any expected failure (bad input, transcription/render error) so callers can show a clean message instead of a raw traceback."""


# Pools an auto-picked style is drawn from, grouped by what the transcript's
# content/pace suggests fits best -- not a real content-understanding model,
# just heuristics over what's already computed for other purposes (speaker
# diarization, the keyword list, word timing). Kept separate from
# RESERVED_STYLE_NAMES in app.py; a style here is skipped automatically if
# it's ever removed from config.json (see the filter in pick_auto_style).
_AUTO_STYLE_POOLS = {
    "speaker": ["speaker-colors"],
    "high_energy": ["mrbeast", "hormozi", "glitch-pop", "wave-bounce", "aarit-zoom"],
    "standard": ["classic-yellow", "karaoke-highlight", "karaoke-wipe", "popline-box", "rise-up"],
    "calm": ["typewriter-glow", "corporate-lower-third", "flamingo-underline", "name-tag", "decrypt-reveal", "blur-pop"],
}


def pick_auto_style(words: list[dict], config: dict) -> str:
    """
    Picks a base caption style automatically from the transcript, for the
    "just upload video + transcript, no style picker" flow.

    Not a real content-understanding model -- plain heuristics: multiple
    detected speakers (see srt_parser.py's "Speaker A: " tagging) means
    speaker-colors is almost always the right call, since it's the one
    style built specifically to distinguish who's talking; a high ratio of
    hype/energy keywords (config.json's keyword_list) or a fast speaking
    pace favors a punchy influencer-style preset; otherwise a calmer
    general-purpose one.

    The specific pick within a pool is a stable hash of the transcript
    text, not random -- re-running the same content always lands on the
    same style instead of flip-flopping on every export.
    """
    if not words:
        return config.get("default_style", "typewriter-glow")

    speakers = {w["speaker_index"] for w in words if w.get("speaker_index") is not None}
    if len(speakers) > 1:
        pool = _AUTO_STYLE_POOLS["speaker"]
    else:
        duration = max(0.1, words[-1]["end"] - words[0]["start"])
        pace = len(words) / duration
        keyword_ratio = sum(1 for w in words if w.get("is_keyword")) / len(words)
        if pace > 3.0 or keyword_ratio > 0.12:
            pool = _AUTO_STYLE_POOLS["high_energy"]
        elif pace > 2.0:
            pool = _AUTO_STYLE_POOLS["standard"]
        else:
            pool = _AUTO_STYLE_POOLS["calm"]

    valid_styles = set(config.get("styles", {}).keys())
    pool = [s for s in pool if s in valid_styles] or sorted(valid_styles)

    signature = " ".join(w["text"] for w in words[:40])
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return pool[int(digest, 16) % len(pool)]


def apply_style_choice(config: dict, words: list[dict], base_style: str, auto_mode: bool) -> dict:
    """
    Returns a config copy with `base_style` as the default (non-triggered)
    preset. When `auto_mode` is off, also mutates `words` in place to clear
    every keyword flag so Dramatic/Energetic never fire and base_style is
    the only style shown. Shared by the quick auto-process flow
    (`run_pipeline`) and the editor's render-from-project endpoint, so the
    two can't drift on what "pick a style" actually means.
    """
    effective_config = dict(config)
    effective_config["default_style"] = base_style
    if not auto_mode:
        effective_config["energetic_word_count"] = 10**9
        for w in words:
            w["is_keyword"] = False
    return effective_config


def run_pipeline(
    input_path: str,
    output_path: str,
    config: dict,
    base_style: str = "auto",
    auto_mode: bool = True,
    cache_transcript: bool = False,
    transcript_srt_path: str | None = None,
    on_stage: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    """
    Renders the styled, captioned video to `output_path`. Word-level
    timestamps come from `transcript_srt_path` when given (a user-supplied
    SRT file -- skips Whisper entirely, since a real transcript beats ASR
    guessing at it), otherwise from Whisper (transcribing `input_path`, or
    reusing a cached transcript when `cache_transcript` is set).

    `base_style` is the preset used for ordinary (non-triggered) captions --
    any key in config.json's `styles` (see the Style Gallery), or "auto" to
    have pick_auto_style() choose one from the transcript. When `auto_mode`
    is on (default), the rule-based Dramatic/Energetic triggers still fire
    on top of that base for keyword moments and fast speech; off,
    `base_style` is the only style that ever shows.

    `on_stage("transcribing" | "rendering")` and `on_progress(frames_done,
    frames_total)` are optional hooks for a caller that wants to report
    progress.

    Returns the actual style id used -- the caller's own `base_style` unless
    it was "auto", in which case this is the only way to learn what got picked.
    """
    stage = on_stage or (lambda _stage: None)

    input_p = Path(input_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    stage("transcribing")
    if transcript_srt_path:
        try:
            words = load_words_from_srt(transcript_srt_path, keyword_list=config.get("keyword_list", []))
        except Exception as e:  # noqa: BLE001
            raise PipelineError(f"Could not read the transcript file: {e}") from e
    else:
        transcript_cache = input_p.with_suffix(".transcript.json")
        if cache_transcript and transcript_cache.exists():
            transcript = load_transcript(str(transcript_cache))
        else:
            try:
                transcript = transcribe(
                    str(input_p),
                    model_name=config.get("whisper_model", "base"),
                    keyword_list=config.get("keyword_list", []),
                )
            except Exception as e:  # noqa: BLE001 -- normalized into PipelineError for callers
                raise PipelineError(f"Transcription failed: {e}") from e
            save_transcript(transcript, str(transcript_cache))
        words = transcript["words"]

    if not words:
        raise PipelineError("No words to caption -- is there speech in this video, or content in the transcript file?")

    if base_style == "auto":
        base_style = pick_auto_style(words, config)

    effective_config = apply_style_choice(config, words, base_style, auto_mode)

    stage("rendering")
    try:
        run_compositor(str(input_p), str(output_path), words, effective_config, on_progress=on_progress)
    except Exception as e:  # noqa: BLE001
        raise PipelineError(f"Rendering failed: {e}") from e

    return base_style
