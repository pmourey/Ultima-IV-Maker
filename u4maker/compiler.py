"""Validateur de scénarios, générateur Boron (config.b / maps.b / vendors.b) et compilateur .mod CDI pour xU4."""

from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .binary_io import (
    TLK_BLOCK_SIZE,
    calculate_tlk_bytes,
    encode_con,
    encode_dng,
    encode_tlk_block,
    encode_ult,
    encode_world_map,
    normalize_u4_ascii,
)
from .constants import (
    ARMORS_LIST,
    EGA_PALETTE,
    NPC_ROLES,
    QUEST_ITEM_LABELS,
    REAGENTS_NAMES,
    SHOP_ROLES,
    TILES,
    WEAPONS_LIST,
)
from .models import DialogueData, MapData, NPCData, ScenarioProject, TavernRumor
from .tileset_renderer import TilesetCache

# Mapping rôle Python -> rôle Boron dans maps.b (tools/pack-xu4.b)
BORON_CITY_ROLES = {
    "companion",
    "weaponsvendor",
    "armorvendor",
    "foodvendor",
    "tavernkeeper",
    "reagentsvendor",
    "healer",
    "innkeeper",
    "guildvendor",
    "horsevendor",
    "lordbritish",
    "hawkwind",
}

ROLE_TO_VENDOR_KEY = {
    "weaponsvendor": "weapons",
    "armorvendor": "armor",
    "foodvendor": "food",
    "tavernkeeper": "tavern",
    "reagentsvendor": "reagents",
    "healer": "healer",
    "innkeeper": "inn",
    "guildvendor": "guild",
    "horsevendor": "stable",
}


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    category: str
    message: str


@dataclass
class BuildResult:
    build_dir: Path
    mod_path: Path
    files_written: List[Path]
    issues: List[ValidationIssue]


def _boron_str(text: str) -> str:
    clean = normalize_u4_ascii(text).decode("ascii")
    clean = clean.replace("^", "^^").replace('"', '^"').replace("\n", "^/")
    return f'"{clean}"'


def _boron_city_key(city_name: str) -> str:
    clean = normalize_u4_ascii(city_name).decode("ascii").strip()
    return "-".join(clean.split()) or "Britain"


