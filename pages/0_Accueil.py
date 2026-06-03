"""
Miny — Accueil
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from core.data_loader import load_css, sidebar_stats
from core.ollama_client import initialiser_ollama

st.set_page_config(
    page_title="Miny — Assistant BI",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

_ollama_status = initialiser_ollama()
_ollama_ok    = _ollama_status.get("disponible", False)
_ollama_model = _ollama_status.get("modele_actif") or "—"
_ollama_exe   = _ollama_status.get("exe")

for _k, _v in {
    "messages": [],
    "response_times": [],
    "pending_question": None,
    "feedback": {},
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⛏ Miny")
    st.caption("Assistant BI · Mine de bauxite R2M CI")
    if _ollama_ok:
        st.success(f"{_ollama_model} disponible", icon="🤖")
    elif _ollama_exe:
        st.warning("Ollama installé — démarrage automatique en cours…", icon="🤖")
    else:
        st.error("Ollama non installé — ⚡ Analytique fonctionne", icon="🤖")
        if st.button("Installer Ollama →", key="sb_install_guide",
                     use_container_width=True):
            st.session_state["params_highlight"] = "install"
            st.switch_page("pages/4_Parametres.py")
    st.divider()
    _s = sidebar_stats()
    if _s.get("years"):
        st.caption("📅 Années : **" + " · ".join(str(y) for y in _s["years"]) + "**")

# ── En-tête ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#1B4F72,#2471A3);
            padding:28px 32px;border-radius:12px;margin-bottom:24px;color:white;
            box-shadow:0 2px 10px rgba(27,79,114,.3)">
  <h1 style="margin:0;font-size:2rem;font-weight:700">⛏ Miny</h1>
  <p style="margin:6px 0 0 0;opacity:.9;font-size:1rem">
      Votre assistant BI minier — données, calculs, expertise et documents en français
  </p>
</div>
""", unsafe_allow_html=True)

# ── Les 4 modes ───────────────────────────────────────────────────────────────
st.markdown("#### Posez n'importe quelle question — Miny choisit le bon moteur automatiquement")

m1, m2, m3, m4 = st.columns(4)
_card = (
    "padding:14px 16px;border-radius:10px;height:100%;border-left:4px solid {color};"
    "background:{bg};margin-bottom:4px"
)
m1.markdown(
    f'<div style="{_card.format(color="#27AE60", bg="#f0faf3")}">'
    "<b>⚡ Analytique</b><br>"
    "<small style='color:#555'>Tonnage · Pannes · Carburant · Objectifs · PGES · Heures machine</small>"
    "</div>", unsafe_allow_html=True,
)
m2.markdown(
    f'<div style="{_card.format(color="#283593", bg="#f0f1fa")}">'
    "<b>🔢 Calcul</b><br>"
    "<small style='color:#555'>Arithmétique · Pourcentages · CAGR · ROI · Conversions d'unités</small>"
    "</div>", unsafe_allow_html=True,
)
m3.markdown(
    f'<div style="{_card.format(color="#e65100", bg="#fff8f0")}">'
    "<b>🏭 Expertise</b><br>"
    "<small style='color:#555'>Normes ISO · Référentiels · Bonnes pratiques · Réglementation minière</small>"
    "</div>", unsafe_allow_html=True,
)
m4.markdown(
    f'<div style="{_card.format(color="#6a1b9a", bg="#faf0ff")}">'
    "<b>💬 Général</b><br>"
    "<small style='color:#555'>Salutations · Dates · Culture générale · Questions hors-données</small>"
    "</div>", unsafe_allow_html=True,
)

# ── Première utilisation ──────────────────────────────────────────────────────
if not _ollama_ok:
    st.warning(
        "**Première utilisation ?** Ollama n'est pas encore démarré sur ce PC.\n\n"
        "Rendez-vous dans **⚙️ Paramètres** pour le guide d'installation en 4 étapes "
        "(gratuit, modèles locaux, aucun abonnement).",
        icon="🚀",
    )
    if st.button("⚙️ Ouvrir le guide de démarrage →", type="primary"):
        st.session_state["params_highlight"] = "install"
        st.switch_page("pages/4_Parametres.py")
    st.divider()

# ── Navigation ────────────────────────────────────────────────────────────────
st.markdown("#### Navigation")

col1, col2, col3, col4 = st.columns(4)

_nav_card = (
    "text-align:center;padding:20px 16px 12px 16px;background:#fff;"
    "border:2px solid {color};border-radius:10px;margin-bottom:8px"
)
with col1:
    st.markdown(
        f'<div style="{_nav_card.format(color="#1B4F72")}">'
        '<div style="font-size:2rem">💬</div>'
        '<div style="font-weight:700;color:#1B4F72">Assistant</div>'
        '<div style="font-size:.8rem;color:#666">Chat analytique et IA</div>'
        "</div>", unsafe_allow_html=True,
    )
    if st.button("Ouvrir →", key="nav_assistant", use_container_width=True):
        st.switch_page("pages/1_Assistant.py")

with col2:
    st.markdown(
        f'<div style="{_nav_card.format(color="#2471A3")}">'
        '<div style="font-size:2rem">📖</div>'
        '<div style="font-weight:700;color:#2471A3">Documentation</div>'
        '<div style="font-size:.8rem;color:#666">Guides & exemples</div>'
        "</div>", unsafe_allow_html=True,
    )
    if st.button("Ouvrir →", key="nav_doc", use_container_width=True):
        st.switch_page("pages/2_Documentation.py")

with col3:
    st.markdown(
        f'<div style="{_nav_card.format(color="#27AE60")}">'
        '<div style="font-size:2rem">📊</div>'
        '<div style="font-weight:700;color:#27AE60">Données</div>'
        '<div style="font-size:.8rem;color:#666">Tables & documents</div>'
        "</div>", unsafe_allow_html=True,
    )
    if st.button("Ouvrir →", key="nav_data", use_container_width=True):
        st.switch_page("pages/3_Donnees.py")

with col4:
    st.markdown(
        f'<div style="{_nav_card.format(color="#F39C12")}">'
        '<div style="font-size:2rem">⚙️</div>'
        '<div style="font-weight:700;color:#F39C12">Paramètres</div>'
        '<div style="font-size:.8rem;color:#666">Import · Ollama · Config</div>'
        "</div>", unsafe_allow_html=True,
    )
    if st.button("Ouvrir →", key="nav_params", use_container_width=True):
        st.switch_page("pages/4_Parametres.py")

# ── Déploiement cloud ─────────────────────────────────────────────────────────
with st.expander("☁️ Déploiement Streamlit Cloud — ce qu'il faut savoir", expanded=False):
    st.markdown("""
**Mode ⚡ Analytique (DuckDB)** : fonctionne partout, y compris sur Streamlit Cloud. Aucune dépendance externe.

**Modes 🔢 Calcul · 🏭 Expertise · 💬 Général · 🤖 Documents** : nécessitent **Ollama**, qui tourne en local.
Sur Streamlit Cloud, Ollama n'est **pas disponible** — ces modes retourneront une erreur.

**Options pour déployer avec LLM :**
1. **Serveur dédié** (VPS, Docker) — installez Ollama et pointez `OLLAMA_BASE_URL` vers votre serveur
2. **API cloud** — remplacez Ollama par Groq (gratuit, rapide) ou OpenAI dans `core/ollama_client.py`
3. **Usage local uniquement** — démarrez l'app sur votre poste avec `.venv\\Scripts\\python.exe -m streamlit run app.py`
""")
