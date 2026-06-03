"""
Détection d'intention sémantique pour Miny (Step 2 — plan d'amélioration).

Fournit :
  - DICTIONNAIRE_SYNONYMES : synonymes miniers → forme canonique
  - VERBES_ACTION          : verbes d'action → catégorie d'intention
  - normaliser()           : normalise + étend les synonymes d'une question
  - detecter_intention()   : retourne une Intention structurée

Usage dans query_router.py (Step 3) :
    from src.engine.intention import detecter_intention
    intent = detecter_intention(question)
    # intent.domaine, intent.verbe, intent.table, intent.engin, intent.confiance
"""

from __future__ import annotations

from dataclasses import dataclass

from src.utils.text import norm as _base_norm

# ── Synonymes → forme canonique ──────────────────────────────────────────────
# Clé   = terme canonique utilisé dans les handlers analytics
# Valeur = synonymes à remplacer (triés du plus long au plus court à l'appel)
DICTIONNAIRE_SYNONYMES: dict[str, list[str]] = {
    # Tonnage / production descendue
    "tonnage descendu": [
        "quantite journaliere descendue", "quantite descendue",
        "production journaliere", "minerai descend",
    ],
    "tonnage excave": [
        "tonnage extrait", "volume extrait", "quantite extraite",
        "minerai extrait", "extraction",
    ],
    "tonnage transporte": [
        "quantite transportee", "minerai achemine", "achemine au port",
        "envoye au port", "expedie",
    ],
    # Engins — normalisations avant detection domaine
    "tombereau": ["camion benne", "benne basculante", "dumper"],
    "trencher":  ["trs n 296", "trs296", "trs n°296", "trs 296", "bulldozer trs"],
    # Qualité
    "teneur al2o3": ["taux alumine", "alumine", "al203"],
    "teneur sio2":  ["taux silice", "silice", "si02"],
    "teneur fe2o3": ["taux fer", "oxyde de fer", "fe203"],
    # Carburant
    "carburant": [
        "gasoil", "diesel", "fuel", "consommation carburant",
        "litre consomme", "plein", "depotage",
    ],
    # Statuts HSE/PGES
    "realise":     ["termine", "acheve", "accompli", "effectue", "execute", "cloture"],
    "non realise": [
        "pas encore fait", "pas realise", "non effectue", "non accompli",
        "restent a faire", "jamais fait", "pas termine", "non fait", "pas fait",
    ],
    "en cours": ["en-cours", "encours", "en progres", "en avancement", "en train"],
    # Comparaison
    "comparer": [
        "par rapport a", "difference entre", "ecart entre",
        "evolution de", "bilan comparatif",
    ],
    # Granularités temporelles (complément de ABBREV dans analytics.py)
    "par mois":      ["mensuel", "mensuelle", "mois par mois", "chaque mois"],
    "par semaine":   ["hebdomadaire", "semaine par semaine", "chaque semaine"],
    "par trimestre": ["trimestriel", "trimestrielle", "chaque trimestre"],
    "par semestre":  ["semestriel", "semestrielle", "chaque semestre"],
}

# ── Verbes d'action → catégorie d'intention ─────────────────────────────────
VERBES_ACTION: dict[str, list[str]] = {
    "lister": [
        "donner", "montrer", "afficher", "voir", "connaitre", "savoir",
        "liste", "enumerer", "indiquer", "quels sont", "quelles sont",
        "donne moi", "montre moi",
    ],
    "calculer": [
        "calculer", "calculez", "combien", "quel est le total", "quel est le",
        "quelle est la quantite", "quelle est la", "quelle valeur",
        "combien de", "quel chiffre", "quel montant",
    ],
    "comparer": [
        "comparer", "compare", "comparaison", "versus", " vs ", "par rapport",
        "difference", "ecart", "evolution", "progression",
        "bilan comparatif",
    ],
    "analyser": [
        "analyser", "analyse", "pourquoi", "comment expliquer",
        "comprendre", "interpreter", "quel impact", "quelle cause",
        "qu est-ce qui", "expliquer",
    ],
    "resumer": [
        "resumer", "resume", "synthese", "bilan", "recapituler",
        "recapitule", "faire le point", "recap", "recapitulatif",
    ],
    "prioriser": [
        "prioriser", "priorite", "urgent", "critique", "choisir",
        "recommander", "que faire", "quelle action", "faut-il",
        "lesquelles choisir", "quoi faire en premier",
    ],
}

# ── Domaines → table DuckDB cible ────────────────────────────────────────────
DOMAINE_TABLE: dict[str, str] = {
    "document":        "__rag__",            # bypass analytics → BM25+LLM
    "pges":            "pges_actions",
    "hse":             "suivi_actions",
    "tombereaux":      "descente_minerai",   # activité engins (présence = travail)
    "pannes_trencher": "journal",            # pannes des deux trenchers
    "heures_machine":  "shifts_horaires",   # heures moteur / shifts par mois
    "transport":       "transport_minerai_paa",
    "port":            "productivite_loading",
    "qualite":         "qualite_echantillons",
    "carburant":       "carburant_citerne",
    "tonnage_excav":   "excavation",
    "objectifs":       "objectifs",
    "meta":            "descente_minerai",
    "tonnage_descente": "descente_minerai",  # domaine par défaut
}

