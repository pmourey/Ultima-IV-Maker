"""Lecture et écriture exactes des fichiers binaires Ultima IV / xU4."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

from .constants import (
    CON_FOOTER_CONST,
    CON_HEADER_CONST,
    MOVEMENT_TO_ULT_BYTE,
    ULT_BYTE_TO_MOVEMENT,
)
from .models import (
    DialogueData,
    DungeonRoomData,
    DungeonTriggerData,
    MapData,
    NPCData,
)

TLK_BLOCK_SIZE = 288
ULT_FILE_SIZE = 1280
WORLD_MAP_SIZE = 65536
CON_FILE_SIZE = 192


def normalize_u4_ascii(text: str) -> bytes:
    """Convertit une chaîne Unicode (avec accents français) en ASCII compatible xU4."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_str.encode("ascii")


def _format_tlk_keyword(kw: str) -> bytes:
    raw = normalize_u4_ascii(kw).decode("ascii").strip().upper()
    if not raw:
        return b"A   "
    # Dans Ultima IV, les mots-clés sont tronqués/complétés à 4 caractères (ou plus si libre)
    padded = (raw[:4]).ljust(4, " ")
    return padded.encode("ascii")


def _build_tlk_strings(dlg: DialogueData) -> List[Tuple[str, bytes]]:
    return [
        ("Nom", normalize_u4_ascii(dlg.name)),
        ("Pronom", normalize_u4_ascii(dlg.pronoun or "He")),
        ("Description (LOOK)", normalize_u4_ascii(dlg.look)),
        ("Métier (JOB)", normalize_u4_ascii(dlg.job)),
        ("Santé (HEAL)", normalize_u4_ascii(dlg.health)),
        ("Réponse 1", normalize_u4_ascii(dlg.response1)),
        ("Réponse 2", normalize_u4_ascii(dlg.response2)),
        ("Question (Y/N)", normalize_u4_ascii(dlg.question)),
        ("Réponse OUI", normalize_u4_ascii(dlg.yes_response)),
        ("Réponse NON", normalize_u4_ascii(dlg.no_response)),
        ("Mot-clé 1", _format_tlk_keyword(dlg.keyword1)),
        ("Mot-clé 2", _format_tlk_keyword(dlg.keyword2)),
    ]


def calculate_tlk_bytes(dlg: DialogueData) -> Tuple[int, Dict[str, int]]:
    """Retourne (total_octets, detail_par_champ) pour un bloc .TLK de 288 octets."""
    fields = _build_tlk_strings(dlg)
    breakdown: Dict[str, int] = {"En-tête binaire": 3}
    total = 3
    for label, bval in fields:
        sz = len(bval) + 1  # +1 pour octet nul \0
        breakdown[label] = sz
        total += sz
    return total, breakdown


def encode_tlk_block(dlg: DialogueData, strict: bool = False) -> bytes:
    """Encode un dialogue en un bloc exact de 288 octets (.TLK)."""
    fields = _build_tlk_strings(dlg)
    payload = bytearray()
    payload.append(dlg.question_trigger & 0xFF)
    payload.append(1 if dlg.affects_humility else 0)
    payload.append(dlg.turn_away_prob & 0xFF)

    # Si non strict et dépasse 288 octets, on réduit d'abord les longues descriptions pour rester valide
    str_values = [b for _, b in fields]
    total = 3 + sum(len(s) + 1 for s in str_values)
    if total > TLK_BLOCK_SIZE:
        if strict:
            raise ValueError(
                f"Dialogue '{dlg.name}' dépasse la limite de {TLK_BLOCK_SIZE} octets ({total} octets)."
            )
        # Réduction progressive des chaînes de réponses longues (indices 2..9)
        excess = total - TLK_BLOCK_SIZE
        for idx in (9, 8, 7, 6, 5, 4, 3, 2):
            if excess <= 0:
                break
            cur = str_values[idx]
            if len(cur) > 10:
                cut = min(excess, len(cur) - 10)
                str_values[idx] = cur[:-cut]
                excess -= cut

    for s in str_values:
        payload.extend(s)
        payload.append(0)

    if len(payload) > TLK_BLOCK_SIZE:
        raise ValueError(
            f"Dialogue '{dlg.name}' dépasse {TLK_BLOCK_SIZE} octets même après réduction ({len(payload)})."
        )

    payload.extend(b"\x00" * (TLK_BLOCK_SIZE - len(payload)))
    return bytes(payload)


