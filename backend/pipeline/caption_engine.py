"""Caption style templates and per-frame text rendering (Pillow)."""

import math
import random
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .graphic_engine import draw_corporate_bar, draw_pill_badge, draw_ribbon_bar, draw_ribbon_tag

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
    # Corporate Lower Third (recreates the "Corporate Lower Thirds" MOGRT look natively).
    corporate_bar: bool = False  # sharp-cornered bar with a left accent stripe, instead of a rounded pill
    accent_color: str = "#00D4FF"
    # Name Tag (recreates the "Design Lower Thirds" name-plate + ribbon-flag look natively).
    ribbon_tag: bool = False  # small folded-flag accent shape attached under the bg_color bar
    # Decrypt Text (ported from the open-source OpenSub project's DecryptText
    # animation): each word scrambles through random characters before
    # locking in left-to-right, matrix/hacker-style. Selected via
    # animation="decrypt" rather than a separate flag, since it replaces the
    # entrance animation itself.
    # Karaoke word highlighting (ported from captions.js's getFillColor /
    # box-word / underline): the word currently being spoken switches color,
    # independent of whichever entrance animation is also running.
    karaoke_highlight: bool = False
    active_word_color: str = "#FFD400"
    active_word_box: bool = False  # colored pill behind just the active word
    active_word_box_color: str | None = None  # falls back to active_word_color
    active_word_underline: bool = False  # underline that grows across the word's own spoken duration
    # Speaker diarization colors (ported from beautiful-captions' speaker
    # coloring): words carrying a speaker_index (see srt_parser.py's
    # "Speaker A: " prefix detection) use a per-speaker color instead of the
    # style's base color. None (the default) leaves every word on style.color.
    speaker_colors: list[str] | None = None


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


def _animation_progress(t: float, word_start: float, word_end: float, animation: str) -> tuple[float, float, float]:
    """Returns (opacity, scale, blur_radius) for a word at time `t`, given
    its own [word_start, word_end] window and the style's animation type."""
    enter = 0.15
    if t < word_start:
        return 0.0, 1.0, 0.0

    if animation in ("word_fade_in", "typewriter"):
        return min(1.0, (t - word_start) / enter), 1.0, 0.0
    if animation == "scale_punch_in":
        progress = min(1.0, (t - word_start) / enter)
        return 1.0, 1.3 - 0.3 * progress, 0.0
    if animation == "slide_in":
        return min(1.0, (t - word_start) / enter), 1.0, 0.0
    if animation in ("decrypt", "wave", "glitch_text"):
        # Reveal is handled per-character/per-layer in the draw loop instead
        # of a uniform word-level opacity/scale.
        return 1.0, 1.0, 0.0
    if animation == "rise_up":
        return min(1.0, (t - word_start) / enter), 1.0, 0.0
    if animation == "blur_pop":
        # Ported from OpenSub's PopUp.svelte: blur+scale overshoot settling
        # to 1.0, opacity ramping in step with the first (overshoot) phase.
        blur_enter = 0.3
        p = min(1.0, (t - word_start) / blur_enter)
        opacity = min(1.0, p / 0.65)
        if p < 0.65:
            scale = 0.88 + 0.16 * (p / 0.65)
        else:
            scale = 1.04 - 0.04 * ((p - 0.65) / 0.35)
        blur = 2.0 * max(0.0, 1.0 - p / 0.65)
        return opacity, scale, blur
    return 1.0, 1.0, 0.0


_WAVE_STAGGER = 0.03
_WAVE_RISE_DURATION = 0.07
_WAVE_SETTLE_DURATION = 0.06
_RISE_UP_ENTER = 0.15
_GLITCH_DURATION = 0.28


def _rise_up_offset(t: float, word_start: float, font_size: int) -> int:
    """Ported from OpenSub's BottomToTop.svelte: the word rises from +20px
    (scaled to font size) up into place as it fades in."""
    progress = min(1.0, max(0.0, (t - word_start) / _RISE_UP_ENTER))
    return int(font_size * 0.4 * (1.0 - progress))


