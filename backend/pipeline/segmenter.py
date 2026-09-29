"""
MediaPipe-based person segmentation plus face/body bounding-box detection.

Uses MediaPipe's Tasks API (ImageSegmenter / FaceDetector / PoseLandmarker)
rather than the older `mediapipe.solutions.*` convenience classes -- the
Windows PyPI wheels (checked on 0.10.35 and 1.0.1) no longer ship the
`solutions` subpackage at all, only `tasks`. Functionally equivalent, just a
different, slightly more verbose API that also needs its `.task`/`.tflite`
model files, which are downloaded once into `assets/models/` on first use
(same one-time-download pattern as the Whisper model).
"""

import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from mediapipe import Image as MPImage
from mediapipe import ImageFormat
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

_MODELS_DIR = Path(__file__).resolve().parent.parent / "assets" / "models"

_MODEL_URLS = {
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
}


def _ensure_model(filename: str) -> str:
    """Downloads a MediaPipe model asset into assets/models/ the first time it's needed, and reuses the cached copy after that."""
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = _MODELS_DIR / filename
    if not path.exists():
        print(f"Downloading MediaPipe model: {filename} ...")
        urllib.request.urlretrieve(_MODEL_URLS[filename], path)
    return str(path)


@dataclass
class FrameAnalysis:
    person_mask: np.ndarray  # float32 [0,1], same H,W as the frame
    face_bbox: tuple[int, int, int, int] | None  # x, y, w, h in pixels
    body_bbox: tuple[int, int, int, int] | None
    person_center_x_ratio: float  # 0..1, used by layout_engine to decide left/right placement


class PersonSegmenter:
    """
    Wraps MediaPipe's ImageSegmenter (selfie segmentation), FaceDetector, and
    PoseLandmarker so the heavy model graphs are initialized once and reused
    across every frame, not re-created per call. All three run in VIDEO mode
    with an explicit, monotonically increasing timestamp (required by the
    Tasks API for video/stream input). Call `close()` when done with a video.
    """

    def __init__(self) -> None:
        self._segmenter = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=_ensure_model("selfie_segmenter.tflite")),
                running_mode=vision.RunningMode.VIDEO,
                output_category_mask=False,
                output_confidence_masks=True,
            )
        )
        self._face = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=_ensure_model("blaze_face_short_range.tflite")),
                running_mode=vision.RunningMode.VIDEO,
                min_detection_confidence=0.5,
            )
        )
        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_ensure_model("pose_landmarker_lite.task")),
                running_mode=vision.RunningMode.VIDEO,
                min_pose_detection_confidence=0.5,
            )
        )

    def close(self) -> None:
        self._segmenter.close()
        self._face.close()
        self._pose.close()

    def analyze(self, frame_bgr: np.ndarray, timestamp_ms: int) -> FrameAnalysis:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = MPImage(image_format=ImageFormat.SRGB, data=rgb)

        seg_result = self._segmenter.segment_for_video(mp_image, timestamp_ms)
        # Confidence mask channel 1 is the foreground/person class for the
        # selfie_segmenter model (channel 0 is background).
        if seg_result.confidence_masks and len(seg_result.confidence_masks) > 1:
            mask = seg_result.confidence_masks[1].numpy_view()
        elif seg_result.confidence_masks:
            mask = seg_result.confidence_masks[0].numpy_view()
        else:
            mask = np.zeros((h, w), dtype=np.float32)
        mask = np.squeeze(mask).astype(np.float32)  # numpy_view() can come back as (H,W,1)

        face_bbox = None
        face_result = self._face.detect_for_video(mp_image, timestamp_ms)
        if face_result.detections:
            best = max(face_result.detections, key=lambda d: d.categories[0].score if d.categories else 0.0)
            bb = best.bounding_box
            face_bbox = (max(0, bb.origin_x), max(0, bb.origin_y), bb.width, bb.height)

        body_bbox = None
        pose_result = self._pose.detect_for_video(mp_image, timestamp_ms)
        if pose_result.pose_landmarks:
            landmarks = pose_result.pose_landmarks[0]
            xs = [lm.x for lm in landmarks if getattr(lm, "visibility", 1.0) > 0.3]
            ys = [lm.y for lm in landmarks if getattr(lm, "visibility", 1.0) > 0.3]
            if xs and ys:
                x0, x1 = max(0.0, min(xs)), min(1.0, max(xs))
                y0, y1 = max(0.0, min(ys)), min(1.0, max(ys))
                body_bbox = (int(x0 * w), int(y0 * h), int((x1 - x0) * w), int((y1 - y0) * h))

        # Fall back to the segmentation mask's own centroid when pose/face
        # detection miss a frame (motion blur, person partly out of frame).
        if body_bbox:
            center_x_ratio = (body_bbox[0] + body_bbox[2] / 2) / w
        else:
            ys_idx, xs_idx = np.where(mask > 0.5)
            center_x_ratio = float(np.mean(xs_idx) / w) if len(xs_idx) else 0.5

        return FrameAnalysis(person_mask=mask, face_bbox=face_bbox, body_bbox=body_bbox, person_center_x_ratio=center_x_ratio)
