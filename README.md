# M5 Tamagochi

Un jeu de créature virtuelle (genre « virtual pet ») pour le **M5StickC Plus2**.
On fait éclore un oeuf, on nourrit, lave, soigne, éduque et fait jouer la créature, qui grandit
et évolue selon la qualité des soins : bébé → enfant → ado → adulte (3 formes) → vieux.

## Compiler et flasher

Il faut [PlatformIO](https://platformio.org/) (extension VS Code ou `pip install platformio`).

```bash
pio run -e m5stick-c-plus2 -t upload
```

Avant chaque compilation, `tools/pio_prebuild.py` convertit automatiquement les PNG en code C++
(il installe Pillow si besoin).

Tests de la logique sur PC :

```bash
pio test -e native
```

## Commandes

| Bouton | Action |
|---|---|
| **A** (gros bouton en façade) | Valider ; sans icône sélectionnée : caresser |
| **B** (bouton du côté droit) | Icône / élément suivant |
| **PWR** (côté gauche), appui court | Retour / désélectionner |
| Secouer le Stick | Caresser |

L'écran s'éteint après 30 s ; un appui le rallume. Il se rallume tout seul quand la créature appelle.

### Menu (barre du haut)

| Icône | Rôle |
|---|---|
| Manger | Repas (faim +1, poids +1) ou friandise (joie +1, poids +2 ; trop = malade) |
| Jouer | Mini-jeu : devine de quel côté elle va regarder (A = gauche, B = droite), 3 sur 5 pour gagner |
| Nettoyer | Enlève les cacas (4 cacas = malade) |
| Soigner | Médicament, 1 ou 2 doses |
| Lumière | Éteindre quand elle dort, sinon erreur de soin |
| Gronder | Pendant un caprice (« ! » sans besoin réel, ou refus) : discipline +25 %. Sans raison : elle est triste |
| Stats | Âge, poids, faim, joie, énergie, discipline, heure, batterie |
| Réglages | Son, vitesse du temps (x1, x10, x60 pour tester), luminosité, heure, nouvel oeuf |

### Règles

- **Durées** (vitesse x1) : oeuf 1 min, bébé 1 h, enfant 1 jour, ado 2 jours, adulte 5 jours, vieux 2 à 4 jours.
- Un besoin (faim ou joie à zéro, lumière allumée la nuit) ignoré **15 min** = une **erreur de soin**.
- À l'âge adulte : peu d'erreurs et bonne discipline → `adult_good`, sinon `adult_mid` ou `adult_bad`.
- **Mort** : faim à zéro pendant 12 h, maladie non soignée pendant 6 h, ou vieillesse.
- Le temps continue quand le Stick est éteint (horloge RTC) : au rallumage, le temps écoulé est rattrapé (7 jours max).
- Sauvegarde automatique en mémoire flash.

## Sprites

La créature est un **dragon** : ses sprites (`assets/sprites/`) ont été générés avec l'API
[Fal](https://fal.ai) par `tools/fal_dragons.py`. Les bulles, objets, icônes et éléments d'interface
sont des **sprites provisoires** dessinés par `tools/make_placeholders.py`.
La **liste exhaustive** des sprites à dessiner, avec tailles, nombre d'images, priorités et
conventions de nommage, est dans **[docs/SPRITES.md](docs/SPRITES.md)**.

Pour remplacer un provisoire, dépose ton PNG dans `assets/sprites/` avec le même chemin,
par exemple `assets/sprites/baby/idle_01.png`, puis recompile.

### Régénérer les dragons avec Fal

```bash
export FAL_KEY=ta_cle_fal
python3 tools/fal_dragons.py --refs-only     # 1 référence par stade + planche assets/fal_raw/refs_sheet.png
python3 tools/fal_dragons.py                 # toutes les poses (~230 éditions + détourages, ~10 $)
python3 tools/fal_dragons.py --stage baby --pose eat --force   # refaire une pose ratée
```

Méthode : le bébé est généré par texte (FLUX dev), chaque stade suivant est obtenu en éditant le
précédent (FLUX Kontext), puis chaque pose en éditant la référence du stade : c'est toujours le
même dragon. Le fond est détouré par BiRefNet, puis l'image est réduite en 32x32 et 16 couleurs.
Les images brutes sont en cache dans `assets/fal_raw/` (non versionné) : relancer ne recoûte rien.

## Organisation du code

| Fichier | Rôle |
|---|---|
| `src/Pet.*` | Logique pure : stats, vieillissement, évolution, maladie, mort (testée dans `test/`) |
| `src/Animator.*` | Choix de la pose, de la bulle d'émotion et du déplacement |
| `src/Renderer.*` | Dessin (double buffer `M5Canvas`, sprites agrandis, transparence, miroir) |
| `src/Sound.*` | Mélodies non bloquantes sur le buzzer |
| `src/main.cpp` | Écrans, boutons, mini-jeu, réglages, sauvegarde, horloge |
| `tools/sprite_manifest.py` | Liste de référence de tous les sprites |
| `tools/png2rgb565.py` | Conversion PNG → `src/generated/sprites_gen.*` |
| `tools/gen_sprite_doc.py` | Régénère `docs/SPRITES.md` |
| `tools/fal_dragons.py` | Génère les sprites du dragon avec l'API Fal |
