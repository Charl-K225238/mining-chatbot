# 📁 Structure des Fichiers - Localisation des Données

## Réponse à votre question : "Où sont les fichiers Excel bruts ?"

### 📊 Fichiers Excel ORIGINAUX (RAW)
Les fichiers Excel **bruts** (source) ne sont **pas** stockés localement par défaut. Ils étaient initialement dans le répertoire:
```
data/raw/  (actuellement vide)
```

Si vous rechargez les fichiers Excel via l'interface Streamlit, ils seront:
1. **Sauvegardés** dans: `data/raw/` (fichiers .xlsx originaux)
2. **Traités** et convertis en JSON
3. **Stockés** dans: `data/clean/excel/` (fichiers `_processed.json`)

### 📝 Structure Actuelle des Données Nettoyées

```
data/clean/
├── excel/                              # Données minières processées
│   ├── Benene_0_Chargeuses.xlsx        (fichier source)
│   ├── Benene_0_Chargeuses_processed.json     (données JSON)
│   ├── Benene_0_Personnel.xlsx
│   ├── Benene_0_Personnel_processed.json
│   ├── Benene_0_Stocks.xlsx
│   ├── Benene_0_Stocks_processed.json
│   ├── Benene_1_Excavation.xlsx        (DONNÉES D'EXCAVATION Q1 2024)
│   ├── Benene_1_Excavation_processed.json
│   ├── Benene_1_Journal.xlsx
│   ├── Benene_1_Journal_processed.json
│   ├── Benene_1_Shifts_horaires.xlsx
│   ├── Benene_1_Shifts_horaires_processed.json
│   ├── Benene_1_Shifts_personnel.xlsx
│   ├── Benene_1_Shifts_personnel_processed.json
│   ├── Benene_2_Qualite_echantillons.xlsx
│   ├── Benene_2_Qualite_echantillons_processed.json
│   ├── Benene_2_Qualite_navires.xlsx
│   ├── Benene_2_Qualite_navires_processed.json
│   ├── Benene_3_Regul_Qté_stock.xlsx
│   ├── Benene_3_Regul_Qté_stock_processed.json
│   ├── Benene_3_Regul_Qualité_stock.xlsx
│   ├── Benene_3_Regul_Qualité_stock_processed.json
│   ├── Budget.xlsx
│   ├── Budget_processed.json
│   ├── CARBURANT.xlsx
│   ├── CARBURANT_processed.json
│   ├── DESCENTE MINERAI.xlsx
│   ├── DESCENTE MINERAI_processed.json
│   ├── PLAN D'ACTIONS DU PGES.xlsx
│   ├── PLAN D'ACTIONS DU PGES_processed.json
│   ├── PRODUCTIVITE PORT.xlsx
│   ├── PRODUCTIVITE PORT_processed.json
│   ├── Suivi des actions.xlsx
│   ├── Suivi des actions_processed.json
│   ├── TRANSPORT MINERAI PAA.xlsx
│   └── TRANSPORT MINERAI PAA_processed.json
├── pdf/                                # Rapports PDF traités
│   └── *_processed.json
├── doc/                                # Documents DOCX traités
│   └── *_processed.json
└── txt/                                # Fichiers texte traités
    └── *_processed.json
```

## 🔍 Comment le Chatbot Fonctionne

### Flux de traitement des fichiers:
1. **Upload** → Fichier Excel chargé dans `data/raw/`
2. **Traitement** → Conversion en JSON structuré
3. **Stockage** → Sauvegarde dans `data/clean/excel/` avec suffixe `_processed.json`
4. **Utilisation** → RAG Engine récupère les données JSON pour enrichir les réponses

### Fichiers pour EXCAVATION (Q1 2024):
Pour répondre à votre question "Quel est le tonnage total extrait sur le T1 2024 ?"
- 📍 Principal fichier: **`Benene_1_Excavation_processed.json`**
- Il contient les données d'excavation avec les colonnes:
  - Date/Shift
  - Tonnage extrait
  - Zone d'excavation
  - Équipement utilisé

### Fichiers pour CARBURANT (Efficacité énergétique):
Pour calculer l'efficacité (T/L):
- 📍 Fichier: **`CARBURANT_processed.json`**
- Contient: Consommation de carburant par période
- Formule: `SUM(Tonnage) / SUM(Carburant_L)` = Efficacité (T/L)

## 📋 Tableau des Données Disponibles

| Table | Description | Fichier JSON | Données principales |
|-------|-------------|--------------|---------------------|
| Benene_0_* | Objectifs & Ressources Q0 | Respectifs | Personnel, Engins, Stocks, Objectifs |
| Benene_1_Excavation | **EXTRACTION Q1 2024** | `_processed.json` | Tonnage, Zones, Shifts |
| Benene_1_Journal | Journal des opérations | `_processed.json` | Événements, Problèmes |
| Benene_1_Shifts | Horaires & Personnel | `_processed.json` | Heures, Équipes |
| Benene_2_Qualite | Qualité Q2 2024 | `_processed.json` | Échantillons, Navires |
| Benene_3_Regul | Régulation Q3 2024 | `_processed.json` | Stock, Qualité |
| CARBURANT | Consommation énergétique | `_processed.json` | L/jour, Coûts |
| PRODUCTIVITE PORT | Rendement des opérations | `_processed.json` | Tonnes/jour, Efficacité |
| TRANSPORT MINERAI | Logistique | `_processed.json` | Routes, Tonnages |
| Budget | Budget & Dépenses | `_processed.json` | Allocations, Dépenses |
| PGES | Suivi Actions Environnement | `_processed.json` | Actions, Statuts |

## ⚙️ Corrections Apportées

### ✅ Fixes du Session {date}:
1. **Erreurs de lecture fichiers**: Corrigé le RAG Engine pour filtrer SEULEMENT les fichiers `_processed.json`
2. **Erreurs UTF-8**: Amélioration du traitement des fichiers Excel en binaire
3. **Erreurs JSON**: Meilleure gestion des erreurs de décodage JSON
4. **Présentation du Chatbot**: Ajout d'un message de bienvenue poli avec liste des capacités
5. **Métrique de temps**: Correction du bug d'affichage du temps de réponse

### 📊 Données accessibles:
Le chatbot peut maintenant interroger correctement:
- Données d'excavation (tonnages) par trimestre/année
- Comparaisons Q1 2023 vs Q1 2024
- Calculs d'efficacité énergétique
- Analyses de productivité
- Rapports de qualité
- Suivi de budget

## 🚀 Prochaines Étapes

Pour répondre à votre question sur **"Quel est le tonnage total extrait sur le T1 2024, et comment ça se compare au T1 2023 ?"**:

1. Consulter: `data/clean/excel/Benene_1_Excavation_processed.json`
2. Agréger les tonnages par date pour Q1 2024 (Jan-Mar)
3. Comparaison avec données Q1 2023 si disponibles
4. Calculer les variations/tendances

Le chatbot peut maintenant effectuer ces analyses automatiquement! 🤖
