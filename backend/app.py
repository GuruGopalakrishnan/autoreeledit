"""
FastAPI backend: wraps the Whisper + MediaPipe auto-editor pipeline behind
an HTTP API so the Next.js frontend can upload a video, watch progress, and
download the result. Jobs run in a background thread and their state lives
in an in-memory dict -- this is a local, single-user tool, so a database is
more machinery than the problem needs.
"""

import json
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline.runner import PipelineError, run_pipeline

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = BASE_DIR / "config.json"

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


def _run_job(job_id: str, input_path: Path, output_path: Path, style: str) -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    try:

        def on_stage(stage: str) -> None:
            _set_job(job_id, status=stage, progress=0)

        def on_progress(done: int, total: int) -> None:
            pct = int(done / total * 100) if total else 0
            _set_job(job_id, progress=pct)

        run_pipeline(str(input_path), str(output_path), config, style=style, on_stage=on_stage, on_progress=on_progress)
        _set_job(job_id, status="done", progress=100)
    except PipelineError as e:
        _set_job(job_id, status="failed", error=str(e))
    except Exception as e:  # noqa: BLE001 -- last-resort catch so a job always resolves to failed, never hangs "processing" forever
        _set_job(job_id, status="failed", error=f"Unexpected error: {e}")


@app.post("/api/jobs")
async def create_job(video: UploadFile = File(...), style: str = Form("auto")):
    valid_styles = {"auto", "casual", "dramatic", "energetic", "minimal"}
    if style not in valid_styles:
        raise HTTPException(400, f"style must be one of {sorted(valid_styles)}")

    job_id = uuid.uuid4().hex
    ext = Path(video.filename or "input.mp4").suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{job_id}{ext}"
    output_path = OUTPUT_DIR / f"{job_id}.mp4"

    with input_path.open("wb") as f:
        shutil.copyfileobj(video.file, f)

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "progress": 0, "error": None}

    thread = threading.Thread(target=_run_job, args=(job_id, input_path, output_path, style), daemon=True)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
