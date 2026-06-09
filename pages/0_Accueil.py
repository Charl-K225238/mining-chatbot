"""
Miny — Accueil
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from core.data_loader import load_css, sidebar_stats

st.set_page_config(
    page_title="Miny — Assistant BI",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

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
      Votre assistant BI minier — interrogez vos données minières en français
  </p>
</div>
""", unsafe_allow_html=True)

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
        '<div style="font-size:.8rem;color:#666">Chat analytique</div>'
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
        '<div style="font-size:.8rem;color:#666">Import des données</div>'
        "</div>", unsafe_allow_html=True,
    )
    if st.button("Ouvrir →", key="nav_params", use_container_width=True):
        st.switch_page("pages/4_Parametres.py")

