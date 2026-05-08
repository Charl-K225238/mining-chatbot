# 🤖 INSTALLATION LOCAL - Mistral 7B via Ollama

**Version:** 2026-05-07 (Dernière version Mistral)  
**Prérequis:** Environnement virtuel `.venv` existant

## 📋 Vue d'ensemble

Configuration complète pour exécuter **Mistral 7B localement** sans dépendre de l'API cloud.

### Architecture
```
Ollama (Local LLM Server)
    ↓
Mistral 7B Model (~4GB)
    ↓
Python Client (ollama library)
    ↓
Streamlit UI
```

### Prérequis
- **RAM:** 16GB minimum (recommandé 32GB)
- **Disque:** 20GB libre
- **OS:** Windows 10+, macOS 11+, Linux (Ubuntu 20.04+)
- **GPU (optionnel):** NVIDIA/AMD/Apple Silicon (accélération)

---

## 🚀 Installation Rapide

### Windows (avec .venv existant)

```bash
# 1. Activer .venv
.venv\Scripts\activate.bat

# 2. Exécuter script setup (installe dépendances dans .venv)
setup_local.bat

# 3. Télécharger Ollama
# Aller sur: https://ollama.ai/download
# Windows: Exécuter .exe installer

# 4. Vérifier installation
ollama --version

# 5. Démarrer service Ollama (dans NOUVEAU terminal)
ollama serve

# 6. Télécharger Mistral 7B (dans AUTRE terminal - Ollama doit tourner)
ollama pull mistral

# 7. Vérifier disponible
ollama list
# Output: mistral    latest    # ~4GB

# 8. Lancer Streamlit (dans NOUVEAU terminal - avec .venv actif)
streamlit run streamlit_app.py
```

### macOS (avec .venv existant)

```bash
# 1. Activer .venv
source .venv/bin/activate

# 2. Exécuter script setup (installe dépendances dans .venv)
bash setup_local.sh

# 3. Télécharger Ollama
# Aller sur: https://ollama.ai/download
# macOS: Télécharger .dmg

# 4. Vérifier installation
ollama --version

# 5. Démarrer service Ollama
ollama serve

# 6. Télécharger Mistral 7B (autre terminal - Ollama doit tourner)
ollama pull mistral

# 7. Lancer Streamlit (nouveau terminal - .venv actif)
streamlit run streamlit_app.py
```

### Linux (Ubuntu/Debian - avec .venv existant)

```bash
# 1. Activer .venv
source .venv/bin/activate

# 2. Exécuter script setup (installe dépendances dans .venv)
bash setup_local.sh

# 3. Installer Ollama
curl https://ollama.ai/install.sh | sh

# 4. Démarrer service Ollama
ollama serve

# 5. Télécharger Mistral 7B (autre terminal - Ollama doit tourner)
ollama pull mistral

# 6. Lancer Streamlit (nouveau terminal - .venv actif)
streamlit run streamlit_app.py
```

---

## 📦 DÉPENDANCES DÉTAILLÉES

### Essentielles (Automatiques via setup_local.bat/sh)
```
pandas>=2.1.4          # Data manipulation
numpy>=1.24.3          # Numeric computing
```

### Interface
```
streamlit>=1.31.1      # Web UI framework
streamlit-chat>=0.1.1  # Chat component
```

### Local LLM - DERNIÈRE VERSION
```
ollama>=0.1.0          # Client Python pour Ollama (version récente)
langchain>=0.1.0       # Orchestration chains
langchain-community>=0.0.10  # Community tools
```

### Utilities
```
python-dotenv>=1.0.0   # Environment variables
requests>=2.31.0       # HTTP client
openpyxl>=3.1.2        # Excel support
```

### Performance (Optionnel - ~2GB)
```
torch>=2.0.1           # PyTorch pour GPU (optionnel)
transformers>=4.35.0   # Hugging Face models (optionnel)
```

---

## 🛠️ INSTALLATION PAS À PAS

### Préalable: Environnement virtuel .venv

✅ Le dossier `.venv` existe déjà. Vous devez simplement l'**activer** avant chaque utilisation:

```bash
# Windows
.venv\Scripts\activate.bat

# macOS/Linux
source .venv/bin/activate
```

**Indication:** Vous verrez `(.venv)` au début de votre prompt terminal quand il est actif.

### Étape 1: Installer Ollama (Séparé de Python)

#### Windows
1. Aller sur https://ollama.ai/download
2. Télécharger "Ollama for Windows"
3. Exécuter installeur
4. Redémarrer PC
5. Vérifier: `ollama --version`

#### macOS
1. Aller sur https://ollama.ai/download
2. Télécharger "Ollama for macOS"
3. Ouvrir .dmg et drag into Applications
4. Lancer Ollama.app
5. Vérifier: `ollama --version`

