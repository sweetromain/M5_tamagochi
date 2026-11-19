#!/usr/bin/env python3
"""Génère avec l'API Fal les décors et les derniers sprites (bulles, icônes, interface, effet).

- Décors 240x135 : `day` et `title` par texte (FLUX dev), `night`, `sick`, `game` par édition
  Kontext de `day` (même lieu).
- Petits sprites : seul le SYMBOLE est généré (puis détouré par BiRefNet) ; la tuile des icônes,
  la bulle des émotions, les barres de batterie et les images d'animation sont composées en code
  pour rester nettes à 8x8 / 16x16.

Cache : assets/fal_raw/ui/. Usage :
  export FAL_KEY=ta_cle
  python3 tools/fal_ui.py                       # tout (~37 générations, ~2 $)
  python3 tools/fal_ui.py --only bg --force     # refaire les décors
  python3 tools/fal_ui.py --only heart          # refaire un symbole
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fal_dragons as F  # noqa: E402
import sprite_manifest as M  # noqa: E402

RAW = os.path.join(F.RAW, "ui")
OUT = F.OUT

SYMBOL_STYLE = ("single simple game icon symbol, 16-bit pixel art, very bold chunky shape, thick dark outline, "
                "flat vivid colors, minimal details, centered, plain solid magenta #FF00FF background, "
                "no text, no shadow")
BG_STYLE = ("16-bit pixel art video game background, side view, soft muted pastel colors, low contrast, "
            "simple shapes, wide empty flat ground strip along the whole bottom edge, nothing in the center, "
            "no characters, no animals, no text")
KEEP_BG = "Keep exactly the same scene layout, same pixel art style, same flat ground at the bottom, no characters, no text."

# --------------------------------------------------------------------------- symboles
SYMBOLS = {
    # icônes du menu
    "i_food": "a roasted meat drumstick with a bone",
    "i_play": "a red and white toy ball",
    "i_clean": "a blue shower head spraying water drops",
    "i_medicine": "a red medical cross",
    "i_light": "a glowing yellow light bulb",
    "i_discipline": "a silver referee whistle",
    "i_stats": "a bar chart with three colored vertical bars",
    "i_settings": "a grey gear cog",
    "i_attention": "a bold red exclamation mark",
    # bulles d'émotion
    "e_heart": "a red heart",
    "e_broken_heart": "a red heart broken in two halves with a zigzag crack",
    "e_anger": "a red cartoon anger vein symbol, four curved marks forming a cross",
    "e_sweat": "a single light blue sweat drop",
    "e_tear": "a single blue teardrop",
    "e_exclaim": "a bold red exclamation mark",
    "e_question": "a bold blue question mark",
    "e_z": "a bold blue letter Z",
    "e_note": "a black music note, eighth note",
    "e_skull": "a white cartoon skull",
    "e_stink": "three wavy green stink lines rising up",
    "e_food": "a roasted meat drumstick with a bone",
    "e_star": "a shiny yellow five-pointed star",
    # interface
    "u_heart": "a red heart",
    "u_battery": "an empty horizontal battery outline, white frame, black inside, small tip on the right",
    "u_speaker": "a white loudspeaker with sound waves",
    "u_arrow": "a solid white triangle arrow pointing right",
    "u_cursor": "a solid yellow triangle pointer pointing right",
    "u_scale": "a bathroom weighing scale with a round dial",
    "u_cake": "a small birthday cake with one lit candle",
    # effet
    "f_sparkle": "a golden four-pointed sparkle star burst with small glints",
}
EDITS = {  # nom -> (symbole source, édition Kontext)
    "u_heart_empty": ("u_heart", "Make the heart empty: keep only its thick dark outline, the inside light grey."),
}

BACKGROUNDS = {
    "day": ("t2i", "a peaceful dragon meadow at daytime: blue sky with a few clouds, distant soft green "
                   "mountains, small rocks and bushes on the sides, grassy flat ground"),
    "night": ("edit:day", "Make it night: dark blue sky with stars and a crescent moon, everything darker and bluish."),
    "sick": ("edit:day", "Make it gloomy: overcast greyish-green sky, sickly greenish tint over everything, light fog."),
    "game": ("edit:day", "Make it festive: colorful bunting flags hanging across the sky, bright sunny sky, "
                         "a few balloons on the sides."),
    "title": ("t2i", "a speckled green dragon egg resting in a straw nest on top of a grassy hill at sunrise, "
                     "orange and pink sky, the egg small in the lower middle, large empty sky at the top"),
}


def raw(name):
    return os.path.join(RAW, f"{name}.png")


def generate(fal, name, prompt, force, size="square_hd", base=None):
    p = raw(name)
    if os.path.exists(p) and not force:
        return p
    if base is None:
        url = fal.run(F.MODEL_T2I, {"prompt": prompt, "image_size": size, "num_inference_steps": 32,
                                    "output_format": "png", "seed": 21})
    else:
        url = fal.run(F.MODEL_EDIT, {"prompt": prompt, "image_url": open(raw(base) + ".url").read().strip(),
                                     "output_format": "png", "seed": 21})
    fal.download(url, p)
    F.cutout_reset(p)
    with open(p + ".url", "w") as f:
        f.write(url)
    print(f"[fal] {name}")
    return p


def sym(name, box, colors=12):
    """Symbole détouré réduit dans une boîte (w, h), centré."""
    return F.to_sprite(raw(name), max(box), box, "center", colors)


def save(img, group, name, idx):
    d = os.path.join(OUT, group)
    os.makedirs(d, exist_ok=True)
    img.save(os.path.join(d, f"{name}_{idx + 1:02d}.png"))


def paste_center(dst, src, dx=0, dy=0):
    x = (dst.width - src.width) // 2 + dx
    y = (dst.height - src.height) // 2 + dy
    dst.alpha_composite(src, (max(0, x), max(0, y)))


def shifted(img, dx, dy):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy), img)
    return out


# --------------------------------------------------------------------------- compositions
INK = (30, 20, 40, 255)


def tile(color):
    t = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(t).rounded_rectangle([0, 0, 15, 15], radius=3, fill=color)
    return t


def build_icons():
    for n in ("food", "play", "clean", "medicine", "light", "discipline", "stats", "settings"):
        s = sym(f"i_{n}", (12, 12))
        for suffix, col in (("", (70, 70, 90, 255)), ("_sel", (255, 220, 40, 255))):
            t = tile(col)
            paste_center(t, s)
            save(t, "icons", n + suffix, 0)
    s = sym("i_attention", (12, 12))
    for i, col in enumerate(((230, 40, 60, 255), (110, 20, 30, 255))):
        t = tile(col)
        paste_center(t, s)
        if i == 1:  # symbole assombri
            px = t.load()
            for y in range(16):
                for x in range(16):
                    r, g, b, a = px[x, y]
                    if a and (r, g, b, a) != (110, 20, 30, 255):
                        px[x, y] = (r // 2, g // 2, b // 2, a)
        save(t, "icons", "attention", i)


def bubble():
    b = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.rounded_rectangle([0, 0, 15, 12], radius=4, fill=(255, 255, 255, 255), outline=INK)
    d.polygon([(4, 12), (6, 15), (8, 12)], fill=(255, 255, 255, 255), outline=INK)
    d.line([5, 12, 7, 12], fill=(255, 255, 255, 255))
    return b


def in_bubble(symbol, dx=0, dy=0):
    b = bubble()
    area = Image.new("RGBA", (16, 13), (0, 0, 0, 0))
    paste_center(area, symbol, dx, dy)
    b.alpha_composite(area, (0, 0))
    return b


def build_emotes():
    simple = {  # nom manifeste -> (symbole, animation)
        "heart": ("e_heart", "pulse"), "broken_heart": ("e_broken_heart", None), "anger": ("e_anger", "pulse"),
        "sweat": ("e_sweat", None), "tear": ("e_tear", "fall"), "exclaim": ("e_exclaim", None),
        "question": ("e_question", None), "note": ("e_note", "sway"), "skull": ("e_skull", "fall"),
        "stink": ("e_stink", "rise"), "food_bubble": ("e_food", None), "star": ("e_star", "pulse"),
    }
    counts = {x[1]: x[4] for x in M.OTHER if x[0] == "emotes"}
    for name, (s, anim) in simple.items():
        big = sym(s, (11, 10))
        small = sym(s, (9, 8))
        for i in range(counts[name]):
            if i == 0 or anim is None:
                img = in_bubble(big)
            elif anim == "pulse":
                img = in_bubble(small)
            elif anim == "fall":
                img = in_bubble(big, 0, 1)
            elif anim == "rise":
                img = in_bubble(big, 0, -1)
            else:  # sway
                img = in_bubble(big, 1, 0)
            save(img, "emotes", name, i)
    # zzz : 1, 2 puis 3 Z de plus en plus grands
    zs = [sym("e_z", (s, s)) for s in (4, 5, 6)]
    for i in range(3):
        b = bubble()
        for k in range(i + 1):
            z = zs[k]
            b.alpha_composite(z, (2 + k * 4, 8 - k * 3 - z.height // 2))
        save(b, "emotes", "zzz", i)


def build_ui():
    save(sym("u_heart", (8, 8), 6), "ui", "heart_full", 0)
    save(sym("u_heart_empty", (8, 8), 6), "ui", "heart_empty", 0)
    bat = sym("u_battery", (12, 8), 6)
    for lvl in range(5):
        b = bat.copy()
        d = ImageDraw.Draw(b)
        col = (230, 40, 60, 255) if lvl <= 1 else (80, 220, 80, 255)
        for k in range(lvl):
            d.rectangle([2 + k * 2, 2, 2 + k * 2, 5], fill=col)
        save(b, "ui", "battery", lvl)
    spk = sym("u_speaker", (8, 8), 6)
    save(spk, "ui", "sound_on", 0)
    off = spk.copy()
    d = ImageDraw.Draw(off)
    d.line([5, 3, 7, 5], fill=(230, 40, 60, 255))
    d.line([5, 5, 7, 3], fill=(230, 40, 60, 255))
    save(off, "ui", "sound_off", 0)
    arrow = sym("u_arrow", (8, 8), 4)
    save(arrow, "ui", "arrow_right", 0)
    save(arrow.transpose(Image.FLIP_LEFT_RIGHT), "ui", "arrow_left", 0)
    save(sym("u_cursor", (8, 8), 4), "ui", "cursor", 0)
    save(sym("u_scale", (16, 16)), "ui", "scale", 0)
    save(sym("u_cake", (16, 16)), "ui", "cake", 0)


def build_fx():
    base = F.to_sprite(raw("f_sparkle"), 32, (32, 32), "center", 12)
    for i, (k, angle) in enumerate(((0.6, 0), (0.8, 20), (1.0, 40))):
        s = int(32 * k)
        img = base.resize((s, s), Image.NEAREST).rotate(angle)
        out = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        paste_center(out, img)
        save(out, "fx", "sparkle", i)


def build_bg(name):
    img = Image.open(raw(f"bg_{name}")).convert("RGB")
    img = img.resize((240, 135), Image.LANCZOS)
    img = img.quantize(colors=64, method=Image.Quantize.MEDIANCUT).convert("RGB")
    d = os.path.join(OUT, "bg")
    os.makedirs(d, exist_ok=True)
    img.save(os.path.join(d, f"{name}.png"))


# --------------------------------------------------------------------------- planches
def sheets():
    scale, cell = 6, 16 * 6 + 8
    groups = [g for g in ("icons", "emotes", "ui", "fx")]
    rows = []
    for g in groups:
        files = sorted(f for f in os.listdir(os.path.join(OUT, g)) if f.endswith(".png"))
        rows.append((g, [Image.open(os.path.join(OUT, g, f)).convert("RGBA") for f in files]))
    per_row = 18
    lines = []
    for g, imgs in rows:
        for k in range(0, len(imgs), per_row):
            lines.append((g if k == 0 else "", imgs[k:k + per_row]))
    sheet = Image.new("RGB", (80 + per_row * cell, len(lines) * (32 * scale // 2 + 12) + 10), (34, 34, 44))
    d = ImageDraw.Draw(sheet)
    y = 6
    for label, imgs in lines:
        d.text((6, y + 30), label, fill=(255, 210, 90))
        h = 0
        for i, im in enumerate(imgs):
            bg = Image.new("RGBA", im.size, (150, 170, 150, 255))
            bg.alpha_composite(im)
            big = bg.resize((im.width * scale // 2 if im.width > 16 else im.width * scale,
                             im.height * scale // 2 if im.width > 16 else im.height * scale), Image.NEAREST)
            sheet.paste(big, (80 + i * cell, y))
            h = max(h, big.height)
        y += max(h, 16 * scale) + 12
    sheet = sheet.crop((0, 0, sheet.width, y))
    sheet.save(os.path.join(F.ROOT, "docs", "ui_planche.png"))
    # décors
    names = [n for n in BACKGROUNDS if os.path.exists(os.path.join(OUT, "bg", f"{n}.png"))]
    dec = Image.new("RGB", (2 * 480 + 30, ((len(names) + 1) // 2) * 280 + 10), (34, 34, 44))
    for i, n in enumerate(names):
        im = Image.open(os.path.join(OUT, "bg", f"{n}.png")).resize((480, 270), Image.NEAREST)
        dec.paste(im, (10 + (i % 2) * 490, 10 + (i // 2) * 280))
    dec.save(os.path.join(F.ROOT, "docs", "decors_planche.png"))
    print("planches : docs/ui_planche.png, docs/decors_planche.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="bg, icons, emotes, ui, fx, ou un nom de symbole (ex. e_heart)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    fal = F.Fal()
    F.CUT_FAL = fal
    only = set(a.only or [])

    def want(*keys):
        return not only or any(k in only for k in keys)

    errors = []

    def safe(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except Exception as e:  # noqa: BLE001
            label = next((x for x in args if isinstance(x, str)), fn.__name__)
            errors.append(f"{label}: {e}")
            print(f"ERREUR {errors[-1]}")

    # 1. générations
    for name, (kind, prompt) in BACKGROUNDS.items():
        if want("bg", name):
            if kind == "t2i":
                safe(generate, fal, f"bg_{name}", f"{prompt}, {BG_STYLE}", a.force, "landscape_16_9")
            else:
                safe(generate, fal, f"bg_{name}", f"{prompt} {KEEP_BG}", a.force, base="bg_" + kind.split(":")[1])
    for name, desc in SYMBOLS.items():
        grp = {"i": "icons", "e": "emotes", "u": "ui", "f": "fx"}[name[0]]
        if want(grp, name):
            safe(generate, fal, name, f"{desc}, {SYMBOL_STYLE}", a.force)
    for name, (src, edit) in EDITS.items():
        if want("ui", name, src):
            safe(generate, fal, name, f"{edit} Keep the same pixel art style and the same plain solid magenta "
                                      f"background, no text, no shadow.", a.force, base=src)

    # 2. compositions (sans appel Fal hormis les détourages manquants)
    for name in BACKGROUNDS:
        if want("bg", name) and os.path.exists(raw(f"bg_{name}")):
            safe(build_bg, name)
    for grp, fn in (("icons", build_icons), ("emotes", build_emotes), ("ui", build_ui), ("fx", build_fx)):
        safe(fn)
    print(f"{fal.calls} appels Fal, {len(errors)} erreur(s)")
    sheets()
    for e in errors:
        print("  " + e)


if __name__ == "__main__":
    main()
