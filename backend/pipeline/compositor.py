"""Frame-by-frame compositor: layers background, person, graphics, and
captions into the final output video, then muxes the original audio back in
with ffmpeg (the frame-writing pass itself is silent)."""

import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from tqdm import tqdm

from .caption_engine import StyleConfig, render_caption_frame
from .graphic_engine import draw_confetti, draw_dotted_line, draw_starburst
from .layout_engine import decide_layout, text_box_for_anchor
from .segmenter import PersonSegmenter


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _pick_style(t: float, words: list[dict], config: dict) -> str:
    """Style trigger, highest priority first: an explicit per-caption Title
    Moment (set by hand in the editor) always wins; then the rule-based
    triggers -- dramatic for `dramatic_hold_seconds` after a keyword,
    energetic for a fast run of recent words; else the chosen base style --
    see config.json's `keyword_list` / `energetic_word_count`."""
    for w in words:
        if w.get("title_moment") and w["start"] <= t <= w["end"]:
            return w["title_moment"]

    hold = config.get("dramatic_hold_seconds", 2.0)
    for w in words:
        if w["is_keyword"] and w["start"] <= t <= w["end"] + hold:
            return "dramatic"

    recent = [w for w in words if t - 2.5 <= w["start"] <= t]
    if len(recent) > config.get("energetic_word_count", 5):
        return "energetic"

    return config.get("default_style", "casual")


def _active_words_for_style(t: float, words: list[dict], style: str, config: dict) -> list[dict]:
    """The word window a given style should currently show: dramatic shows
    just its triggering keyword. For the others, words carrying a `cue_id`
    (from a user-supplied SRT transcript) show exactly their own cue's
    words -- the cue boundaries are already human-chosen phrase breaks, so
    that reads far better than an arbitrary sliding time window that can
    straddle two unrelated cues and overflow the frame. Whisper-sourced
    words have no cue_id, so they fall back to a trailing ~4s window."""
    if style == "dramatic":
        hold = config.get("dramatic_hold_seconds", 2.0)
        return [w for w in words if w["is_keyword"] and w["start"] <= t <= w["end"] + hold]

    spoken = [w for w in words if w["start"] <= t]
    if spoken and "cue_id" in spoken[-1]:
        current_cue = spoken[-1]["cue_id"]
        return [w for w in words if w.get("cue_id") == current_cue]

    window = 4.0
    return [w for w in words if t - window <= w["start"] <= t and w["end"] >= t - window]


