"""
src/llm/ollama_client.py — Délégation vers core/ollama_client.py.

Ce module existe uniquement pour la compatibilité avec src/engine/query_router.py.
Toute la logique réelle est dans core/ollama_client.py (modèles, options, auto-start).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.ollama_client import (  # noqa: F401
    ask,
    stream,
    is_available,
    active_model_name,
    appeler_ollama,
    afficher_erreur_ollama,
)
