"""
Routeur de requêtes — orchestre le moteur analytique et le RAG BM25.

Cascade gérée par router_question() :
  0. Intent "document"   → RAG+LLM direct (bypass analytics)
  1. Moteur analytique   → DuckDB SQL (réponse précise, instantanée)
  2. Question de suivi   → ré-essai avec contexte question précédente
  3. RAG BM25 + LLM      → documents pertinents → contexte Ollama
  4. Garde-fou           → _NO_ANSWER si aucun contexte trouvé

Le mode LLM (factuel / synthese / analyse) est déduit du verbe
d'intention via _intent_to_llm_mode() pour des réponses plus précises.
"""

import logging
import re
import sys
from datetime import date as _date
from pathlib import Path
from typing import Iterator

import duckdb

# Assurer que ROOT est accessible pour importer core/
_ROOT = Path(__file__).parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.db.connection import get_db
from src.engine import analytics
from src.engine.intention import detecter_intention
from src.rag.index import BM25Index, get_index
from src.rag.retriever import retrieve
from src.utils.text import norm
from config.settings import PRIMARY_MODEL, FALLBACK_MODEL

from core import ollama_client

logger = logging.getLogger(__name__)

# ── Détection questions générales ──────────────────────────────────────────────

_MINING_KEYWORDS = {
    "tonnage", "engin", "panne", "shift", "carburant", "excavation",
    "tombereau", "trencher", "minerai", "production", "objectif",
    "transport", "navire", "qualite", "pges", "hse", "heures", "machine",
    "camion", "chargement", "pompe", "bulldozer", "pelle", "foreuse",
    "bouteur", "descente", "observation", "journal", "stock",
}

_GENERAL_KEYWORDS = {
    "bonjour", "bonsoir", "salut", "merci", "au revoir", "ciao",
    "aujourd'hui", "météo", "meteo", "heure", "horloge",
    "définition", "definition", "explique", "expliques",
    "hier", "demain", "calendrier",
    "comment allez", "comment vas", "comment ca va",
    "bonne journee", "bonne semaine", "bonne nuit",
    "que signifie", "kesako", "c est quoi",
}

# Noms de jours — utiles pour les questions de calendrier ("lundi dernier", "samedi prochain")
_DAY_NAMES = {
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
}

# Mots-clés d'expertise industrielle (normalisés, sans accents)
# Permettent de détecter des questions sur les normes, standards, bonnes pratiques
# que le LLM peut répondre depuis sa formation, sans base de données.
_EXPERT_KEYWORDS = {
    "standard", "standards", "referentiel", "referentiels",
    "norme", "normes", "certification", "certifications",
    "concurrentiel", "concurrentiels", "benchmark",
    "iso", "ohsas", "icmm", "irma", "eiti",
    "accreditation", "label", "homologation",
    "recommandation", "recommandations", "preconise", "preconiser",
    "reglementation", "reglementaire",
    "bonnes pratiques", "bonne pratique", "meilleure pratique", "meilleures pratiques",
    "methodologie", "due diligence",
    # Impact / risque / gestion
    "impact environnemental", "risque environnemental", "evaluation impact",
    "plan de fermeture", "rehabilitation site",
    "mitigation", "compensation communautaire",
    "gestion des risques", "gestion risque", "analyse risque", "analyse des risques",
    "risques hse", "risques sst", "risques operationnels",
    # Gouvernance
    "gouvernance", "parties prenantes", "consultation communautaire",
    "transparence", "responsabilite sociale", "rse",
    # Qualité management
    "management qualite", "plan qualite", "amelioration continue",
    "indicateur performance", "kpi minier",
}

# Mots strictement liés aux données numériques du site (bloquent le mode expert).
# Distinct de _MINING_KEYWORDS : exclut les domaines organisationnels (hse, pges)
# qui peuvent aussi faire l'objet de questions d'expertise industrielle.
_DATA_KEYWORDS = {
    "tonnage", "panne", "shift", "carburant", "excavation",
    "tombereau", "trencher", "minerai", "production", "objectif",
    "transport", "navire", "heures", "machine", "camion", "chargement",
    "pompe", "bulldozer", "pelle", "foreuse", "bouteur", "descente", "stock",
}

