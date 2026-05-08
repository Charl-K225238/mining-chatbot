"""
explore_clean.py
─────────────────────────────────────────────────────────────────
Explore tous les fichiers .xlsx/.csv du dossier CLEAN_FOLDER et
produit un rapport focalisé sur :
  • Types de données (avec signalement si type inattendu)
  • Valeurs manquantes (nombre + %)
  • Doublons
  • Aperçu (5 premières lignes)

Les anomalies de type outlier/IQR sont volontairement omises car
non pertinentes à ce stade de la chaîne de traitement.
─────────────────────────────────────────────────────────────────
"""

import pandas as pd
import os
import sys
from datetime import datetime
from openpyxl import load_workbook

# ─────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────
CLEAN_FOLDER = os.path.dirname(os.path.abspath(__file__))
LOG_FILE     = os.path.join(CLEAN_FOLDER, "rapport_exploration_clean.txt")

MISSING_LIKE = ["", " ", "NA", "N/A", "na", "n/a", "NULL", "null", "None", "-", "?"]

# Seuil d'alerte valeurs manquantes (%)
MISSING_WARN  = 20.0   # orange : entre 20 % et 50 %
MISSING_CRIT  = 50.0   # rouge  : > 50 %


# ─────────────────────────────────────────
#  LOGGER
# ─────────────────────────────────────────
class Logger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "w", encoding="utf-8")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.write(f"{'=' * 60}\n  RAPPORT D'EXPLORATION — DONNÉES NETTOYÉES\n  Généré le : {now}\n{'=' * 60}\n\n")

    def write(self, msg):
        self.terminal.write(msg)
        self.log.write(msg)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def section(logger, title):
    logger.write(f"\n{'─' * 50}\n  {title}\n{'─' * 50}\n")


# ─────────────────────────────────────────
#  EXPLORATION SIMPLIFIÉE
# ─────────────────────────────────────────
def flag_missing(pct: float) -> str:
    """Retourne un indicateur visuel selon le taux de valeurs manquantes."""
    if pct >= MISSING_CRIT:
        return "🔴"
    elif pct >= MISSING_WARN:
        return "🟡"
    return "🟢"


def check_types(df: pd.DataFrame) -> list[str]:
    """
    Signale les colonnes dont le type semble incohérent :
    - Colonne avec 'date'/'Date' dans le nom mais pas de type datetime
    - Colonne entièrement numérique mais stockée en object
    """
    warnings = []
    for col in df.columns:
        col_lower = str(col).lower()
        dtype = df[col].dtype

        # Colonne au nom "date" mais pas datetime
        if ("date" in col_lower or "heure" in col_lower) and not pd.api.types.is_datetime64_any_dtype(dtype):
            warnings.append(f"⚠️  '{col}' (type={dtype}) — nom suggère une date/heure")

        # Colonne object mais 100 % numérique
        if dtype == object:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                num_rate = pd.to_numeric(non_null.astype(str), errors="coerce").notna().mean()
                if num_rate == 1.0:
                    warnings.append(f"⚠️  '{col}' (type=object) — contient uniquement des nombres, conversion possible")
    return warnings


