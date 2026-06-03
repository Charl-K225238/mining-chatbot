# Miny — Assistant BI Minier

Chatbot d'analyse de données de production minière. Posez des questions en français sur le tonnage, les pannes, les engins, la qualité, le transport, les objectifs — et obtenez des réponses instantanées depuis vos propres données Excel.

---

## Ce que fait Miny

| Question | Réponse |
|---|---|
| `Tonnage descendu par mois en 2026` | Tableau Jan–Avr avec total |
| `Tonnage excavé 2025` | 1 216 242 T (table excavation) |
| `Tonnage transporté 2025` | 1 193 575 T (mine→port) |
| `Tonnage arrivé au port 2025` | 1 189 786 T (logistique port) |
| `Tonnage navire 2025` | Chargements navires |
| `Comparer 2024 et 2025` | Tonnage + voyages + tombereaux + taux objectif |
| `Taux accomplissement 2025` | Prévu 1 341 400 T → Réalisé 86,2 % ⚠️ |
| `Quels tombereaux ont le plus de pannes ?` | Classement par nombre de pannes |
| `Tonnage S1–S6 2026` | Semaines ISO 1 à 6 |
| `Tonnage par trimestre en 2025` | T1 / T2 / T3 / T4 avec total |
| `Tonnage S1 et S2 2025` | Les deux semestres |
| `Bilan des pannes en 2023` | Direction : 38 · Pneu : 10 · Carburant : 10… |
| `Q1, Q2` *(virgule)* | Réponses aux deux questions séparément |

**5 types de tonnage reconnus :**

| Mot-clé | Type | Table |
|---|---|---|
| *(aucun)* ou `descendu` | Tonnage descendu (défaut) | `descente_minerai` |
| `excavé` / `excavation` | Tonnage excavé | `excavation` |
| `transporté` / `camion` | Chargé mine (pesée mine) | `transport_minerai_paa` |
| `arrivé port` / `PAA` | Réceptionné au port | `transport_minerai_paa` |
| `navire` | Chargé sur navire | `productivite_loading` |

**Questions de suivi :** Miny mémorise votre dernière question.

| Première question | Suivi court | Résultat |
|---|---|---|
| `Bilan des pannes` | `en 2023` | Bilan 2023 |
| `Bilan des pannes` | `de direction` | Pannes direction |
| `Tonnage descendu` | `en 2026` | Tonnage 2026 |
| `Top 5 engins` | `en 2025` | Top 5 pour 2025 |

---

## Prérequis

### 1. Python 3.10 ou supérieur

```bash
python --version
```

Téléchargement : https://www.python.org/downloads/

### 2. Ollama (pour les réponses narratives — optionnel)

Ollama fait tourner le modèle de langage localement.

**Installation Windows :**
1. Téléchargez : https://ollama.com/download
2. Installez et ouvrez un terminal :

```bash
ollama pull phi3:mini
```

> **Sans Ollama** : Miny répond à toutes les questions analytiques (tonnage, pannes, objectifs, engins…). Seules les questions narratives libres (recherche dans le journal, PGES) nécessitent Ollama.

---

## Installation

### Étape 1 — Créer l'environnement virtuel

```bash
cd chemin/vers/mining-chatbot
python -m venv .venv
```

### Étape 2 — Activer l'environnement

```bash
# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

### Étape 3 — Installer les dépendances

```bash
pip install -r requirements-local.txt
```

### Étape 4 — Préparer les données (une seule fois)

Lit tous les fichiers Excel, nettoie et convertit en Parquet :

```bash
python -m src.ingest.pipeline
```

---

## Lancement

> **Important :** toujours utiliser le Python du `.venv`.

### Démarrer Ollama (optionnel, dans un terminal séparé)

```bash
ollama serve
```

### Lancer le chatbot

```bash
cd chemin/vers/mining-chatbot
.venv\Scripts\python.exe -m streamlit run app.py
```

L'interface s'ouvre dans votre navigateur : **http://localhost:8501**

> **Pourquoi `python.exe -m streamlit` ?**
> Le lanceur `streamlit.exe` contient un chemin codé en dur qui se casse si le projet est déplacé. `python.exe -m streamlit` fonctionne toujours.

---

## Fonctionnalités de l'interface

### Sidebar gauche

| Section | Description |
|---|---|
| **📊 Données disponibles** | Liste toutes les tables avec nombre de lignes et **date de la dernière donnée** |
| **🗑 Effacer** | Efface l'historique de la conversation |
| **🔄 Réindexer** | Recharge les données et reconstruit l'index après modification manuelle |
| **📁 Charger des données** | Upload de fichiers Excel, CSV, PDF, DOCX, TXT — traitement automatique |
| **💡 Comment formuler ?** | Guide avec structure et exemples de questions |
| **📖 Comprendre Miny** | Limites, erreurs à éviter, guide des questions de suivi |

### Rappel de fraîcheur

En bas de page, Miny affiche la date des dernières données pour les tables principales :
> `📅 Dernières données : descente minerai 21/04/2026 · excavation 26/04/2026 · objectifs 26/04/2026`

### Raccourcis période

| Saisie | Interprétation |
|---|---|
| `S17 2026` | Semaine ISO 17 de 2026 |
| `S1-S6 2026` | Semaines ISO 1 à 6 de 2026 |
| `T3 2025` | Trimestre 3 / 2025 |
| `S1 2026` | Semestre 1 / 2026 |
| `cette année` | Année en cours |

---

## Mise à jour des données

### Via l'interface (recommandé)

1. Ouvrez le menu **📁 Charger des données** dans la sidebar
2. Sélectionnez votre fichier Excel/CSV/PDF/DOCX/TXT
3. Cliquez **⬆️ Importer et traiter**

Miny détecte automatiquement quelle table mettre à jour et ne re-traite **que les données concernées** (plus rapide). L'index documentaire est reconstruit automatiquement.

### Via ligne de commande

```bash
# Copier le fichier dans data/raw/ puis :
python -m src.ingest.pipeline

