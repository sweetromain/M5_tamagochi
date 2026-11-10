#!/usr/bin/env python3
"""Génère les sprites de la créature (un dragon) avec l'API Fal.

Principe :
  1. une image de RÉFÉRENCE par stade ; chaque stade est dérivé du précédent par édition
     (le bébé grandit -> même dragon d'un stade à l'autre) ;
  2. chaque pose = édition de la référence du stade (FLUX Kontext) -> même personnage ;
  3. post-traitement : détourage du fond, recadrage, réduction 32x32, 16 couleurs,
     écriture dans assets/sprites/<stade>/<pose>_NN.png (prioritaire sur les provisoires).

Les images brutes sont mises en cache dans assets/fal_raw/ (relancer ne recoûte rien).

Usage :
  export FAL_KEY=ta_cle            # clé API Fal (https://fal.ai/dashboard/keys)
  python3 tools/fal_dragons.py --refs-only          # 9 références + planche de contrôle
  python3 tools/fal_dragons.py                      # toutes les poses (~230 images, ~10 $)
  python3 tools/fal_dragons.py --stage baby --pose eat --force   # refaire une pose
  python3 tools/fal_dragons.py --postprocess-only   # refaire seulement la réduction 32x32
"""
import argparse
import json
import os
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprite_manifest as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "assets", "fal_raw")
OUT = os.path.join(ROOT, "assets", "sprites")
REFS_JSON = os.path.join(RAW, "refs.json")

MODEL_T2I = "fal-ai/flux/dev"
MODEL_EDIT = "fal-ai/flux-pro/kontext"
MODEL_CUTOUT = "fal-ai/birefnet"

STYLE = ("cute chibi fantasy dragon, 16-bit pixel art game sprite, full body visible, side view facing right, "
         "thick dark outline, flat vivid colors, simple shapes, centered, plain solid magenta #FF00FF background, "
         "no ground, no shadow, no text")
KEEP = ("Keep exactly the same dragon character, same colors, same proportions, same pixel art style, "
        "same plain solid magenta background, full body visible, no shadow, no text.")

# --------------------------------------------------------------------------- stades
# (stade, stade source pour l'édition ou None = texte seul, description)
STAGE_REFS = [
    ("baby", None, "a tiny round baby dragon, green scales, cream belly, big shiny eyes, tiny stubby wings, "
                   "short tail, two little horn nubs, very cute"),
    ("child", "baby", "Make this baby dragon grow into a young child dragon: slightly bigger and taller, "
                      "bigger wings, small horns, longer tail, still cute."),
    ("teen", "child", "Make this dragon grow into a teenage dragon: change the scales to teal blue-green, "
                      "body much slimmer and taller with a long neck, longer swept-back horns, bigger wings, "
                      "spiky back ridge, confident smirk."),
    ("adult_good", "teen", "Make this dragon grow into a majestic adult dragon: change the scales to bright "
                           "emerald green with shiny golden belly plates, large golden crown-like horns, huge "
                           "golden-edged wings, muscular tall body, proud happy expression."),
    ("adult_mid", "teen", "Make this dragon grow into an ordinary adult dragon: change the scales to "
                          "orange-brown, chubby round body with a big belly, short stubby wings, blunt short "
                          "horns, sleepy relaxed expression."),
    ("adult_bad", "teen", "Make this dragon grow into a grumpy neglected adult dragon: dark purple and black "
                          "scales, many sharp spikes, torn wings, red eyes, scowling expression."),
    ("senior", "adult_good", "Make this dragon very old: grey faded scales, long white beard and eyebrows, "
                             "droopy wings, slightly hunched, kind tired eyes."),
    ("ghost", "baby", "Turn this dragon into a translucent pale blue ghost spirit of a dragon floating in the "
                      "air, wispy tail instead of legs, glowing golden halo above its head, peaceful closed eyes."),
    ("egg", "baby", "Replace the dragon with a single large dragon egg standing upright: oval egg with green "
                    "scale pattern and golden spots in the same colors as the dragon, no dragon visible."),
]

# Taille maximale (pixels) du sprite dans la case 32x32 : la créature grandit.
STAGE_SIZE = {"egg": 24, "baby": 22, "child": 26, "teen": 29, "adult_good": 31, "adult_mid": 31,
              "adult_bad": 31, "senior": 29, "ghost": 28}

