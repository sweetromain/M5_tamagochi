"""Source unique de vérité : liste exhaustive des sprites du jeu.

Utilisé par :
  - tools/make_placeholders.py  (génère les sprites provisoires)
  - tools/png2rgb565.py          (convertit les PNG en code C++)
  - tools/gen_sprite_doc.py      (génère la liste des sprites dans docs/SPRITES.md)

NE PAS changer l'ordre des listes sans regénérer (les identifiants C++ en dépendent).
"""

TRANSPARENT_RGB = (255, 0, 255)  # magenta = transparent

CREATURE_SIZE = (32, 32)

# (dossier, description)
STAGES = [
    ("egg", "Oeuf"),
    ("baby", "Bébé"),
    ("child", "Enfant"),
    ("teen", "Ado"),
    ("adult_good", "Adulte bien soigné"),
    ("adult_mid", "Adulte soins moyens"),
    ("adult_bad", "Adulte négligé"),
    ("senior", "Vieux"),
    ("ghost", "Esprit (après la mort)"),
]

# (nom, nb images conseillé, repli, priorité, description)
# Repli : pose utilisée si celle-ci n'est pas dessinée pour ce stade.
#         "mirror:<pose>" = image miroir de cette pose.
POSES = [
    ("idle",       2, None,           "P1", "Respire / se balance légèrement"),
    ("walk",       2, "idle",         "P1", "Marche vers la droite (la gauche = miroir automatique)"),
    ("blink",      1, "idle",         "P2", "Yeux fermés, une image (clignement)"),
    ("happy",      2, "idle",         "P1", "Sourire, bras levés"),
    ("very_happy", 2, "happy",        "P2", "Saut de joie (en l'air puis atterrissage)"),
    ("love",       2, "happy",        "P2", "Yeux en coeur / rougit (caresse)"),
    ("sad",        2, "idle",         "P1", "Tête basse, yeux tristes"),
    ("cry",        2, "sad",          "P2", "Pleure (larmes)"),
    ("angry",      2, "sad",          "P1", "Fâché, joues gonflées, tape du pied"),
    ("refuse",     2, "angry",        "P1", "Secoue la tête « non » (refuse de manger / jouer)"),
    ("surprised",  1, "idle",         "P2", "Yeux ronds, bouche en O"),
    ("bored",      2, "sad",          "P3", "S'ennuie, regard vide, soupire"),
    ("hungry",     2, "sad",          "P1", "Se tient le ventre, bave"),
    ("eat",        3, "happy",        "P1", "Bouche ouverte -> mâche -> mâche"),
    ("full",       1, "happy",        "P3", "Ventre rond, satisfait"),
    ("sleepy",     2, "idle",         "P2", "Bâille, paupières lourdes"),
    ("sleep",      2, "idle",         "P1", "Dort couché, respiration"),
    ("wake_up",    2, "idle",         "P3", "S'étire en se réveillant"),
    ("sick",       2, "sad",          "P1", "Teint verdâtre, frissons"),
    ("medicine",   2, "refuse",       "P2", "Grimace en avalant le médicament"),
    ("dirty",      2, "sad",          "P2", "Gêné par la saleté / l'odeur"),
    ("poop",       2, "idle",         "P1", "Accroupi, fait caca"),
    ("wash",       2, "happy",        "P2", "Sous la douche, yeux fermés"),
    ("scolded",    2, "sad",          "P1", "Se fait gronder, penaud"),
    ("call",       2, "idle",         "P1", "S'agite pour attirer l'attention"),
    ("look_left",  1, "idle",         "P1", "Regarde à gauche (mini-jeu)"),
    ("look_right", 1, "mirror:look_left", "P1", "Regarde à droite (mini-jeu), miroir de look_left si absent"),
    ("win",        2, "very_happy",   "P1", "Victoire au mini-jeu (danse)"),
    ("lose",       2, "sad",          "P1", "Défaite (déçu)"),
    ("evolve",     1, "idle",         "P2", "Silhouette blanche (flash de transformation)"),
    ("dying",      2, "sick",         "P1", "S'affaiblit, s'effondre"),
    ("dead",       1, "sleep",        "P1", "Allongé, yeux en X"),
    # Poses spécifiques à l'oeuf et à l'esprit
    ("wobble",     2, "idle",         "P1", "(oeuf) tremble fort, éclosion proche"),
    ("crack",      3, "wobble",       "P1", "(oeuf) fissures de plus en plus grandes"),
    ("hatch",      2, "crack",        "P1", "(oeuf) la coquille éclate"),
    ("ascend",     3, "idle",         "P1", "(esprit) monte vers le ciel et disparaît"),
]

EGG_POSES = ["idle", "wobble", "crack", "hatch"]
GHOST_POSES = ["idle", "ascend"]
LIVING_POSES = [p[0] for p in POSES if p[0] not in ("wobble", "crack", "hatch", "ascend")]