# Mots-clés calculatrice (normalisés, sans accents)
_MATH_KEYWORDS = {
    "calcule", "calculer", "calcul de",
    "combien font", "combien fait", "combien vaut", "combien de fois",
    "racine carree", "racine cubique", "racine de",
    "logarithme", "factorielle",
    "cagr", "taux de croissance annuel", "taux annualise",
    "taux de rendement interne",  # "taux de rendement" seul retiré (ambigu avec rendement minier)
    "convertir", "conversion de",
    "pourcentage de", "% de",
    "multiplie par", "additionne", "soustrait",
    # Formulations verbales de calcul
    "divise par", "diviser par", "divisé par",
    "a la puissance", "exposant",  # "puissance de" retiré (terme minier ambigu)
    "en combien de jours", "en combien de temps",
    "combien de jours reste", "combien d'heures reste", "combien d'heures faut",
    "si j'ai", "si tu as", "si on a",
    "par jour il reste", "par heure il reste",
    "au bout de combien",
    # Formules financières — formes précises uniquement (pas "van" ou "roi" seuls)
    "valeur actuelle nette",
    "retour sur investissement", "calcul roi",
}

# Expressions arithmétiques directes : "125 + 48", "3 × 5 = ?", "12^3", "15% de 3500"
_MATH_EXPR = re.compile(
    r"\d+\s*[+\-×÷*/^]\s*\d+"                   # opérateur entre deux nombres
    r"|\d+\s*%\s+de\s+\d+"                       # X% de Y
    r"|\d+\s*\^\s*\d+"                           # puissance n^k
    r"|\d+\s*(?:[ée]\s+)?(?:a\s+la\s+)?puissance\s+\d"  # "2 à la puissance 10" / "2 puissance 10"
    r"|divis[eée]s?\s+\d+\s+par\s+\d+"           # "divise(s) 3600 par 24"
    r"|\d+\s+divis[eée]s?\s+par\s+\d+"           # "3600 divise par 24"
    r"|\d+L?\s+(?:et\s+)?d[eé]pense[sz]?\s+\d"  # "10L et dépense 1.5L/jour"
    r"|multipli[eé]s?\s+\d+\s+par\s+\d+"         # "multiplie 25 par 4"
    r"|\d+\s+par\s+(?:jour|heure|semaine|mois)"  # "1.5 par jour" (contexte durée)
    r"|\bsi\s+j['’\s]ai\s+\d",               # "si j'ai 10L..." (apostrophe ou espace)
    re.IGNORECASE,
)

_GENERAL_PATTERNS = re.compile(
    r"^(quelle?s?\s+est\b|quelle?s?\s+sont\b|c'est\s+quoi\b|qu'est[- ]ce\s+que\b|"
    r"comment\s+\w+|pourquoi\s+\w+|quand\s+\w+|qui\s+est\b|"
    r"que\s+veut\s+dire\b|kesako\b|à\s+quelle\s+date\b|"
    r"qu'est[- ]ce\s+qu'|c'est\s+quoi\b|signifie\b)",
    re.IGNORECASE,
)


_DEFINITION_TRIGGERS = {
    "que signifie", "c'est quoi", "qu'est-ce que", "definition de",
    "signifie quoi", "veut dire", "qu est-ce que", "kesako",
    "c est quoi", "que veut dire",
}


def _is_general_question(question: str) -> bool:
    """
    Retourne True si la question est hors-domaine minier (date, météo, salutation,
    définition générale…) et peut être traitée directement par le LLM en mode conversationnel.
    Ne couvre PAS les questions d'expertise industrielle (voir _is_expert_question).

    Les demandes de définition ("que signifie PGES ?") passent en mode général
    même si elles contiennent un terme métier, car l'utilisateur cherche une explication.
    """
    q_lower = question.lower()
    # Demandes de définition → toujours général (avant blocage mining)
    if any(trigger in q_lower for trigger in _DEFINITION_TRIGGERS):
        return True
    # Présence d'un mot-clé métier → pas général
    if any(kw in q_lower for kw in _MINING_KEYWORDS):
        return False
    # Mot-clé général explicite → général
    if any(kw in q_lower for kw in _GENERAL_KEYWORDS):
        return True
    # Nom de jour de semaine → question calendaire → général
    if any(day in q_lower for day in _DAY_NAMES):
        return True
    # Question courte (< 100 chars) avec pattern interrogatif → général
    if len(question) < 100 and _GENERAL_PATTERNS.search(question):
        return True
    return False


