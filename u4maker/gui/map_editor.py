"""Éditeur de cartes visuel (Monde, Villes .ULT, Donjons .DNG, Sanctuaires/Combat .CON)."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..constants import (
    DUNGEON_TILES,
    QUEST_ITEM_LABELS,
    TILE_CATEGORIES,
    TILES,
    TILES_BY_ID,
)
from ..models import LabelData, MapData, MoongateData, PortalData, ScenarioProject
from ..tileset_renderer import TilesetCache

DUNGEON_MONSTERS: List[Tuple[int, str]] = [
    (0, "Aucun monstre"),
    (1, "Rat"),
    (2, "Chauve-souris"),
    (3, "Araignée"),
    (4, "Fantôme"),
    (5, "Gelée"),
    (6, "Troll"),
    (7, "Gremlin"),
    (8, "Mimique"),
    (9, "Faucheur"),
    (10, "Nuée d'insectes"),
    (11, "Tyrannœil"),
    (12, "Spectre"),
    (13, "Orque"),
    (14, "Squelette"),
    (15, "Brigand"),
]


class NewMapDialog(QDialog):
    """Assistant simple pour créer une nouvelle carte compatible xU4."""

    def __init__(self, next_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Créer une nouvelle carte")
        self.setMinimumWidth(380)
        layout = QFormLayout(self)

        self.name_edit = QLineEdit("Nouveau Village")
        self.type_combo = QComboBox()
        self.type_combo.addItem("Ville / Château / Village (32×32, .ULT)", "city")
        self.type_combo.addItem("Donjon 3D (8×8 × 8 niveaux, .DNG)", "dungeon")
        self.type_combo.addItem("Sanctuaire de Vertu (11×11, .CON)", "shrine")
        self.type_combo.addItem("Arène de Combat (11×11, .CON)", "combat")
        self.type_combo.addItem("Carte du Monde (256×256, .MAP)", "world")

        self.id_spin = QSpinBox()
        self.id_spin.setRange(0, 255)
        self.id_spin.setValue(next_id)

        self.fname_edit = QLineEdit(f"village_{next_id}.ult")

        def _update_defaults() -> None:
            mtype = self.type_combo.currentData()
            base = self.name_edit.text().strip().lower().replace(" ", "_") or f"map_{self.id_spin.value()}"
            ext = {
                "city": ".ult",
                "dungeon": ".dng",
                "shrine": ".con",
                "combat": ".con",
                "world": ".map",
            }[mtype]
            self.fname_edit.setText(f"{base}{ext}")

        self.type_combo.currentIndexChanged.connect(_update_defaults)

        layout.addRow("Nom du lieu :", self.name_edit)
        layout.addRow("Type de carte :", self.type_combo)
        layout.addRow("Identifiant xU4 (ID) :", self.id_spin)
        layout.addRow("Nom du fichier binaire :", self.fname_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def build_map(self) -> MapData:
        mtype = self.type_combo.currentData()
        mid = self.id_spin.value()
        name = self.name_edit.text().strip() or f"Carte {mid}"
        fname = self.fname_edit.text().strip() or f"map_{mid}.ult"
        if mtype == "world":
            m = MapData(
                id=mid,
                name=name,
                fname=fname,
                map_type="world",
                width=256,
                height=256,
                levels=1,
                chunk_dim=32,
                border_behavior="wrap",
                music=1,
            )
            m.ensure_grids(fill_tile=0)
        elif mtype == "dungeon":
            m = MapData(
                id=mid,
                name=name,
                fname=fname,
                map_type="dungeon",
                width=8,
                height=8,
                levels=8,
                border_behavior="wrap",
                music=7,
            )
            m.ensure_grids(fill_tile=0xF0)
        elif mtype in ("shrine", "combat"):
            m = MapData(
                id=mid,
                name=name,
                fname=fname,
                map_type=mtype,
                width=11,
                height=11,
                levels=1,
                border_behavior="fixed",
                music=3 if mtype == "shrine" else 8,
            )
            m.ensure_grids(fill_tile=4)
        else:
            stem = fname.rsplit(".", 1)[0]
            m = MapData(
                id=mid,
                name=name,
                fname=fname,
                map_type="city",
                width=32,
                height=32,
                levels=1,
                border_behavior="exit",
                music=2,
                tlk_fname=f"{stem}.tlk",
            )
            m.ensure_grids(fill_tile=4)
        return m


class PortalDialog(QDialog):
    """Dialogue pour ajouter ou éditer un portail entre cartes."""

    def __init__(
        self,
        project: ScenarioProject,
        portal: Optional[PortalData] = None,
        default_x: int = 0,
        default_y: int = 0,
        default_z: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurer un Portail")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 255)
        self.x_spin.setValue(portal.x if portal else default_x)

        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 255)
        self.y_spin.setValue(portal.y if portal else default_y)

        self.z_spin = QSpinBox()
        self.z_spin.setRange(0, 7)
        self.z_spin.setValue(portal.z if portal else default_z)

        self.action_combo = QComboBox()
        for act in ["save-enter", "enter", "climb", "descend", "exit_north", "exit_east", "exit_south", "exit_west"]:
            self.action_combo.addItem(act, act)
        if portal:
            idx = self.action_combo.findData(portal.action)
            if idx >= 0:
                self.action_combo.setCurrentIndex(idx)

        self.dest_map_combo = QComboBox()
        for m in sorted(project.maps, key=lambda x: x.id):
            self.dest_map_combo.addItem(f"[{m.id}] {m.name} ({m.width}×{m.height})", m.id)
        if portal:
            idx = self.dest_map_combo.findData(portal.dest_map_id)
            if idx >= 0:
                self.dest_map_combo.setCurrentIndex(idx)

        self.dest_x_spin = QSpinBox()
        self.dest_x_spin.setRange(0, 255)
        self.dest_x_spin.setValue(portal.dest_x if portal else 15)

        self.dest_y_spin = QSpinBox()
        self.dest_y_spin.setRange(0, 255)
        self.dest_y_spin.setValue(portal.dest_y if portal else 30)

        self.transport_combo = QComboBox()
        for tr in ["footorhorse", "foot", "horse", "ship", "balloon"]:
            self.transport_combo.addItem(tr, tr)
        if portal:
            idx = self.transport_combo.findData(portal.transport)
            if idx >= 0:
                self.transport_combo.setCurrentIndex(idx)

        self.msg_edit = QLineEdit(portal.message if portal else "")

        layout.addRow("Position X sur cette carte :", self.x_spin)
        layout.addRow("Position Y sur cette carte :", self.y_spin)
        layout.addRow("Niveau Z (donjon) :", self.z_spin)
        layout.addRow("Action déclencheur :", self.action_combo)
        layout.addRow("Carte de destination :", self.dest_map_combo)
        layout.addRow("Destination X :", self.dest_x_spin)
        layout.addRow("Destination Y :", self.dest_y_spin)
        layout.addRow("Transport autorisé :", self.transport_combo)
        layout.addRow("Message affiché :", self.msg_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def build_portal(self) -> PortalData:
        return PortalData(
            x=self.x_spin.value(),
            y=self.y_spin.value(),
            z=self.z_spin.value(),
            action=self.action_combo.currentData(),
            dest_map_id=self.dest_map_combo.currentData(),
            dest_x=self.dest_x_spin.value(),
            dest_y=self.dest_y_spin.value(),
            transport=self.transport_combo.currentData(),
            message=self.msg_edit.text().strip(),
        )


class MapGraphicsView(QGraphicsView):
    """Canevas QGraphicsView interactif gérant clic, glisser, survol et molette."""

    cell_pressed = Signal(int, int, Qt.MouseButton)
    cell_moved = Signal(int, int)
    cell_released = Signal(int, int)
    cell_hovered = Signal(int, int)

    def __init__(self, scene: QGraphicsScene, parent: Optional[QWidget] = None) -> None:
        super().__init__(scene, parent)
        self.tile_px = 24
        self.map_w = 32
        self.map_h = 32
        self._drawing = False
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

    def _coords_from_event(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        scene_pt = self.mapToScene(pos.toPoint())
        cx = int(scene_pt.x() // self.tile_px)
        cy = int(scene_pt.y() // self.tile_px)
        if 0 <= cx < self.map_w and 0 <= cy < self.map_h:
            return cx, cy
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)
            return
        coords = self._coords_from_event(event.position())
        if coords is not None:
            self._drawing = True
            self.cell_pressed.emit(coords[0], coords[1], event.button())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        coords = self._coords_from_event(event.position())
        if coords is not None:
            self.cell_hovered.emit(coords[0], coords[1])
            if self._drawing:
                self.cell_moved.emit(coords[0], coords[1])
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        if self._drawing:
            self._drawing = False
            coords = self._coords_from_event(event.position())
            if coords is not None:
                self.cell_released.emit(coords[0], coords[1])
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)


class MapEditorWidget(QWidget):
    """Onglet complet Éditeur de Cartes avec palette, outils, calques et portails."""

    project_changed = Signal()
    npc_place_requested = Signal(int, int, int)  # map_id, x, y

    def __init__(
        self,
        project: ScenarioProject,
        tileset: TilesetCache,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.tileset = tileset
        self.current_map: Optional[MapData] = None
        self.current_level: int = 0
        self.selected_tile_id: int = 4  # prairie
        self.selected_dng_type: int = 0x00
        self.selected_dng_monster: int = 0
        self.current_tool: str = "brush"  # brush, rect, fill, picker, portal, label
        self.tile_px: int = 24
        self._rect_start: Optional[Tuple[int, int]] = None
        self._tile_items: List[List[QGraphicsPixmapItem]] = []
        self._overlay_items: List[QGraphicsItem] = []
        self._grid_items: List[QGraphicsItem] = []
        self._undo_stack: List[List[List[int]]] = []
        self._redo_stack: List[List[List[int]]] = []
        self._stroke_snapshot: Optional[List[List[int]]] = None

        self._build_ui()
        self.refresh_from_project()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        # Barre supérieure de sélection et d'outils
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Carte :"))
        self.map_combo = QComboBox()
        self.map_combo.setMinimumWidth(240)
        self.map_combo.currentIndexChanged.connect(self._on_map_selected)
        top_bar.addWidget(self.map_combo)

        self.btn_new_map = QPushButton("+ Nouvelle carte")
        self.btn_new_map.clicked.connect(self._create_new_map)
        top_bar.addWidget(self.btn_new_map)

        self.level_label = QLabel("Niveau :")
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 8)
        self.level_spin.valueChanged.connect(self._on_level_changed)
        top_bar.addWidget(self.level_label)
        top_bar.addWidget(self.level_spin)

        top_bar.addSpacing(12)

        self.tool_buttons: Dict[str, QToolButton] = {}
        tools = [
            ("brush", "🖌️ Pinceau"),
            ("rect", "⬛ Rectangle"),
            ("fill", "🪣 Remplir"),
            ("picker", "💉 Pipette"),
            ("portal", "🚪 Portail"),
            ("label", "⭐ Objet"),
        ]
        for tkey, tlabel in tools:
            btn = QToolButton()
            btn.setText(tlabel)
            btn.setCheckable(True)
            btn.setChecked(tkey == "brush")
            btn.clicked.connect(lambda _=False, k=tkey: self._set_tool(k))
            self.tool_buttons[tkey] = btn
            top_bar.addWidget(btn)

        top_bar.addSpacing(8)
        self.btn_undo = QPushButton("↶ Annuler")
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo = QPushButton("↷ Rétablir")
        self.btn_redo.clicked.connect(self.redo)
        top_bar.addWidget(self.btn_undo)
        top_bar.addWidget(self.btn_redo)

        top_bar.addSpacing(8)
        self.chk_grid = QCheckBox("Grille")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(self._rebuild_grid)
        top_bar.addWidget(self.chk_grid)

        self.chk_overlays = QCheckBox("PNJ / Objets")
        self.chk_overlays.setChecked(True)
        self.chk_overlays.toggled.connect(self._rebuild_overlays)
        top_bar.addWidget(self.chk_overlays)

        btn_zoom_out = QPushButton("－")
        btn_zoom_out.setFixedWidth(30)
        btn_zoom_out.clicked.connect(lambda: self.view.scale(0.8, 0.8))
        btn_zoom_in = QPushButton("＋")
        btn_zoom_in.setFixedWidth(30)
        btn_zoom_in.clicked.connect(lambda: self.view.scale(1.25, 1.25))
        top_bar.addWidget(btn_zoom_out)
        top_bar.addWidget(btn_zoom_in)
        top_bar.addStretch()

        root.addLayout(top_bar)

        # Splitter principal : Canevas à gauche, Palette + Portails/Labels à droite
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Gauche : Scene & Status
        canvas_box = QWidget()
        canvas_layout = QVBoxLayout(canvas_box)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QGraphicsScene(self)
        self.view = MapGraphicsView(self.scene, self)
        self.view.cell_pressed.connect(self._on_cell_pressed)
        self.view.cell_moved.connect(self._on_cell_moved)
        self.view.cell_released.connect(self._on_cell_released)
        self.view.cell_hovered.connect(self._on_cell_hovered)
        canvas_layout.addWidget(self.view, 1)

        self.hover_label = QLabel("Survolez la carte pour inspecter les coordonnées et tuiles. Clic droit = Pipette.")
        self.hover_label.setStyleSheet("padding: 4px; color: #e6b84c; font-weight: bold;")
        canvas_layout.addWidget(self.hover_label)
        splitter.addWidget(canvas_box)

        # Droite : Palette + Propriétés
        right_panel = QWidget()
        right_panel.setMinimumWidth(340)
        right_panel.setMaximumWidth(450)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)

        # Aperçu tuile active
        active_group = QGroupBox("Tuile sélectionnée")
        active_hbox = QHBoxLayout(active_group)
        self.active_tile_icon = QLabel()
        self.active_tile_icon.setFixedSize(48, 48)
        self.active_tile_icon.setStyleSheet("border: 1px solid #e6b84c; background: #000;")
        self.active_tile_info = QLabel("Prairie (#4)")
        self.active_tile_info.setWordWrap(True)
        active_hbox.addWidget(self.active_tile_icon)
        active_hbox.addWidget(self.active_tile_info, 1)
        right_layout.addWidget(active_group)

        # Contrôles spécifiques Donjon (affichés si map_type == 'dungeon')
        self.dng_group = QGroupBox("Pinceau Donjon 3D (.DNG)")
        dng_form = QFormLayout(self.dng_group)
        self.dng_type_combo = QComboBox()
        for val, label in DUNGEON_TILES:
            self.dng_type_combo.addItem(f"0x{val:02X} — {label}", val)
        self.dng_type_combo.currentIndexChanged.connect(self._on_dng_brush_changed)
        self.dng_monster_combo = QComboBox()
        for mval, mlabel in DUNGEON_MONSTERS:
            self.dng_monster_combo.addItem(f"{mval} — {mlabel}", mval)
        self.dng_monster_combo.currentIndexChanged.connect(self._on_dng_brush_changed)
        dng_form.addRow("Case donjon :", self.dng_type_combo)
        dng_form.addRow("Monstre :", self.dng_monster_combo)
        self.dng_group.setVisible(False)
        right_layout.addWidget(self.dng_group)

        # Palette de tuiles 2D (Monde / Villes / Sanctuaires)
        self.palette_group = QGroupBox("Palette des 256 tuiles EGA")
        pal_vbox = QVBoxLayout(self.palette_group)
        filter_row = QHBoxLayout()
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(TILE_CATEGORIES)
        self.cat_combo.currentIndexChanged.connect(self._populate_palette)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrer (eau, mur, dragon...)")
        self.search_edit.textChanged.connect(self._populate_palette)
        filter_row.addWidget(self.cat_combo)
        filter_row.addWidget(self.search_edit)
        pal_vbox.addLayout(filter_row)

        self.palette_list = QListWidget()
        self.palette_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.palette_list.setIconSize(QPixmap(32, 32).size())
        self.palette_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.palette_list.setMovement(QListWidget.Movement.Static)
        self.palette_list.setSpacing(4)
        self.palette_list.currentItemChanged.connect(self._on_palette_selected)
        pal_vbox.addWidget(self.palette_list, 1)
        right_layout.addWidget(self.palette_group, 1)

        # Onglets bas droite : Portails et Objets/Moongates
        sub_tabs = QTabWidget()
        # Onglet Portails
        portals_tab = QWidget()
        p_layout = QVBoxLayout(portals_tab)
        self.portals_table = QTableWidget(0, 4)
        self.portals_table.setHorizontalHeaderLabels(["Pos", "Action", "Dest ID", "Message"])
        self.portals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.portals_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        p_layout.addWidget(self.portals_table)
        p_btns = QHBoxLayout()
        btn_add_p = QPushButton("+ Portail")
        btn_add_p.clicked.connect(lambda: self._add_portal_at(0, 0))
        btn_del_p = QPushButton("Supprimer")
        btn_del_p.clicked.connect(self._delete_selected_portal)
        p_btns.addWidget(btn_add_p)
        p_btns.addWidget(btn_del_p)
        p_layout.addLayout(p_btns)
        sub_tabs.addTab(portals_tab, "🚪 Portails")

        # Onglet Labels (Objets de quête)
        labels_tab = QWidget()
        l_layout = QVBoxLayout(labels_tab)
        self.labels_table = QTableWidget(0, 3)
        self.labels_table.setHorizontalHeaderLabels(["Objet (Label)", "Coord", "Description"])
        self.labels_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.labels_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        l_layout.addWidget(self.labels_table)
        l_btns = QHBoxLayout()
        btn_add_l = QPushButton("+ Objet")
        btn_add_l.clicked.connect(lambda: self._add_label_at(1, 1))
        btn_del_l = QPushButton("Supprimer")
        btn_del_l.clicked.connect(self._delete_selected_label)
        l_btns.addWidget(btn_add_l)
        l_btns.addWidget(btn_del_l)
        l_layout.addLayout(l_btns)
        sub_tabs.addTab(labels_tab, "⭐ Objets")

        right_layout.addWidget(sub_tabs)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._populate_palette()
        self._update_active_tile_preview()

    def set_project(self, project: ScenarioProject) -> None:
        self.project = project
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.refresh_from_project()

    def refresh_from_project(self) -> None:
        prev_id = self.current_map.id if self.current_map else None
        self.map_combo.blockSignals(True)
        self.map_combo.clear()
        for m in sorted(self.project.maps, key=lambda x: x.id):
            self.map_combo.addItem(f"[{m.id}] {m.name} ({m.map_type} {m.width}×{m.height})", m.id)
        self.map_combo.blockSignals(False)

        if not self.project.maps:
            self.current_map = None
            self.scene.clear()
            return

        target_idx = 0
        if prev_id is not None:
            found = self.map_combo.findData(prev_id)
            if found >= 0:
                target_idx = found
        self.map_combo.setCurrentIndex(target_idx)
        self._on_map_selected(target_idx)

    def _on_map_selected(self, index: int) -> None:
        if index < 0:
            return
        mid = self.map_combo.itemData(index)
        m = self.project.get_map(mid)
        if not m:
            return
        m.ensure_grids()
        self.current_map = m
        self.current_level = 0
        self._undo_stack.clear()
        self._redo_stack.clear()

        is_dng = m.map_type == "dungeon"
        self.level_label.setVisible(is_dng)
        self.level_spin.setVisible(is_dng)
        self.level_spin.blockSignals(True)
        self.level_spin.setRange(1, max(1, m.levels))
        self.level_spin.setValue(1)
        self.level_spin.blockSignals(False)

        self.dng_group.setVisible(is_dng)
        self.palette_group.setVisible(not is_dng)

        # Ajuster taille de tuile pour que le 256x256 reste fluide
        self.tile_px = 16 if m.width >= 128 else 28
        self.view.tile_px = self.tile_px
        self.view.map_w = m.width
        self.view.map_h = m.height

        self._rebuild_scene()
        self._refresh_sub_tables()

    def _on_level_changed(self, value: int) -> None:
        self.current_level = max(0, value - 1)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._rebuild_scene()

    def _create_new_map(self) -> None:
        dlg = NewMapDialog(self.project.next_map_id(), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            m = dlg.build_map()
            self.project.maps.append(m)
            if m.tlk_fname and m.tlk_fname not in self.project.dialogues:
                self.project.dialogues[m.tlk_fname] = []
            self.refresh_from_project()
            idx = self.map_combo.findData(m.id)
            if idx >= 0:
                self.map_combo.setCurrentIndex(idx)
            self.project_changed.emit()

    def _set_tool(self, tool_key: str) -> None:
        self.current_tool = tool_key
        for k, btn in self.tool_buttons.items():
            btn.setChecked(k == tool_key)

    def _populate_palette(self) -> None:
        cat = self.cat_combo.currentText()
        q = self.search_edit.text().strip().lower()
        self.palette_list.clear()
        for t in TILES:
            if cat != "Toutes" and t.category != cat:
                continue
            if q and (q not in t.label_fr.lower() and q not in t.name.lower() and q != str(t.id)):
                continue
            pm = self.tileset.get_pixmap(t.id, 32)
            item = QListWidgetItem(QIcon(pm), f"#{t.id}")
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            item.setToolTip(f"#{t.id} {t.label_fr} ({t.name})")
            self.palette_list.addItem(item)

    def _on_palette_selected(self, current: Optional[QListWidgetItem], _prev) -> None:
        if not current:
            return
        self.selected_tile_id = int(current.data(Qt.ItemDataRole.UserRole))
        self._update_active_tile_preview()

    def _on_dng_brush_changed(self) -> None:
        self.selected_dng_type = int(self.dng_type_combo.currentData() or 0)
        self.selected_dng_monster = int(self.dng_monster_combo.currentData() or 0)

    def _update_active_tile_preview(self) -> None:
        t = TILES_BY_ID.get(self.selected_tile_id)
        if not t:
            return
        self.active_tile_icon.setPixmap(self.tileset.get_pixmap(t.id, 48))
        props = []
        props.append("Marchable" if t.walkable else "Bloquant")
        if t.sailable:
            props.append("Navigable")
        if t.opaque:
            props.append("Opaque")
        self.active_tile_info.setText(
            f"<b>#{t.id} — {t.label_fr}</b><br/>"
            f"Identifiant xU4 : <code>{t.name}</code><br/>"
            f"Catégorie : {t.category} | {', '.join(props)}"
        )

    def _dungeon_byte_to_visual_tile(self, val: int) -> int:
        high = val & 0xF0
        mapping = {
            0x00: 22,  # floor
            0x10: 27,  # up ladder
            0x20: 28,  # down ladder
            0x30: 27,  # up/down
            0x40: 60,  # chest
            0x50: 62,
            0x60: 62,
            0x70: 78,  # orb
            0x80: 79,  # trap
            0x90: 2,   # fountain
            0xA0: 70 if (val & 0x0F) == 2 else 68,  # field
            0xB0: 74,  # altar
            0xC0: 59,  # door
            0xD0: 72,  # room
            0xE0: 73,  # secret door
            0xF0: 57,  # stone wall
        }
        return mapping.get(high, 22)

    def _visual_pixmap_for_cell(self, val: int) -> QPixmap:
        if self.current_map and self.current_map.map_type == "dungeon":
            vis_id = self._dungeon_byte_to_visual_tile(val)
            return self.tileset.get_pixmap(vis_id, self.tile_px)
        return self.tileset.get_pixmap(val, self.tile_px)

    def _rebuild_scene(self) -> None:
        self.scene.clear()
        self._tile_items.clear()
        self._overlay_items.clear()
        self._grid_items.clear()
        m = self.current_map
        if not m:
            return
        grid = m.grids[self.current_level]
        self.scene.setSceneRect(0, 0, m.width * self.tile_px, m.height * self.tile_px)

        for y in range(m.height):
            row_items: List[QGraphicsPixmapItem] = []
            for x in range(m.width):
                pm = self._visual_pixmap_for_cell(grid[y][x])
                item = self.scene.addPixmap(pm)
                item.setPos(x * self.tile_px, y * self.tile_px)
                item.setZValue(0)
                row_items.append(item)
            self._tile_items.append(row_items)

        self._rebuild_grid()
        self._rebuild_overlays()

    def _rebuild_grid(self) -> None:
        for it in self._grid_items:
            self.scene.removeItem(it)
        self._grid_items.clear()
        m = self.current_map
        if not m or not self.chk_grid.isChecked():
            return
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(1)
        w_px = m.width * self.tile_px
        h_px = m.height * self.tile_px
        for x in range(m.width + 1):
            line = self.scene.addLine(x * self.tile_px, 0, x * self.tile_px, h_px, pen)
            line.setZValue(10)
            self._grid_items.append(line)
        for y in range(m.height + 1):
            line = self.scene.addLine(0, y * self.tile_px, w_px, y * self.tile_px, pen)
            line.setZValue(10)
            self._grid_items.append(line)

    def _rebuild_overlays(self) -> None:
        for it in self._overlay_items:
            self.scene.removeItem(it)
        self._overlay_items.clear()
        m = self.current_map
        if not m or not self.chk_overlays.isChecked():
            return

        # PNJ (sur villes)
        for npc in m.npcs:
            pm = self.tileset.get_pixmap(npc.tile_id, self.tile_px)
            pix = self.scene.addPixmap(pm)
            pix.setPos(npc.x * self.tile_px, npc.y * self.tile_px)
            pix.setZValue(20)
            pix.setToolTip(f"PNJ : {npc.name} ({npc.role})")
            self._overlay_items.append(pix)

            border = self.scene.addRect(
                npc.x * self.tile_px,
                npc.y * self.tile_px,
                self.tile_px,
                self.tile_px,
                QPen(QColor("#5bc0eb"), 2),
            )
            border.setZValue(21)
            self._overlay_items.append(border)

        # Portails
        for p in m.portals:
            if p.z != self.current_level and m.map_type == "dungeon":
                continue
            rect = self.scene.addRect(
                p.x * self.tile_px + 2,
                p.y * self.tile_px + 2,
                self.tile_px - 4,
                self.tile_px - 4,
                QPen(QColor("#ffd166"), 2),
                QBrush(QColor(255, 209, 102, 70)),
            )
            rect.setZValue(22)
            txt = self.scene.addSimpleText("P", QFont("Arial", max(7, self.tile_px // 3), QFont.Weight.Bold))
            txt.setBrush(QBrush(QColor("#ffffff")))
            txt.setPos(p.x * self.tile_px + 4, p.y * self.tile_px + 2)
            txt.setZValue(23)
            self._overlay_items.extend([rect, txt])

        # Moongates
        for mg in m.moongates:
            rect = self.scene.addEllipse(
                mg.x * self.tile_px + 2,
                mg.y * self.tile_px + 2,
                self.tile_px - 4,
                self.tile_px - 4,
                QPen(QColor("#00f5d4"), 2),
                QBrush(QColor(0, 245, 212, 80)),
            )
            rect.setZValue(22)
            self._overlay_items.append(rect)

        # Objets / Labels
        for lbl in m.labels:
            if lbl.z != self.current_level and m.map_type == "dungeon":
                continue
            rect = self.scene.addRect(
                lbl.x * self.tile_px + 2,
                lbl.y * self.tile_px + 2,
                self.tile_px - 4,
                self.tile_px - 4,
                QPen(QColor("#ff595e"), 2),
                QBrush(QColor(255, 89, 94, 70)),
            )
            rect.setZValue(24)
            txt = self.scene.addSimpleText("★", QFont("Arial", max(7, self.tile_px // 3)))
            txt.setBrush(QBrush(QColor("#ffe66d")))
            txt.setPos(lbl.x * self.tile_px + 3, p_y := lbl.y * self.tile_px + 1)
            txt.setZValue(25)
            self._overlay_items.extend([rect, txt])

        # Monstres donjon
        if m.map_type == "dungeon":
            grid = m.grids[self.current_level]
            for y in range(m.height):
                for x in range(m.width):
                    mon = grid[y][x] & 0x0F
                    if mon > 0 and (grid[y][x] & 0xF0) not in (0x80, 0x90, 0xA0, 0xD0):
                        txt = self.scene.addSimpleText(
                            f"M{mon}",
                            QFont("Arial", max(7, self.tile_px // 3), QFont.Weight.Bold),
                        )
                        txt.setBrush(QBrush(QColor("#ff6b6b")))
                        txt.setPos(x * self.tile_px + 2, y * self.tile_px + 2)
                        txt.setZValue(26)
                        self._overlay_items.append(txt)

    def _clone_grid(self) -> List[List[int]]:
        assert self.current_map is not None
        return [list(row) for row in self.current_map.grids[self.current_level]]

    def _push_undo(self, snapshot: List[List[int]]) -> None:
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> None:
        if not self.current_map or not self._undo_stack:
            return
        self._redo_stack.append(self._clone_grid())
        self.current_map.grids[self.current_level] = self._undo_stack.pop()
        self._rebuild_scene()
        self.project_changed.emit()

    def redo(self) -> None:
        if not self.current_map or not self._redo_stack:
            return
        self._undo_stack.append(self._clone_grid())
        self.current_map.grids[self.current_level] = self._redo_stack.pop()
        self._rebuild_scene()
        self.project_changed.emit()

    def _active_paint_value(self) -> int:
        if self.current_map and self.current_map.map_type == "dungeon":
            if self.selected_dng_type in (0x80, 0x90, 0x91, 0xA0, 0xA2, 0xD0):
                return self.selected_dng_type
            return (self.selected_dng_type & 0xF0) | (self.selected_dng_monster & 0x0F)
        return self.selected_tile_id

    def _paint_cell(self, x: int, y: int, val: int) -> None:
        m = self.current_map
        if not m:
            return
        if m.grids[self.current_level][y][x] == val:
            return
        m.grids[self.current_level][y][x] = val
        self._tile_items[y][x].setPixmap(self._visual_pixmap_for_cell(val))

    def _flood_fill(self, start_x: int, start_y: int, replacement: int) -> None:
        m = self.current_map
        if not m:
            return
        grid = m.grids[self.current_level]
        target = grid[start_y][start_x]
        if target == replacement:
            return
        self._push_undo(self._clone_grid())
        q = deque([(start_x, start_y)])
        visited = set()
        while q:
            cx, cy = q.popleft()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            if not (0 <= cx < m.width and 0 <= cy < m.height):
                continue
            if grid[cy][cx] != target:
                continue
            grid[cy][cx] = replacement
            self._tile_items[cy][cx].setPixmap(self._visual_pixmap_for_cell(replacement))
            q.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
        if m.map_type == "dungeon":
            self._rebuild_overlays()
        self.project_changed.emit()

    def _pick_at(self, x: int, y: int) -> None:
        m = self.current_map
        if not m:
            return
        val = m.grids[self.current_level][y][x]
        if m.map_type == "dungeon":
            high = val & 0xF0
            mon = val & 0x0F
            idx = self.dng_type_combo.findData(high)
            if idx >= 0:
                self.dng_type_combo.setCurrentIndex(idx)
            midx = self.dng_monster_combo.findData(mon)
            if midx >= 0:
                self.dng_monster_combo.setCurrentIndex(midx)
        else:
            self.selected_tile_id = val
            self._update_active_tile_preview()

    def _on_cell_pressed(self, x: int, y: int, button: Qt.MouseButton) -> None:
        m = self.current_map
        if not m:
            return
        if button == Qt.MouseButton.RightButton or self.current_tool == "picker":
            self._pick_at(x, y)
            return

        if self.current_tool == "brush":
            self._stroke_snapshot = self._clone_grid()
            self._paint_cell(x, y, self._active_paint_value())
        elif self.current_tool == "rect":
            self._rect_start = (x, y)
        elif self.current_tool == "fill":
            self._flood_fill(x, y, self._active_paint_value())
        elif self.current_tool == "portal":
            self._add_portal_at(x, y)
        elif self.current_tool == "label":
            self._add_label_at(x, y)

    def _on_cell_moved(self, x: int, y: int) -> None:
        if self.current_tool == "brush" and self.current_map:
            self._paint_cell(x, y, self._active_paint_value())

    def _on_cell_released(self, x: int, y: int) -> None:
        m = self.current_map
        if not m:
            return
        if self.current_tool == "brush" and self._stroke_snapshot is not None:
            if self._stroke_snapshot != m.grids[self.current_level]:
                self._push_undo(self._stroke_snapshot)
                if m.map_type == "dungeon":
                    self._rebuild_overlays()
                self.project_changed.emit()
            self._stroke_snapshot = None
        elif self.current_tool == "rect" and self._rect_start is not None:
            sx, sy = self._rect_start
            self._rect_start = None
            val = self._active_paint_value()
            self._push_undo(self._clone_grid())
            for ry in range(min(sy, y), max(sy, y) + 1):
                for rx in range(min(sx, x), max(sx, x) + 1):
                    self._paint_cell(rx, ry, val)
            if m.map_type == "dungeon":
                self._rebuild_overlays()
            self.project_changed.emit()

    def _on_cell_hovered(self, x: int, y: int) -> None:
        m = self.current_map
        if not m:
            return
        val = m.grids[self.current_level][y][x]
        if m.map_type == "dungeon":
            info = f"Donjon (Niv.{self.current_level+1}) ({x},{y}) — Octet 0x{val:02X}"
        else:
            t = TILES_BY_ID.get(val)
            tname = t.label_fr if t else f"#{val}"
            info = f"({x}, {y}) — Tuile #{val} : {tname}"
        npcs_here = [n.name for n in m.npcs if n.x == x and n.y == y]
        if npcs_here:
            info += f" | PNJ: {', '.join(npcs_here)}"
        labels_here = [l.name for l in m.labels if l.x == x and l.y == y and l.z == self.current_level]
        if labels_here:
            info += f" | Objet: {', '.join(labels_here)}"
        self.hover_label.setText(info)

    def _add_portal_at(self, x: int, y: int) -> None:
        m = self.current_map
        if not m:
            return
        dlg = PortalDialog(self.project, default_x=x, default_y=y, default_z=self.current_level, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            m.portals.append(dlg.build_portal())
            self._rebuild_overlays()
            self._refresh_sub_tables()
            self.project_changed.emit()

    def _delete_selected_portal(self) -> None:
        m = self.current_map
        if not m:
            return
        row = self.portals_table.currentRow()
        if 0 <= row < len(m.portals):
            m.portals.pop(row)
            self._rebuild_overlays()
            self._refresh_sub_tables()
            self.project_changed.emit()

    def _add_label_at(self, x: int, y: int) -> None:
        m = self.current_map
        if not m:
            return
        items = [f"{k} — {desc}" for k, desc in QUEST_ITEM_LABELS]
        choice, ok = QInputDialog.getItem(
            self,
            "Placer un objet de quête (Label)",
            f"Objet à placer en ({x}, {y}) :",
            items,
            0,
            False,
        )
        if not ok or not choice:
            return
        key = choice.split(" — ")[0].strip()
        desc = choice.split(" — ")[1].strip() if " — " in choice else key
        m.labels.append(LabelData(name=key, x=x, y=y, z=self.current_level, description=desc))
        self._rebuild_overlays()
        self._refresh_sub_tables()
        self.project_changed.emit()

    def _delete_selected_label(self) -> None:
        m = self.current_map
        if not m:
            return
        row = self.labels_table.currentRow()
        if 0 <= row < len(m.labels):
            m.labels.pop(row)
            self._rebuild_overlays()
            self._refresh_sub_tables()
            self.project_changed.emit()

    def _refresh_sub_tables(self) -> None:
        m = self.current_map
        self.portals_table.setRowCount(0)
        self.labels_table.setRowCount(0)
        if not m:
            return
        for p in m.portals:
            r = self.portals_table.rowCount()
            self.portals_table.insertRow(r)
            self.portals_table.setItem(r, 0, QTableWidgetItem(f"{p.x},{p.y}" + (f",{p.z}" if p.z else "")))
            self.portals_table.setItem(r, 1, QTableWidgetItem(p.action))
            self.portals_table.setItem(r, 2, QTableWidgetItem(f"{p.dest_map_id} ({p.dest_x},{p.dest_y})"))
            self.portals_table.setItem(r, 3, QTableWidgetItem(p.message))

        for lbl in m.labels:
            r = self.labels_table.rowCount()
            self.labels_table.insertRow(r)
            self.labels_table.setItem(r, 0, QTableWidgetItem(lbl.name))
            self.labels_table.setItem(r, 1, QTableWidgetItem(f"{lbl.x},{lbl.y}" + (f",{lbl.z}" if lbl.z else "")))
            self.labels_table.setItem(r, 2, QTableWidgetItem(lbl.description))
