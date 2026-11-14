# Ultima IV Maker (xU4 Scenario Studio)

**Ultima IV Maker** est un éditeur visuel complet écrit en Python (**PySide6** + **YAML**) conçu pour créer des scénarios et des campagnes complètes compatibles avec le moteur C++ open-source **[xU4](https://codeberg.org/xU4/xu4)** sans aucune compétence en programmation.

Il conserve l'esthétique EGA 16 couleurs (256 tuiles 16×16 `SHAPES.EGA`), les règles classiques des 8 Vertus, le système de dialogues par mots-clés (`.TLK`) et compile automatiquement vos projets YAML en scripts **Boron** (`config.b`, `maps.b`, `vendors.b`), en fichiers binaires Ultima IV (`.MAP`, `.ULT`, `.TLK`, `.DNG`, `.CON`, `shapes.ega`) et en archive **CDI `.mod`** directement jouable par `xu4`.

---

## Prérequis & Installation

Python 3.10+ est requis.

```bash
pip install -r requirements.txt
```

Dépendances principales :
- `PySide6>=6.6.0` (interface graphique Qt)
- `PyYAML>=6.0` (sauvegarde/chargement lisible des scénarios)
- `Pillow>=10.0.0` (génération et lecture des tuiles EGA 16×16)
- `pytest>=8.0.0` (tests automatisés)

---

## Lancement rapide

### Ouvrir l'éditeur graphique (charge par défaut `scenarios/britannia_starter`)
```bash
python3 main.py
```

### Ouvrir un scénario YAML spécifique
```bash
python3 main.py chemin/vers/mon_scenario
```

### Valider ou compiler sans interface graphique (CLI)
```bash
# Vérifier la cohérence du scénario
python3 main.py --validate-only scenarios/britannia_starter

# Compiler directement en dossier Boron + binaires + archive .mod
python3 main.py --compile-only --output-dir build scenarios/britannia_starter
```

---

## Les 5 Ateliers de l'Éditeur

1. **🗺 Éditeur de Cartes (`u4maker/gui/map_editor.py`)**
   - Édition de la carte du monde `WORLD.MAP` (256×256 découpée en chunks 32×32), des villes `.ULT` (32×32), des donjons multi-niveaux `.DNG` (8 niveaux × 8×8 + salles de combat 11×11), et des arènes/sanctuaires `.CON` (11×11).
   - Palette des 256 tuiles EGA regroupées par thème, pinceau, pot de remplissage (*flood fill*), pipette, gomme, Annuler/Rétablir (Undo/Redo), zoom, grilles et superposition visuelle des PNJ, portails, moongates et labels d'objets.

2. **👥 Éditeur de PNJ & Boutiques (`u4maker/gui/npc_editor.py`)**
   - Gestion des 32 emplacements PNJ d'un `.ULT`, sprites animés, comportements de déplacement (`fixed`, `wander`, `follow`, `attack`), liaison à un dialogue `.TLK`, et configuration complète des boutiques/rôles spéciaux (`lordbritish`, `hawkwind`, marchands d'armes, armuriers, taverniers, guérisseurs, écuries…).

3. **💬 Éditeur de Dialogues `.TLK` & Simulateur (`u4maker/gui/dialogue_editor.py`)**
   - Rédaction des dialogues classiques Ultima IV (`LOOK`, `JOB`, `HEALTH`, 2 mots-clés `.TLK` + question Oui/Non) avec **jauge mémoire stricte de 288 octets** en temps réel (normalisation ASCII automatique à la compilation) et **simulateur interactif intégré** pour tester la conversation comme dans le jeu (`NAME`, `JOB`, `HEAL`, `YES`/`NO`, `BYE`).

4. **📜 Éditeur de Quêtes, Sanctuaires & Graphe d'Indices (`u4maker/gui/quest_editor.py`)**
   - Création des quêtes et étapes avec sélecteurs liés aux PNJ, banques `.TLK`, mots-clés, labels d'objets xU4 (`honestyrune`, `bell`, `book`, `candle`, etc.) et cartes cibles.
   - Configuration des 8 Sanctuaires & Mantras et des rumeurs de taverne.
   - **Graphe d'Indices visuel (`QGraphicsScene`)** et analyseur de dépendances détectant les PNJ introuvables, mots-clés absents ou objets non placés.

5. **🚀 Générateur de Module Jouable xU4 (`u4maker/gui/module_generator.py`)**
   - Édition des métadonnées (`MODI`), bouton **« Vérifier la cohérence du scénario »**, aperçu temps réel des scripts Boron (`config.b`, `maps.b`, `vendors.b`), documentation intégrée et bouton **« Générer le Module Jouable xU4 »**.

---

## Structure YAML d'un Scénario

Chaque scénario est stocké dans un dossier versionnable et lisible à la main :

```text
mon_scenario/
├── project.yaml           # Métadonnées, liste des cartes, sanctuaires, rumeurs
├── maps/
│   ├── 00_monde.yaml      # Grille world 256x256, portails, moongates, labels
│   └── 01_britain.yaml    # Grille ville 32x32, portails, labels
├── npcs/
│   └── 01_britain.yaml    # 32 slots PNJ max, rôles & boutiques Boron
├── dialogues/
│   └── britain.tlk.yaml   # Banques de dialogues (blocs 288 octets + notes)
└── quests/
    └── quests.yaml        # Quêtes, étapes, mots-clés et indices liés
```

---

## Jouer le module généré dans xU4

Après compilation dans `build/` :
1. Copiez `build/<Nom-Du-Module>.mod` dans votre répertoire de modules **xU4** puis lancez :
   ```bash
   xu4 -m <Nom-Du-Module>.mod
   ```
2. Vous pouvez également inspecter le dossier `build/<Nom-Du-Module>/` qui contient tous les scripts Boron (`config.b`, `maps.b`, `vendors.b`) et les binaires bruts compatibles Ultima IV / `pack-xu4.b`.

---

## Architecture du Projet

- `u4maker/constants.py` — Catalogue des 256 tuiles (`u4-save-ids`), palette EGA 16 couleurs, rôles PNJ, Vertus et labels xU4.
- `u4maker/models.py` — Modèles de données (`ScenarioProject`, `MapData`, `NPCData`, `DialogueData`, `QuestData`, etc.).
- `u4maker/yaml_io.py` — Sérialisation / désérialisation YAML des projets.
- `u4maker/binary_io.py` — Lecture et écriture binaire exacte `.ULT`, `.TLK`, `WORLD.MAP`, `.DNG`, `.CON`.
- `u4maker/tileset_renderer.py` — Rendu pixel-art intégré + lecture/écriture 4-bit `SHAPES.EGA`.
- `u4maker/compiler.py` — Validation de cohérence, génération Boron et empaquetage `.mod` (format CDI `xu4^2`).
- `u4maker/sample_scenario.py` — Générateur du scénario de démonstration *La Quête du Calice d'Avatar* (`scenarios/britannia_starter`).
- `docs/XU4_DATA_FORMATS.md` — Étude technique détaillée des formats binaires et Boron de `xU4`.

---

## Tests automatisés

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -v
```