#### Linux
```bash
# Installation via script
curl https://ollama.ai/install.sh | sh

# Vérifier
ollama --version
```

### Étape 2: Installer Dépendances Python dans .venv

#### Option A: Script Automatique (RECOMMANDÉ)

**Windows:**
```bash
# 1. Activer .venv
.venv\Scripts\activate.bat

# 2. Exécuter setup (installe dans .venv)
setup_local.bat
```

**macOS/Linux:**
```bash
# 1. Activer .venv
source .venv/bin/activate

# 2. Exécuter setup
bash setup_local.sh
```

✅ Les dépendances s'installent **DANS .venv** - pas globalement

#### Option B: Installation Manuelle (Alternative)

```bash
# Activer .venv (IMPORTANT!)
# Windows: .venv\Scripts\activate.bat
# macOS/Linux: source .venv/bin/activate

# Installer tout via requirements-local.txt
pip install -r requirements-local.txt

# GPU acceleration (optionnel - ~2GB)
# pip install torch transformers
```

### Étape 3: Télécharger Mistral 7B

```bash
# Dans terminal - Démarrer Ollama service
ollama serve

# Dans AUTRE terminal (Ollama doit tourner)
ollama pull mistral

# Attendre... (~5-10 min selon connexion)
# Download: ~4GB
```

### Étape 4: Lancer Application

```bash
# Terminal 1: Ollama service (si pas déjà lancé)
ollama serve

# Terminal 2: Streamlit app (avec .venv actif)
# Windows: .venv\Scripts\activate.bat && streamlit run streamlit_app.py
# macOS/Linux: source .venv/bin/activate && streamlit run streamlit_app.py
streamlit run streamlit_app.py
```

---

## 🔧 CONFIGURATION LOCAL MISTRAL

### Adapter Code pour Ollama Local

#### Dans `mistral_config.py`

Ajouter configuration locale:

```python
# Local Ollama Configuration
LOCAL_OLLAMA_CONFIG = {
    "model": "mistral",  # Model name dans Ollama
    "base_url": "http://localhost:11434",  # Default Ollama URL
    "temperature": 0.3,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 1500,  # Equivalent max_tokens
}

# Option: Utiliser local vs API
USE_LOCAL_LLM = True  # True = Ollama, False = Mistral API
```

#### Créer `ollama_integration.py`

```python
"""
Intégration Ollama Local - Alternative à Mistral API
"""

import ollama
from mistral_config import LOCAL_OLLAMA_CONFIG

class OllamaLocalChatbot:
    """Chatbot avec Ollama Mistral 7B local"""
    
    def __init__(self):
        self.model = LOCAL_OLLAMA_CONFIG["model"]
        self.base_url = LOCAL_OLLAMA_CONFIG["base_url"]
        
        # Vérifier connexion Ollama
        try:
            response = ollama.list()
            print(f"✅ Ollama connecté: {len(response.models)} modèles")
        except Exception as e:
            print(f"❌ Impossible connecter Ollama: {e}")
            print("💡 Démarrer Ollama: ollama serve")
            raise
    
    def query(self, user_query: str, verbose: bool = False) -> dict:
        """Traiter requête via Ollama local"""
        
        try:
            # Appeler Ollama
            response = ollama.generate(
                model=self.model,
                prompt=user_query,
                temperature=LOCAL_OLLAMA_CONFIG["temperature"],
                top_p=LOCAL_OLLAMA_CONFIG["top_p"],
                num_predict=LOCAL_OLLAMA_CONFIG["num_predict"],
            )
            
            return {
                "status": "success",
                "response": response.get("response", ""),
                "model": self.model,
                "local": True,
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": self.model,
            }
```

#### Adapter `streamlit_app.py`

```python
# Au lieu de mistral_integration.py
from ollama_integration import OllamaLocalChatbot

# Dans main()
if LOCAL_OLLAMA := True:  # Use local
    chatbot = OllamaLocalChatbot()
else:
    from mistral_integration import MistralChatbot
    chatbot = MistralChatbot()
```

---

## 📊 PERFORMANCE LOCAL vs CLOUD

### Comparaison

| Aspect | Local (Ollama) | Cloud (Mistral API) |
|--------|----------------|-------------------|
| **Latence** | 2-5s (dépend GPU) | 1-2s (réseau) |
| **Coût** | 0€ (une fois setup) | $ par token |
| **Confidentialité** | 100% local | Données envoyées |
| **RAM** | 16GB+ requis | Pas de limite |
| **Internet** | Pas requis | Obligatoire |
| **Modèle** | Mistral 7B | Mistral Large (meilleur) |
| **Qualité** | Bon (7B) | Excellent (Large) |

