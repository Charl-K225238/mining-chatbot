"""Utilitaires texte partagés (normalisation, accents)."""

import unicodedata


def norm(s: str) -> str:
    """Minuscules + suppression des accents (NFD). Utilisé par analytics et BM25."""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(s).lower())
        if unicodedata.category(c) != "Mn"
    )