def _draw_wave_word(draw: "ImageDraw.ImageDraw", cursor_x: int, baseline_y: int, text: str, font: ImageFont.FreeTypeFont, style: "StyleConfig", elapsed: float, outline_fill: tuple | None) -> None:
    """Ported from OpenSub's Wave.svelte: each character bounces up
    (opacity + vertical offset) with a small stagger between characters."""
    x = float(cursor_x)
    for i, ch in enumerate(text):
        local_t = elapsed - i * _WAVE_STAGGER
        if local_t <= 0:
            opacity, y_off = 0.0, 12.0
        elif local_t < _WAVE_RISE_DURATION:
            p = local_t / _WAVE_RISE_DURATION
            opacity, y_off = p, 12.0 - 26.0 * p
        elif local_t < _WAVE_RISE_DURATION + _WAVE_SETTLE_DURATION:
            p = (local_t - _WAVE_RISE_DURATION) / _WAVE_SETTLE_DURATION
            opacity, y_off = 1.0, -14.0 + 14.0 * p
        else:
            opacity, y_off = 1.0, 0.0

        advance = font.getlength(ch)
        if opacity > 0 and ch != " ":
            fill = _hex_to_rgba(style.color, int(255 * opacity))
            draw.text((x, baseline_y + y_off), ch, font=font, fill=fill, stroke_width=style.outline_width, stroke_fill=outline_fill)
        x += advance