# Puis cliquer "🔄 Réindexer" dans l'interface
# OU relancer le chatbot complètement
```

---

## Structure du projet

```
mining-chatbot/
│
├── app.py                        ← Point d'entrée Streamlit
├── pages/
│   ├── 1_Assistant.py            ← Chat analytique (interface principale)
│   ├── 2_Documentation.py        ← Guide d'utilisation et exemples
│   └── 4_Parametres.py           ← Upload de fichiers (Excel, PDF, DOCX, TXT)
│
├── core/                         ← Pipeline NLP + routing (couche orchestration)
│   ├── nlp.py                    ← Normalisation, détection domaines et intentions
│   ├── router.py                 ← Routeur intelligent (analytique / LLM / clarif.)
│   ├── clarification.py          ← Suggestions contextuelles non-bloquantes
│   ├── data_loader.py            ← Cache ressources partagées (DuckDB, BM25)
│   └── ollama_client.py          ← Client Ollama (démarrage auto, état)
│
├── config/                       ← Dictionnaires métier miniers
│   ├── synonymes.py              ← Synonymes → forme canonique
│   └── verbes.py                 ← Verbes d'action reconnus
│
├── src/
│   ├── ingest/
│   │   ├── config.py             ← Décrit chaque fichier Excel source
│   │   ├── loader.py             ← Lit les fichiers Excel
│   │   ├── cleaner.py            ← Nettoie et normalise les données
│   │   ├── pipeline.py           ← Orchestre ETL Excel → Parquet
│   │   └── upload_handler.py     ← Gestion des uploads (routage, pipeline ciblé)
│   │
│   ├── db/
│   │   └── connection.py         ← Connexion DuckDB + vues Parquet + calendrier ISO
│   │
│   ├── engine/
│   │   ├── analytics.py          ← 17+ handlers NL→SQL (tonnage, pannes, heures…)
│   │   ├── clarification.py      ← Désambiguïsation sémantique par domaine
│   │   ├── intention.py          ← Détection d'intentions (verbes d'action)
│   │   └── query_router.py       ← Cascade analytique → RAG → LLM
│   │
│   ├── rag/
│   │   ├── corpus.py             ← Extrait textes DuckDB + PDF/DOCX/TXT uploadés
│   │   ├── index.py              ← Index BM25 (corpus tokenisé en pickle)
│   │   └── retriever.py          ← Recherche top-K documents pertinents
│   │
│   ├── llm/
│   │   ├── prompts.py            ← System prompts par mode (factuel/synthèse/analyse)
│   │   └── ollama_client.py      ← Client Ollama (streaming + fallback)
│   │
│   └── utils/
│       └── text.py               ← norm() — normalisation accents/casse partagée
│
├── assets/
│   └── style.css                 ← CSS injecté dans Streamlit
│
├── data/
│   ├── raw/                      ← Fichiers Excel sources
│   ├── parquet/                  ← Tables Parquet (générées par le pipeline ETL)
│   └── clean/                    ← Documents uploadés (PDF, DOCX, TXT)
│
└── test/                         ← Tests unitaires et d'intégration
```

---

## Tables de données

| Table | Description | Période |
|---|---|---|
| `descente_minerai` | Tonnage journalier, engins, voyages, observations pannes tombereaux | 2023–2026 |
| `objectifs` | Objectifs quotidiens excavation + descente (prévu vs réalisé) | 2024–2026 |
| `excavation` | Volumes et tonnages excavés par shift | 2024–2026 |
| `transport_minerai_paa` | Transport camions mine → port PAA (pesée mine et port) | 2024–2026 |
| `productivite_loading` | Chargement navires (tonnage et productivité port) | 2024–2026 |
| `carburant_citerne` | Consommation carburant par engin (Petro Ivoire) | 2024–2026 |
| `journal` | Pannes et événements de la trencher (TRENCHER TRS N°296 par défaut) | 2024–2026 |
| `shifts_horaires` | Heures machine par équipement et vacation | 2024–2026 |
| `qualite_echantillons` | Analyses qualité : teneurs Al₂O₃, SiO₂, Fe₂O₃ | 2024–2026 |
| `pges_actions` | Actions du Plan de Gestion Environnementale et Sociale | — |
| `suivi_actions` | Obligations HSE et leur statut d'avancement | — |

---

## Comment fonctionne Miny

```
Votre question
      │
      ▼
