"""Fenêtre principale (MainWindow) et thème sombre d'Ultima IV Maker."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from ..binary_io import (
    read_con,
    read_dng,
    read_tlk,
    read_ult,
    read_world_map,
)
from ..models import (
    DialogueData,
    MapData,
    ScenarioMetadata,
    ScenarioProject,
    ShrineConfig,
)
from ..constants import VIRTUES
from ..sample_scenario import create_starter_scenario, ensure_starter_scenario
from ..tileset_renderer import TilesetCache
from ..yaml_io import load_project_yaml, save_project_yaml
from .dialogue_editor import DialogueEditorWidget
from .map_editor import MapEditorWidget
from .module_generator import ModuleGeneratorWidget
from .npc_editor import NPCEditorWidget
from .quest_editor import QuestEditorWidget

DARK_U4_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #111622;
    color: #E5E7EB;
    font-size: 13px;
}
QMenuBar {
    background-color: #0B0F17;
    color: #F3F4F6;
    border-bottom: 1px solid #2A3447;
}
QMenuBar::item:selected {
    background-color: #1E3A5F;
}
QMenu {
    background-color: #161D2C;
    color: #F3F4F6;
    border: 1px solid #334155;
}
QMenu::item:selected {
    background-color: #2563EB;
}
QToolBar {
    background-color: #161D2C;
    border-bottom: 1px solid #2A3447;
    spacing: 6px;
    padding: 4px;
}
QTabWidget::pane {
    border: 1px solid #2A3447;
    background-color: #111622;
}
QTabBar::tab {
    background-color: #1A2233;
    color: #9CA3AF;
    padding: 8px 14px;
    border: 1px solid #2A3447;
    border-bottom: none;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1E3A5F;
    color: #FBBF24;
    font-weight: bold;
    border-top: 2px solid #FBBF24;
}
QGroupBox {
    border: 1px solid #2D384D;
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #FCD34D;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QListWidget, QTableWidget {
    background-color: #0D121B;
    color: #F3F4F6;
    border: 1px solid #334155;
    border-radius: 3px;
    padding: 4px;
}
QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #1E40AF;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #1A2233;
    color: #E5E7EB;
    border: 1px solid #2D384D;
    padding: 4px;
    font-weight: bold;
}
QPushButton {
    background-color: #1F2937;
    color: #F3F4F6;
    border: 1px solid #374151;
    border-radius: 4px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #2D3A4F;
    border-color: #60A5FA;
}
QPushButton:checked {
    background-color: #1D4ED8;
    border-color: #93C5FD;
    color: #FFFFFF;
}
QStatusBar {
    background-color: #0B0F17;
    color: #CBD5E1;
    border-top: 1px solid #2A3447;
}
"""


def apply_dark_u4_theme(target: QApplication | QWidget) -> None:
    """Applique la charte graphique sombre inspirée d'Ultima IV."""
    target.setStyleSheet(DARK_U4_STYLESHEET)


