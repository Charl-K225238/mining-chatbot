import os
import re

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLEAN_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "clean"))
INPUT_FILE_NAMES = [
    "rapport_exploitation_clean.txt",
    "rapport_exploration_clean.txt",
]
OUTPUT_FILE = os.path.join(BASE_DIR, "..", "docs", "Schema.md")

FILE_DESCRIPTION_MAP = {
    "chargeuses": "Liste des chargeuses et tonnages pour l'exploitation.",
    "liste engins": "Inventaire des engins et équipements miniers.",
    "objectifs": "Objectifs de production ou de performance.",
    "personnel": "Informations sur le personnel et leurs rôles.",
    "stocks": "Données de stock et de qualité.",
    "valeurs initiales": "Valeurs initiales associées aux stocks.",
    "zone excavation": "Zones d'excavation répertoriées.",
    "excavation": "Données d'excavation et de tonnage.",
    "journal": "Journal d'activité ou de suivi.",
    "shifts horaires": "Données horaires des shifts.",
    "shifts personnel": "Affectation du personnel par shift.",
    "qualite echantillons": "Qualité des échantillons miniers.",
    "qualite navires": "Qualité des navires.",
    "regul qté stock": "Régulation des quantités de stock.",
    "regul qualite stock": "Régulation de la qualité du stock.",
    "budget": "Données de budget de production et de descente.",
    "carburant": "Données de consommation de carburant et activités.",
    "descente minerai": "Descente journalière du minerai.",
    "plan d'actions du pges": "Plan d'actions du PGES.",
    "productivite port": "Productivité portuaire et suivi des voyages.",
    "suivi des actions": "Suivi des obligations et actions.",
    "transport minerai paa": "Transport de minerai PAA.",
    "rapport exploitation clean": "Rapport d'exploitation nettoyé.",
    "rapport exploration clean": "Rapport d'exploration nettoyé.",
    "calendar": "Table calendrier pour analyses temporelles.",
}

FILE_ROLE_MAP = {
    "benene_0_chargeuses": "Référentiel des chargeuses utilisées sur site avec leur capacité de tonnage.",
    "benene_0_liste_engins": "Inventaire global des engins et équipements du site.",
    "benene_1_excavation": "Suivi de la production d'excavation (volume, tonnage, zones, équipements).",
    "carburant": "Suivi de la consommation de carburant par engin, activité et cuves.",
    "descente_minerai": "Suivi du transport de minerai du site vers zones de stockage ou livraison.",
    "transport_minerai_paa": "Suivi détaillé du transport vers PAA (Port Autonome / point de livraison).",
    "plan_d_actions_du_pges": "Suivi des actions environnementales et obligations réglementaires.",
    "budget": "Prévision de production et descente mensuelle.",
    "suivi_des_actions": "Suivi des obligations et actions.",
    "benene_0_personnel": "Référentiel des employés.",
    "benene_1_shifts_personnel": "Affectation du personnel par shift.",
    "calendar": "Table calendrier utilisée pour relier toutes les données temporelles.",
}

FILE_USAGE_MAP = {
    "benene_0_chargeuses": [
        "Calcul de capacité de production",
        "Analyse performance engins",
    ],
    "benene_0_liste_engins": [
        "Référentiel commun entre production, carburant et transport",
    ],
    "benene_1_excavation": [
        "KPI production journalière",
        "Comparaison objectif vs réalisé",
        "Analyse performance équipements",
    ],
    "carburant": [
        "Analyse coût opérationnel",
        "Calcul productivité carburant",
        "Suivi consommation par machine",
    ],
    "descente_minerai": [
        "KPI logistique",
        "Suivi tonnage transporté",
        "Analyse performance transporteurs",
    ],
    "transport_minerai_paa": [
        "Logistique export",
        "Contrôle poids et conformité transport",
    ],
    "plan_d_actions_du_pges": [
        "Reporting conformité environnementale",
        "Suivi ANDE",
        "Audit ESG",
    ],
    "budget": [
        "Planification annuelle",
        "Comparaison réel vs objectif",
    ],
    "benene_0_personnel": [
        "Gestion RH",
        "Affectation des shifts",
    ],
    "benene_1_shifts_personnel": [
        "Planification des équipes",
        "Suivi des heures travaillées",
    ],
    "calendar": [
        "Analyses temporelles (semaines, mois, années)",
        "Relations temporelles dans Power BI",
        "Filtrage par périodes",
    ],
}

