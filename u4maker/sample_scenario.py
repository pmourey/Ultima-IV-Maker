"""Générateur du scénario starter complet et cohérent 'La Quête du Calice d'Avatar'."""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

from .constants import VIRTUES
from .models import (
    DialogueData,
    DungeonRoomData,
    LabelData,
    MapData,
    MoongateData,
    NPCData,
    PortalData,
    QuestData,
    QuestStep,
    ScenarioMetadata,
    ScenarioProject,
    ShopConfig,
    ShrineConfig,
    TavernRumor,
)
from .yaml_io import save_project_yaml


def _paint_rect(grid: List[List[int]], x0: int, y0: int, x1: int, y1: int, tile: int) -> None:
    h = len(grid)
    w = len(grid[0]) if h else 0
    for y in range(max(0, y0), min(h, y1 + 1)):
        for x in range(max(0, x0), min(w, x1 + 1)):
            grid[y][x] = tile


def _paint_border(grid: List[List[int]], x0: int, y0: int, x1: int, y1: int, tile: int) -> None:
    h = len(grid)
    w = len(grid[0]) if h else 0
    for x in range(max(0, x0), min(w, x1 + 1)):
        if 0 <= y0 < h:
            grid[y0][x] = tile
        if 0 <= y1 < h:
            grid[y1][x] = tile
    for y in range(max(0, y0), min(h, y1 + 1)):
        if 0 <= x0 < w:
            grid[y][x0] = tile
        if 0 <= x1 < w:
            grid[y][x1] = tile


def _build_world_map() -> MapData:
    grid = [[0] * 256 for _ in range(256)]  # Haute mer

    # Continent principal de Britannia (forme organique simple)
    for y in range(12, 240):
        for x in range(18, 220):
            dx = (x - 115) / 95.0
            dy = (y - 125) / 108.0
            dist = math.sqrt(dx * dx + dy * dy)
            wobble = 0.14 * math.sin(x * 0.08) + 0.12 * math.cos(y * 0.07)
            if dist + wobble < 0.92:
                grid[y][x] = 4  # Prairie
            elif dist + wobble < 0.99:
                grid[y][x] = 2  # Eaux peu profondes
            elif dist + wobble < 1.07:
                grid[y][x] = 1  # Eau profonde

    # Île de Moonglow / Deceit à l'est
    for y in range(55, 145):
        for x in range(222, 248):
            dx = (x - 235) / 12.0
            dy = (y - 100) / 40.0
            if dx * dx + dy * dy < 0.85:
                grid[y][x] = 4
            elif dx * dx + dy * dy < 1.1:
                grid[y][x] = 1

    # Chaînes de montagnes et collines
    _paint_rect(grid, 60, 35, 95, 42, 8)
    _paint_rect(grid, 55, 43, 100, 45, 7)
    _paint_rect(grid, 140, 75, 175, 88, 8)
    _paint_rect(grid, 236, 68, 244, 77, 8)  # Montagne autour de Deceit

    # Forêts et marais
    _paint_rect(grid, 45, 70, 72, 95, 6)
    _paint_rect(grid, 105, 120, 142, 150, 6)
    _paint_rect(grid, 118, 175, 145, 195, 3)  # Marais
    _paint_rect(grid, 110, 82, 130, 96, 5)   # Broussailles

    # Rivière avec pont menant de Britain vers l'est
    for y in range(70, 135):
        grid[y][100] = 1
        grid[y][101] = 1
    grid[106][100] = 23  # Pont
    grid[106][101] = 23

    # Lieux clés sur la carte
    grid[107][85] = 13   # Château L.B. Ouest
    grid[107][86] = 14   # Château L.B. Entrée
    grid[107][87] = 15   # Château L.B. Est
    grid[106][82] = 10   # Britain
    grid[90][136] = 12   # Cove
    grid[92][128] = 30   # Sanctuaire de la Compassion
    grid[73][240] = 9    # Donjon Deceit
    grid[135][232] = 10  # Moonglow
    grid[233][233] = 9   # Grand Abysse Stygien

    return MapData(
        id=0,
        name="Britannia",
        fname="world.map",
        map_type="world",
        width=256,
        height=256,
        levels=1,
        chunk_dim=32,
        border_behavior="wrap",
        music=1,
        grids=[grid],
        portals=[
            PortalData(x=86, y=107, action="save-enter", dest_map_id=1, dest_x=15, dest_y=30, transport="footorhorse", message="Enter Castle Britannia."),
            PortalData(x=82, y=106, action="save-enter", dest_map_id=6, dest_x=1, dest_y=15, transport="footorhorse", message="Enter the towne of Britain."),
            PortalData(x=240, y=73, action="save-enter", dest_map_id=17, dest_x=1, dest_y=1, transport="foot", message="Enter the dungeon Deceit!"),
            PortalData(x=128, y=92, action="save-enter", dest_map_id=26, dest_x=5, dest_y=9, condition="shrine", transport="footorhorse", message="Enter the Shrine of Compassion."),
        ],
        moongates=[
            MoongateData(phase=0, x=224, y=133),
            MoongateData(phase=1, x=96, y=102),
            MoongateData(phase=2, x=38, y=224),
            MoongateData(phase=3, x=50, y=37),
            MoongateData(phase=4, x=166, y=19),
            MoongateData(phase=5, x=104, y=194),
            MoongateData(phase=6, x=23, y=126),
            MoongateData(phase=7, x=187, y=167),
        ],
        labels=[
            LabelData(name="bell", x=176, y=208, description="Bell of Courage on the southern island"),
            LabelData(name="book", x=136, y=90, description="Book of Truth hidden near Cove"),
            LabelData(name="candle", x=138, y=91, description="Candle of Love"),
            LabelData(name="whitestone", x=64, y=80, description="White Stone of the Mountains"),
        ],
    )


