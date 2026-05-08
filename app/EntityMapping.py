"""
Entity Mapping - Mapping des entités et synonymes
Pour aider LLM à reconnaître variantes de noms
"""

# ─────────────────────────────────────────
# MAPPING TABLES - NOMS ALTERNATIFS
# ─────────────────────────────────────────

TABLE_ALIASES = {
    "Benene_1_Excavation": {
        "canonical": "Benene_1_Excavation",
        "aliases": [
            "excavation",
            "extraction",
            "production excavation",
            "tonnage excavé",
            "excavatrice",
            "excavage"
        ],
        "short": "EXCAVATION"
    },
    
    "DESCENTE MINERAI": {
        "canonical": "DESCENTE MINERAI",
        "aliases": [
            "descente",
            "descente de minerai",
            "transport descente",
            "tonnage descendu"
        ],
        "short": "DESCENTE"
    },
    
    "TRANSPORT MINERAI PAA": {
        "canonical": "TRANSPORT MINERAI PAA",
        "aliases": [
            "transport paa",
            "transport port",
            "paa",
            "transport minerai",
            "acheminement port"
        ],
        "short": "TRANSPORT"
    },
    
    "CARBURANT": {
        "canonical": "CARBURANT",
        "aliases": [
            "carburant",
            "essence",
            "gasoil",
            "consommation fuel",
            "consumption",
            "litres"
        ],
        "short": "FUEL"
    },
    
    "Budget": {
        "canonical": "Budget",
        "aliases": [
            "budget",
            "objectif",
            "objectifs",
            "target",
            "prévisions",
            "forecast"
        ],
        "short": "BUDGET"
    },
    
    "PLAN D'ACTIONS DU PGES": {
        "canonical": "PLAN D'ACTIONS DU PGES",
        "aliases": [
            "pges",
            "plan actions",
            "actions pges",
            "plan d'actions",
            "actions",
            "obligation"
        ],
        "short": "ACTIONS"
    },
    
    "Suivi des actions": {
        "canonical": "Suivi des actions",
        "aliases": [
            "suivi",
            "suivi actions",
            "tracking",
            "progression",
            "avancement"
        ],
        "short": "SUIVI"
    },
    
    "Benene_0_Liste_engins": {
        "canonical": "Benene_0_Liste_engins",
        "aliases": [
            "liste engins",
            "engins",
            "équipements",
            "machines",
            "equipment",
            "fleet"
        ],
        "short": "ENGINS"
    },
    
    "Benene_0_Chargeuses": {
        "canonical": "Benene_0_Chargeuses",
        "aliases": [
            "chargeuses",
            "chargeuse",
            "loaders",
            "loader"
        ],
        "short": "CHARGEUSES"
    },
    
    "Benene_0_Personnel": {
        "canonical": "Benene_0_Personnel",
        "aliases": [
            "personnel",
            "personnes",
            "operateurs",
            "responsables",
            "staff",
            "employees"
        ],
        "short": "PERSONNEL"
    },
    
    "Calendrier": {
        "canonical": "Calendrier",
        "aliases": [
            "calendrier",
            "calendar",
            "dates",
            "dimension temps",
            "temporal",
            "time"
        ],
        "short": "CAL"
    },
}

# ─────────────────────────────────────────
# MAPPING COLONNES - NOMS ALTERNATIFS
# ─────────────────────────────────────────