def _is_math_question(question: str) -> bool:
    """
    Retourne True si la question est un calcul mathématique autonome :
    arithmétique, conversion d'unités, formules financières (CAGR, ROI…),
    opérations algébriques, pourcentages avec valeurs explicites.

    N'est PAS bloqué par _DATA_KEYWORDS : l'utilisateur peut fournir
    ses propres chiffres (ex: CAGR si tonnage passe de 1200 à 1850).
    """
    q_norm = norm(question)
    # Mot-clé calculatrice explicite
    if any(kw in q_norm for kw in _MATH_KEYWORDS):
        return True
    # Expression arithmétique directe dans la question
    if _MATH_EXPR.search(question):
        return True
    return False


def _is_expert_question(question: str) -> bool:
    """
    Retourne True si la question porte sur des standards, normes, référentiels,
    bonnes pratiques ou réglementation industrielle — sans données spécifiques au site.
    Le LLM répond depuis ses connaissances de formation (mode expert).

    Utilise _DATA_KEYWORDS (pas _MINING_KEYWORDS) pour bloquer uniquement les questions
    sur des données chiffrées du site, tout en laissant passer les questions d'expertise
    sur des domaines organisationnels comme HSE, PGES, qualité.
    """
    q_lower = question.lower()
    # Données chiffrées du site → analytique, pas expert
    if any(kw in q_lower for kw in _DATA_KEYWORDS):
        return False
    q_norm = norm(question)
    return any(kw in q_norm for kw in _EXPERT_KEYWORDS)

_bm25_index: BM25Index | None = None


def _to_str(result) -> str | None:
    """Extrait le texte brut d'un résultat analytics.handle().

    analytics.handle() peut retourner str, GenericHandlerResult, ou None.
    Dans query_router le résultat est toujours utilisé comme texte brut —
    les métadonnées enrichies (questions_suivi, limit_notice) appartiennent
    à la couche Streamlit (pages/1_Assistant.py).
    """
    if result is None:
        return None
    return result.response if hasattr(result, "response") else result

_EXAMPLES = (
    "Exemples :\n"
    "  • Tonnage par mois en 2025\n"
    "  • Comparer 2024 et 2025\n"
    "  • Bilan des pannes 2026\n"
    "  • Qui est le responsable du site en 2026 ?"
)

_NO_ANSWER = (
    "Je n'ai pas trouvé d'information correspondant à cette question "
    "dans les données disponibles.\n\n"
    "**Essayez** en précisant :\n"
    "- La période : *en 2025*, *en 2026*, *au T1 2025*…\n"
    "- Le domaine : *tonnage*, *pannes*, *engins*, *transport*…\n\n"
    f"{_EXAMPLES}"
)


def _get_index(con: duckdb.DuckDBPyConnection) -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = get_index(con)
    return _bm25_index


def _intent_to_llm_mode(verbe: str) -> str:
    """Traduit le verbe d'intention en mode LLM (factuel / synthese / analyse)."""
    return {
        "analyser":  "analyse",
        "prioriser": "analyse",
        "resumer":   "synthese",
        "lister":    "synthese",
        "comparer":  "synthese",
        "calculer":  "factuel",
    }.get(verbe, "auto")


def router_question(
    question: str,
    con: duckdb.DuckDBPyConnection,
    index: BM25Index,
    prev_question: str | None = None,
) -> str | None:
    """
    Route une question vers le bon moteur et retourne la réponse.

    Retourne None si aucune source n'a pu répondre (l'appelant affiche _NO_ANSWER).
    """
    intent = detecter_intention(question)
    llm_mode = _intent_to_llm_mode(intent.verbe)

    # 0. Documents / rapports uploadés → RAG+LLM direct (bypass analytics)
    if intent.domaine == "document":
        rag_context = retrieve(question, index)
        if rag_context:
            response = _handle_rag_sync(rag_context, question, llm_mode)
            return analytics._src(response, "observations / journal / PGES")
        return None

    # 1. Moteur analytique DuckDB
    answer = _to_str(analytics.handle(con, question))
    if answer:
        return answer

    # 2. Question de suivi courte (ex: "en 2026", "par mois")
    if prev_question and _is_followup(question):
        answer = _to_str(analytics.handle(con, f"{prev_question} {question}"))
        if answer:
            return answer

    # 3. RAG BM25 + LLM
    rag_context = retrieve(question, index)
    if rag_context:
        response = ollama_client.ask(question, rag_context, mode=llm_mode)
        return analytics._src(response, "observations / journal / PGES")

    return None


