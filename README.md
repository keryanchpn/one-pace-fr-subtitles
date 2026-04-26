# One Pace — Sous-titres français (traduction automatique via Gemini)

Sous-titres en français pour [One Pace](https://onepace.net), générés automatiquement
à partir des sous-titres anglais officiels via l'API Gemini de Google.

> **Avertissement** : il s'agit d'une traduction automatique. La qualité est bonne
> mais des erreurs subsistent. Les noms propres et termes One Piece sont protégés
> par un glossaire dédié pour rester fidèles à la VF.

---

## Sous-titres disponibles

| Arc | Saison One Pace | Épisodes | Statut |
|-----|----------------|----------|--------|
| Long Ring Island (Davy Back Fight) | Season 17 | E01–E06 | ✅ Complet (6/6) |
| Enies Lobby | Season 19 | E01–E25 | ✅ Complet (20/25 traduits via Gemini + E05–E09 FR natifs dans le MKV) |
| Post-Enies Lobby | Season 20 | E01–E05 | ✅ Complet (5/5) |

---

## Utiliser les sous-titres

Les fichiers `.fr.ass` peuvent être chargés dans n'importe quel lecteur supportant
les sous-titres ASS : **VLC**, **MPC-HC**, **mpv**, **Jellyfin**, etc.

Placer le fichier `.fr.ass` dans le même dossier que le `.mkv` correspondant,
avec le même nom de base (sans l'extension `.mkv`).

---

## Générer les sous-titres toi-même (scripts)

### Prérequis

```bash
pip install google-genai
```

- **Python 3.11+**
- **ffmpeg** dans le PATH (ou dans `C:\ffmpeg\bin\`)
- Une clé API Gemini (gratuite sur [aistudio.google.com](https://aistudio.google.com))

### Configuration

Crée un fichier `.env` dans le dossier `scripts/` :

```
GEMINI_API_KEY=ta_clé_ici
```

Ou exporte la variable dans ton shell :

```bash
# Windows
set GEMINI_API_KEY=ta_clé_ici

# Linux / macOS
export GEMINI_API_KEY=ta_clé_ici
```

### Lancer la traduction

```bash
# Toute une saison (extraction auto des .ass depuis les MKV si besoin)
python scripts/translate_v2.py --season-dir "D:/One Pace/Season 17"

# Un seul épisode
python scripts/translate_v2.py --season-dir "D:/One Pace/Season 17" --episode S17E02

# Dry-run (voir ce qui sera envoyé à Gemini, sans appel API)
python scripts/translate_v2.py --season-dir "D:/One Pace/Season 17" --episode S17E01 --dry-run
```

### Architecture du pipeline

```
MKV  ──ffmpeg──▶  .ass (EN)
                    │
              ass_parser.py   ← extrait les tags ASS {…} → [T0],[T1]…
                    │
              glossary.py     ← protège les termes One Piece (Luffy, Zoro…)
                    │
             Gemini Flash      ← traduit le texte pur (ne voit jamais les tags)
                    │
              glossary.py     ← restaure les termes FR
                    │
              ass_parser.py   ← réinjecte les tags, valide, écrit le .fr.ass
```

Le modèle utilisé est **gemini-2.5-flash** (rapide et peu coûteux).
Avec le tier gratuit, une saison de ~6 épisodes prend environ 5–10 minutes.

### Fichiers

| Fichier | Rôle |
|---------|------|
| `scripts/translate_v2.py` | Script principal — pipeline complet |
| `scripts/ass_parser.py` | Parsing/écriture .ass, extraction/restauration des tags |
| `scripts/glossary.py` | Glossaire One Piece EN→FR (noms, lieux, techniques) |

---

## Contribuer

- **Corriger le glossaire** : édite `scripts/glossary.py` pour ajouter ou corriger des termes
- **Soumettre des corrections de sous-titres** : ouvre une issue ou une PR
- **Ajouter d'autres arcs** : lance le script sur ta saison et partage les `.fr.ass`

---

## Crédits

- Sous-titres anglais source : [one-pace/one-pace-public-subtitles](https://github.com/one-pace/one-pace-public-subtitles)
- Traduction automatique : Google Gemini 2.5 Flash
- Script & glossaire : championkeryan