COLUMN_ALIASES = {
    "Date": {
        "canonical": "Date",
        "tables": ["Benene_1_Excavation", "DESCENTE MINERAI", "CARBURANT"],
        "aliases": ["date", "jour", "day", "date_jour"],
        "data_type": "datetime",
        "unit": "YYYY-MM-DD"
    },
    
    "Tonnage": {
        "canonical": "Tonnage",
        "tables": ["Benene_1_Excavation", "DESCENTE MINERAI"],
        "aliases": ["tonnage", "quantité", "volume", "tons", "t"],
        "data_type": "float",
        "unit": "T"
    },
    
    "Equipement": {
        "canonical": "Equipement",
        "tables": ["Benene_1_Excavation", "CARBURANT"],
        "aliases": ["equipement", "machine", "engin", "equipment", "excavator"],
        "data_type": "string",
        "unit": "ID"
    },
    
    "N° CAMION": {
        "canonical": "N° CAMION",
        "tables": ["DESCENTE MINERAI", "TRANSPORT MINERAI PAA"],
        "aliases": ["camion", "truck", "n°camion", "numero camion"],
        "data_type": "string",
        "unit": "ID"
    },
    
    "Quantité Servie (L)": {
        "canonical": "Quantité Servie (L)",
        "tables": ["CARBURANT"],
        "aliases": ["quantité", "litre", "litres", "l", "fuel"],
        "data_type": "float",
        "unit": "L"
    },
    
    "Année": {
        "canonical": "Année",
        "tables": ["Budget", "Calendrier"],
        "aliases": ["année", "year", "ans"],
        "data_type": "int",
        "unit": "YYYY"
    },
    
    "Mois": {
        "canonical": "Mois",
        "tables": ["Budget", "Calendrier"],
        "aliases": ["mois", "month"],
        "data_type": "int",
        "unit": "MM"
    },
    
    "Echéance": {
        "canonical": "Échéance",
        "tables": ["PLAN D'ACTIONS DU PGES"],
        "aliases": ["echéance", "deadline", "date limite", "due date"],
        "data_type": "datetime",
        "unit": "YYYY-MM-DD"
    },
    
    "Responsable": {
        "canonical": "Responsable",
        "tables": ["PLAN D'ACTIONS DU PGES", "Suivi des actions"],
        "aliases": ["responsable", "manager", "owner", "assigné"],
        "data_type": "string",
        "unit": "NAME"
    },
}

# ─────────────────────────────────────────
# MAPPING METRICS - CALCULS COURANTS
# ─────────────────────────────────────────

METRIC_ALIASES = {
    "efficiency": {
        "canonical": "Efficacité",
        "aliases": ["efficacité", "efficiency", "ratio", "productivité"],
        "formula": "SUM(Tonnage) / SUM(Carburant_L)",
        "unit": "T/L",
        "tables": ["Benene_1_Excavation", "CARBURANT"]
    },
    
    "performance": {
        "canonical": "Performance",
        "aliases": ["performance", "taux", "rate", "% atteinte"],
        "formula": "Réalisé / Objectif * 100",
        "unit": "%",
        "tables": ["Budget", "Benene_1_Excavation"]
    },
    
    "delay": {
        "canonical": "Retard",
        "aliases": ["retard", "delay", "jours de retard", "jours_retard"],
        "formula": "DATEDIFF(TODAY(), Échéance)",
        "unit": "days",
        "tables": ["PLAN D'ACTIONS DU PGES"]
    },
    
    "total_tonnage": {
        "canonical": "Tonnage Total",
        "aliases": ["tonnage total", "total tonnage", "sum tonnage"],
        "formula": "SUM(Tonnage)",
        "unit": "T",
        "tables": ["Benene_1_Excavation"]
    },
    
    "total_fuel": {
        "canonical": "Carburant Total",
        "aliases": ["carburant total", "total fuel", "consommation totale"],
        "formula": "SUM(Quantité Servie)",
        "unit": "L",
        "tables": ["CARBURANT"]
    },
}

# ─────────────────────────────────────────
# MAPPING CONCEPTS MÉTIER
# ─────────────────────────────────────────

BUSINESS_CONCEPTS = {
    "production": {
        "definition": "Volume total extrait en tonnes",
        "related_tables": ["Benene_1_Excavation", "DESCENTE MINERAI"],
        "keywords": ["production", "extraction", "excavation", "tonnage"],
        "key_metric": "Tonnage"
    },
    
    "transport": {
        "definition": "Mouvement du minerai vers zones stockage/port",
        "related_tables": ["DESCENTE MINERAI", "TRANSPORT MINERAI PAA"],
        "keywords": ["transport", "descente", "acheminement", "livraison"],
        "key_metric": "Tonnage"
    },
    
    "efficiency": {
        "definition": "Ratio production par unité de carburant",
        "related_tables": ["Benene_1_Excavation", "CARBURANT"],
        "keywords": ["efficacité", "performance", "productivity", "ratio"],
        "key_metric": "Tonnes/Litre"
    },
    
    "compliance": {
        "definition": "Respect des objectifs environnementaux/légaux",
        "related_tables": ["PLAN D'ACTIONS DU PGES", "Suivi des actions"],
        "keywords": ["actions", "obligations", "conformité", "compliance"],
        "key_metric": "% Avancement"
    },
    
    "planning": {
        "definition": "Comparaison Objectif vs Réalisation",
        "related_tables": ["Budget", "Benene_1_Excavation"],
        "keywords": ["budget", "objectif", "prévision", "forecast"],
        "key_metric": "% Performance"
    },
}

# ─────────────────────────────────────────
# UTILITÉ PARSER
# ─────────────────────────────────────────

