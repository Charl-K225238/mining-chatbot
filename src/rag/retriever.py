"""
Interface de recherche RAG — optimisée pour Miny.

Fonctionnalités :
- Boost des fichiers uploadés (PDF/DOCX/TXT) quand la question porte sur des rapports
- Score minimum adaptatif selon le type de question
- Déduplication des sources identiques
- Contexte enrichi avec le type de document (via doc_manifest)
- Guidance si aucun document pertinent n'est trouvé
"""

import logging
from typing import Any

from src.rag.index import BM25Index
from src.utils.text import norm

logger = logging.getLogger(__name__)

_MIN_SCORE      = 0.2    # seuil global
_MIN_SCORE_DOC  = 0.05   # seuil pour docs uploadés (souvent sous-représentés en BM25)
_TOP_K          = 10
_MAX_TEXT_LEN   = 600    # chars max par document
_MAX_TEXT_LEN_DOC = 1500 # chars max pour docs uploadés
_MAX_RESULTS    = 8

# Mots-clés indiquant une question sur un document uploadé
_DOC_QUESTION_KW = {
    "inspection", "rapport", "non-conformit", "non conformit", "bureau veritas",
    "audit", "organisme", "visite", "constat", "certif", "bv", "ref", "ins-mine",
    "correctif", "levee", "delai", "majeur", "mineur", "garde-corps", "passerelle",
    "concasseur", "conformite", "conformit", "procedure", "instruction",
    "securite", "hse", "incident", "accident",
}

# Mapping mots-clés → type de document pour guidance "aucun doc trouvé"
_KW_TO_DOC_TYPE: dict[str, str] = {
    "inspection": "inspection", "audit": "inspection", "non-conformit": "inspection",
    "bureau veritas": "inspection", "conformit": "inspection",
    "procedure": "procedure", "instruction": "procedure",
    "securite": "securite", "hse": "securite",
}

# Tables de fichiers uploadés (priorité boost)
_UPLOADED_TABLES = {"fichier_txt", "fichier_pdf", "fichier_docx"}


def _is_doc_question(query: str) -> bool:
    q = norm(query)
    return any(kw in q for kw in _DOC_QUESTION_KW)


def _detect_expected_doc_type(query: str) -> str | None:
    """Détecte quel type de document est attendu pour une question."""
    q = norm(query)
    for kw, doc_type in _KW_TO_DOC_TYPE.items():
        if kw in q:
            return doc_type
    return None


def retrieve(query: str, index: BM25Index, top_k: int = _TOP_K) -> str:
    """
    Recherche les documents pertinents et retourne un bloc de contexte
    formaté pour injection dans le prompt LLM.

    Si aucun document pertinent n'est trouvé mais que le type de document
    attendu est identifiable, retourne une guidance pour l'utilisateur.
    """
    is_doc_q = _is_doc_question(query)
    results  = index.search(query, top_k=top_k)

    # Filtre par score
    filtered = []
    for r in results:
        table = r["doc"].get("table", "")
        min_s = _MIN_SCORE_DOC if table in _UPLOADED_TABLES else _MIN_SCORE
        if r["score"] >= min_s:
            filtered.append(r)

    # Boost : docs uploadés en premier si question doc
    if is_doc_q:
        filtered.sort(
            key=lambda r: (0 if r["doc"].get("table") in _UPLOADED_TABLES else 1,
                           -r["score"])
        )
    else:
        filtered.sort(key=lambda r: -r["score"])

    # Dédupliquer par source
    seen: set[str] = set()
    deduped = []
    for r in filtered:
        src = r["doc"].get("meta", {}).get("source", r["doc"]["id"])
        if src not in seen:
            seen.add(src)
            deduped.append(r)
        if len(deduped) >= _MAX_RESULTS:
            break

    if not deduped:
        # Vérifier si un document du bon type devrait être chargé
        if is_doc_q:
            expected_type = _detect_expected_doc_type(query)
            if expected_type:
                try:
                    from src.rag.doc_manifest import guidance_no_doc
                    guidance = guidance_no_doc(expected_type)
                    if guidance:
                        return f"__NO_DOC_GUIDANCE__:{guidance}"
                except Exception:
                    pass
        return ""

    # Enrichir chaque résultat avec le type de document si disponible
    try:
        from src.rag.doc_manifest import get as _get_meta
        _manifest_available = True
    except Exception:
        _manifest_available = False

    lines = [f"Documents pertinents ({len(deduped)}) :"]
    for r in deduped:
        doc: dict[str, Any] = r["doc"]
        date_str    = f" [{doc['date']}]" if doc.get("date") else ""
        source_meta = doc.get("meta", {}).get("source", "")
        table_label = f"{doc['table']}{' · ' + source_meta if source_meta else ''}"

        # Enrichir avec le type du document (manifeste)
        type_suffix = ""
        if _manifest_available and source_meta:
            meta = _get_meta(source_meta)
            if meta:
                type_suffix = f" — {meta['type_label']}"

        source = f"[{table_label}{date_str}{type_suffix}]"
        text   = doc["text"]
        max_len = _MAX_TEXT_LEN_DOC if doc.get("table") in _UPLOADED_TABLES else _MAX_TEXT_LEN
        if len(text) > max_len:
            text = text[:max_len] + "…"
        lines.append(f"  {source} {text}")

    return "\n".join(lines)