def validate_project(project: ScenarioProject) -> List[ValidationIssue]:
    """Vérifie la cohérence complète du scénario avant compilation."""
    issues: List[ValidationIssue] = []

    if not project.metadata.module_name.strip():
        issues.append(ValidationIssue("error", "Métadonnées", "Le nom technique du module ne doit pas être vide."))
    elif len(project.metadata.module_name) > 35:
        issues.append(
            ValidationIssue(
                "error",
                "Métadonnées",
                "Le nom du module + '.mod' doit faire moins de 40 caractères pour xU4.",
            )
        )

    if not project.maps:
        issues.append(ValidationIssue("error", "Cartes", "Le scénario ne contient aucune carte."))
        return issues

    map_ids = {m.id for m in project.maps}
    if 0 not in map_ids:
        issues.append(ValidationIssue("warning", "Cartes", "Aucune carte Monde avec l'ID 0 n'est définie."))

    # Index global des dialogues et des labels
    all_labels = {lbl.name for m in project.maps for lbl in m.labels}
    all_npc_names = set()
    keywords_by_npc: Dict[str, set] = {}

    for bank_name, dlgs in project.dialogues.items():
        if len(dlgs) > 16:
            issues.append(
                ValidationIssue(
                    "warning",
                    "Dialogues",
                    f"La banque '{bank_name}' contient {len(dlgs)} dialogues (les .TLK originaux sont limités à 16).",
                )
            )
        seen_ids = set()
        for d in dlgs:
            if d.id in seen_ids:
                issues.append(
                    ValidationIssue("error", "Dialogues", f"ID en double {d.id} dans la banque '{bank_name}'.")
                )
            seen_ids.add(d.id)
            total_bytes, _ = calculate_tlk_bytes(d)
            if total_bytes > TLK_BLOCK_SIZE:
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Dialogues",
                        f"'{d.name}' ({bank_name} #{d.id}) fait {total_bytes}/288 octets et sera tronqué à l'export .TLK.",
                    )
                )
            nkey = d.name.strip().lower()
            all_npc_names.add(nkey)
            kws = keywords_by_npc.setdefault(nkey, set())
            for kw in (d.keyword1, d.keyword2):
                kclean = normalize_u4_ascii(kw).decode("ascii").strip().upper()
                if kclean and kclean != "A":
                    kws.add(kclean[:4])
            for ext in d.extra_topics:
                kclean = normalize_u4_ascii(ext.keyword).decode("ascii").strip().upper()
                if kclean:
                    kws.add(kclean[:4])

    for m in project.maps:
        if m.map_type == "world" and (m.width != 256 or m.height != 256):
            issues.append(
                ValidationIssue("error", "Cartes", f"La carte monde '{m.name}' doit mesurer 256x256.")
            )
        elif m.map_type == "city" and (m.width != 32 or m.height != 32):
            issues.append(
                ValidationIssue("error", "Cartes", f"La ville '{m.name}' doit mesurer 32x32 pour .ULT.")
            )
        elif m.map_type in ("combat", "shrine") and (m.width != 11 or m.height != 11):
            issues.append(
                ValidationIssue("error", "Cartes", f"La carte '{m.name}' doit mesurer 11x11 pour .CON.")
            )
        elif m.map_type == "dungeon" and (m.width != 8 or m.height != 8 or m.levels != 8):
            issues.append(
                ValidationIssue("error", "Cartes", f"Le donjon '{m.name}' doit mesurer 8x8 sur 8 niveaux pour .DNG.")
            )

        # Portails
        for p in m.portals:
            dest = project.get_map(p.dest_map_id)
            if dest is None:
                issues.append(
                    ValidationIssue(
                        "error",
                        "Portails",
                        f"Carte '{m.name}' : portail en ({p.x},{p.y}) pointe vers une carte inexistante ID {p.dest_map_id}.",
                    )
                )
            else:
                if not (0 <= p.dest_x < dest.width and 0 <= p.dest_y < dest.height):
                    issues.append(
                        ValidationIssue(
                            "error",
                            "Portails",
                            f"Carte '{m.name}' : portail ({p.x},{p.y}) -> destination ({p.dest_x},{p.dest_y}) hors limites de '{dest.name}'.",
                        )
                    )

        # PNJ et liens TLK
        bank = project.dialogues.get(m.tlk_fname, [])
        bank_ids = {d.id for d in bank}
        used_slots = set()
        for npc in m.npcs:
            if npc.slot_index in used_slots:
                issues.append(
                    ValidationIssue(
                        "error",
                        "PNJ",
                        f"Ville '{m.name}' : emplacement PNJ #{npc.slot_index + 1} utilisé plusieurs fois.",
                    )
                )
            used_slots.add(npc.slot_index)
            if not (0 <= npc.x < m.width and 0 <= npc.y < m.height):
                issues.append(
                    ValidationIssue(
                        "error",
                        "PNJ",
                        f"Ville '{m.name}' : PNJ '{npc.name}' hors carte ({npc.x},{npc.y}).",
                    )
                )
            if npc.tlk_index > 0:
                if not m.tlk_fname:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "PNJ",
                            f"Ville '{m.name}' : PNJ '{npc.name}' référence dialogue #{npc.tlk_index} mais aucun fichier .TLK n'est associé.",
                        )
                    )
                elif npc.tlk_index not in bank_ids:
                    issues.append(
                        ValidationIssue(
                            "error",
                            "PNJ",
                            f"Ville '{m.name}' : PNJ '{npc.name}' pointe vers le dialogue #{npc.tlk_index} absent de '{m.tlk_fname}'.",
                        )
                    )

    # Quêtes
    for q in project.quests:
        if not q.steps:
            issues.append(
                ValidationIssue("warning", "Quêtes", f"La quête '{q.title}' ne contient aucune étape.")
            )
        for st in q.steps:
            if st.required_item_label and st.required_item_label not in all_labels:
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Quêtes",
                        f"Quête '{q.title}' / Étape '{st.title}' : l'objet '{st.required_item_label}' n'est placé sur aucune carte.",
                    )
                )
            if st.npc_name:
                nkey = st.npc_name.strip().lower()
                if nkey not in all_npc_names:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            "Quêtes",
                            f"Quête '{q.title}' / Étape '{st.title}' : le PNJ '{st.npc_name}' est introuvable dans les dialogues.",
                        )
                    )
                elif st.keyword:
                    kw_norm = normalize_u4_ascii(st.keyword).decode("ascii").strip().upper()[:4]
                    builtin_kws = {"NAME", "LOOK", "JOB", "HEAL", "GIVE", "JOIN", "BYE", "HELP"}
                    if kw_norm not in builtin_kws and kw_norm not in keywords_by_npc.get(nkey, set()):
                        issues.append(
                            ValidationIssue(
                                "warning",
                                "Quêtes",
                                f"Quête '{q.title}' / Étape '{st.title}' : le mot-clé '{st.keyword}' n'est pas configuré sur '{st.npc_name}'.",
                            )
                        )
            if st.target_map_id is not None and project.get_map(st.target_map_id) is None:
                issues.append(
                    ValidationIssue(
                        "error",
                        "Quêtes",
                        f"Quête '{q.title}' : carte cible ID {st.target_map_id} introuvable.",
                    )
                )

    if not issues:
        issues.append(
            ValidationIssue("info", "Validation", "Aucune erreur détectée. Le scénario est prêt à être compilé !")
        )
    return issues


