"""
core/nlp.py — Normalisation et analyse sémantique des questions Miny.

Fonctions publiques :
  normaliser(texte)          → str     (min + sans accents + synonymes)
  extraire_periode(question) → dict    {annee, mois, mois_nom, trimestre, semestre, brut}
  analyser_intentions(q)     → list[str]
  detecter_domaines(q)       → list[str]
  analyser_question(q)       → dict    {question, q_norm, domaines, intentions, periode,
                                        nb_mots, multi_questions}
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.text import norm as _base_norm
from config.synonymes import DICTIONNAIRE_SYNONYMES
from config.verbes import VERBES_ACTION


# ── Mois FR normalisés → numéro 01-12 ─────────────────────────────────────────
_MOIS_FR: dict[str, str] = {
    "janvier": "01", "jan": "01",
    "fevrier": "02", "fev": "02",
    "mars": "03",
    "avril": "04", "avr": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07", "juil": "07",
    "aout": "08", "aou": "08",
    "septembre": "09", "sep": "09", "sept": "09",
    "octobre": "10", "oct": "10",
    "novembre": "11", "nov": "11",
    "decembre": "12", "dec": "12",
}

# ── Abréviations temporelles (normalisées avant extraction) ───────────────────
_ABBREV_PERIODE: list[tuple[str, str]] = [
    (r"\bT1\b", "trimestre 1"), (r"\bT2\b", "trimestre 2"),
    (r"\bT3\b", "trimestre 3"), (r"\bT4\b", "trimestre 4"),
    (r"\bQ1\b", "trimestre 1"), (r"\bQ2\b", "trimestre 2"),
    (r"\bQ3\b", "trimestre 3"), (r"\bQ4\b", "trimestre 4"),
    (r"\bS1\b", "semestre 1"),  (r"\bS2\b", "semestre 2"),
]

# ── Mots-clés de domaine (ordre = spécificité décroissante) ───────────────────
# Utilisés par detecter_domaines() et analyser_question().
DOMAINE_KW: dict[str, list[str]] = {
    "non_conformite": [
        "non-conformite", "non conformite", "nc ", " nc", "anomalie",
        "inspection", "bureau veritas", "audit organisme", "certificat", "bv ",
        "rapport inspection", "conformit",
    ],
    "pges": [
        "pges", "ande", "environnemental", "plan de gestion",
        "reboisement", "dechet", "biodiversite", "poussiere", "erosion",
        "rehabilitation", "hydrocarbure",
    ],
    "hse": [
        "obligation hse", "hse", "avancement action",
        "action corrective", "actions correctives",
        "levee action", "delai action",
        "urgence", "urgent", "urgentes", "urgents",
        "prioritaire", "prioritaires",
        "non conforme", "non conformite", "conformite",
        "suivi obligation",
    ],
    "panne": [
        "panne", "pannes", "arret technique", "defaillance", "maintenance",
        "trencher", "trs", "breakdown", "immobilise", "reparation",
        "journal engin",
    ],
    "indemnisation": [
        "indemnisation", "compensation", "communaute", "populations",
        "terres", "degradation terrain",
    ],
    "statut": [
        "statut", "non realise", "en cours",
        "avancement", "bloque", "progression",
        "retard", "en retard", "depasse", "depassee",
        "clore", "cloture", "cloturee",
    ],
    "tombereau": [
        "tombereau", "tombereaux", "camion benne", "benne",
        "dumper", "a40g", "volvo", "cat n",
    ],
    "pelle": [
        "pelle", "pelles", "liebherr", "r9200", "excavatrice",
    ],
    "utilisation": [
        "utilise", "travaille", "a travaille", "ont travaille",
        "a fonctionne", "ont fonctionne", "actif", "en service",
        "rotations", "voyages", "sessions", "heures moteur",
        "combien de fois", "nombre de fois",
    ],
    "engin": [
        "engin", "engins", "equipement", "flotte", "materiel roulant", "parc",
    ],
    "heures_machine": [
        "heure machine", "heures machine", "hm", "shift", "shifts",
        "vacation", "poste de travail", "horaire", "temps travail",
        "disponibilite engin", "taux disponibilite",
    ],
    "carburant": [
        "carburant", "gasoil", "diesel", "fuel", "litre", "citerne",
        "depotage", "ravitaillement", "approvisionnement", "petro", "iveqi",
    ],
    "transport": [
        "transport", "transporte", "achemine", "arrive port", "depart mine",
        "paa", "transport minerai", "societe transport", "rotation transport",
    ],
    "navire": [
        "navire", "chargement navire", "loading", "bateau", "cargo",
        "depart navire", "arrivee navire", "productivite port",
    ],
    "qualite": [
        "qualite", "teneur al2o3", "teneur sio2", "teneur fe2o3",
        "alumine", "silice", "bauxite", "echantillon", "analyse labo",
        "resultat labo",
    ],
    "excavation": [
        "tonnage excave", "excavation", "excave", "sterile",
        "decapage", "volume excave", "decouverte",
    ],
    "objectif": [
        "objectif", "prevu", "prevision", "target", "ecart",
        "taux accomplissement", "budget", "planifie", "programme",
    ],
    "tonnage": [
        "tonnage descendu", "tonnage transporte", "tonnage",
        "descente", "descendu", "production journaliere",
        "quantite journaliere", "minerai descend",
        "comparer", "compare", "comparaison",  # comparaison → tonnage par défaut
    ],
    "meta": [
        "donnees disponibles", "tables disponibles", "quelles donnees",
        "quelles tables", "annees disponibles", "quelle periode",
        "que contient", "quelles annees", "periode couverte",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ═══════════════════════════════════════════════════════════════════════════════

def normaliser(texte: str) -> str:
    """
    Normalise un texte :
    1. Minuscules + suppression accents (via _base_norm de src/utils/text)
    2. Remplacement des synonymes miniers (config/synonymes) par forme canonique.
       Les synonymes purement alphabétiques utilisent des frontières de mots (\b)
       pour éviter les substitutions de sous-chaînes (ex: "accompli" dans
       "accomplissement" ne doit pas être remplacé par "realise").
    """
    q = _base_norm(texte)
    for canonical, synonymes in DICTIONNAIRE_SYNONYMES.items():
        for syn in sorted(synonymes, key=len, reverse=True):
            if syn not in q:
                continue
            # Utiliser \b pour les synonymes purement alphabétiques (lettres + espaces)
            # afin d'éviter les collisions de sous-chaînes
            if re.match(r'^[a-z ]+$', syn):
                q = re.sub(r'\b' + re.escape(syn) + r'\b', canonical, q)
            else:
                q = q.replace(syn, canonical)
    return q


def _normaliser_abbrev_periode(q: str) -> str:
    """Remplace T1/T4, Q1/Q4, S1/S2 par leurs formes longues."""
    for pattern, replacement in _ABBREV_PERIODE:
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    return q


def extraire_periode(question: str) -> dict:
    """
    Extrait la période temporelle d'une question.

    Retourne un dict :
      annee     : int | None     (ex: 2025)
      mois      : str | None     (ex: "03" pour mars)
      mois_nom  : str | None     (ex: "Mars")
      trimestre : int | None     (1–4)
      semestre  : int | None     (1–2)
      brut      : list[str]      (fragments trouvés)
    """
    q = normaliser(question)
    q = _normaliser_abbrev_periode(q)

    result: dict = {
        "annee": None, "mois": None, "mois_nom": None,
        "trimestre": None, "semestre": None, "brut": [],
    }

    # Année (20XX)
    m = re.search(r"\b(20\d{2})\b", q)
    if m:
        result["annee"] = int(m.group(1))
        result["brut"].append(m.group(0))

    # Mois (plus long en premier pour éviter "oct" capturant "octobre")
    for mois_nom, mois_num in sorted(_MOIS_FR.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(r"\b" + mois_nom + r"\b", q):
            result["mois"]     = mois_num
            result["mois_nom"] = mois_nom.capitalize()
            result["brut"].append(mois_nom)
            break

    # Trimestre
    m = re.search(r"trimestre\s*([1-4])", q)
    if m:
        result["trimestre"] = int(m.group(1))
        result["brut"].append(m.group(0))

    # Semestre
    m = re.search(r"semestre\s*([1-2])", q)
    if m:
        result["semestre"] = int(m.group(1))
        result["brut"].append(m.group(0))

    return result


def analyser_intentions(question: str) -> list[str]:
    """
    Détecte les intentions/verbes d'action dans la question normalisée.
    Retourne la liste des catégories trouvées (ordre d'apparition dans VERBES_ACTION).
    """
    q = normaliser(question)
    return [
        intent
        for intent, verbes in VERBES_ACTION.items()
        if any(v in q for v in verbes)
    ]


def _kw_match(kw: str, q_norm: str) -> bool:
    """
    Teste si le mot-clé kw est présent dans la question normalisée q_norm.
    - Mots-clés purement alphabétiques (lettres + espaces) : frontière de mot \b
      pour éviter les faux positifs ("statut" dans "statistique", "panne" dans "compagne").
    - Mots-clés contenant des chiffres ou caractères spéciaux : sous-chaîne simple
      (ex: "al2o3", "s1-s6", "trs n°296").
    """
    if re.match(r'^[a-z ]+$', kw):
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', q_norm))
    return kw in q_norm


def detecter_domaines(question: str) -> list[str]:
    """
    Détecte les domaines métier présents dans la question.
    Ordre = spécificité décroissante (non_conformite en premier, tonnage en dernier).
    """
    q = normaliser(question)
    return [
        dom
        for dom, kws in DOMAINE_KW.items()
        if any(_kw_match(kw, q) for kw in kws)
    ]


def _est_multi_question(question: str) -> bool:
    """
    True uniquement si la question contient clairement plusieurs sous-questions.

    Critères (ordre de priorité) :
      1. Deux points d'interrogation "?" → deux vraies questions.
      2. Virgule ou " et " séparant deux segments, chacun contenant
         au moins un mot-clé de domaine distinct → ex: "Q1, Q2"
         mais PAS "Tonnage par mois en 2025, en tonnes métriques".
    """
    if question.count("?") > 1:
        return True
    # Découpe sur virgule ou " et "
    sep_pattern = re.compile(r",| et ", re.IGNORECASE)
    parts = sep_pattern.split(question)
    if len(parts) < 2:
        return False
    # Chaque segment doit contenir au moins un domaine reconnu
    segments_avec_domaine = sum(
        1 for part in parts if detecter_domaines(part.strip())
    )
    return segments_avec_domaine >= 2


def analyser_question(question: str) -> dict:
    """
    Analyse complète d'une question.

    Retourne :
      question       : str        (texte original)
      q_norm         : str        (texte normalisé)
      domaines       : list[str]  (domaines détectés)
      intentions     : list[str]  (verbes d'action détectés)
      periode        : dict       (voir extraire_periode)
      nb_mots        : int
      multi_questions: bool       (plusieurs "?" ou virgule longue)
    """
    q_norm = normaliser(question)
    return {
        "question":        question,
        "q_norm":          q_norm,
        "domaines":        detecter_domaines(question),
        "intentions":      analyser_intentions(question),
        "periode":         extraire_periode(question),
        "nb_mots":         len(q_norm.split()),
        # Multi-question : deux "?" ou virgule séparant deux segments
        # qui contiennent chacun un mot-clé de domaine distinct.
        "multi_questions": _est_multi_question(question),
    }
