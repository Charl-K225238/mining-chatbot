"""
src/engine/schema_registry.py — Registre de schémas dynamique pour Miny.

Construit au démarrage depuis les tables DuckDB réelles.
Fournit pour chaque table :
  - Colonnes et types réels (depuis DESCRIBE)
  - Détection sémantique de rôles (date, quantité, équipement, heures…)
  - Raisons métier des valeurs NULL (ex: Equipement vide = précisez l'engin)
  - Périodes de données disponibles (années)
  - Messages de guidance contextuels quand aucune donnée n'est trouvée

Principe NULL métier :
  Pour certaines colonnes, une valeur NULL n'est pas une erreur mais signifie
  soit une raison technique connue (ex: champ non renseigné pour la période),
  soit une invitation à préciser (ex: "Equipement NULL = données agrégées,
  précisez TRS 296 ou TRS 1347 pour filtrer").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Patterns de rôles sémantiques
# Chaque rôle → liste de sous-chaînes (minuscules) à rechercher dans le nom de colonne.
# L'ordre dans la liste = priorité (plus spécifique en premier).
# ─────────────────────────────────────────────────────────────────────────────
_ROLE_PATTERNS: dict[str, list[str]] = {
    "date":        ["date", "jour", "period"],
    "equipment":   ["equipement", "engin", "machine", "immatriculation", "code engin"],
    "quantity":    ["quantite", "tonnage", "tonne", "volume", "poids", "chargee"],
    "hours":       ["heure moteur", "heure tambour", "heure", "hour", "duree"],
    "shift":       ["shift", "vacation", "poste", "equipe"],
    "status":      ["statut", "status", "etat", "avancement"],
    "responsible": ["responsable", "agent", "operateur", "chef"],
    "observation": ["observation", "commentaire", "description", "note", "remarque"],
    "category":    ["categorie", "type", "nature", "classe", "domaine"],
    "fuel_qty":    ["litre", "servi", "consomm", "depotage"],
    "priority":    ["priorite", "priority", "urgence"],
    "deadline":    ["deadline", "echeance", "fin", "realisation"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Raisons métier des valeurs NULL — {table: {col_name: NullReason}}
# "user_can_specify": True → le système propose à l'utilisateur de préciser
# "message": texte explicatif affiché si NULL détecté
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class NullReason:
    message: str
    user_can_specify: bool = False
    hint: str = ""          # suggestion de reformulation pour l'utilisateur


_NULL_BUSINESS_REASONS: dict[str, dict[str, NullReason]] = {
    "shifts_horaires": {
        "Equipement": NullReason(
            message=(
                "Non renseigné pour 2024–2025 : les heures sont agrégées sur tous les engins. "
                "En 2026, deux trenchers sont identifiés : TRS N°296 et TRS N°1347."
            ),
            user_can_specify=True,
            hint="Précisez l'engin : *Heures machine TRS 296 en 2026* ou *Heures machine TRS 1347 en 2026*",
        ),
    },
    "descente_minerai": {
        "OBSERVATION": NullReason(
            message="Absent quand la journée se déroule sans incident — valeur vide = journée normale.",
        ),
        "QUALITE": NullReason(
            message="Non systématiquement renseigné : vide = qualité standard.",
        ),
    },
    "transport_minerai_paa": {
        "DATE ARRIVEE PAA": NullReason(
            message="Vide si le transport est en cours de livraison au port.",
        ),
    },
    "pges_actions": {
        "Responsable": NullReason(
            message="Certaines actions n'ont pas encore de responsable désigné.",
            user_can_specify=True,
            hint="Précisez le responsable : *Actions de responsable LEB*",
        ),
        "Sous actions": NullReason(
            message="Vide si l'action n'a pas été décomposée en sous-actions.",
        ),
    },
    "suivi_actions": {
        "% Avancement": NullReason(
            message="Vide pour les actions non encore démarrées (statut Non réalisé).",
        ),
        "Deadline": NullReason(
            message="Vide si aucune échéance n'a été fixée.",
            user_can_specify=True,
            hint="Pour les actions avec deadline, essayez : *Obligations HSE avec deadline*",
        ),
    },
    "journal": {
        "Commentaire": NullReason(
            message="Non renseigné pour toutes les entrées du journal.",
        ),
    },
    "carburant_citerne": {
        "Depotage": NullReason(
            message="Vide pour les lignes de consommation (pas d'approvisionnement ce jour).",
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Descriptions des tables (pour les messages d'aide)
# ─────────────────────────────────────────────────────────────────────────────
_TABLE_DESCRIPTIONS: dict[str, str] = {
    "descente_minerai":       "Tonnage journalier descendu (tombereaux)",
    "excavation":             "Tonnage excavé par jour",
    "shifts_horaires":        "Heures moteur / machine par shift (trencher)",
    "shifts_personnel":       "Présence et shifts du personnel",
    "journal":                "Journal d'activité et pannes trencher",
    "carburant_citerne":      "Consommation et approvisionnement carburant (Petro Ivoire / Iveqi)",
    "carburant_activites":    "Activités engins liées au carburant",
    "transport_minerai_paa":  "Transport mine → Port Autonome d'Abidjan",
    "productivite_loading":   "Chargement des navires",
    "productivite_navires":   "Voyages navires",
    "suivi_actions":          "Obligations HSE et suivi d'avancement",
    "pges_actions":           "Actions du Plan de Gestion Environnementale et Sociale (PGES)",
    "objectifs":              "Objectifs de production prévu vs réalisé",
    "qualite_echantillons":   "Analyses qualité des échantillons de bauxite",
    "qualite_navires":        "Qualité lors des chargements navires",
    "regul_qte_stock":        "Régulations de la quantité de stock",
    "regul_qualite_stock":    "Régulations de la qualité de stock",
    "engins":                 "Référentiel des engins (liste de tous les équipements)",
    "chargeuses":             "Référentiel des chargeuses",
    "personnel":              "Référentiel du personnel",
    "budget":                 "Budget de production",
    "stocks_ref":             "Référentiel des zones de stockage",
    "valeurs_initiales":      "Valeurs initiales de référence",
    "zones_excavation":       "Référentiel des zones d'excavation",
}

# ─────────────────────────────────────────────────────────────────────────────
# Tables sans colonne date (référentiels) — pas de filtrage temporel attendu
# ─────────────────────────────────────────────────────────────────────────────
_REFERENCE_TABLES = {
    "engins", "chargeuses", "personnel", "budget",
    "stocks_ref", "valeurs_initiales", "zones_excavation",
    "pges_actions", "suivi_actions",
}


# ─────────────────────────────────────────────────────────────────────────────
# TableSchema
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TableSchema:
    """
    Profil d'une table : colonnes, types, rôles sémantiques, raisons NULL.
    """
    name:     str
    col_info: dict[str, str]              # {col_name: col_type}
    _roles:   dict[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._roles = {}
        self._detect_roles()

    def _detect_roles(self) -> None:
        for role, patterns in _ROLE_PATTERNS.items():
            for c in self.col_info:
                cl = c.lower()
                # "date" : ne pas confondre avec colonnes d'heures (TIMESTAMP mais durée)
                if role == "date" and any(x in cl for x in ("heure", "hour")):
                    continue
                if any(p in cl for p in patterns):
                    self._roles.setdefault(role, c)

    # ── Accès rôles ──────────────────────────────────────────────────────────

    def col(self, role: str) -> str | None:
        """Nom de colonne pour un rôle sémantique (None si non trouvé)."""
        return self._roles.get(role)

    def has_role(self, role: str) -> bool:
        return self._roles.get(role) is not None

    def col_type(self, col_name: str) -> str:
        return self.col_info.get(col_name, "UNKNOWN")

    # ── Filtres par type ──────────────────────────────────────────────────────

    def numeric_cols(self) -> list[str]:
        return [
            c for c, t in self.col_info.items()
            if any(tp in t.upper() for tp in ("DOUBLE", "FLOAT", "INTEGER",
                                               "DECIMAL", "BIGINT", "HUGEINT"))
        ]

    def timestamp_cols(self) -> list[str]:
        return [c for c, t in self.col_info.items() if "TIMESTAMP" in t.upper()]

    def varchar_cols(self) -> list[str]:
        return [c for c, t in self.col_info.items() if "VARCHAR" in t.upper()]

    # ── Annotations métier ────────────────────────────────────────────────────

    def null_reason(self, col_name: str) -> NullReason | None:
        return _NULL_BUSINESS_REASONS.get(self.name, {}).get(col_name)

    def description(self) -> str:
        return _TABLE_DESCRIPTIONS.get(self.name, self.name)

    def is_reference(self) -> bool:
        return self.name in _REFERENCE_TABLES


# ─────────────────────────────────────────────────────────────────────────────
# Registre global + fonctions publiques
# ─────────────────────────────────────────────────────────────────────────────
_registry: dict[str, TableSchema]   = {}
_years_cache: dict[str, list[int]]  = {}


def build_registry(con: duckdb.DuckDBPyConnection) -> None:
    """
    Construit le registre pour toutes les tables disponibles dans DuckDB.
    À appeler une fois après _register_parquet_tables().
    """
    global _registry, _years_cache
    _registry    = {}
    _years_cache = {}
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return
    for table in tables:
        try:
            rows     = con.execute(f"DESCRIBE {table}").fetchall()
            col_info = {r[0]: r[1] for r in rows}
            _registry[table] = TableSchema(name=table, col_info=col_info)
        except Exception as exc:
            logger.debug("schema_registry: skipped %s (%s)", table, exc)
    logger.info("schema_registry: %d tables enregistrées.", len(_registry))


def get_schema(table: str) -> TableSchema | None:
    return _registry.get(table)


def get_or_build(con: duckdb.DuckDBPyConnection, table: str) -> TableSchema | None:
    """Retourne ou construit à la demande le schéma d'une table."""
    if table not in _registry:
        try:
            rows     = con.execute(f"DESCRIBE {table}").fetchall()
            col_info = {r[0]: r[1] for r in rows}
            _registry[table] = TableSchema(name=table, col_info=col_info)
        except Exception:
            return None
    return _registry.get(table)