def _normalize_rules_version(rules: str) -> str:
    """Normalise le champ rules pour déclarer l'extension de module xU4 1.4."""
    cleaned = (rules or "Ultima-IV").strip()
    if cleaned in ("Ultima-IV", ""):
        return "Ultima-IV/1.4"
    return cleaned


def generate_config_b(project: ScenarioProject) -> str:
    """Génère le fichier config.b Boron conforme à module/Ultima-IV/config.b."""
    meta = project.metadata
    rules_val = _normalize_rules_version(meta.rules)
    lines = [
        "module [",
        f"    author: {_boron_str(meta.author)}",
        "    about: {{",
        f"        {normalize_u4_ascii(meta.about).decode('ascii')}",
        "    }}",
        f"    version: {_boron_str(meta.version)}",
        f"    rules: {_boron_str(rules_val)}",
        "]",
        "",
        "armors: [",
        '    "Skin"         96',
        '    "Cloth"       128',
        '    "Leather"     144   not  [mage]',
        '    "Chain Mail"  160   only [fighter tinker paladin]',
        '    "Plate Mail"  176   only [fighter tinker paladin]',
        '    "Magic Chain" 192   only [fighter paladin]',
        '    "Magic Plate" 208   only [paladin]',
        '    "Mystic Robe" 248',
        "]",
        "",
        "weapons: [",
        '    "HND" "Hands"        1     8',
        '    "STF" "Staff"        1    16',
        '    "DAG" "Dagger"      10    24    losewhenranged',
        '    "SLN" "Sling"       10    32',
        '    "MAC" "Mace"         1    40    not [mage]',
        '    "AXE" "Axe"          1    48    not [mage druid]',
        '    "SWD" "Sword"        1    64    not [mage druid]',
        '    "BOW" "Bow"         10    40    not [mage shepherd]',
        '    "XBO" "Crossbow"    10    56    not [mage shepherd]',
        '    "OIL" "Flaming Oil"  9    64    lose choosedistance leavetile: fire_field',
        '    "HAL" "Halberd"      2    96    absolute_range attackthroughobjects dontshowtravel only [fighter tinker paladin]',
        '    "+AX" "Magic Axe"   10    96    magic returns only [tinker paladin]',
        '    "+SW" "Magic Sword"  1   128    magic only [fighter tinker paladin ranger]',
        '    "+BO" "Magic Bow"   10    80    magic not  [mage fighter shepherd]',
        '    "WND" "Magic Wand"  10   160    magic only [mage bard druid] hittile: magic_flash misstile: magic_flash',
        '   "^^SW" "Mystic Sword" 1   255    magic',
        "]",
        "",
        "ega-palette: [",
    ]
    for r, g, b in EGA_PALETTE:
        lines.append(f"    {r:3d}, {g:3d}, {b:3d}")
    lines.extend(
        [
            "]",
            "",
            "u4-save-ids: [",
        ]
    )

    # Construire u4-save-ids à partir de constants.TILES
    idx = 0
    while idx < len(TILES):
        t = TILES[idx]
        if t.frames > 1:
            lines.append(f"    {t.frames} {t.name}")
            idx += t.frames
        else:
            lines.append(f"    {t.name}")
            idx += 1

    lines.extend(
        [
            "]",
            "",
            "include %maps.b",
            "include %vendors.b",
            "",
        ]
    )
    return "\n".join(lines)


