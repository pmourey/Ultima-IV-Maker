"""Éditeur de Quêtes, Sanctuaires, Rumeurs de Taverne et Graphe d'Indices pour Ultima IV Maker."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import QUEST_ITEM_LABELS, VIRTUES
from ..models import (
    QuestData,
    QuestStep,
    ScenarioProject,
    ShrineConfig,
    TavernRumor,
)


class QuestEditorWidget(QWidget):
    """Onglet Quêtes, Sanctuaires/Mantras, Rumeurs et Graphe d'Indices."""

    project_changed = Signal()
    open_dialogue_requested = Signal(str, int)

    def __init__(self, project: ScenarioProject, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.project = project
        self._loading = False
        self._current_quest_idx: int = -1
        self._current_step_idx: int = -1
        self._current_rumor_idx: int = -1

        self._build_ui()
        self.refresh_from_project()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        self.sub_tabs = QTabWidget()
        root.addWidget(self.sub_tabs)

        self.sub_tabs.addTab(self._build_quests_tab(), "📜 Quêtes & Étapes")
        self.sub_tabs.addTab(self._build_shrines_rumors_tab(), "⛩ Sanctuaires & Rumeurs")
        self.sub_tabs.addTab(self._build_clue_graph_tab(), "🕸 Graphe d'Indices & Validateur")

        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)

    def _build_quests_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ---- Panneau gauche : liste des quêtes ----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        left_layout.addWidget(QLabel("<b>Quêtes du scénario</b>"))
        self.quest_list = QListWidget()
        self.quest_list.currentRowChanged.connect(self._on_quest_selected)
        left_layout.addWidget(self.quest_list)

        qbtn_row = QHBoxLayout()
        btn_add_q = QPushButton("➕ Nouvelle quête")
        btn_add_q.clicked.connect(self._add_quest)
        btn_del_q = QPushButton("🗑 Supprimer")
        btn_del_q.clicked.connect(self._delete_quest)
        qbtn_row.addWidget(btn_add_q)
        qbtn_row.addWidget(btn_del_q)
        left_layout.addLayout(qbtn_row)

        splitter.addWidget(left_panel)

        # ---- Panneau droit : détails de la quête + étapes ----
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        meta_box = QGroupBox("Informations de la quête")
        meta_form = QFormLayout(meta_box)

        self.quest_id_edit = QLineEdit()
        self.quest_id_edit.textChanged.connect(self._on_quest_field_edited)
        meta_form.addRow("Identifiant :", self.quest_id_edit)

        self.quest_title_edit = QLineEdit()
        self.quest_title_edit.textChanged.connect(self._on_quest_field_edited)
        meta_form.addRow("Titre :", self.quest_title_edit)

        self.quest_virtue_combo = QComboBox()
        for en_name, fr_name, *_ in VIRTUES:
            self.quest_virtue_combo.addItem(f"{fr_name} ({en_name})", en_name)
        self.quest_virtue_combo.currentIndexChanged.connect(self._on_quest_field_edited)
        meta_form.addRow("Vertu associée :", self.quest_virtue_combo)

        self.quest_main_chk = QCheckBox("Quête principale (requise pour l'Avatar)")
        self.quest_main_chk.toggled.connect(self._on_quest_field_edited)
        meta_form.addRow("", self.quest_main_chk)

        self.quest_reward_edit = QLineEdit()
        self.quest_reward_edit.textChanged.connect(self._on_quest_field_edited)
        meta_form.addRow("Récompense :", self.quest_reward_edit)

        self.quest_summary_edit = QPlainTextEdit()
        self.quest_summary_edit.setMaximumHeight(65)
        self.quest_summary_edit.textChanged.connect(self._on_quest_field_edited)
        meta_form.addRow("Résumé narratif :", self.quest_summary_edit)

        right_layout.addWidget(meta_box)

        # ---- Étapes de la quête ----
        steps_splitter = QSplitter(Qt.Orientation.Horizontal)
        right_layout.addWidget(steps_splitter, stretch=1)

        steps_left = QWidget()
        steps_left_layout = QVBoxLayout(steps_left)
        steps_left_layout.setContentsMargins(0, 0, 0, 0)
        steps_left_layout.addWidget(QLabel("<b>Étapes de progression</b>"))

        self.step_list = QListWidget()
        self.step_list.currentRowChanged.connect(self._on_step_selected)
        steps_left_layout.addWidget(self.step_list)

        sbtn_row = QHBoxLayout()
        btn_add_s = QPushButton("➕ Étape")
        btn_add_s.clicked.connect(self._add_step)
        btn_up_s = QPushButton("⬆")
        btn_up_s.setToolTip("Monter l'étape")
        btn_up_s.clicked.connect(lambda: self._move_step(-1))
        btn_down_s = QPushButton("⬇")
        btn_down_s.setToolTip("Descendre l'étape")
        btn_down_s.clicked.connect(lambda: self._move_step(1))
        btn_del_s = QPushButton("🗑")
        btn_del_s.setToolTip("Supprimer l'étape")
        btn_del_s.clicked.connect(self._delete_step)
        sbtn_row.addWidget(btn_add_s)
        sbtn_row.addWidget(btn_up_s)
        sbtn_row.addWidget(btn_down_s)
        sbtn_row.addWidget(btn_del_s)
        steps_left_layout.addLayout(sbtn_row)

        steps_splitter.addWidget(steps_left)

        step_detail_box = QGroupBox("Détail de l'étape sélectionnée (liens PNJ / Objets / Cartes)")
        step_form = QFormLayout(step_detail_box)

        self.step_id_edit = QLineEdit()
        self.step_id_edit.textChanged.connect(self._on_step_field_edited)
        step_form.addRow("ID étape :", self.step_id_edit)

        self.step_title_edit = QLineEdit()
        self.step_title_edit.textChanged.connect(self._on_step_field_edited)
        step_form.addRow("Intitulé :", self.step_title_edit)

        self.step_npc_combo = QComboBox()
        self.step_npc_combo.setEditable(True)
        self.step_npc_combo.currentTextChanged.connect(self._on_step_field_edited)
        step_form.addRow("PNJ donneur d'indice :", self.step_npc_combo)

        bank_row = QHBoxLayout()
        self.step_bank_combo = QComboBox()
        self.step_bank_combo.currentIndexChanged.connect(self._on_step_bank_changed)
        bank_row.addWidget(self.step_bank_combo, stretch=1)
        self.btn_jump_dlg = QPushButton("💬 Ouvrir dialogue")
        self.btn_jump_dlg.clicked.connect(self._jump_to_step_dialogue)
        bank_row.addWidget(self.btn_jump_dlg)
        step_form.addRow("Banque .TLK :", bank_row)

        self.step_keyword_combo = QComboBox()
        self.step_keyword_combo.setEditable(True)
        self.step_keyword_combo.currentTextChanged.connect(self._on_step_field_edited)
        step_form.addRow("Mot-clé à demander :", self.step_keyword_combo)

        self.step_label_combo = QComboBox()
        self.step_label_combo.setEditable(True)
        self.step_label_combo.currentTextChanged.connect(self._on_step_field_edited)
        step_form.addRow("Objet / Label xU4 :", self.step_label_combo)

        self.step_map_combo = QComboBox()
        self.step_map_combo.currentIndexChanged.connect(self._on_step_field_edited)
        step_form.addRow("Carte cible :", self.step_map_combo)

        coord_row = QHBoxLayout()
        self.step_coords_chk = QCheckBox("Coordonnées précises :")
        self.step_coords_chk.toggled.connect(self._on_step_field_edited)
        self.step_x_spin = QSpinBox()
        self.step_x_spin.setRange(0, 255)
        self.step_x_spin.valueChanged.connect(self._on_step_field_edited)
        self.step_y_spin = QSpinBox()
        self.step_y_spin.setRange(0, 255)
        self.step_y_spin.valueChanged.connect(self._on_step_field_edited)
        coord_row.addWidget(self.step_coords_chk)
        coord_row.addWidget(QLabel("X:"))
        coord_row.addWidget(self.step_x_spin)
        coord_row.addWidget(QLabel("Y:"))
        coord_row.addWidget(self.step_y_spin)
        coord_row.addStretch()
        step_form.addRow("Position cible :", coord_row)

        self.step_desc_edit = QPlainTextEdit()
        self.step_desc_edit.setMaximumHeight(85)
        self.step_desc_edit.textChanged.connect(self._on_step_field_edited)
        step_form.addRow("Notes / Solution :", self.step_desc_edit)

        steps_splitter.addWidget(step_detail_box)
        steps_splitter.setStretchFactor(0, 1)
        steps_splitter.setStretchFactor(1, 2)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        return tab

    def _build_shrines_rumors_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ---- Sanctuaires & Mantras ----
        shrine_box = QGroupBox("Sanctuaires & Mantras des 8 Vertus")
        shrine_layout = QVBoxLayout(shrine_box)

        info_shrine = QLabel(
            "Associez chaque Vertu à son Mantra de méditation et à la carte du Sanctuaire "
            "correspondant dans maps.b / config.b."
        )
        info_shrine.setWordWrap(True)
        shrine_layout.addWidget(info_shrine)

        self.shrines_table = QTableWidget(0, 4)
        self.shrines_table.setHorizontalHeaderLabels(["Vertu", "Mantra", "Carte Sanctuaire", "Rune associée"])
        self.shrines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        shrine_layout.addWidget(self.shrines_table)

        shrine_btns = QHBoxLayout()
        btn_reset_shrines = QPushButton("🔄 Initialiser / Compléter les 8 Vertus")
        btn_reset_shrines.clicked.connect(self._ensure_all_eight_shrines)
        shrine_btns.addWidget(btn_reset_shrines)
        shrine_btns.addStretch()
        shrine_layout.addLayout(shrine_btns)

        splitter.addWidget(shrine_box)

        # ---- Rumeurs de Taverne ----
        rumor_box = QGroupBox("Rumeurs de Taverne (Taverniers)")
        rumor_layout = QVBoxLayout(rumor_box)

        info_rumor = QLabel(
            "Les taverniers révèlent ces indices lorsque le joueur saisit le sujet "
            "après avoir payé le tarif indiqué en pièces d'or."
        )
        info_rumor.setWordWrap(True)
        rumor_layout.addWidget(info_rumor)

        self.rumor_list = QListWidget()
        self.rumor_list.currentRowChanged.connect(self._on_rumor_selected)
        rumor_layout.addWidget(self.rumor_list)

        rbtn_row = QHBoxLayout()
        btn_add_r = QPushButton("➕ Nouvelle rumeur")
        btn_add_r.clicked.connect(self._add_rumor)
        btn_del_r = QPushButton("🗑 Supprimer rumeur")
        btn_del_r.clicked.connect(self._delete_rumor)
        rbtn_row.addWidget(btn_add_r)
        rbtn_row.addWidget(btn_del_r)
        rumor_layout.addLayout(rbtn_row)

        rumor_form = QFormLayout()
        self.rumor_city_combo = QComboBox()
        self.rumor_city_combo.setEditable(True)
        self.rumor_city_combo.currentTextChanged.connect(self._on_rumor_field_edited)
        rumor_form.addRow("Ville / Taverne :", self.rumor_city_combo)

        self.rumor_topic_edit = QLineEdit()
        self.rumor_topic_edit.setPlaceholderText("ex: CALICE, MANTRA, RUNE")
        self.rumor_topic_edit.textChanged.connect(self._on_rumor_field_edited)
        rumor_form.addRow("Mot-clé / Sujet :", self.rumor_topic_edit)

        self.rumor_price_spin = QSpinBox()
        self.rumor_price_spin.setRange(0, 999)
        self.rumor_price_spin.setSuffix(" po")
        self.rumor_price_spin.valueChanged.connect(self._on_rumor_field_edited)
        rumor_form.addRow("Prix de l'indice :", self.rumor_price_spin)

        self.rumor_text_edit = QPlainTextEdit()
        self.rumor_text_edit.setMaximumHeight(90)
        self.rumor_text_edit.textChanged.connect(self._on_rumor_field_edited)
        rumor_form.addRow("Texte du tavernier :", self.rumor_text_edit)

        rumor_layout.addLayout(rumor_form)

        splitter.addWidget(rumor_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        return tab

    def _build_clue_graph_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_bar = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Actualiser le graphe & analyser les dépendances")
        btn_refresh.clicked.connect(self.rebuild_clue_graph)
        top_bar.addWidget(btn_refresh)

        btn_zoom_in = QPushButton("🔍 +")
        btn_zoom_in.clicked.connect(lambda: self.clue_view.scale(1.15, 1.15))
        btn_zoom_out = QPushButton("🔎 -")
        btn_zoom_out.clicked.connect(lambda: self.clue_view.scale(1 / 1.15, 1 / 1.15))
        btn_zoom_reset = QPushButton("⌖ 100%")
        btn_zoom_reset.clicked.connect(self._reset_graph_zoom)
        top_bar.addWidget(btn_zoom_in)
        top_bar.addWidget(btn_zoom_out)
        top_bar.addWidget(btn_zoom_reset)

        top_bar.addSpacing(12)
        legend = QLabel(
            "Légende : 🟦 Quête | 🟩 Lien valide (PNJ/Mot-clé/Label/Carte) | 🟧/🟥 Référence manquante"
        )
        top_bar.addWidget(legend)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, stretch=1)

        self.clue_scene = QGraphicsScene(self)
        self.clue_view = QGraphicsView(self.clue_scene)
        self.clue_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.clue_view.setBackgroundBrush(QBrush(QColor("#141820")))
        self.clue_view.setMinimumHeight(260)
        splitter.addWidget(self.clue_view)

        dep_box = QGroupBox("Validateur de dépendances narratives")
        dep_layout = QVBoxLayout(dep_box)
        self.dep_summary_label = QLabel("Analyse prête.")
        dep_layout.addWidget(self.dep_summary_label)

        self.dependency_table = QTableWidget(0, 3)
        self.dependency_table.setHorizontalHeaderLabels(["Sévérité", "Élément", "Diagnostic"])
        self.dependency_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dependency_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dependency_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        dep_layout.addWidget(self.dependency_table)

        splitter.addWidget(dep_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        return tab

    # ------------------------------------------------------------------
    # Rafraîchissement global & synchronisation
    # ------------------------------------------------------------------
    def set_project(self, project: ScenarioProject) -> None:
        self.project = project
        self._current_quest_idx = -1
        self._current_step_idx = -1
        self._current_rumor_idx = -1
        self.refresh_from_project()

    def refresh_from_project(self) -> None:
        self._loading = True
        try:
            self._populate_reference_combos()
            self._populate_quest_list()
            self._populate_shrines_table()
            self._populate_rumor_list()
        finally:
            self._loading = False

        self.rebuild_clue_graph()

    def _on_subtab_changed(self, index: int) -> None:
        if index == 2:
            self.rebuild_clue_graph()

    def _populate_reference_combos(self) -> None:
        # PNJ connus (sur cartes + dialogues)
        npc_names: Set[str] = set()
        for m in self.project.maps:
            for npc in m.npcs:
                if npc.name.strip():
                    npc_names.add(npc.name.strip())
        for dlgs in self.project.dialogues.values():
            for d in dlgs:
                if d.name.strip():
                    npc_names.add(d.name.strip())

        cur_npc = self.step_npc_combo.currentText()
        self.step_npc_combo.blockSignals(True)
        self.step_npc_combo.clear()
        self.step_npc_combo.addItem("")
        for name in sorted(npc_names):
            self.step_npc_combo.addItem(name)
        self.step_npc_combo.setCurrentText(cur_npc)
        self.step_npc_combo.blockSignals(False)

        # Banques .TLK
        cur_bank = self.step_bank_combo.currentData()
        self.step_bank_combo.blockSignals(True)
        self.step_bank_combo.clear()
        self.step_bank_combo.addItem("(aucune)", "")
        for bank_name in sorted(self.project.dialogues.keys()):
            self.step_bank_combo.addItem(bank_name, bank_name)
        idx_bank = self.step_bank_combo.findData(cur_bank)
        if idx_bank >= 0:
            self.step_bank_combo.setCurrentIndex(idx_bank)
        self.step_bank_combo.blockSignals(False)

        # Labels d'objets (existants sur cartes + catalogue xU4)
        cur_lbl = self.step_label_combo.currentText()
        self.step_label_combo.blockSignals(True)
        self.step_label_combo.clear()
        self.step_label_combo.addItem("")
        seen_labels: Set[str] = set()
        for m, lbl in self.project.all_labels():
            if lbl.name and lbl.name not in seen_labels:
                seen_labels.add(lbl.name)
                self.step_label_combo.addItem(f"{lbl.name} (sur {m.name})", lbl.name)
        for key, desc in QUEST_ITEM_LABELS:
            if key not in seen_labels:
                self.step_label_combo.addItem(f"{key} — {desc}", key)
        self.step_label_combo.setCurrentText(cur_lbl)
        self.step_label_combo.blockSignals(False)

        # Cartes cibles
        cur_map_id = self.step_map_combo.currentData()
        self.step_map_combo.blockSignals(True)
        self.step_map_combo.clear()
        self.step_map_combo.addItem("(aucune carte)", None)
        for m in self.project.maps:
            self.step_map_combo.addItem(f"[{m.id}] {m.name} ({m.map_type})", m.id)
        idx_map = self.step_map_combo.findData(cur_map_id)
        if idx_map >= 0:
            self.step_map_combo.setCurrentIndex(idx_map)
        self.step_map_combo.blockSignals(False)

        # Villes pour rumeurs
        cur_city = self.rumor_city_combo.currentText()
        self.rumor_city_combo.blockSignals(True)
        self.rumor_city_combo.clear()
        cities: List[str] = []
        for m in self.project.maps:
            if m.map_type == "city" and m.name not in cities:
                cities.append(m.name)
        if "Britain" not in cities:
            cities.append("Britain")
        for c in cities:
            self.rumor_city_combo.addItem(c)
        self.rumor_city_combo.setCurrentText(cur_city)
        self.rumor_city_combo.blockSignals(False)

    def _populate_keyword_combo(self, bank_name: str, keep_text: str) -> None:
        keywords: List[str] = ["", "JOB", "HEALTH"]
        seen: Set[str] = {"", "JOB", "HEALTH"}

        banks_to_scan = [bank_name] if bank_name and bank_name in self.project.dialogues else list(
            self.project.dialogues.keys()
        )
        for bname in banks_to_scan:
            for d in self.project.dialogues.get(bname, []):
                for kw in (d.keyword1, d.keyword2):
                    clean = kw.strip().upper()
                    if clean and clean != "A" and clean not in seen:
                        seen.add(clean)
                        keywords.append(clean)
                for topic in d.extra_topics:
                    clean = topic.keyword.strip().upper()
                    if clean and clean not in seen:
                        seen.add(clean)
                        keywords.append(clean)

        self.step_keyword_combo.blockSignals(True)
        self.step_keyword_combo.clear()
        for kw in keywords:
            self.step_keyword_combo.addItem(kw)
        self.step_keyword_combo.setCurrentText(keep_text)
        self.step_keyword_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Gestion des Quêtes
    # ------------------------------------------------------------------
    def _populate_quest_list(self) -> None:
        prev = self._current_quest_idx
        self.quest_list.blockSignals(True)
        self.quest_list.clear()
        for q in self.project.quests:
            prefix = "★" if q.is_main_quest else "•"
            self.quest_list.addItem(f"{prefix} {q.title} [{q.virtue}] ({len(q.steps)} étapes)")
        self.quest_list.blockSignals(False)

        if self.project.quests:
            target = prev if 0 <= prev < len(self.project.quests) else 0
            self.quest_list.setCurrentRow(target)
            self._load_quest_into_form(target)
        else:
            self._current_quest_idx = -1
            self._clear_quest_form()

    def _clear_quest_form(self) -> None:
        self._loading = True
        try:
            self.quest_id_edit.setText("")
            self.quest_title_edit.setText("")
            self.quest_reward_edit.setText("")
            self.quest_summary_edit.setPlainText("")
            self.step_list.clear()
            self._clear_step_form()
        finally:
            self._loading = False

    def _on_quest_selected(self, row: int) -> None:
        if self._loading:
            return
        self._load_quest_into_form(row)

    def _load_quest_into_form(self, row: int) -> None:
        if not (0 <= row < len(self.project.quests)):
            self._current_quest_idx = -1
            self._clear_quest_form()
            return
        self._current_quest_idx = row
        q = self.project.quests[row]

        self._loading = True
        try:
            self.quest_id_edit.setText(q.id)
            self.quest_title_edit.setText(q.title)
            idx_v = self.quest_virtue_combo.findData(q.virtue)
            self.quest_virtue_combo.setCurrentIndex(max(0, idx_v))
            self.quest_main_chk.setChecked(q.is_main_quest)
            self.quest_reward_edit.setText(q.reward)
            self.quest_summary_edit.setPlainText(q.summary)
            self._populate_step_list(q)
        finally:
            self._loading = False

    def _on_quest_field_edited(self) -> None:
        if self._loading or not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        q.id = self.quest_id_edit.text().strip() or f"quest_{self._current_quest_idx + 1}"
        q.title = self.quest_title_edit.text()
        q.virtue = self.quest_virtue_combo.currentData() or "Compassion"
        q.is_main_quest = self.quest_main_chk.isChecked()
        q.reward = self.quest_reward_edit.text()
        q.summary = self.quest_summary_edit.toPlainText()

        item = self.quest_list.item(self._current_quest_idx)
        if item:
            prefix = "★" if q.is_main_quest else "•"
            item.setText(f"{prefix} {q.title} [{q.virtue}] ({len(q.steps)} étapes)")
        self.project_changed.emit()

    def _add_quest(self) -> None:
        idx = len(self.project.quests) + 1
        new_q = QuestData(
            id=f"quest_{idx}",
            title=f"New Quest {idx}",
            virtue="Compassion",
            summary="Describe the goal of this quest.",
            is_main_quest=False,
            steps=[
                QuestStep(
                    id=f"q{idx}_step_1",
                    title="First Clue",
                    description="Speak to a citizen to gather information.",
                )
            ],
            reward="Blessing of Virtue",
        )
        self.project.quests.append(new_q)
        self._current_quest_idx = len(self.project.quests) - 1
        self._populate_quest_list()
        self.project_changed.emit()

    def _delete_quest(self) -> None:
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        self.project.quests.pop(self._current_quest_idx)
        self._current_quest_idx = min(self._current_quest_idx, len(self.project.quests) - 1)
        self._populate_quest_list()
        self.project_changed.emit()

    # ------------------------------------------------------------------
    # Gestion des Étapes de quête
    # ------------------------------------------------------------------
    def _populate_step_list(self, quest: QuestData) -> None:
        prev = self._current_step_idx
        self.step_list.blockSignals(True)
        self.step_list.clear()
        for i, s in enumerate(quest.steps, start=1):
            hint = f" [{s.npc_name}]" if s.npc_name else ""
            self.step_list.addItem(f"{i}. {s.title}{hint}")
        self.step_list.blockSignals(False)

        if quest.steps:
            target = prev if 0 <= prev < len(quest.steps) else 0
            self.step_list.setCurrentRow(target)
            self._load_step_into_form(quest, target)
        else:
            self._current_step_idx = -1
            self._clear_step_form()

    def _clear_step_form(self) -> None:
        self._loading = True
        try:
            self.step_id_edit.setText("")
            self.step_title_edit.setText("")
            self.step_npc_combo.setCurrentText("")
            self.step_bank_combo.setCurrentIndex(0)
            self._populate_keyword_combo("", "")
            self.step_label_combo.setCurrentText("")
            self.step_map_combo.setCurrentIndex(0)
            self.step_coords_chk.setChecked(False)
            self.step_x_spin.setValue(0)
            self.step_y_spin.setValue(0)
            self.step_desc_edit.setPlainText("")
        finally:
            self._loading = False

    def _on_step_selected(self, row: int) -> None:
        if self._loading or not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        self._load_step_into_form(self.project.quests[self._current_quest_idx], row)

    def _load_step_into_form(self, quest: QuestData, row: int) -> None:
        if not (0 <= row < len(quest.steps)):
            self._current_step_idx = -1
            self._clear_step_form()
            return
        self._current_step_idx = row
        s = quest.steps[row]

        self._loading = True
        try:
            self.step_id_edit.setText(s.id)
            self.step_title_edit.setText(s.title)
            self.step_npc_combo.setCurrentText(s.npc_name)

            idx_b = self.step_bank_combo.findData(s.dialogue_bank)
            self.step_bank_combo.setCurrentIndex(max(0, idx_b))
            self._populate_keyword_combo(s.dialogue_bank, s.keyword)

            idx_l = self.step_label_combo.findData(s.required_item_label)
            if idx_l >= 0:
                self.step_label_combo.setCurrentIndex(idx_l)
            else:
                self.step_label_combo.setCurrentText(s.required_item_label)

            idx_m = self.step_map_combo.findData(s.target_map_id)
            self.step_map_combo.setCurrentIndex(max(0, idx_m))

            has_coords = s.target_x is not None and s.target_y is not None
            self.step_coords_chk.setChecked(has_coords)
            self.step_x_spin.setEnabled(has_coords)
            self.step_y_spin.setEnabled(has_coords)
            self.step_x_spin.setValue(s.target_x if s.target_x is not None else 0)
            self.step_y_spin.setValue(s.target_y if s.target_y is not None else 0)

            self.step_desc_edit.setPlainText(s.description)
        finally:
            self._loading = False

    def _on_step_bank_changed(self) -> None:
        if self._loading:
            return
        bank = self.step_bank_combo.currentData() or ""
        cur_kw = self.step_keyword_combo.currentText()
        self._populate_keyword_combo(bank, cur_kw)
        self._on_step_field_edited()

    def _on_step_field_edited(self) -> None:
        if self._loading:
            return
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        if not (0 <= self._current_step_idx < len(q.steps)):
            return
        s = q.steps[self._current_step_idx]

        s.id = self.step_id_edit.text().strip() or f"{q.id}_step_{self._current_step_idx + 1}"
        s.title = self.step_title_edit.text()
        s.npc_name = self.step_npc_combo.currentText().strip()
        s.dialogue_bank = self.step_bank_combo.currentData() or ""
        s.keyword = self.step_keyword_combo.currentText().strip()

        # Si l'utilisateur a choisi une entrée du combo avec data, récupérer la data brute
        lbl_idx = self.step_label_combo.currentIndex()
        lbl_text = self.step_label_combo.currentText().strip()
        if lbl_idx >= 0 and self.step_label_combo.itemText(lbl_idx) == lbl_text and self.step_label_combo.itemData(lbl_idx):
            s.required_item_label = str(self.step_label_combo.itemData(lbl_idx))
        else:
            s.required_item_label = lbl_text.split(" ")[0] if "—" in lbl_text or "(sur " in lbl_text else lbl_text

        s.target_map_id = self.step_map_combo.currentData()

        use_coords = self.step_coords_chk.isChecked()
        self.step_x_spin.setEnabled(use_coords)
        self.step_y_spin.setEnabled(use_coords)
        if use_coords:
            s.target_x = self.step_x_spin.value()
            s.target_y = self.step_y_spin.value()
        else:
            s.target_x = None
            s.target_y = None

        s.description = self.step_desc_edit.toPlainText()

        item = self.step_list.item(self._current_step_idx)
        if item:
            hint = f" [{s.npc_name}]" if s.npc_name else ""
            item.setText(f"{self._current_step_idx + 1}. {s.title}{hint}")

        self.project_changed.emit()

    def _add_step(self) -> None:
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        idx = len(q.steps) + 1
        q.steps.append(
            QuestStep(
                id=f"{q.id}_step_{idx}",
                title=f"Step {idx}",
                description="",
            )
        )
        self._current_step_idx = len(q.steps) - 1
        self._populate_step_list(q)
        q_item = self.quest_list.item(self._current_quest_idx)
        if q_item:
            prefix = "★" if q.is_main_quest else "•"
            q_item.setText(f"{prefix} {q.title} [{q.virtue}] ({len(q.steps)} étapes)")
        self.project_changed.emit()

    def _move_step(self, delta: int) -> None:
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        src = self._current_step_idx
        dst = src + delta
        if not (0 <= src < len(q.steps) and 0 <= dst < len(q.steps)):
            return
        q.steps[src], q.steps[dst] = q.steps[dst], q.steps[src]
        self._current_step_idx = dst
        self._populate_step_list(q)
        self.project_changed.emit()

    def _delete_step(self) -> None:
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        if not (0 <= self._current_step_idx < len(q.steps)):
            return
        q.steps.pop(self._current_step_idx)
        self._current_step_idx = min(self._current_step_idx, len(q.steps) - 1)
        self._populate_step_list(q)
        q_item = self.quest_list.item(self._current_quest_idx)
        if q_item:
            prefix = "★" if q.is_main_quest else "•"
            q_item.setText(f"{prefix} {q.title} [{q.virtue}] ({len(q.steps)} étapes)")
        self.project_changed.emit()

    def _jump_to_step_dialogue(self) -> None:
        if not (0 <= self._current_quest_idx < len(self.project.quests)):
            return
        q = self.project.quests[self._current_quest_idx]
        if not (0 <= self._current_step_idx < len(q.steps)):
            return
        s = q.steps[self._current_step_idx]
        bank = s.dialogue_bank
        if not bank or bank not in self.project.dialogues:
            QMessageBox.information(
                self,
                "Dialogue non lié",
                "Sélectionnez d'abord une banque .TLK valide pour cette étape.",
            )
            return
        tlk_id = 1
        for d in self.project.dialogues[bank]:
            if s.npc_name and d.name.strip().lower() == s.npc_name.strip().lower():
                tlk_id = d.id
                break
        self.open_dialogue_requested.emit(bank, tlk_id)

    # ------------------------------------------------------------------
    # Sanctuaires & Mantras
    # ------------------------------------------------------------------
    def _populate_shrines_table(self) -> None:
        self.shrines_table.blockSignals(True)
        self.shrines_table.setRowCount(0)

        virtue_lookup = {en: (fr, default_mantra, rune_lbl) for en, fr, default_mantra, rune_lbl, _ in VIRTUES}
        shrine_maps = [m for m in self.project.maps]

        for row, shrine in enumerate(self.project.shrines):
            self.shrines_table.insertRow(row)
            fr_name, _, rune_lbl = virtue_lookup.get(shrine.virtue, (shrine.virtue, "", ""))

            v_item = QTableWidgetItem(f"{fr_name} ({shrine.virtue})")
            v_item.setFlags(v_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.shrines_table.setItem(row, 0, v_item)

            mantra_edit = QLineEdit(shrine.mantra)
            mantra_edit.textChanged.connect(lambda txt, r=row: self._on_shrine_mantra_changed(r, txt))
            self.shrines_table.setCellWidget(row, 1, mantra_edit)

            map_combo = QComboBox()
            for m in shrine_maps:
                tag = "⛩ " if m.map_type == "shrine" else ""
                map_combo.addItem(f"[{m.id}] {tag}{m.name}", m.id)
            idx = map_combo.findData(shrine.map_id)
            if idx >= 0:
                map_combo.setCurrentIndex(idx)
            map_combo.currentIndexChanged.connect(
                lambda _i, r=row, cb=map_combo: self._on_shrine_map_changed(r, cb.currentData())
            )
            self.shrines_table.setCellWidget(row, 2, map_combo)

            rune_placed = any(lbl.name == rune_lbl for _, lbl in self.project.all_labels())
            r_text = f"{rune_lbl} ({'placée' if rune_placed else 'non placée'})" if rune_lbl else "—"
            r_item = QTableWidgetItem(r_text)
            r_item.setFlags(r_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.shrines_table.setItem(row, 3, r_item)

        self.shrines_table.blockSignals(False)

    def _on_shrine_mantra_changed(self, row: int, text: str) -> None:
        if self._loading or not (0 <= row < len(self.project.shrines)):
            return
        shrine = self.project.shrines[row]
        shrine.mantra = text.strip().lower()
        target_map = self.project.get_map(shrine.map_id)
        if target_map and target_map.map_type == "shrine":
            target_map.shrine_mantra = shrine.mantra
        self.project_changed.emit()

    def _on_shrine_map_changed(self, row: int, map_id: Optional[int]) -> None:
        if self._loading or map_id is None or not (0 <= row < len(self.project.shrines)):
            return
        shrine = self.project.shrines[row]
        shrine.map_id = int(map_id)
        target_map = self.project.get_map(shrine.map_id)
        if target_map and target_map.map_type == "shrine":
            target_map.shrine_virtue = shrine.virtue
            target_map.shrine_mantra = shrine.mantra
        self.project_changed.emit()

    def _ensure_all_eight_shrines(self) -> None:
        existing = {s.virtue: s for s in self.project.shrines}
        shrine_maps = [m for m in self.project.maps if m.map_type == "shrine"]
        default_map_id = shrine_maps[0].id if shrine_maps else (self.project.maps[0].id if self.project.maps else 0)

        updated: List[ShrineConfig] = []
        for idx, (en_name, _fr, default_mantra, _rune, _stone) in enumerate(VIRTUES):
            if en_name in existing:
                updated.append(existing[en_name])
            else:
                mapped_id = shrine_maps[idx].id if idx < len(shrine_maps) else default_map_id
                updated.append(ShrineConfig(virtue=en_name, mantra=default_mantra, map_id=mapped_id))
        self.project.shrines = updated
        self._populate_shrines_table()
        self.project_changed.emit()

    # ------------------------------------------------------------------
    # Rumeurs de Taverne
    # ------------------------------------------------------------------
    def _populate_rumor_list(self) -> None:
        prev = self._current_rumor_idx
        self.rumor_list.blockSignals(True)
        self.rumor_list.clear()
        for r in self.project.rumors:
            self.rumor_list.addItem(f"[{r.city_name}] {r.topic} ({r.price} po)")
        self.rumor_list.blockSignals(False)

        if self.project.rumors:
            target = prev if 0 <= prev < len(self.project.rumors) else 0
            self.rumor_list.setCurrentRow(target)
            self._load_rumor_into_form(target)
        else:
            self._current_rumor_idx = -1
            self._clear_rumor_form()

    def _clear_rumor_form(self) -> None:
        self._loading = True
        try:
            self.rumor_city_combo.setCurrentText("Britain")
            self.rumor_topic_edit.setText("")
            self.rumor_price_spin.setValue(20)
            self.rumor_text_edit.setPlainText("")
        finally:
            self._loading = False

    def _on_rumor_selected(self, row: int) -> None:
        if self._loading:
            return
        self._load_rumor_into_form(row)

    def _load_rumor_into_form(self, row: int) -> None:
        if not (0 <= row < len(self.project.rumors)):
            self._current_rumor_idx = -1
            self._clear_rumor_form()
            return
        self._current_rumor_idx = row
        r = self.project.rumors[row]

        self._loading = True
        try:
            self.rumor_city_combo.setCurrentText(r.city_name)
            self.rumor_topic_edit.setText(r.topic)
            self.rumor_price_spin.setValue(r.price)
            self.rumor_text_edit.setPlainText(r.text)
        finally:
            self._loading = False

    def _on_rumor_field_edited(self) -> None:
        if self._loading or not (0 <= self._current_rumor_idx < len(self.project.rumors)):
            return
        r = self.project.rumors[self._current_rumor_idx]
        r.city_name = self.rumor_city_combo.currentText().strip() or "Britain"
        r.topic = self.rumor_topic_edit.text().strip()
        r.price = self.rumor_price_spin.value()
        r.text = self.rumor_text_edit.toPlainText()

        item = self.rumor_list.item(self._current_rumor_idx)
        if item:
            item.setText(f"[{r.city_name}] {r.topic} ({r.price} po)")
        self.project_changed.emit()

    def _add_rumor(self) -> None:
        city = self.rumor_city_combo.currentText().strip() or "Britain"
        self.project.rumors.append(
            TavernRumor(
                topic="CLUE",
                price=15,
                text="Travellers whisper that an ancient shrine hides a secret...",
                city_name=city,
            )
        )
        self._current_rumor_idx = len(self.project.rumors) - 1
        self._populate_rumor_list()
        self.project_changed.emit()

    def _delete_rumor(self) -> None:
        if not (0 <= self._current_rumor_idx < len(self.project.rumors)):
            return
        self.project.rumors.pop(self._current_rumor_idx)
        self._current_rumor_idx = min(self._current_rumor_idx, len(self.project.rumors) - 1)
        self._populate_rumor_list()
        self.project_changed.emit()

    # ------------------------------------------------------------------
    # Graphe d'Indices (QGraphicsScene) & Validateur de dépendances
    # ------------------------------------------------------------------
    def _reset_graph_zoom(self) -> None:
        self.clue_view.resetTransform()

    def _collect_project_indexes(self) -> Tuple[Set[str], Dict[str, List], Set[str]]:
        npc_names_lower: Set[str] = set()
        for m in self.project.maps:
            for npc in m.npcs:
                if npc.name.strip():
                    npc_names_lower.add(npc.name.strip().lower())
        for dlgs in self.project.dialogues.values():
            for d in dlgs:
                if d.name.strip():
                    npc_names_lower.add(d.name.strip().lower())

        labels_placed: Set[str] = {lbl.name for _, lbl in self.project.all_labels() if lbl.name}
        return npc_names_lower, self.project.dialogues, labels_placed

    def _keyword_exists_in_bank(self, bank_name: str, npc_name: str, keyword: str) -> bool:
        kw_up = keyword.strip().upper()
        if kw_up in {"", "JOB", "HEAL", "HEALTH", "LOOK", "NAME", "JOIN"}:
            return True
        banks = [bank_name] if bank_name and bank_name in self.project.dialogues else list(
            self.project.dialogues.keys()
        )
        for b in banks:
            for d in self.project.dialogues.get(b, []):
                if npc_name and d.name.strip().lower() != npc_name.strip().lower() and bank_name:
                    # Autoriser tout de même si le mot-clé existe dans la banque ciblée
                    pass
                kws = {d.keyword1.strip().upper(), d.keyword2.strip().upper()}
                kws.update(t.keyword.strip().upper() for t in d.extra_topics)
                if kw_up in kws:
                    return True
        return False

    def analyze_dependencies(self) -> List[Tuple[str, str, str]]:
        """Analyse les liens entre Quêtes, PNJ, Dialogues, Labels, Cartes et Sanctuaires."""
        findings: List[Tuple[str, str, str]] = []
        npc_names_lower, dialogues_map, labels_placed = self._collect_project_indexes()

        if not self.project.quests:
            findings.append(("warning", "Quêtes", "Aucune quête définie dans ce scénario."))

        for q in self.project.quests:
            if not q.steps:
                findings.append(("warning", q.title, "Cette quête ne contient aucune étape."))
                continue
            for idx, s in enumerate(q.steps, start=1):
                step_tag = f"{q.title} > #{idx} {s.title}"
                if s.npc_name.strip():
                    if s.npc_name.strip().lower() not in npc_names_lower:
                        findings.append(
                            (
                                "error",
                                step_tag,
                                f"PNJ introuvable : '{s.npc_name}' n'est placé sur aucune carte ni défini dans .TLK.",
                            )
                        )
                if s.dialogue_bank.strip():
                    if s.dialogue_bank not in dialogues_map:
                        findings.append(
                            (
                                "error",
                                step_tag,
                                f"Banque de dialogues manquante : '{s.dialogue_bank}'.",
                            )
                        )
                if s.keyword.strip():
                    if not self._keyword_exists_in_bank(s.dialogue_bank, s.npc_name, s.keyword):
                        findings.append(
                            (
                                "warning",
                                step_tag,
                                f"Mot-clé '{s.keyword.upper()}' absent des dialogues de '{s.dialogue_bank or 'toutes banques'}'.",
                            )
                        )
                if s.required_item_label.strip():
                    if s.required_item_label not in labels_placed:
                        findings.append(
                            (
                                "warning",
                                step_tag,
                                f"Objet/Label '{s.required_item_label}' non encore placé sur une carte.",
                            )
                        )
                if s.target_map_id is not None:
                    tmap = self.project.get_map(s.target_map_id)
                    if tmap is None:
                        findings.append(
                            (
                                "error",
                                step_tag,
                                f"Carte cible ID {s.target_map_id} introuvable.",
                            )
                        )
                    elif s.target_x is not None and s.target_y is not None:
                        if not (0 <= s.target_x < tmap.width and 0 <= s.target_y < tmap.height):
                            findings.append(
                                (
                                    "error",
                                    step_tag,
                                    f"Coordonnées ({s.target_x}, {s.target_y}) hors limites de '{tmap.name}' ({tmap.width}x{tmap.height}).",
                                )
                            )

        # Sanctuaires
        for shrine in self.project.shrines:
            if not shrine.mantra.strip():
                findings.append(("error", f"Sanctuaire {shrine.virtue}", "Mantra vide."))
            if self.project.get_map(shrine.map_id) is None:
                findings.append(
                    ("error", f"Sanctuaire {shrine.virtue}", f"Carte ID {shrine.map_id} inexistante.")
                )
        if len(self.project.shrines) < 8:
            findings.append(
                (
                    "warning",
                    "Sanctuaires",
                    f"Seulement {len(self.project.shrines)}/8 sanctuaires configurés pour les Vertus.",
                )
            )

        # Rumeurs
        city_names = {m.name.lower() for m in self.project.maps if m.map_type == "city"}
        for r in self.project.rumors:
            if not r.topic.strip() or not r.text.strip():
                findings.append(("warning", f"Rumeur ({r.city_name})", "Sujet ou texte de rumeur vide."))
            elif city_names and r.city_name.strip().lower() not in city_names:
                findings.append(
                    (
                        "warning",
                        f"Rumeur '{r.topic}'",
                        f"Ville '{r.city_name}' introuvable parmi les cartes de type 'city'.",
                    )
                )

        if not findings:
            findings.append(("info", "Cohérence Narrative", "Tous les liens Quêtes / PNJ / Labels / Sanctuaires sont valides !"))
        return findings

    def _draw_node(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        subtitle: str,
        fill_hex: str,
        border_hex: str,
    ) -> Tuple[float, float]:
        rect = QGraphicsRectItem(x, y, w, h)
        rect.setBrush(QBrush(QColor(fill_hex)))
        rect.setPen(QPen(QColor(border_hex), 2))
        self.clue_scene.addItem(rect)

        t_item = QGraphicsSimpleTextItem(title[:28] + ("…" if len(title) > 28 else ""))
        t_font = QFont("Sans", 9, QFont.Weight.Bold)
        t_item.setFont(t_font)
        t_item.setBrush(QBrush(QColor("#F3F4F6")))
        t_item.setPos(x + 8, y + 6)
        self.clue_scene.addItem(t_item)

        if subtitle:
            s_item = QGraphicsSimpleTextItem(subtitle[:34] + ("…" if len(subtitle) > 34 else ""))
            s_item.setFont(QFont("Sans", 8))
            s_item.setBrush(QBrush(QColor("#CBD5E1")))
            s_item.setPos(x + 8, y + 26)
            self.clue_scene.addItem(s_item)

        return (x + w, y + h / 2)

    def _draw_arrow(self, x1: float, y1: float, x2: float, y2: float, color_hex: str = "#64748B") -> None:
        pen = QPen(QColor(color_hex), 2)
        line = QGraphicsLineItem(x1, y1, x2, y2)
        line.setPen(pen)
        self.clue_scene.addItem(line)

    def rebuild_clue_graph(self) -> List[Tuple[str, str, str]]:
        """Reconstruit la scène graphique du graphe d'indices et met à jour le validateur."""
        self.clue_scene.clear()
        npc_names_lower, dialogues_map, labels_placed = self._collect_project_indexes()

        y_cursor = 20.0
        for q in self.project.quests:
            q_fill = "#1E3A5F" if q.is_main_quest else "#2A324B"
            q_border = "#60A5FA" if q.is_main_quest else "#94A3B8"
            qx_out, qy_out = self._draw_node(
                20.0,
                y_cursor,
                210.0,
                52.0,
                f"{'★ ' if q.is_main_quest else ''}{q.title}",
                f"Vertu : {q.virtue} ({len(q.steps)} étapes)",
                q_fill,
                q_border,
            )

            prev_x, prev_y = qx_out, qy_out
            x_step = 270.0
            max_branch_y = y_cursor + 70.0

            for idx, s in enumerate(q.steps, start=1):
                sx_out, sy_out = self._draw_node(
                    x_step,
                    y_cursor,
                    210.0,
                    52.0,
                    f"{idx}. {s.title}",
                    f"{s.dialogue_bank or 'Sans .TLK'}",
                    "#252B3B",
                    "#818CF8",
                )
                self._draw_arrow(prev_x, prev_y, x_step, y_cursor + 26.0, "#60A5FA")

                # Badges de dépendances sous l'étape
                badge_y = y_cursor + 64.0
                if s.npc_name.strip():
                    ok = s.npc_name.strip().lower() in npc_names_lower
                    self._draw_node(
                        x_step + 12.0,
                        badge_y,
                        198.0,
                        42.0,
                        f"👤 {s.npc_name}",
                        f"Mot-clé : {s.keyword.upper()}" if s.keyword else "Dialogue général",
                        "#17382B" if ok else "#4A1E24",
                        "#34D399" if ok else "#F87171",
                    )
                    self._draw_arrow(x_step + 6.0, y_cursor + 52.0, x_step + 12.0, badge_y + 21.0, "#475569")
                    badge_y += 50.0

                if s.keyword.strip():
                    kw_ok = self._keyword_exists_in_bank(s.dialogue_bank, s.npc_name, s.keyword)
                    if not s.npc_name.strip() or not kw_ok:
                        self._draw_node(
                            x_step + 12.0,
                            badge_y,
                            198.0,
                            40.0,
                            f"💬 {s.keyword.upper()}",
                            "Mot-clé vérifié" if kw_ok else "⚠️ Absent du .TLK",
                            "#17382B" if kw_ok else "#4B3516",
                            "#34D399" if kw_ok else "#FBBF24",
                        )
                        self._draw_arrow(x_step + 6.0, y_cursor + 52.0, x_step + 12.0, badge_y + 20.0, "#475569")
                        badge_y += 48.0

                if s.required_item_label.strip():
                    lbl_ok = s.required_item_label in labels_placed
                    self._draw_node(
                        x_step + 12.0,
                        badge_y,
                        198.0,
                        40.0,
                        f"🗝 {s.required_item_label}",
                        "Placé sur carte" if lbl_ok else "⚠️ Label non placé",
                        "#17382B" if lbl_ok else "#4B3516",
                        "#34D399" if lbl_ok else "#FBBF24",
                    )
                    self._draw_arrow(x_step + 6.0, y_cursor + 52.0, x_step + 12.0, badge_y + 20.0, "#475569")
                    badge_y += 48.0

                if s.target_map_id is not None:
                    tmap = self.project.get_map(s.target_map_id)
                    map_ok = tmap is not None
                    coords_str = f" ({s.target_x},{s.target_y})" if s.target_x is not None else ""
                    self._draw_node(
                        x_step + 12.0,
                        badge_y,
                        198.0,
                        40.0,
                        f"🗺 {tmap.name if tmap else f'Map #{s.target_map_id}'}",
                        f"ID {s.target_map_id}{coords_str}",
                        "#17382B" if map_ok else "#4A1E24",
                        "#34D399" if map_ok else "#F87171",
                    )
                    self._draw_arrow(x_step + 6.0, y_cursor + 52.0, x_step + 12.0, badge_y + 20.0, "#475569")
                    badge_y += 48.0

                max_branch_y = max(max_branch_y, badge_y + 10.0)
                prev_x, prev_y = sx_out, sy_out
                x_step += 250.0

            y_cursor = max_branch_y + 24.0

        # Bandeau Sanctuaires & Rumeurs en bas du graphe
        if self.project.shrines:
            sx = 20.0
            for shrine in self.project.shrines:
                tmap = self.project.get_map(shrine.map_id)
                ok = bool(shrine.mantra.strip()) and tmap is not None
                self._draw_node(
                    sx,
                    y_cursor,
                    165.0,
                    44.0,
                    f"⛩ {shrine.virtue}",
                    f"Mantra: {shrine.mantra.upper() or '?'} -> {tmap.name if tmap else '?'}",
                    "#1F2937" if ok else "#4A1E24",
                    "#A78BFA" if ok else "#F87171",
                )
                sx += 180.0
            y_cursor += 64.0

        if self.project.rumors:
            rx = 20.0
            for rumor in self.project.rumors:
                self._draw_node(
                    rx,
                    y_cursor,
                    185.0,
                    44.0,
                    f"🍺 {rumor.topic or '?'} ({rumor.price} po)",
                    f"Taverne de {rumor.city_name}",
                    "#2D241E",
                    "#F59E0B",
                )
                rx += 200.0
            y_cursor += 60.0

        self.clue_scene.setSceneRect(self.clue_scene.itemsBoundingRect().adjusted(-20, -20, 40, 40))

        # Remplissage table de dépendances
        findings = self.analyze_dependencies()
        self.dependency_table.setRowCount(len(findings))
        err_count = 0
        warn_count = 0
        for row, (sev, elem, msg) in enumerate(findings):
            if sev == "error":
                err_count += 1
                sev_lbl = "❌ Erreur"
                color = QColor("#FCA5A5")
            elif sev == "warning":
                warn_count += 1
                sev_lbl = "⚠️ Avertissement"
                color = QColor("#FCD34D")
            else:
                sev_lbl = "✅ OK"
                color = QColor("#86EFAC")

            i0 = QTableWidgetItem(sev_lbl)
            i0.setForeground(QBrush(color))
            i1 = QTableWidgetItem(elem)
            i2 = QTableWidgetItem(msg)
            self.dependency_table.setItem(row, 0, i0)
            self.dependency_table.setItem(row, 1, i1)
            self.dependency_table.setItem(row, 2, i2)

        self.dep_summary_label.setText(
            f"Analyse : {err_count} erreur(s), {warn_count} avertissement(s) sur "
            f"{len(self.project.quests)} quête(s), {len(self.project.shrines)} sanctuaire(s), "
            f"{len(self.project.rumors)} rumeur(s)."
        )
        return findings
