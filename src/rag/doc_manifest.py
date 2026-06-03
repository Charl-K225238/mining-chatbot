"""
src/rag/doc_manifest.py — Manifeste des documents uploadés.

Enregistre et restitue les métadonnées de chaque document indexé :
  - type de document (inspection, pges, technique, rh, general)
  - date de chargement
  - langue détectée (fr par défaut)
  - thèmes clés détectés à partir du nom de fichier / contenu

Ces métadonnées sont utilisées par le retriever pour :
  1. Enrichir la réponse LLM avec le type de source
  2. Orienter l'utilisateur si le bon document n'est pas chargé
  3. Trier les résultats par pertinence thématique
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT     = Path(__file__).parents[2]
_MANIFEST = _ROOT / "data" / "doc_manifest.json"

# ─────────────────────────────────────────────────────────────────────────────
# Règles de détection de type par mots-clés dans le nom de fichier
# ─────────────────────────────────────────────────────────────────────────────
_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("inspection",  ["inspection", "audit", "visite", "bureau veritas", "bv",
                     "conformit", "nc ", "non-conform", "controle"]),
    ("pges",        ["pges", "plan gestion", "environnement", "ande",
                     "communaute", "biodiversit", "reboisement"]),
    ("procedure",   ["procedure", "mode operatoire", "instruction", "guide",
                     "process", "protocole", "methode"]),
    ("securite",    ["securite", "hse", "sante", "risque", "accident",
                     "incident", "danger", "epi"]),
    ("technique",   ["technique", "specification", "schema", "plan", "notice",
                     "manuel", "fiche technique", "datasheet"]),
    ("rapport",     ["rapport", "bilan", "compte-rendu", "cr ", "synthese",
                     "note", "analyse"]),
    ("contrat",     ["contrat", "convention", "accord", "marche", "appel offre"]),
    ("rh",          ["rh", "ressource humaine", "formation", "recrutement",
                     "effectif", "paie", "salaire"]),
]

# Types lisibles pour l'affichage
_TYPE_LABELS: dict[str, str] = {
    "inspection":  "Rapport d'inspection",
    "pges":        "Document PGES/Environnement",
    "procedure":   "Procédure / Mode opératoire",
    "securite":    "Document HSE / Sécurité",
    "technique":   "Documentation technique",
    "rapport":     "Rapport / Bilan",
    "contrat":     "Contrat / Convention",
    "rh":          "Document RH",
    "general":     "Document général",
}


def detect_type(filename: str, content_sample: str = "") -> str:
    """
    Détecte le type d'un document depuis son nom + un échantillon de contenu.
    Retourne un identifiant de type parmi les clés de _TYPE_LABELS.
    """
    text = (filename + " " + content_sample).lower()
    # Supprimer les accents pour la comparaison
    try:
        import unicodedata
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
    except Exception:
        pass

    for doc_type, keywords in _TYPE_RULES:
        if any(kw in text for kw in keywords):
            return doc_type
    return "general"


def type_label(doc_type: str) -> str:
    return _TYPE_LABELS.get(doc_type, "Document général")


# ─────────────────────────────────────────────────────────────────────────────
# Lecture / écriture du manifeste JSON
# ─────────────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if _MANIFEST.exists():
        try:
            return json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict) -> None:
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register(filename: str, content_sample: str = "") -> dict:
    """
    Enregistre un document dans le manifeste.
    Retourne les métadonnées enregistrées.
    """
    doc_type = detect_type(filename, content_sample)
    meta = {
        "filename":   filename,
        "type":       doc_type,
        "type_label": type_label(doc_type),
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    data = _load()
    data[filename] = meta
    _save(data)
    logger.info("doc_manifest: enregistré %s (%s)", filename, doc_type)
    return meta


def get(filename: str) -> dict | None:
    """Retourne les métadonnées d'un document, ou None s'il n'est pas dans le manifeste."""
    return _load().get(filename)


def get_all() -> dict[str, dict]:
    """Retourne tous les documents enregistrés."""
    return _load()


def remove(filename: str) -> None:
    """Supprime l'entrée d'un document du manifeste."""
    data = _load()
    if filename in data:
        del data[filename]
        _save(data)


def list_by_type(doc_type: str) -> list[dict]:
    """Retourne tous les documents d'un type donné."""
    return [m for m in _load().values() if m.get("type") == doc_type]


def context_for_retrieval(filename: str) -> str:
    """
    Retourne une ligne de contexte à injecter dans le prompt LLM
    pour identifier la source documentaire.
    Ex: "[Source : Rapport d'inspection — rapport_bv_2024.pdf]"
    """
    meta = get(filename)
    if meta:
        return f"[Source : {meta['type_label']} — {filename}]"
    return f"[Source : {filename}]"


def guidance_no_doc(question_type: str) -> str | None:
    """
    Si aucun document du type attendu n'est chargé, retourne un message
    guidant l'utilisateur vers le bon fichier à uploader.

    question_type : "inspection" | "pges" | "procedure" | etc.
    """
    docs = list_by_type(question_type)
    if docs:
        return None  # Des documents existent → pas de guidance nécessaire
    label = type_label(question_type)
    hints: dict[str, str] = {
        "inspection": (
            "Aucun rapport d'inspection chargé. "
            "Uploadez un **rapport d'inspection / audit** (PDF, DOCX) dans **⚙️ Paramètres → Charger un fichier**."
        ),
        "pges": (
            "Aucun document PGES chargé. "
            "Les données PGES sont disponibles dans la table **pges_actions** (Excel). "
            "Pour les documents PGES textuels, uploadez-les dans **⚙️ Paramètres**."
        ),
        "procedure": (
            "Aucune procédure chargée. "
            "Uploadez votre document procédure / mode opératoire dans **⚙️ Paramètres**."
        ),
        "securite": (
            "Aucun document HSE/Sécurité chargé. "
            "Uploadez votre document HSE dans **⚙️ Paramètres → Charger un fichier**."
        ),
    }
    return hints.get(question_type,
                     f"Aucun document de type « {label} » chargé. "
                     f"Uploadez-le dans **⚙️ Paramètres → Charger un fichier**.")
