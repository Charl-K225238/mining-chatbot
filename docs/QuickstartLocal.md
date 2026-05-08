# ⚡ QUICKSTART - Mistral 7B Local (avec .venv existant)

**Durée:** ~30 min (première fois) + téléchargements  
**Prérequis:** `.venv` existant, Ollama à télécharger

---

## 🎯 En 4 étapes

### 1️⃣ Installer Ollama (Séparé de Python)

Télécharger et installer **Ollama** (pas pip, téléchargement natif):
- **Windows/macOS/Linux:** https://ollama.ai/download
- Version: Latest (2026-05)

```bash
# Vérifier après installation
ollama --version
```

### 2️⃣ Installer Dépendances Python dans .venv

```bash
# Windows
.venv\Scripts\activate.bat
setup_local.bat

# macOS/Linux
source .venv/bin/activate
bash setup_local.sh
```

⏱️ ~5 min (téléchargement packages)

### 3️⃣ Télécharger Mistral 7B Model

```bash
# Terminal 1 - Démarrer Ollama service
ollama serve

# Terminal 2 - Télécharger model (Ollama doit tourner)
ollama pull mistral
```

⏱️ ~10-15 min (dépend connexion, ~4GB)

### 4️⃣ Lancer Application

```bash
# Terminal 3 - Streamlit (avec .venv actif)
# Windows
.venv\Scripts\activate.bat
streamlit run streamlit_app.py

# macOS/Linux
source .venv/bin/activate
streamlit run streamlit_app.py
```

✅ **Ouvrir:** http://localhost:8501

---

## 📋 Vérifications

### Ollama OK?
```bash
ollama list
# Doit afficher: mistral    latest
```

### Python OK?
```bash
# Avec .venv actif
python --version  # Python 3.9+
pip list | grep ollama  # Doit voir: ollama
```

### Streamlit OK?
```bash
# Avec .venv actif
streamlit --version
```

---

## 🚨 Problèmes Courants

### "Connection refused" (Ollama)
```bash
# Vérifier Ollama service tourne
ollama serve  # Dans nouveau terminal
```

### "Model not found"
```bash
# Ollama doit tourner
ollama serve

# Télécharger manquant (autre terminal)
ollama pull mistral
```

### "ModuleNotFoundError"
```bash
# Vérifier .venv actif
# Windows: .venv\Scripts\activate.bat
# macOS/Linux: source .venv/bin/activate

# Réinstaller dépendances
pip install -r requirements-local.txt
```

---

## 📊 Architecture

```
┌─────────────────────┐
│   Streamlit UI      │ (http://localhost:8501)
│  Chat Interface     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ .venv Python        │
│ (ollama client)     │
└──────────┬──────────┘
           │
┌──────────▼──────────────────┐
│ Ollama Service              │ (http://localhost:11434)
│ localhost:11434             │
└──────────┬──────────────────┘
           │
┌──────────▼──────────┐
│ Mistral 7B Model    │
│ (~4GB, local)       │
└─────────────────────┘
```

---

## 💾 Fichiers Clés

```
.venv/                      # Environnement virtuel (existant)
├── Scripts/activate.bat    # Windows
└── bin/activate            # macOS/Linux

setup_local.bat             # Setup script Windows
setup_local.sh              # Setup script macOS/Linux

requirements-local.txt      # Dépendances Python
INSTALL_LOCAL_MISTRAL.md    # Guide détaillé

streamlit_app.py            # Application principale
ollama_integration.py       # Client Ollama
schema.json                 # Catalogue données
calendar.csv                # Dimension temporelle
```

---

## ✅ Checklist Setup

```
□ Ollama téléchargé et installé
□ ollama --version fonctionne
□ .venv existant et activable
□ setup_local.bat/sh exécuté
□ pip list contient: ollama, streamlit, pandas
□ Mistral 7B téléchargé (ollama list montre mistral)
□ Ollama service lancé (ollama serve)
□ Streamlit lancé (http://localhost:8501 accessible)
□ Première requête sent une réponse ✅
```

---

## 🎉 Résultat Attendu

1. **Ollama service tourne:** `http://localhost:11434/api/generate`
2. **Streamlit tourne:** `http://localhost:8501`
3. **Poser requête:** "Quel tonnage en janvier 2024?"
4. **Réponse:** Mistral 7B répond localement (2-5s)

---

## 📞 Prochaines Étapes

- **GPU Acceleration:** Installer PyTorch + CUDA (x10 plus rapide)
- **Modèles Alternatifs:** `ollama pull neural-chat` (meilleur), `ollama pull orca-mini` (plus léger)
- **Deployment:** Docker, Kubernetes, etc.

---

**Setup Local:** ✅ Prêt  
**Dernière mise à jour:** 2026-05-07  
**Version Ollama:** >=0.1.0