def write_tlk(dialogues: List[DialogueData], path: str | Path, strict: bool = False) -> int:
    """Écrit un fichier .TLK (jusqu'à 16 blocs de 288 octets). Retourne le nombre de blocs écrits."""
    sorted_dlgs = sorted(dialogues, key=lambda d: d.id)[:16]
    buf = bytearray()
    for dlg in sorted_dlgs:
        buf.extend(encode_tlk_block(dlg, strict=strict))
    Path(path).write_bytes(bytes(buf))
    return len(sorted_dlgs)


def read_tlk(path: str | Path, bank_name: str = "") -> List[DialogueData]:
    """Lit un fichier .TLK binaire et retourne la liste des DialogueData."""
    raw = Path(path).read_bytes()
    bname = bank_name or Path(path).name
    count = len(raw) // TLK_BLOCK_SIZE
    result: List[DialogueData] = []
    for i in range(count):
        block = raw[i * TLK_BLOCK_SIZE : (i + 1) * TLK_BLOCK_SIZE]
        q_trig = block[0]
        humility = bool(block[1])
        turn_away = block[2]
        pos = 3
        strs: List[str] = []
        for _ in range(12):
            nul = block.find(0, pos)
            if nul == -1:
                nul = len(block)
            strs.append(block[pos:nul].decode("latin-1", errors="replace"))
            pos = nul + 1
        kw1 = strs[10].strip() if strs[10] != "A   " else ""
        kw2 = strs[11].strip() if strs[11] != "A   " else ""
        result.append(
            DialogueData(
                id=i + 1,
                bank_name=bname,
                name=strs[0] or f"PNJ #{i+1}",
                pronoun=strs[1] or "He",
                look=strs[2],
                job=strs[3],
                health=strs[4],
                response1=strs[5],
                response2=strs[6],
                question=strs[7],
                yes_response=strs[8],
                no_response=strs[9],
                keyword1=kw1 or "A   ",
                keyword2=kw2 or "A   ",
                question_trigger=q_trig,
                affects_humility=humility,
                turn_away_prob=turn_away,
            )
        )
    return result


def encode_ult(map_data: MapData) -> bytes:
    """Encode une carte de ville/château (32x32 + 32 PNJ) en 1 280 octets .ULT."""
    if map_data.width != 32 or map_data.height != 32:
        raise ValueError(f"Une carte .ULT doit mesurer 32x32 (reçu {map_data.width}x{map_data.height})")
    map_data.ensure_grids()
    buf = bytearray(ULT_FILE_SIZE)
    grid = map_data.grids[0]
    for y in range(32):
        for x in range(32):
            buf[y * 32 + x] = grid[y][x] & 0xFF

    for npc in map_data.npcs:
        slot = npc.slot_index
        if not (0 <= slot < 32):
            continue
        tile_b = npc.tile_id & 0xFF
        x_b = npc.x & 0xFF
        y_b = npc.y & 0xFF
        move_b = MOVEMENT_TO_ULT_BYTE.get(npc.movement, 0x00)
        tlk_b = npc.tlk_index & 0xFF

        buf[0x400 + slot] = tile_b
        buf[0x420 + slot] = x_b
        buf[0x440 + slot] = y_b
        buf[0x460 + slot] = tile_b
        buf[0x480 + slot] = x_b
        buf[0x4A0 + slot] = y_b
        buf[0x4C0 + slot] = move_b
        buf[0x4E0 + slot] = tlk_b

    return bytes(buf)