# ── Mots-clés de détection de domaine (ordre = priorité) ────────────────────
# Domaines listés du plus spécifique au plus général.
# La détection itère dans cet ordre et s'arrête dès un match fort.
_DOMAINE_KW: list[tuple[str, list[str]]] = [
    ("document", [
        "inspection", "non-conformit", "bureau veritas", "audit organisme",
        "certificat", "bv ", "garde-corps", "passerelle", "concasseur",
        "conformit", "ins-mine", "rapport inspection",
    ]),
    ("pges", [
        "pges", "ande", "environnemental", "plan de gestion",
        "dechet", "indemnisation", "communaute", "population",
        "rehabilitation", "reboisement", "hydrocarbure", "erosion",
        "biodiversite", "poussiere", "recommandation ande",
    ]),
    ("hse", [
        "obligation hse", "suivi action", "avancement action",
        "non realise", "en cours", "action corrective",
        "levee action", "delai action",
    ]),
    ("pannes_trencher", [
        "panne", "incident engin", "trencher", "trs", "journal engin",
        "arret technique", "breakdown", "maintenance trencher",
    ]),
    ("heures_machine", [
        "heure machine", "heures machine",
        "hm", "shift", "vacation",
        "disponibilite engin", "taux disponibilite",
        "temps travail", "poste de travail",
        "heure tambour", "heures tambour", "tambour",
        "heure moteur", "heures moteur",
        "heure marche", "heures marche",
        "fonctionnement engin", "temps fonctionnement",
    ]),
    ("tombereaux", [
        "tombereau", "tombereaux", "camion benne", "benne", "activite engin",
        "engin actif", "engin travaille",
    ]),
    ("transport", [
        "transporte", "arrive port", "depart mine", "voyage camion",
        "rotation transport", "societe transport", "paa", "transport minerai",
    ]),
    ("port", [
        "navire", "chargement navire", "loading", "productivite port",
        "depart navire", "arrivee navire",
    ]),
    ("qualite", [
        "qualite", "teneur al2o3", "teneur sio2", "teneur fe2o3",
        "bauxite", "echantillon", "analyse labo", "resultat labo",
    ]),
    ("carburant", [
        "carburant", "gasoil", "diesel", "fuel", "litre",
        "consommation", "citerne", "depotage",
    ]),
    ("tonnage_excav", [
        "tonnage excave", "excavation", "creuse", "extrait",
        "volume excave", "excavation prevue",
    ]),
    ("objectifs", [
        "objectif", "prevu", "prevision", "budget", "cible",
        "planifie", "programme", "descente prevue", "excav prevue",
    ]),
    ("meta", [
        "annees disponibles", "periode disponible", "quelles annees",
        "donnees disponibles", "tables disponibles",
    ]),
    ("tonnage_descente", [
        "tonnage", "descente", "descendu", "quantite journaliere",
        "production journaliere",
    ]),
]

# Engin utilisé par défaut quand aucun engin n'est précisé
ENGIN_DEFAUT = "TRENCHER TRS N°296"


# ── Dataclass résultat ───────────────────────────────────────────────────────

@dataclass
class Intention:
    domaine:   str
    verbe:     str        = "lister"
    table:     str        = "descente_minerai"
    engin:     str | None = None
    confiance: float      = 0.5


# ── Fonctions publiques ──────────────────────────────────────────────────────

def normaliser(question: str) -> str:
    """
    Normalise une question :
    1. Minuscules + suppression accents (via _base_norm)
    2. Remplacement des synonymes miniers par leur forme canonique

    Complément de analytics.preprocess() (qui gère les abréviations
    temporelles T1/S2/…). Les deux peuvent être chaînés.
    """
    q = _base_norm(question)
    for canonical, synonymes in DICTIONNAIRE_SYNONYMES.items():
        # Remplacer du plus long au plus court pour éviter les collisions
        for syn in sorted(synonymes, key=len, reverse=True):
            if syn in q:
                q = q.replace(syn, canonical)
    return q


def detecter_intention(question: str) -> Intention:
    """
    Analyse sémantique d'une question : détecte le domaine, le verbe
    d'action, la table cible et l'engin par défaut si applicable.

    Retourne une Intention avec :
      - domaine    : catégorie métier (ex: "tonnage_descente", "pges", "document")
      - verbe      : type d'action (ex: "lister", "comparer", "analyser")
      - table      : table DuckDB cible
      - engin      : ENGIN_DEFAUT si domaine engins sans engin précisé, sinon None
      - confiance  : 0.0–1.0 (nombre de mots-clés matchés × 0.25, plafonné à 1.0)
    """
    ql = normaliser(question)

    # ── 1. Domaine ───────────────────────────────────────────────────────────
    domaine = "tonnage_descente"   # fallback
    best_score = 0

    for dom, kws in _DOMAINE_KW:
        score = sum(1 for kw in kws if kw in ql)
        if score > best_score:
            best_score = score
            domaine = dom
            if dom == "document":   # priorité absolue
                break

    confiance = min(1.0, best_score * 0.25)

    # ── 2. Verbe d'action ────────────────────────────────────────────────────
    verbe = "lister"
    for v, kws in VERBES_ACTION.items():
        if any(kw in ql for kw in kws):
            verbe = v
            break

    # ── 3. Table cible ───────────────────────────────────────────────────────
    table = DOMAINE_TABLE.get(domaine, "descente_minerai")

    # ── 4. Engin par défaut ──────────────────────────────────────────────────
    # Si le domaine concerne les engins mais qu'aucun engin spécifique n'est
    # mentionné → on assume l'engin de référence (TRENCHER TRS N°296).
    engin: str | None = None
    if domaine in ("tombereaux", "pannes_trencher"):
        engin_explicite = any(w in ql for w in [
            "tombereau", "benne", "cat n", "trencher", "trs", "chargeuse",
        ])
        if not engin_explicite:
            engin = ENGIN_DEFAUT

    return Intention(
        domaine=domaine,
        verbe=verbe,
        table=table,
        engin=engin,
        confiance=confiance,
    )
