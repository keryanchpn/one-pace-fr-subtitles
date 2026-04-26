"""
glossary.py — Glossaire One Piece centralisé pour la traduction EN→FR.

Deux types d'entrées :
  (en_term, en_term) → conserver tel quel
  (en_term, fr_term) → remplacer par la version FR

Fonctions :
  apply_glossary(text)              → (text_with_placeholders, gloss_map)
  restore_glossary(text, gloss_map) → text restauré
"""

import re

# Ordre : termes longs d'abord (tri automatique dans apply_glossary)
GLOSSARY = [
    # ── Titres / grades Marine ────────────────────────────────────────────────
    ("Fleet Admiral Sengoku",       "Amiral en Chef Sengoku"),
    ("Vice Admiral",                "Vice-Amiral"),
    ("Admiral",                     "Amiral"),
    ("Captain",                     "Capitaine"),

    # ── Factions ──────────────────────────────────────────────────────────────
    ("Straw Hat Pirates",           "Pirates au Chapeau de Paille"),
    ("Foxy Pirates",                "Pirates de Foxy"),
    ("Straw Hat Luffy",             "Luffy au Chapeau de Paille"),
    ("Straw Hats",                  "Chapeaux de Paille"),
    ("Straw Hat",                   "Chapeau de Paille"),
    ("World Government",            "Gouvernement Mondial"),
    ("Marines",                     "Marines"),
    ("Marine",                      "Marine"),
    ("Sea Monkeys",                 "Singes des Mers"),
    ("Sea Kings",                   "Rois des Mers"),
    ("Groggy Monsters",             "Groggy Monsters"),

    # ── Lieux ─────────────────────────────────────────────────────────────────
    ("Long Ring Long Land",         "Long Ring Long Land"),
    ("Water Seven",                 "Water Seven"),
    ("Grand Line",                  "Grand Line"),
    ("New World",                   "Nouveau Monde"),
    ("East Blue",                   "East Blue"),
    ("West Blue",                   "West Blue"),
    ("North Blue",                  "North Blue"),
    ("South Blue",                  "South Blue"),
    ("Calm Belt",                   "Ceinture Calme"),
    ("Red Line",                    "Red Line"),
    ("Navy Headquarters",           "Quartier Général de la Marine"),
    ("Marine HQ",                   "QG de la Marine"),
    ("Navy HQ",                     "QG de la Marine"),

    # ── Noms propres — Mugiwara ───────────────────────────────────────────────
    ("Monkey D. Luffy",             "Monkey D. Luffy"),
    ("Roronoa Zoro",                "Roronoa Zoro"),
    ("Nico Robin",                  "Nico Robin"),
    ("Tony Tony Chopper",           "Tony Tony Chopper"),
    ("Luffy",                       "Luffy"),
    ("Zoro",                        "Zoro"),
    ("Nami",                        "Nami"),
    ("Usopp",                       "Usopp"),
    ("Sanji",                       "Sanji"),
    ("Chopper",                     "Chopper"),
    ("Robin",                       "Robin"),
    ("Franky",                      "Franky"),
    ("Brook",                       "Brook"),

    # ── Noms propres — arc Davy Back Fight / Long Ring ────────────────────────
    ("Foxy",                        "Foxy"),
    ("Porche",                      "Porche"),
    ("Capote",                      "Capote"),
    ("Monda",                       "Monda"),
    ("Hamburg",                     "Hamburg"),
    ("Pickles",                     "Pickles"),
    ("Big Pan",                     "Big Pan"),
    ("Itomimizu",                   "Itomimizu"),
    ("Shelly",                      "Shelly"),
    ("Littonto",                    "Littonto"),
    ("Tonjit",                      "Tonjit"),

    # ── Noms propres — arc Sabaody / S22 ─────────────────────────────────────
    ("Silvers Rayleigh",            "Silvers Rayleigh"),
    ("Dark King Rayleigh",          "Rayleigh le Roi des Ténèbres"),
    ("Rayleigh",                    "Rayleigh"),
    ("Shakky",                      "Shakky"),
    ("Camie",                       "Camie"),
    ("Hachi",                       "Hachi"),
    ("Pappag",                      "Pappag"),
    ("Iron Mask Duval",             "Duval au Masque de Fer"),
    ("Duval",                       "Duval"),
    ("Sentoumaru",                  "Sentoumaru"),
    ("Eustass Kid",                 "Eustass Kid"),
    ("Capone Bege",                 "Capone Bege"),
    ("Trafalgar Law",               "Trafalgar Law"),
    ("X Drake",                     "X Drake"),
    ("Saint Charlos",               "Saint Charlos"),

    # ── Noms propres — arc Thriller Bark / S21 ───────────────────────────────
    ("Gekko Moriah",                "Gekko Moriah"),
    ("Moriah",                      "Moriah"),
    ("Perona",                      "Perona"),
    ("Absalom",                     "Absalom"),
    ("Hogback",                     "Hogback"),
    ("Victoria Cindry",             "Victoria Cindry"),
    ("Cindry",                      "Cindry"),
    ("Bartholomew Kuma",            "Bartholomew Kuma"),
    ("Kuma",                        "Kuma"),
    ("Ryuma",                       "Ryuma"),
    ("Lola",                        "Lola"),
    ("Oars",                        "Oars"),
    ("Kumashi",                     "Kumashi"),
    ("Hildon",                      "Hildon"),
    ("Jigoro",                      "Jigoro"),

    # ── Noms propres — arc Post-Enies Lobby / S20 ────────────────────────────
    ("Portgas D. Ace",              "Portgas D. Ace"),
    ("Fire Fist Ace",               "Ace au Poing de Feu"),
    ("Ace",                         "Ace"),
    ("Marshall D. Teach",           "Marshall D. Teach"),
    ("Blackbeard",                  "Barbe Noire"),
    ("Monkey D. Dragon",            "Monkey D. Dragon"),
    ("Dragon",                      "Dragon"),
    ("Sogeking",                    "Sogeking"),
    ("Whitebeard",                  "Barbe Blanche"),
    ("Edward Newgate",              "Edward Newgate"),
    ("Thatch",                      "Thatch"),

    # ── Noms propres — Marines / Amiraux ─────────────────────────────────────
    ("Sengoku",                     "Sengoku"),
    ("Aokiji",                      "Aokiji"),
    ("Akainu",                      "Akainu"),
    ("Kizaru",                      "Kizaru"),
    ("Smoker",                      "Smoker"),
    ("Crocodile",                   "Crocodile"),
    ("Garp",                        "Garp"),

    # ── Factions / titres ─────────────────────────────────────────────────────
    ("Seven Warlords of the Sea",   "Sept Corsaires de la Mer"),
    ("Revolutionary Army",          "Armée Révolutionnaire"),
    ("Whitebeard Pirates",          "Pirates de Barbe Blanche"),
    ("Celestial Dragons",           "Dragons Célestes"),
    ("World Nobles",                "Nobles Mondiaux"),
    ("Worst Generation",            "Pire Génération"),
    ("Supernovas",                  "Supernovas"),
    ("Supernova",                   "Supernova"),
    ("Pacifista",                   "Pacifista"),
    ("Flying Fish Riders",          "Cavaliers du Poisson-Volant"),

    # ── Lieux — arc S22 Sabaody ──────────────────────────────────────────────
    ("Sabaody Archipelago",         "Archipel de Sabaody"),
    ("Mariejoa",                    "Mariejoa"),
    ("Holy Land",                   "Terre Sainte"),

    # ── Lieux — arc S21 Thriller Bark ────────────────────────────────────────
    ("Florian Triangle",            "Triangle de Florian"),
    ("Thriller Bark",               "Thriller Bark"),

    # ── Lieux — arc S20 ───────────────────────────────────────────────────────
    ("Fish-Man Island",             "Île des Hommes-Poissons"),
    ("Fishman Island",              "Île des Hommes-Poissons"),
    ("Banaro Island",               "Île Banaro"),
    ("Elbaf",                       "Elbaf"),
    ("Baltigo",                     "Baltigo"),
    ("Enies Lobby",                 "Enies Lobby"),

    # ── Pouvoirs / Fruits ─────────────────────────────────────────────────────
    ("Shadow-Shadow Fruit",         "Fruit de l'Ombre"),
    ("Kage Kage no Mi",             "Fruit de l'Ombre"),
    ("Hollow-Hollow Fruit",         "Fruit du Spectre"),
    ("Horo Horo no Mi",             "Fruit du Spectre"),
    ("Paw-Paw Fruit",               "Fruit de la Patte"),
    ("Nikyu Nikyu no Mi",           "Fruit de la Patte"),
    ("Darkness Fruit",              "Fruit des Ténèbres"),
    ("Dark-Dark Fruit",             "Fruit des Ténèbres"),
    ("Flame-Flame Fruit",           "Fruit de la Flamme"),
    ("Mera Mera no Mi",             "Fruit de la Flamme"),
    ("Yami Yami no Mi",             "Fruit des Ténèbres"),
    ("Logia",                       "Logia"),
    ("Paramecia",                   "Paramecia"),
    ("Zoan",                        "Zoan"),
    ("Devil Fruits",                "Fruits du Démon"),
    ("Devil Fruit",                 "Fruit du Démon"),
    ("Conqueror's Haki",            "Haki des Rois"),
    ("Armament Haki",               "Haki de l'Armement"),
    ("Observation Haki",            "Haki de l'Observation"),
    ("Haki",                        "Haki"),
    ("Gum-Gum",                     "Gom Gom"),
    ("Gum Gum",                     "Gom Gom"),
    ("Gomu Gomu",                   "Gom Gom"),

    # ── Techniques — conservées en VO ────────────────────────────────────────
    ("Slow-Slow Beam",              "Slow-Slow Beam"),
    ("Noro Noro Beam",              "Noro Noro Beam"),
    ("Slow Beam",                   "Slow Beam"),
    ("Noro Noro",                   "Noro Noro"),
    ("Slowmo Photons",              "Slowmo Photons"),
    ("Megaton Nine-Tails Rush",     "Megaton Nine-Tails Rush"),
    ("Mirror Racket",               "Mirror Racket"),
    ("Gorilla Punch Golden Hits",   "Gorilla Punch Golden Hits"),
    ("Gorilla Puncher 13",          "Gorilla Puncher 13"),
    ("Rubber Whip",                 "Rubber Whip"),
    ("Rubber Gatling",              "Rubber Gatling"),
    ("Rubber Storm",                "Rubber Storm"),
    ("Gum-Gum Pistol",              "Gum-Gum Pistol"),
    ("Gum-Gum Storm",               "Gum-Gum Storm"),
    ("No-Sword Style",              "No-Sword Style"),
    ("Dragon Twister",              "Dragon Twister"),
    ("Ice Time",                    "Ice Time"),
    ("Ocho Fleurs",                 "Ocho Fleurs"),
    ("Eight Flowers",               "Eight Flowers"),
    ("Bad Manner Kick Course",      "Bad Manner Kick Course"),
    ("Spiteful Shoulder Throw",     "Spiteful Shoulder Throw"),
    ("Sea Surface Splitter",        "Sea Surface Splitter"),
    ("Flame Star",                  "Flame Star"),
    ("Power Shoot",                 "Power Shoot"),
    ("Foxy Fighter",                "Foxy Fighter"),

    # ── Techniques — arc S20 / Ace / Garp ───────────────────────────────────
    ("Fire Fist",                   "Poing de Feu"),
    ("Flame Commandment",           "Commandement de Flamme"),
    ("Great Flame Commandment",     "Grand Commandement de Flamme"),
    ("Flame Emperor",               "Empereur de Flamme"),
    ("Cross Fire",                  "Feu Croisé"),
    ("Firefly Fiery Doll",          "Poupée Flamboyante"),
    ("St. Elmo's Fire",             "Feu de Saint-Elme"),
    ("Fire Pillar",                 "Colonne de Feu"),
    ("Fire Gun",                    "Pistolet de Feu"),
    ("Black Hole",                  "Trou Noir"),
    ("Dark Vortex",                 "Vortex des Ténèbres"),
    ("Fist of Love",                "Poing de l'Amour"),
    ("Punch of Love",               "Poing de l'Amour"),
    ("Coup de Burst",               "Coup de Burst"),
    ("Coup de Vent",                "Coup de Vent"),
    ("Den Den Mushi",               "Den Den Mushi"),

    # ── Techniques — en français ──────────────────────────────────────────────
    ("Troisième Haché",             "Troisième Haché"),
    ("Bouquetière Shot",            "Bouquetière Shot"),
    ("Armée de l'Air Power Shoot",  "Armée de l'Air Power Shoot"),
    ("Armée de l'Air",              "Armée de l'Air"),
    ("Troisième",                   "Troisième"),
    ("Haché",                       "Haché"),
    ("Bouquetiere",                 "Bouquetiere"),
    ("Bouquetière",                 "Bouquetière"),

    # ── Jeux / règles Davy Back Fight ────────────────────────────────────────
    ("Davy Jones' Locker",          "le Coffre de Davy Jones"),
    ("Davy Jones",                  "Davy Jones"),
    ("Davy Back Fight",             "Davy Back Fight"),
    ("Donut Race",                  "Donut Race"),
    ("Groggy Ring",                 "Groggy Ring"),
    ("Jolly Roger",                 "Jolly Roger"),
    ("Barrel Mines",                "Barrel Mines"),

    # ── Véhicules ─────────────────────────────────────────────────────────────
    ("Mothership Coaster",          "Mothership Coaster"),
    ("Barrel Tiger",                "Barrel Tiger"),
    ("Cutie Wagon",                 "Cutie Wagon"),

    # ── Navigation ────────────────────────────────────────────────────────────
    ("Eternal Poses",               "Eternal Poses"),
    ("Eternal Pose",                "Eternal Pose"),
    ("Log Pose",                    "Log Pose"),
    ("Vivre Card",                  "Vivre Card"),
    ("Breath Dial",                 "Breath Dial"),
    ("Jet Dial",                    "Jet Dial"),

    # ── Bateaux ───────────────────────────────────────────────────────────────
    ("Thousand Sunny",              "Thousand Sunny"),
    ("Going Merry",                 "Going Merry"),
    ("Merry",                       "Merry"),

    # ── Titres / divers ───────────────────────────────────────────────────────
    ("Pirate King",                 "Roi des Pirates"),
    ("Yonko",                       "Yonko"),
    ("Shichibukai",                 "Shichibukai"),
    ("Warlord",                     "Corsaire"),
    ("Berrys",                      "Berrys"),
    ("Belly",                       "Berrys"),
    ("Beri",                        "Berrys"),
    ("Chirp-Chirp",                 "Piou-Piou"),
    ("Afro",                        "Afro"),
    ("wotan",                       "wotan"),
    ("fishman",                     "homme-poisson"),
    ("Fishman Karate",              "Karaté des Hommes-Poissons"),
    ("Peanut Strategy",             "Stratégie de la Cacahuète"),
]


def apply_glossary(text: str) -> tuple[str, dict]:
    """
    Remplace les termes du glossaire par des placeholders GLOSSn.
    Trie par longueur décroissante pour éviter les remplacements partiels.
    Retourne (texte_avec_placeholders, gloss_map).
    """
    mapping: dict[str, str] = {}
    idx = 0
    for en_term, fr_term in sorted(GLOSSARY, key=lambda x: -len(x[0])):
        pattern = re.compile(r"\b" + re.escape(en_term) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            placeholder = f"GLOSS{idx}"
            text = pattern.sub(placeholder, text)
            mapping[placeholder] = fr_term
            idx += 1
    return text, mapping


def restore_glossary(text: str, gloss_map: dict) -> str:
    """Restaure les placeholders GLOSSn par leurs termes FR."""
    for placeholder, fr_term in gloss_map.items():
        text = text.replace(placeholder, fr_term)
        text = text.replace(placeholder.lower(), fr_term)
        text = text.replace(placeholder.capitalize(), fr_term)
    return text