def write_ult(map_data: MapData, path: str | Path) -> None:
    Path(path).write_bytes(encode_ult(map_data))


def read_ult(path: str | Path, map_id: int = 1, name: str = "") -> MapData:
    """Lit un fichier .ULT binaire (1 280 octets) vers MapData."""
    raw = Path(path).read_bytes()
    if len(raw) != ULT_FILE_SIZE:
        raise ValueError(f"Fichier .ULT invalide : {len(raw)} octets (attendu {ULT_FILE_SIZE})")
    grid = [[raw[y * 32 + x] for x in range(32)] for y in range(32)]
    npcs: List[NPCData] = []
    for slot in range(32):
        tile_id = raw[0x400 + slot]
        if tile_id == 0:
            continue
        x = raw[0x420 + slot]
        y = raw[0x440 + slot]
        move_b = raw[0x4C0 + slot]
        tlk_idx = raw[0x4E0 + slot]
        npcs.append(
            NPCData(
                slot_index=slot,
                name=f"PNJ #{slot + 1}",
                tile_id=tile_id,
                x=x,
                y=y,
                movement=ULT_BYTE_TO_MOVEMENT.get(move_b, "fixed"),
                tlk_index=tlk_idx,
                role="none",
            )
        )
    fname = Path(path).name
    stem = Path(path).stem
    return MapData(
        id=map_id,
        name=name or stem.capitalize(),
        fname=fname,
        map_type="city",
        width=32,
        height=32,
        levels=1,
        chunk_dim=0,
        border_behavior="exit",
        music=2,
        grids=[grid],
        npcs=npcs,
        tlk_fname=f"{stem}.tlk",
    )


def encode_world_map(map_data: MapData) -> bytes:
    """Encode une carte du monde 256x256 en 64 chunks de 32x32 (65 536 octets)."""
    if map_data.width != 256 or map_data.height != 256:
        raise ValueError(f"WORLD.MAP doit mesurer 256x256 (reçu {map_data.width}x{map_data.height})")
    map_data.ensure_grids()
    grid = map_data.grids[0]
    buf = bytearray(WORLD_MAP_SIZE)
    pos = 0
    for ych in range(8):
        for xch in range(8):
            for y in range(32):
                gy = ych * 32 + y
                row = grid[gy]
                for x in range(32):
                    gx = xch * 32 + x
                    buf[pos] = row[gx] & 0xFF
                    pos += 1
    return bytes(buf)


def write_world_map(map_data: MapData, path: str | Path) -> None:
    Path(path).write_bytes(encode_world_map(map_data))


def read_world_map(path: str | Path, map_id: int = 0) -> MapData:
    """Lit un fichier WORLD.MAP (65 536 octets) avec réassemblage des 64 chunks."""
    raw = Path(path).read_bytes()
    if len(raw) != WORLD_MAP_SIZE:
        raise ValueError(f"WORLD.MAP invalide : {len(raw)} octets (attendu {WORLD_MAP_SIZE})")
    grid = [[0] * 256 for _ in range(256)]
    pos = 0
    for ych in range(8):
        for xch in range(8):
            for y in range(32):
                gy = ych * 32 + y
                for x in range(32):
                    gx = xch * 32 + x
                    grid[gy][gx] = raw[pos]
                    pos += 1
    return MapData(
        id=map_id,
        name="Britannia",
        fname=Path(path).name,
        map_type="world",
        width=256,
        height=256,
        levels=1,
        chunk_dim=32,
        border_behavior="wrap",
        music=1,
        grids=[grid],
    )


