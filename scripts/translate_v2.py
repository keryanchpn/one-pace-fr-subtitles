"""
translate_v2.py — Pipeline de traduction sous-titres One Pace EN→FR via Gemini Flash.

Architecture :
  0. Extraction  → si pas de .ass EN dans season-dir, extraire depuis les MKV via ffmpeg
  1. ass_parser  → parse .ass, extrait les tags en placeholders [Tn]/[NL]
  2. glossary    → remplace termes One Piece par GLOSSn
  3. Gemini Flash → traduit le texte pur (ne voit jamais les tags ASS)
  4. glossary    → restaure GLOSSn → termes FR
  5. ass_parser  → réinjecte les tags, valide, écrit le .fr.ass

Usage :
  set GEMINI_API_KEY=...

  # Toute une saison (extraction auto si besoin + traduction)
  python tools/translate_v2.py --season-dir "D:/media-server/data/tv/One Pace/Season 17"

  # Un seul épisode
  python tools/translate_v2.py --season-dir "..." --episode S17E02

  # Dry-run (affiche le texte envoyé à Gemini sans appel API)
  python tools/translate_v2.py --season-dir "..." --episode S17E01 --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path


def load_env(env_path: Path) -> None:
    """Charge les variables d'un fichier .env dans os.environ (sans écraser)."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

# Charger D:\media-server\.env dès l'import
load_env(Path(__file__).parent.parent / ".env")

# ── Modules locaux ────────────────────────────────────────────────────────────
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))
from ass_parser import parse_ass, extract_ass_tags, restore_ass_tags, validate_tags, write_ass
from glossary import apply_glossary, restore_glossary

# ── Config ────────────────────────────────────────────────────────────────────
MODEL      = "gemini-2.5-flash"
BATCH_SIZE = 150
TRANSLATE_LOG = TOOLS_DIR.parent / "logs" / "translations.log"

SYSTEM_PROMPT = """\
Tu es un traducteur professionnel anglais→français spécialisé dans One Piece.
Traduis chaque ligne EN→FR, ton manga/anime.
Les placeholders [T0], [T1], [NL], GLOSS0… doivent être copiés EXACTEMENT tels quels.
Format de réponse : numéro|traduction (une par ligne, même ordre, sans commentaires).
"""

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    sys.exit("pip install google-genai --user")


# ── Helpers affichage ─────────────────────────────────────────────────────────

def hms(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))

def bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total) if total else 0
    return f"[{'█' * filled}{'░' * (width - filled)}] {done}/{total}"

def sep(char: str = "─", width: int = 60) -> str:
    return char * width

def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}", flush=True)


# ── ffmpeg ────────────────────────────────────────────────────────────────────

def find_ffmpeg() -> str:
    for candidate in ["ffmpeg", r"C:\ffmpeg\bin\ffmpeg.exe"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    sys.exit("ffmpeg introuvable. Installe-le avec : winget install ffmpeg")


def extract_english_sub(ffmpeg: str, mkv: Path, out: Path) -> bool:
    """Extrait la première piste sous-titre anglaise du MKV vers out (.ass)."""
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    probe = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", str(mkv)],
        capture_output=True, text=True,
    )
    sub_index = None
    sub_lang  = "?"
    try:
        streams = json.loads(probe.stdout).get("streams", [])
        all_subs = [s for s in streams if s.get("codec_type") == "subtitle"]
        log(f"  Pistes sous-titres détectées : {len(all_subs)}")
        for s in all_subs:
            lang  = s.get("tags", {}).get("language", "")
            title = s.get("tags", {}).get("title", "")
            codec = s.get("codec_name", "")
            log(f"    → index {s['index']} | lang={lang or '?'} | codec={codec} | title={title or '—'}")
            if sub_index is None and lang in ("eng", "en", ""):
                sub_index = s["index"]
                sub_lang  = lang or "?"
    except Exception as exc:
        log(f"  ffprobe parsing error : {exc}")

    map_arg = f"0:{sub_index}" if sub_index is not None else "0:s:0"
    log(f"  Extraction piste {map_arg} (lang={sub_lang}) → {out.name}")

    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(mkv), "-map", map_arg, str(out)],
        capture_output=True,
    )
    if result.returncode != 0 or not out.exists():
        stderr = result.stderr.decode(errors="replace").strip().splitlines()
        for line in stderr[-5:]:
            log(f"  ffmpeg: {line}")
        return False
    size_kb = out.stat().st_size // 1024
    log(f"  Extraction OK — {out.name} ({size_kb} Ko)")
    return True


