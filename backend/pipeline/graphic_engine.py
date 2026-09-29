"""
Reusable graphic overlay elements: starburst, pill badge, dotted divider,
small decorative star.

Drawn directly with Pillow rather than round-tripped through SVG -- avoids
an extra native-library dependency (cairosvg and its system cairo build,
which is painful to install on Windows) with no visual difference for
shapes this simple.
"""

import math
import random

from PIL import Image, ImageDraw


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def draw_starburst(size: int, color: str, points: int = 8, alpha: int = 255) -> Image.Image:
    """An N-point star on a transparent square, for emphasis behind a person's head."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    outer_r, inner_r = size / 2 * 0.95, size / 2 * 0.45
    vertices = []
    for i in range(points * 2):
        r = outer_r if i % 2 == 0 else inner_r
        angle = math.pi * i / points - math.pi / 2
        vertices.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(vertices, fill=_hex_to_rgba(color, alpha))
    return img


def draw_pill_badge(text_width: int, text_height: int, color: str, padding: int = 20) -> Image.Image:
    """A rounded-rectangle badge sized to fit `text_width` x `text_height` of text behind it."""
    w, h = max(1, text_width + padding * 2), max(1, text_height + padding)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=h // 2, fill=_hex_to_rgba(color, 255))
    return img


def draw_corporate_bar(text_width: int, text_height: int, color: str, accent_color: str, padding: int = 24, accent_width: int = 10) -> Image.Image:
    """A sharp-cornered lower-third bar with a bright accent stripe down the
    left edge -- the classic 'corporate lower third' look (a flat color bar,
    not a rounded pill)."""
    w, h = max(1, text_width + padding * 2 + accent_width), max(1, text_height + padding)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=6, fill=_hex_to_rgba(color, 255))
    draw.rectangle([(0, 0), (accent_width, h - 1)], fill=_hex_to_rgba(accent_color, 255))
    return img


def draw_ribbon_tag(bar_width: int, bar_height: int, accent_color: str) -> Image.Image:
    """A small folded-flag accent shape (rectangle with a triangular notch
    cut from its right edge) meant to sit just under a name-plate bar --
    the 'ribbon tag' flourish from broadcast-style name lower thirds."""
    tag_w = max(1, int(bar_width * 0.42))
    tag_h = max(1, int(bar_height * 0.55))
    notch = tag_h // 2
    img = Image.new("RGBA", (tag_w + notch, tag_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    points = [(0, 0), (tag_w, 0), (tag_w + notch, tag_h // 2), (tag_w, tag_h), (0, tag_h)]
    draw.polygon(points, fill=_hex_to_rgba(accent_color, 255))
    return img


def draw_dotted_line(length: int, color: str, dot_radius: int = 3, gap: int = 10, vertical: bool = True) -> Image.Image:
    """A vertical (or horizontal) dotted divider, `length` px long."""
    length = max(1, length)
    if vertical:
        img = Image.new("RGBA", (dot_radius * 2 + 2, length), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        y = 0
        while y < length:
            draw.ellipse([(0, y), (dot_radius * 2, y + dot_radius * 2)], fill=_hex_to_rgba(color, 255))
            y += dot_radius * 2 + gap
    else:
        img = Image.new("RGBA", (length, dot_radius * 2 + 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        x = 0
        while x < length:
            draw.ellipse([(x, 0), (x + dot_radius * 2, dot_radius * 2)], fill=_hex_to_rgba(color, 255))
            x += dot_radius * 2 + gap
    return img


def draw_small_star(size: int, color: str) -> Image.Image:
    """A small 4-point decorative sparkle, for scattering in a corner of the frame."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    outer_r, inner_r = size / 2, size / 8
    vertices = []
    for i in range(8):
        r = outer_r if i % 2 == 0 else inner_r
        angle = math.pi * i / 4
        vertices.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(vertices, fill=_hex_to_rgba(color, 255))
    return img


_CONFETTI_COLORS = ["#FF3B3B", "#FFD400", "#39FF14", "#00D4FF", "#FF6EC7", "#FFFFFF"]


def draw_confetti(width: int, height: int, elapsed: float, count: int = 40) -> Image.Image:
    """Falling confetti squares for the Confetti Pop title moment. Each
    particle's path is derived purely from its (fixed) index and `elapsed`
    so it's reproducible frame-to-frame without keeping state between calls."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(count):
        rng = random.Random(i * 7919)
        base_x = rng.uniform(0, width)
        speed = rng.uniform(90, 220)
        phase = rng.uniform(0, math.tau)
        drift_amp = rng.uniform(10, 40)
        size = rng.randint(5, 11)
        start_delay = rng.uniform(0, 0.6)
        t = max(0.0, elapsed - start_delay)
        y = (t * speed) % (height + 40) - 20
        x = base_x + drift_amp * math.sin(t * 3 + phase)
        color = _CONFETTI_COLORS[i % len(_CONFETTI_COLORS)]
        draw.rectangle([(x - size / 2, y - size / 2), (x + size / 2, y + size / 2)], fill=_hex_to_rgba(color, 235))
    return img


def draw_ribbon_bar(width: int, height: int, bar_height: int, color: str, progress: float, center_y_ratio: float = 0.78, alpha: int = 235) -> Image.Image:
    """A full-width color bar that wipes in from the center as `progress` goes 0 -> 1, for the Ribbon Banner title moment (news-chyron style reveal)."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    progress = max(0.0, min(1.0, progress))
    visible_w = int(width * progress)
    if visible_w <= 0:
        return img
    cy = int(height * center_y_ratio)
    x0 = width // 2 - visible_w // 2
    draw.rectangle([(x0, cy - bar_height // 2), (x0 + visible_w, cy + bar_height // 2)], fill=_hex_to_rgba(color, alpha))
    return img


def paste_with_alpha(base: Image.Image, overlay: Image.Image, position: tuple[int, int], scale: float = 1.0, opacity: float = 1.0) -> None:
    """
    Pastes `overlay` (RGBA) onto `base` (RGBA) at `position`, applying a
    uniform scale and opacity -- the shared primitive every graphic's
    appear/disappear and scale-in animation is built from.
    """
    if scale != 1.0:
        new_size = (max(1, int(overlay.width * scale)), max(1, int(overlay.height * scale)))
        overlay = overlay.resize(new_size, Image.LANCZOS)
    if opacity < 1.0:
        alpha = overlay.split()[3].point(lambda p: int(p * opacity))
        overlay = overlay.copy()
        overlay.putalpha(alpha)
    base.alpha_composite(overlay, position)