# --------------------------------------------------------------------------- poses
# Pour chaque pose : liste d'images. "gen:<instruction>" = édition Fal,
# "same:<i>" = copie de l'image i, "bob:<i>" = image i décalée d'1 px vers le haut,
# "squash:<i>" = image i légèrement écrasée, "up:<i>:<px>" = image i montée de px,
# "fade:<i>:<px>" = montée + estompée.
P = {
    "idle": ["gen:standing still, calm, gentle smile, looking forward", "bob:0"],
    "walk": ["gen:walking to the right, one foot lifted mid-step", "gen:walking to the right, the other foot lifted mid-step"],
    "blink": ["gen:standing still with both eyes closed, blinking, gentle smile"],
    "happy": ["gen:very happy, big open smile, arms raised", "bob:0"],
    "very_happy": ["gen:jumping in the air with joy, huge smile, wings spread, sparkles", "same:0"],
    "love": ["gen:blushing pink cheeks, eyes shaped like red hearts, adorable", "bob:0"],
    "sad": ["gen:sad, head down, droopy wings, teary sad eyes, frown", "same:0"],
    "cry": ["gen:crying loudly, big tears streaming down, open mouth wailing", "bob:0"],
    "angry": ["gen:angry, furrowed brows, puffed red cheeks, stomping foot, small smoke puff from nostrils", "bob:0"],
    "refuse": ["gen:shaking its head no, eyes closed, turning head away, refusing", "gen:shaking its head no, turned the other way, eyes closed, refusing"],
    "surprised": ["gen:surprised, wide round eyes, mouth open in an O shape"],
    "bored": ["gen:bored, half-closed eyes, flat mouth, sighing, slouching", "same:0"],
    "hungry": ["gen:hungry, holding its belly with both hands, drooling, pleading eyes", "bob:0"],
    "eat": ["gen:mouth wide open, about to take a big bite, eyes closed happily",
            "gen:chewing with mouth closed, cheeks full of food, happy closed eyes", "bob:1"],
    "full": ["gen:very full, round bloated belly, satisfied smile, patting its belly"],
    "sleepy": ["gen:sleepy, yawning with mouth open, heavy half-closed eyelids", "same:0"],
    "sleep": ["gen:sleeping curled up lying on the floor, eyes closed, tail wrapped around body", "squash:0"],
    "wake_up": ["gen:waking up and stretching, arms and wings stretched up, yawning", "bob:0"],
    "sick": ["gen:sick, pale greenish face, dizzy spiral eyes, shivering, sweat drop", "same:0"],
    "medicine": ["gen:grimacing after swallowing bitter medicine, tongue out, eyes squeezed shut", "bob:0"],
    "dirty": ["gen:dirty with mud stains, embarrassed, small flies buzzing around", "same:0"],
    "poop": ["gen:squatting low and straining, eyes squeezed shut, sweat drop, embarrassed", "squash:0"],
    "wash": ["gen:taking a bath with soap bubbles all over its body, eyes closed, happy", "bob:0"],
    "scolded": ["gen:being scolded, ashamed, head lowered, looking down, sweat drop", "same:0"],
    "call": ["gen:waving both arms excitedly to get attention, mouth open calling out", "bob:0"],
    "look_left": ["gen:turned to look towards the left side, head and eyes pointing left, curious"],
    "look_right": ["gen:turned to look towards the right side, head and eyes pointing right, curious"],
    "win": ["gen:celebrating victory, dancing, fist pumped up, huge grin, sparkles", "bob:0"],
    "lose": ["gen:disappointed after losing, slumped shoulders, single tear, sad frown", "same:0"],
    "evolve": ["gen:glowing bright white silhouette, the whole body pure white light, transformation glow"],
    "dying": ["gen:very weak and sick, collapsing to the ground, eyes half closed", "squash:0"],
    "dead": ["gen:lying flat on its back on the floor motionless, eyes drawn as X marks"],
    # oeuf
    "wobble": ["gen:the egg tilted to the left, wobbling", "gen:the egg tilted to the right, wobbling"],
    "crack": ["gen:the egg with a small crack at the top", "gen:the egg with several big cracks",
              "gen:the egg almost broken, many large cracks, a piece missing"],
    "hatch": ["gen:the egg broken open, the top shell flying off, a cute baby green dragon head peeking out",
              "up:0:2"],
    # esprit : monte et s'estompe
    "ascend": ["ref", "up:0:6", "fade:0:14"],
}
# "ref" = l'image de référence du stade, réduite telle quelle
STAGE_OVERRIDES = {
    "egg": {"idle": ["ref", "squash:0"]},
    "ghost": {"idle": ["ref", "up:0:2"]},
}


# --------------------------------------------------------------------------- API
class Fal:
    def __init__(self):
        key = os.environ.get("FAL_KEY", "proxy-injected")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Key {key}", "Content-Type": "application/json"})
        self.lock = threading.Lock()
        self.calls = 0

    def run(self, model, payload, tries=4):
        for i in range(tries):
            try:
                r = self.s.post(f"https://fal.run/{model}", data=json.dumps(payload), timeout=300)
                if r.status_code == 200:
                    with self.lock:
                        self.calls += 1
                    j = r.json()
                    return j["images"][0]["url"] if "images" in j else j["image"]["url"]
                msg = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (401, 403, 422):
                    raise RuntimeError(msg)
            except requests.RequestException as e:
                msg = str(e)
            time.sleep(2 ** (i + 1))
        raise RuntimeError(f"échec {model}: {msg}")

    def download(self, url, path):
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(r.content)


