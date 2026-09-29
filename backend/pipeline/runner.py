"""Shared pipeline orchestration used by both a CLI entry point and the FastAPI app -- one place that owns 'transcribe, then render' so front ends can't drift apart."""

from pathlib import Path
from typing import Callable

from .compositor import run_compositor
from .transcriber import load_transcript, save_transcript, transcribe


class PipelineError(Exception):
    """Raised for any expected failure (bad input, transcription/render error) so callers can show a clean message instead of a raw traceback."""


def run_pipeline(
    input_path: str,
    output_path: str,
    config: dict,
    style: str = "auto",
    cache_transcript: bool = False,
    on_stage: Callable[[str], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    """
    Transcribes `input_path` (or reuses a cached transcript) and renders the
    styled, captioned video to `output_path`. `on_stage("transcribing" |
    "rendering")` and `on_progress(frames_done, frames_total)` are optional
    hooks for a caller that wants to report progress.
    """
    stage = on_stage or (lambda _stage: None)

    input_p = Path(input_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    transcript_cache = input_p.with_suffix(".transcript.json")
    stage("transcribing")
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
        raise PipelineError("Transcription produced no words -- is there speech in this video?")

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
