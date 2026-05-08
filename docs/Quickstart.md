# 🚀 QUICKSTART - Chatbot Interrogation Données

## 5 Minutes pour Démarrer

### 1️⃣ Installation (2 min)

```bash
# Naviguer dans le dossier
cd "Cadrage"

# Installer dépendances
pip install -r requirements.txt

# Ajouter clé API Mistral
echo MISTRAL_API_KEY=sk_VOTRE_CLE > .env
```

**Obtenir clé API:** https://console.mistral.ai/keys

### 2️⃣ Lancer l'App (30 sec)

```bash
streamlit run streamlit_app.py
```

**Ouvre automatiquement:** http://localhost:8501

### 3️⃣ Tester (2 min)

Tab **"💬 Chat"**:

```
📝 Posez question:
"Quel tonnage excavé en janvier 2024?"

🔍 Cliquez: Analyser

✅ Réponse structurée s'affiche!
```

---

## 📚 Comprendre la Structure

### Schéma en Étoile (⭐ Important)

```
                📅 CALENDRIER
              /    |    \    \
            /      |     \     \
     Excavation  Carburant  Budget  Actions
```

**Clé:** Toutes les dates passent par **Calendrier**

### Tables Principales

| Table | Données |
|-------|---------|
| `Benene_1_Excavation` | Tonnage excavé par jour |
| `CARBURANT` | Litres consommés |
| `Budget` | Objectifs année/mois |
| `Calendrier` | Dimension temporelle (2023-2026) |

---

## 💡 Exemples Requêtes

### Simple (Facile)
```
"Production janvier 2024?"
```

### Comparaison (Moyen)
```
"Évolution production 2023 vs 2024 vs 2025?"
```

### Complexe (Difficile)
```
"Efficacité (tonnage/carburant) par équipement en 2024?"
```

---

## ⚙️ Configuration

### Modifier Température LLM

```python
# Dans mistral_config.py
LLM_PARAMETERS["temperature"] = 0.5  # Plus créatif
```

- `0.0` = Très précis (données)
- `0.5` = Équilibré
- `1.0` = Très créatif

### Réduire Temps Réponse

```python
LLM_PARAMETERS["max_tokens"] = 1000  # De 1500
```

---

## 🧪 Valider Installation

```bash
python test_chatbot_structure.py
```

**Output attendu:**
```
✅ TOUS LES TESTS PASSÉS - PRÊT POUR DÉPLOIEMENT
```

---

## 🐛 Problèmes Courants

| Problème | Solution |
|----------|----------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `MISTRAL_API_KEY not found` | Ajouter dans `.env` |
| `ConnectionError` | Vérifier internet + clé API |
| `Réponse hors sujet` | Poser question plus précise |

---

## 📂 Fichiers Importants

```
✅ schema.json           ← Métadonnées tables
✅ relationships.py      ← Graphe relations
✅ mistral_config.py     ← Configuration LLM
✅ streamlit_app.py      ← Application UI
✅ entity_mapping.py     ← Alias tables
```

---

## 📖 Documentation Complète

- **Déploiement:** Voir `README_DEPLOYMENT.md`
- **Patterns Requêtes:** Voir `query_patterns.md`
- **Contexte LLM:** Voir `chatbot_context.md`
- **Index Fichiers:** Voir `FILES_INDEX.md`

---

## 🎯 Prochaines Étapes

### Immédiat
- [ ] Installer dépendances
- [ ] Configurer clé Mistral
- [ ] Lancer streamlit
- [ ] Tester requête simple

### Court terme (1-2 jours)
- [ ] Tester 5-10 requêtes variées
- [ ] Affiner entity_mapping.py si besoin
- [ ] Vérifier réponses qualité

### Moyen terme (1-2 semaines)
- [ ] Déployer sur Streamlit Cloud
- [ ] Activer monitoring/logs
- [ ] Fine-tune Mistral si besoin

---

## 🌐 Déployer en Ligne (5 min extra)

### Streamlit Cloud (Recommandé)

1. Pousser sur GitHub
2. Aller sur https://share.streamlit.io
3. Connecter GitHub
4. Sélectionner repo + `streamlit_app.py`
5. Ajouter secrets (MISTRAL_API_KEY)

✅ **App live en 2-3 min**

---

## 💬 Questions Rapides?

```
Q: Où ajouter API Key?
R: Dans fichier `.env` ou environment variable

Q: Peut changer modèle LLM?
R: Dans mistral_config.py ligne "model"

Q: Fonctionne hors-ligne?
R: Non, nécessite Mistral API (ou ollama local)

Q: Historique conversations?
R: Voir session_state dans streamlit_app.py
```

---

## ✅ Checklist Démarrage

```
□ Python 3.9+ installé
□ pip en place
□ Mistral API Key obtenue
□ Fichiers copié dans dossier
□ requirements.txt installé
□ MISTRAL_API_KEY configuré
□ streamlit run ...
□ App ouverte dans navigateur
□ Requête test posée
□ Réponse reçue
□ Validé ✅
```

---

**Durée Totale:** ~10 min  
**Difficulté:** ⭐ Facile  
**Support:** Voir README_DEPLOYMENT.md
