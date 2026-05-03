"""
ass_parser.py — Parsing et écriture de fichiers .ass pour la traduction.

Styles non traduits — détection par pattern (case-insensitive) :
  - contient : karaoke, kanji, furigana, lyrics, credits, romaji, translation
  - commence par : OP suivi de chiffres (OP13-..., OP18 ..., OP19 ...)

Fonctions publiques :
  parse_ass(path)                        → list[dict]  (entrées du fichier)
  extract_ass_tags(text)                 → (text_clean, tag_map)
  restore_ass_tags(text, tag_map)        → text original
  validate_tags(original, translated)    → bool
  write_ass(path, entries)               → None
"""

import re
from pathlib import Path

# Patterns de styles à NE PAS traduire
_SKIP_PATTERNS = re.compile(
    r"karaoke|kanji|furigana|lyrics|credits|romaji|translation|^OP\d",
    re.IGNORECASE,
)

def _should_skip(style: str) -> bool:
    return bool(_SKIP_PATTERNS.search(style))

# Vrais tags ASS : contiennent obligatoirement un \ (ex: {\i1}, {\fad(...)})
# Les {texte lisible} sans \ sont des références One Pace, pas des tags ASS
RE_TAG = re.compile(r'\{[^}]*\\[^}]*\}')
RE_NL  = re.compile(r'\\N', re.IGNORECASE)


def parse_ass(path: Path) -> list[dict]:
    """
    Lit un fichier .ass et retourne une liste d'entrées.

    Chaque entrée est un dict :
      {
        "type":      "dialogue" | "other",
        "line_num":  int,
        "raw":       str,          # ligne brute complète
        "prefix":    str,          # "Dialogue: 0,0:00:01.00,0:00:02.00,Style,," etc.
        "style":     str,          # nom du style ASS
        "text":      str,          # texte brut (avec tags ASS)
        "translate": bool,         # False si style ignoré
      }
    """
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    entries = []
    for line_num, line in enumerate(content.splitlines(keepends=True)):
        if line.startswith("Dialogue:"):
            parts = line.rstrip("\n").split(",", 9)
            if len(parts) == 10:
                style = parts[3].strip()
                entries.append({
                    "type":      "dialogue",
                    "line_num":  line_num,
                    "raw":       line,
                    "prefix":    ",".join(parts[:9]) + ",",
                    "style":     style,
                    "text":      parts[9],
                    "translate": not _should_skip(style),
                })
                continue
        entries.append({
            "type":      "other",
            "line_num":  line_num,
            "raw":       line,
            "prefix":    "",
            "style":     "",
            "text":      "",
            "translate": False,
        })
    return entries


def extract_ass_tags(text: str) -> tuple[str, dict]:
    """
    Remplace les tags ASS {…} par [T0],[T1]… et \\N par [NL].
    Retourne (texte_nettoyé, tag_map).
    """
    tag_map: dict[str, str] = {}
    idx = 0

    def replace_tag(m: re.Match) -> str:
        nonlocal idx
        placeholder = f"[T{idx}]"
        tag_map[placeholder] = m.group(0)
        idx += 1
        return placeholder

    text = RE_TAG.sub(replace_tag, text)
    text = RE_NL.sub("[NL]", text)
    return text, tag_map


def restore_ass_tags(text: str, tag_map: dict) -> str:
    """Restaure [Tn] et [NL] dans le texte traduit."""
    text = text.replace("[NL]", "\\N")
    for placeholder, original in tag_map.items():
        text = text.replace(placeholder, original)
    return text


def validate_tags(original: str, translated: str) -> bool:
    """Vérifie que le nombre de tags {…} est identique."""
    return len(RE_TAG.findall(original)) == len(RE_TAG.findall(translated))


def write_ass(path: Path, entries: list[dict]) -> None:
    """Écrit les entrées dans un fichier .ass (UTF-8)."""
    lines = []
    for e in entries:
        if e["type"] == "dialogue":
            lines.append(e["prefix"] + e["text"] + "\n")
        else:
            lines.append(e["raw"])
    path.write_text("".join(lines), encoding="utf-8")