# ── Détection des épisodes ────────────────────────────────────────────────────

def episode_code(name: str) -> str | None:
    m = re.search(r"(S\d{2}E\d{2,})", name, re.IGNORECASE)
    return m.group(1).upper() if m else None


def discover_episodes(season_dir: Path, filter_episode: str | None) -> list[tuple[Path, Path, Path]]:
    mkv_files = sorted(season_dir.glob("*.mkv"))
    if not mkv_files:
        sys.exit(f"Aucun MKV trouvé dans {season_dir}")

    triplets: list[tuple[Path, Path, Path]] = []
    for mkv in mkv_files:
        code = episode_code(mkv.name)
        if filter_episode and (not code or code != filter_episode.upper()):
            continue
        triplets.append((mkv, mkv.with_suffix(".ass"), mkv.with_suffix(".fr.ass")))

    if not triplets:
        sys.exit(f"Aucun épisode correspondant trouvé dans {season_dir}")
    return triplets


def ensure_english_subs(triplets: list[tuple[Path, Path, Path]], ffmpeg: str) -> None:
    missing = [(mkv, ass_en) for mkv, ass_en, _ in triplets if not ass_en.exists()]
    if not missing:
        log(f"Tous les .ass source déjà présents ({len(triplets)} épisode(s))")
        print()
        return

    print(sep())
    print(f"  ÉTAPE 0 — Extraction sous-titres EN ({len(missing)}/{len(triplets)} épisode(s))")
    print(sep())
    t0 = time.time()
    for n, (mkv, ass_en) in enumerate(missing, 1):
        print(f"\n  [{n}/{len(missing)}] {mkv.name}")
        if not extract_english_sub(ffmpeg, mkv, ass_en):
            log("ÉCHEC — épisode ignoré")
    print(f"\n  Extraction terminée en {hms(time.time() - t0)}\n")


# ── Appel Gemini ──────────────────────────────────────────────────────────────

MAX_RETRIES = 5

