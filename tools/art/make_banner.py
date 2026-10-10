"""Helios Tilt banner (1280x640)."""

import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS = 1280, 640, 2
w, h = W * SS, H * SS
F = "/usr/share/fonts/truetype/sand-box/custom/Open Sauce Sans/OpenSauceSans-"


def font(weight, size):
    return ImageFont.truetype(F + weight + ".ttf", int(size * SS))


bg = Image.new("RGB", (1, h))
top, bot = (14, 34, 78), (6, 14, 34)
for y in range(h):
    t = y / (h - 1)
    bg.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
img = bg.resize((w, h)).convert("RGBA")


def glow(cx, cy, r, color, alpha):
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    return lay.filter(ImageFilter.GaussianBlur(r * 0.6))


img = Image.alpha_composite(
    img, glow(int(w * 0.2), int(h * 0.48), 430, (255, 150, 40), 70)
)
img = Image.alpha_composite(
    img, glow(int(w * 0.88), int(h * 0.12), 300, (40, 190, 240), 50)
)

# A row of small panels at the bottom, all tilted toward a sun arc.
lines = Image.new("RGBA", (w, h), (0, 0, 0, 0))
d = ImageDraw.Draw(lines)
base = 604 * SS
d.line([(0, base), (w, base)], fill=(255, 181, 46, 90), width=3 * SS)
x = 40
k = 0
while x < W - 60:
    ang = 15 + 30 * abs(math.sin(k * 0.7))
    cx, cy = (x + 28) * SS, base - 22 * SS
    L = 52 * SS
    dx, dy = L / 2 * math.cos(math.radians(ang)), L / 2 * math.sin(math.radians(ang))
    col = (70, 225, 255) if k % 2 == 0 else (255, 181, 46)
    d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=col + (160,), width=5 * SS)
    d.line([(cx, cy), (cx, base)], fill=col + (120,), width=3 * SS)
    x += 86
    k += 1
img = Image.alpha_composite(img, lines.filter(ImageFilter.GaussianBlur(8 * SS)))
img = Image.alpha_composite(img, lines)

icon = (
    Image.open("icon_512.png")
    .convert("RGBA")
    .resize((380 * SS, 380 * SS), Image.LANCZOS)
)
ix, iy = 80 * SS, 90 * SS
shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
shadow.paste((0, 0, 0, 170), (ix + 10 * SS, iy + 24 * SS), icon.getchannel("A"))
img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(26 * SS)))
img.alpha_composite(icon, (ix, iy))

d = ImageDraw.Draw(img)
tx = 512 * SS
maxw = (W - 512 - 50) * SS
size = 150
while d.textlength("Helios Tilt", font=font("Black", size)) > maxw:
    size -= 2
d.text((tx, 96 * SS), "Helios Tilt", font=font("Black", size), fill=(255, 255, 255))
d.text(
    (tx + 4 * SS, 252 * SS),
    "Solar panels that follow the sun",
    font=font("SemiBold", 38),
    fill=(226, 232, 240),
)
d.text(
    (tx + 4 * SS, 300 * SS),
    "and stow before the storm",
    font=font("SemiBold", 38),
    fill=(226, 232, 240),
)

chips = [
    ("Tracking + seasonal", (255, 181, 46)),
    ("Daily optimum", (255, 181, 46)),
    ("Wind + storm stow", (70, 225, 255)),
    ("Cover / number / script", (70, 225, 255)),
]
chip_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
cd = ImageDraw.Draw(chip_layer)
cf = font("Bold", 24)
cx, cy = tx + 4 * SS, 374 * SS
for i, (label, col) in enumerate(chips):
    if i == 2:
        cx, cy = tx + 4 * SS, cy + 60 * SS
    tw = cd.textlength(label, font=cf)
    pw, ph = tw + 40 * SS, 46 * SS
    cd.rounded_rectangle(
        [cx, cy, cx + pw, cy + ph],
        radius=ph // 2,
        fill=col + (34,),
        outline=col + (220,),
        width=2 * SS,
    )
    cd.text((cx + 20 * SS, cy + ph / 2), label, font=cf, fill=col + (255,), anchor="lm")
    cx += pw + 14 * SS
img = Image.alpha_composite(img, chip_layer)
d = ImageDraw.Draw(img)
d.text(
    (w - 40 * SS, 40 * SS),
    "Home Assistant  \u00b7  HACS  \u00b7  DonTranQuiL",
    font=font("Medium", 22),
    fill=(148, 163, 184),
    anchor="ra",
)

img = img.resize((W, H), Image.LANCZOS).convert("RGB")
img.save("banner.png", optimize=True)
print(img.size, size)