def poses_for_stage(stage):
    if stage == "egg":
        return EGG_POSES
    if stage == "ghost":
        return GHOST_POSES
    return LIVING_POSES


# Sprites hors créature : (groupe, nom, largeur, hauteur, nb images, description)
OTHER = [
    # Bulles d'émotion affichées au-dessus de la tête
    ("emotes", "heart",        16, 16, 2, "Content / caresse"),
    ("emotes", "broken_heart", 16, 16, 1, "Triste, joie à zéro"),
    ("emotes", "anger",        16, 16, 2, "Veine de colère"),
    ("emotes", "sweat",        16, 16, 1, "Gêne, effort, se fait gronder"),
    ("emotes", "tear",         16, 16, 2, "Pleure"),
    ("emotes", "exclaim",      16, 16, 1, "« ! » besoin d'attention"),
    ("emotes", "question",     16, 16, 1, "« ? » mini-jeu"),
    ("emotes", "zzz",          16, 16, 3, "Dort"),
    ("emotes", "note",         16, 16, 2, "Joyeux / chante"),
    ("emotes", "skull",        16, 16, 2, "Malade"),
    ("emotes", "stink",        16, 16, 2, "Odeur autour des cacas"),
    ("emotes", "food_bubble",  16, 16, 1, "Pense à la nourriture (faim)"),
    ("emotes", "star",         16, 16, 2, "Victoire"),
    # Objets
    ("items", "meal",      16, 16, 4, "Repas : entier -> 3/4 -> 1/2 -> miettes"),
    ("items", "snack",     16, 16, 4, "Friandise : entière -> ... -> miettes"),
    ("items", "pill",      16, 16, 1, "Médicament"),
    ("items", "poop",      16, 16, 2, "Caca (frémit)"),
    ("items", "shower",    32, 32, 2, "Pommeau de douche + gouttes"),
    ("items", "ball",      16, 16, 2, "Balle (écran du mini-jeu)"),
    ("items", "tombstone", 32, 32, 1, "Pierre tombale"),
    ("items", "bed",       32, 16, 1, "Lit sous la créature qui dort (bonus)"),
    # Icônes de menu (normal + sélectionné)
    ("icons", "food",           16, 16, 1, "Menu manger"),
    ("icons", "food_sel",       16, 16, 1, "Menu manger (sélectionné)"),
    ("icons", "play",           16, 16, 1, "Menu jouer"),
    ("icons", "play_sel",       16, 16, 1, "Menu jouer (sélectionné)"),
    ("icons", "clean",          16, 16, 1, "Menu nettoyer"),
    ("icons", "clean_sel",      16, 16, 1, "Menu nettoyer (sélectionné)"),
    ("icons", "medicine",       16, 16, 1, "Menu soigner"),
    ("icons", "medicine_sel",   16, 16, 1, "Menu soigner (sélectionné)"),
    ("icons", "light",          16, 16, 1, "Menu lumière"),
    ("icons", "light_sel",      16, 16, 1, "Menu lumière (sélectionné)"),
    ("icons", "discipline",     16, 16, 1, "Menu gronder"),
    ("icons", "discipline_sel", 16, 16, 1, "Menu gronder (sélectionné)"),
    ("icons", "stats",          16, 16, 1, "Menu statistiques"),
    ("icons", "stats_sel",      16, 16, 1, "Menu statistiques (sélectionné)"),
    ("icons", "settings",       16, 16, 1, "Menu réglages"),
    ("icons", "settings_sel",   16, 16, 1, "Menu réglages (sélectionné)"),
    ("icons", "attention",      16, 16, 2, "Alerte « appel » (clignote)"),
    # Interface
    ("ui", "heart_full",  8, 8, 1, "Jauge : coeur plein"),
    ("ui", "heart_empty", 8, 8, 1, "Jauge : coeur vide"),
    ("ui", "battery",    12, 8, 5, "Batterie : 0 à 4 barres (5 images)"),
    ("ui", "sound_on",    8, 8, 1, "Son activé"),
    ("ui", "sound_off",   8, 8, 1, "Son coupé"),
    ("ui", "arrow_left",  8, 8, 1, "Flèche gauche"),
    ("ui", "arrow_right", 8, 8, 1, "Flèche droite"),
    ("ui", "cursor",      8, 8, 1, "Curseur de menu"),
    ("ui", "scale",      16, 16, 1, "Icône poids"),
    ("ui", "cake",       16, 16, 1, "Icône âge"),
    # Effets
    ("fx", "sparkle",    32, 32, 3, "Étincelles d'évolution"),
]

# Fonds optionnels (pas de provisoire : fond dessiné en code si absent)
BACKGROUNDS = [
    ("day",   240, 135, "Fond de jour"),
    ("night", 240, 135, "Fond de nuit (lumière éteinte)"),
    ("sick",  240, 135, "Fond teinté quand malade"),
    ("game",  240, 135, "Fond du mini-jeu"),
    ("title", 240, 135, "Écran titre avec logo"),
]