def generate_maps_b(project: ScenarioProject) -> str:
    """Génère le fichier maps.b Boron pour toutes les cartes, portails, rôles, moongates et labels."""
    lines = ["maps: ["]
    for m in sorted(project.maps, key=lambda x: x.id):
        attrs = [
            f"id: {m.id}",
            f"type: {m.map_type}",
            f'fname: "{m.fname}"',
            f"width: {m.width}",
            f"height: {m.height}",
            f"levels: {m.levels}",
        ]
        if m.chunk_dim > 0:
            attrs.append(f"chunk-dim: {m.chunk_dim}")
        attrs.append(f"borderbehavior: {m.border_behavior}")
        if m.map_type == "dungeon":
            attrs.append("firstperson: true")
        elif m.map_type == "combat":
            attrs.append("nolineofsight: true")
        attrs.append(f"music: {m.music}")

        has_block = bool(
            m.portals
            or m.moongates
            or m.labels
            or m.map_type in ("city", "dungeon", "shrine")
        )
        if not has_block:
            lines.append(f"    map ({' '.join(attrs)})")
            continue

        lines.append(f"    map ({' '.join(attrs)}) [")

        if m.map_type == "city":
            tlk_name = m.tlk_fname or f"{Path(m.fname).stem}.tlk"
            city_roles = [
                n for n in m.npcs if n.role in BORON_CITY_ROLES and n.role != "none"
            ]
            if city_roles:
                lines.append(
                    f'        city (name: {_boron_str(m.name)} type: {m.city_type} tlk_fname: "{tlk_name}") ['
                )
                lines.append("            roles [")
                for n in sorted(city_roles, key=lambda x: x.slot_index):
                    lines.append(f"                {n.role} {n.slot_index + 1}")
                lines.append("            ]")
                lines.append("        ]")
            else:
                lines.append(
                    f'        city (name: {_boron_str(m.name)} type: {m.city_type} tlk_fname: "{tlk_name}")'
                )
        elif m.map_type == "dungeon":
            n_rooms = max(16, len(m.dungeon_rooms))
            lines.append(f"        dungeon (name: {_boron_str(m.name)} rooms: {n_rooms})")
        elif m.map_type == "shrine":
            lines.append(
                f"        shrine (virtue: {_boron_str(m.shrine_virtue)} mantra: {m.shrine_mantra.lower()})"
            )

        if m.portals:
            lines.append("        portals [")
            for p in m.portals:
                src = f"{p.x},{p.y},{p.z}" if m.map_type == "dungeon" or p.z > 0 else f"{p.x},{p.y}"
                dst = (
                    f"{p.dest_map_id},{p.dest_x},{p.dest_y},{p.dest_z}"
                    if p.dest_z > 0
                    else f"{p.dest_map_id},{p.dest_x},{p.dest_y}"
                )
                extras = []
                if p.condition:
                    extras.append(f"condition: {p.condition}")
                if p.transport and p.transport != "footorhorse":
                    extras.append(f"transport: {p.transport}")
                elif m.map_type == "world" and p.transport == "footorhorse":
                    extras.append("transport: footorhorse")
                if p.message:
                    extras.append(f"message: {_boron_str(p.message)}")
                if p.retro_active_dest and len(p.retro_active_dest) >= 3:
                    rad = p.retro_active_dest
                    extras.append(f"retroActiveDest: {rad[0]},{rad[1]},{rad[2]}")
                extra_txt = (" " + " ".join(extras)) if extras else ""
                lines.append(f"            {src} {p.action} {dst}{extra_txt}")
            lines.append("        ]")

        if m.moongates:
            lines.append("        moongates [")
            for mg in sorted(m.moongates, key=lambda x: x.phase):
                lines.append(f"            {mg.phase},{mg.x},{mg.y}")
            lines.append("        ]")

        if m.labels:
            lines.append("        labels [")
            for lbl in m.labels:
                if lbl.z > 0:
                    lines.append(f"            {lbl.name} {lbl.x},{lbl.y},{lbl.z}")
                else:
                    lines.append(f"            {lbl.name} {lbl.x},{lbl.y}")
            lines.append("        ]")

        lines.append("    ]")
    lines.append("]")
    return "\n".join(lines) + "\n"