def explore_dataframe(df: pd.DataFrame, logger: Logger, label: str):
    section(logger, label)

    logger.write(f"\n📐 Dimensions : {df.shape[0]} lignes × {df.shape[1]} colonnes\n")

    # ── Types ──────────────────────────────────────────────────
    logger.write("\n🔠 Types de données :\n")
    for col in df.columns:
        logger.write(f"   {col:<45} {str(df[col].dtype)}\n")

    # Signalement incohérences de types
    type_warns = check_types(df)
    if type_warns:
        logger.write("\n🔍 Incohérences de types :\n")
        for w in type_warns:
            logger.write(f"   {w}\n")

    # ── Valeurs manquantes ─────────────────────────────────────
    missing_count = df.isnull().sum()
    missing_pct   = (df.isnull().mean() * 100).round(2)
    has_missing   = missing_count[missing_count > 0]

    logger.write("\n❓ Valeurs manquantes :\n")
    if has_missing.empty:
        logger.write("   ✅ Aucune valeur manquante\n")
    else:
        logger.write(f"   {'Colonne':<45} {'Manquant':>10}  {'%':>7}  Niveau\n")
        logger.write(f"   {'─' * 45} {'─' * 10}  {'─' * 7}  {'─' * 6}\n")
        for col in has_missing.index:
            n   = missing_count[col]
            pct = missing_pct[col]
            flag = flag_missing(pct)
            logger.write(f"   {str(col):<45} {n:>10}  {pct:>6.1f}%  {flag}\n")
        logger.write(f"\n   Légende : 🟢 < {MISSING_WARN}%   🟡 {MISSING_WARN}–{MISSING_CRIT}%   🔴 > {MISSING_CRIT}%\n")

    # ── Doublons ───────────────────────────────────────────────
    n_dup = df.duplicated().sum()
    logger.write(f"\n🔁 Doublons : ")
    if n_dup == 0:
        logger.write("✅ Aucun doublon\n")
    else:
        logger.write(f"⚠️  {n_dup} doublon(s) détecté(s)\n")

    # ── Aperçu ─────────────────────────────────────────────────
    logger.write("\n🔍 Aperçu (5 premières lignes) :\n")
    logger.write(str(df.head()) + "\n")


# ─────────────────────────────────────────
#  SCAN & CHARGEMENT
# ─────────────────────────────────────────
def collect_files(root: str) -> list:
    collected = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith((".xlsx", ".csv")) and not filename.startswith("~$"):
                collected.append(os.path.join(dirpath, filename))
    return sorted(collected)


def get_visible_sheets(filepath: str):
    wb = load_workbook(filepath, read_only=True, data_only=True)
    visible = [ws.title for ws in wb.worksheets if ws.sheet_state == "visible"]
    wb.close()
    return visible


# ─────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────
def main():
    logger = Logger(LOG_FILE)
    sys.stdout = logger

    files = collect_files(CLEAN_FOLDER)

    if not files:
        logger.write("⚠️  Aucun fichier trouvé.\n")
        logger.close()
        return

    logger.write(f"📁 {len(files)} fichier(s) trouvé(s) :\n")
    for f in files:
        logger.write(f"  • {os.path.relpath(f, CLEAN_FOLDER)}\n")

    for filepath in files:
        label = os.path.relpath(filepath, CLEAN_FOLDER)
        logger.write(f"\n\n{'#' * 60}\n  FICHIER : {label}\n{'#' * 60}\n")

        try:
            if filepath.endswith(".csv"):
                df = pd.read_csv(filepath, na_values=MISSING_LIKE)
                explore_dataframe(df, logger, label)
            else:
                sheets = get_visible_sheets(filepath)
                for sheet in sheets:
                    try:
                        df = pd.read_excel(filepath, sheet_name=sheet, na_values=MISSING_LIKE)
                        explore_dataframe(df, logger, f"{label} › {sheet}")
                    except Exception as e:
                        logger.write(f"\n❌ Erreur sur '{sheet}' : {e}\n")

        except Exception as e:
            logger.write(f"\n❌ Erreur : {e}\n")

    # ── Résumé global ──────────────────────────────────────────
    logger.write(f"\n\n{'=' * 60}\n  RÉSUMÉ GLOBAL\n{'=' * 60}\n")
    logger.write(f"  Fichiers explorés : {len(files)}\n")
    logger.write(f"  Légende niveaux de valeurs manquantes :\n")
    logger.write(f"    🟢 Bon       : < {MISSING_WARN}% de valeurs manquantes\n")
    logger.write(f"    🟡 Attention : {MISSING_WARN}–{MISSING_CRIT}% de valeurs manquantes\n")
    logger.write(f"    🔴 Critique  : > {MISSING_CRIT}% de valeurs manquantes\n")
    logger.write(f"\n  ✅ Rapport sauvegardé : {LOG_FILE}\n{'=' * 60}\n")

    sys.stdout = logger.terminal
    logger.close()
    print(f"\n✅ Rapport sauvegardé dans : {LOG_FILE}")


if __name__ == "__main__":
    main()