def router_question_stream(
    question: str,
    con: duckdb.DuckDBPyConnection,
    index: BM25Index,
    prev_question: str | None = None,
) -> Iterator[str]:
    """Version streaming de router_question() pour Streamlit."""
    intent = detecter_intention(question)
    llm_mode = _intent_to_llm_mode(intent.verbe)

    # 0. Documents → RAG+LLM direct
    if intent.domaine == "document":
        rag_context = retrieve(question, index)
        if rag_context:
            yield from _handle_rag_stream(rag_context, question, llm_mode, FALLBACK_MODEL)
        else:
            yield _NO_ANSWER
        return

    # 1. Moteur analytique
    answer = _to_str(analytics.handle(con, question))
    if answer:
        yield answer
        return

    # 2. Question de suivi
    if prev_question and _is_followup(question):
        answer = _to_str(analytics.handle(con, f"{prev_question} {question}"))
        if answer:
            yield answer
            return

    # 3. RAG + LLM
    rag_context = retrieve(question, index)
    if rag_context:
        yield from _handle_rag_stream(rag_context, question, llm_mode, FALLBACK_MODEL)
    else:
        yield _NO_ANSWER


def ask(question: str, use_llm: bool = True,
        prev_question: str | None = None) -> str:
    """Répond à une question BI minière (version bloquante)."""
    con = get_db()
    index = _get_index(con)
    result = router_question(question, con, index, prev_question)
    if result:
        return result
    if use_llm:
        return _NO_ANSWER
    return f"Je n'ai pas pu répondre à cette question.\n\n{_EXAMPLES}"


def ask_stream(question: str,
               prev_question: str | None = None) -> Iterator[str]:
    """Version streaming pour Streamlit."""
    con = get_db()
    index = _get_index(con)
    yield from router_question_stream(question, con, index, prev_question)


_GUIDANCE_PREFIX = "__NO_DOC_GUIDANCE__:"


def _handle_rag_stream(
    rag_context: str,
    question: str,
    llm_mode: str,
    model: str,
) -> Iterator[str]:
    """
    Génère les tokens d'une réponse RAG :
    - Guidance "no doc" → yield le message directement (pas de LLM)
    - Contexte normal → stream Ollama
    """
    if rag_context.startswith(_GUIDANCE_PREFIX):
        yield rag_context[len(_GUIDANCE_PREFIX):]
        return
    yield from ollama_client.appeler_ollama(
        question, context=rag_context, modele=model, mode=llm_mode, stream=True,
    )


def _handle_rag_sync(
    rag_context: str,
    question: str,
    llm_mode: str,
) -> str:
    """Version bloquante de _handle_rag_stream (pour router_question non-streaming)."""
    if rag_context.startswith(_GUIDANCE_PREFIX):
        return rag_context[len(_GUIDANCE_PREFIX):]
    return ollama_client.ask(question, rag_context, mode=llm_mode)


def ask_fast_stream(question: str, prev_question: str | None = None) -> Iterator[str]:
    """
    Version rapide de ask_stream — utilise FALLBACK_MODEL pour la réponse LLM.
    Évite les timeouts sur le pipeline LLM (documents, hybride, domaine inconnu).
    """
    con   = get_db()
    index = _get_index(con)
    from src.engine.intention import detecter_intention
    from src.rag.retriever import retrieve

    intent   = detecter_intention(question)
    llm_mode = _intent_to_llm_mode(intent.verbe)

    if intent.domaine == "document":
        rag_context = retrieve(question, index)
        if rag_context:
            yield from _handle_rag_stream(rag_context, question, llm_mode, FALLBACK_MODEL)
        else:
            yield _NO_ANSWER
        return

    answer = _to_str(analytics.handle(con, question))
    if answer:
        yield answer
        return

    if prev_question and _is_followup(question):
        answer = _to_str(analytics.handle(con, f"{prev_question} {question}"))
        if answer:
            yield answer
            return

    rag_context = retrieve(question, index)
    if rag_context:
        yield from _handle_rag_stream(rag_context, question, llm_mode, FALLBACK_MODEL)
    else:
        yield _NO_ANSWER