def translate_batch(client, texts: list[str]) -> list[str]:
    numbered = "\n".join(f"{i}|{t}" for i, t in enumerate(texts))
    prompt = (
        "Traduis chaque ligne ci-dessous anglais→français.\n"
        "Réponds uniquement au format : numéro|traduction\n\n"
        + numbered
    )
    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.2,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
            raw = response.text.strip()
            break
        except Exception as exc:
            err = str(exc)
            # Extraire le retry_delay suggéré par l'API
            delay_match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", err)
            wait = int(delay_match.group(1)) if delay_match else 60 * attempt

            if attempt < MAX_RETRIES and ("429" in err or "quota" in err.lower()):
                log(f"  429 quota — attente {wait}s avant réessai ({attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
            else:
                log(f"  ERREUR Gemini (tentative {attempt}/{MAX_RETRIES}) : {err[:200]}")
                return texts  # fallback : originaux EN

    result = [""] * len(texts)
    for line in raw.splitlines():
        m = re.match(r"^(\d+)\|(.*)$", line)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < len(texts):
                result[idx] = m.group(2)

    fallbacks = sum(1 for t in result if not t)
    for i, t in enumerate(result):
        if not t:
            result[i] = texts[i]

    if fallbacks:
        log(f"  {fallbacks} ligne(s) non parsées → original conservé")

    return result


CREDITS = (
    "; Traduction française automatique via Google Gemini 2.5 Flash\n"
    "; Auteur : championkeryan\n"
    "; Source EN : github.com/one-pace/one-pace-public-subtitles\n"
)

def _inject_credits(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    if "championkeryan" not in content:
        content = content.replace("[Script Info]\n", "[Script Info]\n" + CREDITS, 1)
        path.write_text(content, encoding="utf-8")


# ── Pipeline par épisode ──────────────────────────────────────────────────────

def translate_episode(
    client,
    ass_en: Path,
    ass_fr: Path,
    ep_num: int,
    ep_total: int,
    dry_run: bool,
) -> None:
    print(sep("═"))
    print(f"  ÉPISODE {ep_num}/{ep_total}  —  {ass_en.stem}")
    print(sep("═"))
    t_ep = time.time()

    # ── Parse ──────────────────────────────────────────────────────────────────
    log("Lecture et parsing du .ass...")
    entries = parse_ass(ass_en)

    all_dialogues  = [e for e in entries if e["type"] == "dialogue"]
    skipped        = [e for e in all_dialogues if not e["translate"]]
    to_translate   = [(i, e) for i, e in enumerate(entries) if e["translate"] and e["text"].strip()]
    empty          = [e for e in all_dialogues if e["translate"] and not e["text"].strip()]

    log(f"Dialogues total   : {len(all_dialogues)}")
    log(f"  À traduire      : {len(to_translate)}")
    log(f"  Skippés (Lyrics/Credits) : {len(skipped)}")
    log(f"  Vides           : {len(empty)}")

    if not to_translate:
        log("Rien à traduire — épisode ignoré.")
        print()
        return

    # ── Extraction tags + glossaire ───────────────────────────────────────────
    log("Extraction des tags ASS et application du glossaire...")
    tag_maps: dict[int, dict] = {}
    clean_texts: dict[int, str] = {}
    total_tags   = 0
    total_gloss  = 0

    for i, e in to_translate:
        clean, tag_map = extract_ass_tags(e["text"])
        total_tags += len(tag_map)
        clean, gloss_map = apply_glossary(clean)
        total_gloss += len(gloss_map)
        tag_map["__gloss__"] = gloss_map
        tag_maps[i] = tag_map
        clean_texts[i] = clean

    log(f"  Tags ASS protégés    : {total_tags}")
    log(f"  Termes glossaire     : {total_gloss} occurrences")

    if dry_run:
        print()
        print("  ── DRY-RUN : texte envoyé à Gemini (50 premières lignes) ──")
        for k, (i, _) in enumerate(to_translate[:50]):
            print(f"  {k:3d} | {clean_texts[i]}")
        print("  (Pas d'appel API en mode --dry-run)")
        print()
        return

    # ── Traduction par batch ──────────────────────────────────────────────────
    indices   = [i for i, _ in to_translate]
    texts     = [clean_texts[i] for i in indices]
    n_batches = (len(texts) - 1) // BATCH_SIZE + 1
    translated_map: dict[int, str] = {}

    log(f"Traduction — {len(texts)} lignes en {n_batches} lot(s) de {BATCH_SIZE}")
    print()

    t_batches = time.time()
    for b in range(n_batches):
        batch_texts   = texts[b * BATCH_SIZE : (b + 1) * BATCH_SIZE]
        batch_indices = indices[b * BATCH_SIZE : (b + 1) * BATCH_SIZE]

        done_lines = b * BATCH_SIZE
        pct        = done_lines / len(texts) * 100
        progress   = bar(done_lines, len(texts))

        elapsed = time.time() - t_batches
        if b > 0:
            eta = elapsed / b * (n_batches - b)
            eta_str = f" | ETA {hms(eta)}"
        else:
            eta_str = ""

        print(f"  Lot {b + 1:2d}/{n_batches} {progress}  {pct:5.1f}%{eta_str}")
        log(f"Envoi à Gemini ({len(batch_texts)} lignes)...")

        t_req = time.time()
        try:
            translations = translate_batch(client, batch_texts)
            duration = time.time() - t_req
            log(f"Réponse reçue en {duration:.1f}s")
        except Exception as exc:
            log(f"ERREUR Gemini : {exc}")
            log("Originaux EN conservés pour ce lot")
            translations = batch_texts

        for idx, tr in zip(batch_indices, translations):
            translated_map[idx] = tr

        if b < n_batches - 1:
            time.sleep(1)

    print(f"\n  {bar(len(texts), len(texts))}  100.0%")
    log(f"Traduction terminée en {hms(time.time() - t_batches)}")
    print()

    # ── Restauration + validation ─────────────────────────────────────────────
    log("Restauration des tags et validation...")
    review_lines : list[str] = []
    ok_count     = 0
    invalid_count = 0

    for i, e in to_translate:
        original_text = e["text"]
        translated    = translated_map.get(i, original_text)
        gloss_map     = tag_maps[i].pop("__gloss__")
        tag_map       = tag_maps[i]

        translated = restore_glossary(translated, gloss_map)
        translated = restore_ass_tags(translated, tag_map)

        if validate_tags(original_text, translated):
            e["text"] = translated
            ok_count += 1
        else:
            invalid_count += 1
            review_lines.append(
                f"ligne {e['line_num']} | TAGS invalides\n"
                f"  original : {original_text}\n"
                f"  traduit  : {translated}\n"
            )

    log(f"Validation : {ok_count} OK | {invalid_count} TAGS invalides (→ EN conservé)")

    # ── Écriture ──────────────────────────────────────────────────────────────
    write_ass(ass_fr, entries)
    _inject_credits(ass_fr)
    size_kb = ass_fr.stat().st_size // 1024
    log(f"Fichier écrit : {ass_fr.name} ({size_kb} Ko)")

    # ── Log ───────────────────────────────────────────────────────────────────
    TRANSLATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TRANSLATE_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {ass_fr.name}\n")

    if review_lines:
        review_path = ass_fr.with_suffix(".review.txt")
        review_path.write_text("\n".join(review_lines), encoding="utf-8")
        log(f"{invalid_count} ligne(s) à revoir → {review_path.name}")

    log(f"Épisode terminé en {hms(time.time() - t_ep)}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Traduit les sous-titres One Pace EN→FR via Gemini")
    parser.add_argument("--season-dir", required=True,
                        help="Dossier de la saison (ex. D:/media-server/data/tv/One Pace/Season 17)")
    parser.add_argument("--episode",
                        help="Traiter un seul épisode (ex. S17E02)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Afficher le texte envoyé à Gemini sans appel API")
    args = parser.parse_args()

    season_dir = Path(args.season_dir)
    if not season_dir.exists():
        sys.exit(f"Dossier introuvable : {season_dir}")

    ffmpeg = find_ffmpeg()

    if not args.dry_run:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            sys.exit("GEMINI_API_KEY non définie. Remplis D:\\media-server\\.env")
        client = genai.Client(api_key=api_key)
    else:
        client = None

    triplets = discover_episodes(season_dir, args.episode)

    print()
    print(sep("═"))
    print(f"  One Pace — Pipeline de traduction EN→FR")
    print(sep("═"))
    print(f"  Modèle    : {MODEL}")
    print(f"  Saison    : {season_dir.name}")
    print(f"  Épisodes  : {len(triplets)} MKV trouvé(s)")
    print(f"  Heure     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep("═"))
    print()

    t_total = time.time()

    # Étape 0 : extraction
    ensure_english_subs(triplets, ffmpeg)

    # Étapes 1-5 : traduction
    to_process = [
        (mkv, ass_en, ass_fr)
        for mkv, ass_en, ass_fr in triplets
        if ass_en.exists() and (not ass_fr.exists() or args.dry_run)
    ]
    skipped_existing = len(triplets) - len([t for t in triplets if not t[2].exists()]) - len(
        [t for t in triplets if not t[1].exists()]
    )

    if skipped_existing:
        log(f"{skipped_existing} épisode(s) déjà traduits → ignorés")
        print()

    if not to_process:
        print("  Tous les épisodes sont déjà traduits.")
    else:
        for n, (mkv, ass_en, ass_fr) in enumerate(to_process, 1):
            translate_episode(client, ass_en, ass_fr, n, len(to_process), args.dry_run)

    print(sep("═"))
    log(f"Pipeline complet en {hms(time.time() - t_total)}")
    print(sep("═"))
    print()


if __name__ == "__main__":
    main()
