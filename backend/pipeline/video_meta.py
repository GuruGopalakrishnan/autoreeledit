"""Lightweight video metadata probe -- just what the editor needs (duration/width/height) without pulling in the full compositor."""

import cv2


def probe_video(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()
    duration = frame_count / fps if fps else 0.0
    return {"width": width, "height": height, "duration": duration}