def _build_castle_map() -> MapData:
    grid = [[4] * 32 for _ in range(32)]  # Herbe
    # Murs du château
    _paint_rect(grid, 2, 2, 29, 29, 62)  # Sol en brique
    _paint_border(grid, 2, 2, 29, 29, 57)  # Murs de pierre
    # Douves d'eau autour
    _paint_border(grid, 1, 1, 30, 30, 1)
    # Pont d'entrée sud
    grid[30][15] = 23
    grid[30][16] = 23
    grid[29][15] = 59
    grid[29][16] = 59

    # Salle du trône au nord
    _paint_border(grid, 10, 4, 21, 13, 57)
    grid[13][15] = 59
    grid[13][16] = 59
    grid[6][15] = 74   # Autel royal
    grid[6][16] = 74
    grid[8][12] = 48   # Colonnes
    grid[8][19] = 48
    grid[11][12] = 48
    grid[11][19] = 48

    # Chapelle à l'est (Ankh)
    _paint_border(grid, 22, 6, 28, 14, 57)
    grid[10][22] = 59
    grid[9][26] = 61   # Ankh

    # Infirmerie à l'ouest
    _paint_border(grid, 3, 6, 9, 14, 57)
    grid[10][9] = 59
    grid[8][5] = 75    # Brasero

    npcs = [
        NPCData(slot_index=0, name="Lord British", tile_id=94, x=15, y=7, movement="fixed", tlk_index=1, role="lordbritish"),
        NPCData(slot_index=1, name="Hawkwind", tile_id=32, x=25, y=10, movement="fixed", tlk_index=2, role="hawkwind"),
        NPCData(
            slot_index=2,
            name="Pendragon",
            tile_id=38,
            x=6,
            y=9,
            movement="fixed",
            tlk_index=3,
            role="healer",
            shop_config=ShopConfig(shop_name="Royal Healer", owner_name="Pendragon", price=100),
        ),
        NPCData(slot_index=3, name="Royal Guard", tile_id=80, x=14, y=27, movement="fixed", tlk_index=4, role="none"),
        NPCData(slot_index=4, name="Eleanor", tile_id=82, x=18, y=18, movement="wander", tlk_index=5, role="none"),
    ]

    return MapData(
        id=1,
        name="Castle Britannia",
        fname="lcb_1.ult",
        map_type="city",
        width=32,
        height=32,
        levels=1,
        border_behavior="exit",
        music=9,
        grids=[grid],
        npcs=npcs,
        city_type="castle",
        tlk_fname="lcb.tlk",
        labels=[LabelData(name="spiritualityrune", x=26, y=10, description="Rune of Spirituality in the chapel")],
    )


