#!/usr/bin/env python3
"""Génère les sprites PROVISOIRES dans assets/placeholders/.

Tes vrais sprites vont dans assets/sprites/ (même arborescence) : ils sont
prioritaires sur les provisoires lors de la conversion (tools/png2rgb565.py).

Usage : python3 tools/make_placeholders.py [--sheet docs/sprites_preview.png]
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprite_manifest as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "placeholders")
T = M.TRANSPARENT_RGB

INK = (30, 20, 40)
WHITE = (255, 255, 255)
RED = (230, 40, 60)
PINK = (255, 120, 150)
BLUE = (80, 160, 255)
YELLOW = (255, 220, 40)
GREEN_SICK = (150, 200, 90)
BROWN = (120, 70, 30)

STAGE_STYLE = {
    #            couleur           l   h   détail
    "baby":       ((255, 205, 80),  18, 16, None),
    "child":      ((120, 200, 255), 22, 20, "ears"),
    "teen":       ((130, 220, 140), 22, 24, "antenna"),
    "adult_good": ((255, 150, 190), 26, 24, "ears"),
    "adult_mid":  ((205, 165, 110), 26, 22, "tuft"),
    "adult_bad":  ((150, 110, 205), 26, 24, "horns"),
    "senior":     ((185, 185, 185), 24, 22, "mustache"),
}

# pose -> (yeux, bouche, extras, décalages verticaux par image)
POSE_STYLE = {
    "idle":       ("open",   "smile", [],                   [0, 1]),
    "walk":       ("open",   "smile", ["step"],             [0, -1]),
    "blink":      ("closed", "smile", [],                   [0]),
    "happy":      ("happy",  "grin",  ["arms_up"],          [0, -1]),
    "very_happy": ("happy",  "grin",  ["arms_up", "blush"], [-5, 0]),
    "love":       ("heart",  "smile", ["blush"],            [0, -1]),
    "sad":        ("sad",    "frown", [],                   [1, 1]),
    "cry":        ("sad",    "open",  ["tears"],            [1, 0]),
    "angry":      ("angry",  "frown", ["red_cheeks"],       [0, 1]),
    "refuse":     ("angry",  "flat",  ["shake"],            [0, 0]),
    "surprised":  ("wide",   "o",     [],                   [-1]),
    "bored":      ("half",   "flat",  [],                   [1, 1]),
    "hungry":     ("sad",    "drool", [],                   [0, 1]),
    "eat":        ("closed", "eat",   [],                   [0, 0, 0]),
    "full":       ("happy",  "smile", ["fat"],              [0]),
    "sleepy":     ("half",   "yawn",  [],                   [0, 1]),
    "sleep":      ("closed", "flat",  ["lying"],            [0, 0]),
    "wake_up":    ("half",   "o",     ["arms_up"],          [0, -1]),
    "sick":       ("dizzy",  "wavy",  ["green", "shiver"],  [0, 0]),
    "medicine":   ("closed", "wavy",  ["sweat"],            [0, 1]),
    "dirty":      ("sad",    "wavy",  ["flies"],            [0, 1]),
    "poop":       ("closed", "flat",  ["squat", "sweat"],   [2, 3]),
    "wash":       ("closed", "grin",  ["bubbles"],          [0, 0]),
    "scolded":    ("sad",    "flat",  ["sweat"],            [2, 2]),
    "call":       ("wide",   "open",  ["arms_up"],          [0, -3]),
    "look_left":  ("left",   "flat",  [],                   [0]),
    "look_right": ("right",  "flat",  [],                   [0]),
    "win":        ("happy",  "grin",  ["arms_up", "blush"], [-3, 0]),
    "lose":       ("sad",    "frown", ["tears"],            [1, 1]),
    "evolve":     ("none",   "none",  ["silhouette"],       [0]),
    "dying":      ("dizzy",  "wavy",  ["green", "sink"],    [2, 5]),
    "dead":       ("x",      "flat",  ["lying", "grey"],    [0]),
}


def new(w, h):
    return Image.new("RGB", (w, h), T)


def mix(c, k):
    """Assombrit (k<1) ou éclaircit (k>1) une couleur."""
    if k <= 1:
        return tuple(int(v * k) for v in c)
    return tuple(int(v + (255 - v) * (k - 1)) for v in c)


# --------------------------------------------------------------- créature
def draw_eyes(d, kind, lx, rx, y, f):
    for i, x in enumerate((lx, rx)):
        if kind == "open":
            d.rectangle([x - 1, y - 2, x, y], fill=INK)
            d.point((x, y - 2), fill=WHITE)
        elif kind == "closed":
            d.line([x - 1, y, x + 1, y], fill=INK)
        elif kind == "happy":
            d.point([(x - 1, y), (x, y - 1), (x + 1, y)], fill=INK)
        elif kind == "sad":
            d.rectangle([x - 1, y, x, y + 1], fill=INK)
            sx = -1 if i == 0 else 1
            d.line([x - 1 - sx, y - 3 + (1 if sx < 0 else 0), x + 1 - sx, y - 3 + (0 if sx < 0 else 1)], fill=INK)
        elif kind == "angry":
            d.rectangle([x - 1, y, x, y + 1], fill=INK)
            if i == 0:
                d.line([x - 2, y - 3, x + 1, y - 1], fill=INK)
            else:
                d.line([x - 2, y - 1, x + 1, y - 3], fill=INK)
        elif kind == "wide":
            d.rectangle([x - 2, y - 2, x + 1, y + 1], fill=WHITE, outline=INK)
            d.point((x, y), fill=INK)
        elif kind == "half":
            d.line([x - 1, y, x + 1, y], fill=INK)
            d.point((x, y + 1), fill=INK)
        elif kind == "heart":
            d.point([(x - 1, y - 1), (x + 1, y - 1)], fill=RED)
            d.line([x - 1, y, x + 1, y], fill=RED)
            d.point((x, y + 1), fill=RED)
        elif kind == "x":
            d.line([x - 1, y - 1, x + 1, y + 1], fill=INK)
            d.line([x - 1, y + 1, x + 1, y - 1], fill=INK)
        elif kind == "dizzy":
            d.rectangle([x - 1, y - 1, x + 1, y + 1], outline=INK)
            d.point((x, y) if f % 2 == 0 else (x + 1, y + 1), fill=INK)
        elif kind in ("left", "right"):
            d.rectangle([x - 2, y - 2, x + 1, y + 1], fill=WHITE, outline=INK)
            px = x - 1 if kind == "left" else x
            d.rectangle([px, y - 1, px, y], fill=INK)


def draw_mouth(d, kind, cx, y, f):
    if kind == "smile":
        d.point([(cx - 2, y), (cx + 2, y)], fill=INK)
        d.line([cx - 1, y + 1, cx + 1, y + 1], fill=INK)
    elif kind == "grin":
        d.rectangle([cx - 2, y, cx + 2, y + 2], fill=INK)
        d.line([cx - 1, y + 2, cx + 1, y + 2], fill=RED)
    elif kind == "frown":
        d.line([cx - 1, y, cx + 1, y], fill=INK)
        d.point([(cx - 2, y + 1), (cx + 2, y + 1)], fill=INK)
    elif kind == "flat":
        d.line([cx - 1, y, cx + 1, y], fill=INK)
    elif kind == "o":
        d.rectangle([cx - 1, y, cx + 1, y + 2], outline=INK)
    elif kind == "open":
        d.rectangle([cx - 2, y, cx + 2, y + 2 + (f % 2)], fill=INK)
    elif kind == "drool":
        d.line([cx - 1, y, cx + 1, y], fill=INK)
        d.line([cx + 1, y + 1, cx + 1, y + 2 + f % 2], fill=BLUE)
    elif kind == "yawn":
        h = 3 if f == 0 else 1
        d.ellipse([cx - 2, y, cx + 2, y + h], fill=INK)
    elif kind == "wavy":
        for i in range(-2, 3):
            d.point((cx + i, y + (i + f) % 2), fill=INK)
    elif kind == "eat":
        if f == 0:
            d.rectangle([cx - 2, y - 1, cx + 2, y + 2], fill=INK)
        else:
            d.line([cx - 2, y + (f % 2), cx + 2, y + 1 - (f % 2)], fill=INK)


def draw_creature(stage, pose, f):
    img = new(32, 32)
    d = ImageDraw.Draw(img)
    color, bw, bh, feature = STAGE_STYLE[stage]
    eyes, mouth, extras, dys = POSE_STYLE[pose]
    dy = dys[f % len(dys)]
    dx = 0
    if "shake" in extras:
        dx = -2 if f == 0 else 2
    if "shiver" in extras:
        dx = f % 2
    if "green" in extras:
        color = tuple((a + b) // 2 for a, b in zip(color, GREEN_SICK))
    if "grey" in extras:
        color = (160, 160, 160)
    if "fat" in extras:
        bw += 4
    if "squat" in extras:
        bh -= 3
        bw += 2
    if "sink" in extras:
        bh -= 2 * f
    lying = "lying" in extras
    if lying:
        bw, bh = bw + 6, max(10, bh - 8)
    outline = mix(color, 0.45)

    cx = 16 + dx
    bottom = 29 + min(dy, 2) if dy > 0 else 29 + dy
    top = bottom - bh
    left, right = cx - bw // 2, cx + bw // 2

    # ombre au sol
    d.line([cx - bw // 2 + 2, 31, cx + bw // 2 - 2, 31], fill=(90, 90, 110))

    # détails derrière le corps
    if feature == "ears" and not lying:
        d.polygon([(left + 2, top + 4), (left + 4, top - 4), (left + 8, top + 2)], fill=color, outline=outline)
        d.polygon([(right - 2, top + 4), (right - 4, top - 4), (right - 8, top + 2)], fill=color, outline=outline)
    if feature == "horns" and not lying:
        d.polygon([(left + 4, top + 3), (left + 3, top - 4), (left + 8, top + 1)], fill=(240, 240, 220), outline=INK)
        d.polygon([(right - 4, top + 3), (right - 3, top - 4), (right - 8, top + 1)], fill=(240, 240, 220), outline=INK)
    if feature == "antenna" and not lying:
        d.line([cx, top, cx + 2, top - 5], fill=outline)
        d.ellipse([cx + 1, top - 7, cx + 4, top - 4], fill=YELLOW, outline=outline)

    # bras levés
    if "arms_up" in extras and not lying:
        d.line([left, top + bh // 2, left - 3, top + 2], fill=outline, width=2)
        d.line([right, top + bh // 2, right + 3, top + 2], fill=outline, width=2)

    # pieds
    if not lying:
        step = 1 if ("step" in extras and f % 2) else 0
        d.rectangle([cx - bw // 4 - 2, bottom - 1 - step, cx - bw // 4 + 1, bottom + 1 - step], fill=outline)
        d.rectangle([cx + bw // 4 - 1, bottom - 1 + step - step, cx + bw // 4 + 2, bottom + 1], fill=outline)

    # corps
    if "silhouette" in extras:
        d.ellipse([left, top, right, bottom], fill=WHITE, outline=(200, 220, 255))
        return img
    d.ellipse([left, top, right, bottom], fill=color, outline=outline)
    # reflet
    d.line([left + 3, top + 4, left + 3, top + 6], fill=mix(color, 1.5))

    if feature == "tuft" and not lying:
        d.line([cx - 2, top, cx - 1, top - 3], fill=outline)
        d.line([cx + 1, top, cx + 2, top - 3], fill=outline)

    # visage
    ey = top + max(4, int(bh * 0.4))
    if lying:
        ey = top + bh // 2 - 1
    ex = max(3, bw // 5)
    draw_eyes(d, eyes, cx - ex, cx + ex + 1, ey, f)
    my = ey + 4 if not lying else ey + 3
    draw_mouth(d, mouth, cx, my, f)
    if feature == "mustache" and not lying:
        d.line([cx - 4, my - 1, cx - 1, my - 1], fill=WHITE)
        d.line([cx + 1, my - 1, cx + 4, my - 1], fill=WHITE)

    # extras
    if "blush" in extras or "red_cheeks" in extras:
        cc = PINK if "blush" in extras else RED
        d.point([(cx - ex - 2, ey + 2), (cx - ex - 1, ey + 2), (cx + ex + 2, ey + 2), (cx + ex + 3, ey + 2)], fill=cc)
    if "tears" in extras:
        ty = ey + 2 + (f % 2) * 2
        d.line([cx - ex - 1, ey + 2, cx - ex - 1, ty + 2], fill=BLUE)
        d.line([cx + ex + 2, ey + 2, cx + ex + 2, ty + 2], fill=BLUE)
    if "sweat" in extras:
        sx, sy = right - 1, top + 2 + f
        d.polygon([(sx, sy), (sx - 1, sy + 2), (sx + 1, sy + 2)], fill=BLUE)
    if "flies" in extras:
        for (fx, fy) in [(left - 1, top + 2 + f), (right - 2, top - 1 - f), (cx, top - 4 + f)]:
            if 0 <= fx < 32 and 0 <= fy < 32:
                d.point((fx, fy), fill=INK)
    if "bubbles" in extras:
        for (bx, by) in [(left + 2, top + 2 - f), (right - 4, top + 6 + f), (cx + 2, top - 2 + f)]:
            d.ellipse([bx, by, bx + 2, by + 2], outline=(180, 220, 255))
    return img


def draw_egg(pose, f):
    img = new(32, 32)
    d = ImageDraw.Draw(img)
    shell, spot, outline = (250, 240, 215), (120, 200, 120), (150, 130, 100)
    dx = 0
    if pose == "idle":
        dx = 0 if f == 0 else 1
    elif pose == "wobble":
        dx = -2 if f == 0 else 2
    d.line([9, 31, 23, 31], fill=(90, 90, 110))
    box = [7 + dx, 6, 25 + dx, 30]
    if pose == "hatch":
        # moitié basse + morceau du haut qui s'envole
        d.chord([7, 6, 25, 30], 0, 180, fill=shell, outline=outline)
        d.ellipse([11, 13, 21, 23], fill=(255, 205, 80), outline=mix((255, 205, 80), 0.45))
        d.rectangle([13, 16, 14, 17], fill=INK)
        d.rectangle([18, 16, 19, 17], fill=INK)
        d.line([(7, 18), (10, 21), (13, 17), (16, 21), (19, 17), (22, 21), (25, 18)], fill=outline)
        oy = -4 - 6 * f
        d.chord([8, 6 + oy, 24, 26 + oy], 180, 360, fill=shell, outline=outline)
        return img
    d.ellipse(box, fill=shell, outline=outline)
    for (sx, sy) in [(11, 12), (18, 10), (14, 20), (20, 22)]:
        d.ellipse([sx + dx, sy, sx + dx + 3, sy + 3], fill=spot)
    if pose == "crack":
        pts = [(16 + dx, 6), (14 + dx, 10), (18 + dx, 13), (13 + dx, 17), (19 + dx, 21), (15 + dx, 25)]
        d.line(pts[: 2 + f * 2], fill=INK)
    return img


def draw_ghost(pose, f):
    img = new(32, 32)
    d = ImageDraw.Draw(img)
    dy = [0, -1][f % 2] if pose == "idle" else -5 * (f + 1)
    body = (235, 240, 255) if not (pose == "ascend" and f == 2) else (180, 190, 220)
    top = 8 + dy
    if top + 18 < 0:
        return img
    d.ellipse([10, 1 + dy, 22, 4 + dy], outline=YELLOW)
    d.pieslice([8, top, 24, top + 18], 180, 360, fill=body, outline=(150, 160, 200))
    d.rectangle([8, top + 9, 24, top + 18], fill=body)
    for i in range(4):
        x = 8 + i * 4
        d.polygon([(x, top + 18), (x + 2, top + 21 + (i + f) % 2), (x + 4, top + 18)], fill=body)
    d.line([8, top + 9, 8, top + 18], fill=(150, 160, 200))
    d.line([24, top + 9, 24, top + 18], fill=(150, 160, 200))
    d.line([12, top + 8, 14, top + 8], fill=INK)
    d.line([18, top + 8, 20, top + 8], fill=INK)
    d.ellipse([15, top + 11, 17, top + 13], outline=INK)
    return img


# --------------------------------------------------------------- autres
def heart(d, x, y, s, col):
    d.ellipse([x, y, x + s // 2, y + s // 2], fill=col)
    d.ellipse([x + s // 2, y, x + s, y + s // 2], fill=col)
    d.polygon([(x, y + s // 4 + 1), (x + s, y + s // 4 + 1), (x + s // 2, y + s)], fill=col)


def bubble(d, w=16, h=16):
    d.rounded_rectangle([0, 0, w - 1, h - 4], radius=4, fill=WHITE, outline=INK)
    d.polygon([(4, h - 4), (6, h - 1), (8, h - 4)], fill=WHITE, outline=INK)
    d.line([5, h - 4, 7, h - 4], fill=WHITE)


def draw_other(group, name, w, h, f):
    img = new(w, h)
    d = ImageDraw.Draw(img)
    sel = name.endswith("_sel")
    base = name[:-4] if sel else name
    if group == "icons":
        bg = YELLOW if sel else (70, 70, 90)
        fg = INK if sel else WHITE
        d.rounded_rectangle([0, 0, 15, 15], radius=3, fill=bg)
        if base == "food":
            d.ellipse([3, 6, 12, 13], fill=(200, 120, 60)); d.line([11, 2, 8, 7], fill=fg, width=2)
        elif base == "play":
            d.ellipse([3, 3, 12, 12], fill=RED, outline=fg); d.line([3, 7, 12, 7], fill=WHITE)
        elif base == "clean":
            d.line([4, 3, 4, 12], fill=fg); d.rectangle([5, 3, 11, 5], fill=BLUE)
            for x in (6, 8, 10):
                d.point((x, 8 + (x % 3)), fill=BLUE)
        elif base == "medicine":
            d.rectangle([6, 2, 9, 13], fill=RED); d.rectangle([2, 6, 13, 9], fill=RED)
        elif base == "light":
            d.ellipse([4, 2, 11, 9], fill=(255, 240, 120), outline=fg); d.rectangle([6, 10, 9, 13], fill=fg)
        elif base == "discipline":
            d.text((5, 1), "!", fill=fg); d.rectangle([7, 3, 8, 9], fill=fg); d.rectangle([7, 11, 8, 12], fill=fg)
        elif base == "stats":
            for i, hh in enumerate((4, 8, 6)):
                d.rectangle([3 + i * 4, 13 - hh, 5 + i * 4, 13], fill=fg)
        elif base == "settings":
            d.ellipse([3, 3, 12, 12], outline=fg, width=2); d.ellipse([6, 6, 9, 9], fill=fg)
        elif base == "attention":
            d.rounded_rectangle([0, 0, 15, 15], radius=3, fill=RED if f == 0 else (120, 20, 30))
            d.rectangle([7, 3, 8, 9], fill=WHITE); d.rectangle([7, 11, 8, 12], fill=WHITE)
        return img
    if group == "emotes":
        bubble(d)
        if base == "heart":
            heart(d, 3 + (f % 2) * 0, 2 + (f % 2), 9, RED)
        elif base == "broken_heart":
            heart(d, 3, 2, 9, RED); d.line([(7, 2), (6, 6), (8, 8), (7, 11)], fill=WHITE)
        elif base == "anger":
            c = RED
            s = 1 + f
            d.line([4, 3, 4 + s, 3 + s], fill=c); d.line([11, 3, 11 - s, 3 + s], fill=c)
            d.line([4, 10, 4 + s, 10 - s], fill=c); d.line([11, 10, 11 - s, 10 - s], fill=c)
        elif base == "sweat":
            d.polygon([(8, 2), (5, 8), (8, 10), (11, 8)], fill=BLUE)
        elif base == "tear":
            d.polygon([(8, 2 + f), (6, 7 + f), (10, 7 + f)], fill=BLUE)
        elif base == "exclaim":
            d.rectangle([7, 2, 8, 7], fill=RED); d.rectangle([7, 9, 8, 10], fill=RED)
        elif base == "question":
            d.arc([5, 2, 10, 7], 180, 90, fill=INK); d.line([8, 7, 8, 8], fill=INK); d.point((8, 10), fill=INK)
        elif base == "zzz":
            for i in range(f + 1):
                x, y, s = 3 + i * 4, 8 - i * 3, 3
                d.line([x, y, x + s, y], fill=BLUE); d.line([x + s, y, x, y + s], fill=BLUE); d.line([x, y + s, x + s, y + s], fill=BLUE)
        elif base == "note":
            x = 5 + f
            d.ellipse([x, 7, x + 3, 10], fill=INK); d.line([x + 3, 2, x + 3, 8], fill=INK); d.line([x + 3, 2, x + 6, 4], fill=INK)
        elif base == "skull":
            d.ellipse([4, 2, 11, 8], fill=(220, 220, 220), outline=INK); d.rectangle([6, 8, 9, 10], fill=(220, 220, 220))
            d.point([(6, 5), (9, 5)], fill=INK)
            if f:
                d.point((7 + f, 10), fill=INK)
        elif base == "stink":
            for x in (4, 8, 11):
                d.arc([x - 2, 2 + f, x + 1, 6 + f], 270, 90, fill=GREEN_SICK)
                d.arc([x - 2, 6 + f, x + 1, 10], 90, 270, fill=GREEN_SICK)
        elif base == "food_bubble":
            d.ellipse([3, 4, 12, 10], fill=(200, 120, 60)); d.line([6, 4, 9, 4], fill=WHITE)
        elif base == "star":
            c = YELLOW if f == 0 else (255, 160, 0)
            pts = []
            for i in range(10):
                r = 5 if i % 2 == 0 else 2
                a = -math.pi / 2 + i * math.pi / 5
                pts.append((7.5 + r * math.cos(a), 6 + r * math.sin(a)))
            d.polygon(pts, fill=c, outline=INK)
        return img
    if group == "items":
        if base in ("meal", "snack"):
            if base == "meal":
                d.ellipse([1, 9, 14, 14], fill=WHITE, outline=INK)
                food = (210, 120, 50)
                parts = [[3, 6, 12, 11], [5, 6, 12, 11], [7, 7, 12, 11], None]
                p = parts[f]
                if p:
                    d.ellipse(p, fill=food, outline=BROWN)
                else:
                    d.point([(5, 10), (8, 11), (11, 10)], fill=food)
            else:
                crumbs = [(2, 4, 13, 13), (5, 4, 13, 13), (8, 4, 13, 13), None]
                c = crumbs[f]
                if c:
                    d.rectangle(c, fill=(240, 200, 150), outline=BROWN)
                    d.rectangle([c[0], c[1], c[2], c[1] + 2], fill=PINK)
                    if f == 0:
                        d.point((7, 2), fill=RED)
                else:
                    d.point([(5, 12), (9, 13), (11, 12)], fill=(240, 200, 150))
        elif base == "pill":
            d.rounded_rectangle([3, 5, 12, 10], radius=2, fill=WHITE, outline=INK)
            d.rectangle([8, 6, 11, 9], fill=RED)
        elif base == "poop":
            col = (140, 90, 40)
            d.ellipse([2, 10, 13, 15], fill=col, outline=BROWN)
            d.ellipse([4, 6, 11, 11], fill=col, outline=BROWN)
            d.ellipse([6, 2 + f, 9, 7], fill=col, outline=BROWN)
        elif base == "shower":
            d.rectangle([4, 2, 26, 6], fill=(170, 170, 190), outline=INK)
            for i in range(6):
                x = 6 + i * 4
                y = 9 + ((i + f) % 2) * 4
                d.line([x, y, x, y + 3], fill=BLUE)
                d.line([x + 1, y + 10, x + 1, y + 13], fill=BLUE)
        elif base == "ball":
            d.ellipse([2, 2, 13, 13], fill=RED, outline=INK)
            d.line([2, 7 + f, 13, 8 - f], fill=WHITE)
        elif base == "tombstone":
            d.rounded_rectangle([7, 4, 24, 30], radius=7, fill=(150, 150, 160), outline=INK)
            d.rectangle([14, 9, 17, 22], fill=(90, 90, 100)); d.rectangle([11, 12, 20, 14], fill=(90, 90, 100))
            d.line([3, 30, 28, 30], fill=(80, 160, 80), width=2)
        elif base == "bed":
            d.rectangle([0, 6, 31, 13], fill=(120, 80, 180), outline=INK)
            d.rectangle([1, 4, 8, 8], fill=WHITE, outline=INK)
        return img
    if group == "ui":
        if base == "heart_full":
            heart(d, 0, 0, 7, RED)
        elif base == "heart_empty":
            d.ellipse([0, 0, 3, 3], outline=(120, 120, 120)); d.ellipse([3, 0, 6, 3], outline=(120, 120, 120))
            d.line([(0, 2), (3, 6), (6, 2)], fill=(120, 120, 120))
        elif base == "battery":
            d.rectangle([0, 0, 10, 7], outline=WHITE); d.rectangle([11, 2, 11, 5], fill=WHITE)
            col = RED if f <= 1 else (80, 220, 80)
            for i in range(f):
                d.rectangle([2 + i * 2, 2, 2 + i * 2, 5], fill=col)
        elif base in ("sound_on", "sound_off"):
            d.polygon([(0, 3), (2, 3), (5, 0), (5, 7), (2, 4), (0, 4)], fill=WHITE)
            if base == "sound_on":
                d.line([7, 2, 7, 5], fill=WHITE)
            else:
                d.line([6, 2, 7, 5], fill=RED); d.line([7, 2, 6, 5], fill=RED)
        elif base == "arrow_left":
            d.polygon([(6, 0), (1, 4), (6, 7)], fill=WHITE)
        elif base == "arrow_right":
            d.polygon([(1, 0), (6, 4), (1, 7)], fill=WHITE)
        elif base == "cursor":
            d.polygon([(1, 0), (6, 3), (1, 7)], fill=YELLOW)
        elif base == "scale":
            d.rectangle([2, 10, 13, 14], fill=(180, 180, 200), outline=INK); d.ellipse([4, 2, 11, 9], fill=WHITE, outline=INK)
            d.line([7, 5, 9, 4], fill=RED)
        elif base == "cake":
            d.rectangle([2, 8, 13, 14], fill=(240, 200, 150), outline=BROWN); d.rectangle([2, 8, 13, 9], fill=PINK)
            d.line([7, 3, 7, 7], fill=BLUE); d.point((7, 2), fill=YELLOW)
        return img
    if group == "fx" and base == "sparkle":
        for i in range(6):
            a = i * math.pi / 3 + f * 0.5
            r = 6 + f * 4
            x, y = 16 + r * math.cos(a), 16 + r * math.sin(a)
            d.line([x - 1, y, x + 1, y], fill=YELLOW); d.line([x, y - 1, x, y + 1], fill=YELLOW)
        return img
    return img


def save(img, group, name, idx):
    path = os.path.join(OUT, group, f"{name}_{idx + 1:02d}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def generate():
    produced = []
    for stage, _ in M.STAGES:
        for pose in M.poses_for_stage(stage):
            nframes = next(p[1] for p in M.POSES if p[0] == pose)
            for f in range(nframes):
                if stage == "egg":
                    img = draw_egg(pose, f)
                elif stage == "ghost":
                    img = draw_ghost(pose, f)
                else:
                    img = draw_creature(stage, pose, f)
                produced.append(save(img, stage, pose, f))
    for group, name, w, h, n, _ in M.OTHER:
        for f in range(n):
            produced.append(save(draw_other(group, name, w, h, f), group, name, f))
    return produced


def contact_sheet(path, scale=3):
    """Planche de contrôle : une ligne par stade, toutes les poses."""
    rows = []
    for stage, _ in M.STAGES:
        tiles = []
        for pose in M.poses_for_stage(stage):
            nframes = next(p[1] for p in M.POSES if p[0] == pose)
            for f in range(nframes):
                tiles.append(Image.open(os.path.join(OUT, stage, f"{pose}_{f + 1:02d}.png")))
        rows.append(tiles)
    cols = max(len(r) for r in rows)
    sheet = Image.new("RGB", (cols * 34 * scale, len(rows) * 34 * scale), (40, 40, 50))
    for y, r in enumerate(rows):
        for x, t in enumerate(r):
            t = t.copy()
            px = t.load()
            for j in range(t.height):
                for i in range(t.width):
                    if px[i, j] == T:
                        px[i, j] = (230, 230, 235)
            sheet.paste(t.resize((32 * scale, 32 * scale), Image.NEAREST), (x * 34 * scale, y * 34 * scale))
    sheet.save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", help="écrit aussi une planche de contrôle PNG")
    a = ap.parse_args()
    files = generate()
    print(f"{len(files)} sprites provisoires générés dans {os.path.relpath(OUT, ROOT)}/")
    if a.sheet:
        contact_sheet(a.sheet)
        print(f"Planche : {a.sheet}")