def ask_math_stream(question: str) -> Iterator[str]:
    """Route un calcul mathématique directement vers le LLM en mode calculatrice."""
    yield from ollama_client.appeler_ollama(
        question,
        context="",
        modele=FALLBACK_MODEL,
        mode="math",
        stream=True,
    )


def ask_expert_stream(question: str) -> Iterator[str]:
    """Route une question d'expertise industrielle vers le LLM en mode expert (sans contexte BI).
    Utilise le modèle primaire pour une meilleure qualité sur les normes ISO/IRMA/ICMM."""
    yield from ollama_client.appeler_ollama(
        question,
        context="",
        modele=PRIMARY_MODEL,
        mode="expert",
        stream=True,
    )


_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS_FR  = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def ask_general_stream(question: str) -> Iterator[str]:
    """Route une question générale directement vers le LLM sans contexte BI.

    La date du jour est injectée en tête du message pour les calculs calendaires.
    """
    _today    = _date.today()
    _date_ctx = (
        f"[Date du jour : {_JOURS_FR[_today.weekday()]} "
        f"{_today.day} {_MOIS_FR[_today.month - 1]} {_today.year}]"
    )
    yield from ollama_client.appeler_ollama(
        f"{_date_ctx}\n\n{question}",
        context="",
        modele=FALLBACK_MODEL,
        mode="libre",
        stream=True,
    )


def _is_followup(question: str) -> bool:
    """
    Détecte une question de suivi courte qui affine la question précédente.

    Catégories reconnues :
      1. Temporel     : "en 2026", "en avril", "S1-S6", "trimestre 3"
      2. Granularité  : "par mois", "par semaine", "par engin"
      3. Type/sujet   : "de direction", "de pneu", "excavation"
      4. Combiné      : "de direction en 2023", "par mois en 2026"
    """
    q = norm(question).strip("?.! \t")
    if not q or len(q) > 60:
        return False
    # Retirer un éventuel qualificatif en tête ("uniquement en 2026", "seulement en avril")
    q = re.sub(r"^(uniquement|seulement|aussi|seul|seule)\s+", "", q, flags=re.I)

    qualifs  = r"(\s+(uniquement|seulement|aussi|seul|seule))?"
    _mois    = r"janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre"
    temporal = (
        r"20\d{2}"
        rf"|(?:{_mois})(?:\s+20\d{{2}})?"
        r"|trimestre\s*\d|semestre\s*\d"
        r"|s\d{1,2}"
        r"|cette\s+annee|l.annee\s+derniere"
    )
    granul = r"(par\s+)?(mois|semaine[s]?|trimestre[s]?|semestre[s]?|annee[s]?|engin[s]?|zone[s]?|voyage[s]?)"
    types  = (
        r"direction|pneu[s]?|carburant|flexible[s]?|pluie"
        r"|piste[s]?|climatisation|crevaison[s]?|mecanique"
        r"|excavation|descente|tonnage"
    )
    prep = r"(?:en\s+|pour\s+(?:le\s+)?(?:mois\s+(?:de\s+)?)?|au\s+mois\s+de\s+|sur\s+|de\s+|du\s+)?"

    if re.fullmatch(rf"{prep}({temporal}){qualifs}", q, re.IGNORECASE):
        return True
    if len(q) <= 25 and re.fullmatch(granul, q, re.IGNORECASE):
        return True
    if len(q) <= 25 and re.fullmatch(rf"{prep}({types})", q, re.IGNORECASE):
        return True
    combined = rf"{prep}({types}|{granul})\s+{prep}({temporal}){qualifs}"
    if len(q) <= 40 and re.fullmatch(combined, q, re.IGNORECASE):
        return True

    return False


def rebuild_index() -> None:
    """Reconstruit l'index BM25 après un import de nouvelles données."""
    global _bm25_index
    from src.rag.index import build_and_save
    con = get_db()
    _bm25_index = build_and_save(con)
    logger.info("Index BM25 reconstruit — %d documents.", len(_bm25_index.docs))