DOMAIN_FILE_MAP = {
    "🔥 Domaine Production": [
        "benene_1_excavation",
        "descente_minerai",
        "transport_minerai_paa",
        "productivite_port",
    ],
    "⛽ Domaine Logistique / Carburant": [
        "carburant",
    ],
    "🧪 Domaine Qualité": [
        "benene_2_qualite_echantillons",
        "benene_2_qualite_navires",
        "benene_3_regul_qualité_stock",
    ],
    "👥 Domaine RH / Opérations": [
        "benene_0_personnel",
        "benene_1_shifts_personnel",
        "suivi_des_actions",
    ],
    "📊 Domaine Planification / Budget": [
        "budget",
        "plan_d_actions_du_pges",
        "suivi_des_actions",
    ],
    "📅 Domaine Référentiel": [
        "benene_0_liste_engins",
        "benene_0_chargeuses",
        "calendar",
    ],
}

RELATION_GROUPS = {
    "🔥 Production": [
        "Excavation ↔ Descente Minerai ↔ Transport PAA",
    ],
    "⛽ Carburant": [
        "CARBURANT ↔ ENGINS ↔ ACTIVITES ↔ EXCAVATION",
    ],
    "🧪 Qualité": [
        "Echantillons ↔ Navires ↔ Stocks",
    ],
    "👥 RH": [
        "Personnel ↔ Shifts ↔ Activités machines",
    ],
    "📊 Planification": [
        "Budget ↔ Production réelle",
    ],
    "📅 Calendrier": [
        "Calendrier ↔ Toutes les tables temporelles",
    ],
}

QUALITY_SUMMARY = [
    "doublons fréquents",
    "incohérences de types (object vs float)",
    "colonnes non normalisées",
    "manque de clés uniques",
]

USAGE_SUMMARY = [
    "documentation data",
    "onboarding analystes",
    "base pour dashboard Power BI",
    "alimentation chatbot / RAG",
    "audit qualité données",
]


def normalize_key(file_name):
    return os.path.splitext(file_name)[0].lower().replace(" ", "_").replace("-", "_")


def describe_file(file_name):
    key = os.path.splitext(file_name)[0].lower().replace("_", " ").replace("-", " ")
    for pattern, description in FILE_DESCRIPTION_MAP.items():
        if pattern in key:
            return description
    readable = key.replace("  ", " ").strip()
    if readable:
        return f"Données issues du fichier `{readable}`."
    return "Données issues du fichier."


def get_file_role(file_name):
    key = normalize_key(file_name)
    for pattern, role in FILE_ROLE_MAP.items():
        if pattern in key:
            return role
    return None


def get_file_usage(file_name):
    key = normalize_key(file_name)
    for pattern, usage in FILE_USAGE_MAP.items():
        if pattern in key:
            return usage
    return []


def build_header():
    md = []
    md.append("# 🧠 DATA SCHEMA CATALOG\n")
    md.append("> Version : 1.0  \n> Objectif : documenter toutes les sources de données, leur rôle métier, leurs structures et leurs relations.\n")
    md.append("\n---\n")
    md.append("\n# 🧩 1. VUE GLOBALE DU MODÈLE\n")
    for domain, keys in DOMAIN_FILE_MAP.items():
        md.append(f"\n## {domain}\n")
        for key in keys:
            if key == "carburant":
                md.append(f"- CARBURANT (toutes les feuilles)\n")
            else:
                label = key.replace("_", " ").title()
                if key == "benene_3_regul_qualité_stock":
                    label = "Benene_3_Regul_Qualité_stock"
                elif key == "plan_d_actions_du_pges":
                    label = "PLAN D'ACTIONS DU PGES"
                elif key == "suivi_des_actions":
                    label = "Suivi des actions"
                elif key == "productivite_port":
                    label = "PRODUCTIVITE PORT"
                elif key == "transport_minerai_paa":
                    label = "TRANSPORT MINERAI PAA"
                elif key == "descente_minerai":
                    label = "DESCENTE MINERAI"
                md.append(f"- {label}\n")
    md.append("\n---\n")
    md.append("\n## ⭐ SCHÉMA EN ÉTOILE - CALENDRIER CENTRAL\n")
    md.append("\nLe modèle de données suit un **schéma en étoile** avec la table **Calendrier** au centre de toutes les analyses temporelles :\n")
    md.append("\n### 🗓️ Table Calendrier (Dimension Centrale)\n")
    md.append("- **23 colonnes temporelles** : Date, Année, Mois, Jour, Semaine, Trimestre, Saison, etc.\n")
    md.append("- **Période couverte** : 2023-2026 (1,461 jours)\n")
    md.append("- **Utilisation** : Filtrage et analyse temporelle de toutes les données opérationnelles\n")
    md.append("\n### 🔗 Connexions Temporelles\n")
    md.append("**Tables opérationnelles connectées au Calendrier :**\n")
    md.append("- `Benene_1_Excavation` → `Calendrier` (colonne `Date`)\n")
    md.append("- `DESCENTE MINERAI` → `Calendrier` (colonne `Date`)\n")
    md.append("- `TRANSPORT MINERAI PAA` → `Calendrier` (colonne `HEURE DEPART`)\n")
    md.append("\n**Tables budgétaires connectées au Calendrier :**\n")
    md.append("- `Budget` → `Calendrier` (colonnes `Année`, `Mois`)\n")
    md.append("- `PLAN D'ACTIONS DU PGES` → `Calendrier` (colonne `Échéance`)\n")
    md.append("\n### 🎯 Avantages du Schéma en Étoile\n")
    md.append("- **Filtrage temporel unifié** : Toutes les analyses utilisent la même dimension temporelle\n")
    md.append("- **Performance Power BI** : Optimisé pour les rapports et tableaux de bord\n")
    md.append("- **Évolutivité** : Facilite l'ajout de nouvelles tables opérationnelles\n")
    md.append("- **Cohérence temporelle** : Calendrier partagé pour éviter les incohérences\n")
    md.append("\n---\n")
    return md