def _build_layers(frame_bgr: np.ndarray, mask: np.ndarray, config: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Splits the frame into a background layer and a person layer (RGBA, alpha
    = the segmentation mask) instead of pre-flattening them together --
    keeping them separate is what lets the caller put captions in between
    the two (Subject Mask & Track's "text behind subject").
    """
    bg_mode = config.get("bg_mode", "solid")
    if bg_mode == "blur":
        background = cv2.GaussianBlur(frame_bgr, (55, 55), 0)
    elif bg_mode == "darken":
        background = (frame_bgr.astype(np.float32) * 0.35).astype(np.uint8)
    else:  # solid
        color = _hex_to_bgr(config.get("background_color", "#F0F0F0"))
        background = np.full_like(frame_bgr, color)

    person_bgr = frame_bgr
    if config.get("person_mode") == "bw":
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        person_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    alpha = np.clip(mask * 255, 0, 255).astype(np.uint8)
    person_rgba = cv2.cvtColor(person_bgr, cv2.COLOR_BGR2RGBA)
    person_rgba[:, :, 3] = alpha
    return background, person_rgba


_VIGNETTE_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _vignette_mask(w: int, h: int) -> np.ndarray:
    """Radial darkening mask, cached per (w, h) since it's identical every frame of a render."""
    key = (w, h)
    if key not in _VIGNETTE_CACHE:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2, h / 2
        max_d = math.hypot(cx, cy)
        d = np.hypot(xx - cx, yy - cy) / max_d
        _VIGNETTE_CACHE[key] = np.clip(1.0 - (d**2) * 0.85, 0.18, 1.0)
    return _VIGNETTE_CACHE[key]


def _apply_vignette(frame_bgr: np.ndarray) -> np.ndarray:
    mask = _vignette_mask(frame_bgr.shape[1], frame_bgr.shape[0])
    return (frame_bgr.astype(np.float32) * mask[:, :, None]).astype(np.uint8)


def _apply_spotlight(background: np.ndarray, center: tuple[int, int], radius: float) -> np.ndarray:
    """Darkens `background` outside a soft circle at `center`, for the Spotlight Reveal title moment."""
    h, w = background.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - center[0], yy - center[1])
    t = np.clip((d - radius) / max(1.0, radius), 0.0, 1.0)
    mask = np.clip(1.0 - t * 0.92, 0.08, 1.0)
    return (background.astype(np.float32) * mask[:, :, None]).astype(np.uint8)


def _apply_zoom_punch(frame_bgr: np.ndarray, elapsed: float, duration: float = 0.25, max_scale: float = 1.07) -> np.ndarray:
    """Whole-frame punch-in that decays to 1.0x over `duration` seconds from the moment's start."""
    if elapsed >= duration:
        return frame_bgr
    scale = 1.0 + (max_scale - 1.0) * (1.0 - elapsed / duration)
    h, w = frame_bgr.shape[:2]
    nh, nw = max(h, int(h * scale)), max(w, int(w * scale))
    resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    y0, x0 = (nh - h) // 2, (nw - w) // 2
    return resized[y0 : y0 + h, x0 : x0 + w]


def _apply_shake(frame_bgr: np.ndarray, elapsed: float, duration: float = 0.35) -> np.ndarray:
    """Decaying frame jitter for the first `duration` seconds of the moment, edge-replicated so no black border shows."""
    if elapsed >= duration:
        return frame_bgr
    amplitude = 14.0 * (1.0 - elapsed / duration)
    dx = amplitude * math.sin(elapsed * 60)
    dy = amplitude * math.cos(elapsed * 47)
    h, w = frame_bgr.shape[:2]
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(frame_bgr, m, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _apply_glitch(frame_bgr: np.ndarray, elapsed: float) -> np.ndarray:
    """RGB channel-split glitch, pulsed in short bursts (every ~0.5s) rather than held continuously."""
    if (elapsed % 0.5) > 0.09:
        return frame_bgr
    shift = 6
    out = frame_bgr.copy()
    out[:, :, 2] = np.roll(frame_bgr[:, :, 2], shift, axis=1)
    out[:, :, 0] = np.roll(frame_bgr[:, :, 0], -shift, axis=1)
    return out


def _draw_neon_frame_overlay(w: int, h: int, color_hex: str, pulse: float) -> Image.Image:
    """Pulsing colored border glow (nested semi-transparent rectangles) for the Neon Frame title moment."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = _hex_to_rgb(color_hex)
    thickness = 6 + int(6 * pulse)
    for i in range(thickness):
        alpha = int(130 * (1 - i / thickness))
        draw.rectangle([(i, i), (w - 1 - i, h - 1 - i)], outline=(r, g, b, alpha))
    return img


def _draw_mask_edge(alpha: np.ndarray, color_hex: str, width: int) -> Image.Image:
    """Traces the person cutout's silhouette (from its alpha channel) and returns a transparent RGBA image with just that outline drawn -- the colored edge overlay seen in the Subject Mask panel."""
    h, w = alpha.shape[:2]
    _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    if contours:
        r, g, b = _hex_to_rgb(color_hex)
        cv2.drawContours(canvas, contours, -1, (r, g, b, 255), thickness=max(1, width))
    return Image.fromarray(canvas, mode="RGBA")


def run_compositor(
    input_video: str,
    output_video: str,
    words: list[dict],
    config: dict,
    process_size: tuple[int, int] | None = None,
    on_progress=None,
) -> None:
    """
    Reads `input_video` frame by frame, applies background replacement,
    graphic overlays, and style-driven animated captions, writes a silent
    video to a temp file, then muxes the original audio back in via ffmpeg
    to produce `output_video`. `on_progress(frames_done, frames_total)` is
    an optional hook called periodically during the render (a web front end
    polls this to show a progress bar; the CLI just uses the tqdm bar).
    """
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open input video: {input_video}")

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or config.get("fps", 30)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    proc_w, proc_h = process_size or (config.get("process_width", 1280), config.get("process_height", 720))
    # Preserve the source aspect ratio inside the process resolution rather
    # than stretching -- letterboxing math is simpler to reason about
    # downstream than a distorted person/face.
    scale = min(proc_w / src_w, proc_h / src_h)
    proc_w, proc_h = max(2, int(src_w * scale)), max(2, int(src_h * scale))

    silent_path = str(Path(output_video).with_suffix("")) + "_silent.mp4"
    writer = cv2.VideoWriter(silent_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (proc_w, proc_h))

    segmenter = PersonSegmenter(track_hands=config.get("track_hands", True))
    styles = {name: StyleConfig(**cfg) for name, cfg in config["styles"].items()}

    try:
        for frame_idx in tqdm(range(frame_count), desc="Rendering frames"):
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
            t = frame_idx / fps

            if on_progress and frame_idx % 5 == 0:
                on_progress(frame_idx, frame_count)

            analysis = segmenter.analyze(frame, timestamp_ms=int(t * 1000))
            style_name = _pick_style(t, words, config)
            style = styles[style_name]
            layout = decide_layout(analysis, style.position, proc_w, proc_h)
            active_words = _active_words_for_style(t, words, style_name, config)
            moment_elapsed = (t - active_words[0]["start"]) if active_words else 0.0

            person_rgba = None
            if layout.full_frame:
                fill = style.full_frame_bg_color or config.get("background_color", "#F0F0F0")
                background = np.full_like(frame, _hex_to_bgr(fill))
            else:
                background, person_rgba = _build_layers(frame, analysis.person_mask, config)
                if style.color_pop:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    background = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                if style.spotlight_moment:
                    center, radius = None, None
                    if analysis.face_bbox:
                        fx, fy, fw, fh = analysis.face_bbox
                        center, radius = (fx + fw // 2, fy + fh // 2), max(fw, fh) * 2.4
                    elif analysis.body_bbox:
                        bx, by, bw, bh = analysis.body_bbox
                        center, radius = (bx + bw // 2, by + bh // 3), bh * 0.85
                    if center:
                        background = _apply_spotlight(background, center, radius)

            base_pil = Image.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB)).convert("RGBA")
            person_pil = Image.fromarray(person_rgba, mode="RGBA") if person_rgba is not None else None

            # Starburst emphasis graphic behind the person during a dramatic moment.
            if style.show_starburst and not layout.full_frame and analysis.body_bbox:
                bx, by, bw, bh = analysis.body_bbox
                burst = draw_starburst(max(2, int(bh * 0.9)), "#FFD400", alpha=200)
                base_pil.alpha_composite(burst, (bx + bw // 2 - burst.width // 2, max(0, by - burst.height // 3)))

            caption_img, tw, th = render_caption_frame(active_words, t, style, proc_w, proc_h)

            if tw and th and layout.text_anchor != "center":
                x, y = text_box_for_anchor(layout.text_anchor, proc_w, proc_h, tw, th, analysis.face_bbox, analysis.hand_bboxes)
                # render_caption_frame already centers text on the full canvas;
                # shift the whole canvas so that centered text lands at (x, y).
                dx = x - (proc_w // 2 - tw // 2)
                dy = y - (proc_h // 2 - th // 2)
                shifted = Image.new("RGBA", (proc_w, proc_h), (0, 0, 0, 0))
                shifted.alpha_composite(caption_img, (dx, dy))
                caption_img = shifted

            if style_name == "energetic" and analysis.body_bbox:
                bx, by, bw, bh = analysis.body_bbox
                divider = draw_dotted_line(bh, "#FFFFFF")
                side_x = bx - divider.width - 10 if layout.text_anchor == "right" else bx + bw + 10
                base_pil.alpha_composite(divider, (max(0, min(proc_w - divider.width, side_x)), by))

            # Subject Mask & Track: "text behind subject" draws the caption
            # before the person layer instead of after, so the person's
            # silhouette occludes any part of the text it overlaps.
            if style.text_behind_subject and person_pil is not None:
                base_pil.alpha_composite(caption_img)
                base_pil.alpha_composite(person_pil)
            else:
                if person_pil is not None:
                    base_pil.alpha_composite(person_pil)
                base_pil.alpha_composite(caption_img)

            if style.show_mask_edge and person_rgba is not None:
                edge = _draw_mask_edge(person_rgba[:, :, 3], style.mask_edge_color, style.mask_edge_width)
                base_pil.alpha_composite(edge)

            if style.neon_frame:
                pulse = 0.5 + 0.5 * math.sin(t * 6)
                base_pil.alpha_composite(_draw_neon_frame_overlay(proc_w, proc_h, style.color, pulse))

            if style.confetti_moment:
                base_pil.alpha_composite(draw_confetti(proc_w, proc_h, moment_elapsed))

            if style.flash_moment:
                flash_duration = 0.15
                if moment_elapsed < flash_duration:
                    alpha = int(255 * (1 - moment_elapsed / flash_duration))
                    base_pil.alpha_composite(Image.new("RGBA", (proc_w, proc_h), (255, 255, 255, alpha)))

            out_bgr = cv2.cvtColor(np.array(base_pil.convert("RGB")), cv2.COLOR_RGB2BGR)

            if style.vignette_moment:
                out_bgr = _apply_vignette(out_bgr)
            if style.zoom_punch:
                out_bgr = _apply_zoom_punch(out_bgr, moment_elapsed)
            if style.shake_moment:
                out_bgr = _apply_shake(out_bgr, moment_elapsed)
            if style.glitch_moment:
                out_bgr = _apply_glitch(out_bgr, moment_elapsed)

            writer.write(out_bgr)
        if on_progress:
            on_progress(frame_count, frame_count)
    finally:
        cap.release()
        writer.release()
        segmenter.close()

    _mux_audio(input_video, silent_path, output_video, config.get("ffmpeg_path", "ffmpeg"))
    Path(silent_path).unlink(missing_ok=True)


def _mux_audio(source_with_audio: str, silent_video: str, output_video: str, ffmpeg_path: str = "ffmpeg") -> None:
    """Copies the original audio track onto the newly-rendered silent video with ffmpeg, re-encoding only the audio."""
    Path(output_video).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path, "-y",
        "-i", silent_video,
        "-i", source_with_audio,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        output_video,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio mux failed:\n{result.stderr}")
