# REQUÊTES EXEMPLE - PATTERNS DE QUESTIONS

## 📊 CATÉGORIES DE QUESTIONS

### 1️⃣ ANALYSES TEMPORELLES

**Q1.1 : Données à une date spécifique**
- "Quel tonnage a été excavé le 15 mars 2024?"
- "Combien de carburant consommé le 1er juin 2023?"
- "État de production pour la semaine du 3-9 avril 2024?"

**Approche LLM:**
```
- Table : Benene_1_Excavation ou CARBURANT
- Filtre : Calendrier.Date = "2024-03-15"
- Agrégation : SUM(Tonnage) ou SUM(Quantité Servie)
- Jointure : via Calendrier si besoin colonnes temporelles
```

**Q1.2 : Périodes et comparaisons**
- "Évolution tonnage excavé 2023 vs 2024 vs 2025?"
- "Production moyenne par mois en 2024?"
- "Quel trimestre a été le plus productif?"
- "Évolution carburant par saison?"

**Approche LLM:**
```
- Groupement : Calendrier.Année, Calendrier.Mois, Calendrier.Trimestre, Calendrier.Saison
- Agrégation : SUM, AVG, MAX, MIN
- Format résultat : Tableau ou graphique temporel
```

**Q1.3 : Jours particuliers**
- "Production les jours ouvrés vs weekends?"
- "Productivité jours fériés?"
- "Transport le plus actif (jour de semaine)?"

**Approche LLM:**
```
- Filtre : Calendrier.Est_Jour_Ouvré = True/False
- Filtre : Calendrier.Est_Weekend = True/False
- Agrégation par Calendrier.Nom_Jour_Semaine
```

---

### 2️⃣ PERFORMANCE & PRODUCTIVITÉ

**Q2.1 : Performance d'équipement**
- "Quel engin a produit le plus?"
- "Machine la plus efficace (tonnage/carburant)?"
- "Équipement consommant le plus de carburant?"
- "Chargeuse la plus utilisée?"

**Approche LLM:**
```
- Table : Benene_1_Excavation + CARBURANT (jointure Equipement)
- Groupement : Equipement, MACHINE
- Agrégation : SUM(Tonnage), SUM(Quantité Servie (L))
- Calcul : Tonnage/Carburant = Ratio productivité
```

**Q2.2 : Comparaisons relatifs**
- "Quels 5 engins les plus productifs?"
- "Équipements sous-utilisés?"
- "Transport : qui amène le plus?"

**Approche LLM:**
```
- Tri : ORDER BY agrégation DESC/ASC
- Limit : TOP 5 ou WHERE condition < seuil
- Détail : Inclure périodes concernées
```

**Q2.3 : Ratios et efficacité**
- "Tonnage excavé par heure de carburant?"
- "Nombre de trajets par jour?"
- "Moyenne tonnage par transport?"

**Approche LLM:**
```
- Calcul dérivé : SUM(Tonnage) / SUM(Carburant*Consommation)
- Comptage : COUNT DISTINCT N°CAMION par Date
- Moyenne : AVG(Tonnage DESCENTE) par journée
```

---

### 3️⃣ BUDGETS & PLANIFICATION

**Q3.1 : Objectifs vs Réalisé**
- "Avons-nous respecté l'objectif production avril 2024?"
- "Écart objectif tonnage décembre 2023?"
- "Performance descente vs budget?"
- "Prévisions réalisées?"

**Approche LLM:**
```
- Table : Budget (join année/mois) + Excavation/Descente
- Comparaison : Tonnage à produire vs SUM(Tonnage réalisé)
- Calcul : Écart = (Réalisé - Objectif) / Objectif * 100%
- Format : % d'atteinte, tendance
```

**Q3.2 : Tendances budgétaires**
- "Mois avec pires performances?"
- "Qui dépasse régulièrement les budgets?"
- "Trimestre à mémoriser?"

**Approche LLM:**
```
- Groupement : Par mois/trimestre
- Calcul : % réalisation pour chaque
- Tri : Identifier + faibles et + hauts
```

---

### 4️⃣ ACTIONS & RESPONSABILITÉS

**Q4.1 : Actions et suivi**
- "Quelle est l'action responsable de Jean Dupont?"
- "Actions en retard?"
- "Actions terminées en 2024?"
- "Qui a signé l'action de qualité?"

**Approche LLM:**
```
- Table : PLAN D'ACTIONS DU PGES + Suivi des actions
- Filtre : Responsable = [nom]
- Filtre : Niveau d'avancement = [% ou statut]
- Comparaison : Échéance vs Date actuelle
```

**Q4.2 : Priorités et urgences**
- "Actions prioritaires non commencées?"
- "Actions en cours de réalisation?"
- "Obligations expirées?"

**Approche LLM:**
```
- Filtre : Priorité = haute/urgente
- Filtre : Statut != "Terminée"
- Comparaison : NOW() > Échéance
```

**Q4.3 : Domaines de responsabilité**
- "Domaine/Département responsable des émissions?"
- "Nombre d'actions RH?"
- "Qui gère la qualité?"

**Approche LLM:**
```
- Groupement : Direction/Département
- Comptage : COUNT actions
- Filtre : Domain = [domaine]
```

---

### 5️⃣ QUALITÉ & CONFORMITÉ

**Q5.1 : Données de qualité**
- "Qualité des échantillons février 2024?"
- "Navires avec meilleure conformité?"
- "Stock régulation pour zone X?"

