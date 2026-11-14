"""Constantes et catalogues officiels Ultima IV / xU4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Palette EGA 16 couleurs officielle d'Ultima IV (extraite de module/Ultima-IV/config.b)
EGA_PALETTE: List[Tuple[int, int, int]] = [
    (0, 0, 0),        # 0  Noir
    (0, 0, 170),      # 1  Bleu
    (0, 170, 0),      # 2  Vert
    (0, 170, 170),    # 3  Cyan
    (170, 0, 0),      # 4  Rouge
    (170, 0, 170),    # 5  Magenta
    (170, 85, 0),     # 6  Marron
    (170, 170, 170),  # 7  Gris clair
    (85, 85, 85),     # 8  Gris foncé
    (85, 85, 255),    # 9  Bleu vif
    (85, 255, 80),    # 10 Vert vif
    (85, 255, 255),   # 11 Cyan vif
    (255, 85, 85),    # 12 Rouge vif
    (255, 85, 255),   # 13 Magenta vif
    (255, 255, 85),   # 14 Jaune
    (255, 255, 255),  # 15 Blanc
]

TILE_CATEGORIES: List[str] = [
    "Toutes",
    "Terrain",
    "Eau & Ponts",
    "Lieux",
    "Murs & Sols",
    "Objets & Champs",
    "Classes & Alliés",
    "Citadins",
    "Alphabet",
    "Pirates & Mer",
    "Monstres",
]


@dataclass(frozen=True)
class TileInfo:
    id: int
    name: str
    label_fr: str
    category: str
    walkable: bool = True
    sailable: bool = False
    swimmable: bool = False
    opaque: bool = False
    frames: int = 1
    rule: str = "default"
    is_base: bool = False  # Tuile principale (frame 0) pour les listes compactes


def _build_tile_catalog() -> List[TileInfo]:
    tiles: List[TileInfo] = []

    def add(
        tid: int,
        name: str,
        label_fr: str,
        category: str,
        *,
        walkable: bool = True,
        sailable: bool = False,
        swimmable: bool = False,
        opaque: bool = False,
        frames: int = 1,
        rule: str = "default",
        is_base: bool = True,
    ) -> None:
        tiles.append(
            TileInfo(
                id=tid,
                name=name,
                label_fr=label_fr,
                category=category,
                walkable=walkable,
                sailable=sailable,
                swimmable=swimmable,
                opaque=opaque,
                frames=frames,
                rule=rule,
                is_base=is_base,
            )
        )

    # 0..15 : Terrains, eau, lieux
    add(0, "sea", "Haute mer", "Eau & Ponts", walkable=False, sailable=True, swimmable=True, rule="water")
    add(1, "water", "Eau profonde", "Eau & Ponts", walkable=False, sailable=True, swimmable=True, rule="water")
    add(2, "shallows", "Eaux peu profondes", "Eau & Ponts", walkable=False, swimmable=True, rule="shallows")
    add(3, "swamp", "Marais (poison)", "Terrain", rule="swamp")
    add(4, "grass", "Prairie", "Terrain", rule="grass")
    add(5, "brush", "Broussailles", "Terrain", rule="brush")
    add(6, "forest", "Forêt", "Terrain", opaque=True, rule="brush")
    add(7, "hills", "Collines", "Terrain", rule="hills")
    add(8, "mountains", "Montagnes", "Terrain", walkable=False, opaque=True, rule="mountains")
    add(9, "dungeon", "Entrée de Donjon", "Lieux")
    add(10, "city", "Cité", "Lieux")
    add(11, "castle", "Château", "Lieux")
    add(12, "town", "Village", "Lieux")
    add(13, "lcb_west", "Château L.B. (Ouest)", "Lieux", walkable=False, rule="lcb")
    add(14, "lcb_entrance", "Château L.B. (Entrée)", "Lieux", rule="lcb_entrance")
    add(15, "lcb_east", "Château L.B. (Est)", "Lieux", walkable=False, rule="lcb")

    # 16..19 : Navire (4 directions)
    for idx, suffix in enumerate(["Ouest", "Nord", "Est", "Sud"]):
        add(16 + idx, "ship", f"Navire ({suffix})", "Eau & Ponts", frames=4, rule="ship", is_base=(idx == 0))

    # 20..21 : Cheval (2 directions)
    add(20, "horse", "Cheval (Ouest)", "Classes & Alliés", frames=2, rule="horse", is_base=True)
    add(21, "horse", "Cheval (Est)", "Classes & Alliés", frames=2, rule="horse", is_base=False)

    # 22..31 : Sols, ponts, échelles, lieux spéciaux, Avatar
    add(22, "dungeon_floor", "Sol de donjon / carrelage", "Murs & Sols", rule="floors")
    add(23, "bridge", "Pont", "Eau & Ponts")
    add(24, "balloon", "Montgolfière", "Objets & Champs", rule="balloon")
    add(25, "bridge_n", "Pont (Nord)", "Eau & Ponts")
    add(26, "bridge_s", "Pont (Sud)", "Eau & Ponts")
    add(27, "up_ladder", "Échelle montante", "Lieux")
    add(28, "down_ladder", "Échelle descendante", "Lieux")
    add(29, "ruins", "Ruines", "Lieux")
    add(30, "shrine", "Sanctuaire", "Lieux")
    add(31, "avatar", "Avatar (Héros)", "Classes & Alliés", walkable=False, rule="person")

    # 32..47 : 8 classes (2 frames chacune)
    classes = [
        ("mage", "Mage"),
        ("bard", "Barde"),
        ("fighter", "Combattant"),
        ("druid", "Druide"),
        ("tinker", "Bricoleur"),
        ("paladin", "Paladin"),
        ("ranger", "Rôdeur"),
        ("shepherd", "Berger"),
    ]
    for i, (cname, cfr) in enumerate(classes):
        tid = 32 + i * 2
        add(tid, cname, f"{cfr} (1)", "Classes & Alliés", walkable=False, frames=2, rule="person", is_base=True)
        add(tid + 1, cname, f"{cfr} (2)", "Classes & Alliés", walkable=False, frames=2, rule="person", is_base=False)

    # 48..63 : Architecture, navire, obstacles, sols
    add(48, "column", "Colonne", "Murs & Sols", walkable=False, rule="solid")
    add(49, "waterside_sw", "Bord d'eau SO", "Eau & Ponts", walkable=False, rule="solid_attackover")
    add(50, "waterside_se", "Bord d'eau SE", "Eau & Ponts", walkable=False, rule="solid_attackover")
    add(51, "waterside_nw", "Bord d'eau NO", "Eau & Ponts", walkable=False, rule="solid_attackover")
    add(52, "waterside_ne", "Bord d'eau NE", "Eau & Ponts", walkable=False, rule="solid_attackover")
    add(53, "shipmast", "Mât de navire", "Eau & Ponts", walkable=False, rule="solid")
    add(54, "shipwheel", "Gouvernail", "Eau & Ponts", walkable=False, rule="solid")
    add(55, "rocks", "Rochers", "Terrain", walkable=False, rule="solid")
    add(56, "corpse", "Corps allongé", "Objets & Champs", walkable=False, rule="solid")
    add(57, "stone_wall", "Mur de pierre", "Murs & Sols", walkable=False, opaque=False, rule="walls")
    add(58, "locked_door", "Porte verrouillée", "Murs & Sols", walkable=False, rule="locked_door")
    add(59, "door", "Porte déverrouillée", "Murs & Sols", walkable=False, rule="door")
    add(60, "chest", "Coffre au trésor", "Objets & Champs", rule="chest")
    add(61, "ankh", "Ankh sacré", "Objets & Champs", walkable=False, rule="solid")
    add(62, "brick_floor", "Sol en brique", "Murs & Sols", rule="floors")
    add(63, "wood_floor", "Plancher en bois", "Murs & Sols", rule="floors")

    # 64..79 : Moongates, champs magiques, objets, effets
    for i in range(3):
        add(64 + i, "moongate_opening", f"Moongate (ouverture {i+1})", "Objets & Champs", walkable=False, frames=3, rule="solid", is_base=(i == 0))
    add(67, "moongate", "Moongate ouverte", "Objets & Champs")
    add(68, "poison_field", "Champ de poison", "Objets & Champs", rule="poison_field")
    add(69, "energy_field", "Champ d'énergie", "Objets & Champs", walkable=False, rule="energy_field")
    add(70, "fire_field", "Champ de feu", "Objets & Champs", rule="fire_field")
    add(71, "sleep_field", "Champ de sommeil", "Objets & Champs", rule="sleep_field")
    add(72, "solid", "Barrière solide", "Murs & Sols", walkable=False, rule="solid_attackover")
    add(73, "secret_door", "Passage secret", "Murs & Sols", opaque=True, rule="secret_door")
    add(74, "altar", "Autel", "Objets & Champs")
    add(75, "campfire", "Feu de camp / Brasero", "Objets & Champs", walkable=False, rule="solid")
    add(76, "lava", "Coulée de lave", "Terrain", rule="lava")
    add(77, "miss_flash", "Projectile (manqué)", "Objets & Champs", is_base=False)
    add(78, "magic_flash", "Sphère magique", "Objets & Champs")
    add(79, "hit_flash", "Impact d'attaque", "Objets & Champs", is_base=False)

    # 80..95 : Citadins et PNJ de ville (2 frames chacun)
    townfolk = [
        ("guard", "Garde"),
        ("villager", "Citoyen / Marchand"),
        ("bard_singing", "Barde chanteur"),
        ("jester", "Bouffon"),
        ("beggar", "Mendiant"),
        ("child", "Enfant"),
        ("bull", "Taureau"),
        ("lord_british", "Lord British"),
    ]
    for i, (tname, tfr) in enumerate(townfolk):
        tid = 80 + i * 2
        add(tid, tname, f"{tfr} (1)", "Citadins", walkable=False, frames=2, rule="person", is_base=True)
        add(tid + 1, tname, f"{tfr} (2)", "Citadins", walkable=False, frames=2, rule="person", is_base=False)

    # 96..121 : Lettres A..Z (enseignes de magasins)
    for i in range(26):
        ch = chr(ord("A") + i)
        add(96 + i, ch, f"Enseigne « {ch} »", "Alphabet", walkable=False, rule="signs")

    # 122..127 : Espacements et mur de brique opaque
    add(122, "space", "Enseigne (espace)", "Alphabet", walkable=False, rule="signs")
    add(123, "space_r", "Bordure droite", "Alphabet", walkable=False, rule="spacers")
    add(124, "space_l", "Bordure gauche", "Alphabet", walkable=False, rule="spacers")
    add(125, "window", "Fenêtre / Comptoir", "Murs & Sols", walkable=False, rule="spacers")
    add(126, "black", "Vide noir", "Murs & Sols", walkable=False, rule="spacers")
    add(127, "brick_wall", "Mur de brique (opaque)", "Murs & Sols", walkable=False, opaque=True, rule="walls")

    # 128..131 : Navire pirate (4 directions)
    for idx, suffix in enumerate(["Ouest", "Nord", "Est", "Sud"]):
        add(128 + idx, "pirate_ship", f"Navire pirate ({suffix})", "Pirates & Mer", walkable=False, frames=4, rule="monster", is_base=(idx == 0))

    # 132..143 : Créatures marines & forces naturelles (2 frames chacune)
    sea_creatures = [
        ("nixie", "Nixe"),
        ("giant_squid", "Calmar géant"),
        ("sea_serpent", "Serpent de mer"),
        ("sea_horse", "Hippocampe géant"),
        ("whirlpool", "Tourbillon (Maelström)"),
        ("twister", "Tornade"),
    ]
    for i, (sname, sfr) in enumerate(sea_creatures):
        tid = 132 + i * 2
        rule = "water" if sname == "whirlpool" else ("default" if sname == "twister" else "monster")
        add(tid, sname, f"{sfr} (1)", "Pirates & Mer", walkable=False, frames=2, rule=rule, is_base=True)
        add(tid + 1, sname, f"{sfr} (2)", "Pirates & Mer", walkable=False, frames=2, rule=rule, is_base=False)

    # 144..255 : 28 monstres terrestres/donjons (4 frames chacun)
    monsters = [
        ("rat", "Rat géant"),
        ("bat", "Chauve-souris"),
        ("spider", "Araignée géante"),
        ("ghost", "Fantôme"),
        ("slime", "Gelée (Slime)"),
        ("troll", "Troll"),
        ("gremlin", "Gremlin"),
        ("mimic", "Mimique"),
        ("reaper", "Faucheur (Reaper)"),
        ("insect_swarm", "Nuée d'insectes"),
        ("gazer", "Tyrannœil (Gazer)"),
        ("phantom", "Spectre (Phantom)"),
        ("orc", "Orque"),
        ("skeleton", "Squelette"),
        ("rogue", "Brigand"),
        ("python", "Python"),
        ("ettin", "Ettin (Bicéphale)"),
        ("headless", "Sans-tête (Headless)"),
        ("cyclops", "Cyclope"),
        ("wisp", "Feu follet (Wisp)"),
        ("evil_mage", "Mage noir"),
        ("liche", "Liche"),
        ("lava_lizard", "Lézard de lave"),
        ("zorn", "Zorn"),
        ("daemon", "Démon"),
        ("hydra", "Hydre"),
        ("dragon", "Dragon"),
        ("balron", "Balron"),
    ]
    for i, (mname, mfr) in enumerate(monsters):
        base = 144 + i * 4
        for f in range(4):
            add(
                base + f,
                mname,
                f"{mfr}" if f == 0 else f"{mfr} ({f+1})",
                "Monstres",
                walkable=False,
                frames=4,
                rule="monster",
                is_base=(f == 0),
            )

    assert len(tiles) == 256, f"Expected 256 tiles, got {len(tiles)}"
    return tiles


TILES: List[TileInfo] = _build_tile_catalog()
TILES_BY_ID: Dict[int, TileInfo] = {t.id: t for t in TILES}
BASE_TILES: List[TileInfo] = [t for t in TILES if t.is_base]

# Tuiles principales pour les PNJ dans les villes
NPC_SPRITE_IDS: List[int] = [
    31, 32, 34, 36, 38, 40, 42, 44, 46,
    80, 82, 84, 86, 88, 90, 92, 94,
    61, 75, 156, 188,
]

# Comportements PNJ (.ULT offset 0x4C0)
NPC_MOVEMENTS: Dict[int, Tuple[str, str]] = {
    0x00: ("fixed", "Fixe (ne bouge pas)"),
    0x01: ("wander", "Errant (se déplace librement)"),
    0x80: ("follow", "Suit l'Avatar"),
    0xFF: ("attack", "Hostile (attaque l'Avatar)"),
}

MOVEMENT_TO_ULT_BYTE: Dict[str, int] = {
    "fixed": 0x00,
    "wander": 0x01,
    "follow": 0x80,
    "attack": 0xFF,
}
ULT_BYTE_TO_MOVEMENT: Dict[int, str] = {v: k for k, v in MOVEMENT_TO_ULT_BYTE.items()}

# Rôles PNJ supportés par xU4 (tools/pack-xu4.b npc-roles & src/person.h)
NPC_ROLES: List[Tuple[str, str]] = [
    ("none", "Habitant / Dialogue libre (.TLK)"),
    ("companion", "Compagnon recrutable (JOIN)"),
    ("weaponsvendor", "Marchand d'armes"),
    ("armorvendor", "Armurier"),
    ("foodvendor", "Épicier (Nourriture)"),
    ("tavernkeeper", "Tavernier (Rumeurs & Bière)"),
    ("reagentsvendor", "Herboriste (Réactifs magiques)"),
    ("healer", "Guérisseur"),
    ("innkeeper", "Aubergiste"),
    ("guildvendor", "Marchand de Guilde (Torches/Gemmes/Clés)"),
    ("horsevendor", "Palefrenier (Chevaux)"),
    ("lordbritish", "Lord British (Soin & Niveaux)"),
    ("hawkwind", "Voyant Hawkwind (Vertus)"),
]

SHOP_ROLES = {
    "weaponsvendor",
    "armorvendor",
    "foodvendor",
    "tavernkeeper",
    "reagentsvendor",
    "healer",
    "innkeeper",
    "guildvendor",
    "horsevendor",
}

# Déclencheurs de question Oui/Non dans .TLK (src/discourse_tlk.cpp)
QUESTION_TRIGGERS: List[Tuple[int, str]] = [
    (0, "Aucune question"),
    (3, "Après JOB (Métier)"),
    (4, "Après HEAL (Santé)"),
    (5, "Après Mot-clé 1"),
    (6, "Après Mot-clé 2"),
]

# Les 8 Vertus, Mantras, Runes et Pierres d'Ultima IV
VIRTUES: List[Tuple[str, str, str, str, str]] = [
    ("Honesty", "Honnêteté", "ahm", "honestyrune", "bluestone"),
    ("Compassion", "Compassion", "mu", "compassionrune", "yellowstone"),
    ("Valor", "Valeur", "ra", "valorrune", "redstone"),
    ("Justice", "Justice", "beh", "justicerune", "greenstone"),
    ("Sacrifice", "Sacrifice", "cah", "sacrificerune", "orangestone"),
    ("Honor", "Honneur", "summ", "honorrune", "purplestone"),
    ("Spirituality", "Spiritualité", "om", "spiritualityrune", "whitestone"),
    ("Humility", "Humilité", "lum", "humilityrune", "blackstone"),
]

# Labels d'objets reconnus par src/item.cpp dans xU4
QUEST_ITEM_LABELS: List[Tuple[str, str]] = [
    ("honestyrune", "Rune d'Honnêteté"),
    ("compassionrune", "Rune de Compassion"),
    ("valorrune", "Rune de Valeur"),
    ("justicerune", "Rune de Justice"),
    ("sacrificerune", "Rune de Sacrifice"),
    ("honorrune", "Rune d'Honneur"),
    ("spiritualityrune", "Rune de Spiritualité"),
    ("humilityrune", "Rune d'Humilité"),
    ("bluestone", "Pierre Bleue (Honnêteté)"),
    ("yellowstone", "Pierre Jaune (Compassion)"),
    ("redstone", "Pierre Rouge (Valeur)"),
    ("greenstone", "Pierre Verte (Justice)"),
    ("orangestone", "Pierre Orange (Sacrifice)"),
    ("purplestone", "Pierre Pourpre (Honneur)"),
    ("whitestone", "Pierre Blanche (Spiritualité)"),
    ("blackstone", "Pierre Noire (Humilité)"),
    ("bell", "Cloche du Courage (Bell)"),
    ("book", "Livre de Vérité (Book)"),
    ("candle", "Bougie d'Amour (Candle)"),
    ("horn", "Cor d'Argent (Silver Horn)"),
    ("wheel", "Gouvernail du H.M.S. Cape (Wheel)"),
    ("skull", "Crâne de Mondain (Skull)"),
    ("mandrake1", "Racine de Mandragore #1"),
    ("mandrake2", "Racine de Mandragore #2"),
    ("nightshade1", "Belladone (Nightshade) #1"),
    ("nightshade2", "Belladone (Nightshade) #2"),
    ("mysticarmor", "Armure Mystique"),
    ("mysticswords", "Épées Mystiques"),
    ("telescope", "Télescope du Lycaeum"),
    ("balloon", "Montgolfière"),
    ("lockelake", "Lac Locke (repère)"),
]

# Types de cases de donjon dans .DNG (quartet haut)
DUNGEON_TILES: List[Tuple[int, str]] = [
    (0x00, "Couloir vide"),
    (0x10, "Échelle montante"),
    (0x20, "Échelle descendante"),
    (0x30, "Échelle montante & descendante"),
    (0x40, "Coffre au trésor"),
    (0x50, "Trou au plafond"),
    (0x60, "Trou dans le sol"),
    (0x70, "Orbe magique"),
    (0x80, "Piège (Vents magiques)"),
    (0x91, "Fontaine de soin"),
    (0xA0, "Champ de poison"),
    (0xA2, "Champ de feu"),
    (0xB0, "Autel de pierre"),
    (0xC0, "Porte de donjon"),
    (0xD0, "Salle tactique #0"),
    (0xE0, "Porte secrète"),
    (0xF0, "Mur de donjon"),
]

# Constantes de boutons pour les boutiques
WEAPONS_LIST = [
    ("staff", "Bâton", 20),
    ("dagger", "Dague", 2),
    ("sling", "Fronde", 25),
    ("mace", "Masse", 100),
    ("axe", "Hache", 225),
    ("sword", "Épée", 300),
    ("bow", "Arc", 250),
    ("crossbow", "Arbalète", 600),
    ("oil", "Huile enflammée", 5),
    ("halberd", "Hallebarde", 350),
    ("magic-axe", "Hache magique", 1500),
    ("magic-sword", "Épée magique", 2500),
    ("magic-bow", "Arc magique", 2000),
    ("magic-wand", "Baguette magique", 5000),
]

ARMORS_LIST = [
    ("cloth", "Tissu", 50),
    ("leather", "Cuir", 200),
    ("chain", "Cotte de mailles", 600),
    ("plate", "Armure de plates", 2000),
    ("magic-chain", "Mailles magiques", 4000),
    ("magic-plate", "Plates magiques", 7000),
]

REAGENTS_NAMES = [
    "Cendre sulfureuse (Sulfurous Ash)",
    "Ginseng",
    "Ail (Garlic)",
    "Soie d'araignée (Spider Silk)",
    "Mousse de sang (Blood Moss)",
    "Perle noire (Black Pearl)",
]

# Constante d'en-tête .CON (octets 0x30..0x3F et 0xB9..0xBF de FileFormats.md)
CON_HEADER_CONST = bytes.fromhex("08AD83C0AD83C0AD83C0A000B9A608F0")
CON_FOOTER_CONST = bytes.fromhex("8D00000000B709")