def _build_britain_map() -> MapData:
    grid = [[4] * 32 for _ in range(32)]
    _paint_border(grid, 0, 0, 31, 31, 57)
    # Portes ouest et est
    grid[15][0] = 4
    grid[16][0] = 4
    grid[15][31] = 4
    grid[16][31] = 4

    # Avenue centrale en brique
    _paint_rect(grid, 1, 14, 30, 17, 62)

    # Forge d'armes (Nord-Ouest)
    _paint_rect(grid, 3, 3, 10, 10, 63)
    _paint_border(grid, 3, 3, 10, 10, 127)
    grid[10][6] = 59
    grid[5][4] = 125  # Comptoir

    # Taverne (Nord-Est)
    _paint_rect(grid, 19, 3, 28, 10, 63)
    _paint_border(grid, 19, 3, 28, 10, 127)
    grid[10][23] = 59
    grid[5][22] = 125

    # Maison du Barde (Sud-Ouest)
    _paint_rect(grid, 4, 20, 12, 27, 63)
    _paint_border(grid, 4, 20, 12, 27, 57)
    grid[20][8] = 59

    # Parc central avec feu de camp et rivière
    _paint_rect(grid, 15, 21, 15, 29, 1)
    grid[24][15] = 23  # Pont
    grid[24][25] = 75  # Feu de camp
    _paint_rect(grid, 22, 20, 28, 26, 6)  # Bosquet

    npcs = [
        NPCData(slot_index=0, name="Iolo", tile_id=34, x=8, y=23, movement="wander", tlk_index=1, role="companion"),
        NPCData(
            slot_index=1,
            name="Winston",
            tile_id=82,
            x=6,
            y=5,
            movement="fixed",
            tlk_index=2,
            role="weaponsvendor",
            shop_config=ShopConfig(
                shop_name="Britain Armoury",
                owner_name="Winston",
                inventory=["staff 20", "dagger 2", "sling 25", "sword 300"],
            ),
        ),
        NPCData(
            slot_index=2,
            name="Sam",
            tile_id=82,
            x=23,
            y=5,
            movement="fixed",
            tlk_index=3,
            role="tavernkeeper",
            shop_config=ShopConfig(
                shop_name="The Jolly Spirits",
                owner_name="Sam",
                specialty_name="Lamb Chops",
                specialty_price=4,
            ),
        ),
        NPCData(slot_index=3, name="Jude", tile_id=88, x=17, y=15, movement="wander", tlk_index=4, role="none"),
        NPCData(slot_index=4, name="Aria", tile_id=84, x=24, y=22, movement="fixed", tlk_index=5, role="none"),
        NPCData(slot_index=5, name="Guard Marcus", tile_id=80, x=2, y=15, movement="fixed", tlk_index=6, role="none"),
    ]

    return MapData(
        id=6,
        name="Britain",
        fname="britain.ult",
        map_type="city",
        width=32,
        height=32,
        levels=1,
        border_behavior="exit",
        music=2,
        grids=[grid],
        npcs=npcs,
        city_type="towne",
        tlk_fname="britain.tlk",
        labels=[LabelData(name="compassionrune", x=25, y=24, description="Rune of Compassion near the campfire")],
    )