---

## 🔍 MONITORING & DEBUGGING

### Vérifier Ollama Service

```bash
# Status
ollama list

# Modèles disponibles
ollama list
# Output:
# mistral        latest   4.1 GB

# Tester requête directe
ollama run mistral "Bonjour"
```

### Logs Ollama

```bash
# Windows
# Logs: %USERPROFILE%\.ollama\logs

# macOS
# Logs: ~/.ollama/logs

# Linux
# Logs: ~/.ollama/logs
```

### Test Python Client

```python
import ollama

# Simple test
response = ollama.generate(
    model="mistral",
    prompt="Bonjour, quel est ton nom?",
    stream=False,
)
print(response["response"])
```

---

## ⚠️ TROUBLESHOOTING

### Problème: "Connection refused"

```bash
# Vérifier Ollama service running
ollama serve

# Sur autre terminal
ollama list  # Doit afficher modèles
```

### Problème: "Model not found"

```bash
# Télécharger manquant
ollama pull mistral

# Attendre complétion
# Puis: ollama list
```

### Problème: "Out of memory"

```python
# Réduire max tokens dans config
LOCAL_OLLAMA_CONFIG["num_predict"] = 500  # De 1500

# Ou réduire batch size
# Voir: ollama --help
```

### Problème: Réponse lente

```bash
# Possibilités:
# 1. Pas assez RAM (16GB minimum)
# 2. Disque trop lent
# 3. Model trop gros pour matériel
# 4. Processus autres apps gourmands

# Solution: Utiliser GPU (si disponible)
# CUDA/ROCm accélère 10x

# Vérifier GPU disponible:
ollama --version
# Installation CUDA: https://developer.nvidia.com/cuda-toolkit
```

### Problème: Réponses hors sujet

Même solution que cloud - ajuster system prompt:

```python
# Dans ollama_integration.py
SYSTEM_PROMPT = """
[Voir mistral_config.py SYSTEM_PROMPT]
"""

# Usage dans query
response = ollama.generate(
    model=self.model,
    prompt=SYSTEM_PROMPT + user_query,
    ...
)
```

---

## 📈 OPTIMISATIONS PERFORMANCE

### GPU Acceleration

#### NVIDIA (CUDA)

```bash
# Installer CUDA Toolkit
https://developer.nvidia.com/cuda-toolkit

# Ollama détecte automatiquement CUDA
# Restart: ollama serve

# Vérifier: ollama list
# Doit afficher GPU info
```

#### AMD (ROCm)

```bash
# Installation ROCm
https://rocmdocs.amd.com/en/docs-5.6.0/

# Configuration
export OLLAMA_ROCM_PATH=/opt/rocm

# Restart Ollama
ollama serve
```

#### Apple Silicon (MPS)

```bash
# Ollama supporte Metal (automatic)
# Aucune config requise
# Fonctionne sur M1/M2/M3 automatiquement

# Vérifier:
ollama list
# Doit montrer GPU acceleration
```

### Modèles Alternatifs Légers

```bash
# Plus léger (~2.5GB):
ollama pull neural-chat

# Encore plus léger (~1.3GB):
ollama pull orca-mini

# Plus lourd mais meilleur (~13GB):
ollama pull mistral:latest  # 7B par défaut
# ou
ollama pull neural-chat:latest
```

---

## ✅ CHECKLIST SETUP LOCAL

```
□ Ollama téléchargé et installé
□ Service Ollama lancé (ollama serve)
□ Mistral 7B téléchargé (ollama pull mistral)
□ ollama list affiche mistral
□ Python 3.9+ installé
□ pip à jour
□ Dépendances installées (setup_local.bat/sh)
□ ollama Python client testé
□ Streamlit lancé
□ Première requête envoyée
□ Réponse reçue ✅
```

---

## 🎯 PROCHAINES ÉTAPES

1. **Télécharger Ollama** → 5 min
2. **Télécharger Mistral 7B** → 10 min
3. **Installer dépendances** → 5 min
4. **Lancer Streamlit** → 1 min
5. **Poser première requête** → 2s-5s (latence réponse)

---

## 📞 SUPPORT

### Docs Officielles
- Ollama: https://ollama.ai
- Mistral 7B: https://mistral.ai/mistral-7b/
- Streamlit: https://docs.streamlit.io/

### Community
- Ollama Discord: https://discord.gg/ollama
- GitHub Issues: https://github.com/jmorganca/ollama/issues

---

**Setup Local:** ✅ Complet  
**Durée:** ~30 min (première fois)  
**Support:** Autodémarrage après setup  
**Coût:** 0€ (après setup)
