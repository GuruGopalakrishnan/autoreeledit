"""Decides where captions/graphics go each frame based on the person's
detected position, so text lands on the side opposite the person and never
overlaps the face."""

from dataclasses import dataclass

from .segmenter import FrameAnalysis


@dataclass
class LayoutDecision:
    text_anchor: str  # "left", "right", "center", "top", "lower_third"
    full_frame: bool  # True for a dramatic keyword moment: text takes over the whole frame


def decide_layout(analysis: FrameAnalysis, style: str, frame_w: int, frame_h: int) -> LayoutDecision:
    if style == "dramatic":
        return LayoutDecision(text_anchor="center", full_frame=True)

    if style == "minimal":
        return LayoutDecision(text_anchor="top", full_frame=False)

    if style == "casual":
        return LayoutDecision(text_anchor="lower_third", full_frame=False)

    # energetic: dynamic -- opposite side from the person so it never sits on the face
    if analysis.person_center_x_ratio > 0.55:
        anchor = "left"
    elif analysis.person_center_x_ratio < 0.45:
        anchor = "right"
    else:
        anchor = "center"
    return LayoutDecision(text_anchor=anchor, full_frame=False)


def text_box_for_anchor(
    anchor: str,
    frame_w: int,
    frame_h: int,
    text_w: int,
    text_h: int,
    face_bbox: tuple[int, int, int, int] | None,
) -> tuple[int, int]:
    """Returns a top-left (x, y) for the text box that keeps it clear of the face bbox where possible."""
    margin = int(frame_w * 0.06)

    if anchor == "left":
        x, y = margin, frame_h // 2 - text_h // 2
    elif anchor == "right":
        x, y = frame_w - text_w - margin, frame_h // 2 - text_h // 2
    elif anchor == "top":
        x, y = frame_w // 2 - text_w // 2, int(frame_h * 0.08)
    elif anchor == "lower_third":
        x, y = frame_w // 2 - text_w // 2, int(frame_h * 0.78)
    else:  # center
        x, y = frame_w // 2 - text_w // 2, frame_h // 2 - text_h // 2

    if face_bbox:
        fx, fy, fw, fh = face_bbox
        overlaps = not (x + text_w < fx or x > fx + fw or y + text_h < fy or y > fy + fh)
        if overlaps and anchor in ("left", "right"):
            # Push the box above or below the face instead of sideways past it.
            y = max(margin, fy - text_h - margin) if fy > frame_h / 2 else min(frame_h - text_h - margin, fy + fh + margin)

    return max(0, x), max(0, y)
