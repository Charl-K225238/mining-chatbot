"""Lecture des fichiers Excel bruts vers des DataFrames pandas."""

import logging
from pathlib import Path

import pandas as pd

from .config import TableConfig

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[2] / "data" / "raw"


def load_table(name: str, cfg: TableConfig) -> pd.DataFrame:
    """Lit une feuille Excel et retourne un DataFrame brut (non nettoyé)."""
    path = RAW_DIR / cfg.file
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    df = pd.read_excel(
        path,
        sheet_name=cfg.sheet,
        header=cfg.header_row,
        engine="openpyxl",
    )

    logger.debug("  %s chargé — %d lignes, %d colonnes", name, len(df), len(df.columns))
    return df
