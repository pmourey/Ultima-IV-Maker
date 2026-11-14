# Étude des structures de données du moteur xU4 (Ultima IV Recreated)

Ce document synthétise la structure exacte des données utilisées par le moteur C++ **xU4** (`https://codeberg.org/xU4/xu4`), basée sur `doc/FileFormats.md`, `doc/modules.md`, `tools/pack-xu4.b`, `module/Ultima-IV/*.b`, `src/maploader.cpp`, `src/discourse_tlk.cpp` et `src/item.cpp`.

---

## 1. Architecture à deux couches de xU4

xU4 combine deux couches de données :

1. **Les fichiers binaires historiques d'Ultima IV (DOS)** :
   - `SHAPES.EGA` : graphismes des 256 tuiles ($16 \times 16$, 4 bits par pixel).
   - `WORLD.MAP` : carte du monde $256 \times 256$ découpée en 64 blocs (*chunks*) de $32 \times 32$.
   - `*.ULT` : cartes de villes, châteaux et villages ($32 \times 32$ tuiles + table de 32 PNJ).
   - `*.TLK` : banques de dialogues des PNJ (jusqu'à 16 PNJ par fichier, blocs fixes de 288 octets).
   - `*.DNG` : donjons en 3D (8 niveaux $8 \times 8$ + salles tactiques $11 \times 11$ de 256 octets).
   - `*.CON` : arènes de combat et sanctuaires ($11 \times 11$ tuiles + positions de départ).

2. **Le système modulaire Boron de xU4 (`.b` et archive `.mod` CDI)** :
   - `config.b` : métadonnées du module (`author`, `about`, `version`, `rules: 'Ultima-IV`), tables des armures, armes, créatures, règles de tuiles (`tile-rules`), `tileset`, correspondance `u4-save-ids`, palette EGA (`ega-palette`), sons/musiques, et inclusions (`maps.b`, `graphics.b`, `vendors.b`).
   - `maps.b` : registre de toutes les cartes (`id`, `type`, `fname`, dimensions), des **portails** (`portals`), des **portes lunaires** (`moongates`), des **marqueurs d'objets** (`labels`), des **rôles PNJ spéciaux** (`roles`), et des **sanctuaires** (`shrine` avec vertu et mantra).
   - `vendors.b` : configuration complète des boutiques (armes, armures, nourriture, tavernes + rumeurs, réactifs, guérisseurs, auberges, guilde, écuries).
   - **Paquet `.mod` (CDI Package `xu4^2`)** : conteneur binaire regroupant la configuration compilée, les cartes, les dialogues, les images et l'audio en un seul fichier distribuable.

---

## 2. Formats binaires détaillés

### 2.1 `SHAPES.EGA` — Tuiles graphiques (32 768 octets)
- Contient exactement **256 tuiles** (`id` `0` à `255`).
- Chaque tuile mesure **$16 \times 16$ pixels** en **EGA 16 couleurs** (4 bits par pixel, soit 2 pixels par octet : octet = `(pixel_gauche << 4) | pixel_droite`).
- Taille d'une tuile : $16 \times 8 = 128$ octets (`0x80`). Total : $256 \times 128 = 32\,768$ octets.
- Palette EGA standard (16 entrées RGB) déclarée dans `config.b` :
  - `0`: Noir `(0,0,0)`, `1`: Bleu `(0,0,170)`, `2`: Vert `(0,170,0)`, `3`: Cyan `(0,170,170)`,
  - `4`: Rouge `(170,0,0)`, `5`: Magenta `(170,0,170)`, `6`: Marron `(170,85,0)`, `7`: Gris clair `(170,170,170)`,
  - `8`: Gris foncé `(85,85,85)`, `9`: Bleu vif `(85,85,255)`, `10`: Vert vif `(85,255,80)`, `11`: Cyan vif `(85,255,255)`,
  - `12`: Rouge vif `(255,85,85)`, `13`: Magenta vif `(255,85,255)`, `14`: Jaune `(255,255,85)`, `15`: Blanc `(255,255,255)`.

### 2.2 `WORLD.MAP` — Carte du monde $256 \times 256$ (65 536 octets)
- Grille globale de **$256 \times 256$ tuiles** (1 octet par tuile = index `0..255` dans `u4-save-ids` / `SHAPES.EGA`).
- Organisée en **64 chunks** de **$32 \times 32$** (soit une grille de $8 \times 8$ chunks de 1 024 octets).
- Ordre de stockage vérifié dans `src/maploader.cpp` :
  - Boucle externe sur les lignes de chunks `ych` de `0` à `7`,
  - Boucle interne sur les colonnes de chunks `xch` de `0` à `7`,
  - Dans chaque chunk : `y` de `0` à `31`, puis `x` de `0` à `31`.

### 2.3 `.ULT` — Villes, châteaux et villages (1 280 octets = `0x500`)
| Offset | Taille | Description |
|---|---|---|
| `0x0000` | 1 024 | Matrice $32 \times 32$ de tuiles (ligne par ligne, `y * 32 + x`) |
| `0x0400` | 32 | `tile` : tuile des PNJ 0 à 31 (`0` = emplacement vide) |
| `0x0420` | 32 | `start_x` : coordonnée X initiale des PNJ 0 à 31 (`0..31`) |
| `0x0440` | 32 | `start_y` : coordonnée Y initiale des PNJ 0 à 31 (`0..31`) |
| `0x0460` | 32 | `prev_tile` : répétition de `0x0400..0x041F` |
| `0x0480` | 32 | Répétition de `0x0420..0x043F` |
| `0x04A0` | 32 | Répétition de `0x0440..0x045F` |
| `0x04C0` | 32 | Comportement : `0x00` = Fixe, `0x01` = Errant (*Wander*), `0x80` = Suit (*Follow*), `0xFF` = Hostile (*Attack*) |
| `0x04E0` | 32 | Index de dialogue dans `.TLK` (`1..16`, ou `0` si aucun / rôle boutique) |

*Note importante (`src/maploader.cpp`)* : dans `maps.b`, les rôles spéciaux (`roles [healer 29 hawkwind 30]`) utilisent une indexation **1-based** (`1..32`), qui correspond au slot `index - 1` (`0..31`) dans le fichier `.ULT`.

### 2.4 `.TLK` — Dialogues des PNJ (blocs de 288 octets = `0x120`)
Un fichier `.TLK` contient jusqu'à **16 blocs** consécutifs de **288 octets** chacun :
- `0x00` (1 octet) : `question_trigger` (`0` = Aucune, `3` = après `JOB`, `4` = après `HEAL`, `5` = après Mot-clé 1, `6` = après Mot-clé 2).
- `0x01` (1 octet) : `question_humility` (`0` = Non, `1` = Oui — `Y` retire de l'humilité, `N` en donne).
- `0x02` (1 octet) : `turn_away_prob` (`0..255` : probabilité par tour de dialogue que le PNJ se détourne ou attaque si `turn_away_prob - rand >= 0x40`).
- `0x03..0x11F` : **12 chaînes ASCII** terminées par `\0`, suivies de zéros de bourrage jusqu'à `288` octets :
  1. `name` (Nom)
  2. `pronoun` (`He`, `She`, `It`)
  3. `look` (Description vue au `LOOK`)
  4. `job` (Réponse à `JOB`)
  5. `health` (Réponse à `HEAL`)
  6. `response1` (Réponse au mot-clé 1)
  7. `response2` (Réponse au mot-clé 2)
  8. `question` (Texte de la question Oui/Non)
  9. `yes_response` (Réponse si Oui)
  10. `no_response` (Réponse si Non)
  11. `keyword1` (4 caractères exactement + `\0`, ou `"A   "` si inutilisé)
  12. `keyword2` (4 caractères exactement + `\0`, ou `"A   "` si inutilisé)

Mots-clés intégrés dans le moteur `discourse_tlk.cpp` (ne pas dupliquer) : `NAME`, `LOOK`, `JOB`, `HEAL`, `GIVE`, `JOIN`, `BYE`.

### 2.5 `.DNG` — Donjons (512 octets + 16 ou 64 salles de 256 octets)
- `0x0000..0x01FF` (512 octets) : 8 niveaux de $8 \times 8$ octets :
  - Quartet haut (`byte & 0xF0`) : type de case (`0x00`=Vide, `0x10`=Échelle haut, `0x20`=Échelle bas, `0x30`=Échelle haut/bas, `0x40`=Coffre, `0x50`=Trou plafond, `0x60`=Trou sol, `0x70`=Orbe, `0x80`=Piège vents, `0x81`=Éboulement, `0x8E`=Fosse, `0x90..0x94`=Fontaines, `0xA0..0xA3`=Champs magiques, `0xB0`=Autel, `0xC0`=Porte, `0xD0..0xDF`=Salle 0..15, `0xE0`=Porte secrète, `0xF0`=Mur).
  - Quartet bas (`byte & 0x0F`) : monstre (`0`=Aucun, `1..15`=Rat à Rogue).
- `0x0200+` : Salles de donjon de **256 octets** :
  - `0x00..0x0F` : 4 déclencheurs au sol (4 octets chacun : `tile`, `(x<<4)|y` trigger, `(x1<<4)|y1`, `(x2<<4)|y2`).
  - `0x10..0x3F` : 16 monstres (`tile[16]`, `x[16]`, `y[16]`).
  - `0x40..0x7F` : positions d'entrée du groupe pour les 4 directions (N, E, S, O : `x[8]`, `y[8]` chacune).
  - `0x80..0xF8` : matrice $11 \times 11$ (121 octets) des tuiles de la salle.
  - `0xF9..0xFF` : 7 octets de bourrage.

### 2.6 `.CON` — Arènes de combat et Sanctuaires (192 octets)
- `0x00..0x0F` : `creature_start_x` (16 octets).
- `0x10..0x1F` : `creature_start_y` (16 octets).
- `0x20..0x27` : `player_start_x` (8 octets).
- `0x28..0x2F` : `player_start_y` (8 octets).
- `0x30..0x3F` : 16 octets de constante d'en-tête.
- `0x40..0xB8` : 121 octets de la grille $11 \times 11$.
- `0xB9..0xBF` : 7 octets de bourrage.

---

## 3. Système de Quêtes et Paquet `.mod` (CDI `xu4^2`)

- Dans **Ultima IV / xU4**, les quêtes ne sont pas des scripts impératifs séparés : elles émergent de la coordination entre :
  1. Les **mots-clés** des dialogues `.TLK` et les **rumeurs** de taverne (`vendors.b`),
  2. Les **objets de quête** déclarés via `labels` dans `maps.b` (`honestyrune`..`humilityrune`, `bluestone`..`whitestone`, `bell`, `book`, `candle`, `horn`, `wheel`, `skull`, `mandrake1`, `nightshade1`, `mysticarmor`, `mysticswords`, `telescope`, `balloon`),
  3. Les **portails** reliant le monde, les châteaux/villes, les étages et les donjons,
  4. Les **8 Vertus, Sanctuaires et Mantras**.
- Le format de paquet **`.mod` (CDI Package `xu4^2`)** commence par `DA 7A 70 00 78 75 34 02` suivi de l'offset et la taille de la Table des Matières (`u32` little-endian), des chunks bruts (`CONF` `0x7FC0`, `MODI`/`FNAM` `0x0006`, `Xu4 talk` `0x4007`, `Xu4 map` `0x1FC0`, `PNG` `0x1002`), et de la TOC finale.

**Ultima IV Maker** utilise des fichiers **YAML** lisibles par l'humain comme format source unique, puis compile automatiquement les binaires (`.ULT`, `.TLK`, `.MAP`, `.DNG`, `.CON`, `SHAPES.EGA`), les scripts Boron (`config.b`, `maps.b`, `vendors.b`) et le conteneur `.mod`.