def load_refs():
    if os.path.exists(REFS_JSON):
        with open(REFS_JSON) as f:
            return json.load(f)
    return {}


def save_refs(refs):
    os.makedirs(RAW, exist_ok=True)
    with open(REFS_JSON, "w") as f:
        json.dump(refs, f, indent=1)


def gen_refs(fal, refs, only=None, force=False):
    for stage, src, desc in STAGE_REFS:
        if only and stage not in only and not (force and stage in only):
            continue
        path = os.path.join(RAW, stage, "_ref.png")
        if stage in refs and os.path.exists(path) and not force:
            continue
        if src is None:
            url = fal.run(MODEL_T2I, {"prompt": f"{desc}, {STYLE}", "image_size": "square_hd",
                                      "num_inference_steps": 32, "output_format": "png", "seed": 7})
        else:
            if src not in refs:
                raise SystemExit(f"référence {src} manquante pour {stage}")
            url = fal.run(MODEL_EDIT, {"prompt": f"{desc} Keep the same pixel art style, same plain solid magenta "
                                                 f"background, full body visible, no shadow, no text.",
                                       "image_url": refs[src], "output_format": "png", "seed": 7})
        fal.download(url, path)
        if os.path.exists(path[:-4] + "_cut.png"):
            os.remove(path[:-4] + "_cut.png")
        refs[stage] = url
        save_refs(refs)
        print(f"[ref] {stage}")


# --------------------------------------------------------------------------- post-traitement
def cutout(fal, raw_path):
    """Détourage par BiRefNet (Fal), mis en cache dans <image>_cut.png."""
    cut = raw_path[:-4] + "_cut.png"
    if os.path.exists(cut):
        return cut
    if fal is None:
        return None
    import base64
    with open(raw_path, "rb") as f:
        uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    url = fal.run(MODEL_CUTOUT, {"image_url": uri, "output_format": "png"})
    fal.download(url, cut)
    return cut


