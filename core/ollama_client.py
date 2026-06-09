"""
core/ollama_client.py — Client Ollama avec auto-démarrage silencieux.

Principe :
  L'utilisateur ne démarre JAMAIS Ollama manuellement.
  Le client trouve l'exe, lance le serveur, attend, et gère les erreurs
  en français sans jamais exposer WinError, port ou commande terminal.

Fonctions publiques :
  trouver_ollama_exe()             → str | None
  ollama_est_disponible()          → bool
  demarrer_ollama()                → bool      (Popen silencieux, polling 15s)
  assurer_ollama_disponible()      → bool
  lister_modeles_disponibles()     → list[str]
  assurer_modele_disponible(m, ph) → bool      (pull avec progression)
  appeler_ollama(q, ctx, ...)      → str | Iterator[str]
  afficher_erreur_ollama(code)     → str       (UX française)
  is_available()                   → bool      (rétrocompat src/llm/ollama_client)
  active_model_name()              → str       (rétrocompat)
  ask(q, ctx, mode)                → str       (rétrocompat)
  stream(q, ctx, mode)             → Iterator[str]
  initialiser_ollama(modele)       → dict      (@st.cache_resource)
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import requests
import streamlit as st

# Assurer que ROOT est dans sys.path pour les imports src/ et config/
_ROOT = Path(__file__).parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_EXE_PATHS,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    NUM_CTX_DEFAULT,
    TEMPERATURE_DEFAULT,
)
from src.llm.prompts import build_prompt, get_system_prompt

# Nombre de tokens générés selon le mode LLM
_NUM_PREDICT: dict[str, int] = {
    "expert":   800,   # réponse structurée, max 400 mots
    "analyse":  700,
    "synthese": 600,
    "math":     250,   # résultat bref, pas de LaTeX ni d'introduction
    "libre":    400,
    "factuel":  400,
}

logger = logging.getLogger(__name__)

# ── Environnement ──────────────────────────────────────────────────────────────
IS_WINDOWS = platform.system() == "Windows"

# Streamlit Cloud : STREAMLIT_SHARING_MODE=streamlit (officiel),
# HOME=/home/appuser (ancienne image) ou HOME=/home/adminuser (image Python 3.14+).
IS_STREAMLIT_CLOUD = (
    os.environ.get("STREAMLIT_SHARING_MODE") == "streamlit"
    or os.environ.get("HOME") in ("/home/appuser", "/home/adminuser")
)

# ── Codes d'erreur internes (jamais exposés bruts à l'utilisateur) ───────────
_NOT_INSTALLED  = "__NOT_INSTALLED__"
_NO_MODEL       = "__NO_MODEL__"
_TIMEOUT        = "__TIMEOUT__"
_ERROR_PREFIX   = "__ERROR__:"

# Sentinel émis dans le flux streaming avant la bascule vers le modèle léger.
# La page UI détecte ce token pour afficher une notification non-bloquante.
SWITCH_MODEL_SENTINEL = "__SWITCH_MODEL__"

# ── Timeout HTTP ──────────────────────────────────────────────────────────────
_TIMEOUT_CHECK   = 2    # secondes pour vérifier si Ollama est actif
_TIMEOUT_CHAT    = 120  # secondes pour une réponse complète
_TIMEOUT_PULL    = 300  # secondes pour télécharger un modèle
_MAX_START_SECS  = 15   # secondes d'attente après Popen


# ═══════════════════════════════════════════════════════════════════════════════
# 0. URL OLLAMA (résolution dynamique : env → st.secrets → settings)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_ollama_base_url() -> str:
    """
    Retourne l'URL de base Ollama selon la priorité suivante :
      1. Variable d'environnement OLLAMA_HOST
      2. Secret Streamlit OLLAMA_HOST (pour Streamlit Cloud)
      3. Valeur par défaut de config/settings.py (http://localhost:11434)
    """
    url = os.getenv("OLLAMA_HOST")
    if not url:
        try:
            url = st.secrets.get("OLLAMA_HOST")
        except Exception:
            pass
    return (url or OLLAMA_BASE_URL).rstrip("/")


def is_remote_ollama() -> bool:
    """True si Ollama est configuré sur une URL distante (pas localhost)."""
    url = _get_ollama_base_url()
    return "localhost" not in url and "127.0.0.1" not in url


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TROUVER L'EXÉCUTABLE
# ═══════════════════════════════════════════════════════════════════════════════

def trouver_ollama_exe() -> str | None:
    """
    Cherche l'exécutable Ollama sur toutes les plateformes.
    - Sur Streamlit Cloud : retourne None directement (pas d'Ollama local).
    - Sur toutes les plateformes : vérifie le PATH d'abord (shutil.which).
    - Sur Windows uniquement : vérifie aussi les chemins d'installation standards.
    Retourne le chemin complet ou None si introuvable.
    """
    if IS_STREAMLIT_CLOUD:
        # Streamlit Cloud n'a pas Ollama — accès via OLLAMA_HOST uniquement.
        return None

    # 1. PATH système — fonctionne sur Windows, Linux et Mac
    found = shutil.which("ollama")
    if found:
        return found

    # 2. Emplacements Windows standards (non dans le PATH après installation)
    if IS_WINDOWS:
        for path_tpl in OLLAMA_EXE_PATHS:
            expanded = os.path.expandvars(path_tpl)
            if Path(expanded).exists():
                return expanded

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. VÉRIFIER LA DISPONIBILITÉ
# ═══════════════════════════════════════════════════════════════════════════════

def ollama_est_disponible() -> bool:
    """Vérifie que l'API Ollama répond (GET /api/tags timeout=2s)."""
    try:
        r = requests.get(f"{_get_ollama_base_url()}/api/tags", timeout=_TIMEOUT_CHECK)
        return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DÉMARRER OLLAMA
# ═══════════════════════════════════════════════════════════════════════════════

def demarrer_ollama() -> bool:
    """
    Démarre Ollama silencieusement via Popen (Windows + Linux/Mac).
    Sur Windows : CREATE_NO_WINDOW évite d'ouvrir un terminal visible.
    Sur Linux/Mac : Popen standard avec DEVNULL.
    Attend la disponibilité jusqu'à 15 secondes (polling 1s).
    Retourne True si Ollama répond avant la limite.
    Ne fait rien sur Streamlit Cloud (pas d'exe local).
    """
    if ollama_est_disponible():
        return True

    exe = trouver_ollama_exe()
    if not exe:
        logger.warning("Exécutable ollama introuvable — démarrage automatique impossible.")
        return False

    try:
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        subprocess.Popen([exe, "serve"], **kwargs)
        logger.info("Ollama lancé depuis %s — attente jusqu'à %ds.", exe, _MAX_START_SECS)
    except Exception as exc:
        logger.error("Impossible de démarrer Ollama : %s", exc)
        return False

    # Polling jusqu'à _MAX_START_SECS
    for _ in range(_MAX_START_SECS):
        time.sleep(1)
        if ollama_est_disponible():
            logger.info("Ollama disponible.")
            return True

    logger.warning("Ollama n'a pas répondu dans les %ds.", _MAX_START_SECS)
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ASSURER LA DISPONIBILITÉ
# ═══════════════════════════════════════════════════════════════════════════════

def assurer_ollama_disponible() -> bool:
    """Retourne True si Ollama est prêt (démarre si nécessaire)."""
    return ollama_est_disponible() or demarrer_ollama()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LISTER LES MODÈLES
# ═══════════════════════════════════════════════════════════════════════════════

def lister_modeles_disponibles() -> list[str]:
    """Retourne la liste des modèles installés. Retourne [] si Ollama est inactif."""
    try:
        r = requests.get(f"{_get_ollama_base_url()}/api/tags", timeout=_TIMEOUT_CHECK)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def _get_best_model() -> str:
    """Retourne le meilleur modèle disponible (primary → fallback)."""
    models = lister_modeles_disponibles()
    primary_base  = PRIMARY_MODEL.split(":")[0]
    fallback_base = FALLBACK_MODEL.split(":")[0]
    if any(primary_base in m for m in models):
        return PRIMARY_MODEL
    if any(fallback_base in m for m in models):
        return FALLBACK_MODEL
    return FALLBACK_MODEL  # tentative par défaut


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ASSURER QU'UN MODÈLE EST DISPONIBLE
# ═══════════════════════════════════════════════════════════════════════════════

def assurer_modele_disponible(modele: str, placeholder=None) -> bool:
    """
    Vérifie si le modèle est installé.
    S'il est absent → POST /api/pull avec affichage de progression.
    Retourne True si le modèle est disponible après l'opération.
    """
    models = lister_modeles_disponibles()
    base   = modele.split(":")[0]

    if any(base in m for m in models):
        return True

    if placeholder:
        placeholder.info(
            f"⬇️ Téléchargement de **{modele}**… "
            f"Cette opération peut prendre plusieurs minutes selon la connexion."
        )

    try:
        with requests.post(
            f"{_get_ollama_base_url()}/api/pull",
            json={"name": modele},
            stream=True,
            timeout=_TIMEOUT_PULL,
        ) as r:
            for raw in r.iter_lines():
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    status = data.get("status", "")
                    if placeholder:
                        if "completed" in data and "total" in data and data["total"] > 0:
                            pct = int(data["completed"] / data["total"] * 100)
                            placeholder.info(f"⬇️ {status} — {pct} %")
                        elif status:
                            placeholder.info(f"⬇️ {status}")
                except Exception:
                    pass

        available = any(base in m for m in lister_modeles_disponibles())
        if available and placeholder:
            placeholder.success(f"✅ Modèle **{modele}** installé et prêt.")
        elif placeholder:
            placeholder.error(f"❌ Échec du téléchargement de **{modele}**.")
        return available

    except Exception as exc:
        logger.error("Pull modèle %s échoué : %s", modele, exc)
        if placeholder:
            placeholder.error(f"❌ Erreur lors du téléchargement : {exc}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 7. APPELER OLLAMA
# ═══════════════════════════════════════════════════════════════════════════════

def appeler_ollama(
    question: str,
    context:  str  = "",
    modele:   str | None = None,
    mode:     str  = "auto",
    stream:   bool = False,
) -> str | Iterator[str]:
    """
    Pipeline complet :
      assurer_ollama_disponible() → vérifier modèle → POST /api/chat
      → si ConnectionError : demarrer_ollama() puis retry une fois.

    Retour :
      stream=False → str   (réponse complète ou code d'erreur interne)
      stream=True  → Iterator[str]  (tokens ou message d'erreur unique)

    Codes d'erreur internes (traduits par afficher_erreur_ollama()) :
      __NOT_INSTALLED__  __NO_MODEL__  __TIMEOUT__  __ERROR__:msg
    """
    if not assurer_ollama_disponible():
        code = _NOT_INSTALLED if trouver_ollama_exe() is None else f"{_ERROR_PREFIX}Ollama n'a pas pu démarrer"
        return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)

    _modele = modele or _get_best_model()

    # Vérifier que le modèle est présent (ne pas pull automatiquement ici — coûteux)
    models = lister_modeles_disponibles()
    if models and not any(_modele.split(":")[0] in m for m in models):
        code = _NO_MODEL
        return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)

    system_prompt = get_system_prompt(question, mode=mode)
    user_prompt   = build_prompt(question, context, mode=mode)

    # Lire les paramètres depuis la session utilisateur (slider Paramètres)
    try:
        _num_ctx     = st.session_state.get("adv_num_ctx",     NUM_CTX_DEFAULT)
        _temperature = st.session_state.get("adv_temperature", TEMPERATURE_DEFAULT)
    except Exception:
        _num_ctx, _temperature = NUM_CTX_DEFAULT, TEMPERATURE_DEFAULT

    payload = {
        "model":  _modele,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": stream,
        "options": {
            "temperature":    _temperature,
            "num_predict":    _NUM_PREDICT.get(mode, 500),
            "num_ctx":        _num_ctx,
            "repeat_penalty": 1.1,
            "top_p":          0.9,
        },
    }

    def _do_call() -> str | Iterator[str]:
        if stream:
            # Prépare le payload de secours pour bascule automatique sur timeout
            _fb = (
                {**payload, "model": FALLBACK_MODEL}
                if _modele != FALLBACK_MODEL else None
            )
            return _stream_chat(payload, fallback_payload=_fb)
        else:
            r = requests.post(
                f"{_get_ollama_base_url()}/api/chat",
                json=payload,
                timeout=_TIMEOUT_CHAT,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "").strip()
            return f"{_ERROR_PREFIX}HTTP {r.status_code}"

    try:
        return _do_call()
    except requests.exceptions.Timeout:
        # Non-stream : auto-retry avec modèle léger avant d'afficher l'erreur
        if not stream and _modele != FALLBACK_MODEL:
            logger.info("Timeout sur %s — bascule vers %s", _modele, FALLBACK_MODEL)
            try:
                fb_r = requests.post(
                    f"{_get_ollama_base_url()}/api/chat",
                    json={**payload, "model": FALLBACK_MODEL},
                    timeout=_TIMEOUT_CHAT,
                )
                if fb_r.status_code == 200:
                    return fb_r.json().get("message", {}).get("content", "").strip()
            except Exception:
                pass
        code = _TIMEOUT
        return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)
    except requests.exceptions.ConnectionError:
        # Retry unique après tentative de redémarrage
        if demarrer_ollama():
            try:
                return _do_call()
            except Exception as exc:
                code = f"{_ERROR_PREFIX}{exc}"
                return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)
        code = f"{_ERROR_PREFIX}Connexion perdue"
        return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)
    except Exception as exc:
        code = f"{_ERROR_PREFIX}{exc}"
        return iter([afficher_erreur_ollama(code)]) if stream else afficher_erreur_ollama(code)


