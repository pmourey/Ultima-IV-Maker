"""Modèles de données structurés pour Ultima IV Maker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScenarioMetadata:
    title: str = "New Ultima IV Adventure"
    module_name: str = "Custom-Quest"
    author: str = "Anonymous Author"
    version: str = "1.0"
    about: str = "An original adventure created with Ultima IV Maker for xU4."
    rules: str = "Ultima-IV"


@dataclass
class PortalData:
    x: int
    y: int
    z: int = 0
    action: str = "save-enter"  # save-enter, enter, climb, descend, exit_north, exit_east, exit_south, exit_west
    dest_map_id: int = 0
    dest_x: int = 0
    dest_y: int = 0
    dest_z: int = 0
    message: str = ""
    transport: str = "footorhorse"  # foot, horse, ship, balloon, footorhorse
    condition: str = ""  # abyss, shrine, etc.
    retro_active_dest: Optional[List[int]] = None  # [map_id, x, y]


@dataclass
class MoongateData:
    phase: int  # 0..7
    x: int
    y: int


@dataclass
class LabelData:
    name: str  # ex: compassionrune, book, candle, bell, whitestone
    x: int
    y: int
    z: int = 0
    description: str = ""


@dataclass
class ShopConfig:
    shop_name: str = "The Britannia Shop"
    owner_name: str = "Merchant"
    price: int = 25
    prices_list: List[int] = field(default_factory=lambda: [2, 5, 6, 3, 6, 9])
    inventory: List[str] = field(default_factory=list)
    room_loc: List[int] = field(default_factory=lambda: [28, 6])
    specialty_name: str = "Traveller's Stew"
    specialty_price: int = 4
    message: str = ""


@dataclass
class NPCData:
    slot_index: int  # 0..31 dans le fichier .ULT
    name: str = "Citizen"
    tile_id: int = 82  # villager par défaut
    x: int = 15
    y: int = 15
    movement: str = "fixed"  # fixed, wander, follow, attack
    tlk_index: int = 0  # 1..16 dans le fichier .TLK (0 = aucun)
    role: str = "none"  # voir constants.NPC_ROLES
    shop_config: Optional[ShopConfig] = None


@dataclass
class DungeonTriggerData:
    tile_id: int = 0
    trigger_x: int = 0
    trigger_y: int = 0
    change_x1: int = 0
    change_y1: int = 0
    change_x2: int = 0
    change_y2: int = 0


@dataclass
class DungeonRoomData:
    triggers: List[DungeonTriggerData] = field(default_factory=list)
    monster_tiles: List[int] = field(default_factory=lambda: [0] * 16)
    monster_x: List[int] = field(default_factory=lambda: [0] * 16)
    monster_y: List[int] = field(default_factory=lambda: [0] * 16)
    party_north_x: List[int] = field(default_factory=lambda: [5] * 8)
    party_north_y: List[int] = field(default_factory=lambda: [1] * 8)
    party_east_x: List[int] = field(default_factory=lambda: [9] * 8)
    party_east_y: List[int] = field(default_factory=lambda: [5] * 8)
    party_south_x: List[int] = field(default_factory=lambda: [5] * 8)
    party_south_y: List[int] = field(default_factory=lambda: [9] * 8)
    party_west_x: List[int] = field(default_factory=lambda: [1] * 8)
    party_west_y: List[int] = field(default_factory=lambda: [5] * 8)
    grid: List[List[int]] = field(default_factory=lambda: [[22] * 11 for _ in range(11)])


@dataclass
class MapData:
    id: int
    name: str
    fname: str
    map_type: str = "city"  # world, city, dungeon, shrine, combat
    width: int = 32
    height: int = 32
    levels: int = 1
    chunk_dim: int = 0
    border_behavior: str = "exit"  # wrap, exit, fixed
    music: int = 2
    # Pour world/city/shrine/combat : levels=1 -> grid[y][x] ; pour dungeon : grids[z][y][x]
    grids: List[List[List[int]]] = field(default_factory=list)
    npcs: List[NPCData] = field(default_factory=list)
    portals: List[PortalData] = field(default_factory=list)
    moongates: List[MoongateData] = field(default_factory=list)
    labels: List[LabelData] = field(default_factory=list)
    city_type: str = "towne"  # castle, towne, village, ruins
    tlk_fname: str = ""
    shrine_virtue: str = "Honesty"
    shrine_mantra: str = "ahm"
    dungeon_rooms: List[DungeonRoomData] = field(default_factory=list)
    # Positions de combat (.CON)
    con_creature_start_x: List[int] = field(default_factory=lambda: [5] * 16)
    con_creature_start_y: List[int] = field(default_factory=lambda: [2] * 16)
    con_player_start_x: List[int] = field(default_factory=lambda: [3, 4, 5, 6, 3, 4, 5, 6])
    con_player_start_y: List[int] = field(default_factory=lambda: [8, 8, 8, 8, 9, 9, 9, 9])

    def ensure_grids(self, fill_tile: int = 4) -> None:
        if not self.grids or len(self.grids) != self.levels:
            default_tile = 0xF0 if self.map_type == "dungeon" else fill_tile
            self.grids = [
                [[default_tile for _ in range(self.width)] for _ in range(self.height)]
                for _ in range(self.levels)
            ]

    def get_tile(self, x: int, y: int, z: int = 0) -> int:
        if 0 <= z < len(self.grids) and 0 <= y < self.height and 0 <= x < self.width:
            return self.grids[z][y][x]
        return 0

    def set_tile(self, x: int, y: int, tile_id: int, z: int = 0) -> None:
        if 0 <= z < len(self.grids) and 0 <= y < self.height and 0 <= x < self.width:
            self.grids[z][y][x] = tile_id & 0xFF


@dataclass
class DialogueTopic:
    keyword: str
    response: str
    trigger_question: bool = False


@dataclass
class DialogueData:
    id: int  # 1..16 dans la banque .TLK
    bank_name: str  # ex: britain.tlk
    name: str = "Citizen"
    pronoun: str = "He"
    look: str = "a friendly citizen."
    job: str = "I live and work in Britannia."
    health: str = "I am well, thank thee."
    keyword1: str = "A   "
    response1: str = ""
    keyword2: str = "A   "
    response2: str = ""
    question_trigger: int = 0  # 0=None, 3=Job, 4=Health, 5=Keyword1, 6=Keyword2
    question: str = ""
    yes_response: str = ""
    no_response: str = ""
    affects_humility: bool = False
    turn_away_prob: int = 0  # 0..255
    extra_topics: List[DialogueTopic] = field(default_factory=list)
    notes: str = ""


@dataclass
class QuestStep:
    id: str
    title: str
    description: str = ""
    npc_name: str = ""
    dialogue_bank: str = ""
    keyword: str = ""
    required_item_label: str = ""
    target_map_id: Optional[int] = None
    target_x: Optional[int] = None
    target_y: Optional[int] = None


@dataclass
class QuestData:
    id: str
    title: str
    virtue: str = "Compassion"
    summary: str = ""
    is_main_quest: bool = True
    steps: List[QuestStep] = field(default_factory=list)
    reward: str = ""


@dataclass
class TavernRumor:
    topic: str
    price: int = 20
    text: str = ""
    city_name: str = "Britain"


@dataclass
class ShrineConfig:
    virtue: str
    mantra: str
    map_id: int


@dataclass
class ScenarioProject:
    metadata: ScenarioMetadata = field(default_factory=ScenarioMetadata)
    maps: List[MapData] = field(default_factory=list)
    dialogues: Dict[str, List[DialogueData]] = field(default_factory=dict)  # clé: bank_name (ex: "britain.tlk")
    quests: List[QuestData] = field(default_factory=list)
    rumors: List[TavernRumor] = field(default_factory=list)
    shrines: List[ShrineConfig] = field(default_factory=list)
    custom_shapes_ega: Optional[bytes] = None

    def get_map(self, map_id: int) -> Optional[MapData]:
        for m in self.maps:
            if m.id == map_id:
                return m
        return None

    def next_map_id(self) -> int:
        if not self.maps:
            return 0
        return max(m.id for m in self.maps) + 1

    def get_dialogue(self, bank_name: str, tlk_id: int) -> Optional[DialogueData]:
        for d in self.dialogues.get(bank_name, []):
            if d.id == tlk_id:
                return d
        return None

    def all_labels(self) -> List[tuple[MapData, LabelData]]:
        result: List[tuple[MapData, LabelData]] = []
        for m in self.maps:
            for lbl in m.labels:
                result.append((m, lbl))
        return result
