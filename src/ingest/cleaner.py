"""
Nettoyage des DataFrames issus des fichiers Excel.

Règles :
- Les doublons sont conservés (signification métier).
- Les valeurs nulles numériques restent NaN (pas de remplacement par 0).
- Les valeurs textuelles vides / non informatives deviennent None.
- Les colonnes Unnamed (artefacts Excel) sont supprimées.
"""

import logging
from typing import Optional

import pandas as pd

from .config import TableConfig

logger = logging.getLogger(__name__)

# Valeurs textuelles considérées comme vides
_EMPTY_TEXT = {"", "-", "—", "–", "*", "**", "N/A", "n/a", "NA", "#N/A", "?", "/"}


def clean(df: pd.DataFrame, cfg: TableConfig) -> pd.DataFrame:
    df = df.copy()

    # 1. Supprimer les colonnes explicitement listées
    _drop_named(df, cfg.drop_cols)

    # 2. Supprimer les colonnes Unnamed (artefacts de fusion Excel)
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if unnamed:
        df = df.drop(columns=unnamed)
        logger.debug("  Colonnes Unnamed supprimées : %s", unnamed)

    # 3. Nettoyer les noms de colonnes (espaces en trop)
    df.columns = [str(c).strip() for c in df.columns]

    # 4. Supprimer les lignes entièrement vides
    before = len(df)
    df = df.dropna(how="all")
    if len(df) < before:
        logger.debug("  %d lignes vides supprimées", before - len(df))

    # 5. Nettoyer les valeurs textuelles
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(_clean_text)

    # 6. Convertir les colonnes de dates
    for col in cfg.date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=True)
        else:
            logger.warning("  Colonne date absente : '%s'", col)

    # 7. Convertir les colonnes numériques
    for col in cfg.numeric_cols:
        if col in df.columns:
            df[col] = _to_numeric(df[col])
        else:
            logger.warning("  Colonne numérique absente : '%s'", col)

    return df


def _drop_named(df: pd.DataFrame, cols: list[str]) -> None:
    existing = [c for c in cols if c in df.columns]
    if existing:
        df.drop(columns=existing, inplace=True)


def _clean_text(value) -> Optional[str]:
    if pd.isna(value) or value is None:
        return None
    s = str(value).strip()
    return None if s in _EMPTY_TEXT else s


def _to_numeric(series: pd.Series) -> pd.Series:
    # Remplace virgule décimale par point, supprime espaces
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(" ", "", regex=False)   # espace insécable fine
        .str.replace("\xa0", "", regex=False)      # espace insécable
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")
