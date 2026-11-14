"""Lecture et écriture complète des scénarios au format YAML."""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import (
    DialogueData,
    DialogueTopic,
    DungeonRoomData,
    DungeonTriggerData,
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return slug or "item"


def _encode_grid_rows(grid: List[List[int]]) -> List[str]:
    """Encode une matrice 2D en lignes hexadécimales compactes et lisibles."""
    return ["".join(f"{val & 0xFF:02x}" for val in row) for row in grid]


def _decode_grid_rows(raw_grid: Any, width: int, height: int) -> List[List[int]]:
    """Décode une matrice depuis hex-strings ou listes d'entiers."""
    grid: List[List[int]] = []
    for r_idx in range(height):
        if r_idx < len(raw_grid):
            row_val = raw_grid[r_idx]
            if isinstance(row_val, str):
                cleaned = row_val.replace(" ", "")
                row = [int(cleaned[i : i + 2], 16) for i in range(0, min(len(cleaned), width * 2), 2)]
                while len(row) < width:
                    row.append(0)
                grid.append(row)
            elif isinstance(row_val, list):
                row = [int(x) & 0xFF for x in row_val[:width]]
                while len(row) < width:
                    row.append(0)
                grid.append(row)
            else:
                grid.append([0] * width)
        else:
            grid.append([0] * width)
    return grid


def _dump_yaml(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data,
            fh,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1200,
        )


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def save_project_yaml(project: ScenarioProject, directory: str | Path) -> Path:
    """Sauvegarde tout le scénario dans un dossier structuré de fichiers YAML."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    maps_dir = root / "maps"
    npcs_dir = root / "npcs"
    dlg_dir = root / "dialogues"
    quests_dir = root / "quests"
    for d in (maps_dir, npcs_dir, dlg_dir, quests_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Nettoyer anciens YAML obsolètes pour garder le dossier propre
    for sub in (maps_dir, npcs_dir, dlg_dir):
        for old in sub.glob("*.yaml"):
            old.unlink()

    # 1. project.yaml
    project_doc = {
        "metadata": asdict(project.metadata),
        "shrines": [asdict(s) for s in project.shrines],
        "tavern_rumors": [asdict(r) for r in project.rumors],
        "map_files": [],
        "dialogue_banks": sorted(project.dialogues.keys()),
    }

    # 2. Cartes & PNJ
    for m in sorted(project.maps, key=lambda x: x.id):
        map_slug = f"{m.id:02d}_{_slugify(m.name)}"
        map_rel = f"maps/{map_slug}.yaml"
        project_doc["map_files"].append(map_rel)

        map_doc: Dict[str, Any] = {
            "id": m.id,
            "name": m.name,
            "fname": m.fname,
            "map_type": m.map_type,
            "width": m.width,
            "height": m.height,
            "levels": m.levels,
            "chunk_dim": m.chunk_dim,
            "border_behavior": m.border_behavior,
            "music": m.music,
            "city_type": m.city_type,
            "tlk_fname": m.tlk_fname,
            "shrine_virtue": m.shrine_virtue,
            "shrine_mantra": m.shrine_mantra,
            "portals": [asdict(p) for p in m.portals],
            "moongates": [asdict(mg) for mg in m.moongates],
            "labels": [asdict(lbl) for lbl in m.labels],
            "levels_grid": [_encode_grid_rows(level) for level in m.grids],
        }
        if m.map_type in ("combat", "shrine"):
            map_doc["con_starts"] = {
                "creature_x": m.con_creature_start_x,
                "creature_y": m.con_creature_start_y,
                "player_x": m.con_player_start_x,
                "player_y": m.con_player_start_y,
            }
        if m.dungeon_rooms:
            rooms_out = []
            for r in m.dungeon_rooms:
                rd = asdict(r)
                rd["grid"] = _encode_grid_rows(r.grid)
                rooms_out.append(rd)
            map_doc["dungeon_rooms"] = rooms_out

        _dump_yaml(map_doc, root / map_rel)

        if m.npcs or m.map_type == "city":
            npc_doc = {
                "map_id": m.id,
                "map_name": m.name,
                "tlk_fname": m.tlk_fname,
                "npcs": [asdict(n) for n in sorted(m.npcs, key=lambda x: x.slot_index)],
            }
            _dump_yaml(npc_doc, npcs_dir / f"{map_slug}_npcs.yaml")

    _dump_yaml(project_doc, root / "project.yaml")

    # 3. Dialogues
    for bank_name, dialogues in sorted(project.dialogues.items()):
        bank_slug = _slugify(bank_name.replace(".tlk", ""))
        dlg_doc = {
            "bank_name": bank_name,
            "dialogues": [asdict(d) for d in sorted(dialogues, key=lambda x: x.id)],
        }
        _dump_yaml(dlg_doc, dlg_dir / f"{bank_slug}.yaml")

    # 4. Quêtes
    quests_doc = {
        "quests": [asdict(q) for q in project.quests],
    }
    _dump_yaml(quests_doc, quests_dir / "quests.yaml")

    return root


def load_project_yaml(directory: str | Path) -> ScenarioProject:
    """Charge un scénario complet depuis un dossier YAML."""
    root = Path(directory)
    proj_raw = _load_yaml(root / "project.yaml") or {}
    meta_raw = proj_raw.get("metadata", {})
    metadata = ScenarioMetadata(
        title=meta_raw.get("title", "Aventure Ultima IV"),
        module_name=meta_raw.get("module_name", "Custom-Quest"),
        author=meta_raw.get("author", "Auteur"),
        version=str(meta_raw.get("version", "1.0")),
        about=meta_raw.get("about", ""),
        rules=meta_raw.get("rules", "Ultima-IV"),
    )

    shrines = [
        ShrineConfig(
            virtue=s["virtue"],
            mantra=s["mantra"],
            map_id=int(s["map_id"]),
        )
        for s in proj_raw.get("shrines", [])
    ]

    rumors = [
        TavernRumor(
            topic=r["topic"],
            price=int(r.get("price", 20)),
            text=r.get("text", ""),
            city_name=r.get("city_name", "Britain"),
        )
        for r in proj_raw.get("tavern_rumors", [])
    ]

    # Charger les PNJ par map_id
    npcs_by_map: Dict[int, List[NPCData]] = {}
    npcs_dir = root / "npcs"
    if npcs_dir.exists():
        for npc_file in sorted(npcs_dir.glob("*.yaml")):
            ndoc = _load_yaml(npc_file) or {}
            mid = int(ndoc.get("map_id", -1))
            npc_list: List[NPCData] = []
            for n in ndoc.get("npcs", []):
                sc_raw = n.get("shop_config")
                sc = None
                if isinstance(sc_raw, dict):
                    sc = ShopConfig(
                        shop_name=sc_raw.get("shop_name", "Boutique"),
                        owner_name=sc_raw.get("owner_name", "Marchand"),
                        price=int(sc_raw.get("price", 25)),
                        prices_list=[int(p) for p in sc_raw.get("prices_list", [2, 5, 6, 3, 6, 9])],
                        inventory=list(sc_raw.get("inventory", [])),
                        room_loc=[int(x) for x in sc_raw.get("room_loc", [28, 6])],
                        specialty_name=sc_raw.get("specialty_name", "Ragoût"),
                        specialty_price=int(sc_raw.get("specialty_price", 4)),
                        message=sc_raw.get("message", ""),
                    )
                npc_list.append(
                    NPCData(
                        slot_index=int(n["slot_index"]),
                        name=n.get("name", "PNJ"),
                        tile_id=int(n.get("tile_id", 82)),
                        x=int(n.get("x", 15)),
                        y=int(n.get("y", 15)),
                        movement=n.get("movement", "fixed"),
                        tlk_index=int(n.get("tlk_index", 0)),
                        role=n.get("role", "none"),
                        shop_config=sc,
                    )
                )
            npcs_by_map[mid] = npc_list

    # Charger les cartes
    maps: List[MapData] = []
    map_files = proj_raw.get("map_files") or [
        str(p.relative_to(root)) for p in sorted((root / "maps").glob("*.yaml"))
    ]
    for rel in map_files:
        mraw = _load_yaml(root / rel) or {}
        mid = int(mraw["id"])
        w = int(mraw.get("width", 32))
        h = int(mraw.get("height", 32))
        levels = int(mraw.get("levels", 1))
        grids = [_decode_grid_rows(lvl, w, h) for lvl in mraw.get("levels_grid", [])]
        portals = [
            PortalData(
                x=int(p["x"]),
                y=int(p["y"]),
                z=int(p.get("z", 0)),
                action=p.get("action", "save-enter"),
                dest_map_id=int(p.get("dest_map_id", 0)),
                dest_x=int(p.get("dest_x", 0)),
                dest_y=int(p.get("dest_y", 0)),
                dest_z=int(p.get("dest_z", 0)),
                message=p.get("message", ""),
                transport=p.get("transport", "footorhorse"),
                condition=p.get("condition", ""),
                retro_active_dest=p.get("retro_active_dest"),
            )
            for p in mraw.get("portals", [])
        ]
        moongates = [
            MoongateData(phase=int(mg["phase"]), x=int(mg["x"]), y=int(mg["y"]))
            for mg in mraw.get("moongates", [])
        ]
        labels = [
            LabelData(
                name=lbl["name"],
                x=int(lbl["x"]),
                y=int(lbl["y"]),
                z=int(lbl.get("z", 0)),
                description=lbl.get("description", ""),
            )
            for lbl in mraw.get("labels", [])
        ]
        rooms: List[DungeonRoomData] = []
        for rraw in mraw.get("dungeon_rooms", []):
            triggers = [
                DungeonTriggerData(
                    tile_id=int(t.get("tile_id", 0)),
                    trigger_x=int(t.get("trigger_x", 0)),
                    trigger_y=int(t.get("trigger_y", 0)),
                    change_x1=int(t.get("change_x1", 0)),
                    change_y1=int(t.get("change_y1", 0)),
                    change_x2=int(t.get("change_x2", 0)),
                    change_y2=int(t.get("change_y2", 0)),
                )
                for t in rraw.get("triggers", [])
            ]
            rooms.append(
                DungeonRoomData(
                    triggers=triggers,
                    monster_tiles=[int(x) for x in rraw.get("monster_tiles", [0] * 16)],
                    monster_x=[int(x) for x in rraw.get("monster_x", [0] * 16)],
                    monster_y=[int(x) for x in rraw.get("monster_y", [0] * 16)],
                    party_north_x=[int(x) for x in rraw.get("party_north_x", [5] * 8)],
                    party_north_y=[int(x) for x in rraw.get("party_north_y", [1] * 8)],
                    party_east_x=[int(x) for x in rraw.get("party_east_x", [9] * 8)],
                    party_east_y=[int(x) for x in rraw.get("party_east_y", [5] * 8)],
                    party_south_x=[int(x) for x in rraw.get("party_south_x", [5] * 8)],
                    party_south_y=[int(x) for x in rraw.get("party_south_y", [9] * 8)],
                    party_west_x=[int(x) for x in rraw.get("party_west_x", [1] * 8)],
                    party_west_y=[int(x) for x in rraw.get("party_west_y", [5] * 8)],
                    grid=_decode_grid_rows(rraw.get("grid", []), 11, 11),
                )
            )

        con_starts = mraw.get("con_starts", {})
        mdata = MapData(
            id=mid,
            name=mraw["name"],
            fname=mraw["fname"],
            map_type=mraw.get("map_type", "city"),
            width=w,
            height=h,
            levels=levels,
            chunk_dim=int(mraw.get("chunk_dim", 0)),
            border_behavior=mraw.get("border_behavior", "exit"),
            music=int(mraw.get("music", 2)),
            grids=grids,
            npcs=npcs_by_map.get(mid, []),
            portals=portals,
            moongates=moongates,
            labels=labels,
            city_type=mraw.get("city_type", "towne"),
            tlk_fname=mraw.get("tlk_fname", ""),
            shrine_virtue=mraw.get("shrine_virtue", "Honesty"),
            shrine_mantra=mraw.get("shrine_mantra", "ahm"),
            dungeon_rooms=rooms,
            con_creature_start_x=[int(x) for x in con_starts.get("creature_x", [5] * 16)],
            con_creature_start_y=[int(x) for x in con_starts.get("creature_y", [2] * 16)],
            con_player_start_x=[int(x) for x in con_starts.get("player_x", [3, 4, 5, 6, 3, 4, 5, 6])],
            con_player_start_y=[int(x) for x in con_starts.get("player_y", [8, 8, 8, 8, 9, 9, 9, 9])],
        )
        mdata.ensure_grids()
        maps.append(mdata)

    # Charger les banques de dialogues
    dialogues: Dict[str, List[DialogueData]] = {}
    dlg_dir = root / "dialogues"
    if dlg_dir.exists():
        for dlg_file in sorted(dlg_dir.glob("*.yaml")):
            ddoc = _load_yaml(dlg_file) or {}
            bank_name = ddoc.get("bank_name", dlg_file.stem + ".tlk")
            dlist: List[DialogueData] = []
            for d in ddoc.get("dialogues", []):
                topics = [
                    DialogueTopic(
                        keyword=t["keyword"],
                        response=t["response"],
                        trigger_question=bool(t.get("trigger_question", False)),
                    )
                    for t in d.get("extra_topics", [])
                ]
                dlist.append(
                    DialogueData(
                        id=int(d["id"]),
                        bank_name=bank_name,
                        name=d.get("name", "PNJ"),
                        pronoun=d.get("pronoun", "He"),
                        look=d.get("look", ""),
                        job=d.get("job", ""),
                        health=d.get("health", ""),
                        keyword1=d.get("keyword1", "A   "),
                        response1=d.get("response1", ""),
                        keyword2=d.get("keyword2", "A   "),
                        response2=d.get("response2", ""),
                        question_trigger=int(d.get("question_trigger", 0)),
                        question=d.get("question", ""),
                        yes_response=d.get("yes_response", ""),
                        no_response=d.get("no_response", ""),
                        affects_humility=bool(d.get("affects_humility", False)),
                        turn_away_prob=int(d.get("turn_away_prob", 0)),
                        extra_topics=topics,
                        notes=d.get("notes", ""),
                    )
                )
            dialogues[bank_name] = dlist

    # Charger les quêtes
    quests: List[QuestData] = []
    qfile = root / "quests" / "quests.yaml"
    if qfile.exists():
        qdoc = _load_yaml(qfile) or {}
        for q in qdoc.get("quests", []):
            steps = [
                QuestStep(
                    id=s["id"],
                    title=s.get("title", ""),
                    description=s.get("description", ""),
                    npc_name=s.get("npc_name", ""),
                    dialogue_bank=s.get("dialogue_bank", ""),
                    keyword=s.get("keyword", ""),
                    required_item_label=s.get("required_item_label", ""),
                    target_map_id=s.get("target_map_id"),
                    target_x=s.get("target_x"),
                    target_y=s.get("target_y"),
                )
                for s in q.get("steps", [])
            ]
            quests.append(
                QuestData(
                    id=q["id"],
                    title=q.get("title", "Quête"),
                    virtue=q.get("virtue", "Compassion"),
                    summary=q.get("summary", ""),
                    is_main_quest=bool(q.get("is_main_quest", True)),
                    steps=steps,
                    reward=q.get("reward", ""),
                )
            )

    return ScenarioProject(
        metadata=metadata,
        maps=maps,
        dialogues=dialogues,
        quests=quests,
        rumors=rumors,
        shrines=shrines,
    )
