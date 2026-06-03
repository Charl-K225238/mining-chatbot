"""
Chargement et cache des ressources partagées (DuckDB, BM25).

Centralise les @st.cache_resource pour éviter une connexion par page.
Toutes les pages importent depuis ce module.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st

from src.db.connection import get_db as _get_db, list_tables
from src.rag.index import get_index as _get_index
from src.engine import analytics as _analytics

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner="Connexion à la base de données…")
def get_db():
    """Connexion DuckDB singleton (partagée entre toutes les pages)."""
    return _get_db()


@st.cache_resource(show_spinner="Chargement de l'index de recherche…")
def get_index():
    """Index BM25 singleton."""
    return _get_index(get_db())


def load_css() -> None:
    """Injecte le CSS centralisé dans la page courante."""
    css_path = ROOT / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>",
                    unsafe_allow_html=True)


def max_date(con, table: str) -> str | None:
    """Retourne la date max de la première colonne DATE/TIMESTAMP d'une table."""
    try:
        cols = con.execute(f"DESCRIBE {table}").fetchdf()
        for _, row in cols.iterrows():
            if row["column_type"] in ("DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE"):
                col = row["column_name"]
                r = con.execute(f'SELECT MAX("{col}") FROM {table}').fetchone()[0]
                if r is None:
                    return None
                return r.strftime("%d/%m/%Y") if hasattr(r, "strftime") else str(r)[:10]
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def sidebar_stats() -> dict:
    """
    Statistiques sidebar — mises en cache 5 min.
    Retourne : years, tables [(name, nb, last_date)], freshness {name: date}, error.
    """
    try:
        con = get_db()
        years = [
            r[0] for r in con.execute(
                f'SELECT DISTINCT YEAR("{_analytics.COL["date"]}") '
                f"FROM {_analytics.TABLE} ORDER BY 1"
            ).fetchall()
        ]
        tables = [t for t in list_tables(con) if not t.startswith("dim_")]
        table_stats: list[tuple] = []
        for t in tables:
            try:
                nb   = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                last = max_date(con, t)
                table_stats.append((t, nb, last))
            except Exception:
                pass
        freshness = {t: d for t, _, d in table_stats if d}
        return {
            "years":     years,
            "tables":    table_stats,
            "freshness": freshness,
            "error":     None,
        }
    except Exception as exc:
        logger.warning("sidebar_stats error: %s", exc)
        return {"years": [], "tables": [], "freshness": {}, "error": str(exc)}


def kpi_actions(con) -> dict:
    """
    Calcule les 4 KPIs pour la page Données.
    Retourne : total_pges, non_realise, en_cours, taux_prod (%).
    """
    result = {"total_pges": "—", "non_realise": "—", "en_cours": "—", "taux_prod": "—"}
    try:
        result["total_pges"] = con.execute("SELECT COUNT(*) FROM pges_actions").fetchone()[0]
    except Exception:
        pass
    try:
        result["non_realise"] = con.execute(
            """SELECT COUNT(*) FROM suivi_actions
               WHERE lower(COALESCE(Statuts::VARCHAR, '')) LIKE '%non%'"""
        ).fetchone()[0]
    except Exception:
        pass
    try:
        result["en_cours"] = con.execute(
            """SELECT COUNT(*) FROM suivi_actions
               WHERE lower(COALESCE(Statuts::VARCHAR, '')) LIKE '%cours%'"""
        ).fetchone()[0]
    except Exception:
        pass
    try:
        # Taux de production : dernière année disponible, descente vs objectif
        last_year = con.execute(
            f'SELECT MAX(YEAR("{_analytics.COL["date"]}")) FROM {_analytics.TABLE}'
        ).fetchone()[0]
        if last_year:
            realise = con.execute(
                f'SELECT COALESCE(SUM("{_analytics.COL["qty"]}"), 0) FROM {_analytics.TABLE} '
                f'WHERE YEAR("{_analytics.COL["date"]}") = {last_year}'
            ).fetchone()[0]
            prevu = con.execute(
                f'SELECT COALESCE(SUM("{_analytics.OBJ_DESCENTE}"), 0) FROM {_analytics.OBJ_TABLE} '
                f'WHERE YEAR("{_analytics.OBJ_DATE}") = {last_year}'
            ).fetchone()[0]
            if prevu and float(prevu) > 0:
                result["taux_prod"] = f"{float(realise) / float(prevu) * 100:.1f} %"
    except Exception:
        pass
    return result
