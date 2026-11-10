#!/usr/bin/env python3
"""Convertit les PNG en tableaux RGB565 C++ (src/generated/sprites_gen.{h,cpp}).

Ordre de recherche pour chaque (stade, pose) :
  1. assets/sprites/<stade>/<pose>_NN.png        (TES sprites)
  2. tes sprites des poses de repli (voir sprite_manifest.POSES), jusqu'à "idle"
  3. assets/placeholders/...                     (provisoires)
Le nombre d'images est celui des fichiers trouvés (_01, _02, ...).

Usage : python3 tools/png2rgb565.py   (appelé automatiquement avant chaque build)
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprite_manifest as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER = os.path.join(ROOT, "assets", "sprites")
PH = os.path.join(ROOT, "assets", "placeholders")
GEN = os.path.join(ROOT, "src", "generated")
TRANSP = 0xF81F

POSE_NAMES = [p[0] for p in M.POSES]
FALLBACK = {p[0]: p[2] for p in M.POSES}


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def load(path, size=None):
    img = Image.open(path).convert("RGBA")
    if size and img.size != size:
        raise SystemExit(f"ERREUR {os.path.relpath(path, ROOT)} : taille {img.size}, attendu {size}")
    out = []
    px = img.load()
    pixels = [px[x, y] for y in range(img.height) for x in range(img.width)]
    for r, g, b, a in pixels:
        if a < 128 or (r, g, b) == M.TRANSPARENT_RGB:
            out.append(TRANSP)
        else:
            v = rgb565(r, g, b)
            out.append(TRANSP - 1 if v == TRANSP else v)
    return img.size, out


def frames_in(base, group, name):
    files = []
    i = 1
    while True:
        p = os.path.join(base, group, f"{name}_{i:02d}.png")
        if not os.path.exists(p):
            break
        files.append(p)
        i += 1
    return files


def chain(pose):
    """Liste (pose, miroir) à essayer, du plus précis au plus générique."""
    out, flip, cur, seen = [], False, pose, set()
    while cur and cur not in seen:
        seen.add(cur)
        out.append((cur, flip))
        fb = FALLBACK.get(cur)
        if fb and fb.startswith("mirror:"):
            flip = not flip
            fb = fb.split(":", 1)[1]
        cur = fb
    if "idle" not in seen:
        out.append(("idle", False))
    return out


def resolve(stage, pose):
    valid = set(M.poses_for_stage(stage))
    for base in (USER, PH):
        for p, flip in chain(pose):
            if base == PH and p not in valid:
                continue
            files = frames_in(base, stage, p)
            if files:
                return files, flip, base == USER
    raise SystemExit(f"ERREUR aucun sprite pour {stage}/{pose} (lance tools/make_placeholders.py)")


class Emitter:
    def __init__(self):
        self.arrays = {}   # chemin -> nom C
        self.body = []
        self.bytes = 0

    def array(self, path, size=None):
        if path in self.arrays:
            return self.arrays[path]
        (w, h), px = load(path, size)
        rel = os.path.relpath(path, ROOT)
        name = "px_" + "".join(c if c.isalnum() else "_" for c in rel[len("assets/"):-4])
        lines = []
        for i in range(0, len(px), 16):
            lines.append("  " + ",".join(f"0x{v:04X}" for v in px[i:i + 16]))
        self.body.append(f"// {rel} ({w}x{h})\nstatic const uint16_t {name}[] = {{\n" + ",\n".join(lines) + "\n};\n")
        self.arrays[path] = name
        self.bytes += len(px) * 2
        return name

    def anim(self, var, files, w, h, flip):
        names = [self.array(f, (w, h)) for f in files]
        self.body.append(f"static const uint16_t* const {var}[] = {{ {', '.join(names)} }};\n")
        return f"{{ {var}, {len(names)}, {w}, {h}, {'true' if flip else 'false'} }}"


def main():
    os.makedirs(GEN, exist_ok=True)
    em = Emitter()
    user_count = 0

    creature_rows = []
    for stage, _ in M.STAGES:
        row = []
        for pose in POSE_NAMES:
            files, flip, is_user = resolve(stage, pose)
            user_count += is_user
            row.append(em.anim(f"anim_{stage}_{pose}", files, 32, 32, flip))
        creature_rows.append("  { " + ",\n    ".join(row) + " }")

    other = []
    for group, name, w, h, _, _ in M.OTHER:
        files = frames_in(USER, group, name) or frames_in(PH, group, name)
        if not files:
            raise SystemExit(f"ERREUR aucun sprite pour {group}/{name}")
        other.append(em.anim(f"anim_{group}_{name}", files, w, h, False))

    bgs = []
    for name, w, h, _ in M.BACKGROUNDS:
        p = os.path.join(USER, "bg", f"{name}.png")
        bgs.append(em.array(p, (w, h)) if os.path.exists(p) else "nullptr")

    # ---- header
    h = ["// FICHIER GÉNÉRÉ par tools/png2rgb565.py — ne pas modifier à la main.",
         "#pragma once", "#include <stdint.h>", "",
         "struct Anim {",
         "  const uint16_t* const* frames;  // RGB565, 0xF81F = transparent",
         "  uint8_t count;",
         "  uint8_t w, h;",
         "  bool flip;                       // dessiner en miroir horizontal",
         "};", "",
         f"static const uint16_t SPRITE_TRANSPARENT = 0x{TRANSP:04X};", "",
         "enum StageId : uint8_t {"]
    h += [f"  STAGE_{s.upper()}," for s, _ in M.STAGES] + ["  STAGE_COUNT", "};", ""]
    h += ["enum PoseId : uint8_t {"] + [f"  POSE_{p.upper()}," for p in POSE_NAMES] + ["  POSE_COUNT", "};", ""]
    h += ["enum SpriteId : uint8_t {"] + [f"  SPR_{g.upper()}_{n.upper()}," for g, n, *_ in M.OTHER] + ["  SPR_COUNT", "};", ""]
    h += ["enum BgId : uint8_t {"] + [f"  BG_{n.upper()}," for n, *_ in M.BACKGROUNDS] + ["  BG_COUNT", "};", ""]
    h += ["extern const Anim CREATURE_ANIMS[STAGE_COUNT][POSE_COUNT];",
          "extern const Anim SPRITES[SPR_COUNT];",
          "extern const uint16_t* const BACKGROUNDS[BG_COUNT];  // nullptr si non fourni (240x135)", ""]

    cpp = ["// FICHIER GÉNÉRÉ par tools/png2rgb565.py — ne pas modifier à la main.",
           '#include "sprites_gen.h"', ""] + em.body
    cpp.append("const Anim CREATURE_ANIMS[STAGE_COUNT][POSE_COUNT] = {\n" + ",\n".join(creature_rows) + "\n};\n")
    cpp.append("const Anim SPRITES[SPR_COUNT] = {\n  " + ",\n  ".join(other) + "\n};\n")
    cpp.append("const uint16_t* const BACKGROUNDS[BG_COUNT] = { " + ", ".join(bgs) + " };\n")

    def write(path, text):
        old = open(path).read() if os.path.exists(path) else None
        if old != text:
            with open(path, "w") as fh:
                fh.write(text)

    write(os.path.join(GEN, "sprites_gen.h"), "\n".join(h))
    write(os.path.join(GEN, "sprites_gen.cpp"), "\n".join(cpp))
    print(f"[sprites] {len(em.arrays)} images, {em.bytes // 1024} Ko, "
          f"{user_count}/{len(M.STAGES) * len(POSE_NAMES)} poses créature issues de assets/sprites/")


if __name__ == "__main__":
    main()
