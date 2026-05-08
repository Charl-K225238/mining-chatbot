"""
Chatbot Interrogation Données - Streamlit + Mistral LLM
Déployé pour interroger le catalogue de données minières
"""

import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path

# Configuration page
st.set_page_config(
    page_title="💬 Chatbot Interrogation Données",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SCHEMA_JSON = BASE_DIR / "schema.json"
RELATIONSHIPS_PY = BASE_DIR / "relationships.py"
CALENDAR_CSV = BASE_DIR / "calendar.csv"
CHATBOT_CONTEXT = BASE_DIR / "chatbot_context.md"
QUERY_PATTERNS = BASE_DIR / "query_patterns.md"

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────

@st.cache_resource
def load_schema():
    """Charger le schéma JSON"""
    try:
        with open(SCHEMA_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Erreur chargement schema: {e}")
        return None

@st.cache_resource
def load_calendar():
    """Charger la table calendrier"""
    try:
        return pd.read_csv(CALENDAR_CSV)
    except Exception as e:
        st.error(f"Erreur chargement calendrier: {e}")
        return None

@st.cache_resource
def load_context():
    """Charger le contexte pour le LLM"""
    try:
        with open(CHATBOT_CONTEXT, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        st.error(f"Erreur chargement contexte: {e}")
        return ""

@st.cache_resource
def load_query_patterns():
    """Charger les patterns de requêtes"""
    try:
        with open(QUERY_PATTERNS, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        st.error(f"Erreur chargement patterns: {e}")
        return ""

# ─────────────────────────────────────────
# INTERFACE PRINCIPAL
# ─────────────────────────────────────────

def main():
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        # LLM Model Selection
        llm_provider = st.selectbox(
            "Modèle LLM",
            ["Mistral", "OpenAI", "Local LLM"],
            help="Sélectionner le modèle de langage"
        )
        
        temperature = st.slider(
            "Température (Créativité)",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="0=Déterministe, 1=Créatif"
        )
        
        max_tokens = st.number_input(
            "Tokens max pour réponse",
            min_value=100,
            max_value=4000,
            value=1500,
            step=100
        )
        
        st.divider()
        
        # Information sur le schéma
        schema = load_schema()
        if schema:
            st.subheader("📊 Statistiques Catalogue")
            
            # Compter les tables
            files = schema.get('files', [])
            st.metric("Fichiers documentés", len(files))
            
            # Compter les colonnes
            total_cols = sum(
                sum(len(sheet.get('columns', [])) for sheet in file.get('sheets', []))
                for file in files
            )
            st.metric("Colonnes analysées", total_cols)
            
            # Domaines
            domains = schema.get('domain_model', {})
            st.metric("Domaines métier", len(domains))
            
            st.divider()
            
            # Calendrier
            calendar = load_calendar()
            if calendar is not None:
                st.metric("Jours couverts", len(calendar))
                date_range = f"{calendar['Date'].min()} à {calendar['Date'].max()}"
                st.caption(f"📅 {date_range}")
    
    # Header Principal
    st.title("🤖 Chatbot Interrogation Données")
    st.markdown("""
    Posez vos questions sur les données minières en langage naturel.
    Le chatbot interrogera le catalogue et vous fournira une réponse structurée.
    """)
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "💬 Chat",
        "📚 Schéma",
        "❓ Exemples",
        "ℹ️ Guide"
    ])
    
    # ─────────────────────────────────────────
    # TAB 1: CHAT
    # ─────────────────────────────────────────
    with tab1:
        st.subheader("Posez votre question")
        
        # Input utilisateur
        user_query = st.text_area(
            "Votre question:",
            placeholder="Ex: Quel tonnage a été excavé en janvier 2024?",
            height=100
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            submit_btn = st.button("🔍 Analyser", use_container_width=True)
        
        with col2:
            clear_btn = st.button("🗑️ Effacer", use_container_width=True)
        
        with col3:
            st.info(
                "💡 Tipas: Soyez précis. "
                "Exemple: 'Tonnage excavé janvier 2024 par équipement'",
                icon="💡"
            )
        
        if clear_btn:
            st.session_state.chat_history = []
            st.rerun()
        
        # Historique chat
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        
        # Afficher l'historique
        st.subheader("Conversation")
        for i, (question, response, context) in enumerate(st.session_state.chat_history):
            with st.chat_message("user"):
                st.write(question)
            
            with st.chat_message("assistant"):
                st.write(response)
                
                with st.expander(f"📋 Contexte utilisé (Requête {i+1})"):
                    st.code(context, language="markdown")
        
        # Traiter la nouvelle requête
        if submit_btn and user_query:
            with st.spinner("🤔 Analyse en cours..."):
                # TODO: Intégration avec Mistral LLM
                # Pour l'instant, afficher un placeholder
                
                st.warning("""
                🚧 **Démo Mode** - Intégration LLM en cours
                
                **Étapes pour intégration Mistral:**
                1. Installer: `pip install mistral-client streamlit`
                2. Charger le contexte depuis `chatbot_context.md`
                3. Utiliser `relationships.py` pour clés de jointure
                4. Envoyer requête formatée au LLM
                5. Parser réponse structurée
                
                **Format prompt à utiliser:**
                ```
                Context: [chatbot_context.md]
                User Query: {user_query}
                Query Patterns: [query_patterns.md]
                Response Format: [Voir chatbot_context.md - FORMAT]
                ```
                """)
                
                # Simuler une réponse pour démo
                demo_response = f"""
                ### Analyse de Requête
                
                **Question traitée:** {user_query}
                
                **Tables identifiées:** Benene_1_Excavation, Calendrier
                
                **Approche:** 
                - Filtre: Calendrier.Année = 2024, Calendrier.Mois = 1
                - Agrégation: SUM(Tonnage)
                - Jointure: Excavation + Calendrier via Date
                
                **Limitations connues:**
                - Période couverte: 2023-2026
                - Doublons non filtrés
                - Types incohérents possibles
                
                ⚠️ *Cette démo requiert l'intégration Mistral LLM*
                """
                
                st.session_state.chat_history.append(
                    (user_query, demo_response, "Context utilisé")
                )
                
                st.rerun()
    
    # ─────────────────────────────────────────
    # TAB 2: SCHÉMA
    # ─────────────────────────────────────────
    with tab2:
        st.subheader("📊 Structure du Catalogue")
        
        schema = load_schema()
        if schema:
            # Vue globale
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🎯 Informations Générales")
                st.json({
                    "Title": schema['catalog']['title'],
                    "Version": schema['catalog']['version'],
                    "Objective": schema['catalog']['objective']
                })
            
            with col2:
                st.markdown("### 🗂️ Domaines Métier")
                domains = schema.get('domain_model', {})
                for domain, tables in domains.items():
                    st.write(f"**{domain}** ({len(tables)} tables)")
                    for table in tables:
                        st.caption(f"  • {table}")
            
            # Détail des relations
            st.markdown("### 🔗 Relations")
            relations = schema.get('relations', {})
            for category, rels in relations.items():
                st.write(f"**{category}**")
                for rel in rels:
                    st.caption(f"  → {rel}")
            
            # Table Calendrier
            st.markdown("### 📅 Table Calendrier")
            calendar_info = schema.get('calendar_table', {})
            st.write(f"**Description:** {calendar_info.get('description')}")
            st.write(f"**Colonnes:** {len(calendar_info.get('columns', []))}")
            
            with st.expander("Voir toutes les colonnes temporelles"):
                cols = calendar_info.get('columns', [])
                col_pairs = [cols[i:i+2] for i in range(0, len(cols), 2)]
                cols_display = st.columns(2)
                for i, pair in enumerate(col_pairs):
                    with cols_display[i % 2]:
                        for col in pair:
                            st.write(f"• {col}")
    
    # ─────────────────────────────────────────
    # TAB 3: EXEMPLES
    # ─────────────────────────────────────────
    with tab3:
        st.subheader("❓ Exemples de Requêtes")
        
        patterns = load_query_patterns()
        if patterns:
            # Parser et afficher patterns
            st.markdown(patterns[:3000] + "...")  # Aperçu
            
            with st.expander("Voir tous les patterns"):
                st.markdown(patterns)
    
    # ─────────────────────────────────────────
    # TAB 4: GUIDE
    # ─────────────────────────────────────────
    with tab4:
        st.subheader("ℹ️ Guide d'Utilisation")
        
        context = load_context()
        if context:
            # Afficher contexte par section
            sections = context.split("---")
            for section in sections[:5]:  # Premières sections
                if section.strip():
                    st.markdown(section)
            
            with st.expander("📖 Voir le guide complet"):
                st.markdown(context)
        
        st.divider()
        
        st.markdown("### 🔧 Installation & Déploiement")
        st.code("""
# Installation dépendances
pip install streamlit mistral-client pandas

# Démarrer l'application
streamlit run streamlit_app.py

# Déployer sur Streamlit Cloud
# 1. Push code sur GitHub
# 2. Connecter sur https://share.streamlit.io
# 3. Sélectionner repo et fichier principal
        """, language="bash")

if __name__ == "__main__":
    main()
