"""
core/clarification.py — Questions de suivi contextuelles et vérification qualité.

Fonctions publiques :
  generer_questions_suivi(clarif_type, ctx, question,
                          annees_disponibles, tables_candidates)
    → list[dict{icone, label, prompt}]  max 3 suggestions cliquables

  verifier_qualite_prompt(question)
    → list[str]  consignes non respectées (vide = prompt OK)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.nlp import analyser_question

_NOW            = datetime.now()
_ANNEE_EN_COURS = _NOW.year
_MOIS_EN_COURS  = _NOW.month
_TRIM_EN_COURS  = (_NOW.month - 1) // 3 + 1

# Domaines pour lesquels une période n'est pas nécessaire.
# PGES/HSE = actions sans filtre temporel ; documents = RAG ;
# meta = infos sur la base ; panne = liste par engin, toutes années.
_DOMAINES_SANS_PERIODE: frozenset[str] = frozenset({
    "pges", "hse", "statut", "indemnisation", "non_conformite",
    "meta", "panne",
})

# Noms lisibles des tables DuckDB → affichés dans les boutons
_TABLE_LABELS: dict[str, str] = {
    "descente_minerai":      "Tonnage descendu",
    "excavation":            "Excavation",
    "journal":               "Pannes / Journal engins",
    "carburant_citerne":     "Carburant (Petro Ivoire)",
    "transport_minerai_paa": "Transport mine→port PAA",
    "productivite_loading":  "Chargement navires",
    "pges_actions":          "Actions PGES",
    "suivi_actions":         "Obligations HSE",
    "objectifs":             "Objectifs",
    "qualite_echantillons":  "Qualité / Teneurs",
}

# Messages de contexte affichés au-dessus des boutons
MESSAGES_CLARIF: dict[str, str] = {
    "periode_manquante":  "Pour quelle période souhaitez-vous cette information ?",
    "table_ambigue":      "Plusieurs sources correspondent — choisissez la plus pertinente :",
    "domaine_inconnu":    "Je n'ai pas reconnu le domaine. Essayez l'une de ces catégories :",
    "table_introuvable":  "Les données demandées ne sont pas chargées dans la base.",
    "trop_courte":        "Question trop courte. Voici des exemples complets :",
    "question_large":     "Question large — quel domaine vous intéresse ?",
}


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ═══════════════════════════════════════════════════════════════════════════════

def generer_questions_suivi(
    clarif_type: str,
    ctx: dict,
    question: str,
    annees_disponibles: list[int] | None = None,
    tables_candidates: list[str] | None = None,
) -> list[dict]:
    """
    Génère des suggestions de suivi contextuelles selon le type de clarification.

    Paramètres :
      clarif_type        : type retourné par core/router.py
      ctx                : résultat de analyser_question()
      question           : question originale (pour construire le prompt enrichi)
      annees_disponibles : années dans la base (pour période manquante)
      tables_candidates  : tables candidates (pour table_ambigue)

    Retourne list[dict{icone, label, prompt}] — max 3 boutons.
    """
    if clarif_type == "periode_manquante":
        return _gen_periode(question, annees_disponibles)
    if clarif_type == "table_ambigue":
        return _gen_table_ambigue(question, tables_candidates, ctx)
    if clarif_type == "domaine_inconnu":
        return _gen_domaine_inconnu(ctx)
    if clarif_type == "table_introuvable":
        return _gen_table_introuvable()
    if clarif_type == "trop_courte":
        return _gen_trop_courte(ctx)
    if clarif_type == "question_large":
        return _gen_question_large(ctx)
    return []


def verifier_qualite_prompt(question: str) -> list[str]:
    """
    Vérifie 4 critères de qualité sur la question.
    Retourne la liste des consignes non respectées (strings).
    Afficher ces tips AVANT la réponse, sans bloquer si le pipeline est identifiable.

    Critères :
      1. Période précisée (année / mois / trimestre)
      2. Domaine minier reconnu
      3. Question suffisamment longue (≥ 3 mots)
      4. Une seule question à la fois
    """
    ctx      = analyser_question(question)
    domaines = set(ctx["domaines"])
    echecs   = []

    # 1. Période — uniquement pour les domaines qui en ont besoin.
    #    PGES, HSE, documents et statut n'ont pas besoin de période.
    p = ctx["periode"]
    periode_present = bool(p["annee"] or p["mois"] or p["trimestre"] or p["semestre"])
    domaines_sans_periode = domaines & _DOMAINES_SANS_PERIODE
    domaines_avec_periode = domaines - _DOMAINES_SANS_PERIODE
    if domaines_avec_periode and not periode_present:
        echecs.append(
            "Précisez **la période** : *en 2025*, *T1 2026*, *mars 2025*, *S1 2024*…"
        )

    # 2. Domaine — seulement si aucun domaine identifié (question vraiment opaque).
    if not domaines:
        echecs.append(
            "Domaine non reconnu — reformulez en citant un sujet minier. "
            "Exemples : *« Tonnage par mois en 2024 »*, "
            "*« Bilan des pannes en 2023 »*, *« Carburant par engin en 2024 »*."
        )

    # 3. Longueur — utiliser les mots de la question originale car la normalisation
    #    peut contracter des expressions multi-mots ("taux accomplissement" → "objectif").
    if len(question.split()) < 3:
        echecs.append(
            "La question est **trop courte**. Ajoutez un sujet, une période et un détail."
        )

    # 4. Multi-questions (heuristique conservative : 2 "?" ou virgule dans une longue phrase)
    if ctx["multi_questions"]:
        echecs.append(
            "Posez **une seule question** à la fois pour une réponse plus précise."
        )

    return echecs


# ═══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATEURS CONTEXTUELS
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_periode(question: str, annees: list[int] | None) -> list[dict]:
    """Reprend la question + propose les 2 années les plus récentes + trimestre courant."""
    _last = max(annees) if annees else _ANNEE_EN_COURS - 1
    _prev = _last - 1
    return [
        {
            "icone": "📅",
            "label": f"Toute l'année {_last}",
            "prompt": f"{question} en {_last}",
        },
        {
            "icone": "📅",
            "label": f"Toute l'année {_prev}",
            "prompt": f"{question} en {_prev}",
        },
        {
            "icone": "📅",
            "label": f"T{_TRIM_EN_COURS} {_ANNEE_EN_COURS}",
            "prompt": f"{question} T{_TRIM_EN_COURS} {_ANNEE_EN_COURS}",
        },
    ]


def _gen_table_ambigue(question: str, tables: list[str] | None, ctx: dict | None = None) -> list[dict]:
    """Propose une option cliquable par table candidate (max 3)."""
    if not tables:
        return _gen_domaine_inconnu(ctx)
    result = []
    for t in tables[:3]:
        label = _TABLE_LABELS.get(t, t.replace("_", " ").title())
        result.append({
            "icone": "📊",
            "label": label,
            "prompt": f"{question} (données : {label})",
        })
    return result


def _gen_domaine_inconnu(ctx: dict | None = None) -> list[dict]:
    """Propose les 3 catégories principales du BI minier, en utilisant l'année détectée."""
    _annee = (ctx or {}).get("periode", {}).get("annee") or _ANNEE_EN_COURS
    return [
        {
            "icone": "📦",
            "label": "Production / Tonnage",
            "prompt": f"Tonnage descendu par mois en {_annee}",
        },
        {
            "icone": "⚠️",
            "label": "Engins / Pannes",
            "prompt": "Bilan des pannes en 2023",
        },
        {
            "icone": "📋",
            "label": "PGES / HSE",
            "prompt": "Actions PGES non réalisées",
        },
    ]


