"""
FastAPI backend: wraps the Whisper + MediaPipe auto-editor pipeline behind
an HTTP API so the Next.js frontend can upload a video, watch progress, and
download the result. Jobs run in a background thread and their state lives
in an in-memory dict -- this is a local, single-user tool, so a database is
more machinery than the problem needs.

Two flows:
  - POST /api/jobs: quick auto-process, upload -> render -> download, no
    review step (Phase 1).
  - POST /api/projects: upload -> transcribe/parse once -> GET the caption
    list, edit captions on the timeline, then POST .../render when ready
    (Phase 3, the editor).
"""

import json
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline import project_store
from pipeline.captions import assign_synthetic_cue_ids, group_into_captions, replace_caption_text, set_caption_keyword
from pipeline.compositor import run_compositor
from pipeline.runner import PipelineError, apply_style_choice, run_pipeline
from pipeline.srt_parser import load_words_from_srt
from pipeline.transcriber import transcribe
from pipeline.video_meta import probe_video

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = BASE_DIR / "config.json"

# Reserved preset names: only ever applied automatically by the rule-based
# trigger (keyword -> Dramatic, fast speech -> Energetic), never offered as
# a user-selectable base style in the gallery.
RESERVED_STYLE_NAMES = {"dramatic", "energetic"}

app = FastAPI(title="autoreel")

# The frontend runs on a different origin (Next.js dev server) during local
# development, so it needs CORS explicitly opened up rather than relying on
# same-origin defaults.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set_job(job_id: str, **patch) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(patch)


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _valid_base_styles(config: dict) -> set[str]:
    return set(config["styles"].keys()) - RESERVED_STYLE_NAMES


# ---------------------------------------------------------------------------
# Style Gallery
# ---------------------------------------------------------------------------


@app.get("/api/styles")
async def list_styles():
    """The Style Gallery's data source: every non-reserved preset in config.json, with enough of its look (font/color/animation/etc) for the frontend to render a live preview card."""
    config = _load_config()
    styles = [{"id": name, **cfg} for name, cfg in config["styles"].items() if name not in RESERVED_STYLE_NAMES]
    return {"styles": styles, "defaultStyle": config.get("default_style", "clean-white")}


# ---------------------------------------------------------------------------
# Phase 1: quick auto-process (upload -> render -> download, no review step)
# ---------------------------------------------------------------------------


def _run_job(
    job_id: str, input_path: Path, output_path: Path, base_style: str, auto_mode: bool, transcript_path: Path | None
) -> None:
    config = _load_config()
    try:

        def on_stage(stage: str) -> None:
            _set_job(job_id, status=stage, progress=0)

        def on_progress(done: int, total: int) -> None:
            pct = int(done / total * 100) if total else 0
            _set_job(job_id, progress=pct)

        run_pipeline(
            str(input_path),
            str(output_path),
            config,
            base_style=base_style,
            auto_mode=auto_mode,
            transcript_srt_path=str(transcript_path) if transcript_path else None,
            on_stage=on_stage,
            on_progress=on_progress,
        )
        _set_job(job_id, status="done", progress=100)
    except PipelineError as e:
        _set_job(job_id, status="failed", error=str(e))
    except Exception as e:  # noqa: BLE001 -- last-resort catch so a job always resolves to failed, never hangs "processing" forever
        _set_job(job_id, status="failed", error=f"Unexpected error: {e}")


@app.post("/api/jobs")
async def create_job(
    video: UploadFile = File(...),
    base_style: str = Form("clean-white"),
    auto_mode: bool = Form(True),
    transcript: UploadFile | None = File(None),
):
    config = _load_config()
    valid_base_styles = _valid_base_styles(config)
    if base_style not in valid_base_styles:
        raise HTTPException(400, f"base_style must be one of {sorted(valid_base_styles)}")

    job_id = uuid.uuid4().hex
    ext = Path(video.filename or "input.mp4").suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{job_id}{ext}"
    with input_path.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    transcript_path: Path | None = None
    if transcript is not None and transcript.filename:
        transcript_path = UPLOAD_DIR / f"{job_id}.srt"
        with transcript_path.open("wb") as f:
            shutil.copyfileobj(transcript.file, f)

    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "error": None}

    thread = threading.Thread(
        target=_run_job, args=(job_id, input_path, output_path, base_style, auto_mode, transcript_path), daemon=True
    )
    thread.start()

    return {"jobId": job_id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return {"jobId": job_id, **job}


@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id: str):
    output_path = OUTPUT_DIR / f"{job_id}.mp4"
    if not output_path.exists():
        raise HTTPException(404, "Output not ready.")
    return FileResponse(output_path, media_type="video/mp4", filename=f"autoreel_{job_id}.mp4")


