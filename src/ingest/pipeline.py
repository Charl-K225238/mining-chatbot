"""
Pipeline ETL : Excel → nettoyage → Parquet.

Usage direct :
    python -m src.ingest.pipeline
"""

import logging
import sys
from pathlib import Path

import pandas as pd

from .cleaner import clean
from .config import TABLES
from .loader import load_table

logger = logging.getLogger(__name__)

PARQUET_DIR = Path(__file__).parents[2] / "data" / "parquet"


def run(tables: dict | None = None) -> dict[str, pd.DataFrame]:
    """
    Traite toutes les tables (ou un sous-ensemble) et écrit les fichiers Parquet.

    Args:
        tables: dictionnaire TableConfig à traiter ; utilise TABLES par défaut.

    Returns:
        Dictionnaire {nom_table: DataFrame nettoyé}.
    """
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    target = tables if tables is not None else TABLES
    if not target:
        logger.warning("Aucune table à traiter (dictionnaire vide).")
        return {}
    results: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    for name, cfg in target.items():
        try:
            logger.info("[>>] %s  (%s / %s)", name, cfg.file, cfg.sheet)
            df = load_table(name, cfg)
            df = clean(df, cfg)
            out = PARQUET_DIR / f"{name}.parquet"
            df.to_parquet(out, index=False, engine="pyarrow")
            results[name] = df
            logger.info("   [OK] %d lignes x %d colonnes", len(df), len(df.columns))
        except Exception as exc:
            logger.error("   [ERREUR] : %s", exc)
            errors.append(f"{name}: {exc}")

    logger.info("\nTerminé — %d/%d tables traitées.", len(results), len(target))
    if errors:
        logger.warning("%d erreur(s) :", len(errors))
        for e in errors:
            logger.warning("  %s", e)

    return results


def _print_summary(results: dict[str, pd.DataFrame]) -> None:
    width = max(len(n) for n in results) + 2 if results else 20
    print(f"\n{'Table':<{width}} {'Lignes':>8}  {'Colonnes':>8}")
    print("─" * (width + 20))
    for name, df in results.items():
        print(f"{name:<{width}} {len(df):>8,}  {len(df.columns):>8}")
    print(f"\n{len(results)} tables exportées dans data/parquet/")


if __name__ == "__main__":
    # Force UTF-8 pour affichage correct sous Windows (cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s  %(message)s",
        stream=sys.stdout,
    )
    tables = run()
    _print_summary(tables)
