"""Générateur de module jouable xU4, vérificateur de cohérence et aperçu Boron (.b)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..compiler import (
    BuildResult,
    ValidationIssue,
    compile_module,
    generate_config_b,
    generate_maps_b,
    generate_vendors_b,
    validate_project,
)
from ..models import ScenarioProject
from ..tileset_renderer import TilesetCache


class ModuleGeneratorWidget(QWidget):
    """Onglet Métadonnées, Vérification & Compilation en module xU4 (.mod + Boron + binaires)."""

    project_changed = Signal()
    compile_succeeded = Signal(str)

    def __init__(
        self,
        project: ScenarioProject,
        tileset: Optional[TilesetCache] = None,
        default_output_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.tileset = tileset or TilesetCache()
        self._loading = False
        self._last_build: Optional[BuildResult] = None

        if default_output_dir is None:
            default_output_dir = Path(__file__).resolve().parents[2] / "build"
        self.default_output_dir = Path(default_output_dir)

        self._build_ui()
        self.refresh_from_project()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        main_split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(main_split)

        # ---- Panneau gauche : Métadonnées + Actions + Rapport validation ----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        meta_box = QGroupBox("Métadonnées du Scénario (Archive CDI xU4)")
        meta_form = QFormLayout(meta_box)

        self.title_edit = QLineEdit()
        self.title_edit.textChanged.connect(self._on_meta_edited)
        meta_form.addRow("Titre de l'aventure :", self.title_edit)

        self.module_name_edit = QLineEdit()
        self.module_name_edit.setPlaceholderText("ex: Britannia-Starter (max 35 car.)")
        self.module_name_edit.textChanged.connect(self._on_meta_edited)
        meta_form.addRow("Nom du module (.mod) :", self.module_name_edit)

        self.author_edit = QLineEdit()
        self.author_edit.textChanged.connect(self._on_meta_edited)
        meta_form.addRow("Auteur :", self.author_edit)

        self.version_edit = QLineEdit()
        self.version_edit.textChanged.connect(self._on_meta_edited)
        meta_form.addRow("Version :", self.version_edit)

        self.rules_combo = QComboBox()
        self.rules_combo.setEditable(True)
        self.rules_combo.addItems(["Ultima-IV", "Custom"])
        self.rules_combo.currentTextChanged.connect(self._on_meta_edited)
        meta_form.addRow("Moteur / Règles :", self.rules_combo)

        self.about_edit = QPlainTextEdit()
        self.about_edit.setMaximumHeight(70)
        self.about_edit.textChanged.connect(self._on_meta_edited)
        meta_form.addRow("Description :", self.about_edit)

        left_layout.addWidget(meta_box)

        # ---- Compilation / Destination ----
        build_box = QGroupBox("Génération du Module Jouable")
        build_layout = QVBoxLayout(build_box)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Dossier cible :"))
        self.output_dir_edit = QLineEdit(str(self.default_output_dir))
        out_row.addWidget(self.output_dir_edit, stretch=1)
        btn_browse = QPushButton("📂 Parcourir...")
        btn_browse.clicked.connect(self._browse_output_dir)
        out_row.addWidget(btn_browse)
        build_layout.addLayout(out_row)

        btn_row = QHBoxLayout()
        self.btn_validate = QPushButton("🔍 Vérifier la cohérence du scénario")
        self.btn_validate.clicked.connect(lambda: self.run_validation())
        btn_row.addWidget(self.btn_validate)

        self.btn_compile = QPushButton("🚀 Générer le Module Jouable xU4")
        self.btn_compile.setStyleSheet(
            "QPushButton { background-color: #1D4ED8; color: white; font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #2563EB; }"
        )
        self.btn_compile.clicked.connect(lambda: self.run_compile())
        btn_row.addWidget(self.btn_compile)

        self.btn_launch_xu4 = QPushButton("🎮 Tester dans xU4")
        self.btn_launch_xu4.setStyleSheet(
            "QPushButton { background-color: #15803D; color: white; font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #16A34A; }"
        )
        self.btn_launch_xu4.clicked.connect(lambda: self.run_and_launch_xu4())
        btn_row.addWidget(self.btn_launch_xu4)
        build_layout.addLayout(btn_row)

        self.status_label = QLabel("Prêt pour la vérification et la compilation.")
        self.status_label.setWordWrap(True)
        build_layout.addWidget(self.status_label)

        left_layout.addWidget(build_box)

        # ---- Table de résultats de validation ----
        val_box = QGroupBox("Rapport de cohérence")
        val_layout = QVBoxLayout(val_box)
        self.validation_table = QTableWidget(0, 3)
        self.validation_table.setHorizontalHeaderLabels(["Sévérité", "Catégorie", "Message"])
        self.validation_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.validation_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.validation_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        val_layout.addWidget(self.validation_table)
        left_layout.addWidget(val_box, stretch=1)

        main_split.addWidget(left_panel)

        # ---- Panneau droit : Aperçus Boron (.b), fichiers générés et Documentation ----
        right_panel = QGroupBox("Aperçu des scripts Boron générés & Documentation xU4")
        right_layout = QVBoxLayout(right_panel)

        self.preview_tabs = QTabWidget()
        mono = QFont("Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.TypeWriter)

        self.preview_config = QPlainTextEdit()
        self.preview_config.setReadOnly(True)
        self.preview_config.setFont(mono)
        self.preview_tabs.addTab(self.preview_config, "config.b")

        self.preview_maps = QPlainTextEdit()
        self.preview_maps.setReadOnly(True)
        self.preview_maps.setFont(mono)
        self.preview_tabs.addTab(self.preview_maps, "maps.b")

        self.preview_vendors = QPlainTextEdit()
        self.preview_vendors.setReadOnly(True)
        self.preview_vendors.setFont(mono)
        self.preview_tabs.addTab(self.preview_vendors, "vendors.b")

        self.preview_build_log = QPlainTextEdit()
        self.preview_build_log.setReadOnly(True)
        self.preview_build_log.setFont(mono)
        self.preview_build_log.setPlainText(
            "Cliquez sur « 🚀 Générer le Module Jouable xU4 » pour exporter les binaires "
            "(.MAP, .ULT, .TLK, .DNG, .CON, SHAPES.EGA), les scripts Boron et l'archive .mod."
        )
        self.preview_tabs.addTab(self.preview_build_log, "📦 Journal d'export")

        self.preview_docs = QPlainTextEdit()
        self.preview_docs.setReadOnly(True)
        self.preview_docs.setPlainText(self._load_xu4_docs())
        self.preview_tabs.addTab(self.preview_docs, "📖 Formats xU4")

        right_layout.addWidget(self.preview_tabs)
        main_split.addWidget(right_panel)

        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 1)

    def _load_xu4_docs(self) -> str:
        doc_path = Path(__file__).resolve().parents[2] / "docs" / "XU4_DATA_FORMATS.md"
        if doc_path.exists():
            try:
                return doc_path.read_text(encoding="utf-8")
            except OSError:
                pass
        return "Documentation docs/XU4_DATA_FORMATS.md introuvable."

    # ------------------------------------------------------------------
    # Synchronisation & API publique
    # ------------------------------------------------------------------
    def set_project(self, project: ScenarioProject) -> None:
        self.project = project
        self.refresh_from_project()

    def set_output_dir(self, path: Path | str) -> None:
        self.output_dir_edit.setText(str(path))

    def refresh_from_project(self) -> None:
        self._loading = True
        try:
            meta = self.project.metadata
            self.title_edit.setText(meta.title)
            self.module_name_edit.setText(meta.module_name)
            self.author_edit.setText(meta.author)
            self.version_edit.setText(meta.version)
            self.rules_combo.setCurrentText(meta.rules or "Ultima-IV")
            self.about_edit.setPlainText(meta.about)
        finally:
            self._loading = False

        self._refresh_boron_previews()
        self.run_validation()

    def _refresh_boron_previews(self) -> None:
        try:
            self.preview_config.setPlainText(generate_config_b(self.project))
            self.preview_maps.setPlainText(generate_maps_b(self.project))
            self.preview_vendors.setPlainText(generate_vendors_b(self.project))
        except Exception as exc:
            self.status_label.setText(f"⚠️ Erreur lors de la génération d'aperçu Boron : {exc}")

    def _on_meta_edited(self) -> None:
        if self._loading:
            return
        meta = self.project.metadata
        meta.title = self.title_edit.text()
        meta.module_name = self.module_name_edit.text().strip()
        meta.author = self.author_edit.text()
        meta.version = self.version_edit.text().strip() or "1.0"
        meta.rules = self.rules_combo.currentText().strip() or "Ultima-IV"
        meta.about = self.about_edit.toPlainText()

        self._refresh_boron_previews()
        self.project_changed.emit()

    def _browse_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de sortie du module xU4",
            self.output_dir_edit.text() or str(self.default_output_dir),
        )
        if chosen:
            self.output_dir_edit.setText(chosen)

    def _populate_validation_table(self, issues: List[ValidationIssue]) -> None:
        self.validation_table.setRowCount(len(issues))
        errors = 0
        warnings = 0
        for row, iss in enumerate(issues):
            if iss.severity == "error":
                errors += 1
                sev_lbl = "❌ Erreur"
                color = QColor("#FCA5A5")
            elif iss.severity == "warning":
                warnings += 1
                sev_lbl = "⚠️ Avertissement"
                color = QColor("#FCD34D")
            else:
                sev_lbl = "✅ Valide"
                color = QColor("#86EFAC")

            c0 = QTableWidgetItem(sev_lbl)
            c0.setForeground(QBrush(color))
            c1 = QTableWidgetItem(iss.category)
            c2 = QTableWidgetItem(iss.message)
            self.validation_table.setItem(row, 0, c0)
            self.validation_table.setItem(row, 1, c1)
            self.validation_table.setItem(row, 2, c2)

        if errors > 0:
            self.status_label.setText(
                f"❌ {errors} erreur(s) et {warnings} avertissement(s) détecté(s). Corrigez les erreurs avant diffusion."
            )
        elif warnings > 0:
            self.status_label.setText(
                f"⚠️ Aucune erreur bloquante, {warnings} avertissement(s). Compilation possible."
            )
        else:
            self.status_label.setText("✅ Scénario parfaitement cohérent et prêt à être compilé !")

    def run_validation(self) -> List[ValidationIssue]:
        """Valide le scénario complet via compiler.validate_project et affiche les résultats."""
        issues = validate_project(self.project)
        self._populate_validation_table(issues)
        self._refresh_boron_previews()
        return issues

    def run_compile(self, output_dir: Optional[Path | str] = None) -> Optional[BuildResult]:
        """Compile le scénario en dossier module Boron+binaires et en archive CDI .mod."""
        target_root = Path(output_dir) if output_dir is not None else Path(
            self.output_dir_edit.text().strip() or str(self.default_output_dir)
        )
        issues = validate_project(self.project)
        self._populate_validation_table(issues)
        try:
            result = compile_module(self.project, target_root, tileset=self.tileset)
        except ValueError as exc:
            self.preview_build_log.setPlainText(f"❌ Échec de compilation :\n\n{exc}")
            self.preview_tabs.setCurrentWidget(self.preview_build_log)
            self.status_label.setText("❌ Compilation bloquée : corrigez les erreurs signalées.")
            return None

        self._last_build = result
        self._populate_validation_table(result.issues)
        self._refresh_boron_previews()

        lines = [
            f"=== Compilation terminée ===",
            f"Archive .mod CDI : {result.mod_path} ({result.mod_path.stat().st_size if result.mod_path.exists() else 0} octets)",
            f"Dossier module   : {result.build_dir}",
            "",
            f"Fichiers générés ({len(result.files_written)}) :",
        ]
        for fpath in result.files_written:
            size = fpath.stat().st_size if fpath.exists() else 0
            lines.append(f"  - {fpath.name:<24} ({size} octets)")

        lines.extend(
            [
                "",
                "Pour jouer avec le moteur C++ xU4 :",
                f"  ./xu4-1.4.3/xu4 -m \"{result.mod_path.stem}\"",
            ]
        )
        self.preview_build_log.setPlainText("\n".join(lines))
        self.preview_tabs.setCurrentWidget(self.preview_build_log)
        self.status_label.setText(f"🚀 Module généré avec succès : {result.mod_path.name}")
        self.compile_succeeded.emit(str(result.mod_path))
        return result

    def find_xu4_executable(self) -> Optional[Path]:
        """Recherche le binaire xU4 compilé localement ou sur le système."""
        project_root = Path(__file__).resolve().parents[2]
        candidates = [
            project_root / "xu4-1.4.3" / "xu4",
            Path("/usr/local/bin/xu4"),
        ]
        which_xu4 = shutil.which("xu4")
        if which_xu4:
            candidates.append(Path(which_xu4))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def run_and_launch_xu4(self) -> None:
        """Compile le scénario, copie les assets dans xU4 et lance le moteur."""
        result = self.run_compile()
        if result is None:
            return

        xu4_bin = self.find_xu4_executable()
        if xu4_bin is None:
            self.status_label.setText(
                "❌ Binaire xU4 introuvable. Compilez d'abord xu4 dans ./xu4-1.4.3/xu4."
            )
            return

        app_support = Path.home() / "Library" / "Application Support" / "xu4"
        override_dir = app_support / "u4"
        app_support.mkdir(parents=True, exist_ok=True)
        override_dir.mkdir(parents=True, exist_ok=True)

        # Synchroniser le module .mod dans Application Support et le dossier xu4
        shutil.copy2(result.mod_path, app_support / result.mod_path.name)
        if xu4_bin.parent != app_support:
            shutil.copy2(result.mod_path, xu4_bin.parent / result.mod_path.name)

        # Copier les binaires de scénario en majuscules dans ~/Library/Application Support/xu4/u4
        for existing in override_dir.iterdir():
            if existing.is_file() and existing.suffix.lower() in {".map", ".ult", ".tlk", ".dng", ".con"}:
                existing.unlink()
        for src_file in result.build_dir.iterdir():
            if src_file.is_file() and src_file.suffix.lower() in {".map", ".ult", ".tlk", ".dng", ".con"}:
                shutil.copy2(src_file, override_dir / src_file.name.upper())

        subprocess.Popen(
            [str(xu4_bin), "-m", result.mod_path.stem],
            cwd=str(xu4_bin.parent),
        )
        self.status_label.setText(f"🎮 xU4 lancé avec le module : {result.mod_path.stem}")
