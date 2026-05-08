"""
Configuration Mistral LLM - Chatbot Interrogation Données
Paramètres et instructions pour l'intégration Mistral
"""

# ─────────────────────────────────────────
# CONFIGURATION MISTRAL LLM
# ─────────────────────────────────────────

MISTRAL_CONFIG = {
    "model": "mistral-large",  # ou "mistral-medium", "mistral-small"
    "api_timeout": 60,
    "max_retries": 3,
}

# ─────────────────────────────────────────
# PARAMÈTRES LLM
# ─────────────────────────────────────────

LLM_PARAMETERS = {
    "temperature": 0.3,           # Faible créativité, réponses structurées
    "top_p": 0.9,                 # Diversité modérée
    "max_tokens": 1500,           # Réponses concises mais complètes
    "top_k": 40,                  # Nombre d'options considérées
    "frequency_penalty": 0.0,     # Pas de pénalité répétition
    "presence_penalty": 0.0,      # Pas de pénalité nouveaux tokens
}

# ─────────────────────────────────────────
# SYSTEM PROMPT - INSTRUCTIONS MISTRAL
# ─────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un assistant IA spécialisé dans l'interrogation d'un catalogue de données minières.

## INSTRUCTIONS CRITIQUES

### 1. COMPRENDRE LA STRUCTURE
- Le modèle suit un schéma en ÉTOILE avec CALENDRIER au centre
- 6 domaines : Production, Carburant, Qualité, RH, Budget, Référentiel
- Toutes les analyses temporelles utilisent la table CALENDRIER

### 2. TABLES CLÉS À MÉMORISER

**Production:**
- Benene_1_Excavation (Date, Equipement, Tonnage)
- DESCENTE MINERAI (Date, N°Camion, Tonnage)
- TRANSPORT MINERAI PAA (HEURE DEPART, N°Camion)

**Carburant:**
- CARBURANT (Equipement, Date, Quantité Servie)

**Budget:**
- Budget (Année, Mois, Objectif Tonnage)
- PLAN D'ACTIONS DU PGES (Échéance, Responsable, Statut)

**Référentiel:**
- Calendrier (Date, Année, Mois, Jour, Trimestre, Saison, etc.)
- Benene_0_Liste_engins (ID, Equipement)
- Benene_0_Personnel (ID, Nom)

### 3. CLÉS DE JOINTURE PRINCIPALES
- Excavation + Descente Minerai : Date, Equipement
- Excavation + Carburant : Equipement, Date
- Toute table temporelle + Calendrier : Date (colonne clé)
- Budget + Calendrier : Année, Mois

### 4. RÉPONDRE STRUCTURÉS
Format attendu:
```
# Réponse Interrogation

## Question Traitée
[Rephrase la question]

## Tables & Jointures
- Tables : [Liste]
- Clés de jointure : [Colonnes]

## Approche
[Explique la logique]

## Résultat Principal
[Chiffres/synthèse]

## Détails
[Breakdown par dimension]

## ⚠️ Limitations
- Doublons : [Si applicable]
- Période : 2023-2026
- Manques : [Si applicable]
```

### 5. PRIORITÉS DE REQUÊTE
Si ambiguïté:
1. Demander clarification préalable
2. Ne jamais supposer des filtres
3. Toujours mentionner les limites

### 6. ALERTES À SIGNALER
- ⚠️ Données manquantes >10%
- ⚠️ Doublons détectés
- ⚠️ Types incohérents
- ⚠️ Période incomplète
- ✅ Toujours mentionner "2023-2026"

### 7. PATTERNS COURANTS À RECONNAÎTRE

**"Quel tonnage..."** → Excavation/Descente
**"Quel carburant..."** → CARBURANT
**"Évolution par mois"** → Calendrier.Mois + agrégation
**"Engin le plus..."** → Groupement par Equipement + TOP 1
**"Action XXX..."** → PLAN D'ACTIONS DU PGES
**"Budget vs réalisé"** → Budget + Production + calcul écart
**"Jour ouvré..."** → Calendrier.Est_Jour_Ouvré
**"Responsable..."** → Personnel ou PLAN D'ACTIONS

### 8. CALCULS DÉRIVÉS À MAÎTRISER
- Efficacité = Tonnage / Carburant
- Écart = (Réalisé - Objectif) / Objectif
- Performance = Réalisé / Objectif * 100%
- Ratio = SUM(Colonne1) / SUM(Colonne2)

### 9. PIÈGES À ÉVITER
❌ Ne pas oublier Calendrier pour dates
❌ Ne pas mélanger Date vs Heure (colonnes différentes)
❌ Ne pas supposer jointure si clé différente
❌ Ne pas ignorer doublons
❌ Ne pas mélanger Année/Trimestre/Mois

### 10. FORMAT RÉPONSE CHIFFRES
- Tonnage : T (tonnes)
- Carburant : L (litres)
- Performance : % ou ratio
- Dates : YYYY-MM-DD ou "Période XXX"
- Délais : jours, semaines, mois
"""

# ─────────────────────────────────────────
# TEMPLATES DE PROMPTS
# ─────────────────────────────────────────

PROMPT_TEMPLATES = {
    "simple_query": """Question utilisateur: {user_query}

Contexte disponible:
- Tables: {tables}
- Clés de jointure: {join_keys}
- Période couverte: 2023-2026

Répondre avec:
1. Confirmation question comprise
2. Tables utilisées
3. Approche (jointures, filtres)
4. Réponse chiffrée
5. Limitations""",

    "temporal_analysis": """Analyse temporelle demandée: {user_query}

Dimension temporelle: {temporal_dimension}
Filtre calendrier: {calendar_filter}
Tables: {tables}

