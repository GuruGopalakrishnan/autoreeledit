"""Caption style templates and per-frame text rendering (Pillow)."""

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .graphic_engine import draw_pill_badge, draw_ribbon_bar

# Bundled multi-script fallback: whichever style font is active, a Tamil
# word still needs an actual Tamil-capable font or it renders as tofu boxes
# (Montserrat/Anton/etc. only cover Latin). Checked per word, not per line,
# so Tanglish (mixed Tamil+English) captions render correctly either way.
_TAMIL_RANGE = re.compile(r"[஀-௿]")
_TAMIL_FONT_PATH = str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansTamil-Variable.ttf")

# A caption line wider than this fraction of the frame wraps onto a new line
# instead of running off the edge.
_MAX_LINE_WIDTH_RATIO = 0.88


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
    # Subject Mask & Track (Phase 4). Defaulted so existing config.json
    # presets keep working unchanged -- only presets that opt in set these.
    text_behind_subject: bool = False
    show_mask_edge: bool = False
    mask_edge_color: str = "#FF0000"
    mask_edge_width: int = 4
    # Title Moments (Phase 5).
    show_starburst: bool = False
    full_frame_bg_color: str | None = None  # overrides config.background_color for a full-frame (position="beside_person") style
    # Premium Title Moments -- each is a real per-frame effect applied in
    # compositor.py, not just a caption color/font change. Defaulted off so
    # every existing preset is unaffected.
    spotlight_moment: bool = False  # darkens the background outside a circle centered on the person
    flash_moment: bool = False  # white camera-flash pop for the first ~0.15s the moment is visible
    confetti_moment: bool = False  # falling colored confetti for the whole moment
    glitch_moment: bool = False  # pulsing RGB channel-split distortion
    neon_frame: bool = False  # pulsing colored border around the whole frame
    zoom_punch: bool = False  # whole-frame punch-in that decays over the first ~0.25s
    color_pop: bool = False  # background shown desaturated (from the real video) while the person stays in color
    ribbon_bar: bool = False  # full-width color bar that wipes in behind the text, like a news chyron
    shake_moment: bool = False  # frame jitter that decays over the first ~0.35s
    vignette_moment: bool = False  # strong dark vignette at the frame edges
    # Typewriter + Glow (recreates the "Simple Typewriter Animation" MOGRT look natively).
    text_glow: bool = False  # soft blurred halo behind the typewriter text
    blink_cursor: bool = False  # blinking "|" cursor after the currently-typed text


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


def _font_for_text(text: str, style_font_path: str, size: int) -> ImageFont.FreeTypeFont:
    path = _TAMIL_FONT_PATH if _TAMIL_RANGE.search(text) else style_font_path
    return _load_font(path, size)


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