┌───────────────────────────┐
│  Pré-traitement           │  → accents, abréviations (S17→semaine 17,
│                           │    T3→trimestre 3, S1→semestre 1…)
└─────────────┬─────────────┘
              ▼
┌───────────────────────────┐
│  1. Moteur analytique     │  → 14 handlers NL→SQL, résultat en < 1 s
│     (DuckDB SQL)          │    tonnage, pannes, objectifs, tombereaux…
└─────────────┬─────────────┘
              │ Pas reconnu
              ▼
┌───────────────────────────┐
│  1b. Question de suivi ?  │  → combine prev_question + question courte
│      (si courte < 60 car) │    "de direction" après "bilan des pannes"
└─────────────┬─────────────┘
              │ Toujours pas reconnu
              ▼
┌───────────────────────────┐
│  2. Recherche BM25        │  → top-6 documents pertinents
│     (observations, PGES,  │    (journal, pannes, actions PGES, carburant)
│      journal, PDF/DOCX)   │
└─────────────┬─────────────┘
              │ Documents trouvés + Ollama actif
              ▼
┌───────────────────────────┐
│  3. LLM Ollama phi3:mini  │  → réponse narrative 5-15 s
│     avec contexte RAG     │    garde-fou anti-hallucination si 0 contexte
└───────────────────────────┘
```

---

## Exemples de questions

### Production et tonnage

```
Tonnage par mois en 2026
Tonnage S1-S6 2026
Tonnage semaine par semaine en avril 2026
Tonnage S17 2026
Bilan annuel du tonnage par année
Comparer 2024 et 2025
Comparer le tonnage 2024 et 2025
```

### Objectifs et performance

```
Taux accomplissement 2025
Objectifs vs réalisé 2024
Objectifs excavation 2025
Comparer 2024 et 2025       ← affiche tonnage + voyages + tombereaux + taux
```

### Engins et transport

```
Quels tombereaux ont le plus de pannes ?
Quel est le nombre de pannes par tombereau
Combien de tombereaux distincts ?
Top 5 engins par tonnage
Quelle est la société de transport ?
Quel est le tonnage par voyage ?
```

### Pannes et incidents

```
Bilan des pannes en 2023
Combien de pannes de direction en 2023 ?
Y a-t-il eu des incidents pluie ?
Y a-t-il eu des pneus crevés ?
```

### Organisation et qualité

```
Qui est le responsable du site en 2026 ?
Quelle est la qualité du minerai ?
Top 10 zones de stockage
Quelles actions PGES sont en cours ?
```

### Questions de suivi (exemples enchaînés)

```
1. Bilan des pannes        → résumé toutes années
2. en 2023                 → bilan pour 2023
3. de direction            → pannes de direction en 2023

1. Tonnage par mois        → résumé toutes années
2. en 2026                 → tonnage mensuel 2026

1. Top 5 engins            → classement global
2. en 2025                 → classement pour 2025
```

---

## Résolution des problèmes courants

| Problème | Solution |
|---|---|
| `ModuleNotFoundError` | Vérifiez que `.venv` est activé : `.venv\Scripts\activate` |
| `FileNotFoundError: data/parquet/...` | Relancez : `python -m src.ingest.pipeline` |
| Réponse "Je n'ai pas trouvé..." | Précisez l'année ou le sujet — voir guide dans l'interface |
| Réponse lente (> 30 s) | Normal si Ollama charge le modèle la 1ère fois |
| Données mises à jour non prises en compte | Utilisez **📁 Charger des données** ou cliquez **🔄 Réindexer** |
| Port 11434 déjà utilisé | Ollama est déjà en cours — pas besoin de `ollama serve` |
| `UnicodeDecodeError` dans le pipeline | Normal sur Windows — le pipeline reconfigure l'encodage automatiquement |

---

## Stack technique

| Composant | Rôle |
|---|---|
| **Python 3.10+** | Langage principal |
| **DuckDB** | Base analytique locale (vues sur Parquet, pas de serveur) |
| **Apache Parquet + pyarrow** | Stockage colonnaire optimisé |
| **BM25 (rank-bm25)** | Moteur de recherche documentaire sur observations/journal/PGES |
| **Ollama + phi3:mini** | LLM local — 3B paramètres, ~2 Go RAM |
| **Streamlit** | Interface web interactive |
| **pandas** | Lecture et nettoyage des fichiers Excel |
| **PyPDF2 + python-docx** | Extraction texte des PDF et Word uploadés |
