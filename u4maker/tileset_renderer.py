"""Décodeur SHAPES.EGA et moteur de rendu EGA 16x16 pour les 256 tuiles Ultima IV."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw
from PySide6.QtGui import QImage, QPixmap

from .constants import EGA_PALETTE

# Correspondance exacte couleur RGB -> index EGA (0..15)
_PALETTE_INDEX: Dict[Tuple[int, int, int], int] = {rgb: idx for idx, rgb in enumerate(EGA_PALETTE)}

# Dessins 5x7 simplifiés pour les lettres A..Z sur tuiles 96..121
_FONT_5X7: Dict[str, List[str]] = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#..##", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "#..#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", ".#.#.", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
    "Y": ["#...#", ".#.#.", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
}


def load_shapes_ega(path: str | Path) -> List[Image.Image]:
    """Charge un fichier SHAPES.EGA (32 768 octets -> 256 tuiles 16x16 RGB)."""
    raw = Path(path).read_bytes()
    if len(raw) < 256 * 128:
        raise ValueError(f"SHAPES.EGA invalide : {len(raw)} octets (attendu 32768)")
    images: List[Image.Image] = []
    for tid in range(256):
        offset = tid * 128
        img = Image.new("RGB", (16, 16))
        px = img.load()
        for y in range(16):
            row_off = offset + y * 8
            for x_pair in range(8):
                b = raw[row_off + x_pair]
                c_left = EGA_PALETTE[(b >> 4) & 0x0F]
                c_right = EGA_PALETTE[b & 0x0F]
                px[x_pair * 2, y] = c_left
                px[x_pair * 2 + 1, y] = c_right
        images.append(img)
    return images


def _nearest_ega_index(rgb: Tuple[int, int, int]) -> int:
    if rgb in _PALETTE_INDEX:
        return _PALETTE_INDEX[rgb]
    best_idx = 0
    best_dist = 10**9
    for idx, (er, eg, eb) in enumerate(EGA_PALETTE):
        dist = (rgb[0] - er) ** 2 + (rgb[1] - eg) ** 2 + (rgb[2] - eb) ** 2
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def encode_shapes_ega(images: List[Image.Image]) -> bytes:
    """Encode 256 images 16x16 en format binaire SHAPES.EGA (32 768 octets)."""
    if len(images) != 256:
        raise ValueError(f"Il faut exactement 256 tuiles pour SHAPES.EGA (reçu {len(images)})")
    out = bytearray(256 * 128)
    for tid, img in enumerate(images):
        rgb_img = img.convert("RGB").resize((16, 16), Image.Resampling.NEAREST)
        px = rgb_img.load()
        base = tid * 128
        for y in range(16):
            row_off = base + y * 8
            for x_pair in range(8):
                left = _nearest_ega_index(px[x_pair * 2, y])
                right = _nearest_ega_index(px[x_pair * 2 + 1, y])
                out[row_off + x_pair] = ((left & 0x0F) << 4) | (right & 0x0F)
    return bytes(out)


def save_shapes_ega(images: List[Image.Image], path: str | Path) -> None:
    Path(path).write_bytes(encode_shapes_ega(images))


def _c(idx: int) -> Tuple[int, int, int]:
    return EGA_PALETTE[idx]


def _new_tile(bg: int = 0) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (16, 16), _c(bg))
    return img, ImageDraw.Draw(img)


def _draw_sprite_pattern(
    draw: ImageDraw.ImageDraw,
    pattern: List[str],
    colormap: Dict[str, int],
    ox: int = 0,
    oy: int = 0,
) -> None:
    for y, row in enumerate(pattern):
        for x, ch in enumerate(row):
            if ch in colormap:
                draw.point((ox + x, oy + y), fill=_c(colormap[ch]))


def _draw_humanoid(
    bg: int,
    head_c: int,
    body_c: int,
    accent_c: int,
    frame: int = 0,
    crown: bool = False,
    weapon: bool = False,
    staff: bool = False,
) -> Image.Image:
    img, d = _new_tile(bg)
    # Tête
    if crown:
        d.rectangle([5, 1, 10, 2], fill=_c(14))
        d.point((5, 0), fill=_c(14))
        d.point((8, 0), fill=_c(14))
        d.point((10, 0), fill=_c(14))
    d.rectangle([6, 3, 9, 5], fill=_c(head_c))
    d.point((7, 4), fill=_c(0))
    d.point((8, 4), fill=_c(0))
    # Torse
    d.rectangle([5, 6, 10, 10], fill=_c(body_c))
    d.line([5, 7, 10, 7], fill=_c(accent_c))
    # Bras animés
    arm_y = 7 if frame % 2 == 0 else 8
    d.rectangle([3, arm_y, 4, arm_y + 2], fill=_c(body_c))
    d.rectangle([11, arm_y, 12, arm_y + 2], fill=_c(body_c))
    # Jambes animées
    if frame % 2 == 0:
        d.rectangle([5, 11, 6, 14], fill=_c(accent_c))
        d.rectangle([9, 11, 10, 14], fill=_c(accent_c))
    else:
        d.rectangle([4, 11, 6, 14], fill=_c(accent_c))
        d.rectangle([9, 11, 11, 14], fill=_c(accent_c))
    if weapon:
        d.line([13, 2, 13, 9], fill=_c(15))
        d.line([12, 8, 14, 8], fill=_c(14))
    if staff:
        d.line([2, 2, 2, 14], fill=_c(6))
        d.point((2, 2), fill=_c(11))
    return img


def _draw_monster_sprite(primary: int, secondary: int, eye: int, frame: int, shape: str) -> Image.Image:
    img, d = _new_tile(0)
    bob = 1 if (frame % 2 == 1) else 0
    flap = 1 if (frame >= 2) else 0
    if shape == "winged":
        # Ailes + corps (bat, dragon, balron, daemon)
        d.polygon([(1, 4 + flap), (5, 7), (2, 10)], fill=_c(secondary))
        d.polygon([(14, 4 + flap), (10, 7), (13, 10)], fill=_c(secondary))
        d.rectangle([5, 4 + bob, 10, 12 + bob], fill=_c(primary))
        d.rectangle([6, 2 + bob, 9, 5 + bob], fill=_c(primary))
        d.point((6, 3 + bob), fill=_c(eye))
        d.point((9, 3 + bob), fill=_c(eye))
        d.rectangle([6, 13, 7, 15], fill=_c(secondary))
        d.rectangle([8, 13, 9, 15], fill=_c(secondary))
    elif shape == "crawler":
        # Rat, spider, slime, python
        d.ellipse([3, 6 + bob, 12, 12 + bob], fill=_c(primary))
        d.ellipse([5, 7 + bob, 10, 10 + bob], fill=_c(secondary))
        d.point((5, 8 + bob), fill=_c(eye))
        d.point((10, 8 + bob), fill=_c(eye))
        d.line([2, 12, 4, 14 - flap], fill=_c(secondary))
        d.line([13, 12, 11, 14 - flap], fill=_c(secondary))
        d.line([4, 13, 6, 15], fill=_c(secondary))
        d.line([11, 13, 9, 15], fill=_c(secondary))
    elif shape == "eye":
        # Gazer, wisp, ghost, phantom
        d.ellipse([3, 3 + bob, 12, 12 + bob], fill=_c(primary))
        d.ellipse([5, 5 + bob, 10, 10 + bob], fill=_c(15))
        d.rectangle([7, 7 + bob, 8, 8 + bob], fill=_c(eye))
        for tx in (4, 7, 10, 12):
            d.line([tx, 12 + bob, tx + (1 if flap else -1), 15], fill=_c(secondary))
    else:
        # Bipede monstre (orc, skeleton, troll, ettin, cyclops, liche, etc.)
        d.rectangle([5, 2 + bob, 10, 6 + bob], fill=_c(primary))
        d.point((6, 4 + bob), fill=_c(eye))
        d.point((9, 4 + bob), fill=_c(eye))
        d.rectangle([4, 6 + bob, 11, 11 + bob], fill=_c(secondary))
        d.rectangle([2, 6 + flap, 3, 10 + flap], fill=_c(primary))
        d.rectangle([12, 6 + (1 - flap), 13, 10 + (1 - flap)], fill=_c(primary))
        d.rectangle([5, 12, 6, 15], fill=_c(primary))
        d.rectangle([9, 12, 10, 15], fill=_c(primary))
    return img


def generate_builtin_ega_tileset() -> List[Image.Image]:
    """Génère un jeu complet et fidèle de 256 tuiles EGA 16x16 Ultima IV."""
    tiles: List[Image.Image] = []

    for tid in range(256):
        img, d = _new_tile(0)

        if tid == 0:  # sea
            img, d = _new_tile(1)
            for y in (3, 9, 14):
                for x in range(1, 15, 4):
                    d.point((x, y), fill=_c(9))
                    d.point((x + 1, y - 1), fill=_c(9))
        elif tid == 1:  # water
            img, d = _new_tile(1)
            for y in (2, 6, 10, 14):
                for x in range(0, 16, 4):
                    d.line([x, y, x + 2, y], fill=_c(11))
        elif tid == 2:  # shallows
            img, d = _new_tile(9)
            for y in (3, 8, 13):
                for x in range(1, 15, 3):
                    d.line([x, y, x + 1, y], fill=_c(11))
                    d.point((x, y + 1), fill=_c(1))
        elif tid == 3:  # swamp
            img, d = _new_tile(2)
            for y in (3, 7, 11, 14):
                d.line([2, y, 6, y], fill=_c(5))
                d.line([9, y - 1, 13, y - 1], fill=_c(10))
            for px, py in [(4, 5), (11, 9), (6, 13)]:
                d.point((px, py), fill=_c(13))
        elif tid == 4:  # grass
            img, d = _new_tile(2)
            for px, py in [(2, 3), (7, 2), (12, 4), (4, 8), (10, 9), (14, 11), (3, 13), (8, 14)]:
                d.point((px, py), fill=_c(10))
                d.point((px + 1, py - 1), fill=_c(10))
        elif tid == 5:  # brush
            img, d = _new_tile(2)
            for cx, cy in [(4, 5), (11, 4), (7, 10), (3, 13), (12, 13)]:
                d.ellipse([cx - 2, cy - 2, cx + 2, cy + 1], fill=_c(10), outline=_c(0))
                d.point((cx, cy - 1), fill=_c(6))
        elif tid == 6:  # forest
            img, d = _new_tile(2)
            for cx, cy in [(4, 5), (11, 5), (7, 10), (3, 12), (12, 12)]:
                d.ellipse([cx - 3, cy - 3, cx + 3, cy + 2], fill=_c(10), outline=_c(0))
                d.rectangle([cx - 1, cy + 2, cx + 1, cy + 3], fill=_c(6))
        elif tid == 7:  # hills
            img, d = _new_tile(2)
            d.polygon([(1, 13), (5, 5), (10, 13)], fill=_c(6), outline=_c(14))
            d.polygon([(6, 14), (11, 6), (15, 14)], fill=_c(6), outline=_c(7))
            d.line([5, 5, 7, 9], fill=_c(10))
        elif tid == 8:  # mountains
            img, d = _new_tile(8)
            d.polygon([(0, 15), (5, 2), (10, 15)], fill=_c(7), outline=_c(0))
            d.polygon([(6, 15), (11, 3), (15, 15)], fill=_c(7), outline=_c(0))
            d.polygon([(4, 4), (5, 2), (6, 4)], fill=_c(15))
            d.polygon([(10, 5), (11, 3), (12, 5)], fill=_c(15))
        elif tid == 9:  # dungeon
            img, d = _new_tile(8)
            d.polygon([(1, 14), (8, 1), (14, 14)], fill=_c(7))
            d.rectangle([5, 7, 10, 14], fill=_c(0))
            d.line([5, 7, 10, 7], fill=_c(12))
        elif tid in (10, 11, 12):  # city, castle, town
            img, d = _new_tile(2)
            wall_c = 7 if tid == 10 else (15 if tid == 11 else 6)
            roof_c = 4 if tid == 11 else (12 if tid == 10 else 14)
            d.rectangle([2, 6, 13, 14], fill=_c(wall_c), outline=_c(0))
            d.rectangle([2, 3, 4, 6], fill=_c(wall_c))
            d.rectangle([11, 3, 13, 6], fill=_c(wall_c))
            d.rectangle([6, 4, 9, 6], fill=_c(roof_c))
            d.rectangle([6, 10, 9, 14], fill=_c(0))
            if tid == 11:
                d.line([7, 0, 7, 4], fill=_c(14))
                d.rectangle([8, 0, 10, 2], fill=_c(12))
        elif tid in (13, 14, 15):  # LCB west, entrance, east
            img, d = _new_tile(2)
            d.rectangle([0, 4, 15, 14], fill=_c(7), outline=_c(0))
            for bx in range(0, 16, 3):
                d.rectangle([bx, 2, bx + 1, 4], fill=_c(15))
            if tid == 14:
                d.rectangle([5, 8, 10, 14], fill=_c(0))
                d.rectangle([6, 9, 9, 14], fill=_c(14))
                d.line([7, 0, 7, 4], fill=_c(14))
                d.rectangle([8, 0, 11, 2], fill=_c(12))
            else:
                d.rectangle([6, 6, 9, 9], fill=_c(9))
        elif 16 <= tid <= 19:  # ship (W, N, E, S)
            img, d = _new_tile(1)
            if tid in (16, 18):  # horizontale
                d.polygon([(2, 9), (13, 9), (11, 13), (4, 13)], fill=_c(6))
                d.line([7, 2, 7, 9], fill=_c(14))
                sail_x = [3, 4, 8, 8] if tid == 16 else [7, 7, 12, 11]
                d.rectangle([min(sail_x), 3, max(sail_x), 8], fill=_c(15))
                d.rectangle([7, 1, 9, 2], fill=_c(12))
            else:  # verticale
                d.polygon([(5, 2), (10, 2), (12, 13), (3, 13)], fill=_c(6))
                d.rectangle([4, 6, 11, 9], fill=_c(15))
                d.rectangle([7, 1, 8, 3], fill=_c(12))
        elif tid in (20, 21):  # horse W, E
            img, d = _new_tile(0)
            d.rectangle([4, 6, 11, 10], fill=_c(6))
            hx = 3 if tid == 20 else 11
            d.rectangle([hx, 3, hx + 2, 7], fill=_c(6))
            d.point((hx + (0 if tid == 20 else 2), 4), fill=_c(15))
            d.line([5, 10, 5, 14], fill=_c(14))
            d.line([10, 10, 10, 14], fill=_c(14))
        elif tid == 22:  # dungeon_floor
            img, d = _new_tile(0)
            for y in range(0, 16, 4):
                for x in range(0, 16, 4):
                    if ((x + y) // 4) % 2 == 0:
                        d.rectangle([x, y, x + 3, y + 3], fill=_c(8))
        elif tid in (23, 25, 26):  # bridges
            img, d = _new_tile(1)
            d.rectangle([1, 2, 14, 13], fill=_c(6))
            for i in range(2, 14, 3):
                d.line([1, i, 14, i], fill=_c(14))
            d.line([1, 2, 1, 13], fill=_c(7))
            d.line([14, 2, 14, 13], fill=_c(7))
        elif tid == 24:  # balloon
            img, d = _new_tile(0)
            d.ellipse([3, 1, 12, 10], fill=_c(12), outline=_c(14))
            d.line([5, 10, 6, 12], fill=_c(7))
            d.line([10, 10, 9, 12], fill=_c(7))
            d.rectangle([6, 12, 9, 15], fill=_c(6))
        elif tid in (27, 28):  # up_ladder, down_ladder
            img, d = _new_tile(8)
            d.line([4, 1, 4, 14], fill=_c(14))
            d.line([11, 1, 11, 14], fill=_c(14))
            for y in range(3, 14, 3):
                d.line([4, y, 11, y], fill=_c(14))
            if tid == 27:
                d.polygon([(8, 2), (5, 6), (11, 6)], fill=_c(15))
            else:
                d.polygon([(8, 13), (5, 9), (11, 9)], fill=_c(12))
        elif tid == 29:  # ruins
            img, d = _new_tile(2)
            d.rectangle([2, 7, 5, 14], fill=_c(7))
            d.rectangle([7, 10, 10, 14], fill=_c(7))
            d.rectangle([11, 5, 14, 14], fill=_c(8))
            d.line([2, 7, 5, 5], fill=_c(15))
        elif tid == 30:  # shrine
            img, d = _new_tile(2)
            d.rectangle([2, 11, 13, 14], fill=_c(7))
            d.ellipse([5, 2, 10, 7], outline=_c(14), width=2)
            d.line([7, 7, 7, 12], fill=_c(14))
            d.line([4, 9, 11, 9], fill=_c(14))
        elif tid == 31:  # avatar
            img = _draw_humanoid(0, 15, 11, 14, 0, weapon=True)
        elif 32 <= tid <= 47:  # 8 classes (2 frames)
            cls_idx = (tid - 32) // 2
            frame = (tid - 32) % 2
            colors = [
                (15, 9, 11),   # mage
                (14, 2, 10),   # bard
                (15, 4, 7),    # fighter
                (15, 6, 2),    # druid
                (15, 3, 14),   # tinker
                (15, 7, 14),   # paladin
                (14, 10, 6),   # ranger
                (15, 6, 15),   # shepherd
            ]
            hc, bc, ac = colors[cls_idx]
            img = _draw_humanoid(0, hc, bc, ac, frame, weapon=(cls_idx in (2, 5, 6)), staff=(cls_idx in (0, 3, 7)))
        elif tid == 48:  # column
            img, d = _new_tile(6)
            d.rectangle([4, 1, 11, 14], fill=_c(7))
            d.rectangle([3, 1, 12, 3], fill=_c(15))
            d.rectangle([3, 12, 12, 14], fill=_c(15))
        elif tid in (49, 50, 51, 52):  # waterside corners
            img, d = _new_tile(1)
            if tid == 49:
                d.polygon([(0, 0), (15, 15), (0, 15)], fill=_c(2))
            elif tid == 50:
                d.polygon([(15, 0), (15, 15), (0, 15)], fill=_c(2))
            elif tid == 51:
                d.polygon([(0, 0), (15, 0), (0, 15)], fill=_c(2))
            else:
                d.polygon([(0, 0), (15, 0), (15, 15)], fill=_c(2))
        elif tid == 53:  # shipmast
            img, d = _new_tile(6)
            d.ellipse([4, 4, 11, 11], fill=_c(14))
            d.ellipse([6, 6, 9, 9], fill=_c(0))
        elif tid == 54:  # shipwheel
            img, d = _new_tile(6)
            d.ellipse([3, 3, 12, 12], outline=_c(14), width=2)
            d.line([7, 1, 7, 14], fill=_c(14))
            d.line([1, 7, 14, 7], fill=_c(14))
        elif tid == 55:  # rocks
            img, d = _new_tile(0)
            d.ellipse([2, 5, 9, 12], fill=_c(7), outline=_c(8))
            d.ellipse([7, 3, 14, 10], fill=_c(8), outline=_c(7))
            d.ellipse([5, 8, 12, 14], fill=_c(7), outline=_c(15))
        elif tid == 56:  # corpse
            img, d = _new_tile(0)
            d.rectangle([2, 6, 5, 9], fill=_c(15))
            d.rectangle([5, 6, 13, 10], fill=_c(4))
        elif tid == 57:  # stone_wall
            img, d = _new_tile(8)
            for y in range(0, 16, 4):
                d.line([0, y, 15, y], fill=_c(7))
                offset = 0 if (y // 4) % 2 == 0 else 4
                for x in range(offset, 16, 8):
                    d.line([x, y, x, y + 3], fill=_c(7))
        elif tid in (58, 59):  # locked_door, door
            img, d = _new_tile(8)
            d.rectangle([3, 1, 12, 14], fill=_c(6), outline=_c(14))
            d.line([7, 1, 7, 14], fill=_c(0))
            if tid == 58:
                d.rectangle([9, 7, 11, 9], fill=_c(12))
            else:
                d.point((10, 8), fill=_c(14))
        elif tid == 60:  # chest
            img, d = _new_tile(0)
            d.rectangle([2, 5, 13, 13], fill=_c(6), outline=_c(14))
            d.line([2, 8, 13, 8], fill=_c(14))
            d.rectangle([7, 7, 8, 10], fill=_c(14))
        elif tid == 61:  # ankh
            img, d = _new_tile(0)
            d.ellipse([5, 2, 10, 7], outline=_c(14), width=2)
            d.line([7, 7, 7, 14], fill=_c(14))
            d.line([8, 7, 8, 14], fill=_c(14))
            d.line([3, 9, 12, 9], fill=_c(14))
        elif tid == 62:  # brick_floor
            img, d = _new_tile(8)
            for y in (3, 7, 11, 15):
                d.line([0, y, 15, y], fill=_c(0))
            for x in (3, 7, 11, 15):
                d.line([x, 0, x, 15], fill=_c(0))
        elif tid == 63:  # wood_floor
            img, d = _new_tile(6)
            for y in (3, 7, 11, 15):
                d.line([0, y, 15, y], fill=_c(0))
            for x, y in [(5, 0), (12, 4), (4, 8), (11, 12)]:
                d.line([x, y, x, y + 3], fill=_c(0))
        elif 64 <= tid <= 67:  # moongates
            img, d = _new_tile(0)
            r = (tid - 63) * 2
            d.ellipse([8 - r, 8 - r, 7 + r, 7 + r], fill=_c(9), outline=_c(11))
            if tid == 67:
                d.ellipse([5, 5, 10, 10], fill=_c(15))
        elif tid in (68, 69, 70, 71):  # magic fields (poison, energy, fire, sleep)
            fc = {68: 10, 69: 11, 70: 12, 71: 13}[tid]
            fc2 = {68: 2, 69: 9, 70: 14, 71: 5}[tid]
            img, d = _new_tile(0)
            for y in range(1, 15, 2):
                for x in range(1, 15, 2):
                    d.point((x, y), fill=_c(fc if (x + y) % 4 == 0 else fc2))
        elif tid == 72:  # solid
            img, d = _new_tile(7)
            d.rectangle([1, 1, 14, 14], fill=_c(7), outline=_c(15))
        elif tid == 73:  # secret_door
            img, d = _new_tile(4)
            d.rectangle([0, 0, 15, 15], outline=_c(12))
            d.line([4, 4, 11, 11], fill=_c(12))
            d.line([11, 4, 4, 11], fill=_c(12))
        elif tid == 74:  # altar
            img, d = _new_tile(0)
            d.rectangle([2, 5, 13, 12], fill=_c(7), outline=_c(15))
            d.rectangle([4, 3, 11, 5], fill=_c(14))
        elif tid == 75:  # campfire
            img, d = _new_tile(0)
            d.line([3, 13, 12, 11], fill=_c(6))
            d.line([3, 11, 12, 13], fill=_c(6))
            d.polygon([(8, 2), (4, 10), (11, 10)], fill=_c(12))
            d.polygon([(8, 5), (6, 10), (10, 10)], fill=_c(14))
        elif tid == 76:  # lava
            img, d = _new_tile(4)
            for y in range(2, 15, 3):
                d.line([1, y, 14, y], fill=_c(12))
                d.point((y, y), fill=_c(14))
        elif tid in (77, 78, 79):  # flashes
            fc = {77: 9, 78: 11, 79: 12}[tid]
            img, d = _new_tile(0)
            d.ellipse([3, 3, 12, 12], fill=_c(fc), outline=_c(15))
        elif 80 <= tid <= 95:  # townfolk (2 frames each)
            tf_idx = (tid - 80) // 2
            frame = (tid - 80) % 2
            if tf_idx == 6:  # bull
                img, d = _new_tile(0)
                d.rectangle([3, 6, 12, 11], fill=_c(6))
                d.rectangle([2, 4, 5, 7], fill=_c(6))
                d.point((2, 3), fill=_c(15))
                d.point((5, 3), fill=_c(15))
                d.line([4, 11, 4, 14], fill=_c(6))
                d.line([11, 11, 11, 14], fill=_c(6))
            else:
                tf_colors = [
                    (15, 7, 4),    # guard
                    (15, 3, 6),    # villager
                    (14, 5, 13),   # bard_singing
                    (15, 12, 14),  # jester
                    (15, 8, 6),    # beggar
                    (15, 10, 14),  # child
                    (15, 6, 6),    # bull fallback
                    (15, 12, 14),  # lord_british
                ]
                hc, bc, ac = tf_colors[tf_idx]
                img = _draw_humanoid(0, hc, bc, ac, frame, crown=(tf_idx == 7), weapon=(tf_idx == 0))
        elif 96 <= tid <= 121:  # A..Z
            ch = chr(ord("A") + (tid - 96))
            img, d = _new_tile(1)
            d.rectangle([0, 0, 15, 15], outline=_c(15))
            d.rectangle([1, 1, 14, 14], outline=_c(9))
            glyph = _FONT_5X7[ch]
            for gy, row in enumerate(glyph):
                for gx, pixel in enumerate(row):
                    if pixel == "#":
                        d.rectangle([3 + gx * 2, 2 + gy * 2, 4 + gx * 2, 3 + gy * 2], fill=_c(15))
        elif tid in (122, 123, 124, 125, 126):  # signs / spacers / window / black
            img, d = _new_tile(0 if tid == 126 else 1)
            if tid == 125:
                d.rectangle([1, 2, 14, 13], fill=_c(6), outline=_c(14))
                d.rectangle([3, 4, 12, 11], fill=_c(0))
            elif tid in (123, 124):
                d.rectangle([0, 0, 15, 15], outline=_c(15))
        elif tid == 127:  # brick_wall
            img, d = _new_tile(4)
            for y in range(0, 16, 4):
                d.line([0, y, 15, y], fill=_c(7))
                offset = 0 if (y // 4) % 2 == 0 else 4
                for x in range(offset, 16, 8):
                    d.line([x, y, x, y + 3], fill=_c(7))
        elif 128 <= tid <= 131:  # pirate ship
            img, d = _new_tile(1)
            d.polygon([(2, 9), (13, 9), (11, 13), (4, 13)], fill=_c(8))
            d.rectangle([5, 3, 10, 8], fill=_c(0), outline=_c(15))
            d.point((7, 5), fill=_c(12))
            d.point((8, 6), fill=_c(12))
        elif 132 <= tid <= 143:  # sea creatures
            idx = (tid - 132) // 2
            frame = (tid - 132) % 2
            sc = [(11, 3), (12, 4), (10, 2), (14, 6), (11, 9), (7, 15)][idx]
            img = _draw_monster_sprite(sc[0], sc[1], 15, frame, "eye" if idx >= 4 else "crawler")
        else:  # 144..255 : 28 monstres (4 frames chacun)
            m_idx = (tid - 144) // 4
            frame = (tid - 144) % 4
            specs = [
                (6, 8, 12, "crawler"),     # rat
                (8, 7, 12, "winged"),      # bat
                (0, 8, 12, "crawler"),     # spider
                (15, 7, 11, "eye"),        # ghost
                (10, 2, 14, "crawler"),    # slime
                (2, 6, 12, "biped"),       # troll
                (10, 6, 14, "biped"),      # gremlin
                (6, 14, 12, "crawler"),    # mimic
                (6, 2, 12, "eye"),         # reaper
                (14, 6, 12, "crawler"),    # insect_swarm
                (13, 5, 12, "eye"),        # gazer
                (9, 1, 11, "eye"),         # phantom
                (2, 4, 12, "biped"),       # orc
                (15, 7, 4, "biped"),       # skeleton
                (4, 8, 15, "biped"),       # rogue
                (2, 10, 14, "crawler"),    # python
                (6, 4, 14, "biped"),       # ettin
                (6, 12, 14, "biped"),      # headless
                (6, 7, 12, "biped"),       # cyclops
                (11, 15, 14, "eye"),       # wisp
                (5, 13, 14, "biped"),      # evil_mage
                (7, 5, 12, "biped"),       # liche
                (12, 4, 14, "crawler"),    # lava_lizard
                (8, 14, 12, "biped"),      # zorn
                (12, 4, 14, "winged"),     # daemon
                (2, 10, 12, "crawler"),    # hydra
                (12, 14, 15, "winged"),    # dragon
                (4, 12, 14, "winged"),     # balron
            ]
            p, s, e, shp = specs[m_idx]
            img = _draw_monster_sprite(p, s, e, frame, shp)

        tiles.append(img)
    return tiles


class TilesetCache:
    """Cache Qt (QPixmap) pour afficher rapidement les 256 tuiles EGA à plusieurs échelles."""

    def __init__(self, images: Optional[List[Image.Image]] = None) -> None:
        self.images: List[Image.Image] = images if images is not None else generate_builtin_ega_tileset()
        self._pixmaps: Dict[Tuple[int, int], QPixmap] = {}

    def reload_from_shapes_ega(self, path: str | Path) -> None:
        self.images = load_shapes_ega(path)
        self._pixmaps.clear()

    def export_shapes_ega_bytes(self) -> bytes:
        return encode_shapes_ega(self.images)

    def get_pixmap(self, tile_id: int, size: int = 32) -> QPixmap:
        tid = tile_id % 256
        key = (tid, size)
        if key not in self._pixmaps:
            pil_img = self.images[tid]
            if size != 16:
                pil_img = pil_img.resize((size, size), Image.Resampling.NEAREST)
            data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
            qimg = QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)
            self._pixmaps[key] = QPixmap.fromImage(qimg.copy())
        return self._pixmaps[key]