def build_relations():
    md = []
    md.append("\n---\n")
    md.append("\n# 🔗 3. RELATIONS ENTRE TABLES\n")
    for group, relations in RELATION_GROUPS.items():
        md.append(f"\n## {group}\n")
        for relation in relations:
            md.append(f"- {relation}\n")
    return md


def build_quality_section():
    md = []
    md.append("\n---\n")
    md.append("\n# ⚠️ 4. QUALITÉ GLOBALE DES DONNÉES\n")
    md.append("\n## Problèmes récurrents\n")
    for item in QUALITY_SUMMARY:
        md.append(f"- {item}\n")
    md.append("\n## Recommandations\n")
    md.append("- créer IDs uniques par table\n")
    md.append("- standardiser types (dates, heures)\n")
    md.append("- définir clés de jointure\n")
    md.append("- normaliser noms de colonnes\n")
    return md


def build_usage_section():
    md = []
    md.append("\n---\n")
    md.append("\n# 🚀 5. UTILISATION DU SCHÉMA\n")
    md.append("\nCe fichier sert à :\n")
    for item in USAGE_SUMMARY:
        md.append(f"- {item}\n")
    return md


def find_input_file(): 
    candidates = []
    for name in INPUT_FILE_NAMES:
        candidates.append(os.path.join(BASE_DIR, name))
        candidates.append(os.path.join(CLEAN_DIR, name))

    for path in candidates:
        if os.path.exists(path):
            return path

    if os.path.isdir(CLEAN_DIR):
        for entry in os.listdir(CLEAN_DIR):
            if entry.lower().startswith("rapport_") and entry.lower().endswith("_clean.txt"):
                return os.path.join(CLEAN_DIR, entry)

    available = []
    if os.path.isdir(CLEAN_DIR):
        available = sorted(os.listdir(CLEAN_DIR))

    raise FileNotFoundError(
        "Fichier introuvable. Cherché :\n"
        + "\n".join([f" - {p}" for p in candidates])
        + ("\nFichiers disponibles dans Clean :\n" + "\n".join([f" - {entry}" for entry in available]) if available else "")
    )


# ─────────────────────────────────────────
# LECTURE FICHIER
# ─────────────────────────────────────────
def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────
# EXTRACTION DES BLOCS FICHIERS
# ─────────────────────────────────────────
def extract_files(text):
    pattern = r"#{60,}\n\s*FICHIER : (.*?)\n#{60,}"
    matches = list(re.finditer(pattern, text))

    sections = []

    for i, match in enumerate(matches):
        file_name = match.group(1).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        sections.append((file_name, text[start:end]))

    return sections


# ─────────────────────────────────────────
# EXTRACTION FEUILLES
# ─────────────────────────────────────────
def extract_sheets(section):
    pattern = r"─{30,}\n\s*(.*?)\n─{30,}"
    matches = list(re.finditer(pattern, section))

    sheets = []

    for i, match in enumerate(matches):
        sheet_name = match.group(1).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)

        sheets.append((sheet_name, section[start:end]))

    return sheets