def _build_deceit_dungeon() -> MapData:
    grids = []
    for z in range(8):
        lvl = [[0xF0] * 8 for _ in range(8)]
        for x in range(1, 7):
            lvl[1][x] = 0x00
            lvl[6][x] = 0x00
        for y in range(1, 7):
            lvl[y][1] = 0x00
            lvl[y][6] = 0x00
        if z == 0:
            lvl[1][1] = 0x10  # Échelle sortie
        else:
            lvl[1][1] = 0x30  # Échelle haut & bas
        if z < 7:
            lvl[6][6] = 0x20  # Échelle descendante
        lvl[3][3] = 0x41      # Coffre + Rat
        lvl[3][4] = 0x0D      # Orc
        lvl[1][4] = 0xC0      # Porte
        lvl[2][4] = 0xD0      # Salle 0
        if z == 7:
            lvl[6][6] = 0xB0  # Autel au fond
        grids.append(lvl)

    rooms: List[DungeonRoomData] = []
    for r in range(16):
        rg = [[22] * 11 for _ in range(11)]
        _paint_border(rg, 0, 0, 10, 10, 57)
        rg[0][5] = 22
        rg[10][5] = 22
        rg[5][0] = 22
        rg[5][10] = 22
        rg[5][5] = 60  # Coffre central
        rooms.append(DungeonRoomData(grid=rg))

    return MapData(
        id=17,
        name="Dungeon Deceit",
        fname="deceit.dng",
        map_type="dungeon",
        width=8,
        height=8,
        levels=8,
        border_behavior="wrap",
        music=7,
        grids=grids,
        dungeon_rooms=rooms,
        labels=[LabelData(name="bluestone", x=6, y=6, z=7, description="Blue Stone on the altar of Deceit")],
    )


def _build_shrine_map() -> MapData:
    grid = [[1] * 11 for _ in range(11)]  # Eau
    _paint_rect(grid, 2, 2, 8, 8, 4)     # Herbe
    _paint_rect(grid, 3, 3, 7, 7, 62)    # Sol brique
    grid[5][5] = 61                      # Ankh sacré
    grid[8][5] = 23                      # Pont d'accès sud
    grid[9][5] = 23
    grid[10][5] = 4

    return MapData(
        id=26,
        name="Shrine of Compassion",
        fname="shrine.con",
        map_type="shrine",
        width=11,
        height=11,
        levels=1,
        border_behavior="fixed",
        music=3,
        grids=[grid],
        shrine_virtue="Compassion",
        shrine_mantra="mu",
    )


