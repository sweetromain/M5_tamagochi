#!/usr/bin/env python3
"""Génère les sprites d'OBJETS (assets/sprites/items/) avec l'API Fal, style des dragons.

Image de base par texte (FLUX dev), étapes suivantes (repas entamé...) par édition Kontext de la
base, détourage BiRefNet, réduction à la taille du manifeste. Cache : assets/fal_raw/items/.

Usage :
  export FAL_KEY=ta_cle
  python3 tools/fal_items.py                      # tous les objets (~15 générations, < 1 $)
  python3 tools/fal_items.py --item meal --force  # refaire un objet
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fal_dragons as F  # noqa: E402
import sprite_manifest as M  # noqa: E402

RAW = os.path.join(F.RAW, "items")
OUT = os.path.join(F.OUT, "items")

STYLE = ("single video game item, 16-bit pixel art icon, chunky pixels, thick dark outline, flat vivid colors, "
         "simple readable shape, centered, plain solid magenta #FF00FF background, no text, no shadow")
KEEP = ("Keep exactly the same object, same pixel art style, same colors, same framing, same plain solid "
        "magenta background, no text, no shadow.")

# nom -> (description de base, [images suivantes], ancrage, taille max)
# images suivantes : "gen:<édition>" (Kontext depuis la base), "t2i:<description>" (texte seul),
# "cut:<i>:<f>" (image i dont on retire la fraction f gauche, comme une bouchée ; "cutplate" garde
# l'assiette), "squash", "rot90" (code)
ITEMS = {
    "meal": ("a roasted meat drumstick with a bone on a small round white plate, seen slightly from above",
             ["gen:a big bite is taken out of the meat: a clear round bite mark showing pale meat inside, same plate",
              "cutplate:1:0.4",
              "t2i:a bare white meat bone with a few crumbs on a small round white plate, seen slightly from above"],
             "center", 16),
    "snack": ("a slice of strawberry cream cake with a strawberry on top",
              ["gen:remove the strawberry from the top of the cake slice",
               "cut:1:0.45",
               "gen:only a few cake crumbs are left, the cake is gone"],
              "center", 16),
    "pill": ("a red and white medicine capsule pill, horizontal", [], "center", 15),
    "poop": ("a cute cartoon brown swirl poop with three coils", ["squash"], "bottom", 15),
    "shower": ("a chrome shower head at the top spraying many blue water drops downward",
               ["gen:same shower head, the blue water drops are now at different positions, falling lower"],
               "center", 32),
    "ball": ("a round red and white toy ball with a white stripe", ["rot90"], "center", 15),
    "tombstone": ("a small rounded grey stone tombstone with a cross carved on it, on a small patch of green grass",
                  [], "bottom", 31),
    "bed": ("a small wide low purple cushion pet bed seen from the side, flat and rectangular", [], "bottom", 32),
}


def raw_path(name, i):
    return os.path.join(RAW, f"{name}_{i + 1:02d}.png")


def bite(img, frac, keep_plate=False):
    """Retire la partie gauche (fraction `frac` de la largeur utile) avec un bord arrondi de bouchée.

    keep_plate : épargne les pixels clairs et peu saturés (l'assiette blanche).
    """
    out = img.copy()
    bbox = out.getbbox()
    if not bbox:
        return out
    x0, y0, x1, y1 = bbox
    cut = x0 + (x1 - x0) * frac
    cy, r = (y0 + y1) / 2, (y1 - y0) / 2 + 1
    px = out.load()
    for y in range(out.height):
        # bord concave : la morsure avance davantage au milieu
        dy = (y - cy) / r if r else 0
        edge = cut + max(0.0, 1 - dy * dy) * 2
        for x in range(out.width):
            if x < edge:
                r, g, b, a = px[x, y]
                if keep_plate and a and min(r, g, b) > 160 and max(r, g, b) - min(r, g, b) < 50:
                    continue
                px[x, y] = (0, 0, 0, 0)
    return out


def build(fal, name, force=False):
    w, h = next((x[2], x[3]) for x in M.OTHER if x[0] == "items" and x[1] == name)
    desc, steps, anchor, max_size = ITEMS[name]
    colors = 12 if max(w, h) <= 16 else 16
    base = raw_path(name, 0)
    if force or not os.path.exists(base):
        url = fal.run(F.MODEL_T2I, {"prompt": f"{desc}, {STYLE}", "image_size": "square_hd",
                                    "num_inference_steps": 32, "output_format": "png", "seed": 3})
        fal.download(url, base)
        F.cutout_reset(base)
        with open(base + ".url", "w") as f:
            f.write(url)
    base_url = open(base + ".url").read().strip()
    frames = [F.to_sprite(base, max_size, (w, h), anchor, colors)]
    for i, step in enumerate(steps, 1):
        if step.startswith("gen:"):
            p = raw_path(name, i)
            if force or not os.path.exists(p):
                url = fal.run(F.MODEL_EDIT, {"prompt": f"{step[4:]}. {KEEP}", "image_url": base_url,
                                             "output_format": "png", "seed": 5 + i})
                fal.download(url, p)
                F.cutout_reset(p)
            frames.append(F.to_sprite(p, max_size, (w, h), anchor, colors))
        elif step.startswith("t2i:"):
            p = raw_path(name, i)
            if force or not os.path.exists(p):
                url = fal.run(F.MODEL_T2I, {"prompt": f"{step[4:]}, {STYLE}", "image_size": "square_hd",
                                            "num_inference_steps": 32, "output_format": "png", "seed": 3})
                fal.download(url, p)
                F.cutout_reset(p)
            frames.append(F.to_sprite(p, max_size, (w, h), anchor, colors))
        elif step.startswith(("cut:", "cutplate:")):
            kind, src, frac = step.split(":")
            frames.append(bite(frames[int(src)], float(frac), keep_plate=kind == "cutplate"))
        elif step == "squash":
            frames.append(F.squash(frames[0]))
        elif step == "rot90":
            frames.append(frames[0].rotate(90))
    os.makedirs(OUT, exist_ok=True)
    for i, fr in enumerate(frames):
        fr.save(os.path.join(OUT, f"{name}_{i + 1:02d}.png"))
    print(f"[item] {name} ({len(frames)} image(s))")


def sheet(path, scale=6):
    rows = []
    for name in ITEMS:
        i, tiles = 1, []
        while os.path.exists(p := os.path.join(OUT, f"{name}_{i:02d}.png")):
            tiles.append(Image.open(p).convert("RGBA"))
            i += 1
        rows.append((name, tiles))
    cell = 32 * scale + 8
    img = Image.new("RGB", (110 + 4 * cell, len(rows) * cell + 8), (34, 34, 44))
    d = ImageDraw.Draw(img)
    for r, (name, tiles) in enumerate(rows):
        y = 8 + r * cell
        d.text((8, y + cell // 2 - 8), name, fill=(255, 210, 90))
        for c, t in enumerate(tiles):
            bg = Image.new("RGBA", t.size, (236, 236, 240, 255))
            bg.alpha_composite(t)
            img.paste(bg.resize((t.width * scale, t.height * scale), Image.NEAREST), (110 + c * cell, y))
    img.save(path)
    print(f"planche : {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", action="append", choices=list(ITEMS))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    fal = F.Fal()
    F.CUT_FAL = fal
    errors = []
    for name in a.item or ITEMS:
        try:
            build(fal, name, a.force)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            print(f"ERREUR {name}: {e}")
    print(f"{fal.calls} appels Fal, {len(errors)} erreur(s)")
    sheet(os.path.join(F.ROOT, "docs", "items_planche.png"))


if __name__ == "__main__":
    main()