def resolve_table_alias(user_input: str) -> str:
    """Résoudre alias table → nom canonique"""
    user_input_lower = user_input.lower()
    
    for canonical, aliases_dict in TABLE_ALIASES.items():
        for alias in aliases_dict.get('aliases', []):
            if alias.lower() in user_input_lower:
                return canonical
    
    return user_input

def resolve_column_alias(user_input: str, table_context: str = None) -> str:
    """Résoudre alias colonne → nom canonique"""
    user_input_lower = user_input.lower()
    
    for canonical, aliases_dict in COLUMN_ALIASES.items():
        for alias in aliases_dict.get('aliases', []):
            if alias.lower() in user_input_lower:
                # Vérifier contexte table si fourni
                if table_context:
                    if table_context in aliases_dict.get('tables', []):
                        return canonical
                else:
                    return canonical
    
    return user_input

def get_table_joins(table_name: str) -> dict:
    """Retourner jointures disponibles pour table"""
    from ..docs.Relations import RELATIONSHIPS
    return RELATIONSHIPS.get(table_name, [])

def suggest_table(keywords: list) -> list:
    """Suggérer tables basées sur mots-clés"""
    matches = []
    keywords_lower = [k.lower() for k in keywords]
    
    for table, aliases_dict in TABLE_ALIASES.items():
        table_aliases = [a.lower() for a in aliases_dict.get('aliases', [])]
        if any(kw in table_aliases for kw in keywords_lower):
            matches.append(table)
    
    return matches

def resolve_metric(metric_name: str) -> dict:
    """Retourner info métrique demandée"""
    metric_lower = metric_name.lower()
    
    for metric_key, metric_info in METRIC_ALIASES.items():
        metric_aliases = [a.lower() for a in metric_info.get('aliases', [])]
        if metric_key.lower() in metric_lower or any(a in metric_lower for a in metric_aliases):
            return metric_info
    
    return None

# ─────────────────────────────────────────
# UTILITIES POUR LLM
# ─────────────────────────────────────────

def build_entity_reference() -> str:
    """Construire référence entités pour LLM"""
    output = "## ENTITY MAPPING REFERENCE\n\n"
    
    output += "### TABLES\n"
    for table, info in TABLE_ALIASES.items():
        aliases_str = ", ".join(info['aliases'][:3])
        output += f"- **{table}** (aka: {aliases_str}...)\n"
    
    output += "\n### COLONNES CLÉS\n"
    for col, info in COLUMN_ALIASES.items():
        output += f"- **{col}** ({info['data_type']}) → {info['unit']}\n"
    
    output += "\n### METRICS\n"
    for metric_key, info in METRIC_ALIASES.items():
        output += f"- **{info['canonical']}** : {info['formula']}\n"
    
    return output

if __name__ == "__main__":
    # Test resolvers
    print(resolve_table_alias("donnez moi les productions excavation"))
    print(resolve_column_alias("quel tonnage"))
    print(suggest_table(["production", "excavation"]))


class EntityMapper:
    """Classe pour mapper les entités et gérer les alias."""

    def __init__(self):
        self.table_aliases = TABLE_ALIASES
        self.column_aliases = COLUMN_ALIASES
        self.metric_aliases = METRIC_ALIASES

    def extract_entities(self, query: str) -> list:
        """Extraire les entités pertinentes de la requête."""
        entities = []
        query_lower = query.lower()

        # Chercher tables
        for table, info in self.table_aliases.items():
            for alias in info.get('aliases', []):
                if alias.lower() in query_lower:
                    entities.append({"type": "table", "name": table, "canonical": info["canonical"]})

        # Chercher colonnes
        for col, info in self.column_aliases.items():
            for alias in info.get('aliases', []):
                if alias.lower() in query_lower:
                    entities.append({"type": "column", "name": col, "canonical": info["canonical"]})

        # Chercher métriques
        for metric_key, info in self.metric_aliases.items():
            for alias in info.get('aliases', []):
                if alias.lower() in query_lower:
                    entities.append({"type": "metric", "name": metric_key, "info": info})

        return entities

    def get_related_data(self, entity: dict) -> dict:
        """Obtenir les données liées à une entité."""
        if entity["type"] == "table":
            table_name = entity["canonical"]
            # Données simplifiées pour l'instant
            return {
                "tables": [table_name],
                "snippets": [f"Table {table_name} contient des données pertinentes"]
            }
        return {"tables": [], "snippets": []}
    print(resolve_metric("efficacité"))
