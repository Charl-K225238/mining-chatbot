"""
core/router.py — Routeur intelligent avec détection d'ambiguïté.

Principe :
  Avant toute réponse, analyse la question pour identifier :
  - Le domaine métier (table DuckDB cible)
  - L'intention (lister / compter / comparer / analyser…)
  - La période (annee / mois / trimestre)
  - Si une clarification est nécessaire (et laquelle)

Fonction principale :
  router(question, tables_disponibles) → dict
    pipeline       : "analytique" | "llm" | "hybride" | "clarification"
    table          : str | None
    filtre         : dict  {annee, mois, trimestre, semestre}
    intention      : str
    clarif_type    : str | None
    questions_suivi: list[dict]  [{icone, label, prompt}]
    ctx            : dict  (résultat analyser_question)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.nlp import analyser_question

logger = logging.getLogger(__name__)

def _annee_en_cours() -> int:
    return datetime.now().year

def _mois_en_cours() -> int:
    return datetime.now().month

def _trim_en_cours() -> int:
    return (datetime.now().month - 1) // 3 + 1


# ═══════════════════════════════════════════════════════════════════════════════
# MAPPING DOMAINE → TABLE DUCKDB
# ═══════════════════════════════════════════════════════════════════════════════

DOMAINE_TABLE: dict[str, str | None] = {
    # Tonnage / production
    "tonnage":        "descente_minerai",
    "objectif":       "descente_minerai",
    "excavation":     "excavation",
    # Engins — tombereaux ET pannes sont dans descente_minerai (colonne OBSERVATION)
    # analytics.py/handle_observations() et handle_engins() interrogent cette table.
    # La table "journal" (trenchers spécialisés) est utilisée en fallback si elle existe.
    "tombereau":      "descente_minerai",
    "utilisation":    "descente_minerai",
    "engin":          "descente_minerai",
    "panne":          "descente_minerai",
    # Engins lourds spécialisés → journal si disponible, sinon descente_minerai en fallback
    "pelle":          "journal",
    "foreuse":        "journal",
    "bouteur":        "journal",
    # Flux physique
    "carburant":      "carburant_citerne",
    "transport":      "transport_minerai_paa",
    "navire":         "productivite_loading",
    # Qualité
    "qualite":        "qualite_echantillons",
    # Actions / conformité
    "pges":           "pges_actions",
    "hse":            "suivi_actions",
    "statut":         "suivi_actions",
    "indemnisation":  "pges_actions",
    # Heures machine (shifts)
    "heures_machine": "shifts_horaires",
    # Méta (info sur les données) — pas de table unique → analytics handle_metadata
    "meta":           "descente_minerai",
    # Documents (pas de table DuckDB → RAG + LLM)
    "non_conformite": None,
}

# Domaines qui nécessitent une période explicite pour une réponse pertinente.
# Exclus : PGES/HSE (actions sans filtre temps), meta (info dataset), engin seul.
NECESSITE_PERIODE: set[str] = {
    "tonnage", "excavation", "carburant",
    "tombereau", "utilisation",
    "pelle", "transport", "navire",
    "objectif", "qualite", "heures_machine",
    # "panne" exclu : un bilan pannes par engin a du sens sans filtrer par année
}


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════

def router(
    question: str,
    tables_disponibles: list[str] | None = None,
) -> dict:
    """
    Analyse une question et retourne une décision de routing.

    tables_disponibles : liste des tables chargées dans DuckDB
      (passée depuis la page pour filtrer les tables absentes).

    Retourne un dict :
      pipeline        "analytique" | "llm" | "hybride" | "clarification"
      table           table DuckDB cible (str ou None)
      filtre          {annee, mois, trimestre, semestre}
      intention       verbe d'action principal
      clarif_type     type de clarification demandée (None = pas de clarif)
      questions_suivi [{icone, label, prompt}]  — boutons contextuels
      ctx             résultat complet de analyser_question()
    """
    try:
        return _router_interne(question, tables_disponibles)
    except Exception as exc:
        logger.warning("router() exception sur %r : %s", question, exc)
        # Fallback sûr : laisser passer vers analytics
        return _defaut(question, {})


def _router_interne(question: str, tables_disponibles: list[str] | None) -> dict:
    ctx        = analyser_question(question)
    domaines   = ctx["domaines"]
    intentions = ctx["intentions"]
    periode    = ctx["periode"]
    nb_mots    = ctx["nb_mots"]

    # ── 1. Question trop courte ET aucun domaine identifiable ────────────────
    # (nb_mots < 3 avec un domaine connu → on continue vers "période manquante")
    if nb_mots < 3 and not domaines:
        return _clarif("trop_courte", ctx, _suivi_trop_courte(question))

    # ── 2. Domaine inconnu ────────────────────────────────────────────────────
    if not domaines:
        # Intention purement LLM → RAG direct
        if any(i in intentions for i in ("analyser", "prioriser", "resumer", "verifier")):
            return _llm(ctx, intentions[0] if intentions else "analyser")
        return _clarif("domaine_inconnu", ctx, _suivi_domaine_inconnu(question))

    # ── 3. Résoudre les tables ────────────────────────────────────────────────
    tables_resolues = _resoudre_tables(domaines, tables_disponibles)

    # ── 4. Table introuvable dans la base chargée ────────────────────────────
    if not tables_resolues:
        return _clarif("table_introuvable", ctx, _suivi_table_introuvable())

    # ── 5. Lever l'ambiguïté entre plusieurs tables ──────────────────────────
    if len(tables_resolues) > 1:
        resolved = _lever_ambiguite(tables_resolues, domaines, intentions, ctx)
        if resolved is not None:
            tables_resolues = [resolved]
        else:
            # Ambiguïté non levable → clarif table_ambigue (non-bloquant : on continue
            # avec la première table mais on propose des alternatives)
            _candidates = [t for t in tables_resolues if t is not None]
            tables_resolues = tables_resolues[:1]
            if _candidates:
                return {
                    "pipeline":         "analytique",
                    "table":            tables_resolues[0],
                    "filtre":           _construire_filtre(ctx),
                    "intention":        intentions[0] if intentions else "lister",
                    "clarif_type":      "table_ambigue",
                    "questions_suivi":  [],   # rempli par generer_questions_suivi() dans la page
                    "tables_candidates": _candidates,
                    "ctx":              ctx,
                }

    table = tables_resolues[0]

    # ── 6. Table None → documents → LLM ─────────────────────────────────────
    if table is None:
        return _llm(ctx, intentions[0] if intentions else "analyser")

    # ── 7. Période manquante sur une question temporelle ────────────────────
    has_period = bool(
        periode["annee"] or periode["mois"]
        or periode["trimestre"] or periode["semestre"]
    )
    needs_period = bool(set(domaines) & NECESSITE_PERIODE)

    if needs_period and not has_period:
        # Non-bloquant : analytics tente sur toutes périodes + suggestions affichées
        return {
            "pipeline":          "analytique",
            "table":             table,
            "filtre":            _construire_filtre(ctx),
            "intention":         intentions[0] if intentions else "lister",
            "clarif_type":       "periode_manquante",
            "questions_suivi":   _suivi_periode_manquante(question),
            "tables_candidates": [],
            "ctx":               ctx,
        }

    # ── 8. Intention d'analyse → pipeline hybride (analytics + LLM) ─────────
    if any(i in intentions for i in ("analyser", "prioriser")):
        return {
            "pipeline":          "hybride",
            "table":             table,
            "filtre":            _construire_filtre(ctx),
            "intention":         intentions[0],
            "clarif_type":       None,
            "questions_suivi":   [],
            "tables_candidates": [],
            "ctx":               ctx,
        }

    # ── 9. Défaut → analytique ────────────────────────────────────────────────
    return {
        "pipeline":          "analytique",
        "table":             table,
        "filtre":            _construire_filtre(ctx),
        "intention":         intentions[0] if intentions else "lister",
        "clarif_type":       None,
        "questions_suivi":   [],
        "tables_candidates": [],
        "ctx":               ctx,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNES
# ═══════════════════════════════════════════════════════════════════════════════

def _resoudre_tables(
    domaines: list[str],
    tables_disponibles: list[str] | None,
) -> list[str | None]:
    """Mappe les domaines vers les tables DuckDB, déduplique et filtre absentes."""
    seen: set = set()
    result: list[str | None] = []
    for dom in domaines:
        t   = DOMAINE_TABLE.get(dom)
        key = t if t is not None else "__llm__"
        if key in seen:
            continue
        seen.add(key)
        # Vérifier que la table est chargée (None = LLM, toujours accepté)
        if t is None or tables_disponibles is None or t in tables_disponibles:
            result.append(t)
    return result


def _lever_ambiguite(
    tables: list[str | None],
    domaines: list[str],
    intentions: list[str],
    ctx: dict,
) -> str | None:
    """
    Applique les règles de priorité pour lever une ambiguïté.
    Retourne la table résolue ou None si impossible.
    """
    # non_conformite (document) présent → LLM gagne toujours (retourne None)
    if "non_conformite" in domaines and None in tables:
        return None
    # pges explicitement mentionné → pges_actions prioritaire sur suivi_actions
    if "pges" in domaines and "pges_actions" in tables:
        return "pges_actions"
    # excavation explicite → excavation table prioritaire sur descente_minerai
    if "excavation" in domaines and "excavation" in tables:
        return "excavation"
    # navire → productivite_loading prioritaire sur descente_minerai
    if "navire" in domaines and "productivite_loading" in tables:
        return "productivite_loading"
    # "compter" + "utilisation" → activité engins → descente_minerai
    if "compter" in intentions and "utilisation" in domaines:
        return "descente_minerai"
    # "statut" seul (sans pges/hse) → suivi_actions
    if "statut" in domaines and "suivi_actions" in tables:
        return "suivi_actions"
    # carburant → citerne (si ambigu avec autre table)
    if "carburant" in domaines and "carburant_citerne" in tables:
        return "carburant_citerne"
    # transport + tonnage → transport_minerai_paa
    if "transport" in domaines and "transport_minerai_paa" in tables:
        return "transport_minerai_paa"
    # panne seule → journal
    if "panne" in domaines and "journal" in tables:
        return "journal"
    return None


def _construire_filtre(ctx: dict) -> dict:
    """Extrait les filtres temporels du contexte de la question."""
    p = ctx["periode"]
    return {
        "annee":     p.get("annee"),
        "mois":      p.get("mois"),
        "trimestre": p.get("trimestre"),
        "semestre":  p.get("semestre"),
    }


# ── Constructeurs de résultats ────────────────────────────────────────────────

def _clarif(clarif_type: str, ctx: dict, suivi: list[dict]) -> dict:
    return {
        "pipeline":          "clarification",
        "table":             None,
        "filtre":            {},
        "intention":         "lister",
        "clarif_type":       clarif_type,
        "questions_suivi":   suivi,
        "tables_candidates": [],
        "ctx":               ctx,
    }


def _llm(ctx: dict, intention: str) -> dict:
    return {
        "pipeline":          "llm",
        "table":             None,
        "filtre":            {},
        "intention":         intention,
        "clarif_type":       None,
        "questions_suivi":   [],
        "tables_candidates": [],
        "ctx":               ctx,
    }


def _defaut(question: str, ctx: dict) -> dict:
    return {
        "pipeline":          "analytique",
        "table":             None,
        "filtre":            {},
        "intention":         "lister",
        "clarif_type":       None,
        "questions_suivi":   [],
        "tables_candidates": [],
        "ctx":               ctx,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATEURS DE QUESTIONS DE SUIVI (stub — renforcé à l'Étape 4)
# ═══════════════════════════════════════════════════════════════════════════════

def _suivi_periode_manquante(question: str) -> list[dict]:
    """Propose des versions de la question avec une période précise."""
    annee = _annee_en_cours()
    trim  = _trim_en_cours()
    return [
        {
            "icone": "📅",
            "label": f"En {annee}",
            "prompt": f"{question} en {annee}",
        },
        {
            "icone": "📅",
            "label": f"En {annee - 1}",
            "prompt": f"{question} en {annee - 1}",
        },
        {
            "icone": "📅",
            "label": f"T{trim} {annee}",
            "prompt": f"{question} T{trim} {annee}",
        },
    ]


def _suivi_domaine_inconnu(question: str) -> list[dict]:
    """Propose 3 catégories principales quand le domaine est inconnu."""
    annee = _annee_en_cours()
    return [
        {
            "icone": "📦",
            "label": "Production / Tonnage",
            "prompt": f"Tonnage descendu par mois en {annee}",
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


def _suivi_trop_courte(question: str) -> list[dict]:
    """Rappelle les formulations complètes recommandées."""
    annee = _annee_en_cours()
    return [
        {
            "icone": "📦",
            "label": f"Tonnage {annee}",
            "prompt": f"Tonnage descendu par mois en {annee}",
        },
        {
            "icone": "⚠️",
            "label": "Pannes 2023",
            "prompt": "Bilan des pannes en 2023",
        },
        {
            "icone": "🛢️",
            "label": "Carburant 2024",
            "prompt": "Carburant par mois en 2024",
        },
    ]


def _suivi_table_introuvable() -> list[dict]:
    """Indique que la donnée demandée n'est pas chargée."""
    annee = _annee_en_cours()
    return [
        {
            "icone": "📊",
            "label": "Données disponibles",
            "prompt": "Quelles données sont disponibles ?",
        },
        {
            "icone": "📦",
            "label": f"Tonnage {annee}",
            "prompt": f"Tonnage descendu en {annee}",
        },
    ]