def _stream_chat(payload: dict, fallback_payload: dict | None = None) -> Iterator[str]:
    """
    Streaming HTTP /api/chat — yield token par token.

    Si fallback_payload est fourni et que la requête principale timeout,
    émet SWITCH_MODEL_SENTINEL puis réessaie avec le payload de secours.
    """
    try:
        with requests.post(
            f"{_get_ollama_base_url()}/api/chat",
            json=payload,
            stream=True,
            timeout=_TIMEOUT_CHAT,
        ) as r:
            for raw in r.iter_lines():
                if not raw:
                    continue
                try:
                    data  = json.loads(raw)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except Exception:
                    pass
    except requests.exceptions.Timeout:
        if fallback_payload:
            logger.info(
                "Timeout streaming sur %s — bascule automatique vers %s",
                payload.get("model"), fallback_payload.get("model"),
            )
            yield SWITCH_MODEL_SENTINEL
            yield from _stream_chat(fallback_payload, fallback_payload=None)
        else:
            yield afficher_erreur_ollama(_TIMEOUT)
    except requests.exceptions.ConnectionError:
        yield afficher_erreur_ollama(f"{_ERROR_PREFIX}Connexion interrompue")
    except Exception as exc:
        yield afficher_erreur_ollama(f"{_ERROR_PREFIX}{exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. MESSAGES D'ERREUR UX
# ═══════════════════════════════════════════════════════════════════════════════

def afficher_erreur_ollama(code: str) -> str:
    """
    Traduit un code d'erreur interne en message français lisible.
    JAMAIS de WinError, OSError, port, URL ou commande terminal.
    Les messages distinguent le contexte local (Windows) et cloud (Linux).
    """
    if code == _NOT_INSTALLED:
        if IS_STREAMLIT_CLOUD:
            return (
                "**Cette question dépasse les capacités analytiques de Miny.**\n\n"
                "Miny répond aux questions sur les données de la mine : "
                "tonnage, pannes, carburant, objectifs, PGES, heures machine.\n\n"
                "_Consultez **📖 Documentation** pour voir les exemples de questions._"
            )
        elif IS_WINDOWS:
            return (
                "**Ollama n'est pas installé sur ce PC.**\n\n"
                "**Solution :** téléchargez Ollama depuis *ollama.com* "
                "et installez-le — la page **⚙️ Paramètres** vous guidera.\n\n"
                "_Les réponses analytiques (⚡) fonctionnent sans Ollama._"
            )
        else:
            return (
                "**Ollama n'est pas installé ou n'est pas démarré.**\n\n"
                "**Solution :** installez Ollama (`curl -fsSL https://ollama.com/install.sh | sh`) "
                "puis lancez `ollama serve`.\n\n"
                "La page **⚙️ Paramètres** vous guidera.\n\n"
                "_Les réponses analytiques (⚡) fonctionnent sans Ollama._"
            )
    if code == _NO_MODEL:
        return (
            "**Aucun modèle LLM compatible n'est disponible.**\n\n"
            "**Solution :** dans **⚙️ Paramètres**, cliquez "
            "*⬇️ Télécharger qwen2.5:3b*.\n\n"
            "_Les réponses analytiques (⚡) fonctionnent sans modèle LLM._"
        )
    if code == _TIMEOUT:
        return (
            "**Le modèle LLM n'a pas répondu dans le délai imparti** "
            "(bascule automatique vers le modèle léger déjà tentée).\n\n"
            "**Solutions :**\n"
            "1. Raccourcissez votre question\n"
            "2. Fermez d'autres applications pour libérer de la RAM\n"
            "3. Réduisez `num_ctx` dans **⚙️ Paramètres** → Paramètres avancés\n\n"
            "_Les réponses analytiques (⚡) ne sont pas affectées._"
        )
    if code.startswith(_ERROR_PREFIX):
        msg = code[len(_ERROR_PREFIX):]
        if "memory" in msg.lower() or "oom" in msg.lower():
            return (
                "**Mémoire insuffisante pour exécuter le modèle.**\n\n"
                "**Solutions :**\n"
                "1. Fermez d'autres applications pour libérer de la RAM\n"
                "2. Passez à `phi3:mini` (RAM < 2 Go)\n\n"
                "_Les réponses analytiques (⚡) fonctionnent sans Ollama._"
            )
        return (
            "**Une erreur s'est produite avec le modèle LLM.**\n\n"
            "_Les réponses analytiques (⚡) fonctionnent sans Ollama._"
        )
    # Code inconnu — message neutre
    return (
        "**Le service LLM est temporairement indisponible.**\n\n"
        "_Les réponses analytiques (⚡) fonctionnent normalement._"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. INITIALISATION AU DÉMARRAGE (@st.cache_resource)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="Vérification d'Ollama…")
def initialiser_ollama(modele: str | None = None) -> dict:
    """
    Appelé une fois au démarrage.
    Vérifie la disponibilité d'Ollama (local ou réseau selon OLLAMA_HOST).
    Retourne un dict de statut stocké dans session_state.
    """
    _modele    = modele or PRIMARY_MODEL
    disponible = assurer_ollama_disponible()
    modeles    = lister_modeles_disponibles() if disponible else []
    actif      = _get_best_model() if modeles else None
    url        = _get_ollama_base_url()

    status = {
        "disponible":    disponible,
        "modeles":       modeles,
        "modele_actif":  actif,
        "exe":           trouver_ollama_exe(),
        "is_windows":    IS_WINDOWS,
        "is_cloud":      IS_STREAMLIT_CLOUD,
        "ollama_url":    url,
        "is_remote":     is_remote_ollama(),
    }
    logger.info(
        "Ollama init — disponible=%s modele=%s url=%s windows=%s cloud=%s",
        disponible, actif, url, IS_WINDOWS, IS_STREAMLIT_CLOUD,
    )
    return status


# ═══════════════════════════════════════════════════════════════════════════════
# ALIASES DE RÉTROCOMPATIBILITÉ (compatibles src/llm/ollama_client.py)
# ═══════════════════════════════════════════════════════════════════════════════

def is_available(model: str | None = None) -> bool:
    """Rétrocompat — True si Ollama est démarré ET un modèle compatible existe."""
    if not ollama_est_disponible():
        return False
    models = lister_modeles_disponibles()
    if model:
        return any(model in m for m in models)
    primary_base  = PRIMARY_MODEL.split(":")[0]
    fallback_base = FALLBACK_MODEL.split(":")[0]
    return any(
        any(b in m for m in models)
        for b in [primary_base, fallback_base]
    )


def active_model_name() -> str:
    """Rétrocompat — retourne le nom du modèle actif (pour affichage UI)."""
    return _get_best_model()


def ask(question: str, context: str, mode: str = "auto") -> str:
    """Rétrocompat — réponse complète non-streaming."""
    result = appeler_ollama(question, context=context, mode=mode, stream=False)
    if isinstance(result, str):
        return result
    return "".join(result)


def stream(question: str, context: str, mode: str = "auto") -> Iterator[str]:
    """Rétrocompat — streaming token par token."""
    result = appeler_ollama(question, context=context, mode=mode, stream=True)
    if isinstance(result, str):
        yield result
    else:
        yield from result
