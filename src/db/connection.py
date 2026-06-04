"""
Gestionnaire de connexion DuckDB.

DuckDB lit directement les fichiers Parquet — pas de copie mémoire.
La base mining.duckdb persistante stocke les vues et métadonnées.

Usage :
    from src.db.connection import get_db
    con = get_db()
    df = con.execute("SELECT * FROM descente_minerai LIMIT 10").df()
"""

import logging
import threading
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parents[2]
DB_PATH = _PROJECT_ROOT / "data" / "mining.duckdb"
PARQUET_DIR = _PROJECT_ROOT / "data" / "parquet"

# Connexion par thread : chaque thread (Streamlit worker, script de test…)
# obtient sa propre connexion DuckDB in-memory pour éviter les courses.
_thread_local = threading.local()


def get_db() -> duckdb.DuckDBPyConnection:
    """Retourne la connexion DuckDB du thread courant, en la créant si nécessaire."""
    if not hasattr(_thread_local, "connection") or _thread_local.connection is None:
        _thread_local.connection = _init_db()
    return _thread_local.connection


def _init_db() -> duckdb.DuckDBPyConnection:
    # Connexion en mémoire : DuckDB lit les Parquet directement via des VIEWs.
    # Avantage : pas de fichier .duckdb verrouillé → plusieurs processus peuvent
    # se connecter simultanément (Streamlit + scripts de test).
    con = duckdb.connect(":memory:")
    _register_parquet_tables(con)
    _create_dim_date(con)
    # Construire le registre de schémas (colonnes, rôles, raisons NULL)
    try:
        from src.engine.schema_registry import build_registry
        build_registry(con)
    except Exception as exc:
        logger.warning("schema_registry non disponible : %s", exc)
    return con


def _register_parquet_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Crée une vue DuckDB pour chaque fichier Parquet disponible."""
    parquet_files = sorted(PARQUET_DIR.glob("*.parquet"))
    if not parquet_files:
        logger.warning(
            "Aucun fichier Parquet dans %s. "
            "Lancez d'abord : python -m src.ingest.pipeline",
            PARQUET_DIR,
        )
        return

    for path in parquet_files:
        table_name = path.stem
        # read_parquet() est une fonction de table — DuckDB n'accepte pas de
        # paramètre ? pour son argument. Le chemin vient de notre propre répertoire
        # PARQUET_DIR (pas d'une entrée utilisateur), donc le string formatting est sûr.
        # On échappe les apostrophes par précaution défensive.
        path_sql = path.as_posix().replace("'", "''")
        con.execute(
            f'CREATE OR REPLACE VIEW "{table_name}" AS '
            f"SELECT * FROM read_parquet('{path_sql}')"
        )
        logger.debug("Vue créée : %s", table_name)

    logger.info("%d tables disponibles dans DuckDB.", len(parquet_files))


def _create_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    """
    Vue calendrier générative — couvre toutes les dates des données.

    Colonnes clés :
        date_key    DATE        — clé de jointure pour les autres tables
        annee       INT
        mois        INT         — 1–12
        nom_mois    VARCHAR     — 'Janvier', 'Février', …
        trimestre   INT         — 1–4
        semestre    INT         — 1–2
        semaine_iso INT         — numéro ISO de semaine
        semaine_mois INT        — semaine au sein du mois (1–5)
        jour_semaine INT        — ISO : 1=lundi … 6=samedi … 7=dimanche
        est_weekend BOOLEAN     — True si samedi (6) ou dimanche (7)
    """
    con.execute("""
        CREATE OR REPLACE VIEW dim_date AS
        WITH dates AS (
            SELECT UNNEST(generate_series(
                DATE '2023-01-01',
                DATE '2030-12-31',
                INTERVAL '1 day'
            ))::DATE AS date_key
        )
        SELECT
            date_key,
            YEAR(date_key)                                  AS annee,
            MONTH(date_key)                                 AS mois,
            CASE MONTH(date_key)
                WHEN 1  THEN 'Janvier'   WHEN 2  THEN 'Février'
                WHEN 3  THEN 'Mars'      WHEN 4  THEN 'Avril'
                WHEN 5  THEN 'Mai'       WHEN 6  THEN 'Juin'
                WHEN 7  THEN 'Juillet'   WHEN 8  THEN 'Août'
                WHEN 9  THEN 'Septembre' WHEN 10 THEN 'Octobre'
                WHEN 11 THEN 'Novembre'  WHEN 12 THEN 'Décembre'
            END                                             AS nom_mois,
            QUARTER(date_key)                               AS trimestre,
            CASE WHEN MONTH(date_key) <= 6 THEN 1 ELSE 2 END AS semestre,
            WEEK(date_key)                                  AS semaine_iso,
            CEIL(DAY(date_key) / 7.0)::INT                 AS semaine_mois,
            isodow(date_key)                          AS jour_semaine,
            isodow(date_key) IN (6, 7)               AS est_weekend,
            STRFTIME(date_key, '%Y-%m')                     AS mois_cle
        FROM dates
    """)
    logger.debug("Vue dim_date créée (2023-2030).")


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Retourne la liste des tables/vues enregistrées."""
    rows = con.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]


def table_info(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    """Retourne les métadonnées d'une table (colonnes, types, nb lignes)."""
    cols = con.execute(f"DESCRIBE {table}").fetchdf()
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {
        "table": table,
        "rows": count,
        "columns": cols[["column_name", "column_type"]].to_dict("records"),
    }


def close() -> None:
    """Ferme la connexion DuckDB du thread courant."""
    conn = getattr(_thread_local, "connection", None)
    if conn is not None:
        conn.close()
        _thread_local.connection = None
    # Invalider le registre de schémas pour forcer une reconstruction
    try:
        from src.engine.schema_registry import invalidate
        invalidate()
    except Exception:
        pass
