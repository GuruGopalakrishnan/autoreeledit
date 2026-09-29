"""Shared pipeline orchestration used by both a CLI entry point and the FastAPI app -- one place that owns 'transcribe, then render' so front ends can't drift apart."""

from pathlib import Path
from typing import Callable

from .compositor import run_compositor
from .srt_parser import load_words_from_srt
from .transcriber import load_transcript, save_transcript, transcribe


class PipelineError(Exception):
    """Raised for any expected failure (bad input, transcription/render error) so callers can show a clean message instead of a raw traceback."""


def run_pipeline(
    input_path: str,
    output_path: str,
    config: dict,
    style: str = "auto",
    cache_transcript: bool = False,
    transcript_srt_path: str | None = None,
    on_stage: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    """
    Renders the styled, captioned video to `output_path`. Word-level
    timestamps come from `transcript_srt_path` when given (a user-supplied
    SRT file -- skips Whisper entirely, since a real transcript beats ASR
    guessing at it), otherwise from Whisper (transcribing `input_path`, or
    reusing a cached transcript when `cache_transcript` is set).

    `on_stage("transcribing" | "rendering")` and `on_progress(frames_done,
    frames_total)` are optional hooks for a caller that wants to report
    progress.
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

    effective_config = dict(config)
    if style != "auto":
        # Force a single style: silence the auto-triggers (keyword -> dramatic,
        # word-rate -> energetic) and make the chosen style the only one that ever fires.
        effective_config["default_style"] = style
        effective_config["energetic_word_count"] = 10**9
        for w in words:
            w["is_keyword"] = style == "dramatic"

    stage("rendering")
    try:
        run_compositor(str(input_p), str(output_path), words, effective_config, on_progress=on_progress)
    except Exception as e:  # noqa: BLE001
        raise PipelineError(f"Rendering failed: {e}") from e
