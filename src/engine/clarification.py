"""
Gestion des questions ambiguës — Step 4 du plan d'amélioration.

Fournit :
  - CLARIFICATIONS   : dict[domaine_ambigu → message de clarification + options]
  - CONSIGNES        : conseils de formulation affichés dans l'UI
  - verifier_qualite_prompt() : détecte si une question nécessite une précision
  - ClarificationRequest     : dataclass retournée quand une clarification est utile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from src.engine.intention import normaliser, VERBES_ACTION

# ── Messages de clarification par situation ambiguë ──────────────────────────
# Clé   = identifiant de situation
# Valeur = dict avec "message" et "options" (suggestions de reformulation)
CLARIFICATIONS: dict[str, dict] = {
    "tonnage_ambigu": {
        "message": (
            "Quel type de tonnage souhaitez-vous consulter ?"
        ),
        "options": [
            "Tonnage **descendu** (mine → stock)",
            "Tonnage **excavé** (extraction terrain)",
            "Tonnage **transporté** (mine → port PAA)",
            "Tonnage **chargé** (port → navire)",
        ],
        "exemples": [
            "Tonnage descendu en 2025",
            "Tonnage excavé T1 2026",
            "Tonnage transporté par mois en 2025",
        ],
    },
    "engin_ambigu": {
        "message": (
            "De quel type d'engin parlez-vous ?"
        ),
        "options": [
            "**Tombereaux** (camions-bennes, activité quotidienne)",
            "**Trenchers** (pannes et incidents — journal)",
            "**Chargeuses** (référentiel)",
        ],
        "exemples": [
            "Quels tombereaux ont travaillé en 2025 ?",
            "Pannes du trencher TRS N°296 en 2025",
            "Liste des chargeuses actives",
        ],
    },
    "periode_manquante": {
        "message": (
            "Pour quelle période souhaitez-vous cette information ?"
        ),
        "options": [
            "Une **année** : ex. *en 2025*, *en 2026*",
            "Un **mois** : ex. *en mars 2026*",
            "Un **trimestre** : ex. *T1 2025*, *T3 2026*",
            "Un **semestre** : ex. *S1 2025*",
        ],
        "exemples": [
            "Tonnage par mois en 2025",
            "Bilan des pannes T2 2026",
            "Carburant S1 2025",
        ],
    },
    "pges_ou_hse": {
        "message": (
            "Voulez-vous consulter les actions PGES ou les obligations HSE ?"
        ),
        "options": [
            "**Actions PGES** (Plan de Gestion Environnementale et Sociale — ANDE)",
            "**Obligations HSE** (suivi interne — sécurité, santé, environnement)",
        ],
        "exemples": [
            "Actions PGES non réalisées",
            "Obligations HSE en cours",
            "Avancement action PGES n°14",
        ],
    },
    "qualite_ambigu": {
        "message": (
            "Quel indicateur de qualité souhaitez-vous ?"
        ),
        "options": [
            "**Teneur Al2O3** (alumine — objectif mine)",
            "**Teneur SiO2** (silice — impureté à minimiser)",
            "**Résultats labo** (par échantillon ou par navire)",
        ],
        "exemples": [
            "Teneur Al2O3 par mois en 2025",
            "Qualité des échantillons T1 2026",
            "Résultats labo navire dernier mois",
        ],
    },
}

# ── Conseils de formulation (affichés dans l'UI comme guide) ─────────────────
CONSIGNES: list[str] = [
    "Précisez **la période** : *en 2025*, *T1 2026*, *mars 2025*, *S2 2024*…",
    "Précisez **le type de tonnage** : descendu, excavé, transporté ou chargé.",
    "Pour les engins : mentionnez *tombereau*, *trencher* ou *chargeuse*.",
    "Pour les actions : précisez *PGES* ou *HSE* et le statut : *en cours*, *réalisé*, *non réalisé*.",
    "Pour la qualité : précisez *Al2O3*, *SiO2* ou *Fe2O3*.",
    "Les questions courtes de suivi fonctionnent : *par mois*, *en 2026*, *par engin*.",
]


# ── Dataclass résultat ───────────────────────────────────────────────────────

@dataclass
class ClarificationRequest:
    """Retourné par verifier_qualite_prompt() quand une précision est utile."""
    situation:  str              # clé dans CLARIFICATIONS
    message:    str              # question posée à l'utilisateur
    options:    list[str] = field(default_factory=list)
    exemples:   list[str] = field(default_factory=list)
    obligatoire: bool = False    # True = bloque la réponse, False = avertissement


# ── Détection d'ambiguïté ────────────────────────────────────────────────────

# Mots-clés génériques "tonnage" sans précision du type
_KW_TONNAGE_GENERIQUE = {
    "tonnage", "quantite", "production", "produit",
}
_KW_TONNAGE_PRECIS = {
    "descendu", "descend", "descente",
    "excave", "excavation", "extrait",
    "transporte", "transport", "paa",
    "charge", "chargement", "navire", "loading",
}

# Mots-clés "engin" sans précision du type
_KW_ENGIN_GENERIQUE = {"engin", "machine", "equipement", "vehicule"}
_KW_ENGIN_PRECIS   = {"tombereau", "benne", "trencher", "trs", "chargeuse", "camion"}

# Mots-clés tonnage + verbe analytique → ambiguïté haute
_KW_VERBE_CALCUL   = {"combien", "calculer", "total", "bilan", "quel est", "quelle est"}


def verifier_qualite_prompt(question: str) -> ClarificationRequest | None:
    """
    Analyse une question et retourne une ClarificationRequest si une précision
    améliorerait significativement la réponse, ou None si la question est claire.

    Situations détectées :
      1. "tonnage" sans préciser descendu/excavé/transporté/chargé
      2. "engin" sans préciser tombereau/trencher/chargeuse
      3. Période manquante sur une question de calcul
      4. "action" ou "pges" sans préciser PGES vs HSE (quand les deux sont plausibles)
      5. "qualite" sans préciser l'indicateur
    """
    ql = normaliser(question)

    # 1. Tonnage ambigu
    has_tonnage_generic = any(kw in ql for kw in _KW_TONNAGE_GENERIQUE)
    has_tonnage_precise = any(kw in ql for kw in _KW_TONNAGE_PRECIS)
    has_calcul_verb     = any(kw in ql for kw in _KW_VERBE_CALCUL)

    if has_tonnage_generic and not has_tonnage_precise and has_calcul_verb:
        c = CLARIFICATIONS["tonnage_ambigu"]
        return ClarificationRequest(
            situation="tonnage_ambigu",
            message=c["message"],
            options=c["options"],
            exemples=c["exemples"],
            obligatoire=False,   # on répond quand même avec descente (défaut)
        )

    # 2. Engin ambigu
    has_engin_generic = any(kw in ql for kw in _KW_ENGIN_GENERIQUE)
    has_engin_precise = any(kw in ql for kw in _KW_ENGIN_PRECIS)

    if has_engin_generic and not has_engin_precise:
        c = CLARIFICATIONS["engin_ambigu"]
        return ClarificationRequest(
            situation="engin_ambigu",
            message=c["message"],
            options=c["options"],
            exemples=c["exemples"],
            obligatoire=False,
        )

    # 3. Période manquante sur une question de calcul
    import re
    has_year    = bool(re.search(r"\b20\d{2}\b", ql))
    has_period  = has_year or any(w in ql for w in [
        "mois", "trimestre", "semestre", "semaine", "annee",
        "janvier", "fevrier", "mars", "avril", "mai", "juin",
        "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
    ])
    is_calcul   = any(kw in ql for kw in _KW_VERBE_CALCUL)
    is_short    = len(ql.split()) <= 5

    if is_calcul and not has_period and not is_short and has_tonnage_generic:
        c = CLARIFICATIONS["periode_manquante"]
        return ClarificationRequest(
            situation="periode_manquante",
            message=c["message"],
            options=c["options"],
            exemples=c["exemples"],
            obligatoire=False,
        )

    # 4. PGES vs HSE ambigu (les deux domaines matchent sans discriminant clair)
    has_pges_kw = any(w in ql for w in ["pges", "ande", "environnemental", "plan de gestion"])
    has_hse_kw  = any(w in ql for w in ["obligation", "hse", "avancement", "suivi action"])
    has_action  = "action" in ql

    if has_action and has_pges_kw and has_hse_kw:
        c = CLARIFICATIONS["pges_ou_hse"]
        return ClarificationRequest(
            situation="pges_ou_hse",
            message=c["message"],
            options=c["options"],
            exemples=c["exemples"],
            obligatoire=False,
        )

    # 5. Qualité ambiguë
    has_qualite = "qualite" in ql or "teneur" in ql
    has_indicateur = any(w in ql for w in ["al2o3", "sio2", "fe2o3", "alumine", "silice"])
    if has_qualite and not has_indicateur:
        c = CLARIFICATIONS["qualite_ambigu"]
        return ClarificationRequest(
            situation="qualite_ambigu",
            message=c["message"],
            options=c["options"],
            exemples=c["exemples"],
            obligatoire=False,
        )

    return None
