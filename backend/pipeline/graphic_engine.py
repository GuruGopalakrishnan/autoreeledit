"""
Reusable graphic overlay elements: starburst, pill badge, dotted divider,
small decorative star.

Drawn directly with Pillow rather than round-tripped through SVG -- avoids
an extra native-library dependency (cairosvg and its system cairo build,
which is painful to install on Windows) with no visual difference for
shapes this simple.
"""

import math

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
