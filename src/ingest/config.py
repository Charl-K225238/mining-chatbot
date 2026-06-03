"""
Configuration de lecture pour chaque fichier Excel source.

Chaque entrée dans TABLES décrit :
- file        : nom du fichier dans data/raw/
- sheet       : feuille à lire
- date_cols   : colonnes à parser comme date
- numeric_cols: colonnes à forcer en float
- drop_cols   : colonnes à supprimer (artefacts Excel, URLs internes…)
- header_row  : numéro de la ligne d'en-tête (0 par défaut)
- kind        : "timeseries" | "reference" | "journal"
"""

from dataclasses import dataclass, field


@dataclass
class TableConfig:
    file: str
    sheet: str
    date_cols: list[str] = field(default_factory=list)
    numeric_cols: list[str] = field(default_factory=list)
    drop_cols: list[str] = field(default_factory=list)
    header_row: int = 0
    kind: str = "timeseries"


TABLES: dict[str, TableConfig] = {
    # ── Référentiels ───────────────────────────────────────────────────────────
    "chargeuses": TableConfig(
        file="Benene_0_Chargeuses.xlsx",
        sheet="Benene_0_Chargeuses",
        numeric_cols=["Tonnage"],
        kind="reference",
    ),
    "engins": TableConfig(
        file="Benene_0_Liste_engins.xlsx",
        sheet="Benene_0_Liste_engins",
        drop_cols=["Application créée par", "Application modifiée par"],
        kind="reference",
    ),
    "personnel": TableConfig(
        file="Benene_0_Personnel.xlsx",
        sheet="Benene_0_Personnel",
        date_cols=["Date de départ"],
        numeric_cols=["ID"],
        kind="reference",
    ),
    "stocks_ref": TableConfig(
        file="Benene_0_Stocks.xlsx",
        sheet="Benene_0_Stocks",
        drop_cols=["URL absolue codée"],
        kind="reference",
    ),
    "valeurs_initiales": TableConfig(
        file="Benene_0_Valeurs_initiales.xlsx",
        sheet="Benene_0_Valeurs_initiales",
        date_cols=["Date"],
        numeric_cols=["Valeur"],
        kind="reference",
    ),
    "zones_excavation": TableConfig(
        file="Benene_0_Zone_excavation.xlsx",
        sheet="Benene_0_Zone_excavation",
        numeric_cols=["Teneur Al2O3 prévue", "Teneur SIO2 prévue"],
        kind="reference",
    ),
    "budget": TableConfig(
        file="Budget.xlsx",
        sheet="Target",
        numeric_cols=["Tonnage à produire", "Tonnage à descendre"],
        kind="reference",
    ),
    "objectifs": TableConfig(
        file="Benene_0_Objectifs.xlsx",
        sheet="Benene_0_Objectifs",
        date_cols=["Date"],
        numeric_cols=["Excavation Prévue (T)", "Descente Prévue (T)"],
        kind="timeseries",
    ),
    "pges_actions": TableConfig(
        file="PLAN D'ACTIONS DU PGES.xlsx",
        sheet="LEB",
        header_row=3,
        date_cols=["Date de réalisation sous-action", "Échéance"],
        kind="reference",
    ),
    "suivi_actions": TableConfig(
        file="Suivi des actions.xlsx",
        sheet="Obligations",
        date_cols=["Période (début)", "Période (fin)", "Deadline"],
        numeric_cols=["% Avancement"],
        drop_cols=["Unnamed: 0"],
        kind="reference",
    ),
    # ── Séries temporelles — Exploitation ─────────────────────────────────────
    "descente_minerai": TableConfig(
        file="DESCENTE MINERAI.xlsx",
        sheet="ALL",
        date_cols=["DATE"],
        numeric_cols=[
            "NOMBRE VOYAGE",
            "TONNAGE / VOYAGE",
            "QUANTITE JOURNALIERE DESCENDUE (T)",
        ],
    ),
    "excavation": TableConfig(
        file="Benene_1_Excavation.xlsx",
        sheet="Benene_1_Excavation",
        date_cols=["Date"],
        numeric_cols=[
            "Volume excavé (m3)",
            "Tonnage QD",
            "Tonnage QD transfere en BQ",
            "Tonnage QD transfere en MQ",
            "Tonnage MQ",
            "Linéaire jour (m)",
            "Profondeur moyenne (m)",
            "Ecart (cm)",
            "Volume excavé tenant compte l'écart(m3)",
            "Tonnage excavé estimé (T)",
            "Tonnage se referant à l'ecart  (T)",
            "Tonnage BQ",
            "Métre linéaire (m)",
        ],
    ),
    "shifts_horaires": TableConfig(
        file="Benene_1_Shifts_horaires.xlsx",
        sheet="Benene_1_Shifts_horaires",
        date_cols=["Date"],
    ),
    "shifts_personnel": TableConfig(
        file="Benene_1_Shifts_personnel.xlsx",
        sheet="Benene_1_Shifts_personnel",
        date_cols=["Date"],
    ),
    "journal": TableConfig(
        file="Benene_1_Journal.xlsx",
        sheet="Benene_1_Journal",
        date_cols=["Date"],
        kind="journal",
    ),
    # ── Séries temporelles — Qualité ───────────────────────────────────────────
    "qualite_echantillons": TableConfig(
        file="Benene_2_Qualite_echantillons.xlsx",
        sheet="Benene_2_Qualite_echantillons",
        date_cols=[
            "Date Echantillonnage",
            "Date Expédition",
            "Date préparation mecanique / Date Réception Labo",
            "Date Publication résultats",
        ],
        numeric_cols=["POIDS", "Tonnage/Ech", "Al2O3", "Fe2O3", "SiO2"],
    ),
    "qualite_navires": TableConfig(
        file="Benene_2_Qualite_navires.xlsx",
        sheet="Benene_2_Qualite_navires",
        date_cols=[
            "Date arrivée PAA",
            "Date échantillonnage",
            "Date publication résultats",
        ],
    ),
    "regul_qte_stock": TableConfig(
        file="Benene_3_Regul_Qté_stock.xlsx",
        sheet="Benene_3_Regul_Qté_stock",
        date_cols=["Date"],
        numeric_cols=["Valeur (T)"],
    ),
    "regul_qualite_stock": TableConfig(
        file="Benene_3_Regul_Qualité_stock.xlsx",
        sheet="Benene_3_Regul_Qualité_stock",
        date_cols=["Date"],
    ),
    # ── Séries temporelles — Transport ────────────────────────────────────────
    "transport_minerai_paa": TableConfig(
        file="TRANSPORT MINERAI PAA.xlsx",
        sheet="TRANSPORT MINERAI PAA",
        date_cols=["DATE DEPART", "DATE ARRIVEE PAA"],
        numeric_cols=[
            "P1 TARE (Kg)",
            "POIDS CHARGEE P2 (Kg)",
            "QUANTITE TRANSPORTEE (Kg)",
            "P1 TARE (Kg) PAA",
            "POIDS CHARGEE P2 (Kg) PAA",
            "QUANTITE TRANSPORTEE PAA (Kg)",
            "DIFFERENCE QUANTITE VALEUR",
            "DIFFERENCE QUANTITE %",
        ],
    ),
    # ── Séries temporelles — Carburant ────────────────────────────────────────
    "carburant_activites": TableConfig(
        file="CARBURANT.xlsx",
        sheet="ACTIVITES",
        date_cols=["Date"],
        numeric_cols=["heure", "km début", "km fin", "Vit. moy (km/h)"],
    ),
    "carburant_citerne": TableConfig(
        file="CARBURANT.xlsx",
        sheet="CITERN IVEQI (2)",
        date_cols=["Date"],
        numeric_cols=[
            "Quantité Initiale Théorique (L)",
            "Depotage",
            "Quantité Servie (L)",
            "Quantité Restante (L)",
        ],
    ),
    # ── Port ──────────────────────────────────────────────────────────────────
    "productivite_loading": TableConfig(
        file="PRODUCTIVITE PORT.xlsx",
        sheet="LOADING RATE",
        date_cols=["DATE"],
        numeric_cols=["QUANTITE CHARGEE"],
    ),
    "productivite_navires": TableConfig(
        file="PRODUCTIVITE PORT.xlsx",
        sheet="VOYAGE NAVIRE",
        date_cols=["DATE ARRIVEE", "DATE DE DEPART"],
        numeric_cols=["OBJECTIF QUANTITE", "NOMBRE DE JOURS OPERATIONS PREVUS"],
    ),
}
