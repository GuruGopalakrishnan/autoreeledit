"""In-memory store for the editor flow: upload -> transcribe once -> review/edit captions on a timeline -> render. A local single-user tool, so no database."""

import threading

_projects: dict[str, dict] = {}
_lock = threading.Lock()


def create_project(project_id: str, video_path: str) -> None:
    """Registers a project immediately (status "transcribing") so the frontend has something to poll while transcription/parsing runs in the background."""
    with _lock:
        _projects[project_id] = {
            "status": "transcribing",
            "error": None,
            "video_path": video_path,
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "words": [],
        }


def mark_ready(project_id: str, duration: float, width: int, height: int, words: list[dict]) -> None:
    with _lock:
        if project_id in _projects:
            _projects[project_id].update(status="ready", duration=duration, width=width, height=height, words=words)


def mark_failed(project_id: str, error: str) -> None:
    with _lock:
        if project_id in _projects:
            _projects[project_id].update(status="failed", error=error)


def get_project(project_id: str) -> dict | None:
    with _lock:
        return _projects.get(project_id)


def set_words(project_id: str, words: list[dict]) -> None:
    with _lock:
        if project_id in _projects:
            _projects[project_id]["words"] = words