def remove_background(img, tol=60):
    """Rend transparent le fond connecté aux bords (couleur proche de celle des coins)."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))

    def near(c):
        return abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) < tol * 3 // 2

    def magentaish(c):  # teintes magenta/rose saturées : fond ou ombre portée
        r, g, b = c[0], c[1], c[2]
        return r > 120 and b > 60 and g < 0.6 * min(r, b) and abs(r - b) < 120

    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        c = px[x, y]
        if not (near(c) or magentaish(c)):
            continue
        px[x, y] = (0, 0, 0, 0)
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    # pixels isolés restés magenta (entre les pattes, etc.)
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c[3] and near(c):
                px[x, y] = (0, 0, 0, 0)
    return img


CUT_FAL = None  # client Fal utilisé pour le détourage (None = détourage local)


def to_sprite(raw_path, max_size):
    cut = cutout(CUT_FAL, raw_path)
    img = Image.open(cut).convert("RGBA") if cut else remove_background(Image.open(raw_path))
    bbox = img.getchannel("A").point(lambda a: 255 if a > 128 else 0).getbbox()
    if not bbox:
        raise RuntimeError(f"image vide après détourage : {raw_path}")
    img = img.crop(bbox)
    w, h = img.size
    k = max_size / max(w, h)
    nw, nh = max(1, round(w * k)), max(1, round(h * k))
    small = img.resize((nw, nh), Image.LANCZOS)
    # binarise l'alpha et réduit la palette
    alpha = small.getchannel("A").point(lambda a: 255 if a >= 110 else 0)
    rgb = small.convert("RGB").quantize(colors=16, method=Image.Quantize.MEDIANCUT).convert("RGB")
    out = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    sprite = rgb.convert("RGBA")
    sprite.putalpha(alpha)
    out.paste(sprite, ((32 - nw) // 2, 31 - nh + 1 if nh < 32 else 0), sprite)
    return out


def shift(img, dy, fade=1.0):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, -dy))
    if fade < 1.0:
        a = out.getchannel("A").point(lambda v: int(v * fade) if v * fade >= 110 else 0)
        out.putalpha(a)
    return out


def squash(img):
    bbox = img.getbbox()
    if not bbox:
        return img
    part = img.crop(bbox)
    w, h = part.size
    nh = max(1, h - max(1, h // 12))
    part = part.resize((w + 1, nh), Image.NEAREST)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(part, (bbox[0], bbox[3] - nh), part)
    return out


def frame_specs(stage, pose):
    return STAGE_OVERRIDES.get(stage, {}).get(pose, P[pose])


def build_pose(fal, refs, stage, pose, force=False, postprocess_only=False):
    """Génère (si besoin) puis écrit les images 32x32 d'une pose. Renvoie le nb d'appels Fal."""
    specs = frame_specs(stage, pose)
    frames = []
    for i, spec in enumerate(specs):
        kind, _, arg = spec.partition(":")
        if kind == "ref":
            frames.append(to_sprite(os.path.join(RAW, stage, "_ref.png"), STAGE_SIZE[stage]))
        elif kind == "gen":
            raw = os.path.join(RAW, stage, f"{pose}_{i + 1:02d}.png")
            if (force or not os.path.exists(raw)) and not postprocess_only:
                prompt = f"Same dragon character, now {arg}. {KEEP}"
                url = fal.run(MODEL_EDIT, {"prompt": prompt, "image_url": refs[stage], "output_format": "png",
                                           "seed": 11 + i})
                fal.download(url, raw)
                if os.path.exists(raw[:-4] + "_cut.png"):
                    os.remove(raw[:-4] + "_cut.png")
            if not os.path.exists(raw):
                return
            frames.append(to_sprite(raw, STAGE_SIZE[stage]))
        else:
            parts = arg.split(":")
            base = frames[int(parts[0])]
            if kind == "same":
                frames.append(base.copy())
            elif kind == "bob":
                frames.append(shift(base, 1))
            elif kind == "squash":
                frames.append(squash(base))
            elif kind == "up":
                frames.append(shift(base, int(parts[1])))
            elif kind == "fade":
                frames.append(shift(base, int(parts[1]), 0.55))
    d = os.path.join(OUT, stage)
    os.makedirs(d, exist_ok=True)
    # supprime d'anciennes images en trop
    i = len(frames) + 1
    while os.path.exists(os.path.join(d, f"{pose}_{i:02d}.png")):
        os.remove(os.path.join(d, f"{pose}_{i:02d}.png"))
        i += 1
    for i, f in enumerate(frames):
        f.save(os.path.join(d, f"{pose}_{i + 1:02d}.png"))


def contact_sheet(path, stages, scale=3, refs=False):
    rows = []
    for stage in stages:
        if refs:
            rows.append([to_sprite(os.path.join(RAW, stage, "_ref.png"), STAGE_SIZE[stage])])
            continue
        tiles = []
        for pose in M.poses_for_stage(stage):
            i = 1
            while os.path.exists(p := os.path.join(OUT, stage, f"{pose}_{i:02d}.png")):
                tiles.append(Image.open(p).convert("RGBA"))
                i += 1
        rows.append(tiles)
    cols = max(len(r) for r in rows) or 1
    sheet = Image.new("RGB", (cols * 34 * scale, len(rows) * 34 * scale), (40, 40, 50))
    for y, r in enumerate(rows):
        for x, t in enumerate(r):
            bg = Image.new("RGBA", (32, 32), (230, 230, 235, 255))
            bg.alpha_composite(t)
            sheet.paste(bg.resize((32 * scale, 32 * scale), Image.NEAREST), (x * 34 * scale, y * 34 * scale))
    sheet.save(path)
    print(f"planche : {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="append", help="limiter à ce(s) stade(s)")
    ap.add_argument("--pose", action="append", help="limiter à cette/ces pose(s)")
    ap.add_argument("--refs-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="régénérer même si déjà en cache")
    ap.add_argument("--force-refs", action="store_true", help="régénérer aussi les références des stades choisis")
    ap.add_argument("--postprocess-only", action="store_true", help="ne fait aucun appel Fal")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--sheet", default=os.path.join(ROOT, "docs", "sprites_preview.png"))
    a = ap.parse_args()

    global CUT_FAL
    fal = Fal()
    CUT_FAL = fal
    refs = load_refs()
    stages = a.stage or [s for s, _ in M.STAGES]
    if not a.postprocess_only:
        gen_refs(fal, refs, only=a.stage, force=a.force_refs)
    if a.refs_only:
        contact_sheet(os.path.join(RAW, "refs_sheet.png"), stages, scale=4, refs=True)
        print(f"{fal.calls} appels Fal")
        return

    jobs = [(s, p) for s in stages for p in M.poses_for_stage(s) if not a.pose or p in a.pose]
    errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(build_pose, fal, refs, s, p, a.force, a.postprocess_only): (s, p) for s, p in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            s, p = futs[f]
            try:
                f.result()
                print(f"[{n}/{len(jobs)}] {s}/{p}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{s}/{p}: {e}")
                print(f"[{n}/{len(jobs)}] ERREUR {s}/{p}: {e}")
    print(f"{fal.calls} appels Fal, {len(errors)} erreur(s)")
    if not a.pose and not a.stage:
        contact_sheet(a.sheet, [s for s, _ in M.STAGES])
    for e in errors:
        print("  " + e)


if __name__ == "__main__":
    main()
