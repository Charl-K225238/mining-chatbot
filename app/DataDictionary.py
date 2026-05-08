"""Data dictionary contenant les définitions métier des tables et feuilles du modèle."""

from typing import Dict, Any, Optional

DATA_DICTIONARY = {
    "Benene_0_Chargeuses": {
        "label": "Chargeuses",
        "description": "Référentiel des chargeuses utilisées sur site avec leur capacité de tonnage.",
        "business_usage": [
            "Calcul de capacité de production",
            "Analyse performance engins"
        ]
    },
    "Benene_0_Liste_engins": {
        "label": "Liste des engins",
        "description": "Référentiel global des engins et équipements du site.",
        "business_usage": [
            "Référentiel commun entre production, carburant et transport"
        ]
    },
    "Benene_1_Excavation": {
        "label": "Excavation",
        "description": "Suivi de la production d'excavation (volume, tonnage, équipements, zones).",
        "business_usage": [
            "KPI production journalière",
            "Comparaison objectif vs réalisé",
            "Analyse performance équipements"
        ]
    },
    "CARBURANT": {
        "label": "Carburant",
        "description": "Suivi de la consommation de carburant par engin et activité.",
        "business_usage": [
            "Analyse coût opérationnel",
            "Calcul productivité carburant",
            "Suivi consommation par machine"
        ]
    },
    "DESCENTE MINERAI": {
        "label": "Descente minerai",
        "description": "Suivi du transport du minerai depuis le site vers stockage.",
        "business_usage": [
            "KPI logistique",
            "Suivi tonnage transporté",
            "Analyse performance transporteurs"
        ]
    },
    "TRANSPORT MINERAI PAA": {
        "label": "Transport minerai PAA",
        "description": "Suivi détaillé du transport vers le port (PAA).",
        "business_usage": [
            "Logistique export",
            "Suivi tonnage exporté",
            "Performance transport portuaire"
        ]
    },
    "Budget": {
        "label": "Budget",
        "description": "Prévision de production et descente mensuelle.",
        "business_usage": [
            "Planification annuelle",
            "Comparaison réel vs objectif"
        ]
    }
}

class DataDictionary:
    """Classe pour gérer le dictionnaire de données."""

    def __init__(self):
        self.data = DATA_DICTIONARY

    def get_definition(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Obtenir la définition d'une table."""
        return self.data.get(table_name)

    def search_tables(self, query: str) -> list:
        """Rechercher des tables par mot-clé."""
        results = []
        query_lower = query.lower()
        for table_name, definition in self.data.items():
            if (query_lower in table_name.lower() or
                query_lower in definition.get("label", "").lower() or
                query_lower in definition.get("description", "").lower()):
                results.append(table_name)
        return results