# ─────────────────────────────────────────
# EXTRACTION COLONNES
# ─────────────────────────────────────────
def extract_columns(block):
    pattern = r"^\s{3,}(.+?)\s+(str|float64|float32|int64|int32|bool|category|datetime64\[us\]|datetime64\[ns\]|object)\b"
    return re.findall(pattern, block, re.MULTILINE)


# ─────────────────────────────────────────
# EXTRACTION VALEURS MANQUANTES
# ─────────────────────────────────────────
def extract_missing(block):
    pattern = r"- `(.+?)`\s*:\s*(\d+)\s*\(([\d\.]+)%\)\s*(🟢|🟡|🔴)"
    return re.findall(pattern, block)


def build_column_details(block):
    columns = extract_columns(block)
    missing = extract_missing(block)
    missing_map = {col: (n, pct, lvl) for col, n, pct, lvl in missing}

    lines = []
    date_columns = []

    for col, dtype in columns:
        if dtype.startswith("datetime") or "date" in col.lower() or "jour" in col.lower() or "année" in col.lower() or "year" in col.lower():
            date_columns.append(col)

        missing_info = missing_map.get(col)
        if missing_info:
            n, pct, lvl = missing_info
            lines.append(f"- `{col}` → `{dtype}` — manquant : {n} ({pct}%) {lvl}")
        else:
            lines.append(f"- `{col}` → `{dtype}` — aucune valeur manquante détectée")

    # Report columns detected in missing list but not in the standard column extraction.
    for col, n, pct, lvl in missing:
        if col not in {column for column, _ in columns}:
            lines.append(f"- `{col}` — manquant : {n} ({pct}%) {lvl}")

    return lines, bool(date_columns)


# ─────────────────────────────────────────
# SHAPE
# ─────────────────────────────────────────
def extract_shape(block):
    match = re.search(r"Dimensions\s*:\s*(\d+)\s*lignes\s*×\s*(\d+)\s*colonnes", block)
    if match:
        return match.group(1), match.group(2)
    return None, None


# ─────────────────────────────────────────
# PROBLÈMES
# ─────────────────────────────────────────
def detect_issues(block):
    issues = []

    if "Incohérences de types" in block:
        issues.append("⚠️ incohérences de types détectées")

    if "doublon" in block.lower():
        issues.append("⚠️ doublons détectés")

    return issues


# ─────────────────────────────────────────
# BUILD MARKDOWN
# ─────────────────────────────────────────
def build_schema(text):
    files = extract_files(text)

    md = []
    md.extend(build_header())
    md.append("\n# 📁 2. DESCRIPTION DÉTAILLÉE DES FICHIERS\n")
    md.append("\n---\n")

    for file_name, content in files:
        md.append(f"\n## 📁 {file_name}\n")

        file_role = get_file_role(file_name)
        if file_role:
            md.append(f"\n### 🎯 Rôle métier\n{file_role}\n")

        file_usage = get_file_usage(file_name)
        if file_usage:
            md.append("\n### 🔗 Utilisation\n")
            for usage in file_usage:
                md.append(f"- {usage}\n")

        file_description = describe_file(file_name)
        if file_description:
            md.append(f"\n- Description : {file_description}\n")

        sheets = extract_sheets(content)
        if sheets:
            md.append(f"\n- Nombre de feuilles : **{len(sheets)}**\n")

        for sheet_name, block in sheets:
            rows, cols = extract_shape(block)

            md.append(f"\n### 📄 Feuille : {sheet_name}\n")

            if rows and cols:
                md.append(f"- Dimensions : {rows} × {cols}\n")

            details, has_date_columns = build_column_details(block)
            if details:
                md.append("\n#### 🔠 Colonnes\n")
                for line in details:
                    md.append(f"{line}\n")

            if has_date_columns:
                md.append(
                    "\n#### 📅 Relation calendrier Power BI\n"
                    "- Cette feuille contient des colonnes de type date. En Power BI, privilégiez une table Calendrier calculée dédiée pour les relations temporelles.\n"
                )

            issues = detect_issues(block)
            if issues:
                md.append("\n#### ⚠️ Qualité des données\n")
                for i in issues:
                    md.append(f"- {i}\n")

        md.append("\n---\n")

    md.extend(build_relations())
    md.extend(build_quality_section())
    md.extend(build_usage_section())
    return "\n".join(md)


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    input_file = find_input_file()
    text = load_text(input_file)

    schema = build_schema(text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(schema)

    print(f"[OK] schema.md genere avec succes : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()