def create_starter_scenario() -> ScenarioProject:
    """Crée un scénario de démonstration complet prêt à éditer et compiler."""
    world = _build_world_map()
    castle = _build_castle_map()
    britain = _build_britain_map()
    deceit = _build_deceit_dungeon()
    shrine = _build_shrine_map()

    dialogues = {
        "lcb.tlk": [
            DialogueData(
                id=1,
                bank_name="lcb.tlk",
                name="Lord British",
                pronoun="He",
                look="a benevolent king.",
                job="I guide heroes toward the Avatar.",
                health="Strong and serene.",
                keyword1="QUES",
                response1="Find the Rune in Britain and its Mantra.",
                keyword2="ABYS",
                response2="Three Keys unlock the Abyss.",
                question_trigger=5,
                question="Wilt thou follow the Virtues?",
                yes_response="Seek Iolo in Britain!",
                no_response="Return when ready.",
                affects_humility=False,
                turn_away_prob=0,
            ),
            DialogueData(
                id=2,
                bank_name="lcb.tlk",
                name="Hawkwind",
                pronoun="He",
                look="a seer clad in starry robes.",
                job="I peer into thy soul upon the path of Virtue.",
                health="My mind is clear.",
                keyword1="MANT",
                response1="The Mantra of Compassion is MU. Meditate east.",
                keyword2="RUNE",
                response2="Seek the Rune beside a campfire in Britain.",
                question_trigger=0,
            ),
            DialogueData(
                id=3,
                bank_name="lcb.tlk",
                name="Pendragon",
                pronoun="He",
                look="a royal healer in white robes.",
                job="I mend the wounded and cure the poisoned.",
                health="By the heavens, I am well.",
                keyword1="BLOO",
                response1="Giving of thy blood proves thy Sacrifice.",
                keyword2="A   ",
                response2="",
            ),
            DialogueData(
                id=4,
                bank_name="lcb.tlk",
                name="Royal Guard",
                pronoun="He",
                look="a guard in gleaming plate.",
                job="I watch the castle gates day and night.",
                health="Ever vigilant!",
                keyword1="BRIT",
                response1="The towne of Britain lies just west of the moat.",
                keyword2="A   ",
                response2="",
                question_trigger=3,
                question="Art thou an invincible warrior?",
                yes_response="Pride leadeth to a fall...",
                no_response="Humility befits the brave.",
                affects_humility=True,
            ),
            DialogueData(
                id=5,
                bank_name="lcb.tlk",
                name="Eleanor",
                pronoun="She",
                look="a chronicler holding a scroll.",
                job="I record the noble deeds of Britannia.",
                health="Weary from writing, yet glad.",
                keyword1="DECE",
                response1="Dungeon Deceit hides the Blue Stone on an eastern isle.",
                keyword2="COVE",
                response2="The Book of Truth rests near the hidden towne of Cove.",
            ),
        ],
        "britain.tlk": [
            DialogueData(
                id=1,
                bank_name="britain.tlk",
                name="Iolo",
                pronoun="He",
                look="a bard with his lute.",
                job="I sing ballads and craft fine bows.",
                health="In fine fettle!",
                keyword1="RUNE",
                response1="Aria watches the campfire to the southeast.",
                keyword2="JOIN",
                response2="Speak JOIN if thou wishest my company!",
                question_trigger=5,
                question="Dost thou enjoy merry ballads?",
                yes_response="Then let us play a joyful tune!",
                no_response="Music yet soothes the weary soul.",
            ),
            DialogueData(
                id=2,
                bank_name="britain.tlk",
                name="Winston",
                pronoun="He",
                look="a sturdy smith covered in soot.",
                job="I forge blades and slings for travellers.",
                health="Strong as steel.",
                keyword1="SWOR",
                response1="A fine iron sword costs 300 gold pieces.",
                keyword2="A   ",
                response2="",
            ),
            DialogueData(
                id=3,
                bank_name="britain.tlk",
                name="Sam",
                pronoun="He",
                look="a smiling tavernkeeper wiping a tankard.",
                job="I pour ale and hear sailors' tales.",
                health="Never dry!",
                keyword1="RUMO",
                response1="Buy a drink and tip well to hear rare secrets.",
                keyword2="STON",
                response2="The Blue Stone lies on the 8th level of Deceit.",
            ),
            DialogueData(
                id=4,
                bank_name="britain.tlk",
                name="Jude",
                pronoun="He",
                look="a poor beggar in tattered rags.",
                job="I survive by the compassion of passersby.",
                health="I am hungry, traveller...",
                keyword1="GIVE",
                response1="Use GIVE to spare a coin, noble heart.",
                keyword2="MANT",
                response2="The wise whisper that Compassion's mantra is MU.",
            ),
            DialogueData(
                id=5,
                bank_name="britain.tlk",
                name="Aria",
                pronoun="She",
                look="a scholar gazing into the flames.",
                job="I tend the ancient sacred fire of Britain.",
                health="At peace.",
                keyword1="RUNE",
                response1="The Rune of Compassion lies buried by this fire (25,24)!",
                keyword2="MANT",
                response2="Seek the Shrine to the east. Its mantra is MU.",
            ),
            DialogueData(
                id=6,
                bank_name="britain.tlk",
                name="Marcus",
                pronoun="He",
                look="a watchful guard at the west gate.",
                job="I guard the road toward Castle Britannia.",
                health="Well enough.",
                keyword1="CAST",
                response1="Exit west and walk east to reach Lord British.",
                keyword2="A   ",
                response2="",
            ),
        ],
    }

    quests = [
        QuestData(
            id="quest_compassion",
            title="Awakening of Compassion",
            virtue="Compassion",
            summary="Answer Lord British's call, recover the Rune of Compassion in Britain, and meditate at the Shrine.",
            is_main_quest=True,
            reward="Partial elevation in Compassion and Iolo joining the party.",
            steps=[
                QuestStep(
                    id="step_1",
                    title="Audience with the King",
                    description="Speak with Lord British in Castle Britannia and ask about the QUEST ('QUES').",
                    npc_name="Lord British",
                    dialogue_bank="lcb.tlk",
                    keyword="QUES",
                    target_map_id=1,
                    target_x=15,
                    target_y=7,
                ),
                QuestStep(
                    id="step_2",
                    title="Consult Iolo the Bard",
                    description="Travel to Britain and ask Iolo about the RUNE ('RUNE').",
                    npc_name="Iolo",
                    dialogue_bank="britain.tlk",
                    keyword="RUNE",
                    target_map_id=6,
                    target_x=8,
                    target_y=23,
                ),
                QuestStep(
                    id="step_3",
                    title="Uncover the Rune with Aria",
                    description="Speak to Aria beside the campfire ('RUNE') and search the ground at (25,24).",
                    npc_name="Aria",
                    dialogue_bank="britain.tlk",
                    keyword="RUNE",
                    required_item_label="compassionrune",
                    target_map_id=6,
                    target_x=25,
                    target_y=24,
                ),
                QuestStep(
                    id="step_4",
                    title="Meditate at the Shrine",
                    description="Learn the mantra 'MU' from Hawkwind ('MANT') and meditate at the Shrine of Compassion.",
                    npc_name="Hawkwind",
                    dialogue_bank="lcb.tlk",
                    keyword="MANT",
                    target_map_id=26,
                    target_x=5,
                    target_y=5,
                ),
            ],
        ),
        QuestData(
            id="quest_deceit",
            title="The Blue Stone of Deceit",
            virtue="Honesty",
            summary="Follow the chronicler's clues and delve into the depths of Dungeon Deceit.",
            is_main_quest=False,
            reward="Recovery of the Blue Stone.",
            steps=[
                QuestStep(
                    id="step_d1",
                    title="Clue from the Chronicler",
                    description="Ask Eleanor at the castle about DECEIT ('DECE').",
                    npc_name="Eleanor",
                    dialogue_bank="lcb.tlk",
                    keyword="DECE",
                    target_map_id=1,
                    target_x=18,
                    target_y=18,
                ),
                QuestStep(
                    id="step_d2",
                    title="Reach the Altar of Deceit",
                    description="Descend to level 8 of Deceit to claim the Blue Stone.",
                    required_item_label="bluestone",
                    target_map_id=17,
                    target_x=6,
                    target_y=6,
                ),
            ],
        ),
    ]

    rumors = [
        TavernRumor(
            topic="black stone",
            price=20,
            city_name="Britain",
            text="They say the Black Stone slumbers near a moongate on new moons...",
        ),
        TavernRumor(
            topic="white stone",
            price=15,
            city_name="Britain",
            text="The White Stone rests high within the Serpent's Spine to the northwest.",
        ),
        TavernRumor(
            topic="bell",
            price=25,
            city_name="Britain",
            text="The Bell of Courage sank near the southern isle (176, 208).",
        ),
    ]

    shrines = [
        ShrineConfig(virtue=v_en, mantra=mantra, map_id=25 + idx)
        for idx, (v_en, _, mantra, _, _) in enumerate(VIRTUES)
    ]

    return ScenarioProject(
        metadata=ScenarioMetadata(
            title="The Quest of the Avatar's Chalice",
            module_name="Britannia-Starter",
            author="Ultima IV Maker",
            version="1.0",
            about="A complete starter adventure featuring Lord British, Britain, Deceit, and the Shrine.",
            rules="Ultima-IV",
        ),
        maps=[world, castle, britain, deceit, shrine],
        dialogues=dialogues,
        quests=quests,
        rumors=rumors,
        shrines=shrines,
    )


def ensure_starter_scenario(base_dir: str | Path) -> Path:
    """Crée le scénario starter dans scenarios/britannia_starter s'il n'existe pas encore."""
    p = Path(base_dir)
    target = p if p.name == "britannia_starter" else p / "scenarios" / "britannia_starter"
    if not (target / "project.yaml").exists():
        proj = create_starter_scenario()
        save_project_yaml(proj, target)
    return target