class MainWindow(QMainWindow):
    """Fenêtre principale d'Ultima IV Maker réunissant les 5 ateliers de création."""

    def __init__(
        self,
        project: Optional[ScenarioProject] = None,
        project_dir: Optional[Path | str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.repo_root = Path(__file__).resolve().parents[2]
        self.project_dir: Optional[Path] = Path(project_dir) if project_dir is not None else None
        self._dirty = False

        if project is not None:
            self.project = project
        elif self.project_dir is not None and self.project_dir.exists():
            self.project = load_project_yaml(self.project_dir)
        else:
            starter_dir = self.repo_root / "scenarios" / "britannia_starter"
            ensure_starter_scenario(starter_dir)
            self.project = load_project_yaml(starter_dir)
            self.project_dir = starter_dir

        self.tileset = TilesetCache()
        if self.project.custom_shapes_ega:
            self._load_custom_shapes_bytes(self.project.custom_shapes_ega)

        self.setMinimumSize(1180, 760)
        apply_dark_u4_theme(self)

        self._build_central_tabs()
        self._build_menus_and_toolbar()
        self._build_status_bar()
        self._wire_signals()
        self._update_window_title()

    def _load_custom_shapes_bytes(self, raw: bytes) -> None:
        if len(raw) == 256 * 128:
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as tmp:
                ega_path = Path(tmp) / "shapes.ega"
                ega_path.write_bytes(raw)
                self.tileset.reload_from_shapes_ega(ega_path)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _build_central_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.map_editor = MapEditorWidget(self.project, self.tileset)
        self.npc_editor = NPCEditorWidget(self.project, self.tileset)
        self.dialogue_editor = DialogueEditorWidget(self.project)
        self.quest_editor = QuestEditorWidget(self.project)
        self.module_generator = ModuleGeneratorWidget(
            self.project,
            self.tileset,
            default_output_dir=self.repo_root / "build",
        )

        self.tabs.addTab(self.map_editor, "🗺 Cartes")
        self.tabs.addTab(self.npc_editor, "👥 PNJ & Boutiques")
        self.tabs.addTab(self.dialogue_editor, "💬 Dialogues (.TLK)")
        self.tabs.addTab(self.quest_editor, "📜 Quêtes & Indices")
        self.tabs.addTab(self.module_generator, "🚀 Module xU4")

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_menus_and_toolbar(self) -> None:
        menu_bar = self.menuBar()
        toolbar = QToolBar("Barre principale", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # ---- Menu Fichier ----
        m_file = menu_bar.addMenu("&Fichier")

        act_new = QAction("🆕 Nouveau scénario", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(lambda: self.new_scenario())
        m_file.addAction(act_new)
        toolbar.addAction(act_new)

        act_open = QAction("📂 Ouvrir YAML...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(lambda: self.open_project_dialog())
        m_file.addAction(act_open)
        toolbar.addAction(act_open)

        act_save = QAction("💾 Enregistrer YAML", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(lambda: self.save_project())
        m_file.addAction(act_save)
        toolbar.addAction(act_save)

        act_save_as = QAction("💾 Enregistrer sous...", self)
        act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(lambda: self.save_project_as())
        m_file.addAction(act_save_as)

        m_file.addSeparator()
        act_starter = QAction("🏰 Charger Britannia-Starter (exemple)", self)
        act_starter.triggered.connect(lambda: self.load_starter_scenario())
        m_file.addAction(act_starter)

        m_file.addSeparator()
        act_quit = QAction("Quitter", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        # ---- Menu Édition ----
        m_edit = menu_bar.addMenu("&Édition")
        toolbar.addSeparator()

        act_undo = QAction("↩ Annuler (Carte)", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self.map_editor.undo)
        m_edit.addAction(act_undo)
        toolbar.addAction(act_undo)

        act_redo = QAction("↪ Rétablir (Carte)", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self.map_editor.redo)
        m_edit.addAction(act_redo)
        toolbar.addAction(act_redo)

        # ---- Menu Importer Asset xU4 ----
        m_imp = menu_bar.addMenu("&Importer xU4")

        act_imp_world = QAction("🌍 Importer WORLD.MAP (256x256)...", self)
        act_imp_world.triggered.connect(self.import_world_map_dialog)
        m_imp.addAction(act_imp_world)

        act_imp_ult = QAction("🏘 Importer une ville (.ULT)...", self)
        act_imp_ult.triggered.connect(self.import_ult_dialog)
        m_imp.addAction(act_imp_ult)

        act_imp_tlk = QAction("💬 Importer des dialogues (.TLK)...", self)
        act_imp_tlk.triggered.connect(self.import_tlk_dialog)
        m_imp.addAction(act_imp_tlk)

        act_imp_dng = QAction("🗝 Importer un donjon (.DNG)...", self)
        act_imp_dng.triggered.connect(self.import_dng_dialog)
        m_imp.addAction(act_imp_dng)

        act_imp_con = QAction("⚔️ Importer une arène/sanctuaire (.CON)...", self)
        act_imp_con.triggered.connect(self.import_con_dialog)
        m_imp.addAction(act_imp_con)

        m_imp.addSeparator()
        act_imp_ega = QAction("🎨 Importer un tileset SHAPES.EGA...", self)
        act_imp_ega.triggered.connect(self.import_shapes_ega_dialog)
        m_imp.addAction(act_imp_ega)

        # ---- Menu Module xU4 ----
        m_mod = menu_bar.addMenu("&Module xU4")
        toolbar.addSeparator()

        act_validate = QAction("🔍 Vérifier scénario", self)
        act_validate.triggered.connect(self.validate_scenario)
        m_mod.addAction(act_validate)
        toolbar.addAction(act_validate)

        act_compile = QAction("🚀 Générer Module .mod", self)
        act_compile.setShortcut("F9")
        act_compile.triggered.connect(self.compile_scenario)
        m_mod.addAction(act_compile)
        toolbar.addAction(act_compile)

        # ---- Menu Aide ----
        m_help = menu_bar.addMenu("&Aide")

        act_docs = QAction("📖 Documentation des formats xU4", self)
        act_docs.triggered.connect(self.show_xu4_docs)
        m_help.addAction(act_docs)

        act_about = QAction("ℹ️ À propos d'Ultima IV Maker", self)
        act_about.triggered.connect(self.show_about)
        m_help.addAction(act_about)

    def _build_status_bar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.status_dir_label = QLabel("")
        sb.addPermanentWidget(self.status_dir_label)
        self._update_status_dir()

    def _wire_signals(self) -> None:
        self.map_editor.project_changed.connect(self._mark_dirty)
        self.npc_editor.project_changed.connect(self._mark_dirty)
        self.dialogue_editor.project_changed.connect(self._mark_dirty)
        self.quest_editor.project_changed.connect(self._mark_dirty)
        self.module_generator.project_changed.connect(self._on_meta_or_project_changed)

        self.npc_editor.open_dialogue_requested.connect(self._open_dialogue_tab)
        self.quest_editor.open_dialogue_requested.connect(self._open_dialogue_tab)
        self.map_editor.npc_place_requested.connect(self._on_npc_place_requested)

        self.module_generator.compile_succeeded.connect(
            lambda mod_path: self.statusBar().showMessage(f"Module xU4 généré : {mod_path}", 8000)
        )

    # ------------------------------------------------------------------
    # Gestion des signaux & synchronisation inter-onglets
    # ------------------------------------------------------------------
    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_window_title()

    def _on_meta_or_project_changed(self) -> None:
        self._mark_dirty()
        self._update_window_title()

    def _update_window_title(self) -> None:
        star = " *" if self._dirty else ""
        self.setWindowTitle(f"{self.project.metadata.title}{star} — Ultima IV Maker (Moteur xU4)")

    def _update_status_dir(self) -> None:
        loc = str(self.project_dir) if self.project_dir else "Projet non sauvegardé"
        self.status_dir_label.setText(f"Dossier YAML : {loc}")

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is not None and hasattr(widget, "refresh_from_project"):
            widget.refresh_from_project()

    def _open_dialogue_tab(self, bank_name: str, tlk_id: int) -> None:
        self.tabs.setCurrentWidget(self.dialogue_editor)
        self.dialogue_editor.refresh_from_project()
        self.dialogue_editor.select_dialogue(bank_name, tlk_id)
        self.statusBar().showMessage(f"Dialogue ouvert : {bank_name} #{tlk_id}", 5000)

    def _on_npc_place_requested(self, map_id: int, x: int, y: int) -> None:
        self.tabs.setCurrentWidget(self.npc_editor)
        self.npc_editor.refresh_from_project()
        idx = self.npc_editor.city_combo.findData(map_id)
        if idx >= 0:
            self.npc_editor.city_combo.setCurrentIndex(idx)
        # Sélectionner un PNJ déjà à ces coordonnées s'il existe
        cmap = self.project.get_map(map_id)
        if cmap:
            for row, npc in enumerate(cmap.npcs):
                if npc.x == x and npc.y == y:
                    self.npc_editor.npc_list.setCurrentRow(row)
                    break
        self.statusBar().showMessage(
            f"Coordonnées sélectionnées sur la carte #{map_id} : ({x}, {y}). "
            f"Ajoutez ou déplacez un PNJ ici.",
            6000,
        )

    def set_project(self, project: ScenarioProject, project_dir: Optional[Path | str] = None) -> None:
        self.project = project
        self.project_dir = Path(project_dir) if project_dir is not None else None
        self._dirty = False

        if self.project.custom_shapes_ega:
            self._load_custom_shapes_bytes(self.project.custom_shapes_ega)
        else:
            self.tileset = TilesetCache()
            self.map_editor.tileset = self.tileset
            self.npc_editor.tileset = self.tileset
            self.module_generator.tileset = self.tileset

        self.map_editor.set_project(self.project)
        self.npc_editor.set_project(self.project)
        self.dialogue_editor.set_project(self.project)
        self.quest_editor.set_project(self.project)
        self.module_generator.set_project(self.project)

        self._update_window_title()
        self._update_status_dir()

    # ------------------------------------------------------------------
    # Actions Fichier : Nouveau / Ouvrir / Sauvegarder
    # ------------------------------------------------------------------
    def new_scenario(self) -> None:
        """Crée un scénario minimal propre prêt à être personnalisé."""
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
        world.ensure_grids(fill_tile=4)  # herbe

        city = MapData(
            id=1,
            name="Citadel",
            fname="citadel.ult",
            map_type="city",
            width=32,
            height=32,
            border_behavior="exit",
            city_type="towne",
            tlk_fname="citadel.tlk",
        )
        city.ensure_grids(fill_tile=4)

        shrine_map = MapData(
            id=2,
            name="Shrine of Compassion",
            fname="shrine.con",
            map_type="shrine",
            width=11,
            height=11,
            border_behavior="fixed",
            shrine_virtue="Compassion",
            shrine_mantra="mu",
        )
        shrine_map.ensure_grids(fill_tile=22)

        proj = ScenarioProject(
            metadata=ScenarioMetadata(
                title="New Ultima IV Scenario",
                module_name="New-Module",
                author="Creator",
                version="1.0",
                about="An adventure created with Ultima IV Maker.",
            ),
            maps=[world, city, shrine_map],
            dialogues={
                "citadel.tlk": [
                    DialogueData(
                        id=1,
                        bank_name="citadel.tlk",
                        name="Guard",
                        pronoun="He",
                        look="a proud guard of the citadel.",
                        job="I watch over the towne gates.",
                        health="In fine fettle.",
                        keyword1="QUES",
                        response1="Speak with the sage in the tower to learn more.",
                    )
                ]
            },
            shrines=[
                ShrineConfig(virtue=en, mantra=mantra, map_id=shrine_map.id)
                for en, _fr, mantra, _r, _s in VIRTUES
            ],
        )
        self.set_project(proj, project_dir=None)
        self.statusBar().showMessage("Nouveau scénario créé.", 5000)

    def load_starter_scenario(self) -> None:
        starter_dir = self.repo_root / "scenarios" / "britannia_starter"
        if starter_dir.exists():
            proj = load_project_yaml(starter_dir)
        else:
            proj = create_starter_scenario()
            save_project_yaml(proj, starter_dir)
        self.set_project(proj, starter_dir)
        self.statusBar().showMessage("Scénario d'exemple Britannia-Starter rechargé.", 5000)

    def open_project_dialog(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Ouvrir un dossier de scénario YAML",
            str(self.project_dir or (self.repo_root / "scenarios")),
        )
        if not chosen:
            return
        try:
            proj = load_project_yaml(chosen)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de chargement YAML", f"Impossible d'ouvrir le scénario :\n{exc}")
            return
        self.set_project(proj, chosen)
        self.statusBar().showMessage(f"Scénario ouvert depuis {chosen}", 6000)

    def save_project(self) -> Optional[Path]:
        if self.project_dir is None:
            return self.save_project_as()
        out = save_project_yaml(self.project, self.project_dir)
        self._dirty = False
        self._update_window_title()
        self._update_status_dir()
        self.statusBar().showMessage(f"Scénario YAML enregistré dans {out}", 5000)
        return out

    def save_project_as(self) -> Optional[Path]:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de sauvegarde YAML",
            str(self.project_dir or (self.repo_root / "scenarios")),
        )
        if not chosen:
            return None
        self.project_dir = Path(chosen)
        return self.save_project()

    # ------------------------------------------------------------------
    # Importation de binaires Ultima IV existants
    # ------------------------------------------------------------------
    def _upsert_map(self, new_map: MapData) -> None:
        for idx, existing in enumerate(self.project.maps):
            if existing.id == new_map.id:
                self.project.maps[idx] = new_map
                break
        else:
            self.project.maps.append(new_map)
        self.map_editor.refresh_from_project()
        self.npc_editor.refresh_from_project()
        self.quest_editor.refresh_from_project()
        self._mark_dirty()

    def import_world_map_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer WORLD.MAP", str(self.repo_root), "Carte Monde (*.map *.MAP);;Tous (*)"
        )
        if not path:
            return
        m = read_world_map(path, map_id=0)
        self._upsert_map(m)
        self.statusBar().showMessage(f"WORLD.MAP importé depuis {path}", 5000)

    def import_ult_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une ville (.ULT)", str(self.repo_root), "Ville Ultima IV (*.ult *.ULT);;Tous (*)"
        )
        if not path:
            return
        p = Path(path)
        m = read_ult(p, map_id=self.project.next_map_id(), name=p.stem.capitalize())
        self._upsert_map(m)
        self.statusBar().showMessage(f"Ville importée : {m.name} ({len(m.npcs)} PNJ)", 5000)

    def import_tlk_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer des dialogues (.TLK)", str(self.repo_root), "Dialogues (.tlk .TLK);;Tous (*)"
        )
        if not path:
            return
        p = Path(path)
        bank_name = p.name.lower()
        dlgs = read_tlk(p, bank_name=bank_name)
        self.project.dialogues[bank_name] = dlgs
        self.dialogue_editor.refresh_from_project()
        self.npc_editor.refresh_from_project()
        self._mark_dirty()
        self.statusBar().showMessage(f"Banque {bank_name} importée ({len(dlgs)} dialogues)", 5000)

    def import_dng_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un donjon (.DNG)", str(self.repo_root), "Donjon (.dng .DNG);;Tous (*)"
        )
        if not path:
            return
        m = read_dng(path, map_id=self.project.next_map_id())
        self._upsert_map(m)
        self.statusBar().showMessage(f"Donjon importé : {m.name} ({m.levels} niveaux)", 5000)

    def import_con_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un fichier .CON", str(self.repo_root), "Combat/Sanctuaire (.con .CON);;Tous (*)"
        )
        if not path:
            return
        m = read_con(path, map_id=self.project.next_map_id(), map_type="combat")
        self._upsert_map(m)
        self.statusBar().showMessage(f"Carte .CON importée : {m.name}", 5000)

    def import_shapes_ega_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer SHAPES.EGA (tuiles 16x16)", str(self.repo_root), "Tileset EGA (*.ega *.EGA);;Tous (*)"
        )
        if not path:
            return
        self.tileset.reload_from_shapes_ega(path)
        self.project.custom_shapes_ega = Path(path).read_bytes()
        self.map_editor.refresh_from_project()
        self.npc_editor.refresh_from_project()
        self._mark_dirty()
        self.statusBar().showMessage(f"Tileset SHAPES.EGA chargé depuis {path}", 6000)

    # ------------------------------------------------------------------
    # Validation, Compilation & Aide
    # ------------------------------------------------------------------
    def validate_scenario(self) -> None:
        self.tabs.setCurrentWidget(self.module_generator)
        self.module_generator.run_validation()

    def compile_scenario(self) -> None:
        self.tabs.setCurrentWidget(self.module_generator)
        self.module_generator.run_compile()

    def show_xu4_docs(self) -> None:
        self.tabs.setCurrentWidget(self.module_generator)
        self.module_generator.preview_tabs.setCurrentWidget(self.module_generator.preview_docs)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "À propos d'Ultima IV Maker",
            "<h3>Ultima IV Maker (xU4 Scenario Studio)</h3>"
            "<p>Éditeur graphique tout-en-un pour créer des scénarios jouables "
            "compatibles avec le moteur C++ <b>xU4</b> sans écrire de code.</p>"
            "<ul>"
            "<li>Stockage lisible 100 % YAML</li>"
            "<li>Éditeur de cartes (.MAP / .ULT / .DNG / .CON) & tuiles SHAPES.EGA</li>"
            "<li>Éditeur de PNJ, boutiques & dialogues .TLK avec simulateur</li>"
            "<li>Éditeur de quêtes, sanctuaires & graphe d'indices</li>"
            "<li>Compilateur Boron + archive CDI (.mod)</li>"
            "</ul>",
        )
