"""Éditeur visuel de PNJ (.ULT) et de Boutiques (vendors.b) pour Ultima IV Maker."""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..constants import (
    ARMORS_LIST,
    NPC_MOVEMENTS,
    NPC_ROLES,
    NPC_SPRITE_IDS,
    SHOP_ROLES,
    TILES_BY_ID,
    WEAPONS_LIST,
)
from ..models import MapData, NPCData, ScenarioProject, ShopConfig
from ..tileset_renderer import TilesetCache


class NPCEditorWidget(QWidget):
    """Onglet Éditeur de PNJ et de Boutiques."""

    project_changed = Signal()
    open_dialogue_requested = Signal(str, int)  # bank_name, tlk_id

    def __init__(
        self,
        project: ScenarioProject,
        tileset: TilesetCache,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.tileset = tileset
        self.current_city: Optional[MapData] = None
        self.current_npc: Optional[NPCData] = None
        self._anim_frame = 0
        self._loading = False
        self._shop_item_checks: dict[str, QCheckBox] = {}

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_anim)
        self._anim_timer.start(450)

        self._build_ui()
        self.refresh_from_project()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Barre ville
        top = QHBoxLayout()
        top.addWidget(QLabel("Ville / Château (.ULT) :"))
        self.city_combo = QComboBox()
        self.city_combo.setMinimumWidth(260)
        self.city_combo.currentIndexChanged.connect(self._on_city_changed)
        top.addWidget(self.city_combo)

        self.city_tlk_label = QLabel("")
        self.city_tlk_label.setStyleSheet("color: #9fb3c8;")
        top.addWidget(self.city_tlk_label)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Colonne gauche : Liste des PNJ (max 32 slots .ULT)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.addWidget(QLabel("Habitants de la carte (32 emplacements max) :"))
        self.npc_list = QListWidget()
        self.npc_list.setIconSize(QPixmap(32, 32).size())
        self.npc_list.currentRowChanged.connect(self._on_npc_selected)
        left_lay.addWidget(self.npc_list, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Ajouter un PNJ")
        self.btn_add.clicked.connect(self._add_npc)
        self.btn_del = QPushButton("Supprimer")
        self.btn_del.clicked.connect(self._delete_npc)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_del)
        left_lay.addLayout(btn_row)
        splitter.addWidget(left)

        # Colonne droite : Formulaire PNJ + Boutique dans ScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        right_lay = QVBoxLayout(form_container)

        # Carte d'identité & sprite
        id_group = QGroupBox("Identité, Apparence & Placement (.ULT)")
        id_hbox = QHBoxLayout(id_group)

        preview_box = QVBoxLayout()
        self.sprite_preview = QLabel()
        self.sprite_preview.setFixedSize(64, 64)
        self.sprite_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite_preview.setStyleSheet("background: #000; border: 2px solid #e6b84c;")
        preview_box.addWidget(self.sprite_preview)
        preview_box.addStretch()
        id_hbox.addLayout(preview_box)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._apply_changes)

        self.sprite_combo = QComboBox()
        for tid in NPC_SPRITE_IDS:
            t = TILES_BY_ID.get(tid)
            label = f"#{tid} — {t.label_fr}" if t else f"#{tid}"
            self.sprite_combo.addItem(QIcon(self.tileset.get_pixmap(tid, 24)), label, tid)
        self.sprite_combo.currentIndexChanged.connect(self._apply_changes)

        coord_row = QHBoxLayout()
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 31)
        self.x_spin.valueChanged.connect(self._apply_changes)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 31)
        self.y_spin.valueChanged.connect(self._apply_changes)
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(1, 32)
        self.slot_spin.setEnabled(False)
        coord_row.addWidget(QLabel("X :"))
        coord_row.addWidget(self.x_spin)
        coord_row.addWidget(QLabel("Y :"))
        coord_row.addWidget(self.y_spin)
        coord_row.addWidget(QLabel("Slot .ULT :"))
        coord_row.addWidget(self.slot_spin)

        self.move_combo = QComboBox()
        for byte_val, (mkey, mlabel) in NPC_MOVEMENTS.items():
            self.move_combo.addItem(f"{mlabel} (0x{byte_val:02X})", mkey)
        self.move_combo.currentIndexChanged.connect(self._apply_changes)

        self.role_combo = QComboBox()
        for rkey, rlabel in NPC_ROLES:
            self.role_combo.addItem(rlabel, rkey)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)

        dlg_row = QHBoxLayout()
        self.tlk_combo = QComboBox()
        self.tlk_combo.currentIndexChanged.connect(self._apply_changes)
        self.btn_edit_dlg = QPushButton("💬 Éditer son dialogue ➔")
        self.btn_edit_dlg.clicked.connect(self._jump_to_dialogue)
        dlg_row.addWidget(self.tlk_combo, 1)
        dlg_row.addWidget(self.btn_edit_dlg)

        form.addRow("Nom du PNJ :", self.name_edit)
        form.addRow("Apparence (Sprite) :", self.sprite_combo)
        form.addRow("Position sur la carte :", coord_row)
        form.addRow("Comportement :", self.move_combo)
        form.addRow("Rôle moteur xU4 :", self.role_combo)
        form.addRow("Dialogue lié (.TLK) :", dlg_row)
        id_hbox.addLayout(form, 1)
        right_lay.addWidget(id_group)

        # Panneau boutique contextuel
        self.shop_group = QGroupBox("Configuration de Boutique / Service (vendors.b)")
        shop_form = QFormLayout(self.shop_group)

        self.shop_name_edit = QLineEdit()
        self.shop_name_edit.textEdited.connect(self._apply_changes)
        self.shop_owner_edit = QLineEdit()
        self.shop_owner_edit.textEdited.connect(self._apply_changes)
        self.shop_price_spin = QSpinBox()
        self.shop_price_spin.setRange(0, 9999)
        self.shop_price_spin.valueChanged.connect(self._apply_changes)
        self.shop_spec_edit = QLineEdit()
        self.shop_spec_edit.textEdited.connect(self._apply_changes)

        self.stock_container = QWidget()
        self.stock_layout = QVBoxLayout(self.stock_container)
        self.stock_layout.setContentsMargins(0, 0, 0, 0)

        shop_form.addRow("Nom de l'enseigne :", self.shop_name_edit)
        shop_form.addRow("Nom du marchand :", self.shop_owner_edit)
        shop_form.addRow("Prix de base (PO) :", self.shop_price_spin)
        shop_form.addRow("Spécialité (taverne) :", self.shop_spec_edit)
        shop_form.addRow("Catalogue / Stock :", self.stock_container)
        self.shop_group.setVisible(False)
        right_lay.addWidget(self.shop_group)

        right_lay.addStretch()
        scroll.setWidget(form_container)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

    def set_project(self, project: ScenarioProject) -> None:
        self.project = project
        self.refresh_from_project()

    def refresh_from_project(self) -> None:
        prev_id = self.current_city.id if self.current_city else None
        self.city_combo.blockSignals(True)
        self.city_combo.clear()
        cities = [m for m in sorted(self.project.maps, key=lambda x: x.id) if m.map_type == "city"]
        for c in cities:
            self.city_combo.addItem(f"[{c.id}] {c.name} ({c.fname})", c.id)
        self.city_combo.blockSignals(False)

        if not cities:
            self.current_city = None
            self.current_npc = None
            self.npc_list.clear()
            return

        target_idx = 0
        if prev_id is not None:
            found = self.city_combo.findData(prev_id)
            if found >= 0:
                target_idx = found
        self.city_combo.setCurrentIndex(target_idx)
        self._on_city_changed(target_idx)

    def _on_city_changed(self, index: int) -> None:
        if index < 0:
            return
        cid = self.city_combo.itemData(index)
        self.current_city = self.project.get_map(cid)
        if not self.current_city:
            return
        self.city_tlk_label.setText(f"Banque de dialogues : {self.current_city.tlk_fname or '(aucune)'}")
        self._refresh_tlk_combo()
        self._refresh_npc_list()

    def _refresh_tlk_combo(self) -> None:
        self.tlk_combo.blockSignals(True)
        self.tlk_combo.clear()
        self.tlk_combo.addItem("0 — Aucun dialogue .TLK (Rôle spécial / Muet)", 0)
        if self.current_city and self.current_city.tlk_fname:
            bank = sorted(self.project.dialogues.get(self.current_city.tlk_fname, []), key=lambda d: d.id)
            for d in bank:
                self.tlk_combo.addItem(f"#{d.id} — {d.name} ({d.keyword1.strip() or '-'})", d.id)
        self.tlk_combo.blockSignals(False)

    def _refresh_npc_list(self, select_slot: Optional[int] = None) -> None:
        self.npc_list.blockSignals(True)
        self.npc_list.clear()
        if not self.current_city:
            self.npc_list.blockSignals(False)
            return
        npcs = sorted(self.current_city.npcs, key=lambda n: n.slot_index)
        sel_row = 0
        for row_idx, n in enumerate(npcs):
            role_label = dict(NPC_ROLES).get(n.role, n.role)
            pm = self.tileset.get_pixmap(n.tile_id, 32)
            item = QListWidgetItem(
                QIcon(pm),
                f"[Slot {n.slot_index + 1}] {n.name} — ({n.x},{n.y}) | {role_label}",
            )
            item.setData(Qt.ItemDataRole.UserRole, n.slot_index)
            self.npc_list.addItem(item)
            if select_slot is not None and n.slot_index == select_slot:
                sel_row = row_idx
        self.npc_list.blockSignals(False)
        if npcs:
            self.npc_list.setCurrentRow(sel_row)
            self._on_npc_selected(sel_row)
        else:
            self.current_npc = None
            self.shop_group.setVisible(False)

    def _on_npc_selected(self, row: int) -> None:
        if not self.current_city or row < 0:
            self.current_npc = None
            return
        item = self.npc_list.item(row)
        if not item:
            return
        slot = int(item.data(Qt.ItemDataRole.UserRole))
        npc = next((n for n in self.current_city.npcs if n.slot_index == slot), None)
        if not npc:
            return
        self.current_npc = npc
        self._loading = True

        self.name_edit.setText(npc.name)
        sidx = self.sprite_combo.findData(npc.tile_id)
        if sidx < 0:
            self.sprite_combo.addItem(
                QIcon(self.tileset.get_pixmap(npc.tile_id, 24)), f"#{npc.tile_id}", npc.tile_id
            )
            sidx = self.sprite_combo.count() - 1
        self.sprite_combo.setCurrentIndex(sidx)

        self.x_spin.setValue(npc.x)
        self.y_spin.setValue(npc.y)
        self.slot_spin.setValue(npc.slot_index + 1)

        midx = self.move_combo.findData(npc.movement)
        if midx >= 0:
            self.move_combo.setCurrentIndex(midx)

        ridx = self.role_combo.findData(npc.role)
        if ridx >= 0:
            self.role_combo.setCurrentIndex(ridx)

        tidx = self.tlk_combo.findData(npc.tlk_index)
        self.tlk_combo.setCurrentIndex(tidx if tidx >= 0 else 0)

        self._update_shop_panel()
        self._update_sprite_preview()
        self._loading = False

    def _on_role_changed(self) -> None:
        if self._loading or not self.current_npc:
            return
        role = self.role_combo.currentData()
        if role in SHOP_ROLES and self.current_npc.shop_config is None:
            self.current_npc.shop_config = ShopConfig(
                shop_name=f"Échoppe de {self.current_npc.name}",
                owner_name=self.current_npc.name,
            )
        self._apply_changes()
        self._update_shop_panel()

    def _update_shop_panel(self) -> None:
        npc = self.current_npc
        if not npc or npc.role not in SHOP_ROLES:
            self.shop_group.setVisible(False)
            return
        if npc.shop_config is None:
            npc.shop_config = ShopConfig(shop_name=f"Échoppe de {npc.name}", owner_name=npc.name)
        sc = npc.shop_config
        self.shop_group.setVisible(True)
        self.shop_name_edit.setText(sc.shop_name)
        self.shop_owner_edit.setText(sc.owner_name)
        self.shop_price_spin.setValue(sc.price)
        self.shop_spec_edit.setText(sc.specialty_name)
        self.shop_spec_edit.setEnabled(npc.role == "tavernkeeper")

        # Reconstruire la liste d'articles si marchand d'armes/armures
        while self.stock_layout.count():
            child = self.stock_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._shop_item_checks.clear()

        if npc.role in ("weaponsvendor", "armorvendor"):
            catalog = WEAPONS_LIST if npc.role == "weaponsvendor" else ARMORS_LIST
            existing = {entry.split()[0] for entry in sc.inventory}
            for key, label_fr, default_price in catalog:
                chk = QCheckBox(f"{label_fr} ({default_price} PO)")
                chk.setChecked(key in existing)
                chk.toggled.connect(self._apply_changes)
                self._shop_item_checks[f"{key} {default_price}"] = chk
                self.stock_layout.addWidget(chk)
        else:
            info = QLabel("Service automatique géré par les règles xU4 (prix et enseigne personnalisés).")
            info.setStyleSheet("color: #9fb3c8;")
            self.stock_layout.addWidget(info)

    def _apply_changes(self) -> None:
        if self._loading or not self.current_npc:
            return
        npc = self.current_npc
        npc.name = self.name_edit.text().strip() or "Habitant"
        npc.tile_id = int(self.sprite_combo.currentData())
        npc.x = self.x_spin.value()
        npc.y = self.y_spin.value()
        npc.movement = self.move_combo.currentData()
        npc.role = self.role_combo.currentData()
        npc.tlk_index = int(self.tlk_combo.currentData() or 0)

        if npc.role in SHOP_ROLES and npc.shop_config is not None:
            sc = npc.shop_config
            sc.shop_name = self.shop_name_edit.text().strip() or "Boutique"
            sc.owner_name = self.shop_owner_edit.text().strip() or npc.name
            sc.price = self.shop_price_spin.value()
            sc.specialty_name = self.shop_spec_edit.text().strip()
            if self._shop_item_checks:
                sc.inventory = [k for k, chk in self._shop_item_checks.items() if chk.isChecked()]

        # Mettre à jour le texte de la liste sans perdre la sélection
        row = self.npc_list.currentRow()
        if row >= 0:
            item = self.npc_list.item(row)
            role_label = dict(NPC_ROLES).get(npc.role, npc.role)
            item.setIcon(QIcon(self.tileset.get_pixmap(npc.tile_id, 32)))
            item.setText(f"[Slot {npc.slot_index + 1}] {npc.name} — ({npc.x},{npc.y}) | {role_label}")
        self._update_sprite_preview()
        self.project_changed.emit()

    def _tick_anim(self) -> None:
        self._anim_frame = (self._anim_frame + 1) % 2
        self._update_sprite_preview()

    def _update_sprite_preview(self) -> None:
        if not self.current_npc:
            self.sprite_preview.clear()
            return
        tid = self.current_npc.tile_id
        t = TILES_BY_ID.get(tid)
        frame_tid = tid + (self._anim_frame if (t and t.frames > 1) else 0)
        self.sprite_preview.setPixmap(self.tileset.get_pixmap(frame_tid, 48))

    def _add_npc(self) -> None:
        if not self.current_city:
            return
        used = {n.slot_index for n in self.current_city.npcs}
        free_slot = next((s for s in range(32) if s not in used), None)
        if free_slot is None:
            QMessageBox.warning(self, "Limite atteinte", "Un fichier .ULT ne peut contenir que 32 PNJ maximum.")
            return
        new_npc = NPCData(
            slot_index=free_slot,
            name=f"Citizen {free_slot + 1}",
            tile_id=82,
            x=15,
            y=15,
            movement="wander",
            tlk_index=0,
            role="none",
        )
        self.current_city.npcs.append(new_npc)
        self._refresh_npc_list(select_slot=free_slot)
        self.project_changed.emit()

    def _delete_npc(self) -> None:
        if not self.current_city or not self.current_npc:
            return
        slot = self.current_npc.slot_index
        self.current_city.npcs = [n for n in self.current_city.npcs if n.slot_index != slot]
        self.current_npc = None
        self._refresh_npc_list()
        self.project_changed.emit()

    def _jump_to_dialogue(self) -> None:
        if not self.current_city or not self.current_npc:
            return
        bank = self.current_city.tlk_fname
        if not bank:
            QMessageBox.information(self, "Information", "Cette ville n'a pas de banque .TLK configurée.")
            return
        tid = self.current_npc.tlk_index or 1
        self.open_dialogue_requested.emit(bank, tid)
