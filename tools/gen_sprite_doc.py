#!/usr/bin/env python3
"""Génère docs/SPRITES.md (liste exhaustive des sprites) depuis sprite_manifest.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprite_manifest as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INTRO = """# Sprites à dessiner

> Fichier généré par `tools/gen_sprite_doc.py` à partir de `tools/sprite_manifest.py`.

Les sprites du **dragon** (`assets/sprites/`, aperçu ci-dessous) ont été générés avec Fal par
`tools/fal_dragons.py`, les **objets** par `tools/fal_items.py` (aperçu : `items_planche.png`).
Les bulles, icônes, interface et effets utilisent les **sprites provisoires** de `assets/placeholders/`.
Chaque PNG déposé dans `assets/sprites/` (même nom, même dossier) **remplace** le provisoire ou le
dragon à la compilation suivante. Tu peux retoucher ou livrer petit à petit.

![Aperçu des sprites du dragon](sprites_preview.png)

## Règles de dessin

| Règle | Valeur |
|---|---|
| Format | PNG |
| Taille créature | **32 x 32** (affichée x3 = 96 x 96 à l'écran 240 x 135) |
| Placement | créature centrée, **pieds sur les lignes 29-31** (le sol) |
| Transparence | canal alpha, ou magenta pur `#FF00FF` |
| Palette | 16 couleurs max conseillé, contour sombre de 1 px |
| Orientation | tournée vers la **droite** (la gauche = miroir automatique) |
| Animation | 1 à 4 images, `_01`, `_02`... (le nombre est libre) |
| Nommage | `assets/sprites/<dossier>/<nom>_NN.png`, ex. `assets/sprites/baby/eat_01.png` |

**Repli automatique** : si une pose manque pour un stade où tu as déjà dessiné quelque chose,
le jeu utilise la pose de repli indiquée (puis `idle`) **de tes dessins**. Si un stade n'a aucun
de tes dessins, ce sont les provisoires qui s'affichent.

Priorités : **P1** indispensable, **P2** recommandé, **P3** bonus.
Conseil : commence par `baby` en complet, puis les autres stades en P1.
"""


def fname(name, n):
    return f"`{name}_01.png`" if n == 1 else f"`{name}_01..{n:02d}.png`"


def main():
    out = [INTRO]
    out.append("## 1. Stades de vie (un dossier par stade)\n")
    out.append("| Dossier | Stade | Poses à dessiner |\n|---|---|---|")
    for s, desc in M.STAGES:
        n = len(M.poses_for_stage(s))
        out.append(f"| `{s}` | {desc} | {n} poses |")
    out.append("")

    living = [p for p in M.POSES if p[0] in M.LIVING_POSES]
    tot = sum(p[1] for p in living)
    p1 = [p for p in living if p[3] == "P1"]
    out.append("## 2. Poses et émotions de la créature\n")
    out.append("À dessiner pour **chaque** stade vivant : `baby`, `child`, `teen`, `adult_good`, "
               "`adult_mid`, `adult_bad`, `senior`.\n")
    out.append("| # | Fichier | Images | Prio | Repli si absent | Description |\n|---|---|---|---|---|---|")
    for i, (name, n, fb, prio, desc) in enumerate(living, 1):
        fbs = (fb or "—").replace("mirror:", "miroir de ")
        out.append(f"| {i} | {fname(name, n)} | {n} | {prio} | {fbs} | {desc} |")
    out.append("")
    out.append(f"Par stade : **{len(p1)} poses P1 ({sum(p[1] for p in p1)} images)**, "
               f"{len(living)} poses en tout ({tot} images).  ")
    out.append(f"Pour les 7 stades vivants : {7 * sum(p[1] for p in p1)} images en P1, {7 * tot} images au complet.\n")

    for stage, title in (("egg", "Oeuf (`egg/`)"), ("ghost", "Esprit (`ghost/`)")):
        out.append(f"## 3. {title}\n" if stage == "egg" else f"## 4. {title}\n")
        out.append("| Fichier | Images | Description |\n|---|---|---|")
        for name in M.poses_for_stage(stage):
            p = next(x for x in M.POSES if x[0] == name)
            desc = p[4] if stage != "egg" or name != "idle" else "Se dandine doucement"
            if stage == "ghost" and name == "idle":
                desc = "Flotte avec une auréole"
            out.append(f"| {fname(name, p[1])} | {p[1]} | {desc} |")
        out.append("")

    groups = [("emotes", "5. Bulles d'émotion (`emotes/`)", "Affichées au-dessus de la tête, agrandies x2."),
              ("items", "6. Objets (`items/`)", "Agrandis x2."),
              ("icons", "7. Icônes du menu (`icons/`)", "Barre du haut, taille réelle. Version normale + `_sel` (sélectionnée)."),
              ("ui", "8. Interface (`ui/`)", ""),
              ("fx", "9. Effets (`fx/`)", "")]
    for g, title, note in groups:
        out.append(f"## {title}\n")
        if note:
            out.append(note + "\n")
        out.append("| Fichier | Taille | Images | Usage |\n|---|---|---|---|")
        for grp, name, w, h, n, desc in M.OTHER:
            if grp == g:
                out.append(f"| {fname(name, n)} | {w}x{h} | {n} | {desc} |")
        out.append("")

    out.append("## 10. Fonds optionnels (`bg/`)\n")
    out.append("Sans fichier, un fond uni est dessiné. Un fond = 64 Ko de mémoire flash.\n")
    out.append("| Fichier | Taille | Usage |\n|---|---|---|")
    for name, w, h, desc in M.BACKGROUNDS:
        out.append(f"| `{name}.png` (pas de numéro) | {w}x{h} | {desc} |")
    out.append("")

    n_other = sum(x[4] for x in M.OTHER)
    out.append("## Récapitulatif\n")
    out.append(f"- Créature : {len(living)} poses x 7 stades + oeuf ({sum(next(p[1] for p in M.POSES if p[0]==x) for x in M.EGG_POSES)} images) "
               f"+ esprit ({sum(next(p[1] for p in M.POSES if p[0]==x) for x in M.GHOST_POSES)} images)")
    out.append(f"- Autres sprites (bulles, objets, icônes, interface, effets) : {n_other} images")
    out.append(f"- Fonds optionnels : {len(M.BACKGROUNDS)}")
    out.append("")
    out.append("Après avoir ajouté des PNG : `pio run -t upload` (la conversion est automatique). "
               "Pour régénérer l'aperçu : `python3 tools/make_placeholders.py --sheet docs/sprites_preview.png`.\n")

    with open(os.path.join(ROOT, "docs", "SPRITES.md"), "w") as f:
        f.write("\n".join(out))
    print("docs/SPRITES.md écrit")


if __name__ == "__main__":
    main()