**Approche LLM:**
```
- Table : Benene_2_Qualite_*
- Filtre : Calendrier.Mois/Année ou Zone
- Agrégation : Moyennes, % conformité
```

**Q5.2 : Anomalies**
- "Zones avec problèmes qualité?"
- "Navires non conformes?"
- "Stocks à régulariser?"

**Approche LLM:**
```
- Filtre : Status = anomalie/non-conforme
- Groupement : Zone, Navire
- Détail : Nature du problème
```

---

### 6️⃣ RÉFÉRENCES & MAÎTRES DONNÉES

**Q6.1 : Inventaire**
- "Combien d'engins au total?"
- "Types d'équipements disponibles?"
- "Liste des chargeuses et capacités?"
- "Personnel disponible?"

**Approche LLM:**
```
- Table : Benene_0_Liste_engins, Benene_0_Chargeuses, Benene_0_Personnel
- Comptage : COUNT DISTINCT
- Détail : Colonnes descriptives (Capacité, Type, Centre)
```

**Q6.2 : Caractéristiques**
- "Chargeuse avec meilleure capacité?"
- "Engin plus neuf?"
- "Opérateur principal de la machine X?"

**Approche LLM:**
```
- Filtre/Tri : ORDER BY Capacité DESC ou date
- Jointure : Personnel.ID si shiftsPersonnel
```

---

### 7️⃣ REQUÊTES COMPLEXES (Multi-tables)

**Q7.1 : Vue 360° d'une entité**
- "Profil complet de l'engin XXX" (spec + utilisation + carburant + performance + maintenance?)
- "Dossier complet de l'action YYY" (description + responsable + statut + échéance)?

**Approche LLM:**
```
- Jointures multiples : Liste_engins + Carburant + Excavation
- Format : Synthèse structurée
```

**Q7.2 : Analyses croisées**
- "Engins avec pire consommation carburant et production faible?"
- "Actions sans progrès et responsable indisponible?"

**Approche LLM:**
```
- Multiple jointures et filtres combinés
- Logique : AND/OR selon question
```

---

## 🎯 PATTERNS DE RÉPONSE ATTENDUS

### Format 1: Données Simples
```
Q: "Tonnage excavé le 15/03/2024?"

Réponse:
Le 15 mars 2024, le tonnage total excavé s'élève à **2,450 T**.

Détail par équipement:
- Excavatrice E1: 1,200 T
- Excavatrice E2: 1,000 T
- Chargeuse C1: 250 T

⚠️ Note: 1 ligne dupliquée détectée et exclue du calcul.
```

### Format 2: Comparaison Temporelle
```
Q: "Évolution tonnage 2023 vs 2024 vs 2025?"

Réponse:
| Année | Tonnage Total | Moyenne Mensuelle | Variation Y-o-Y |
|-------|---------------|------------------|-----------------|
| 2023  | 28,540 T      | 2,378 T           | -               |
| 2024  | 31,205 T      | 2,600 T           | +9.3%           |
| 2025  | 26,890 T      | 2,241 T           | -13.8% (partiel) |

📊 Observation: Pic production 2024, ralentissement 2025.
```

### Format 3: Analyse Multi-dimensions
```
Q: "Machine la plus efficace (tonnage/carburant)?"

Réponse:
Ratio Efficacité (Tonnage/L carburant):

🥇 Excavatrice E2: **1.85 T/L**
🥈 Chargeuse C1: **1.72 T/L**
🥉 Excavatrice E1: **1.54 T/L**

Contexte:
- E2 utilisée 245 jours (88% disponibilité)
- Production E2: 15,240 T / 8,200 L carburant
- Période: 2023-2024

💡 Recommandation: Maintenir E2 comme référence.
```

### Format 4: Alertes et Exceptions
```
Q: "Actions urgentes en retard?"

Réponse:
⚠️ **2 actions critiques en retard:**

1. **Action #15: Amélioration Qualité PGES**
   - Responsable: Jean Dupont
   - Échéance: 31 mars 2024 ❌ DÉPASSÉE
   - Jours de retard: 37 jours
   - % Avancement: 45%
   - Recommandation: Escalade requise

2. **Action #23: Conformité Environnement**
   - Responsable: Marie Martin
   - Échéance: 15 avril 2024 ⏰ J-5
   - % Avancement: 20%
   - Recommandation: Relancer URGENT

[Voir détails complets: consulter Suivi des actions.xlsx]
```

---

## 🔍 VALIDATION & CLARIFICATIONS

### Questions Ambigu
Quand la question est peu claire, toujours demander:

```
Q (imprécis): "Quel est le meilleur engin?"

Réponse LLM:
Pour répondre précisément, pourriez-vous clarifier:
1. **Critère d'excellence**: 
   - Productivité (tonnage excavé)?
   - Efficacité (tonnage/carburant)?
   - Disponibilité (taux utilisation)?
2. **Période de référence**: 
   - 2024 complète? 2025 YTD? Tous les temps?
3. **Filtre engin**:
   - Tous les types? Uniquement excavatrices?

Exemple réponse avec Productivité + 2024 entière:
[→ voir réponse structurée ci-dessus]
```

---

## 📋 CHECKLIST POUR LLM

Avant de répondre, vérifier:
- ✅ Table(s) nécessaire(s) identifiée(s)?
- ✅ Clés de jointure validées?
- ✅ Période couverte (2023-2026)?
- ✅ Doublons/anomalies signalés?
- ✅ Unités cohérentes (T, L, %, jours)?
- ✅ Réponse structurée et actionable?
- ✅ Limitation/hypothèses documentées?