def _wrap_into_lines(visible: list[dict], advances: list[float], max_width: float) -> list[list[int]]:
    """Greedily groups word indices into lines so no line's total advance exceeds `max_width`."""
    lines: list[list[int]] = []
    current: list[int] = []
    current_width = 0.0
    for i in range(len(visible)):
        w = advances[i]
        if current and current_width + w > max_width:
            lines.append(current)
            current = []
            current_width = 0.0
        current.append(i)
        current_width += w
    if current:
        lines.append(current)
    return lines


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
    window (already filtered by the caller). Each word picks its own font
    (see `_font_for_text`) so Tamil words render correctly even inside an
    English-styled theme. Lines that would run wider than the frame wrap
    automatically (see `_wrap_into_lines`).
    """
    canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    visible = [w for w in words if current_time >= w["start"]]
    if not visible:
        return canvas, 0, 0

    outline_fill = _hex_to_rgba(style.outline_color) if style.outline_color else None

    if style.animation == "typewriter":
        text = " ".join(w["text"] for w in visible)
        font = _font_for_text(text, style.font, style.font_size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=style.outline_width)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # Drawn vertically centered on this canvas -- not at its final
        # on-screen position -- so the compositor's anchor-shift math (which
        # assumes every branch centers its output the same way the
        # word-by-word branch below does) repositions it correctly instead
        # of shifting it off-frame.
        x0, y0 = frame_w // 2 - tw // 2, frame_h // 2 - th // 2

        if style.text_glow:
            # Soft blurred halo behind the sharp text -- draw the same text
            # on its own layer, blur it, then composite it underneath.
            glow_layer = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
            ImageDraw.Draw(glow_layer).text((x0, y0), text, font=font, fill=_hex_to_rgba(style.color, 210))
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=max(4, style.font_size // 9)))
            canvas.alpha_composite(glow_layer)

        draw.text(
            (x0, y0),
            text,
            font=font,
            fill=_hex_to_rgba(style.color),
            stroke_width=style.outline_width,
            stroke_fill=outline_fill,
        )

        if style.blink_cursor and int(current_time * 2) % 2 == 0:
            cursor_w = max(2, style.font_size // 18)
            cursor_gap = int(style.font_size * 0.12)
            cx = x0 + tw + cursor_gap
            draw.rectangle([(cx, y0), (cx + cursor_w, y0 + th)], fill=_hex_to_rgba(style.color))
            tw += cursor_gap + cursor_w

        return canvas, tw, th

    # Word-by-word layout: each word gets its own font (Tamil words fall
    # back automatically), so line width is the sum of individual word
    # advances rather than one textbbox call over the whole string.
    #
    # A style's configured font_size (e.g. Dramatic's 120px) can still be
    # wider than the frame for a single long word, which wrapping alone
    # can't fix (it only breaks *between* words) -- so shrink the font size
    # to fit when even one line is too wide, rather than letting it run off
    # both edges.
    spacer = " "
    max_line_width = frame_w * _MAX_LINE_WIDTH_RATIO
    effective_size = style.font_size

    for _ in range(4):
        word_advances = []
        for w in visible:
            f = _font_for_text(w["text"], style.font, effective_size)
            wb = draw.textbbox((0, 0), w["text"] + spacer, font=f, stroke_width=style.outline_width)
            word_advances.append(wb[2] - wb[0])
        lines = _wrap_into_lines(visible, word_advances, max_line_width)
        widest = max(sum(word_advances[i] for i in line) for line in lines)
        if widest <= max_line_width or effective_size <= 14:
            break
        effective_size = max(14, int(effective_size * max_line_width / widest * 0.97))

    line_height = effective_size * 1.25 + style.outline_width * 2
    line_widths = [sum(word_advances[i] for i in line) for line in lines]
    tw = int(max(line_widths))
    th = int(len(lines) * line_height)

    if style.bg_color:
        badge = draw_pill_badge(tw, th, style.bg_color)
        canvas.alpha_composite(badge, (frame_w // 2 - badge.width // 2, frame_h // 2 - badge.height // 2))

    if style.ribbon_bar:
        # Wipes in from the center over the moment's first 0.25s. Drawn on
        # this pre-shift canvas at frame_h * 0.5 (its own vertical center) so
        # it tracks the text when the compositor repositions the whole
        # canvas to its final anchor, same as the bg_color badge above.
        progress = min(1.0, (current_time - visible[0]["start"]) / 0.25)
        bar_height = int(th * 1.5) + style.outline_width * 2
        ribbon = draw_ribbon_bar(frame_w, frame_h, bar_height, style.bg_color or "#E63946", progress, center_y_ratio=0.5)
        canvas.alpha_composite(ribbon)

    block_top = frame_h // 2 - th // 2

    for line_index, (line, line_width) in enumerate(zip(lines, line_widths)):
        cursor_x = frame_w // 2 - int(line_width) // 2
        baseline_y = int(block_top + line_index * line_height)

        for i in line:
            w = visible[i]
            word_advance = word_advances[i]
            opacity, scale = _animation_progress(current_time, w["start"], w["end"], style.animation)

            if opacity <= 0:
                cursor_x += int(word_advance)
                continue

            font = _font_for_text(w["text"], style.font, effective_size)
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
            cursor_x += int(word_advance)

    return canvas, tw, th
