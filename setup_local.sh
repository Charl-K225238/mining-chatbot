#!/bin/bash
# Setup Local Mistral 7B Environment - Linux/Mac
# Utilise l'environnement virtuel .venv existant
# Version: 2026-05-07 (Derniere version Mistral)

echo ""
echo "========================================"
echo "[SETUP LOCAL MISTRAL 7B - .venv]"
echo "========================================"
echo ""

# Verifier .venv existe
if [ ! -d ".venv" ]; then
    echo "[ERROR] Dossier .venv n'existe pas"
    echo "Creer d'abord: python3 -m venv .venv"
    exit 1
fi

echo "[OK] .venv detecte"
echo ""

# Activer .venv
echo "[*] Activation .venv..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    echo "[ERROR] Impossible activer .venv"
    exit 1
fi

echo "[OK] .venv active"
echo ""

# Verifier Python dans .venv
python3 --version
if [ $? -ne 0 ]; then
    echo "[ERROR] Python3 non trouve dans .venv"
    exit 1
fi

echo "[OK] Python3 detecte"
echo ""

# Mettre a jour pip dans .venv
echo "[*] Mise a jour pip..."
python3 -m pip install --upgrade pip

echo ""
echo "[*] Installation dependances..."
pip install -r requirements-local.txt

if [ $? -ne 0 ]; then
    echo "[ERROR] Erreur installation dependances"
    exit 1
fi

echo ""
echo "[OK] Dependances installees"
echo ""

# Verifier Ollama CLI
echo "[*] Verification Ollama CLI..."
if ! command -v ollama &> /dev/null; then
    echo "[WARNING] Ollama CLI n'est pas installe"
    echo "Telecharger: https://ollama.ai/download"
    echo ""
else
    echo "[OK] Ollama CLI detecte"
    ollama --version
fi

echo ""
echo "========================================"
echo "[SETUP TERMINE - .venv PRET]"
echo "========================================"
echo ""
echo "Commandes suivantes:"
echo "  1. Ollama: ollama serve (dans nouveau terminal)"
echo "  2. Mistral: ollama pull mistral (quand Ollama running)"
echo "  3. Streamlit: streamlit run streamlit_app.py"
echo ""
echo ".venv deja active - vous pouvez executer directement!"
echo ""
