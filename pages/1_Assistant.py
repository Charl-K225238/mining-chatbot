"""
Miny — 💬 Assistant BI Minier
Page de chat analytique.
"""

import re
import sys
import time
from datetime import datetime as _dt
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import streamlit.components.v1 as _components

from core.data_loader import get_db, get_index, load_css, sidebar_stats
from core.ollama_client import (
    is_available, active_model_name, initialiser_ollama, SWITCH_MODEL_SENTINEL,
)
from config.settings import FALLBACK_MODEL
from core.router import router as _router
from core.clarification import (
    generer_questions_suivi as _gen_suivi,
    verifier_qualite_prompt as _verif_qualite,
    MESSAGES_CLARIF,
)
from src.engine import analytics as _analytics
from src.engine.clarification import verifier_qualite_prompt as _verif_semantique
from src.engine.smart_clarification import (
    analyser_question as _smart_analyse,
    SmartClarification,
)
from src.engine.query_router import (
    ask_stream, ask_fast_stream,
    ask_general_stream, ask_expert_stream, ask_math_stream,
    _is_followup, _is_general_question, _is_expert_question, _is_math_question,
    rebuild_index,
)
from src.db.connection import close as close_db, list_tables as _list_tables
from src.engine.generic_handler import GenericHandlerResult as _GenericResult