def available_years(con: duckdb.DuckDBPyConnection, table: str) -> list[int]:
    """Retourne les années disponibles dans une table timeseries (avec cache)."""
    if table in _years_cache:
        return _years_cache[table]
    schema = get_or_build(con, table)
    if not schema or schema.is_reference():
        return []
    date_col = schema.col("date")
    if not date_col:
        return []
    try:
        rows  = con.execute(
            f'SELECT DISTINCT YEAR("{date_col}") AS yr '
            f'FROM {table} WHERE "{date_col}" IS NOT NULL ORDER BY 1'
        ).fetchall()
        years = [int(r[0]) for r in rows if r[0] is not None]
        _years_cache[table] = years
        return years
    except Exception:
        return []


def invalidate() -> None:
    """Remet à zéro le registre et le cache (après rechargement de données)."""
    global _registry, _years_cache
    _registry    = {}
    _years_cache = {}


# ─────────────────────────────────────────────────────────────────────────────
# Génération de messages de guidance contextuels
# ─────────────────────────────────────────────────────────────────────────────

def smart_no_data(
    table: str,
    label: str,
    year: int | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
    extra_hint: str | None = None,
) -> str:
    """
    Génère un message d'aide contextuel quand aucune donnée n'est trouvée.

    - Si l'année demandée n'est pas couverte → liste les années disponibles.
    - Si la table a une description → l'inclut pour orienter l'utilisateur.
    - extra_hint : conseil spécifique au handler (ex: "précisez l'engin").
    """
    schema = get_schema(table)
    desc   = schema.description() if schema else table

    lines: list[str] = []

    if year and con is not None:
        years = available_years(con, table)
        if years and year not in years:
            yrs_str = ", ".join(map(str, years))
            lines.append(
                f"Aucune donnée pour **{year}** dans *{desc}*.\n"
                f"Années disponibles : **{yrs_str}**."
            )
            if extra_hint:
                lines.append(f"\n_{extra_hint}_")
            return "\n".join(lines)

    lines.append(f"Aucune donnée correspondante dans *{desc}* ({label}).")
    if extra_hint:
        lines.append(f"\n_{extra_hint}_")
    return "\n".join(lines)


