"""Helios Tilt icon: rounded navy tile, amber sun, tilted cyan panel on an actuator arm."""

import math

from PIL import Image, ImageDraw, ImageFilter

S = 2048
AMBER = (255, 181, 46, 255)
ORANGE = (255, 128, 30, 255)
CYAN = (70, 225, 255, 255)
NAVY = (9, 22, 52, 255)
STEEL = (150, 175, 210, 255)


def rr_mask(size, inset, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [inset, inset, size - inset, size - inset], radius=radius, fill=255
    )
    return m


def gradient(size, top, bottom):
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        g.putpixel(
            (0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        )
    return g.resize((size, size))


def glow(canvas, draw_fn, color, blurs, strength=1.5):
    for b in blurs:
        lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(lay), color)
        g = lay.filter(ImageFilter.GaussianBlur(b))
        g.putalpha(g.getchannel("A").point(lambda v: min(255, int(v * strength))))
        canvas = Image.alpha_composite(canvas, g)
    lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(lay), color)
    return Image.alpha_composite(canvas, lay)


def rot(px, py, cx, cy, ang):
    a = math.radians(ang)
    dx, dy = px - cx, py - cy
    return (
        cx + dx * math.cos(a) - dy * math.sin(a),
        cy + dx * math.sin(a) + dy * math.cos(a),
    )


def build(dark=False):
    inset, radius = 40, 400
    mask = rr_mask(S, inset, radius)
    top, bottom = (
        ((14, 34, 78), (7, 18, 44)) if not dark else ((10, 22, 50), (4, 10, 26))
    )
    bg = gradient(S, top, bottom).convert("RGBA")
    rad = Image.new("L", (S, S), 0)
    ImageDraw.Draw(rad).ellipse([S * 0.40, S * 0.02, S * 1.05, S * 0.62], fill=110)
    rad = rad.filter(ImageFilter.GaussianBlur(240))
    canvas = Image.composite(Image.new("RGBA", (S, S), (120, 80, 40, 255)), bg, rad)

    # Sun (upper right) with rays.
    sx, sy, sr = 1470, 520, 230

    def sun(dd, col):
        dd.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=col)

    def rays(dd, col):
        for k in range(12):
            a = math.radians(k * 30 + 15)
            r0, r1 = sr + 70, sr + 170
            dd.line(
                [
                    (sx + r0 * math.cos(a), sy + r0 * math.sin(a)),
                    (sx + r1 * math.cos(a), sy + r1 * math.sin(a)),
                ],
                fill=col,
                width=46,
            )

    canvas = glow(canvas, rays, AMBER, (40, 12), 1.2)
    sun_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sun_layer).ellipse(
        [sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, 255)
    )
    shade = gradient(S, (255, 205, 90), (255, 120, 30)).convert("RGBA")
    for b in (120, 50):
        g = sun_layer.filter(ImageFilter.GaussianBlur(b))
        g = Image.composite(
            Image.new("RGBA", (S, S), AMBER),
            Image.new("RGBA", (S, S), (0, 0, 0, 0)),
            g.getchannel("A").point(lambda v: min(255, int(v * 1.3))),
        )
        canvas = Image.alpha_composite(canvas, g)
    canvas = Image.alpha_composite(
        canvas,
        Image.composite(
            shade, Image.new("RGBA", (S, S), (0, 0, 0, 0)), sun_layer.getchannel("A")
        ),
    )

    d = ImageDraw.Draw(canvas)
    # Ground.
    gy = 1660
    d.rounded_rectangle([260, gy, 1790, gy + 46], radius=23, fill=(60, 90, 140, 255))

    # Panel: pivot on a post, tilted toward the sun.
    px, py = 1000, 1250
    ang = 30  # degrees: back (left) edge raised, the face looks up-right at the sun
    L, T = 1120, 92
    corners = [
        rot(px - L / 2, py - T / 2, px, py, ang),
        rot(px + L / 2, py - T / 2, px, py, ang),
        rot(px + L / 2, py + T / 2, px, py, ang),
        rot(px - L / 2, py + T / 2, px, py, ang),
    ]

    # Post and actuator arm (behind the panel).
    d.rounded_rectangle([px - 44, py, px + 44, gy + 10], radius=30, fill=STEEL)
    base = (px - 470, gy)
    attach = rot(px - 360, py + 40, px, py, ang)
    d.line([base, attach], fill=STEEL, width=64)
    mid = (
        base[0] + (attach[0] - base[0]) * 0.55,
        base[1] + (attach[1] - base[1]) * 0.55,
    )
    d.line([base, mid], fill=(110, 135, 175, 255), width=96)  # cylinder
    for (cx, cy), r in ((base, 58), (attach, 50), ((px, py), 62)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 215, 240, 255))
        d.ellipse(
            [cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=NAVY
        )

    # Panel face: a thick glowing cyan slab with cell lines.
    face = [
        rot(px - L / 2, py - T / 2 - 210, px, py, ang),
        rot(px + L / 2, py - T / 2 - 210, px, py, ang),
        rot(px + L / 2, py - T / 2, px, py, ang),
        rot(px - L / 2, py - T / 2, px, py, ang),
    ]

    def panel(dd, col):
        dd.polygon(face, fill=col)

    canvas = glow(canvas, panel, CYAN, (60, 20), 1.0)
    d = ImageDraw.Draw(canvas)
    d.polygon(face, fill=(28, 120, 190, 255))
    # cells
    for k in range(1, 6):
        t = k / 6
        a = (
            face[0][0] + (face[1][0] - face[0][0]) * t,
            face[0][1] + (face[1][1] - face[0][1]) * t,
        )
        b = (
            face[3][0] + (face[2][0] - face[3][0]) * t,
            face[3][1] + (face[2][1] - face[3][1]) * t,
        )
        d.line([a, b], fill=(110, 230, 255, 255), width=14)
    for k in (1,):
        t = k / 2
        a = (
            face[0][0] + (face[3][0] - face[0][0]) * t,
            face[0][1] + (face[3][1] - face[0][1]) * t,
        )
        b = (
            face[1][0] + (face[2][0] - face[1][0]) * t,
            face[1][1] + (face[2][1] - face[1][1]) * t,
        )
        d.line([a, b], fill=(110, 230, 255, 255), width=14)
    d.polygon(face, outline=CYAN, width=34)
    d.polygon(corners, fill=(200, 215, 240, 255))  # frame underside
    # glint
    g0 = rot(px - L / 2 + 120, py - T / 2 - 160, px, py, ang)
    g1 = rot(px - L / 2 + 360, py - T / 2 - 160, px, py, ang)
    d.line([g0, g1], fill=(235, 252, 255, 230), width=22)

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        [inset + 6, inset + 6, S - inset - 6, S - inset - 6],
        radius=radius - 6,
        outline=(120, 170, 255, 70),
        width=10,
    )
    return Image.alpha_composite(out, rim)


if __name__ == "__main__":
    for dark in (False, True):
        img = build(dark)
        tag = "dark_" if dark else ""
        for size in (512, 256):
            img.resize((size, size), Image.LANCZOS).save(
                f"{tag}icon_{size}.png", optimize=True
            )
    print("ok")