# ---------------------------------------------------------------------------
# Phase 3: the editor (upload -> review/edit captions on a timeline -> render)
# ---------------------------------------------------------------------------


def _prepare_project(project_id: str, video_path: Path, transcript_path: Path | None) -> None:
    config = _load_config()
    try:
        meta = probe_video(str(video_path))

        if transcript_path:
            words = load_words_from_srt(str(transcript_path), keyword_list=config.get("keyword_list", []))
        else:
            result = transcribe(str(video_path), model_name=config.get("whisper_model", "base"), keyword_list=config.get("keyword_list", []))
            words = result["words"]

        if not words:
            raise PipelineError("No words to caption -- is there speech in this video, or content in the transcript file?")

        assign_synthetic_cue_ids(words)
        project_store.mark_ready(project_id, meta["duration"], meta["width"], meta["height"], words)
    except PipelineError as e:
        project_store.mark_failed(project_id, str(e))
    except Exception as e:  # noqa: BLE001
        project_store.mark_failed(project_id, f"Unexpected error: {e}")


@app.post("/api/projects")
async def create_project(video: UploadFile = File(...), transcript: UploadFile | None = File(None)):
    project_id = uuid.uuid4().hex
    ext = Path(video.filename or "input.mp4").suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{project_id}{ext}"
    with input_path.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    transcript_path: Path | None = None
    if transcript is not None and transcript.filename:
        transcript_path = UPLOAD_DIR / f"{project_id}.srt"
        with transcript_path.open("wb") as f:
            shutil.copyfileobj(transcript.file, f)

    project_store.create_project(project_id, str(input_path))

    thread = threading.Thread(target=_prepare_project, args=(project_id, input_path, transcript_path), daemon=True)
    thread.start()

    return {"projectId": project_id}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    captions = group_into_captions(project["words"]) if project["status"] == "ready" else []
    return {
        "id": project_id,
        "status": project["status"],
        "error": project["error"],
        "duration": project["duration"],
        "width": project["width"],
        "height": project["height"],
        "captions": captions,
    }


@app.get("/api/projects/{project_id}/video")
async def get_project_video(project_id: str):
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    return FileResponse(project["video_path"], media_type="video/mp4")


@app.patch("/api/projects/{project_id}/captions/{cue_id}")
async def update_caption(project_id: str, cue_id: int, body: dict = Body(...)):
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    if project["status"] != "ready":
        raise HTTPException(409, "Project is not ready yet.")

    words = project["words"]
    if "text" in body:
        config = _load_config()
        keyword_set = {k.lower() for k in config.get("keyword_list", [])}
        words = replace_caption_text(words, cue_id, body["text"], keyword_set)
    if "forceKeyword" in body:
        set_caption_keyword(words, cue_id, bool(body["forceKeyword"]))

    project_store.set_words(project_id, words)
    captions = group_into_captions(words)
    updated = next((c for c in captions if c["id"] == cue_id), None)
    if updated is None:
        raise HTTPException(404, "Caption not found.")
    return {"caption": updated}


def _run_project_render(job_id: str, project: dict, output_path: Path, base_style: str, auto_mode: bool) -> None:
    config = _load_config()
    try:
        words = [dict(w) for w in project["words"]]  # apply_style_choice may mutate is_keyword; don't touch the stored copy
        effective_config = apply_style_choice(config, words, base_style, auto_mode)

        def on_progress(done: int, total: int) -> None:
            pct = int(done / total * 100) if total else 0
            _set_job(job_id, progress=pct)

        _set_job(job_id, status="rendering", progress=0)
        run_compositor(project["video_path"], str(output_path), words, effective_config, on_progress=on_progress)
        _set_job(job_id, status="done", progress=100)
    except Exception as e:  # noqa: BLE001
        _set_job(job_id, status="failed", error=f"Rendering failed: {e}")


@app.post("/api/projects/{project_id}/render")
async def render_project(project_id: str, base_style: str = Form("clean-white"), auto_mode: bool = Form(True)):
    project = project_store.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    if project["status"] != "ready":
        raise HTTPException(409, "Project is not ready yet.")

    config = _load_config()
    valid_base_styles = _valid_base_styles(config)
    if base_style not in valid_base_styles:
        raise HTTPException(400, f"base_style must be one of {sorted(valid_base_styles)}")

    job_id = uuid.uuid4().hex
    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "error": None}

    thread = threading.Thread(target=_run_project_render, args=(job_id, project, output_path, base_style, auto_mode), daemon=True)
    thread.start()

    return {"jobId": job_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