def generate_vendors_b(project: ScenarioProject) -> str:
    """Génère le fichier vendors.b Boron incluant boutiques personnalisées et rumeurs de taverne."""
    # Collecter les boutiques personnalisées par type de vendeur
    by_vendor_type: Dict[str, List[Tuple[str, NPCData]]] = {v: [] for v in ROLE_TO_VENDOR_KEY.values()}
    for m in project.maps:
        if m.map_type != "city":
            continue
        ckey = _boron_city_key(m.name)
        for npc in m.npcs:
            vkey = ROLE_TO_VENDOR_KEY.get(npc.role)
            if vkey and npc.shop_config is not None:
                by_vendor_type[vkey].append((ckey, npc))

    lines = [
        "vendors: [",
        "random/seed 'clock",
        "=>: func [msg data] [>> construct msg data]",
        "",
        "; Configuration générée automatiquement par Ultima IV Maker",
    ]

    # Rumeurs de taverne personnalisées
    lines.append("custom-rumors: [")
    if project.rumors:
        for r in project.rumors:
            t_clean = normalize_u4_ascii(r.topic).decode("ascii").strip().lower()
            lines.append(f"    {_boron_str(t_clean)} [")
            lines.append(f"        price: {r.price}")
            lines.append(f"        city: {_boron_str(r.city_name)}")
            lines.append(f"        text: {_boron_str(r.text)}")
            lines.append("    ]")
    lines.append("]")
    lines.append("")

    # Locales des boutiques configurées par l'utilisateur
    lines.append("vendor-locales: [")
    for vtype, entries in by_vendor_type.items():
        if not entries:
            continue
        lines.append(f"    {vtype} [")
        for ckey, npc in entries:
            sc = npc.shop_config
            assert sc is not None
            lines.append(f"        {ckey} [")
            lines.append(f"            shop: {_boron_str(sc.shop_name)}")
            lines.append(f"            owner: {_boron_str(sc.owner_name or npc.name)}")
            lines.append(f"            price: {sc.price}")
            if vtype in ("weapons", "armor") and sc.inventory:
                lines.append(f"            stock: [{' '.join(sc.inventory)}]")
            elif vtype == "reagents" and sc.prices_list:
                plist = ",".join(str(x) for x in sc.prices_list[:6])
                lines.append(f"            prices: {plist}")
            elif vtype == "tavern":
                lines.append(f"            specialty: {_boron_str(sc.specialty_name)}")
                lines.append(f"            spec_price: {sc.specialty_price}")
            elif vtype == "inn" and len(sc.room_loc) >= 2:
                lines.append(f"            room-loc: {sc.room_loc[0]},{sc.room_loc[1]}")
            lines.append("        ]")
        lines.append("    ]")
    lines.append("]")
    lines.append("]")
    return "\n".join(lines) + "\n"


