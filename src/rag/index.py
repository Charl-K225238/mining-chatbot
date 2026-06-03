"""
Index BM25 sur le corpus textuel minier.

BM25 pondère les termes par fréquence dans le document ET rareté dans le corpus —
robuste sur du texte métier dense en mots-clés.

Optimisation de chargement : le corpus tokenisé est sauvegardé dans le pickle
pour éviter de re-tokeniser N documents à chaque démarrage.
"""

import logging
import pickle
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from src.utils.text import norm

logger = logging.getLogger(__name__)

INDEX_PATH = Path(__file__).parents[2] / "data" / "bm25_index.pkl"

_STOPWORDS_FR = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "au",
    "aux", "ce", "qui", "que", "ou", "par", "sur", "dans", "avec", "pour",
    "est", "sont", "a", "il", "elle", "on", "se", "ne", "pas", "plus",
    "tout", "tous", "toute", "toutes", "cette", "cet", "ces", "son", "sa",
    "ses", "leur", "leurs", "nous", "vous", "ils", "elles", "me", "te",
    "y", "je", "tu", "si", "ni", "car", "mais",
}


def _tokenize(text: str) -> list[str]:
    """Normalise (accents, casse) et tokenise en mots-clés significatifs."""
    tokens = re.findall(r"\b[a-z0-9]{2,}\b", norm(text))
    return [t for t in tokens if t not in _STOPWORDS_FR]


class BM25Index:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = docs
        tokenized = [_tokenize(d["text"]) for d in docs]
        self.bm25 = BM25Okapi(tokenized)
        logger.info("Index BM25 construit — %d documents.", len(docs))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [
            {"doc": self.docs[i], "score": float(s)}
            for i, s in ranked[:top_k]
            if s > 0
        ]

    def save(self, path: Path = INDEX_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tokenized = [_tokenize(d["text"]) for d in self.docs]
        with open(path, "wb") as f:
            # Sauvegarder le corpus tokenisé pour éviter de re-tokeniser au chargement
            pickle.dump({"docs": self.docs, "tokenized": tokenized}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("Index sauvegardé : %s (%d docs)", path, len(self.docs))

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> "BM25Index":
        with open(path, "rb") as f:
            data = pickle.load(f)
        instance = cls.__new__(cls)
        instance.docs = data["docs"]
        # Réutilise le tokenized sauvegardé si disponible (ancien format = recalcul)
        tokenized = data.get("tokenized") or [_tokenize(d["text"]) for d in instance.docs]
        instance.bm25 = BM25Okapi(tokenized)
        logger.info("Index chargé : %s (%d docs)", path, len(instance.docs))
        return instance


def build_and_save(con) -> BM25Index:
    from src.rag.corpus import build_corpus
    docs = build_corpus(con)
    idx = BM25Index(docs)
    idx.save()
    return idx


def get_index(con=None) -> BM25Index:
    if INDEX_PATH.exists():
        return BM25Index.load()
    if con is None:
        raise RuntimeError(
            "Index BM25 absent. Fournissez une connexion DuckDB : python -m src.rag.index"
        )
    return build_and_save(con)