def _gen_question_large(ctx: dict | None = None) -> list[dict]:
    """4 domaines principaux avec l'année détectée — pour les questions bilan/résumé/analyse."""
    _annee = (ctx or {}).get("periode", {}).get("annee") or _ANNEE_EN_COURS
    return [
        {
            "icone": "📦",
            "label": f"Production {_annee}",
            "prompt": f"Tonnage descendu par mois en {_annee}",
        },
        {
            "icone": "⚡",
            "label": f"Carburant {_annee}",
            "prompt": f"Consommation carburant par engin en {_annee}",
        },
        {
            "icone": "⚠️",
            "label": f"Pannes {_annee}",
            "prompt": f"Bilan des pannes en {_annee}",
        },
        {
            "icone": "🎯",
            "label": f"Objectifs {_annee}",
            "prompt": f"Taux de réalisation des objectifs en {_annee}",
        },
    ]


def _gen_table_introuvable() -> list[dict]:
    """Données non chargées → invite à uploader ou poser une autre question."""
    return [
        {
            "icone": "📦",
            "label": f"Tonnage {_ANNEE_EN_COURS}",
            "prompt": f"Tonnage descendu par mois en {_ANNEE_EN_COURS}",
        },
        {
            "icone": "📊",
            "label": "Données disponibles",
            "prompt": "Quelles données sont disponibles ?",
        },
    ]


def _gen_trop_courte(ctx: dict | None = None) -> list[dict]:
    """3 exemples complets et cliquables représentant les 3 domaines principaux."""
    _annee = (ctx or {}).get("periode", {}).get("annee") or _ANNEE_EN_COURS
    return [
        {
            "icone": "📦",
            "label": f"Tonnage {_annee}",
            "prompt": f"Tonnage descendu par mois en {_annee}",
        },
        {
            "icone": "⚠️",
            "label": "Pannes 2023",
            "prompt": "Bilan des pannes en 2023",
        },
        {
            "icone": "🛢️",
            "label": "Carburant 2024",
            "prompt": "Carburant par engin en 2024",
        },
    ]
