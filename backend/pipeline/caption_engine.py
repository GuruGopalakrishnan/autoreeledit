"""Caption style templates and per-frame text rendering (Pillow)."""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .graphic_engine import draw_pill_badge


@dataclass
class StyleConfig:
    font: str
    font_size: int
    color: str
    outline_color: str | None
    outline_width: int
    bg_color: str | None
    position: str
    animation: str


_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(path, size)
        except OSError:
            # Missing font file (see assets/fonts/README.md) -- fall back to a
            # built-in bitmap font so the pipeline still runs, just less pretty.
            _FONT_CACHE[key] = ImageFont.load_default(size=size)
    return _FONT_CACHE[key]


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def _animation_progress(t: float, word_start: float, word_end: float, animation: str) -> tuple[float, float]:
    """Returns (opacity, scale) for a word at time `t`, given its own
    [word_start, word_end] window and the style's animation type."""
    enter = 0.15
    if t < word_start:
        return 0.0, 1.0

    if animation in ("word_fade_in", "typewriter"):
        return min(1.0, (t - word_start) / enter), 1.0
    if animation == "scale_punch_in":
        progress = min(1.0, (t - word_start) / enter)
        return 1.0, 1.3 - 0.3 * progress
    if animation == "slide_in":
        return min(1.0, (t - word_start) / enter), 1.0
    return 1.0, 1.0


def render_caption_frame(
    words: list[dict],
    current_time: float,
    style: StyleConfig,
    frame_w: int,
    frame_h: int,
) -> tuple[Image.Image, int, int]:
    """
    Renders the currently-visible words for this style at `current_time`
    onto a transparent RGBA canvas the size of the frame, centered, and
    returns (canvas, text_width, text_height) of the tight text bounding
    box -- the layout engine repositions the whole canvas using those real
    dimensions rather than this function knowing about anchors itself.

    `words` is the slice of the transcript relevant to this style's active
    window (already filtered by the caller).
    """
    font = _load_font(style.font, style.font_size)
    canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    visible = [w for w in words if current_time >= w["start"]]
    if not visible:
        return canvas, 0, 0

    outline_fill = _hex_to_rgba(style.outline_color) if style.outline_color else None

    if style.animation == "typewriter":
        text = " ".join(w["text"] for w in visible)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=style.outline_width)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (frame_w // 2 - tw // 2, int(frame_h * 0.08)),
            text,
            font=font,
            fill=_hex_to_rgba(style.color),
            stroke_width=style.outline_width,
            stroke_fill=outline_fill,
        )
        return canvas, tw, th

    # Word-by-word layout: measure the full line first so we can center it,
    # then draw each word with its own animation progress.
    spacer = " "
    full_text = spacer.join(w["text"] for w in visible)
    bbox = draw.textbbox((0, 0), full_text, font=font, stroke_width=style.outline_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    if style.bg_color:
        badge = draw_pill_badge(tw, th, style.bg_color)
        canvas.alpha_composite(badge, (frame_w // 2 - badge.width // 2, frame_h // 2 - badge.height // 2))

    cursor_x = frame_w // 2 - tw // 2
    baseline_y = frame_h // 2 - th // 2

    for w in visible:
        opacity, scale = _animation_progress(current_time, w["start"], w["end"], style.animation)
        word_bbox = draw.textbbox((0, 0), w["text"] + spacer, font=font, stroke_width=style.outline_width)
        word_advance = word_bbox[2] - word_bbox[0]

        if opacity <= 0:
            cursor_x += word_advance
            continue

        word_img = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        word_draw = ImageDraw.Draw(word_img)
        color = _hex_to_rgba(style.color, int(255 * opacity))
        word_outline = _hex_to_rgba(style.outline_color, int(255 * opacity)) if style.outline_color else None
        word_draw.text(
            (cursor_x, baseline_y),
            w["text"],
            font=font,
            fill=color,
            stroke_width=style.outline_width,
            stroke_fill=word_outline,
        )

        if scale != 1.0:
            scaled_w, scaled_h = max(1, int(frame_w * scale)), max(1, int(frame_h * scale))
            word_img = word_img.resize((scaled_w, scaled_h), Image.LANCZOS)
            # Recenter after scaling so a punch-in shrinks toward its own
            # center rather than the canvas corner, then crop back to frame size.
            offset_x, offset_y = (scaled_w - frame_w) // 2, (scaled_h - frame_h) // 2
            word_img = word_img.crop((offset_x, offset_y, offset_x + frame_w, offset_y + frame_h))

        canvas.alpha_composite(word_img)
        cursor_x += word_advance

    return canvas, tw, th