def encode_con(map_data: MapData) -> bytes:
    """Encode une carte de combat ou sanctuaire 11x11 en 192 octets (.CON)."""
    if map_data.width != 11 or map_data.height != 11:
        raise ValueError(f"Une carte .CON doit mesurer 11x11 (reçu {map_data.width}x{map_data.height})")
    map_data.ensure_grids()
    buf = bytearray(CON_FILE_SIZE)
    for i in range(16):
        buf[0x00 + i] = (map_data.con_creature_start_x[i] if i < len(map_data.con_creature_start_x) else 5) & 0xFF
        buf[0x10 + i] = (map_data.con_creature_start_y[i] if i < len(map_data.con_creature_start_y) else 2) & 0xFF
    for i in range(8):
        buf[0x20 + i] = (map_data.con_player_start_x[i] if i < len(map_data.con_player_start_x) else 5) & 0xFF
        buf[0x28 + i] = (map_data.con_player_start_y[i] if i < len(map_data.con_player_start_y) else 8) & 0xFF
    buf[0x30:0x40] = CON_HEADER_CONST
    grid = map_data.grids[0]
    for y in range(11):
        for x in range(11):
            buf[0x40 + y * 11 + x] = grid[y][x] & 0xFF
    buf[0xB9:0xC0] = CON_FOOTER_CONST
    return bytes(buf)


def write_con(map_data: MapData, path: str | Path) -> None:
    Path(path).write_bytes(encode_con(map_data))


def read_con(path: str | Path, map_id: int = 33, map_type: str = "combat") -> MapData:
    raw = Path(path).read_bytes()
    if len(raw) != CON_FILE_SIZE:
        raise ValueError(f"Fichier .CON invalide : {len(raw)} octets (attendu {CON_FILE_SIZE})")
    cx = [raw[0x00 + i] for i in range(16)]
    cy = [raw[0x10 + i] for i in range(16)]
    px = [raw[0x20 + i] for i in range(8)]
    py = [raw[0x28 + i] for i in range(8)]
    grid = [[raw[0x40 + y * 11 + x] for x in range(11)] for y in range(11)]
    return MapData(
        id=map_id,
        name=Path(path).stem.capitalize(),
        fname=Path(path).name,
        map_type=map_type,
        width=11,
        height=11,
        levels=1,
        border_behavior="fixed",
        music=3 if map_type == "shrine" else 8,
        grids=[grid],
        con_creature_start_x=cx,
        con_creature_start_y=cy,
        con_player_start_x=px,
        con_player_start_y=py,
    )


def encode_dng(map_data: MapData) -> bytes:
    """Encode un donjon (8 niveaux 8x8 + salles 11x11 de 256 octets) au format .DNG."""
    if map_data.width != 8 or map_data.height != 8 or map_data.levels != 8:
        raise ValueError("Un donjon .DNG doit mesurer 8x8 sur 8 niveaux")
    map_data.ensure_grids()
    n_rooms = max(16, len(map_data.dungeon_rooms))
    buf = bytearray(512 + n_rooms * 256)
    for z in range(8):
        for y in range(8):
            for x in range(8):
                buf[z * 64 + y * 8 + x] = map_data.grids[z][y][x] & 0xFF

    for r_idx in range(n_rooms):
        base = 512 + r_idx * 256
        if r_idx < len(map_data.dungeon_rooms):
            room = map_data.dungeon_rooms[r_idx]
        else:
            room = DungeonRoomData()
        for t_idx in range(min(4, len(room.triggers))):
            trig = room.triggers[t_idx]
            off = base + t_idx * 4
            buf[off] = trig.tile_id & 0xFF
            buf[off + 1] = ((trig.trigger_x & 0x0F) << 4) | (trig.trigger_y & 0x0F)
            buf[off + 2] = ((trig.change_x1 & 0x0F) << 4) | (trig.change_y1 & 0x0F)
            buf[off + 3] = ((trig.change_x2 & 0x0F) << 4) | (trig.change_y2 & 0x0F)

        for i in range(16):
            buf[base + 0x10 + i] = (room.monster_tiles[i] if i < len(room.monster_tiles) else 0) & 0xFF
            buf[base + 0x20 + i] = (room.monster_x[i] if i < len(room.monster_x) else 0) & 0xFF
            buf[base + 0x30 + i] = (room.monster_y[i] if i < len(room.monster_y) else 0) & 0xFF

        for i in range(8):
            buf[base + 0x40 + i] = (room.party_north_x[i] if i < len(room.party_north_x) else 5) & 0xFF
            buf[base + 0x48 + i] = (room.party_north_y[i] if i < len(room.party_north_y) else 1) & 0xFF
            buf[base + 0x50 + i] = (room.party_east_x[i] if i < len(room.party_east_x) else 9) & 0xFF
            buf[base + 0x58 + i] = (room.party_east_y[i] if i < len(room.party_east_y) else 5) & 0xFF
            buf[base + 0x60 + i] = (room.party_south_x[i] if i < len(room.party_south_x) else 5) & 0xFF
            buf[base + 0x68 + i] = (room.party_south_y[i] if i < len(room.party_south_y) else 9) & 0xFF
            buf[base + 0x70 + i] = (room.party_west_x[i] if i < len(room.party_west_x) else 1) & 0xFF
            buf[base + 0x78 + i] = (room.party_west_y[i] if i < len(room.party_west_y) else 5) & 0xFF

        for y in range(11):
            for x in range(11):
                val = room.grid[y][x] if y < len(room.grid) and x < len(room.grid[y]) else 22
                buf[base + 0x80 + y * 11 + x] = val & 0xFF

    return bytes(buf)


