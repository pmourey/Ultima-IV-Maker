"""Éditeur de dialogues (.TLK) avec jauge mémoire 288 octets et simulateur Ultima IV en direct."""

from __future__ import annotations

import random
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..binary_io import TLK_BLOCK_SIZE, calculate_tlk_bytes, normalize_u4_ascii
from ..constants import QUESTION_TRIGGERS
from ..models import DialogueData, ScenarioProject


class DialogueEditorWidget(QWidget):
    """Onglet Éditeur de Dialogues .TLK + Simulateur interactif."""

    project_changed = Signal()

    def __init__(self, project: ScenarioProject, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.project = project
        self.current_bank: str = ""
        self.current_dlg: Optional[DialogueData] = None
        self._loading = False
        self._sim_waiting_yn = False

        self._build_ui()
        self.refresh_from_project()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Barre de sélection de banque .TLK
        top = QHBoxLayout()
        top.addWidget(QLabel("Banque de dialogues (.TLK) :"))
        self.bank_combo = QComboBox()
        self.bank_combo.setMinimumWidth(220)
        self.bank_combo.currentIndexChanged.connect(self._on_bank_selected)
        top.addWidget(self.bank_combo)

        btn_new_bank = QPushButton("+ Nouvelle banque")
        btn_new_bank.clicked.connect(self._create_bank)
        top.addWidget(btn_new_bank)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Colonne 1 : Liste des dialogues (1..16)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.addWidget(QLabel("Dialogues (max 16 par .TLK) :"))
        self.dlg_list = QListWidget()
        self.dlg_list.currentRowChanged.connect(self._on_dlg_selected)
        left_lay.addWidget(self.dlg_list, 1)
        l_btns = QHBoxLayout()
        btn_add = QPushButton("+ Ajouter")
        btn_add.clicked.connect(self._add_dialogue)
        btn_del = QPushButton("Supprimer")
        btn_del.clicked.connect(self._delete_dialogue)
        l_btns.addWidget(btn_add)
        l_btns.addWidget(btn_del)
        left_lay.addLayout(l_btns)
        splitter.addWidget(left)

        # Colonne 2 : Formulaire guidé + Jauge 288 octets
        center_scroll = QScrollArea()
        center_scroll.setWidgetResizable(True)
        center_w = QWidget()
        center_lay = QVBoxLayout(center_w)

        # Jauge 288 octets
        gauge_box = QGroupBox("Mémoire binaire .TLK (limite stricte : 288 octets par PNJ)")
        g_lay = QVBoxLayout(gauge_box)
        self.tlk_bar = QProgressBar()
        self.tlk_bar.setRange(0, TLK_BLOCK_SIZE)
        self.tlk_bar.setFormat("%v / 288 octets")
        self.tlk_detail_lbl = QLabel("")
        self.tlk_detail_lbl.setStyleSheet("color: #9fb3c8; font-size: 11px;")
        g_lay.addWidget(self.tlk_bar)
        g_lay.addWidget(self.tlk_detail_lbl)
        center_lay.addWidget(gauge_box)

        # Identité & réponses standards
        id_box = QGroupBox("Identité et Réponses de Base")
        form1 = QFormLayout(id_box)
        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._apply_changes)
        self.pronoun_combo = QComboBox()
        self.pronoun_combo.setEditable(True)
        self.pronoun_combo.addItems(["He", "She", "It"])
        self.pronoun_combo.currentTextChanged.connect(self._apply_changes)

        self.look_edit = QLineEdit()
        self.look_edit.setPlaceholderText("ex: un vieux forgeron robuste.")
        self.look_edit.textEdited.connect(self._apply_changes)

        self.job_edit = QPlainTextEdit()
        self.job_edit.setMaximumHeight(54)
        self.job_edit.textChanged.connect(self._apply_changes)

        self.health_edit = QPlainTextEdit()
        self.health_edit.setMaximumHeight(46)
        self.health_edit.textChanged.connect(self._apply_changes)

        form1.addRow("Nom (NAME) :", self.name_edit)
        form1.addRow("Pronom :", self.pronoun_combo)
        form1.addRow("Description (LOOK) :", self.look_edit)
        form1.addRow("Métier (JOB) :", self.job_edit)
        form1.addRow("Santé (HEAL) :", self.health_edit)
        center_lay.addWidget(id_box)

        # Mots-clés personnalisés
        kw_box = QGroupBox("Mots-clés d'Enquête (4 lettres reconnues par Ultima IV)")
        kw_form = QFormLayout(kw_box)

        self.kw1_edit = QLineEdit()
        self.kw1_edit.setMaxLength(12)
        self.kw1_edit.setPlaceholderText("ex: RUNE (4 lettres max en binaire)")
        self.kw1_edit.textEdited.connect(self._apply_changes)
        self.resp1_edit = QPlainTextEdit()
        self.resp1_edit.setMaximumHeight(54)
        self.resp1_edit.textChanged.connect(self._apply_changes)

        self.kw2_edit = QLineEdit()
        self.kw2_edit.setMaxLength(12)
        self.kw2_edit.setPlaceholderText("ex: MANT (laisser vide ou 'A' si inutilisé)")
        self.kw2_edit.textEdited.connect(self._apply_changes)
        self.resp2_edit = QPlainTextEdit()
        self.resp2_edit.setMaximumHeight(54)
        self.resp2_edit.textChanged.connect(self._apply_changes)

        kw_form.addRow("Mot-clé 1 :", self.kw1_edit)
        kw_form.addRow("Réponse 1 :", self.resp1_edit)
        kw_form.addRow("Mot-clé 2 :", self.kw2_edit)
        kw_form.addRow("Réponse 2 :", self.resp2_edit)
        center_lay.addWidget(kw_box)

        # Question Oui/Non et Karma
        yn_box = QGroupBox("Question Oui / Non & Comportement Moral")
        yn_form = QFormLayout(yn_box)
        self.trigger_combo = QComboBox()
        for code, label in QUESTION_TRIGGERS:
            self.trigger_combo.addItem(label, code)
        self.trigger_combo.currentIndexChanged.connect(self._apply_changes)

        self.question_edit = QLineEdit()
        self.question_edit.textEdited.connect(self._apply_changes)
        self.yes_edit = QLineEdit()
        self.yes_edit.textEdited.connect(self._apply_changes)
        self.no_edit = QLineEdit()
        self.no_edit.textEdited.connect(self._apply_changes)

        self.humility_chk = QCheckBox("Cette question teste l'Humilité (Oui = orgueil -, Non = humble +)")
        self.humility_chk.toggled.connect(self._apply_changes)

        prob_row = QHBoxLayout()
        self.turn_slider = QSlider(Qt.Orientation.Horizontal)
        self.turn_slider.setRange(0, 255)
        self.turn_slider.valueChanged.connect(self._apply_changes)
        self.turn_lbl = QLabel("0 / 255 (Jamais)")
        prob_row.addWidget(self.turn_slider, 1)
        prob_row.addWidget(self.turn_lbl)

        yn_form.addRow("Déclencher après :", self.trigger_combo)
        yn_form.addRow("Question posée :", self.question_edit)
        yn_form.addRow("Si joueur dit OUI :", self.yes_edit)
        yn_form.addRow("Si joueur dit NON :", self.no_edit)
        yn_form.addRow(self.humility_chk)
        yn_form.addRow("Fuite / Hostilité :", prob_row)
        center_lay.addWidget(yn_box)

        center_lay.addStretch()
        center_scroll.setWidget(center_w)
        splitter.addWidget(center_scroll)

        # Colonne 3 : Simulateur de conversation Ultima IV en direct
        sim_box = QGroupBox("Simulateur de Conversation xU4 en direct")
        sim_lay = QVBoxLayout(sim_box)

        self.sim_screen = QTextEdit()
        self.sim_screen.setReadOnly(True)
        self.sim_screen.setFont(QFont("Courier New", 11))
        self.sim_screen.setStyleSheet(
            "background-color: #07090f; color: #f5f5f5; border: 2px solid #5bc0eb; padding: 6px;"
        )
        sim_lay.addWidget(self.sim_screen, 1)

        # Boutons rapides d'interaction
        quick_grid = QGridLayout()
        self.quick_buttons: dict[str, QPushButton] = {}
        quick_specs = [
            ("name", "NAME", 0, 0),
            ("look", "LOOK", 0, 1),
            ("job", "JOB", 0, 2),
            ("heal", "HEAL", 0, 3),
            ("kw1", "Mot-clé 1", 1, 0),
            ("kw2", "Mot-clé 2", 1, 1),
            ("give", "GIVE", 1, 2),
            ("join", "JOIN", 1, 3),
            ("yes", "YES (OUI)", 2, 0),
            ("no", "NO (NON)", 2, 1),
            ("bye", "BYE", 2, 2),
        ]
        for key, text, r, c in quick_specs:
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, k=key: self._sim_quick(k))
            self.quick_buttons[key] = btn
            quick_grid.addWidget(btn, r, c)

        btn_restart = QPushButton("🔄 Recommencer")
        btn_restart.clicked.connect(self._sim_restart)
        quick_grid.addWidget(btn_restart, 2, 3)
        sim_lay.addLayout(quick_grid)

        input_row = QHBoxLayout()
        self.sim_input = QLineEdit()
        self.sim_input.setPlaceholderText("Tapez un mot-clé (ex: job, rune, bye) et appuyez sur Entrée...")
        self.sim_input.returnPressed.connect(self._sim_send_input)
        btn_send = QPushButton("Dire")
        btn_send.clicked.connect(self._sim_send_input)
        input_row.addWidget(self.sim_input, 1)
        input_row.addWidget(btn_send)
        sim_lay.addLayout(input_row)

        splitter.addWidget(sim_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

    def set_project(self, project: ScenarioProject) -> None:
        self.project = project
        self.refresh_from_project()

    def select_dialogue(self, bank_name: str, tlk_id: int) -> None:
        idx = self.bank_combo.findData(bank_name)
        if idx >= 0:
            self.bank_combo.setCurrentIndex(idx)
            self._on_bank_selected(idx)
            for row in range(self.dlg_list.count()):
                item = self.dlg_list.item(row)
                if item and int(item.data(Qt.ItemDataRole.UserRole)) == tlk_id:
                    self.dlg_list.setCurrentRow(row)
                    break

    def refresh_from_project(self) -> None:
        prev_bank = self.current_bank
        self.bank_combo.blockSignals(True)
        self.bank_combo.clear()
        for bank in sorted(self.project.dialogues.keys()):
            self.bank_combo.addItem(bank, bank)
        self.bank_combo.blockSignals(False)

        if not self.project.dialogues:
            self.current_bank = ""
            self.dlg_list.clear()
            self.current_dlg = None
            return

        idx = self.bank_combo.findData(prev_bank)
        self.bank_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._on_bank_selected(self.bank_combo.currentIndex())

    def _on_bank_selected(self, idx: int) -> None:
        if idx < 0:
            return
        self.current_bank = self.bank_combo.itemData(idx)
        self._refresh_dlg_list()

    def _create_bank(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Nouvelle banque de dialogues", "Nom du fichier .TLK (ex: yew.tlk) :"
        )
        if not ok or not name.strip():
            return
        bname = name.strip().lower()
        if not bname.endswith(".tlk"):
            bname += ".tlk"
        if bname not in self.project.dialogues:
            self.project.dialogues[bname] = [
                DialogueData(id=1, bank_name=bname, name="Citizen 1")
            ]
        self.refresh_from_project()
        idx = self.bank_combo.findData(bname)
        if idx >= 0:
            self.bank_combo.setCurrentIndex(idx)
        self.project_changed.emit()

    def _refresh_dlg_list(self, select_id: Optional[int] = None) -> None:
        self.dlg_list.blockSignals(True)
        self.dlg_list.clear()
        dlgs = sorted(self.project.dialogues.get(self.current_bank, []), key=lambda d: d.id)
        sel_row = 0
        for r, d in enumerate(dlgs):
            kw1 = d.keyword1.strip()
            kw_hint = f"[{kw1}]" if kw1 and kw1 != "A" else ""
            item = QListWidgetItem(f"#{d.id} — {d.name} {kw_hint}")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            self.dlg_list.addItem(item)
            if select_id is not None and d.id == select_id:
                sel_row = r
        self.dlg_list.blockSignals(False)
        if dlgs:
            self.dlg_list.setCurrentRow(sel_row)
            self._on_dlg_selected(sel_row)
        else:
            self.current_dlg = None
            self.sim_screen.clear()

    def _on_dlg_selected(self, row: int) -> None:
        if row < 0 or not self.current_bank:
            self.current_dlg = None
            return
        item = self.dlg_list.item(row)
        if not item:
            return
        did = int(item.data(Qt.ItemDataRole.UserRole))
        dlg = self.project.get_dialogue(self.current_bank, did)
        if not dlg:
            return
        self.current_dlg = dlg
        self._loading = True

        self.name_edit.setText(dlg.name)
        self.pronoun_combo.setCurrentText(dlg.pronoun)
        self.look_edit.setText(dlg.look)
        self.job_edit.setPlainText(dlg.job)
        self.health_edit.setPlainText(dlg.health)
        self.kw1_edit.setText("" if dlg.keyword1.strip() == "A" else dlg.keyword1.strip())
        self.resp1_edit.setPlainText(dlg.response1)
        self.kw2_edit.setText("" if dlg.keyword2.strip() == "A" else dlg.keyword2.strip())
        self.resp2_edit.setPlainText(dlg.response2)

        tidx = self.trigger_combo.findData(dlg.question_trigger)
        self.trigger_combo.setCurrentIndex(tidx if tidx >= 0 else 0)
        self.question_edit.setText(dlg.question)
        self.yes_edit.setText(dlg.yes_response)
        self.no_edit.setText(dlg.no_response)
        self.humility_chk.setChecked(dlg.affects_humility)
        self.turn_slider.setValue(dlg.turn_away_prob)

        self._update_byte_gauge()
        self._update_quick_labels()
        self._loading = False
        self._sim_restart()

    def _apply_changes(self) -> None:
        if self._loading or not self.current_dlg:
            return
        d = self.current_dlg
        d.name = self.name_edit.text().strip() or "PNJ"
        d.pronoun = self.pronoun_combo.currentText().strip() or "He"
        d.look = self.look_edit.text().strip()
        d.job = self.job_edit.toPlainText().strip()
        d.health = self.health_edit.toPlainText().strip()
        d.keyword1 = self.kw1_edit.text().strip().upper() or "A   "
        d.response1 = self.resp1_edit.toPlainText().strip()
        d.keyword2 = self.kw2_edit.text().strip().upper() or "A   "
        d.response2 = self.resp2_edit.toPlainText().strip()
        d.question_trigger = int(self.trigger_combo.currentData() or 0)
        d.question = self.question_edit.text().strip()
        d.yes_response = self.yes_edit.text().strip()
        d.no_response = self.no_edit.text().strip()
        d.affects_humility = self.humility_chk.isChecked()
        d.turn_away_prob = self.turn_slider.value()

        row = self.dlg_list.currentRow()
        if row >= 0:
            kw1 = d.keyword1.strip()
            kw_hint = f"[{kw1}]" if kw1 and kw1 != "A" else ""
            self.dlg_list.item(row).setText(f"#{d.id} — {d.name} {kw_hint}")

        self._update_byte_gauge()
        self._update_quick_labels()
        self.project_changed.emit()

    def _update_byte_gauge(self) -> None:
        if not self.current_dlg:
            return
        total, breakdown = calculate_tlk_bytes(self.current_dlg)
        self.tlk_bar.setValue(min(total, TLK_BLOCK_SIZE))
        self.tlk_bar.setFormat(f"{total} / {TLK_BLOCK_SIZE} octets")
        if total <= 240:
            color = "#2ec4b6"
        elif total <= TLK_BLOCK_SIZE:
            color = "#ff9f1c"
        else:
            color = "#e71d36"
        self.tlk_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; }} QProgressBar {{ text-align: center; }}"
        )
        prob = self.turn_slider.value()
        pct = int(round(prob * 100 / 256))
        self.turn_lbl.setText(f"{prob} / 255 ({pct}%)")

        status = "OK" if total <= TLK_BLOCK_SIZE else f"DÉPASSEMENT DE {total - TLK_BLOCK_SIZE} OCTETS"
        self.tlk_detail_lbl.setText(
            f"Statut : {status} | Champs : Nom={breakdown['Nom']}o, Look={breakdown['Description (LOOK)']}o, "
            f"Job={breakdown['Métier (JOB)']}o, R1={breakdown['Réponse 1']}o, R2={breakdown['Réponse 2']}o"
        )

    def _update_quick_labels(self) -> None:
        if not self.current_dlg:
            return
        k1 = self.current_dlg.keyword1.strip()
        k2 = self.current_dlg.keyword2.strip()
        self.quick_buttons["kw1"].setText(k1[:4] if (k1 and k1 != "A") else "Mot 1")
        self.quick_buttons["kw2"].setText(k2[:4] if (k2 and k2 != "A") else "Mot 2")

    def _add_dialogue(self) -> None:
        if not self.current_bank:
            return
        dlgs = self.project.dialogues.setdefault(self.current_bank, [])
        if len(dlgs) >= 16:
            QMessageBox.warning(self, "Limite .TLK", "Un fichier .TLK contient au maximum 16 PNJ.")
            return
        used = {d.id for d in dlgs}
        new_id = next(i for i in range(1, 17) if i not in used)
        dlgs.append(DialogueData(id=new_id, bank_name=self.current_bank, name=f"Citizen #{new_id}"))
        self._refresh_dlg_list(select_id=new_id)
        self.project_changed.emit()

    def _delete_dialogue(self) -> None:
        if not self.current_bank or not self.current_dlg:
            return
        did = self.current_dlg.id
        self.project.dialogues[self.current_bank] = [
            d for d in self.project.dialogues[self.current_bank] if d.id != did
        ]
        self._refresh_dlg_list()
        self.project_changed.emit()

    # ---------------- Simulateur de conversation Ultima IV ----------------

    def _sim_append(self, text: str, color: str = "#f5f5f5") -> None:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        self.sim_screen.append(f'<span style="color:{color};">{safe}</span>')

    def _sim_restart(self) -> None:
        self.sim_screen.clear()
        self._sim_waiting_yn = False
        d = self.current_dlg
        if not d:
            return
        self._sim_append(f"You meet {d.look or 'someone.'}", "#e6b84c")
        self._sim_append(f"{d.pronoun} says: I am {d.name}", "#5bc0eb")
        self._sim_append("\nYour Interest:", "#9fb3c8")

    def _sim_quick(self, key: str) -> None:
        if not self.current_dlg:
            return
        if key == "kw1":
            word = self.current_dlg.keyword1.strip()
            if not word or word == "A":
                return
        elif key == "kw2":
            word = self.current_dlg.keyword2.strip()
            if not word or word == "A":
                return
        else:
            word = key
        self._process_sim_input(word)

    def _sim_send_input(self) -> None:
        txt = self.sim_input.text().strip()
        self.sim_input.clear()
        self._process_sim_input(txt)

    def _process_sim_input(self, raw_input: str) -> None:
        d = self.current_dlg
        if not d:
            return
        clean = normalize_u4_ascii(raw_input).decode("ascii").strip().lower()
        self._sim_append(f"> {raw_input or '(none)'}", "#a8dadc")

        if self._sim_waiting_yn:
            if clean.startswith("y"):
                self._sim_append(d.yes_response or "...", "#ffffff")
                if d.affects_humility:
                    self._sim_append("[Karma: -5 Humility (Pride!)]", "#ff595e")
                self._sim_waiting_yn = False
                self._sim_append("\nYour Interest:", "#9fb3c8")
            elif clean.startswith("n"):
                self._sim_append(d.no_response or "...", "#ffffff")
                if d.affects_humility:
                    self._sim_append("[Karma: +5 Humility]", "#8ac926")
                self._sim_waiting_yn = False
                self._sim_append("\nYour Interest:", "#9fb3c8")
            else:
                self._sim_append("Yes or no!", "#ffd166")
            return

        if not clean or clean.startswith("bye"):
            self._sim_append("Bye.", "#e6b84c")
            return

        if d.turn_away_prob > 0:
            prob = random.randint(0, 255)
            if prob < d.turn_away_prob:
                if d.turn_away_prob - prob < 0x40:
                    self._sim_append(f"{d.pronoun} turns away!", "#ff9f1c")
                else:
                    self._sim_append(f"{d.pronoun} says: On guard! Fool!", "#ff595e")
                return

        kw1 = normalize_u4_ascii(d.keyword1).decode("ascii").strip().lower()[:4]
        kw2 = normalize_u4_ascii(d.keyword2).decode("ascii").strip().lower()[:4]

        trigger_fired = False
        if kw1 and kw1 != "a" and clean.startswith(kw1):
            self._sim_append(d.response1 or "...", "#ffffff")
            trigger_fired = d.question_trigger == 5
        elif kw2 and kw2 != "a" and clean.startswith(kw2):
            self._sim_append(d.response2 or "...", "#ffffff")
            trigger_fired = d.question_trigger == 6
        elif clean.startswith("job"):
            self._sim_append(d.job or "...", "#ffffff")
            trigger_fired = d.question_trigger == 3
        elif clean.startswith("heal"):
            self._sim_append(d.health or "...", "#ffffff")
            trigger_fired = d.question_trigger == 4
        elif clean.startswith("look"):
            self._sim_append(f"You see {d.look}", "#ffffff")
        elif clean.startswith("name"):
            self._sim_append(f"{d.pronoun} says: I am {d.name}", "#5bc0eb")
        elif clean.startswith("give"):
            self._sim_append(f"{d.pronoun} says: I do not need thy gold. Keep it!", "#ffffff")
        elif clean.startswith("join"):
            self._sim_append(f"{d.pronoun} says: If {d.name} has the Companion role, I am honored to join thee!", "#8ac926")
        else:
            self._sim_append("That I cannot help thee with.", "#9fb3c8")

        if trigger_fired and d.question:
            self._sim_append(f"\n{d.question}\nYou say (Y/N):", "#ffd166")
            self._sim_waiting_yn = True
        else:
            self._sim_append("\nYour Interest:", "#9fb3c8")
