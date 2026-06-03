"""
Miny — Point d'entrée principal.

Lancement : .venv\\Scripts\\python.exe -m streamlit run app.py

Navigation gérée par st.navigation() — chaque page définit sa propre
configuration (set_page_config) et son contenu sidebar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

pg = st.navigation(
    [
        st.Page("pages/0_Accueil.py",       title="Accueil",       icon="🏠", default=True),
        st.Page("pages/1_Assistant.py",      title="Assistant",     icon="💬"),
        st.Page("pages/2_Documentation.py",  title="Documentation", icon="📖"),
        st.Page("pages/3_Donnees.py",        title="Données",       icon="📊"),
        st.Page("pages/4_Parametres.py",     title="Paramètres",    icon="⚙️"),
    ]
)
pg.run()