def _draw_glitch_word(word_img: Image.Image, cursor_x: int, baseline_y: int, text: str, font: ImageFont.FreeTypeFont, style: "StyleConfig", elapsed: float, outline_fill: tuple | None) -> None:
    """Ported from OpenSub's GlitchText.svelte: a quick chromatic-aberration
    jitter (cyan/magenta band ghosts either side of the true text) settling
    into place, instead of a plain fade."""
    draw = ImageDraw.Draw(word_img)
    if elapsed >= _GLITCH_DURATION:
        draw.text((cursor_x, baseline_y), text, font=font, fill=_hex_to_rgba(style.color), stroke_width=style.outline_width, stroke_fill=outline_fill)
        return

    frac = elapsed / _GLITCH_DURATION
    base_opacity = min(1.0, frac / 0.12)
    draw.text(
        (cursor_x, baseline_y), text, font=font,
        fill=_hex_to_rgba(style.color, int(255 * base_opacity)),
        stroke_width=style.outline_width, stroke_fill=outline_fill,
    )
    if frac < 0.12:
        return

    shake_frac = min(1.0, (frac - 0.12) / 0.42)
    jitter = int(4 * (1.0 - shake_frac) * math.sin(elapsed * 90))
    bbox = draw.textbbox((cursor_x, baseline_y), text, font=font, stroke_width=style.outline_width)
    band_h = max(1, (bbox[3] - bbox[1]) // 4)

    for color, dx, top in ((( 0, 229, 255, 190), -2 + jitter, bbox[1]), ((255, 43, 214, 190), 2 - jitter, bbox[3] - band_h)):
        ghost = Image.new("RGBA", word_img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ghost).text((cursor_x + dx, baseline_y), text, font=font, fill=color)
        top = max(0, min(word_img.height - 1, top))
        bottom = max(top + 1, min(word_img.height, top + band_h))
        strip = ghost.crop((0, top, word_img.width, bottom))
        word_img.alpha_composite(strip, (0, top))


_DECRYPT_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*"
_DECRYPT_DURATION = 0.35  # seconds for a word to fully "lock in", left to right


def _decrypt_display_text(text: str, elapsed: float) -> str:
    """Ported from OpenSub's DecryptText.svelte (sequential reveal mode):
    characters lock in left-to-right over `_DECRYPT_DURATION`; the rest
    show a random character each call. Seeded off (text, character index,
    a coarse time bucket) so repeated calls at the same instant agree, but
    the scramble still visibly flickers frame to frame."""
    if elapsed >= _DECRYPT_DURATION:
        return text
    if elapsed <= 0:
        revealed = 0
    else:
        revealed = int(len(text) * elapsed / _DECRYPT_DURATION)
    tick = int(elapsed * 20)  # ~20 scramble flickers/sec
    chars = []
    for i, ch in enumerate(text):
        if ch == " " or i < revealed:
            chars.append(ch)
        else:
            rng = random.Random(f"{text}|{i}|{tick}")
            chars.append(rng.choice(_DECRYPT_CHARS))
    return "".join(chars)


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

    if style.bg_color and style.corporate_bar:
        badge = draw_corporate_bar(tw, th, style.bg_color, style.accent_color)
        badge_x, badge_y = frame_w // 2 - badge.width // 2, frame_h // 2 - badge.height // 2
        canvas.alpha_composite(badge, (badge_x, badge_y))
    elif style.bg_color:
        badge = draw_pill_badge(tw, th, style.bg_color)
        badge_x, badge_y = frame_w // 2 - badge.width // 2, frame_h // 2 - badge.height // 2
        canvas.alpha_composite(badge, (badge_x, badge_y))

        if style.ribbon_tag:
            # The folded-flag accent hangs just under the bar, overlapping
            # its bottom-left corner, in the style's accent_color.
            tag = draw_ribbon_tag(badge.width, badge.height, style.accent_color)
            canvas.alpha_composite(tag, (badge_x + int(badge.width * 0.06), badge_y + badge.height - int(tag.height * 0.4)))

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
            opacity, scale, blur = _animation_progress(current_time, w["start"], w["end"], style.animation)
            elapsed = current_time - w["start"]

            if opacity <= 0:
                cursor_x += int(word_advance)
                continue

            is_active_word = style.karaoke_highlight and w["start"] <= current_time <= w["end"]
            speaker_index = w.get("speaker_index")
            base_color = style.speaker_colors[speaker_index % len(style.speaker_colors)] if style.speaker_colors and speaker_index is not None else style.color
            effective_color = style.active_word_color if is_active_word else base_color

            font = _font_for_text(w["text"], style.font, effective_size)
            word_img = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
            word_draw = ImageDraw.Draw(word_img)
            color = _hex_to_rgba(effective_color, int(255 * opacity))
            word_outline = _hex_to_rgba(style.outline_color, int(255 * opacity)) if style.outline_color else None

            word_y = baseline_y
            if style.animation == "rise_up":
                word_y += _rise_up_offset(current_time, w["start"], effective_size)

            if is_active_word and (style.active_word_box or style.active_word_underline):
                word_bbox = word_draw.textbbox((cursor_x, word_y), w["text"], font=font, stroke_width=style.outline_width)

            if is_active_word and style.active_word_box:
                box_color = style.active_word_box_color or style.active_word_color
                pad_x, pad_y = int(effective_size * 0.18), int(effective_size * 0.08)
                word_draw.rounded_rectangle(
                    [(word_bbox[0] - pad_x, word_bbox[1] - pad_y), (word_bbox[2] + pad_x, word_bbox[3] + pad_y)],
                    radius=max(2, int(effective_size * 0.12)),
                    fill=_hex_to_rgba(box_color, int(255 * opacity)),
                )

            if style.animation == "wave":
                _draw_wave_word(word_draw, cursor_x, word_y, w["text"], font, style, elapsed, word_outline)
            elif style.animation == "glitch_text":
                _draw_glitch_word(word_img, cursor_x, word_y, w["text"], font, style, elapsed, word_outline)
            else:
                # word_advance stays keyed off the true word text (below) even
                # in decrypt mode, so scrambled substitute glyphs of
                # different widths never shift layout/line-wrapping frame to frame.
                text_to_draw = _decrypt_display_text(w["text"], elapsed) if style.animation == "decrypt" else w["text"]
                word_draw.text(
                    (cursor_x, word_y),
                    text_to_draw,
                    font=font,
                    fill=color,
                    stroke_width=style.outline_width,
                    stroke_fill=word_outline,
                )

            if is_active_word and style.active_word_underline:
                # Grows across the word's own spoken duration -- an
                # improvement on captions.js's source, which always passes a
                # constant (ease(1) == 1) and so never actually animates the
                # underline's width despite computing a per-word progress.
                word_duration = max(0.05, w["end"] - w["start"])
                underline_progress = min(1.0, (current_time - w["start"]) / word_duration)
                underline_y = word_bbox[3] + max(2, int(effective_size * 0.08))
                underline_w = max(2, int(effective_size * 0.07))
                word_draw.line(
                    [(word_bbox[0], underline_y), (word_bbox[0] + int((word_bbox[2] - word_bbox[0]) * underline_progress), underline_y)],
                    fill=_hex_to_rgba(style.active_word_color, int(255 * opacity)),
                    width=underline_w,
                )

            if blur > 0:
                word_img = word_img.filter(ImageFilter.GaussianBlur(radius=blur))

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
