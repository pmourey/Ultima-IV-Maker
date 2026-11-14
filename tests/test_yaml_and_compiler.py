"""Tests d'intégration pour YAML, validation, scripts Boron et archive CDI .mod."""

from __future__ import annotations

import copy
import struct
from pathlib import Path

import pytest

import main as cli_main
from u4maker.binary_io import CON_FILE_SIZE, TLK_BLOCK_SIZE, ULT_FILE_SIZE, WORLD_MAP_SIZE
from u4maker.compiler import (
    compile_module,
    generate_config_b,
    generate_maps_b,
    generate_vendors_b,
    validate_project,
)
from u4maker.models import PortalData
from u4maker.sample_scenario import create_starter_scenario
from u4maker.yaml_io import load_project_yaml, save_project_yaml


def test_starter_scenario_yaml_roundtrip(tmp_path: Path) -> None:
    proj = create_starter_scenario()
    yaml_dir = tmp_path / "starter_yaml"
    save_project_yaml(proj, yaml_dir)

    assert (yaml_dir / "project.yaml").exists()
    assert (yaml_dir / "quests" / "quests.yaml").exists()
    assert list((yaml_dir / "maps").glob("*.yaml"))
    assert list((yaml_dir / "dialogues").glob("*.yaml"))

    reloaded = load_project_yaml(yaml_dir)
    assert reloaded.metadata.title == proj.metadata.title
    assert reloaded.metadata.module_name == proj.metadata.module_name
    assert len(reloaded.maps) == len(proj.maps)
    assert set(reloaded.dialogues.keys()) == set(proj.dialogues.keys())
    assert len(reloaded.quests) == len(proj.quests)
    assert len(reloaded.rumors) == len(proj.rumors)
    assert len(reloaded.shrines) == len(proj.shrines)

    # Vérifier conservation d'une carte et d'un PNJ avec boutique
    world_orig = proj.get_map(0)
    world_new = reloaded.get_map(0)
    assert world_orig is not None and world_new is not None
    assert world_new.get_tile(10, 10) == world_orig.get_tile(10, 10)
    assert len(world_new.portals) == len(world_orig.portals)
    assert len(world_new.moongates) == len(world_orig.moongates)

    britain_orig = proj.get_map(6)
    britain_new = reloaded.get_map(6)
    assert britain_orig is not None and britain_new is not None
    assert len(britain_new.npcs) == len(britain_orig.npcs)
    for n0, n1 in zip(britain_orig.npcs, britain_new.npcs):
        assert n1.name == n0.name
        assert n1.role == n0.role
        assert n1.tlk_index == n0.tlk_index


def test_validation_catches_broken_references(tmp_path: Path) -> None:
    clean = create_starter_scenario()
    issues_clean = validate_project(clean)
    assert all(i.severity == "info" for i in issues_clean)

    broken = copy.deepcopy(clean)
    broken.maps[0].portals.append(PortalData(x=1, y=1, dest_map_id=999, dest_x=0, dest_y=0))
    city = broken.get_map(6)
    assert city is not None
    city.npcs[0].tlk_index = 99  # inexistant
    broken.quests[0].steps[0].target_map_id = 888

    issues = validate_project(broken)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) >= 3
    with pytest.raises(ValueError):
        compile_module(broken, tmp_path / "out_fail")


def test_boron_and_cdi_module_compile(tmp_path: Path) -> None:
    proj = create_starter_scenario()

    cfg = generate_config_b(proj)
    maps_b = generate_maps_b(proj)
    vendors_b = generate_vendors_b(proj)
    assert "module [" in cfg and "u4-save-ids" in cfg and "include %maps.b" in cfg
    assert "city " in maps_b and "shrine " in maps_b and "portal" in maps_b and "moongate" in maps_b
    assert "tavern" in vendors_b and "weapons" in vendors_b

    out_root = tmp_path / "build"
    result = compile_module(proj, out_root)
    assert result.mod_path.exists()
    assert result.build_dir.exists()
    assert (result.build_dir / "config.b").exists()
    assert (result.build_dir / "maps.b").exists()
    assert (result.build_dir / "vendors.b").exists()
    assert (result.build_dir / "world.map").stat().st_size == WORLD_MAP_SIZE
    assert (result.build_dir / "britain.ult").stat().st_size == ULT_FILE_SIZE
    assert (result.build_dir / "britain.tlk").stat().st_size % TLK_BLOCK_SIZE == 0
    assert (result.build_dir / "shrine.con").stat().st_size == CON_FILE_SIZE
    assert (result.build_dir / "shapes.ega").stat().st_size == 256 * 128

    # Vérification structure binaire CDI xu4^2 du .mod
    mod_bytes = result.mod_path.read_bytes()
    assert mod_bytes[:8] == b"\xDA\x7A\x70\x00xu4\x02"
    toc_offset, toc_len = struct.unpack_from("<II", mod_bytes, 8)
    assert toc_offset > 16
    assert toc_offset + toc_len == len(mod_bytes)
    assert toc_len % 16 == 0

    entries = {}
    for pos in range(toc_offset, toc_offset + toc_len, 16):
        magic, cdi_fmt = struct.unpack_from(">2sH", mod_bytes, pos)
        assert magic == b"\xDA\x7A"
        app_id = mod_bytes[pos + 4 : pos + 8]
        chunk_off, chunk_len = struct.unpack_from("<II", mod_bytes, pos + 8)
        assert chunk_off + chunk_len <= toc_offset
        entries[app_id] = (cdi_fmt, mod_bytes[chunk_off : chunk_off + chunk_len])

    assert b"MODI" in entries
    assert b"FNAM" in entries
    assert b"CONF" in entries
    assert any(k.startswith(b"MA") for k in entries)
    assert any(k.startswith(b"NC") for k in entries)

    # Vérifier Form 1 CDI String Table dans MODI (4 chaînes: about, author, rules, version)
    modi_fmt, modi_payload = entries[b"MODI"]
    assert modi_fmt == 0x0006
    assert modi_payload[0] == 1
    modi_count = (modi_payload[1] << 16) | (modi_payload[2] << 8) | modi_payload[3]
    assert modi_count == 4


def test_cli_validate_and_compile_only(tmp_path: Path) -> None:
    proj = create_starter_scenario()
    yaml_dir = tmp_path / "cli_scenario"
    save_project_yaml(proj, yaml_dir)
    out_dir = tmp_path / "cli_build"

    assert cli_main.main(["--validate-only", str(yaml_dir)]) == 0
    assert cli_main.main(["--compile-only", "--output-dir", str(out_dir), str(yaml_dir)]) == 0
    assert (out_dir / f"{proj.metadata.module_name}.mod").exists()
