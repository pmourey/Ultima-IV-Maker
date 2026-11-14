"""Tests smoke PySide6 en mode headless (QT_QPA_PLATFORM=offscreen) pour Ultima IV Maker."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from u4maker.gui.main_window import MainWindow
from u4maker.sample_scenario import create_starter_scenario


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_mainwindow_all_tabs_workflow(qapp: QApplication, tmp_path: Path) -> None:
    proj = create_starter_scenario()
    win = MainWindow(project=proj)

    assert win.tabs.count() == 5

    # Parcourir tous les onglets
    for idx in range(5):
        win.tabs.setCurrentIndex(idx)
        qapp.processEvents()
        assert win.tabs.currentIndex() == idx

    # ---- 1. Éditeur de cartes : peindre + Undo / Redo ----
    win.tabs.setCurrentWidget(win.map_editor)
    cur_map = win.map_editor.current_map
    assert cur_map is not None
    orig_tile = cur_map.get_tile(2, 2, win.map_editor.current_level)
    new_tile = 14 if orig_tile != 14 else 4
    win.map_editor.selected_tile_id = new_tile
    win.map_editor.current_tool = "brush"

    win.map_editor._on_cell_pressed(2, 2, Qt.MouseButton.LeftButton)
    win.map_editor._on_cell_released(2, 2)
    assert cur_map.get_tile(2, 2, win.map_editor.current_level) == new_tile

    win.map_editor.undo()
    assert cur_map.get_tile(2, 2, win.map_editor.current_level) == orig_tile
    win.map_editor.redo()
    assert cur_map.get_tile(2, 2, win.map_editor.current_level) == new_tile

    # ---- 2. Éditeur PNJ + saut vers Dialogue ----
    win.tabs.setCurrentWidget(win.npc_editor)
    assert win.npc_editor.npc_list.count() > 0
    win.npc_editor.npc_list.setCurrentRow(0)
    assert win.npc_editor.current_npc is not None
    win.npc_editor.name_edit.setText("Iolo le Barde")
    win.npc_editor._apply_changes()
    assert win.npc_editor.current_npc.name == "Iolo le Barde"

    # Ouvrir dialogue depuis le signal open_dialogue_requested
    win.npc_editor.open_dialogue_requested.emit("britain.tlk", 1)
    qapp.processEvents()
    assert win.tabs.currentWidget() is win.dialogue_editor

    # ---- 3. Simulateur .TLK ----
    assert win.dialogue_editor.current_dlg is not None
    win.dialogue_editor._process_sim_input("NAME")
    win.dialogue_editor._process_sim_input("JOB")
    win.dialogue_editor._process_sim_input("BYE")
    transcript = win.dialogue_editor.sim_screen.toPlainText()
    assert "says: I am" in transcript
    assert "Bye." in transcript

    # ---- 4. Éditeur de Quêtes, Sanctuaires & Graphe d'Indices ----
    win.tabs.setCurrentWidget(win.quest_editor)
    findings = win.quest_editor.rebuild_clue_graph()
    assert len(findings) >= 1
    assert len(win.quest_editor.clue_scene.items()) > 0
    assert win.quest_editor.shrines_table.rowCount() == 8

    # ---- 5. Générateur de Module xU4 ----
    win.tabs.setCurrentWidget(win.module_generator)
    issues = win.module_generator.run_validation()
    assert not any(i.severity == "error" for i in issues)

    build_res = win.module_generator.run_compile(tmp_path / "gui_build")
    assert build_res is not None
    assert build_res.mod_path.exists()
    assert "u4-save-ids" in win.module_generator.preview_config.toPlainText()
    assert "city " in win.module_generator.preview_maps.toPlainText()

    # Nouveau scénario propre
    win.new_scenario()
    assert len(win.project.maps) >= 3
    win.close()