st.set_page_config(
    page_title="💬 Assistant — Miny",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

# ── Exemples par catégorie ─────────────────────────────────────────────────────
EXAMPLES_BY_CAT: dict[str, list[tuple[str, str]]] = {
    "📦 Tonnage & Production": [
        ("Par mois 2026",         "Tonnage descendu par mois en 2026"),
        ("Par semaine 2026",      "Tonnage par semaine en 2026"),
        ("Par trimestre 2025",    "Tonnage par trimestre en 2025"),
        ("Excavé 2025",           "Tonnage excavation 2025"),
        ("Comparer 2024 / 2025",  "Comparer tonnage 2024 et 2025"),
        ("S1-S6 2026",            "Tonnage S1-S6 2026"),
    ],
    "🚢 Transport & Navires": [
        ("Mine → port 2025",      "Tonnage transporté mine vers port en 2025"),
        ("Navires chargés 2025",  "Tonnage navire en 2025"),
        ("Par mois 2025",         "Transport minerai par mois en 2025"),
        ("Écart mine / port",     "Écart tonnage mine et port en 2025"),
        ("Top mois transport",    "Meilleur mois de transport en 2025"),
        ("Cumul annuel",          "Cumul transport minerai en 2025"),
    ],
    "⚠️ Engins & Pannes": [
        ("Bilan pannes 2023",          "Bilan des pannes en 2023"),
        ("Pannes direction 2023",      "Pannes de direction en 2023"),
        ("Tombereaux — classement",    "Quels tombereaux ont le plus de pannes ?"),
        ("Pannes trencher TRS 296",    "Pannes de la trencher TRS N°296"),
        ("Types de pannes 2024",       "Quels types de pannes en 2024 ?"),
        ("Top 5 engins tonnage",       "Top 5 engins par tonnage en 2026"),
    ],
    "🛢️ Carburant": [
        ("Total 2024",             "Carburant consommé en 2024"),
        ("Par mois 2024",          "Carburant par mois en 2024"),
        ("Par engin 2024",         "Carburant par engin en 2024"),
        ("Approvisionnement",      "Approvisionnement citerne en 2024"),
        ("Consommation mensuelle", "Évolution consommation carburant par mois"),
        ("Top consommateurs",      "Top 5 engins consommateurs de carburant"),
    ],
    "📊 Objectifs & Perf.": [
        ("Taux réalisation 2025",   "Taux d'accomplissement en 2025"),
        ("Objectifs vs réalisé",    "Objectifs vs réalisé en 2025"),
        ("Objectifs excavation",    "Objectifs excavation en 2025"),
        ("Comparaison 2024/2025",   "Comparaison taux 2024 et 2025"),
        ("Retard vs objectif",      "Retard par rapport à l'objectif en 2026"),
        ("Heures machine 2025",     "Heures machine par mois en 2025"),
    ],
    "📋 PGES & HSE": [
        ("Actions PGES",            "Actions PGES"),
        ("Non réalisées",           "Obligations non réalisées"),
        ("En cours",                "Actions en cours"),
        ("Gestion déchets",         "Actions gestion des déchets"),
        ("Non-conformités",         "Quelles sont les non-conformités majeures ?"),
        ("Actions urgentes",        "Quelles actions correctives prioriser en urgence ?"),
    ],
}


def _fmt_duration(sec: float) -> str:
    if sec < 60:
        return f"{sec:.0f} s"
    m, s = divmod(int(sec), 60)
    return f"{m} min {s:02d} s"


_TABLE_LABELS: dict[str, str] = {
    "descente_minerai":      "Descente minerai",
    "excavation":            "Excavation",
    "journal":               "Journal engins",
    "shifts_horaires":       "Heures machine",
    "carburant_citerne":     "Carburant (Petro Ivoire)",
    "transport_minerai_paa": "Transport mine→port PAA",
    "productivite_loading":  "Chargement navires",
    "pges_actions":          "Actions PGES",
    "suivi_actions":         "Obligations HSE",
    "objectifs":             "Objectifs",
    "qualite_echantillons":  "Qualité / Teneurs",
}

_MOIS_NUM_FR: dict[str, str] = {
    "01": "Janv", "02": "Févr", "03": "Mars", "04": "Avr",
    "05": "Mai",  "06": "Juin", "07": "Juil", "08": "Août",
    "09": "Sept", "10": "Oct",  "11": "Nov",  "12": "Déc",
}


def _route_caption(route: dict) -> str | None:
    """Construit une ligne de métadonnées pour la réponse analytique."""
    table  = route.get("table")
    filtre = route.get("filtre") or {}
    parts: list[str] = []

    if table:
        parts.append(f"📋 {_TABLE_LABELS.get(table, table)}")

    period_parts: list[str] = []
    if filtre.get("annee"):
        period_parts.append(str(filtre["annee"]))
    if filtre.get("mois"):
        period_parts.append(_MOIS_NUM_FR.get(str(filtre["mois"]).zfill(2), str(filtre["mois"])))
    if filtre.get("trimestre"):
        period_parts.append(f"T{filtre['trimestre']}")
    if filtre.get("semestre"):
        period_parts.append(f"S{filtre['semestre']}")
    if period_parts:
        parts.append("📅 " + " · ".join(period_parts))
    else:
        parts.append("📅 toutes périodes")

    return "  ·  ".join(parts) if parts else None


# ── Session state ──────────────────────────────────────────────────────────────
for _k, _v in {
    "messages":         [],
    "response_times":   [],
    "pending_question": None,
    "feedback":         {},
    "saved_responses":  [],
    "do_scroll_top":    False,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _set_pending(q: str) -> None:
    st.session_state.pending_question = q


def _set_feedback(idx: int, val: int) -> None:
    st.session_state.setdefault("feedback", {})[idx] = val


_NO_DATA_MARKERS = (
    "aucune donnée", "aucun résultat", "aucun enregistrement",
    "non trouvée", "pas de données", "no data",
    "années disponibles", "vérifiez la période",
)


def _is_no_data(content: str) -> bool:
    """Détecte les réponses "aucune donnée" du moteur analytique."""
    c = content.lower()
    return any(m in c for m in _NO_DATA_MARKERS)


def _confidence_badge(rtype: str, content: str) -> str:
    """Retourne le HTML du badge de confiance selon le type de réponse."""
    if rtype == "analytics":
        if _is_no_data(content):
            return '<span class="confidence-badge confidence-medium">ℹ Données non trouvées</span>'
        return '<span class="confidence-badge confidence-high">✓ Données exactes</span>'
    if rtype == "generic":
        if _is_no_data(content):
            return '<span class="confidence-badge confidence-medium">ℹ Table importée — aucune donnée</span>'
        return '<span class="confidence-badge confidence-medium">~ Analyse auto-détectée</span>'
    if rtype == "math":
        return '<span class="confidence-badge confidence-high">✓ Calcul vérifié</span>'
    if rtype == "expert":
        return '<span class="confidence-badge confidence-medium">~ Connaissances LLM</span>'
    if rtype == "general":
        return '<span class="confidence-badge confidence-medium">~ Réponse générale</span>'
    if rtype == "llm":
        if any(p in content.lower() for p in ["je n'ai pas", "je ne trouve", "aucune information"]):
            return '<span class="confidence-badge confidence-low">⚠ Données insuffisantes</span>'
        return '<span class="confidence-badge confidence-medium">~ Analyse documentaire</span>'
    return ""


def _render_assistant(content: str, rtype: str) -> None:
    if rtype == "analytics":
        st.markdown('<span class="badge-analytics">⚡ Analytique</span>',
                    unsafe_allow_html=True)
        if _is_no_data(content):
            # "Aucune donnée pour 2027…" → boîte info, pas bloc code
            st.info(content)
        else:
            st.markdown(f'<div class="analytics-block">{content}</div>',
                        unsafe_allow_html=True)
    elif rtype == "generic":
        st.markdown('<span class="badge-generic">🔍 Analyse générique</span>',
                    unsafe_allow_html=True)
        if _is_no_data(content):
            st.info(content)
        else:
            st.markdown(f'<div class="analytics-block">{content}</div>',
                        unsafe_allow_html=True)
    elif rtype == "math":
        st.markdown('<span class="badge-math">🔢 Calcul</span>',
                    unsafe_allow_html=True)
        st.markdown(content)
    elif rtype == "expert":
        st.markdown('<span class="badge-expert">🏭 Expertise industrie</span>',
                    unsafe_allow_html=True)
        st.markdown(content)
    elif rtype == "general":
        st.markdown('<span class="badge-general">💬 Réponse générale</span>',
                    unsafe_allow_html=True)
        st.markdown(content)
    elif rtype == "error":
        st.warning(content)
    else:
        try:
            _model = active_model_name()
        except Exception:
            _model = "LLM"
        st.markdown(f'<span class="badge-llm">🤖 {_model}</span>',
                    unsafe_allow_html=True)
        st.markdown(content)
    # Badge de confiance (sauf erreur)
    if rtype != "error":
        _badge = _confidence_badge(rtype, content)
        if _badge:
            st.markdown(_badge, unsafe_allow_html=True)


def _last_user_question() -> str | None:
    return next(
        (m["content"] for m in reversed(st.session_state.messages)
         if m["role"] == "user"),
        None,
    )


# ── Multi-question ─────────────────────────────────────────────────────────────

def _split_multi_question(text: str) -> tuple[str, str | None]:
    """
    Détecte si le texte contient plusieurs questions.
    Retourne (première_question, texte_du_reste_ou_None).
    Exemple : "Tonnage 2025 ? Et les normes ISO ?" → ("Tonnage 2025 ?", "Et les normes ISO ?")
    """
    q_count = text.count("?")
    if q_count < 2:
        return text, None

    idx = text.index("?")
    first  = text[:idx + 1].strip()
    remain = text[idx + 1:].strip().lstrip("ety ,;–-").strip()
    if not remain or len(remain) < 5:
        return text, None
    return first, remain


# ── Ollama unavailability ──────────────────────────────────────────────────────

def _show_ollama_warning(key_suffix: str = "") -> str:
    """
    Affiche un message adapté selon l'état d'Ollama.
    Distingue contexte local (Windows) et cloud (Linux / Streamlit Cloud).
    Redirige vers la bonne section de Paramètres via un flag de session.
    Retourne le message pour l'historique.
    """
    _exe       = _ollama_status.get("exe")
    _modeles   = _ollama_status.get("modeles", [])
    _is_win    = _ollama_status.get("is_windows", True)
    _is_cloud  = _ollama_status.get("is_cloud", False)
    _is_remote = _ollama_status.get("is_remote", False)

    if _is_cloud and not _exe:
        # Streamlit Cloud — pas d'Ollama local, OLLAMA_HOST non configuré
        msg = (
            "**Ollama n'est pas accessible depuis ce serveur cloud.**\n\n"
            "Les modes 🔢 Calcul · 🏭 Expertise · 💬 Général · 🤖 Documents "
            "nécessitent une instance Ollama exposée sur Internet.\n\n"
            "Configurez **OLLAMA_HOST** dans les Secrets Streamlit pour activer les modes LLM.\n\n"
            "⚡ **Analytique** répond instantanément sans Ollama."
        )
        st.error(msg, icon="🤖")
        btn_label    = "⚙️ Guide de connexion cloud →"
        session_flag = "install"
    elif not _exe and _is_win:
        # Windows local — Ollama pas installé
        msg = (
            "**Ollama n'est pas installé sur ce PC.**\n\n"
            "Les modes 🔢 Calcul · 🏭 Expertise · 💬 Général · 🤖 Documents "
            "nécessitent Ollama, un moteur IA gratuit qui tourne entièrement en local.\n\n"
            "⚡ **Analytique** répond instantanément sans Ollama."
        )
        st.error(msg, icon="🤖")
        btn_label    = "⚙️ Guide d'installation →"
        session_flag = "install"
    elif not _exe and not _is_win and not _is_cloud:
        # Linux/Mac local — Ollama pas dans le PATH
        msg = (
            "**Ollama n'est pas installé ou n'est pas démarré.**\n\n"
            "Installez Ollama puis lancez `ollama serve` pour activer "
            "les modes 🔢 Calcul · 🏭 Expertise · 💬 Général.\n\n"
            "⚡ **Analytique** répond instantanément sans Ollama."
        )
        st.error(msg, icon="🤖")
        btn_label    = "⚙️ Guide d'installation →"
        session_flag = "install"
    elif not _modeles:
        src = "accessible" if _is_remote else "installé"
        msg = (
            f"**Ollama est {src} mais aucun modèle n'est encore disponible.**\n\n"
            "Téléchargez un modèle pour activer les modes 🔢 Calcul · 🏭 Expertise · 💬 Général.\n\n"
            "⚡ **Analytique** fonctionne sans modèle."
        )
        st.warning(msg, icon="🤖")
        btn_label    = "⚙️ Télécharger un modèle →"
        session_flag = "model"
    else:
        msg = (
            "**Ollama est configuré mais ne répond pas.**\n\n"
            "Il se relancera automatiquement à la prochaine question LLM. "
            "Si le problème persiste, cliquez sur **Vérifier Ollama** dans Paramètres.\n\n"
            "⚡ **Analytique** répond instantanément sans Ollama."
        )
        st.warning(msg, icon="🤖")
        btn_label    = "⚙️ Vérifier Ollama dans Paramètres →"
        session_flag = "check"

    if st.button(btn_label, key=f"btn_ollama_warn_{key_suffix}", type="primary"):
        st.session_state["params_highlight"] = session_flag
        st.switch_page("pages/4_Parametres.py")
    return msg


# ── Sauvegarde de réponse ──────────────────────────────────────────────────────

def _save_response(question: str, answer: str, rtype: str) -> None:
    st.session_state.saved_responses.append({
        "question":  question,
        "answer":    answer,
        "type":      rtype,
        "timestamp": _dt.now().strftime("%d/%m %H:%M"),
    })


def afficher_clarification(
    questions_suivi: list[dict],
    clarif_type: str,
    message: str | None = None,
) -> None:
    """
    Affiche les suggestions contextuelles du router dans un encadré orange (clarif-box).
    Chaque bouton envoie le prompt enrichi directement dans le chat.

    Paramètres :
      questions_suivi : list[{icone, label, prompt}]
      clarif_type     : clé de type clarification (pour déduire le message)
      message         : message affiché en tête (prioritaire sur MESSAGES_CLARIF)
    """
    if not questions_suivi:
        return

    _msg = message or MESSAGES_CLARIF.get(clarif_type, "💡 Suggestions :")

    st.markdown(
        f'<div class="clarif-box"><b>💡 {_msg}</b></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(min(len(questions_suivi), 3))
    for i, s in enumerate(questions_suivi):
        with cols[i % len(cols)]:
            st.button(
                f"{s['icone']} {s['label']}",
                key=f"clarif_route_{clarif_type}_{i}",
                on_click=_set_pending, args=(s["prompt"],),
                use_container_width=True,
            )


def _afficher_consignes(tips: list[str]) -> None:
    """
    Affiche les consignes de qualité non respectées (encadré discret).
    Non-bloquant : la réponse est quand même affichée.
    """
    if not tips:
        return
    with st.expander("✍️ Conseils pour améliorer votre question", expanded=False):
        for tip in tips:
            st.markdown(f"- {tip}")


def _afficher_clarification_semantique(question: str) -> None:
    """Détection d'ambiguïté domaine-spécifique (src/engine/clarification.py)."""
    clarif = _verif_semantique(question)
    if not clarif:
        return
    with st.info(icon="💡", body=""):
        st.markdown(f"**{clarif.message}**")
        for opt in clarif.options:
            st.markdown(f"- {opt}")
        if clarif.exemples:
            st.markdown("**Exemples :**")
            cols = st.columns(min(len(clarif.exemples), 3))
            for i, ex in enumerate(clarif.exemples):
                with cols[i % len(cols)]:
                    st.button(
                        ex, key=f"clarif_sem_{clarif.situation}_{i}",
                        on_click=_set_pending, args=(ex,),
                        use_container_width=True,
                    )


def _afficher_smart_clarification(question: str, key_suffix: str = "") -> tuple[bool, bool]:
    """
    Analyse intelligente de la question : fautes, inversions, imprécisions.
    Affiche une carte premium "Vouliez-vous dire ?" avec bouton de confirmation.

    Retourne un tuple (blocked, showed_something) :
      - blocked=True  → correction auto appliquée, la réponse doit être bloquée
      - showed_something=True → une carte a été affichée (évite double clarification)
    Pour compatibilité, reste truthy/falsy via __bool__ du premier élément.
    """
    result: SmartClarification | None = _smart_analyse(question)
    if not result:
        return False, False

    # ── Carte de clarification premium ───────────────────────────────────────
    cat_icons = {
        "spelling":   "✏️",
        "inversion":  "🔄",
        "incomplete": "📅",
        "ambiguous":  "❓",
    }
    icon = cat_icons.get(result.category, "💡")

    container_class = {
        "spelling":   "smart-clarif-spelling",
        "inversion":  "smart-clarif-inversion",
        "incomplete": "smart-clarif-incomplete",
        "ambiguous":  "smart-clarif-ambiguous",
    }.get(result.category, "smart-clarif-default")

    # HTML de la carte (rendu premium)
    corrections_html = ""
    if result.corrections:
        corrections_html = "<ul class='clarif-corrections'>"
        for orig, fixed in result.corrections:
            corrections_html += f"<li><s>{orig}</s> → <strong>{fixed}</strong></li>"
        corrections_html += "</ul>"

    reformulation_html = ""
    if result.has_change:
        reformulation_html = (
            f"<div class='clarif-reformulation'>"
            f"<span class='clarif-did-you-mean'>Vouliez-vous dire&nbsp;?</span>"
            f"<span class='clarif-rewritten'>« {result.reformulated_q} »</span>"
            f"</div>"
        )

    st.markdown(
        f"""<div class="smart-clarif-card {container_class}">
            <div class="clarif-header">{icon} <strong>{result.explanation}</strong></div>
            {corrections_html}
            {reformulation_html}
        </div>""",
        unsafe_allow_html=True,
    )

    # Options de précision (ambiguïté / incomplétude)
    if result.options:
        opt_cols = st.columns(min(len(result.options), 2))
        for i, opt in enumerate(result.options[:4]):
            with opt_cols[i % len(opt_cols)]:
                # Construire un prompt enrichi avec l'option choisie
                enriched = f"{question} {opt.split('(')[0].strip().replace('**', '').lower()}"
                st.button(
                    opt, key=f"smart_opt_{key_suffix}_{i}",
                    on_click=_set_pending, args=(enriched,),
                    use_container_width=True,
                )

    # Bouton de confirmation pour reformulations (spelling / inversion)
    if result.has_change and result.needs_confirm:
        c1, c2, _ = st.columns([2, 2, 6])
        with c1:
            if st.button(
                "✅ Oui, utiliser cette formulation",
                key=f"smart_confirm_{key_suffix}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.pending_question = result.reformulated_q
                st.rerun()
        with c2:
            if st.button(
                "✏️ Modifier ma question",
                key=f"smart_edit_{key_suffix}",
                use_container_width=True,
            ):
                pass  # L'utilisateur retape dans le chat

    elif result.has_change and not result.needs_confirm:
        # Auto-application silencieuse pour corrections simples (1 faute orthographe).
        # st.rerun() interrompt immédiatement le rendu courant — la réponse à la version
        # originale (typo) n'est jamais générée, et la version corrigée est soumise.
        st.caption(f"✏️ *Correction automatique appliquée : « {result.reformulated_q} »*")
        st.session_state.pending_question = result.reformulated_q
        st.rerun()  # FIX : interrompt le rendu, bloque la réponse à la question typo

    return True, True  # carte affichée ; showed_something=True


_TYPING_HTML = (
    '<div class="typing-dots">'
    '<span></span><span></span><span></span>'
    '</div>'
)


def _stream_llm(
    question: str,
    prev_question: str | None,
    *,
    token_source=None,
    silent_switch: bool = False,
) -> str:
    """
    Stream la réponse LLM token par token.
    token_source : générateur alternatif (ex: ask_general_stream). Si None, utilise ask_stream.
    silent_switch : si True, supprime la notification de bascule de modèle.
    Retourne la réponse complète.
    """
    placeholder   = st.empty()
    switch_notice = st.empty()

    placeholder.markdown(_TYPING_HTML, unsafe_allow_html=True)

    full_answer = ""
    source = token_source if token_source is not None else ask_stream(question, prev_question=prev_question)

    for token in source:
        if token == SWITCH_MODEL_SENTINEL:
            full_answer = ""
            placeholder.markdown(_TYPING_HTML, unsafe_allow_html=True)
            if not silent_switch:
                switch_notice.info(
                    f"⏳ Modèle principal lent — passage à **{FALLBACK_MODEL}** "
                    "pour une réponse plus rapide…",
                    icon="🔄",
                )
            continue
        full_answer += token
        placeholder.markdown(full_answer + "▌")

    placeholder.markdown(full_answer)
    return full_answer


# ── Ressources (toutes @st.cache_resource — init unique par session) ───────────
con = get_db()
_   = get_index()
_ollama_status = initialiser_ollama()   # @st.cache_resource — réseau 1 seule fois

# Statut Ollama depuis le cache (évite un appel réseau sur chaque rerun)
_ollama_dispo    = _ollama_status.get("disponible", False)
_ollama_model    = _ollama_status.get("modele_actif") or "Démarrage auto"
_ollama_exe      = _ollama_status.get("exe")
_ollama_is_win   = _ollama_status.get("is_windows", True)
_ollama_is_cloud = _ollama_status.get("is_cloud", False)

# Sidebar stats en une seule fois pour toute la page
_sidebar_s = sidebar_stats()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⛏ Miny")
    st.caption("Assistant BI · Données & Documents")

    if _ollama_dispo:
        st.success(f"{_ollama_model} disponible", icon="🤖")
    elif _ollama_exe:
        st.warning("Ollama installé — démarrage auto…", icon="🤖")
    elif _ollama_is_cloud:
        st.error("LLM non configuré — ⚡ Analytique fonctionne", icon="🤖")
        if st.button("Configurer OLLAMA_HOST →", key="sb_install_guide",
                     use_container_width=True):
            st.session_state["params_highlight"] = "install"
            st.switch_page("pages/4_Parametres.py")
    else:
        st.error("Ollama non installé — ⚡ Analytique fonctionne", icon="🤖")
        if st.button("Installer Ollama →", key="sb_install_guide",
                     use_container_width=True):
            st.session_state["params_highlight"] = "install"
            st.switch_page("pages/4_Parametres.py")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑 Effacer", use_container_width=True,
                     help="Effacer l'historique"):
            st.session_state.messages = []
            st.session_state.response_times = []
            st.rerun()
    with c2:
        if st.button("🔄 Réindexer", use_container_width=True,
                     help="Reconstruire l'index après ajout de données"):
            with st.spinner("Reconstruction…"):
                rebuild_index()
                close_db()
                st.cache_resource.clear()
                st.cache_data.clear()
            st.success("Index reconstruit !")

    st.divider()

    if not _sidebar_s.get("error") and _sidebar_s.get("years"):
        _yr = " · ".join(str(y) for y in _sidebar_s["years"])
        st.caption(f"📅 Années : **{_yr}**")
        st.caption(f"📦 {len(_sidebar_s['tables'])} tables disponibles")

    # ── Compteur messages + rappel historique ─────────────────────────────────
    _n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")
    if _n_user > 0:
        st.caption(f"💬 **{_n_user}** question{'s' if _n_user > 1 else ''} dans la session")
        if _n_user >= 6:
            st.info(
                "L'historique est long — les réponses peuvent ralentir.\n\n"
                "Cliquez **🗑 Effacer** pour repartir sur une page vide.",
                icon="💡",
            )

    st.divider()

    # ── Réponses sauvegardées ─────────────────────────────────────────────────
    _saved = st.session_state.saved_responses
    if _saved:
        with st.expander(f"📌 Sauvegardées ({len(_saved)})", expanded=False):
            for _si, _sv in enumerate(_saved):
                st.markdown(f"**{_sv['question'][:55]}{'…' if len(_sv['question']) > 55 else ''}**")
                st.caption(_sv["timestamp"])
                _sc1, _sc2 = st.columns(2)
                with _sc1:
                    if st.button("🔄 Relancer", key=f"sv_rerun_{_si}",
                                 use_container_width=True):
                        st.session_state.pending_question = _sv["question"]
                        st.rerun()
                with _sc2:
                    if st.button("🗑 Supprimer", key=f"sv_del_{_si}",
                                 use_container_width=True):
                        st.session_state.saved_responses.pop(_si)
                        st.rerun()
                st.caption(
                    _sv["answer"][:180] + "…"
                    if len(_sv["answer"]) > 180
                    else _sv["answer"]
                )
                if _si < len(_saved) - 1:
                    st.divider()

    st.divider()

    with st.expander("💡 Comment poser une question"):
        st.markdown("**Données analytiques** (⚡ instantané)")
        st.code("[Sujet] + [Période] + [Détail]", language=None)
        st.markdown("""
- `Tonnage par mois en 2026`
- `Pannes de la trencher TRS 296`
- `Carburant par engin en 2024`
- `Heures machine en 2025`

**Raccourcis :** `S17` · `T3` · `S1-S6` · `TRENCHER TRS N°296`
""")
        st.markdown("**Autres modes** (🤖 Ollama requis, 10–60 s)")
        st.markdown("""
- 🔢 `Calculer 15% de 3500` · `CAGR de 1200 à 1850 en 3 ans`
- 🏭 `Quelles normes ISO pour une mine ?`
- 💬 `Bonjour` · `Quelle est la date du lundi dernier ?`
""")
        st.caption("📖 Guide complet → [Documentation](pages/2_Documentation.py)")

# ── Zone principale ────────────────────────────────────────────────────────────
_dot_cls = "ollama-dot" if _ollama_dispo else "ollama-dot offline"
_h_model = _ollama_model
st.markdown(f"""
<div class="miny-header">
    <div>
        <div class="header-title">⛏ Miny — Assistant BI</div>
        <div class="header-sub">Données · Calculs · Expertise · Questions générales</div>
    </div>
    <div class="ollama-badge">
        <span class="{_dot_cls}"></span>
        🤖 {_h_model}
    </div>
</div>
""", unsafe_allow_html=True)

# Ancre invisible en haut de page (cible du bouton scroll)
st.markdown('<div id="miny-chat-top"></div>', unsafe_allow_html=True)

st.markdown("---")

# Exemples par catégorie
with st.expander("🗂 Questions exemples", expanded=(not st.session_state.messages)):
    st.caption("Parcourez les catégories ci-dessous et cliquez sur un exemple pour l'envoyer directement dans le chat.")
    ex_tabs = st.tabs(list(EXAMPLES_BY_CAT.keys()))
    for ci, (ex_tab, (cat, examples)) in enumerate(zip(ex_tabs, EXAMPLES_BY_CAT.items())):
        with ex_tab:
            cols = st.columns(3)
            for i, (label, question) in enumerate(examples):
                cols[i % 3].button(
                    label, key=f"ex_{ci}_{i}",
                    use_container_width=True,
                    on_click=_set_pending, args=(question,),
                )

st.markdown("---")

# Historique du chat
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            _render_assistant(msg["content"], msg.get("type", "llm"))

            # ── Barre d'actions sous chaque réponse ───────────────────────
            _fb = st.session_state.get("feedback", {})
            # Trouver la question utilisateur associée
            _assoc_q = (
                st.session_state.messages[idx - 1]["content"]
                if idx > 0 and st.session_state.messages[idx - 1]["role"] == "user"
                else None
            )
            _ac1, _ac2, _ac3, _ac4 = st.columns([1, 1, 2, 8])
            with _ac1:
                st.button("👍", key=f"fb_up_{idx}",
                          help="Réponse satisfaisante",
                          type="primary" if _fb.get(idx) == 1 else "secondary",
                          on_click=_set_feedback, args=(idx, 1))
            with _ac2:
                st.button("👎", key=f"fb_dn_{idx}",
                          help="Réponse insuffisante",
                          type="primary" if _fb.get(idx) == -1 else "secondary",
                          on_click=_set_feedback, args=(idx, -1))
            with _ac3:
                if st.button("💾 Sauvegarder", key=f"save_{idx}",
                             help="Sauvegarder cette réponse pour la retrouver plus tard"):
                    _save_response(
                        _assoc_q or "Question",
                        msg["content"],
                        msg.get("type", "llm"),
                    )
                    st.toast("Réponse sauvegardée !", icon="💾")

            # Message contextuel feedback
            if _fb.get(idx) == 1:
                st.caption("✅ Merci !")
            elif _fb.get(idx) == -1:
                st.info(
                    "Essayez de :\n"
                    "- Préciser la période (*en 2026*, *au mois de mars*)\n"
                    "- Nommer l'engin ou la table\n"
                    "- Reformuler avec des mots-clés métier",
                    icon="💡",
                )
        else:
            # Message utilisateur + bouton relancer
            st.markdown(msg["content"])
            _rc1, _rc2 = st.columns([2, 10])
            with _rc1:
                if st.button("↩ Relancer", key=f"rerun_q_{idx}",
                             help="Poser à nouveau cette question"):
                    st.session_state.pending_question = msg["content"]
                    st.rerun()

# Rappel fraîcheur des données (réutilise _sidebar_s déjà chargé)
if not _sidebar_s.get("error") and _sidebar_s.get("freshness"):
    _key_tables = ["descente_minerai", "excavation", "objectifs", "journal"]
    _parts = [
        f"**{t.replace('_', ' ')}** {_sidebar_s['freshness'][t]}"
        for t in _key_tables if t in _sidebar_s["freshness"]
    ]
    if _parts:
        st.caption("📅 Dernières données : " + " · ".join(_parts))

st.caption("Pas d'idée par où commencer ? Voici quelques questions types :")
if _ollama_dispo:
    st.caption(
        "⚡ *Tonnage par mois 2026* · *Pannes TRS 296* · *Carburant 2024*  "
        "· 🔢 *15% de 3500* · 🏭 *Normes ISO mine* · 💬 *Bonjour*"
    )
else:
    st.caption(
        "⚡ *Tonnage par mois 2026* · *Pannes TRS 296* · *Carburant 2024*"
    )
    st.caption(
        "🔢 *15% de 3500* · 🏭 *Normes ISO mine* · 💬 *Bonjour*  "
        "— *(nécessitent Ollama — non installé)*"
    )

# ── Saisie ─────────────────────────────────────────────────────────────────────
pending = st.session_state.pop("pending_question", None)
prompt  = st.chat_input("Discutons de vos données — posez une question sur la production, les pannes, le carburant…") or pending

if prompt:
    prev_q = _last_user_question()
    st.session_state.messages.append({"role": "user", "content": prompt})

    # ── Détection multi-question ───────────────────────────────────────────
    _effective_prompt, _multi_q_remainder = _split_multi_question(prompt)

    # ── Routing intelligent (core/router.py) ──────────────────────────────
    route = _router(_effective_prompt, list(_list_tables(con)))

    # Enrichir les questions_suivi avec les années disponibles
    if route.get("clarif_type"):
        _years = _sidebar_s.get("years", [])
        route["questions_suivi"] = _gen_suivi(
            route["clarif_type"],
            route["ctx"],
            _effective_prompt,
            annees_disponibles=_years,
            tables_candidates=route.get("tables_candidates"),
        )

    # 0. Analyse intelligente de la question (fautes, inversions, imprécisions)
    _smart_blocked, _smart_showed = _afficher_smart_clarification(
        _effective_prompt,
        key_suffix=str(len(st.session_state.messages)),
    )

    # 1. Suggestions contextuelles du router
    if not _smart_blocked and route.get("questions_suivi"):
        afficher_clarification(route["questions_suivi"], route["clarif_type"])

    # 2. Ambiguïté sémantique — seulement si smart_clarification n'a rien affiché
    #    (évite deux cartes de clarification overlappantes sur la même ambiguïté)
    if not _smart_showed:
        _afficher_clarification_semantique(_effective_prompt)

    # 3. Conseils qualité
    if not _smart_blocked:
        _afficher_consignes(_verif_qualite(_effective_prompt))

    with st.chat_message("user"):
        st.markdown(prompt)
        _rrun_c1, _ = st.columns([2, 10])
        with _rrun_c1:
            if st.button("↩ Relancer", key="rerun_current",
                         help="Poser à nouveau cette question"):
                st.session_state.pending_question = prompt
                st.rerun()

    # FIX 1 : ne générer de réponse QUE si la correction auto n'a pas interrompu le rendu.
    # Normalement st.rerun() dans _afficher_smart_clarification stoppe l'exécution,
    # mais on garde ce guard comme filet de sécurité supplémentaire.
    if _smart_blocked:
        st.stop()

    with st.chat_message("assistant"):
        start = time.time()

        # Avertissement multi-question (non bloquant)
        if _multi_q_remainder:
            st.info(
                f"**2 questions détectées** — je traite la première.\n\n"
                f"Posez ensuite : *\"{_multi_q_remainder}\"*",
                icon="💡",
            )

        # ── 0a. Calcul mathématique ────────────────────────────────────────
        if _is_math_question(_effective_prompt):
            if not _ollama_dispo:
                answer = _show_ollama_warning(str(len(st.session_state.messages)))
                rtype  = "error"
            else:
                st.markdown('<span class="badge-math">🔢 Calcul</span>',
                            unsafe_allow_html=True)
                answer = _stream_llm(
                    _effective_prompt, None,
                    token_source=ask_math_stream(_effective_prompt),
                    silent_switch=True,
                )
                rtype = "math"

        # ── 0b. Expertise industrielle ────────────────────────────────────
        elif _is_expert_question(_effective_prompt):
            if not _ollama_dispo:
                answer = _show_ollama_warning(str(len(st.session_state.messages)))
                rtype  = "error"
            else:
                st.markdown('<span class="badge-expert">🏭 Expertise industrie</span>',
                            unsafe_allow_html=True)
                answer = _stream_llm(
                    _effective_prompt, None,
                    token_source=ask_expert_stream(_effective_prompt),
                    silent_switch=True,
                )
                rtype = "expert"

        # ── 0c. Question générale ─────────────────────────────────────────
        elif _is_general_question(_effective_prompt):
            if not _ollama_dispo:
                answer = _show_ollama_warning(str(len(st.session_state.messages)))
                rtype  = "error"
            else:
                st.markdown('<span class="badge-general">💬 Réponse générale</span>',
                            unsafe_allow_html=True)
                answer = _stream_llm(
                    _effective_prompt, None,
                    token_source=ask_general_stream(_effective_prompt),
                    silent_switch=True,
                )
                rtype = "general"

        # ── Pipeline LLM direct (documents RAG) — utilise FALLBACK_MODEL ────
        elif route["pipeline"] == "llm":
            if not _ollama_dispo:
                answer = _show_ollama_warning(str(len(st.session_state.messages)))
                rtype  = "error"
            else:
                st.markdown(f'<span class="badge-llm">🤖 {_ollama_model}</span>',
                            unsafe_allow_html=True)
                answer = _stream_llm(
                    _effective_prompt, prev_q,
                    token_source=ask_fast_stream(_effective_prompt, prev_q),
                    silent_switch=True,
                )
                rtype  = "llm"

        else:
            # ── Pipeline analytique (DuckDB — pas d'Ollama requis) ────────
            analytics_answer = _analytics.handle(con, _effective_prompt)

            if not analytics_answer and prev_q and _is_followup(_effective_prompt):
                analytics_answer = _analytics.handle(con, f"{prev_q} {_effective_prompt}")

            if analytics_answer:
                # ── Réponse du handler générique (table nouvellement importée) ──
                if isinstance(analytics_answer, _GenericResult):
                    _gen    = analytics_answer
                    answer  = _gen.response
                    rtype   = "generic"

                    # Alerte : confiance faible (table peut-être pas la bonne)
                    if _gen.confidence < 0.55:
                        st.warning(
                            f"❓ Résultat issu de la table `{_gen.table}` "
                            f"(détection automatique, confiance {_gen.confidence:.0%}). "
                            "Si ce n'est pas la bonne source, précisez le sujet de votre question.",
                            icon="🔍",
                        )

                    # Alerte limite fonctionnelle (pas de date, ambiguïté de colonnes…)
                    if _gen.limit_notice:
                        st.info(_gen.limit_notice, icon="💡")

                    # Réponse
                    _display = re.sub(r"\n\n_📋[^_]*_\s*$", "", answer).rstrip()
                    _render_assistant(_display or answer, "generic")

                    # Questions de suivi contextuelles
                    if _gen.questions_suivi:
                        afficher_clarification(
                            _gen.questions_suivi,
                            "generic_followup",
                            message="Affiner l'analyse :",
                        )

                # ── Réponse d'un handler dédié (analytique standard) ───────────
                else:
                    _display = re.sub(r"\n\n_📋[^_]*_\s*$", "", analytics_answer).rstrip()
                    _render_assistant(_display or analytics_answer, "analytics")
                    answer = analytics_answer
                    rtype  = "analytics"

                _cap = _route_caption(route)
                if _cap:
                    st.caption(_cap)
            else:
                # LLM fallback
                if not _ollama_dispo:
                    answer = _show_ollama_warning(str(len(st.session_state.messages)))
                    rtype  = "error"
                else:
                    st.markdown(f'<span class="badge-llm">🤖 {_ollama_model}</span>',
                                unsafe_allow_html=True)
                    # ask_fast_stream = FALLBACK_MODEL, évite les timeouts PRIMARY_MODEL
                    answer = _stream_llm(
                        _effective_prompt, prev_q,
                        token_source=ask_fast_stream(_effective_prompt, prev_q),
                        silent_switch=True,
                    )
                    rtype  = "llm"

        elapsed = time.time() - start
        st.session_state.response_times.append(elapsed)
        st.caption(f"_{_fmt_duration(elapsed)}_")

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "type": rtype,
    })

# ── Bouton fixe "Retour en haut" ───────────────────────────────────────────────
# Affiché seulement quand l'historique est assez long pour justifier le scroll.
if len(st.session_state.messages) >= 4:
    st.markdown(
        """
<div id="miny-scroll-top">
  <a href="#miny-chat-top"
     onclick="
       var candidates=[
         '[data-testid=\\'stAppViewBlockContainer\\']',
         '[data-testid=\\'stMainBlockContainer\\']',
         '.main'
       ];
       candidates.forEach(function(s){
         var el=document.querySelector(s);
         if(el)el.scrollTop=0;
       });
       window.scrollTo(0,0);
     "
     title="Remonter en haut"
     style="
       display:inline-flex;align-items:center;justify-content:center;
       width:42px;height:42px;border-radius:50%;
       background:#1B4F72;color:white;
       font-size:20px;font-weight:700;
       text-decoration:none;
       box-shadow:0 2px 10px rgba(27,79,114,.4);
       opacity:0.88;
       transition:opacity .2s,background .2s;
     "
     onmouseover="this.style.opacity='1';this.style.background='#2471A3';"
     onmouseout="this.style.opacity='0.88';this.style.background='#1B4F72';"
  >↑</a>
</div>
        """,
        unsafe_allow_html=True,
    )
