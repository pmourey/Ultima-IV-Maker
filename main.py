#!/usr/bin/env python3
"""Point d'entrée d'Ultima IV Maker (interface graphique PySide6 et compilateur CLI xU4)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from u4maker.compiler import compile_module, validate_project
from u4maker.sample_scenario import ensure_starter_scenario
from u4maker.yaml_io import load_project_yaml


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ultima IV Maker — Éditeur visuel YAML & Générateur de modules xU4."
    )
    parser.add_argument(
        "scenario_dir",
        nargs="?",
        default=None,
        help="Dossier du scénario YAML à ouvrir (par défaut : scenarios/britannia_starter).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Vérifie la cohérence du scénario en ligne de commande sans ouvrir la fenêtre.",
    )
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Compile le scénario en module xU4 (.mod + Boron + binaires) sans ouvrir la fenêtre.",
    )
    parser.add_argument(
        "--output-dir",
        default="build",
        help="Dossier de sortie pour --compile-only (par défaut : ./build).",
    )
    return parser.parse_args(argv)


def _resolve_scenario_dir(raw_dir: str | None) -> Path:
    repo_root = Path(__file__).resolve().parent
    if raw_dir:
        return Path(raw_dir).resolve()
    starter_dir = repo_root / "scenarios" / "britannia_starter"
    ensure_starter_scenario(starter_dir)
    return starter_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scenario_dir = _resolve_scenario_dir(args.scenario_dir)

    if args.validate_only or args.compile_only:
        project = load_project_yaml(scenario_dir)
        issues = validate_project(project)
        for iss in issues:
            print(f"[{iss.severity.upper()}] {iss.category}: {iss.message}")
        has_errors = any(i.severity == "error" for i in issues)

        if args.compile_only:
            if has_errors:
                print("\nCompilation annulée en raison des erreurs ci-dessus.")
                return 1
            out_dir = Path(args.output_dir).resolve()
            result = compile_module(project, out_dir)
            print(f"\nArchive .mod générée : {result.mod_path}")
            print(f"Dossier Boron/binaires : {result.build_dir} ({len(result.files_written)} fichiers)")
        return 1 if has_errors else 0

    from PySide6.QtWidgets import QApplication
    from u4maker.gui.main_window import MainWindow, apply_dark_u4_theme

    app = QApplication(sys.argv)
    app.setApplicationName("Ultima IV Maker")
    app.setOrganizationName("xU4 Scenario Studio")
    apply_dark_u4_theme(app)

    window = MainWindow(project_dir=scenario_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
