"""Mapping des relations entre tables du modèle avec clés de jointure."""

RELATIONSHIPS = {
    "Benene_1_Excavation": [
        {"table": "DESCENTE MINERAI", "join_on": ["Date", "Equipement"]},
        {"table": "TRANSPORT MINERAI PAA", "join_on": ["Date"]},
        {"table": "Calendrier", "join_on": ["Date"]},
        {"table": "CARBURANT", "join_on": ["Equipement"]},
        {"table": "Budget", "join_on": ["Année", "Mois"]}
    ],
    "DESCENTE MINERAI": [
        {"table": "TRANSPORT MINERAI PAA", "join_on": ["Date", "N° CAMION"]},
        {"table": "Calendrier", "join_on": ["Date"]}
    ],
    "TRANSPORT MINERAI PAA": [
        {"table": "Calendrier", "join_on": ["HEURE DEPART"]}
    ],
    "CARBURANT": [
        {"table": "Benene_0_Liste_engins", "join_on": ["Engin/Equipement"]}
    ],
    "Benene_1_Shifts_personnel": [
        {"table": "Benene_0_Personnel", "join_on": ["ID"]},
        {"table": "CARBURANT", "join_on": ["Equipement"]},
        {"table": "Suivi des actions", "join_on": ["Responsable R2M"]}
    ],
    "Budget": [
        {"table": "Calendrier", "join_on": ["Année", "Mois"]},
        {"table": "PLAN D'ACTIONS DU PGES", "join_on": ["Année", "Mois"]}
    ],
    "PLAN D'ACTIONS DU PGES": [
        {"table": "Calendrier", "join_on": ["Échéance"]},
        {"table": "Suivi des actions", "join_on": ["Responsable"]}
    ],
    "Suivi des actions": [
        {"table": "Benene_0_Personnel", "join_on": ["Responsable R2M"]}
    ]
}


def get_related_tables(table_name):
    """Retourne les tables liées à la table donnée avec les clés de jointure."""
    return RELATIONSHIPS.get(table_name, [])


def get_join_keys(table1, table2):
    """Retourne les clés de jointure entre deux tables (cherche dans les deux sens)."""
    # Cherche d'abord table1 -> table2
    relations = get_related_tables(table1)
    for rel in relations:
        if rel["table"] == table2:
            return rel["join_on"]

    # Si pas trouvé, cherche table2 -> table1
    relations = get_related_tables(table2)
    for rel in relations:
        if rel["table"] == table1:
            return rel["join_on"]

    return []
