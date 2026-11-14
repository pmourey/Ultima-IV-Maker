"""Tests unitaires pour les formats binaires Ultima IV / xU4 et SHAPES.EGA."""

from __future__ import annotations

from pathlib import Path

import pytest

from u4maker.binary_io import (
    CON_FILE_SIZE,
    TLK_BLOCK_SIZE,
    ULT_FILE_SIZE,
    WORLD_MAP_SIZE,
    calculate_tlk_bytes,
    encode_con,
    encode_dng,
    encode_tlk_block,
    encode_ult,
    encode_world_map,
    normalize_u4_ascii,
    read_con,
    read_dng,
    read_tlk,
    read_ult,
    read_world_map,
    write_con,
    write_dng,
    write_tlk,
    write_ult,
    write_world_map,
)
from u4maker.models import (
    DialogueData,
    DungeonRoomData,
    DungeonTriggerData,
    MapData,
    NPCData,
)
from u4maker.tileset_renderer import (
    encode_shapes_ega,
    generate_builtin_ega_tileset,
    load_shapes_ega,
    save_shapes_ega,
)


def test_normalize_u4_ascii_strips_accents() -> None:
    assert normalize_u4_ascii("Épée sacrée de Vérité à Noël") == b"Epee sacree de Verite a Noel"


def test_tlk_block_roundtrip_and_limits(tmp_path: Path) -> None:
    dlg = DialogueData(
        id=1,
        bank_name="britain.tlk",
        name="Iolo",
        pronoun="He",
        look="un barde joyeux.",
        job="Je compose des chants de Compassion.",
        health="Fort comme un chêne!",
        keyword1="calice",
        response1="Cherche la rune jaune dans le bosquet.",
        keyword2="",
        response2="",
        question_trigger=5,
        question="As-tu déjà chanté ?",
        yes_response="Bravo l'ami !",
        no_response="Écoute donc mon luth.",
        affects_humility=True,
        turn_away_prob=12,
    )
    total, breakdown = calculate_tlk_bytes(dlg)
    assert total < TLK_BLOCK_SIZE
    assert breakdown["En-tête binaire"] == 3

    block = encode_tlk_block(dlg, strict=True)
    assert len(block) == TLK_BLOCK_SIZE

    tlk_path = tmp_path / "britain.tlk"
    write_tlk([dlg], tlk_path, strict=True)
    loaded = read_tlk(tlk_path, bank_name="britain.tlk")
    assert len(loaded) == 1
    d = loaded[0]
    assert d.name == "Iolo"
    assert d.pronoun == "He"
    assert d.keyword1 == "CALI"
    assert d.keyword2 == "A   "
    assert d.question_trigger == 5
    assert d.affects_humility is True
    assert d.turn_away_prob == 12
    assert "Fort comme un chene!" == d.health

    # Dépassement strict vs troncature non stricte
    huge = DialogueData(
        id=1,
        bank_name="test.tlk",
        name="Bavard",
        look="x" * 100,
        job="y" * 120,
        health="z" * 120,
        keyword1="TEST",
        response1="w" * 100,
    )
    with pytest.raises(ValueError):
        encode_tlk_block(huge, strict=True)
    truncated = encode_tlk_block(huge, strict=False)
    assert len(truncated) == TLK_BLOCK_SIZE


def test_ult_city_roundtrip(tmp_path: Path) -> None:
    city = MapData(
        id=5,
        name="Britain",
        fname="britain.ult",
        map_type="city",
        width=32,
        height=32,
    )
    city.ensure_grids(fill_tile=4)
    city.set_tile(0, 0, 127)
    city.set_tile(31, 31, 62)
    city.set_tile(15, 10, 74)
    city.npcs = [
        NPCData(slot_index=0, name="Lord British", tile_id=94, x=15, y=4, movement="fixed", tlk_index=0),
        NPCData(slot_index=3, name="Gwenno", tile_id=82, x=12, y=18, movement="wander", tlk_index=2),
        NPCData(slot_index=7, name="Garde", tile_id=80, x=20, y=25, movement="follow", tlk_index=5),
        NPCData(slot_index=12, name="Brigand", tile_id=184, x=2, y=29, movement="attack", tlk_index=0),
    ]

    raw = encode_ult(city)
    assert len(raw) == ULT_FILE_SIZE

    ult_path = tmp_path / "britain.ult"
    write_ult(city, ult_path)
    decoded = read_ult(ult_path, map_id=5, name="Britain")

    assert decoded.get_tile(0, 0) == 127
    assert decoded.get_tile(31, 31) == 62
    assert decoded.get_tile(15, 10) == 74
    by_slot = {n.slot_index: n for n in decoded.npcs}
    assert set(by_slot.keys()) == {0, 3, 7, 12}
    assert by_slot[0].tile_id == 94 and by_slot[0].x == 15 and by_slot[0].y == 4
    assert by_slot[3].movement == "wander" and by_slot[3].tlk_index == 2
    assert by_slot[7].movement == "follow" and by_slot[7].tlk_index == 5
    assert by_slot[12].movement == "attack"


