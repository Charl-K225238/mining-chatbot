# Miny — Assistant BI Minier

Application de chatbot analytique permettant d'interroger des données de production minière en langage naturel français.

---

## Fonctionnalités

- **⚡ Mode Analytique** — Réponses instantanées depuis les données (DuckDB SQL)
- **🔢 Mode Calcul** — Arithmétique, pourcentages, formules financières (CAGR, ROI…)
- **🏭 Mode Expertise** — Normes ISO, IRMA, bonnes pratiques industrie minière
- **💬 Mode Général** — Questions conversationnelles et définitions

Domaines couverts : tonnage, excavation, transport, engins, pannes, carburant, qualité, objectifs, PGES/HSE.

---

## Stack technique

| Composant | Rôle |
|---|---|
| **Python 3.10+** | Langage principal |
| **Streamlit** | Interface web |
| **DuckDB** | Moteur analytique (vues sur Parquet) |
| **Apache Parquet** | Stockage colonnaire |
| **BM25** | Recherche documentaire |
| **Ollama** | LLM local (optionnel) |

---

## Installation locale

```bash
# 1. Environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac / Linux

# 2. Dépendances
pip install -r requirements-local.txt

# 3. Pipeline ETL (première fois)
python -m src.ingest.pipeline

# 4. Lancement
python -m streamlit run app.py
```

L'interface est accessible sur **http://localhost:8501**

---

## Configuration

Les paramètres principaux sont dans `config/settings.py` :
- URL et modèles Ollama
- Chemins des répertoires de données

---

## Déploiement cloud

L'application est déployée sur **Streamlit Cloud**.  
Le mode Analytique fonctionne sans Ollama. Les modes LLM nécessitent un service Ollama local ou une API compatible.

---

## Licence

Usage interne — tous droits réservés.