Utiliser table Calendrier pour:
- Regroupement par {temporal_dimension}
- Filtrage {calendar_filter}

Répondre avec graphique ASCII ou tableau.""",

    "comparison": """Comparaison demandée: {user_query}

Entités à comparer: {entities}
Métriques: {metrics}
Période: {period}

Répondre avec tableau comparatif
Format: | Entité | Métrique1 | Métrique2 | Écart % |""",

    "complex_join": """Requête multi-tables: {user_query}

Tables impliquées: {tables}
Jointures: {joins}
Agrégations: {aggregations}

Étapes:
1. Table 1 + Table 2 via {join1}
2. Résultat + Table 3 via {join2}
3. Grouper par {group_by}
4. Calculer {aggregations}""",
}

# ─────────────────────────────────────────
# MAPPAGE COLONNES <-> CONCEPTS
# ─────────────────────────────────────────

COLUMN_CONCEPTS = {
    # Production
    "Tonnage": "Volume extrait en tonnes",
    "Quantité": "Nombre d'unités",
    "Date": "Dimension temporelle (clé calendrier)",
    "Equipement": "Machine/Engin utilisé",
    "N° CAMION": "Identifiant véhicule transport",
    "Heure": "Moment de la journée",
    
    # Carburant
    "Quantité Servie (L)": "Litre carburant distribué",
    "Consommation (L/h)": "Consommation horaire",
    "MACHINE": "Machine identifiée",
    
    # Budget
    "Année": "Année fiscale",
    "Mois": "Mois calendrier (01-12)",
    "Objectif": "Cible à atteindre",
    
    # Actions
    "Échéance": "Date limite réalisation",
    "Responsable": "Personne assignée",
    "Statut": "État avancement (%)ou catégorie",
    "Priorité": "Niveau urgence",
    
    # Calendrier
    "Année": "2023, 2024, 2025, 2026",
    "Trimestre": "Q1, Q2, Q3, Q4",
    "Saison": "Hiver, Printemps, Été, Automne",
    "Est_Jour_Ouvré": "Lundi-Vendredi (True/False)",
    "Est_Weekend": "Samedi-Dimanche (True/False)",
}

# ─────────────────────────────────────────
# EXEMPLES QUERIES SQL-LIKE (PSEUDO-CODE)
# ─────────────────────────────────────────

QUERY_EXAMPLES = {
    "tonnage_by_date": """
SELECT 
    cal.Date,
    SUM(ex.Tonnage) as Total_Tonnage
FROM Benene_1_Excavation ex
JOIN Calendrier cal ON ex.Date = cal.Date
WHERE cal.Année = 2024 AND cal.Mois = 1
GROUP BY cal.Date
ORDER BY cal.Date
    """,

    "efficacite_engin": """
SELECT 
    ex.Equipement,
    SUM(ex.Tonnage) / SUM(cb.Quantité_Servie) as Ratio_T_L
FROM Benene_1_Excavation ex
JOIN CARBURANT cb ON ex.Equipement = cb.Equipement AND ex.Date = cb.Date
GROUP BY ex.Equipement
ORDER BY Ratio_T_L DESC
    """,

    "budget_vs_reel": """
SELECT 
    b.Année,
    b.Mois,
    b.Tonnage_Objectif as Objectif,
    SUM(ex.Tonnage) as Reel,
    (SUM(ex.Tonnage) - b.Tonnage_Objectif) / b.Tonnage_Objectif * 100 as Ecart_Pct
FROM Budget b
LEFT JOIN Benene_1_Excavation ex ON 
    YEAR(ex.Date) = b.Année AND MONTH(ex.Date) = b.Mois
GROUP BY b.Année, b.Mois
    """,

    "actions_retard": """
SELECT 
    p.N_Action,
    p.Titre,
    p.Responsable,
    p.Echéance,
    DATEDIFF(day, p.Echéance, TODAY()) as Jours_Retard,
    s.Avancement_Pct
FROM PLAN_D_ACTIONS p
LEFT JOIN Suivi_des_actions s ON p.N_Action = s.N_Action
WHERE p.Echéance < TODAY() AND s.Avancement_Pct < 100
ORDER BY Jours_Retard DESC
    """,
}

# ─────────────────────────────────────────
# GUARDRAILS - VALIDATION RÉPONSE
# ─────────────────────────────────────────

VALIDATION_RULES = {
    "tonnage": {
        "unit": "T",
        "min": 0,
        "max": 100000,
        "precision": 2
    },
    "carburant": {
        "unit": "L",
        "min": 0,
        "max": 10000000,
        "precision": 1
    },
    "efficacite": {
        "unit": "T/L",
        "min": 0.1,
        "max": 5,
        "precision": 2
    },
    "pourcentage": {
        "unit": "%",
        "min": 0,
        "max": 100,
        "precision": 1
    }
}

# ─────────────────────────────────────────
# CONSEILS D'INTERPRÉTATION
# ─────────────────────────────────────────

INTERPRETATION_TIPS = {
    "low_efficiency": "Efficacité faible (<1 T/L) peut indiquer: problème mécanique, surcharge, trajet long",
    "high_consumption": "Consommation élevée: vérifier préventif, conditions travail difficiles",
    "missed_budget": "Objectif non atteint: Vérifier arrêts machines, maintenance, conditions météo",
    "behind_schedule": "Action en retard: Nécessite escalade, réajustement ressources ou délai",
    "seasonal_pattern": "Variations saisonnières: Hiver plus difficile, Été plus productif",
}

if __name__ == "__main__":
    print("Configuration Mistral LLM chargée")
    print(f"Modèle: {MISTRAL_CONFIG['model']}")
    print(f"Température: {LLM_PARAMETERS['temperature']}")
