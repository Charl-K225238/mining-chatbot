import sys
from pathlib import Path

# Ajouter la racine du projet au PYTHONPATH pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import logging
from datetime import datetime
from app.Prompts import get_system_prompt
from app.RagEngine import RAGEngine
from app.FileProcessor import FileProcessor
from abbreviations import normalize_abbreviations
import time

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    st.error("Le module 'ollama' n'est pas installé. Veuillez installer les dépendances avec 'pip install -r requirements-local.txt' et relancer l'application.")

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Miny - IA Minieres Optimisee", layout="wide")

st.title("⚡ Miny - Optimisee")
st.markdown("*Assistant IA rapide pour donnees minieres*")

# Initialisation des composants
if "rag_engine" not in st.session_state:
    st.session_state.rag_engine = RAGEngine()

if "file_processor" not in st.session_state:
    st.session_state.file_processor = FileProcessor()

if "response_times" not in st.session_state:
    st.session_state.response_times = []

# Initialisation de l'état de session
if "messages" not in st.session_state:
    st.session_state.messages = []
    logger.info("Session initialized")

# Afficher le message de bienvenue
st.markdown("""
### ⚡ Bienvenue dans Miny!
Assistant IA rapide pour donnees minieres

**📊 Data:** Excavation Q1/Q2/Q3 | Carburant | Budget | Qualite | Personnel | PGES

**⚡ Rapide:**
- "T1 tonnage?" → Reponse instant
- "Compare Q1 vs Q2?" → Comparaison rapide  
- "Efficacite T/L?" → Calcul immed

*Francais | Tables transparentes | Dates verifiees*
""")

# Sidebar pour le chargement de fichiers
st.sidebar.header("📁 Chargement de Documents")
uploaded_file = st.sidebar.file_uploader(
    "Chargez vos fichiers (PDF, DOCX, TXT, Excel)",
    type=["pdf", "docx", "doc", "txt", "xlsx", "xls"],
    help="Les fichiers seront stockés dans data/raw/ et utilisés pour enrichir les réponses."
)

if uploaded_file:
    filename = uploaded_file.name
    with st.sidebar:
        with st.spinner("Traitement du fichier..."):
            file_path = st.session_state.file_processor.save_file(uploaded_file, filename)
            processed = st.session_state.file_processor.process_file(file_path)
            if "error" in processed:
                st.error(f"Erreur lors du traitement: {processed['error']}")
            else:
                st.success(f"Fichier '{filename}' traité avec succès!")
                st.info(f"Type: {processed.get('type', 'inconnu')}")

# Fonction pour obtenir la réponse du modèle
def get_model_response(prompt):
    if not OLLAMA_AVAILABLE:
        return "Erreur : Ollama indisponible"

    start_time = time.time()

    # Etape 1: Analyse + normalisation abbreviations
    with st.spinner("⚡ Traitement..."):
        time.sleep(0.3)

    # Etape 2: Recuperation contexte optimise
    with st.spinner("📊 Contexte..."):
        augmented_prompt, table_metadata, normalized_query = st.session_state.rag_engine.process_query(prompt)
        time.sleep(0.3)

    # Etape 3: Generation reponse
    with st.spinner("🤖 Miny pense..."):
        try:
            logger.info(f"Query: {prompt}")
            if prompt != normalized_query:
                logger.info(f"Normalized: {normalized_query}")
            system_prompt = get_system_prompt()

            response = ollama.chat(
                model="mistral",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": augmented_prompt
                    }
                ]
            )

            answer = response["message"]["content"]
            logger.info("Response generated successfully")

            # Calcul du temps de reponse
            response_time = time.time() - start_time
            st.session_state.response_times.append(response_time)

            # Affichage des metadonnees des tables utilisees
            if table_metadata:
                st.markdown("---")
                st.markdown("**📊 Sources de donnees utilisees:**")
                for meta in table_metadata:
                    st.caption(f"✓ {meta['name']} (mise a jour: {meta['date']})")
                st.markdown("---")

            return answer
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Désolé, une erreur s'est produite lors de la génération de la réponse."

# Affichage des statistiques
if st.session_state.response_times:
    avg_time = sum(st.session_state.response_times) / len(st.session_state.response_times)
    st.sidebar.metric("Temps moyen de réponse", f"{avg_time:.2f}s")

# Affichage historique
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Saisie utilisateur
prompt = st.chat_input("Posez une question sur les données minières...")

if prompt:
    # Ajouter le message utilisateur
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "timestamp": datetime.now()}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Obtenir et afficher la réponse
    with st.chat_message("assistant"):
        answer = get_model_response(prompt)
        st.markdown(answer)

    # Ajouter la réponse à l'historique
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "timestamp": datetime.now()}
    )