def null_context(table: str, col_name: str) -> str | None:
    """
    Retourne le message contextuel pour une valeur NULL connue, ou None.
    Utilisé par les handlers pour expliquer pourquoi une valeur est vide
    plutôt que de retourner une erreur cryptique.
    """
    schema = get_schema(table)
    if not schema:
        return None
    nr = schema.null_reason(col_name)
    if not nr:
        return None
    msg = f"_{nr.message}_"
    if nr.user_can_specify and nr.hint:
        msg += f"\n💡 {nr.hint}"
    return msg


def col_for_role(table: str, role: str) -> str | None:
    """Retourne le nom de la colonne pour un rôle sémantique dans une table."""
    schema = get_schema(table)
    return schema.col(role) if schema else None


def list_tables_with_context(con: duckdb.DuckDBPyConnection) -> str:
    """
    Résumé textuel de toutes les tables avec description et période couverte.
    Utilisé dans les messages d'aide quand l'utilisateur ne sait pas quoi demander.
    """
    lines: list[str] = []
    for tname in sorted(_registry):
        schema = _registry[tname]
        desc   = schema.description()
        yr     = available_years(con, tname)
        yr_s   = f" ({min(yr)}–{max(yr)})" if yr else ""
        lines.append(f"  • `{tname}` : {desc}{yr_s}")
    return "\n".join(lines) if lines else "Aucune table disponible."