def _build_cdi_string_table_form1(strings: List[str]) -> bytes:
    """Construit une CDI String Table Form 1 compatible src/support/cdi.c."""
    store = bytearray()
    offsets: List[int] = []
    for s in strings:
        offsets.append(len(store))
        store.extend(normalize_u4_ascii(s))
        store.append(0)
    count = len(strings)
    header = bytes([1, (count >> 16) & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    index_bytes = bytearray()
    for off in offsets:
        index_bytes.extend(struct.pack("<H", off))
    return header + bytes(index_bytes) + bytes(store)


def _serialize_conf_with_boron(build_dir: Path) -> Optional[bytes]:
    """Sérialise le chunk CONF au format binaire Boron via pack-xu4.b si disponible."""
    project_root = Path(__file__).resolve().parents[1]
    boron_candidates = [
        project_root / "xu4-1.4.3" / "boron" / "boron",
        *( [Path(p)] if (p := shutil.which("boron")) else [] ),
    ]
    boron_bin = next((c for c in boron_candidates if c.is_file()), None)
    pack_script = project_root / "xu4-1.4.3" / "tools" / "pack-xu4.b"
    if boron_bin is None or not pack_script.is_file():
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_mod = Path(tmp_dir) / "serialized.mod"
            subprocess.run(
                [str(boron_bin), "-s", str(pack_script), str(build_dir), "-o", str(tmp_mod)],
                check=True,
                capture_output=True,
            )
            mod_bytes = tmp_mod.read_bytes()
            if len(mod_bytes) < 16 or mod_bytes[:8] != b"\xDA\x7A\x70\x00xu4\x02":
                return None
            toc_offset, toc_len = struct.unpack_from("<II", mod_bytes, 8)
            for pos in range(toc_offset, toc_offset + toc_len, 16):
                app_id = mod_bytes[pos + 4 : pos + 8]
                if app_id == b"CONF":
                    chunk_off, chunk_len = struct.unpack_from("<II", mod_bytes, pos + 8)
                    return mod_bytes[chunk_off : chunk_off + chunk_len]
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def build_cdi_mod_package(
    project: ScenarioProject,
    chunks: List[Tuple[int, bytes, bytes]],
    output_mod_path: Path,
) -> Path:
    """Empaquette les chunks au format binaire CDI xu4^2 (.mod)."""
    output_mod_path.parent.mkdir(parents=True, exist_ok=True)
    buf = bytearray()
    # Header: DA 7A 70 00 + "xu4\x02" + u32 toc_offset + u32 toc_len
    buf.extend(b"\xDA\x7A\x70\x00xu4\x02\x00\x00\x00\x00\x00\x00\x00\x00")

    toc = bytearray()
    for cdi_format, app_id, data in chunks:
        if len(app_id) != 4:
            raise ValueError(f"app_id doit faire 4 octets, reçu {app_id!r}")
        offset = len(buf)
        buf.extend(data)
        toc.extend(b"\xDA\x7A")
        toc.extend(struct.pack(">H", cdi_format))
        toc.extend(app_id)
        toc.extend(struct.pack("<II", offset, len(data)))

    toc_offset = len(buf)
    toc_len = len(toc)
    buf.extend(toc)
    struct.pack_into("<II", buf, 8, toc_offset, toc_len)

    output_mod_path.write_bytes(bytes(buf))
    return output_mod_path


def compile_module(
    project: ScenarioProject,
    output_root: str | Path,
    tileset: Optional[TilesetCache] = None,
) -> BuildResult:
    """Compile un ScenarioProject YAML en module complet + archive .mod jouable pour xU4."""
    issues = validate_project(project)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        msg = "\n".join(f"- [{e.category}] {e.message}" for e in errors)
        raise ValueError(f"Impossible de compiler le module suite à des erreurs :\n{msg}")

    out_root = Path(output_root)
    mod_slug = project.metadata.module_name.strip() or "Custom-Quest"
    build_dir = out_root / mod_slug
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    files_written: List[Path] = []
    cdi_chunks: List[Tuple[int, bytes, bytes]] = []
    file_names: List[str] = []

    # 1. Fichiers Boron (.b)
    config_b_text = generate_config_b(project)
    maps_b_text = generate_maps_b(project)
    vendors_b_text = generate_vendors_b(project)

    for fname, txt in [
        ("config.b", config_b_text),
        ("maps.b", maps_b_text),
        ("vendors.b", vendors_b_text),
    ]:
        p = build_dir / fname
        p.write_text(txt, encoding="utf-8")
        files_written.append(p)

    # 2. SHAPES.EGA (tuiles 16x16 4-bit)
    tcache = tileset or TilesetCache()
    shapes_bytes = project.custom_shapes_ega or tcache.export_shapes_ega_bytes()
    shapes_path = build_dir / "shapes.ega"
    shapes_path.write_bytes(shapes_bytes)
    files_written.append(shapes_path)
    file_names.append("shapes.ega")

    # 3. Cartes binaires (.MAP, .ULT, .DNG, .CON)
    for m in sorted(project.maps, key=lambda x: x.id):
        m.ensure_grids()
        fpath = build_dir / m.fname
        if m.map_type == "world":
            raw = encode_world_map(m)
        elif m.map_type == "city":
            raw = encode_ult(m)
        elif m.map_type == "dungeon":
            raw = encode_dng(m)
        else:
            raw = encode_con(m)
        fpath.write_bytes(raw)
        files_written.append(fpath)
        file_names.append(m.fname)
        app_id = b"MA" + struct.pack(">H", m.id & 0xFFFF)
        cdi_chunks.append((0x1FC0, app_id, raw))

    # 4. Banques de dialogues (.TLK)
    for idx, (bank_name, dlgs) in enumerate(sorted(project.dialogues.items())):
        if not dlgs:
            continue
        tpath = build_dir / bank_name
        raw_tlk = bytearray()
        for d in sorted(dlgs, key=lambda x: x.id)[:16]:
            raw_tlk.extend(encode_tlk_block(d, strict=False))
        tpath.write_bytes(bytes(raw_tlk))
        files_written.append(tpath)
        file_names.append(bank_name)
        app_id = b"NC" + struct.pack(">H", idx & 0xFFFF)
        cdi_chunks.append((0x4007, app_id, bytes(raw_tlk)))

    # 5. Guide d'installation / lancement xU4
    readme_txt = (
        f"Module Ultima IV Maker : {project.metadata.title} (v{project.metadata.version})\n"
        f"Auteur : {project.metadata.author}\n\n"
        f"Contenu généré dans ce dossier :\n"
        f"- Scripts Boron xU4 : config.b, maps.b, vendors.b\n"
        f"- Assets binaires Ultima IV : world.map, *.ult, *.tlk, *.dng, *.con, shapes.ega\n"
        f"- Archive CDI : {mod_slug}.mod\n\n"
        f"Utilisation avec xU4 :\n"
        f"1) Copier {mod_slug}.mod dans le dossier modules de xU4 et lancer : xu4 -m {mod_slug}.mod\n"
        f"2) Ou compiler directement via Boron avec : ./tools/pack-xu4.b {mod_slug}\n"
        f"3) Ou copier les fichiers .ULT / .TLK / .MAP / .DNG / .CON dans un dossier Ultima IV DOS compatible xU4.\n"
    )
    rpath = build_dir / "README_MODULE.txt"
    rpath.write_text(readme_txt, encoding="utf-8")
    files_written.append(rpath)

    # 6. Chunks MODI, FNAM, CONF et écriture du fichier .mod CDI
    meta = project.metadata
    rules_val = _normalize_rules_version(meta.rules)
    # Ordre ModInfoValues dans src/module.c : about, author, rules, version
    modi_data = _build_cdi_string_table_form1(
        [meta.about, meta.author, rules_val, meta.version]
    )
    fnam_data = _build_cdi_string_table_form1(file_names)
    conf_data = _serialize_conf_with_boron(build_dir)
    if conf_data is None:
        conf_data = normalize_u4_ascii(config_b_text + "\n" + maps_b_text + "\n" + vendors_b_text)

    all_chunks = (
        cdi_chunks
        + [
            (0x0006, b"MODI", modi_data),
            (0x0006, b"FNAM", fnam_data),
            (0x7FC0, b"CONF", conf_data),
        ]
    )
    mod_path = out_root / f"{mod_slug}.mod"
    build_cdi_mod_package(project, all_chunks, mod_path)
    files_written.append(mod_path)

    return BuildResult(
        build_dir=build_dir,
        mod_path=mod_path,
        files_written=files_written,
        issues=issues,
    )