def write_dng(map_data: MapData, path: str | Path) -> None:
    Path(path).write_bytes(encode_dng(map_data))


def read_dng(path: str | Path, map_id: int = 17) -> MapData:
    raw = Path(path).read_bytes()
    if len(raw) < 512:
        raise ValueError(f"Fichier .DNG trop court ({len(raw)} octets)")
    grids = [
        [[raw[z * 64 + y * 8 + x] for x in range(8)] for y in range(8)]
        for z in range(8)
    ]
    n_rooms = (len(raw) - 512) // 256
    rooms: List[DungeonRoomData] = []
    for r_idx in range(n_rooms):
        base = 512 + r_idx * 256
        triggers: List[DungeonTriggerData] = []
        for t_idx in range(4):
            off = base + t_idx * 4
            tile_id = raw[off]
            if tile_id != 0:
                triggers.append(
                    DungeonTriggerData(
                        tile_id=tile_id,
                        trigger_x=(raw[off + 1] >> 4) & 0x0F,
                        trigger_y=raw[off + 1] & 0x0F,
                        change_x1=(raw[off + 2] >> 4) & 0x0F,
                        change_y1=raw[off + 2] & 0x0F,
                        change_x2=(raw[off + 3] >> 4) & 0x0F,
                        change_y2=raw[off + 3] & 0x0F,
                    )
                )
        room_grid = [[raw[base + 0x80 + y * 11 + x] for x in range(11)] for y in range(11)]
        rooms.append(
            DungeonRoomData(
                triggers=triggers,
                monster_tiles=list(raw[base + 0x10 : base + 0x20]),
                monster_x=list(raw[base + 0x20 : base + 0x30]),
                monster_y=list(raw[base + 0x30 : base + 0x40]),
                party_north_x=list(raw[base + 0x40 : base + 0x48]),
                party_north_y=list(raw[base + 0x48 : base + 0x50]),
                party_east_x=list(raw[base + 0x50 : base + 0x58]),
                party_east_y=list(raw[base + 0x58 : base + 0x60]),
                party_south_x=list(raw[base + 0x60 : base + 0x68]),
                party_south_y=list(raw[base + 0x68 : base + 0x70]),
                party_west_x=list(raw[base + 0x70 : base + 0x78]),
                party_west_y=list(raw[base + 0x78 : base + 0x80]),
                grid=room_grid,
            )
        )
    return MapData(
        id=map_id,
        name=Path(path).stem.capitalize(),
        fname=Path(path).name,
        map_type="dungeon",
        width=8,
        height=8,
        levels=8,
        border_behavior="wrap",
        music=7,
        grids=grids,
        dungeon_rooms=rooms,
    )