def test_world_map_chunked_roundtrip(tmp_path: Path) -> None:
    world = MapData(
        id=0,
        name="Britannia",
        fname="world.map",
        map_type="world",
        width=256,
        height=256,
        chunk_dim=32,
        border_behavior="wrap",
    )
    world.ensure_grids(fill_tile=1)
    samples = [
        (0, 0, 4),
        (31, 31, 5),
        (32, 0, 8),
        (127, 200, 14),
        (255, 255, 76),
    ]
    for x, y, t in samples:
        world.set_tile(x, y, t)

    raw = encode_world_map(world)
    assert len(raw) == WORLD_MAP_SIZE

    w_path = tmp_path / "world.map"
    write_world_map(world, w_path)
    decoded = read_world_map(w_path, map_id=0)
    for x, y, expected in samples:
        assert decoded.get_tile(x, y) == expected


def test_con_roundtrip(tmp_path: Path) -> None:
    con = MapData(
        id=25,
        name="Honesty Shrine",
        fname="shrine.con",
        map_type="shrine",
        width=11,
        height=11,
        con_creature_start_x=[i for i in range(16)],
        con_creature_start_y=[(15 - i) % 11 for i in range(16)],
        con_player_start_x=[1, 2, 3, 4, 5, 6, 7, 8],
        con_player_start_y=[9, 9, 8, 8, 7, 7, 6, 6],
    )
    con.ensure_grids(fill_tile=22)
    con.set_tile(5, 5, 74)
    con.set_tile(0, 10, 127)

    raw = encode_con(con)
    assert len(raw) == CON_FILE_SIZE

    c_path = tmp_path / "shrine.con"
    write_con(con, c_path)
    decoded = read_con(c_path, map_id=25, map_type="shrine")
    assert decoded.get_tile(5, 5) == 74
    assert decoded.get_tile(0, 10) == 127
    assert decoded.con_creature_start_x == con.con_creature_start_x
    assert decoded.con_creature_start_y == con.con_creature_start_y
    assert decoded.con_player_start_x == con.con_player_start_x
    assert decoded.con_player_start_y == con.con_player_start_y


def test_dng_roundtrip(tmp_path: Path) -> None:
    room = DungeonRoomData(
        triggers=[DungeonTriggerData(tile_id=0x16, trigger_x=4, trigger_y=5, change_x1=1, change_y1=2, change_x2=9, change_y2=10)],
    )
    room.monster_tiles[0] = 200
    room.monster_x[0] = 3
    room.monster_y[0] = 4
    room.grid[5][5] = 0x3C

    dng = MapData(
        id=17,
        name="Covetous",
        fname="covetous.dng",
        map_type="dungeon",
        width=8,
        height=8,
        levels=8,
        dungeon_rooms=[room],
    )
    dng.ensure_grids(fill_tile=0xF0)
    dng.set_tile(3, 4, 0x10, z=0)
    dng.set_tile(7, 7, 0x80, z=7)

    raw = encode_dng(dng)
    assert len(raw) == 512 + 16 * 256

    d_path = tmp_path / "covetous.dng"
    write_dng(dng, d_path)
    decoded = read_dng(d_path, map_id=17)

    assert decoded.levels == 8
    assert decoded.get_tile(3, 4, z=0) == 0x10
    assert decoded.get_tile(7, 7, z=7) == 0x80
    assert len(decoded.dungeon_rooms) == 16
    r0 = decoded.dungeon_rooms[0]
    assert len(r0.triggers) == 1
    assert r0.triggers[0].trigger_x == 4 and r0.triggers[0].trigger_y == 5
    assert r0.monster_tiles[0] == 200
    assert r0.grid[5][5] == 0x3C


def test_shapes_ega_roundtrip(tmp_path: Path) -> None:
    tiles = generate_builtin_ega_tileset()
    assert len(tiles) == 256
    assert tiles[0].size == (16, 16)

    raw = encode_shapes_ega(tiles)
    assert len(raw) == 256 * 128

    ega_path = tmp_path / "shapes.ega"
    save_shapes_ega(tiles, ega_path)
    reloaded = load_shapes_ega(ega_path)
    assert len(reloaded) == 256
    for tid in (0, 4, 22, 82, 94, 255):
        assert reloaded[tid].tobytes() == tiles[tid].tobytes()
