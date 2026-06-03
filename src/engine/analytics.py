"""
Moteur analytique principal — descente_minerai (table BI centrale).

Corrections vs test_agent.py :
  - Aucun filtre année par défaut (on interroge toutes les années si non précisée)
  - Tombereaux = engins dont le nom contient un numéro (ex: "TOMBEREAU CAT N°5")
  - Questions multi-parties traitées ensemble
  - Correspondance de mots-clés robuste (société de transport, qualité, etc.)
  - Pannes / observations : compte sur toutes les années par défaut
  - Ventilation hebdomadaire au sein d'un mois (S1–S4/S5)
"""

import logging
import re
from datetime import datetime

import duckdb
import pandas as pd

from src.utils.text import norm as _norm
from src.engine.intention import normaliser as _normaliser
from src.engine import schema_registry as _reg

TABLE = "descente_minerai"

# ── Colonnes table objectifs ────────────────────────────────────────────────
OBJ_TABLE    = "objectifs"
OBJ_DATE     = "Date"
OBJ_DESCENTE = "Descente Prévue (T)"
OBJ_EXCAV    = "Excavation Prévue (T)"

# ── Colonnes table excavation ───────────────────────────────────────────────
EXC_TABLE = "excavation"
EXC_DATE  = "Date"
EXC_QTY   = "Tonnage excavé estimé (T)"

# ── Colonnes table transport_minerai_paa ─────────────────────────────────────
TRANS_TABLE     = "transport_minerai_paa"
TRANS_DATE_MINE = "DATE DEPART"
TRANS_DATE_PORT = "DATE ARRIVEE PAA"
TRANS_QTY_MINE  = "QUANTITE TRANSPORTEE (Kg)"   # mesuré à la mine (en Kg → ÷1000 pour T)
TRANS_QTY_PORT  = "QUANTITE TRANSPORTEE PAA (Kg)"  # mesuré au port logistique (en Kg → ÷1000)

# ── Colonnes table productivite_loading (navires) ────────────────────────────
LOAD_TABLE    = "productivite_loading"
LOAD_DATE     = "DATE"
LOAD_QTY      = "QUANTITE CHARGEE"   # en T

# ── Colonnes table carburant_citerne (Petro Ivoire) ──────────────────────────
CARB_TABLE = "carburant_citerne"
CARB_DATE  = "Date"
CARB_QTY   = "Quantité Servie (L)"      # litres servis aux engins
CARB_DEPOT = "Depotage"                  # approvisionnement citerne
CARB_ENGIN = "Engin/Equipement"

# ── Message de désambiguïsation ──────────────────────────────────────────────
_TONNAGE_TYPES_NOTE = (
    "\n_ℹ️ Tonnage **descendu** par défaut. "
    "Précisez si besoin : **excavé**, **transporté** (mine→port), "
    "**arrivé port**, **navire**._"
)

# ── Correspondances colonnes descente_minerai ────────────────────────────────
COL = {
    "date":   "DATE",
    "qty":    "QUANTITE JOURNALIERE DESCENDUE (T)",
    "engin":  "Code / Nom engin / Immatriculation",
    "site":   "Site",
    "resp":   "Responsable site",
    "prod":   "Produit",
    "trans":  "SOCIETE DE TRANSPORT",
    "voy":    "NOMBRE VOYAGE",
    "tv":     "TONNAGE / VOYAGE",
    "qual":   "QUALITE",
    "zone":   "ZONE DE STOCKAGE",
    "obs":    "OBSERVATION",
    "camion": "N°CAMION",
}

MOIS_FR: dict[str, int] = {
    "janvier": 1,  "jan": 1,
    "fevrier": 2,  "février": 2, "fev": 2,
    "mars": 3,
    "avril": 4,    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,  "juil": 7,
    "aout": 8,     "août": 8,
    "septembre": 9, "sep": 9, "sept": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "décembre": 12, "dec": 12,
}

MOIS_NUM_FR: dict[int, str] = {
    1: "Janvier", 2: "Février",   3: "Mars",      4: "Avril",
    5: "Mai",     6: "Juin",      7: "Juillet",   8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

# _norm imported from src.utils.text


ABBREV = [
    # Plage de semaines ISO (ex: S1-S6) — doit précéder les règles semestre
    (r"\bS([12])\b(?=\s*-\s*S)", r"semaine \1"),   # S1-S6 → semaine 1  (range)
    # Semestres S1/S2 standalone
    (r"\bS1\b", "semestre 1"), (r"\bS2\b", "semestre 2"),
    # Trimestres
    (r"\bT1\b", "trimestre 1"), (r"\bT2\b", "trimestre 2"),
    (r"\bT3\b", "trimestre 3"), (r"\bT4\b", "trimestre 4"),
    (r"\bQ1\b", "trimestre 1"), (r"\bQ2\b", "trimestre 2"),
    (r"\bQ3\b", "trimestre 3"), (r"\bQ4\b", "trimestre 4"),
    # Semaines ISO : S3-S9 (1 chiffre), S10-S53 (2 chiffres)
    (r"\bS([3-9])\b", r"semaine \1"),
    (r"\bS(\d{2})\b", r"semaine \1"),
    (r"\bSem\.?\s*(\d{1,2})\b", r"semaine \1"),
    (r"\bcette\s+ann[ée]e\b", str(datetime.now().year)),
    (r"\bl.ann[ée]e\s+derni[eè]re\b", str(datetime.now().year - 1)),
    (r"\bzone\s+(\d+)\b", r"stock \1"),
    (r"\btns?\b", "tonnage"),
]

def preprocess(q: str) -> str:
    for pat, repl in ABBREV:
        q = re.sub(pat, repl, q, flags=re.IGNORECASE)
    return q

# ── Extraction temporelle ───────────────────────────────────────────────────

def _year(ql: str) -> int | None:
    """Retourne l'année mentionnée, ou None (pas de valeur par défaut)."""
    m = re.search(r"\b(20\d{2})\b", ql)
    return int(m.group(1)) if m else None

def _months(ql: str) -> list[int]:
    found: list[int] = []
    for nom, num in MOIS_FR.items():
        if re.search(rf"\b{re.escape(_norm(nom))}\b", _norm(ql)):
            if num not in found:
                found.append(num)
    return found

_ORD = r"(?:er|[eè]re?|[eè]me?)?"   # suffixe ordinal : 1er, 2ème, 3e…

def _quarter(ql: str) -> int | None:
    m = re.search(r"trimestre\s+(\d)", ql, re.I)
    if m: return int(m.group(1))
    m = re.search(rf"\b(\d){_ORD}\s+trimestre", ql, re.I)
    return int(m.group(1)) if m else None

def _semester(ql: str) -> int | None:
    m = re.search(r"semestre\s+(\d)", ql, re.I)
    if m: return int(m.group(1))
    m = re.search(rf"\b(\d){_ORD}\s+semestre", ql, re.I)
    return int(m.group(1)) if m else None

def _semesters(ql: str) -> list[int]:
    """Tous les semestres mentionnés, y compris '1er semestre', '2ème semestre'."""
    found  = [int(m) for m in re.findall(r"semestre\s+(\d)", ql, re.I)]
    found += [int(m) for m in re.findall(rf"\b(\d){_ORD}\s+semestre", ql, re.I)]
    return [s for s in list(dict.fromkeys(found)) if s in (1, 2)]

def _quarters(ql: str) -> list[int]:
    """Tous les trimestres mentionnés, y compris '3ème trimestre'."""
    found  = [int(m) for m in re.findall(r"trimestre\s+(\d)", ql, re.I)]
    found += [int(m) for m in re.findall(rf"\b(\d){_ORD}\s+trimestre", ql, re.I)]
    return [q for q in list(dict.fromkeys(found)) if 1 <= q <= 4]

def _iso_week_range(ql: str) -> tuple[int, int] | None:
    """Plage de semaines ISO après expansion ABBREV : 'semaine 1-semaine 6', 'semaine 1 à 8'."""
    m = re.search(
        r"semaine[s]?\s+(\d{1,2})\s*[-àa]\s*(?:semaine[s]?\s+)?(\d{1,2})",
        ql, re.I
    )
    return (int(m.group(1)), int(m.group(2))) if m else None


def _single_week(ql: str) -> int | None:
    """Numéro de semaine ISO unique : 'semaine 17', '1ère semaine', 'W3'."""
    if _iso_week_range(ql):
        return None  # évite collision avec les plages
    if re.search(r"derni[eè]re?\s+semaine", ql, re.I):
        return -1   # sentinelle : dernière semaine
    m = re.search(r"\bsemaine\s+(\d{1,2})\b", ql, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s*[eè][rèmième]*\s+semaine\b", ql, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b[Ww](\d{1,2})\b", ql, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _specific_date(ql: str) -> str | None:
    """Extrait DD/MM/YYYY ou DD-MM-YYYY → ISO YYYY-MM-DD, ou None."""
    m = re.search(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b', ql)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= day <= 31 and 1 <= month <= 12:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None

# ── Clauses SQL ─────────────────────────────────────────────────────────────
# Ces fonctions construisent des fragments SQL réutilisables par tous les handlers.

def _where(year: int | None = None, month: int | None = None,
           quarter: int | None = None, semester: int | None = None,
           iso_week: int | None = None) -> str:
    parts: list[str] = []
    if year:
        parts.append(f"YEAR({COL['date']}) = {year}")
    if month:
        parts.append(f"MONTH({COL['date']}) = {month}")
    if quarter:
        months = {1: [1,2,3], 2: [4,5,6], 3: [7,8,9], 4: [10,11,12]}[quarter]
        parts.append(f"MONTH({COL['date']}) IN ({','.join(map(str, months))})")
    if semester:
        months = {1: [1,2,3,4,5,6], 2: [7,8,9,10,11,12]}[semester]
        parts.append(f"MONTH({COL['date']}) IN ({','.join(map(str, months))})")
    if iso_week and iso_week > 0:
        parts.append(f"WEEK({COL['date']}) = {iso_week}")
    return ("WHERE " + " AND ".join(parts)) if parts else ""

def _label(year, month, quarter, semester, iso_week=None, iso_range=None) -> str:
    parts = []
    if year:
        parts.append(str(year))
    if month:
        parts.append(MOIS_NUM_FR.get(month, str(month)))
    if quarter:
        parts.append(f"T{quarter}")
    if semester:
        parts.append(f"S{semester}")
    if iso_range:
        parts.append(f"S{iso_range[0]}–S{iso_range[1]}")
    elif iso_week and iso_week > 0:
        parts.append(f"S{iso_week}")
    elif iso_week == -1:
        parts.append("dernière semaine")
    return " | ".join(parts) if parts else "toutes périodes"

# ── Formatters ──────────────────────────────────────────────────────────────

def _no_data(
    table: str,
    label: str,
    year: int | None = None,
    con: duckdb.DuckDBPyConnection | None = None,
    extra_hint: str | None = None,
) -> str:
    """
    Message contextuel quand aucune donnée n'est trouvée.
    Délègue au schema_registry pour suggérer les années disponibles
    et fournir une raison métier si connue.
    """
    return _reg.smart_no_data(table, label, year=year, con=con, extra_hint=extra_hint)


def _fmt_list(title: str, values: list) -> str:
    if not values:
        return f"{title} : aucune valeur."
    lines = "\n".join(f"  • {v}" for v in sorted(set(str(v) for v in values if v)))
    return f"{title} ({len(set(str(v) for v in values if v))}) :\n{lines}"

def _fmt_table(title: str, rows: list[tuple], headers: list[str]) -> str:
    if not rows:
        return f"{title} : aucun résultat."
    col_w = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
             for i, h in enumerate(headers)]
    sep = "  ".join("-" * w for w in col_w)
    head = "  ".join(str(h).ljust(w) for h, w in zip(headers, col_w))
    body = "\n".join(
        "  ".join(str(c).ljust(w) for c, w in zip(row, col_w)) for row in rows
    )
    return f"{title} :\n{head}\n{sep}\n{body}"

def _fmt_monthly(title: str, rows: list[tuple]) -> str:
    """Formate un tableau mois → valeur avec total."""
    if not rows:
        return f"{title} : aucune donnée."
    total = sum(r[1] for r in rows if r[1] is not None)
    lines = [f"  {MOIS_NUM_FR.get(r[0], r[0]):>12} : {r[1]:>14,.0f}" for r in rows]
    lines.append(f"  {'TOTAL':>12} : {total:>14,.0f}")
    return f"{title} :\n" + "\n".join(lines)


def _fmt_weekly(title: str, rows: list[tuple]) -> str:
    """Formate un tableau semaine ISO → valeur avec total (label : S{n})."""
    if not rows:
        return f"{title} : aucune donnée."
    total = sum(r[1] for r in rows if r[1] is not None)
    lines = [f"  S{r[0]:<2} : {r[1]:>14,.0f}" for r in rows]
    lines.append(f"  {'TOTAL':<5} : {total:>14,.0f}")
    return f"{title} :\n" + "\n".join(lines)

# ── Requêtes SQL ────────────────────────────────────────────────────────────

def _q(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()

def _scalar(con, sql: str):
    return con.execute(sql).fetchone()[0]

def _ext(w: str, *extra: str) -> str:
    """Ajoute des conditions AND à une clause WHERE existante (ou en crée une)."""
    cond = " AND ".join(c for c in extra if c)
    if not cond:
        return w
    return f"WHERE {cond}" if not w else f"{w} AND {cond}"

# ── Handlers ────────────────────────────────────────────────────────────────

def handle_tonnage(con, ql: str, year, months, quarter, semester,
                   iso_week: int | None = None,
                   iso_range: tuple[int, int] | None = None,
                   specific_date: str | None = None) -> str | None:
    kw_ton = any(w in ql for w in ["tonnage", "quantite", "tonne", "descendu", "descente", "produit", "production"])
    kw_voy = any(w in ql for w in ["voyage", "rotation", "trajet"])
    if not kw_ton and not kw_voy:
        return None
    # Exclure les conversions d'unités et autres contextes non-tonnage minier
    if any(w in ql for w in ["convertir", "conversion", "en gramme", "en kg", "en litre"]):
        return None

    wants_breakdown = any(w in ql for w in [
        "par mois", "mensuel", "mensuelle", "chaque mois", "mois par mois",
        "par semaine", "semaine", "chaque semaine",
        "par trimestre", "par semestre", "par zone", "par engin",
    ])
    wants_weekly_year = any(w in ql for w in ["par semaine", "semaine par semaine", "chaque semaine"])

    month = months[0] if len(months) == 1 else None

    def _weekly_sql(where_clause: str) -> pd.DataFrame:
        return _q(con, f"""
            SELECT WEEK({COL['date']}) as semaine,
                   MIN({COL['date']}) as date_debut,
                   SUM("{COL['qty']}") as tonnage,
                   SUM("{COL['voy']}") as voyages
            FROM {TABLE} {where_clause}
            GROUP BY 1 ORDER BY 1
        """)

    # -1. Date précise (ex: "le 03/02/2026")
    if specific_date:
        _d = f"{specific_date[8:10]}/{specific_date[5:7]}/{specific_date[:4]}"
        w = f'WHERE "{COL["date"]}" = DATE \'{specific_date}\''
        parts = []
        if kw_ton:
            val = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {w}') or 0
            if val == 0:
                cnt = _scalar(con, f'SELECT COUNT(*) FROM {TABLE} {w}') or 0
                if cnt == 0:
                    return f"Aucune donnée pour le {_d}."
            parts.append(f"Tonnage **descendu** le {_d} : {val:,.0f} T")
        if kw_voy:
            val = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {w}') or 0
            parts.append(f"Voyages le {_d} : {val:,.0f}")
        return "\n".join(parts) if parts else None

    # 0. Plage de semaines ISO (ex: S1-S6 2026) — affiche toutes les semaines, 0 si vide
    if iso_range and year:
        w1, w2 = iso_range
        where = f"WHERE YEAR({COL['date']}) = {year} AND WEEK({COL['date']}) BETWEEN {w1} AND {w2}"
        df = _weekly_sql(where)
        lbl = f"S{w1}–S{w2} {year}"
        if df.empty:
            return _no_data(TABLE, lbl, year=year, con=con)
        week_data = {int(r.semaine): (r.tonnage or 0, r.voyages or 0) for _, r in df.iterrows()}
        parts = []
        if kw_ton:
            rows = [(wk, week_data.get(wk, (0, 0))[0]) for wk in range(w1, w2 + 1)]
            parts.append(_fmt_weekly(f"Tonnage {lbl}", rows))
        if kw_voy:
            rows = [(wk, week_data.get(wk, (0, 0))[1]) for wk in range(w1, w2 + 1)]
            parts.append(_fmt_weekly(f"Voyages {lbl}", rows))
        return "\n\n".join(parts)

    # 0b. Multi-semestres (ex: "S1 et S2 2025") ou "par semestre en 2025"
    semesters_req = _semesters(ql)
    if not semesters_req and re.search(r"par semestre|chaque semestre", ql, re.I) and not semester:
        semesters_req = [1, 2]
    if len(semesters_req) >= 2 and year:
        _SEM_LABEL = {1: "Jan–Juin", 2: "Juil–Déc"}
        lines = [f"Tonnage par semestre ({year}) :"]
        total = 0
        for s in sorted(set(semesters_req)):
            v = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {_where(year=year, semester=s)}') or 0
            lines.append(f"  S{s} ({_SEM_LABEL[s]}) : {v:>14,.0f} T")
            total += v
        lines.append(f"  {'TOTAL':<14} : {total:>14,.0f} T")
        return "\n".join(lines)

    # 0c. Ventilation par trimestre (ex: "par trimestre en 2025")
    quarters_req = _quarters(ql)
    if not quarters_req and re.search(r"par trimestre|chaque trimestre", ql, re.I) and not quarter:
        quarters_req = [1, 2, 3, 4]
    if len(quarters_req) >= 2 and year:
        lines = [f"Tonnage par trimestre ({year}) :"]
        total = 0
        for q_n in sorted(set(quarters_req)):
            v = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {_where(year=year, quarter=q_n)}') or 0
            lines.append(f"  T{q_n} : {v:>14,.0f} T")
            total += v
        lines.append(f"  {'TOTAL':<5} : {total:>14,.0f} T")
        return "\n".join(lines)

    # 1. Semaine ISO précise sans mois → scalaire (ex: "S17 2026", "S3 2026")
    #    Si mois ET semaine sont présents, on préfère le breakdown mensuel (branche 2)
    if iso_week and year and not month:
        label = _label(year, None, quarter, semester, iso_week=iso_week)
        w = _where(year=year, iso_week=iso_week if iso_week > 0 else None)
        parts = []
        if kw_ton:
            val = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {w}') or 0
            if val == 0:
                return _no_data(TABLE, label, year=year, con=con,
                                extra_hint="Essayez une plage : *S1-S6 2026*")
            parts.append(f"Tonnage ({label}) : {val:,.0f} T")
        if kw_voy:
            val = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {w}') or 0
            parts.append(f"Voyages ({label}) : {val:,.0f} voyages")
        return "\n".join(parts) if parts else None

    # 2. Ventilation hebdomadaire ISO dans un mois (ex: "semaine par semaine en Avril 2026")
    if "semaine" in ql and month and year:
        label = _label(year, month, quarter, semester)
        df = _weekly_sql(_where(year=year, month=month))
        if df.empty:
            return f"Aucune donnée pour {label}."
        parts = []
        if kw_ton:
            parts.append(_fmt_weekly(f"Tonnage par semaine — {label}", [(int(r.semaine), r.tonnage) for _, r in df.iterrows()]))
        if kw_voy:
            parts.append(_fmt_weekly(f"Voyages par semaine — {label}", [(int(r.semaine), r.voyages) for _, r in df.iterrows()]))
        return "\n\n".join(parts)

    # 2b. Ventilation hebdomadaire pour une année entière avec en-têtes mois
    if wants_weekly_year and year and not month and not iso_week and not iso_range:
        df = _weekly_sql(_where(year=year))
        if df.empty:
            return f"Aucune donnée hebdomadaire pour {year}."

        def _month_of(dt) -> int | None:
            try:
                return pd.Timestamp(dt).month if pd.notna(dt) else None
            except Exception:
                return None

        def _weekly_with_months(title: str, col: str) -> str:
            lines = [f"{title} :"]
            cur_month = None
            total = 0
            for _, r in df.iterrows():
                wk = int(r.semaine)
                val = r[col] or 0
                m_n = _month_of(r['date_debut'])
                if m_n and m_n != cur_month:
                    lines.append(f"  ── {MOIS_NUM_FR[m_n]} ──")
                    cur_month = m_n
                lines.append(f"  S{wk:<2} : {val:>14,.0f}")
                total += val
            lines.append(f"  {'TOTAL':<5} : {total:>14,.0f}")
            return "\n".join(lines)

        parts = []
        if kw_ton:
            parts.append(_weekly_with_months(f"Tonnage descendu par semaine {year}", "tonnage"))
        if kw_voy:
            parts.append(_weekly_with_months(f"Voyages par semaine {year}", "voyages"))
        return "\n\n".join(parts) if parts else None

    # 3. Ventilation mensuelle (ex: "tonnage par mois en 2026")
    if year and not month and not quarter and not semester and not iso_week and wants_breakdown and not wants_weekly_year:
        df = _q(con, f"""
            SELECT MONTH({COL['date']}) as m,
                   SUM("{COL['qty']}") as tonnage,
                   SUM("{COL['voy']}") as voyages
            FROM {TABLE} {_where(year=year)}
            GROUP BY 1 ORDER BY 1
        """)
        if df.empty:
            return _no_data(TABLE, str(year), year=year, con=con)
        parts = []
        if kw_ton:
            parts.append(_fmt_monthly(f"Tonnage descendu mensuel {year}", [(int(r.m), r.tonnage) for _, r in df.iterrows()]))
        if kw_voy:
            parts.append(_fmt_monthly(f"Voyages mensuels {year}", [(int(r.m), r.voyages) for _, r in df.iterrows()]))
        return "\n\n".join(parts)

    # 4. Plusieurs mois (comparaison)
    if len(months) >= 2 and year:
        parts = []
        for m in months:
            w = _where(year=year, month=m)
            if kw_ton:
                val = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {w}') or 0
                parts.append(f"  {MOIS_NUM_FR[m]} {year} : {val:,.0f} T")
            if kw_voy:
                val = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {w}') or 0
                parts.append(f"  {MOIS_NUM_FR[m]} {year} : {val:,.0f} voyages")
        return "\n".join(parts)

    # Aucune période précisée → demander des précisions
    if kw_ton and not year and not months and not quarter and not semester and not iso_week and not iso_range:
        return (
            "Pour le tonnage, merci de préciser la période :\n\n"
            "- **Année** : *2024, 2025, 2026*\n"
            "- **Mois** : *janvier 2026*, *mars–avril 2025*\n"
            "- **Semaine ISO** : *S17 2026* · *S1–S6 2026*\n"
            "- **Trimestre** : *T1 2026* · **Semestre** : *S1 2025*\n"
            "- **Date précise** : *le 03/02/2026*\n\n"
            "_Exemple : « Tonnage par mois en 2026 »_"
        )

    # 5. Scalaire (mois précis, trimestre, semestre, total annuel)
    label = _label(year, month, quarter, semester)
    w = _where(year=year, month=month, quarter=quarter, semester=semester)
    parts = []
    # Détecter si l'utilisateur a précisé un type → pas de note désambiguïsation
    has_type_kw = any(k in ql for k in ["descente", "descendu", "excav", "transport", "port", "paa", "navire"])
    if kw_ton:
        val = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {w}') or 0
        if val == 0:
            count = _scalar(con, f'SELECT COUNT(*) FROM {TABLE} {w}') or 0
            if count == 0:
                return _no_data(TABLE, label, year=year, con=con,
                                extra_hint="Précisez la période : *tonnage par mois en 2025*")
        note = "" if has_type_kw else _TONNAGE_TYPES_NOTE
        parts.append(f"Tonnage **descendu** ({label}) : {val:,.0f} T{note}")
    if kw_voy:
        val = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {w}') or 0
        parts.append(f"Voyages ({label}) : {val:,.0f} voyages")
    return "\n".join(parts) if parts else None


_TAUX_LEGEND = "  _(✅ ≥95% · ⚠️ 80–94% · ❌ <80%)_"

def _taux(realise: float, prevu: float) -> str:
    """Formate un taux d'accomplissement avec indicateur visuel."""
    if not prevu:
        return "n/d"
    t = realise / prevu * 100
    icon = "✅" if t >= 95 else ("⚠️" if t >= 80 else "❌")
    return f"{t:.1f}% {icon}"


def handle_compare_years(con, ql: str) -> str | None:
    years = re.findall(r"\b(20\d{2})\b", ql)
    if len(years) < 2:
        return None
    if not any(w in ql for w in ["compar", "vs", "versus", "contre", "ecart", "difference", "evolution", "entre"]):
        return None
    y1, y2 = int(years[0]), int(years[1])

    # Détecter le sujet de la comparaison
    kw_ton = any(w in ql for w in ["tonnage", "quantite", "tonne", "descente"])
    kw_voy = any(w in ql for w in ["voyage", "rotation"])
    kw_tmb = any(w in ql for w in ["tombereau", "engin"])
    kw_obj = any(w in ql for w in ["objectif", "prevision", "prevu", "realise", "taux", "accomplissement", "atteint"])
    # Sans sujet explicite → comparaison complète
    all_ = not (kw_ton or kw_voy or kw_tmb or kw_obj)

    parts = []

    if kw_ton or all_:
        v1 = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {_where(year=y1)}') or 0
        v2 = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {_where(year=y2)}') or 0
        diff, pct = v2 - v1, (v2 - v1) / v1 * 100 if v1 else 0
        parts.append(
            f"Tonnage descente :\n"
            f"  {y1} : {v1:>14,.0f} T\n"
            f"  {y2} : {v2:>14,.0f} T\n"
            f"  Écart  : {diff:>+13,.0f} T  ({pct:+.1f}%)"
        )

    if kw_voy or all_:
        v1 = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {_where(year=y1)}') or 0
        v2 = _scalar(con, f'SELECT SUM("{COL["voy"]}") FROM {TABLE} {_where(year=y2)}') or 0
        diff, pct = v2 - v1, (v2 - v1) / v1 * 100 if v1 else 0
        parts.append(
            f"Voyages :\n"
            f"  {y1} : {v1:>14,.0f}\n"
            f"  {y2} : {v2:>14,.0f}\n"
            f"  Écart  : {diff:>+14,.0f}  ({pct:+.1f}%)"
        )

    if kw_tmb or all_:
        flt = f"LOWER(\"{COL['engin']}\") LIKE '%tombereau%'"
        n1 = _scalar(con, f'SELECT COUNT(DISTINCT "{COL["engin"]}") FROM {TABLE} {_where(year=y1)} AND {flt}') or 0
        n2 = _scalar(con, f'SELECT COUNT(DISTINCT "{COL["engin"]}") FROM {TABLE} {_where(year=y2)} AND {flt}') or 0
        parts.append(f"Tombereaux distincts (nommés 'TOMBEREAU…') :\n  {y1} : {n1} tombereau(x)\n  {y2} : {n2} tombereau(x)")

    if kw_obj or all_:
        try:
            lines = [f"Taux accomplissement descente :{_TAUX_LEGEND}"]
            for yr in (y1, y2):
                prev = _scalar(con, f'SELECT SUM("{OBJ_DESCENTE}") FROM {OBJ_TABLE} WHERE {OBJ_DATE} IS NOT NULL AND YEAR({OBJ_DATE}) = {yr}') or 0
                real = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE} {_where(year=yr)}') or 0
                lines.append(f"  {yr} : {real:>10,.0f} / {prev:>10,.0f} T  → {_taux(real, prev)}")
            parts.append("\n".join(lines))
        except Exception:
            pass

    if not parts:
        return None
    return f"Comparaison {y1} vs {y2} :\n\n" + "\n\n".join(parts)



# Questions méta/analytiques → LLM plutôt que handler SQL
_META_KW_ACTIONS = frozenset({
    "prioris", "choisir", "choisirais", "recommand", "sugger",
    "meilleur", "identique", "similaire", "format", "synthetis",
    "que faire", "comparer les fichiers", "compare les",
})

# Mots-clés domaine PGES (environnement, déchets, communautés…)
_PGES_DOMAIN_KW = frozenset({
    "pges", "ande",
    "environnemental", "environnement",
    "dechet",
    "indemnisation",
    "communaute", "population",
    "rehabilitation", "reboisement",
    "hydrocarbure",
    "erosion",
    "biodiversite",
    "poussiere",
    "taux avancement",
    "niveau avancement",
    "recommandation ande",
    "plan de gestion",
})


def handle_suivi_actions(con, ql: str) -> str | None:
    """Obligations HSE (suivi_actions) et actions PGES (pges_actions).

    Supports :
    - Filtre par statut (en cours, non réalisé, réalisé)
    - Filtre par responsable ("actions de N'guessan", "responsable LEB")
    - Filtre par mot-clé dans le titre ("comité santé", "rapport mensuel")
    - Filtre par numéro d'action PGES ("action n°14", "action 14")
    - Tri par urgence ("actions correctives prioriser en urgence")
    """
    # Questions sur actions correctives / urgence → répondre depuis la DB même si "prioris" présent
    _is_urgence_query = any(w in ql for w in [
        "corrective", "correctives", "urgence", "urgent", "urgentes",
        "prioritaire", "prioritaires", "priorite",
    ])
    # Exception PGES/ANDE : si la question porte sur le PGES, ne pas bloquer même si
    # "recommand" est présent (ex: "recommandations ANDE" ≠ question méta-analytique)
    _is_pges_context = any(kw in ql for kw in _PGES_DOMAIN_KW)
    # Questions méta/analytiques générales → laisser au LLM (sauf si urgence/corrective/PGES)
    if not _is_urgence_query and not _is_pges_context and any(kw in ql for kw in _META_KW_ACTIONS):
        return None

    kw = ["action", "obligation", "pges", "hse", "non realise", "en cours",
          "recommandation ande", "ande", "plan de gestion", "avancement pges",
          "plan gestion", "environnemental avancement"]
    if not any(w in ql for w in kw):
        return None
    if any(w in ql for w in ["tonnage", "taux", "descente", "excav", "prevu"]) and \
       not any(w in ql for w in ["pges", "obligation", "hse", "avancement"]):
        return None

    kw_pges  = any(kw in ql for kw in _PGES_DOMAIN_KW)
    kw_non_r = any(w in ql for w in [
        "non realise", "non realisee", "pas realise",
        "non effectue", "non respecte", "non accompli",
        "restent a faire", "pas encore", "jamais fait", "pas termine",
        "non fait", "pas fait",
    ])
    kw_cours = any(w in ql for w in ["en cours", "executer", "a faire"])
    kw_real  = any(w in ql for w in [
        "realise", "termine", "acheve", "fait", "accompli", "effectue", "execute",
    ]) and not kw_non_r

    # ── Détection de filtre responsable ─────────────────────────────────────
    # Pattern strict : "responsable [de] X", "dont le responsable est X"
    resp_filter = None
    m_resp = re.search(
        r"(?:responsable\s+(?:de\s+|est\s+)?|dont le responsable est\s+)"
        r"([A-Za-zÀ-ÿ'\-]{3,})",
        ql, re.I
    )
    if m_resp:
        resp_kw = m_resp.group(1).strip()
        # Sanitiser avant injection SQL (supprimer guillemets, points-virgules…)
        resp_kw = re.sub(r"[\"';\\%]", "", resp_kw)
        if len(resp_kw) >= 3 and resp_kw.lower() not in {"les", "des", "que", "est", "une", "action"}:
            resp_filter = resp_kw

    # ── Détection numéro d'action PGES ──────────────────────────────────────
    num_filter = None
    m_num = re.search(r"(?:action\s+n[°o]?\s*|n[°o]\s*)(\d+)", ql, re.I)
    if m_num:
        num_filter = int(m_num.group(1))

    # ── Détection de mot-clé dans titre ─────────────────────────────────────
    title_kw = None
    _stop = {"action", "actions", "obligation", "obligations", "hse", "pges",
             "quelles", "quels", "sont", "les", "qui", "dont", "responsable",
             "statut", "liste", "toutes", "tous", "dans", "avec", "pour",
             "concernent", "concerne", "portent", "porte", "sur",
             # Mots d'urgence/corrective → ne pas utiliser comme filtre titre
             "corrective", "correctives", "urgentes", "urgents", "urgence",
             "urgent", "prioritaire", "prioritaires", "priorite"}
    if not _is_urgence_query and not resp_filter and not num_filter \
            and not kw_cours and not kw_real and not kw_non_r:
        words = [w for w in re.findall(r"\b[A-Za-zÀ-ÿ]{5,}\b", ql, re.I)
                 if w.lower() not in _stop]
        if words:
            # Sanitiser avant injection SQL
            title_kw = re.sub(r"[\"';\\%]", "", words[0])

    results = []

    if kw_pges or num_filter:
        total = con.execute("SELECT COUNT(*) FROM pges_actions").fetchone()[0]

        where_parts = []
        if num_filter:
            where_parts.append(f'"N°" = {num_filter}')
        if resp_filter:
            where_parts.append(f'LOWER("Responsable") LIKE \'%{resp_filter.lower()}%\'')

        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        df = _q(con, f"""
            SELECT "N°", "Actions PGES / Recommandation ANDE" AS action,
                   COALESCE("Niveau d'avancement", 'Non démarré') AS avancement,
                   Responsable
            FROM pges_actions {where}
            ORDER BY 1
        """)

        if num_filter and not df.empty:
            # Détail complet pour une action précise
            r = df.iloc[0]
            lines = [f"Action PGES n°{int(r['N°'])} :"]
            lines.append(f"  Description : {str(r['action'] or '')}")
            lines.append(f"  Avancement  : {r['avancement']}")
            lines.append(f"  Responsable : {r['Responsable'] or 'Non précisé'}")
        else:
            label = f"par {resp_filter}" if resp_filter else f"({len(df)}/{total})"
            lines = [f"Actions PGES {label} :"]
            for _, r in df.iterrows():
                act = str(r['action'] or "")[:65]
                resp = f" [Resp: {r['Responsable']}]" if resp_filter and r['Responsable'] else ""
                lines.append(f"  #{int(r['N°'])} · {act}{resp}")
        results.append("\n".join(lines))

    else:
        total = con.execute("SELECT COUNT(*) FROM suivi_actions").fetchone()[0]
        statuts_df = _q(con, """
            SELECT Statuts, COUNT(*) AS nb
            FROM suivi_actions WHERE Statuts IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
        """)
        stat_line = " · ".join(f"{r['Statuts']}: {int(r.nb)}" for _, r in statuts_df.iterrows())

        # Construire les filtres WHERE
        where_parts = []
        if kw_real:
            where_parts.append("Statuts LIKE '%Réalisé%'")
        elif kw_cours:
            where_parts.append("Statuts LIKE '%En cours%'")
        elif kw_non_r:
            where_parts.append("Statuts LIKE '%Non réalisé%'")
        else:
            where_parts.append("Statuts NOT LIKE '%Réalisé%'")

        if resp_filter:
            where_parts.append(f'LOWER("Responsable R2M") LIKE \'%{resp_filter.lower()}%\'')
        if title_kw:
            where_parts.append(
                f'(LOWER("Titre des obligations") LIKE \'%{title_kw.lower()}%\' OR '
                f'LOWER("Description") LIKE \'%{title_kw.lower()}%\')'
            )

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        # Pour les requêtes d'urgence : trier par deadline croissante + priorité
        _order = ("ORDER BY Deadline NULLS LAST, Priorité, Statuts"
                  if _is_urgence_query else "ORDER BY Priorité, Statuts")
        df_sel = _q(con, f"""
            SELECT "Titre des obligations", Statuts,
                   COALESCE(CAST("% Avancement" AS VARCHAR), '?') AS pct,
                   Priorité, "Responsable R2M", Deadline
            FROM suivi_actions {where}
            {_order}
        """)

        if resp_filter or title_kw:
            # Mode recherche spécifique — détail complet
            label = f"responsable '{resp_filter}'" if resp_filter else f"contenant '{title_kw}'"
            if df_sel.empty and title_kw:
                # Fallback : chercher aussi dans pges_actions
                df_pges_fb = _q(con, f"""
                    SELECT "N°", "Actions PGES / Recommandation ANDE" AS action,
                           COALESCE("Niveau d'avancement", 'Non démarré') AS avancement,
                           Responsable
                    FROM pges_actions
                    WHERE LOWER("Actions PGES / Recommandation ANDE") LIKE '%{title_kw.lower()}%'
                       OR LOWER(COALESCE("Sous actions", ''))           LIKE '%{title_kw.lower()}%'
                    ORDER BY 1 LIMIT 10
                """)
                if not df_pges_fb.empty:
                    fb_lines = [f"Actions PGES — contenant '{title_kw}' ({len(df_pges_fb)}) :"]
                    for _, r in df_pges_fb.iterrows():
                        act = str(r['action'] or "")[:70]
                        fb_lines.append(f"  #{int(r['N°'])} · {act} [{r['avancement']}]")
                    results.append("\n".join(fb_lines))
                    results.append(f"_📋 pges_actions (fallback depuis suivi_actions)_")
                else:
                    results.append(f"Aucune obligation HSE ni action PGES contenant '{title_kw}'.")
            else:
                lines = [f"Obligations HSE — {label} ({len(df_sel)}) :"]
                for _, r in df_sel.iterrows():
                    titre = str(r['Titre des obligations'] or "")[:70]
                    resp = str(r['Responsable R2M'] or "Non précisé")
                    pct = str(r['pct']).split('.')[0] if str(r['pct']) != '?' else '?'
                    dl = str(r['Deadline'])[:10] if r['Deadline'] and str(r['Deadline']) != 'NaT' else "—"
                    lines.append(f"  [{r['Statuts']}] {titre}")
                    lines.append(f"    Responsable: {resp} | Avancement: {pct}% | Deadline: {dl}")
                results.append("\n".join(lines))
        else:
            # Mode liste standard
            lines = [f"Obligations HSE ({total} total) : {stat_line}",
                     f"\n  Sélection ({len(df_sel)}) :"]
            for _, r in df_sel.iterrows():
                titre = str(r['Titre des obligations'] or "")[:58]
                pct = str(r['pct']).split('.')[0] if str(r['pct']) != '?' else '?'
                lines.append(f"  [{r['Statuts']}] {titre} ({pct}%)")
            results.append("\n".join(lines))

    if not results:
        return None
    src = "_📋 pges_actions_" if (kw_pges or num_filter) else "_📋 suivi_actions_"
    return "\n\n".join(results) + f"\n\n{src}"


def handle_objectifs(con, ql: str, year) -> str | None:
    """Objectifs (prévu) vs réalisé + taux d'accomplissement."""
    kw = ["objectif", "prevision", "prevu", "realise", "taux", "accomplissement",
          "atteint", "remplissage", "budget", "plan de production",
          "planification", "planning", "programme", "programme production",
          "cible production", "objectif journalier"]
    if not any(k in ql for k in kw):
        return None
    # Ne pas intercepter les questions d'actions/obligations HSE
    if any(w in ql for w in ["action", "obligation", "pges", "hse"]) and \
       not any(w in ql for w in ["tonnage", "taux", "descente", "excav"]):
        return None
    # Ne pas intercepter les questions sur disponibilité/shifts (taux ≠ taux d'accomplissement)
    if any(w in ql for w in ["disponibilite", "taux disponibilite", "heure machine",
                              "heures machine", "shift", "vacation",
                              "disponibilite des engin"]):
        return None
    # Ne pas intercepter les questions sur rapports uploadés / inspections / PGES
    if any(w in ql for w in ["inspection", "rapport", "organisme", "audit",
                              "non-conformit", "non conformit", "bureau",
                              "certif", "visite", "constat"]):
        return None
    if any(kw in ql for kw in _PGES_DOMAIN_KW):
        return None

    kw_exc = any(w in ql for w in ["excavation", "excav", "excave"])
    kw_desc = any(w in ql for w in ["descente", "descendre", "tonnage"]) or not kw_exc

    lbl = _label(year, None, None, None)
    yf = f" AND YEAR({OBJ_DATE}) = {year}" if year else ""
    yf_d = f" {_where(year=year)}" if year else ""
    parts = []

    if kw_desc:
        prev = _scalar(con, f'SELECT SUM("{OBJ_DESCENTE}") FROM {OBJ_TABLE} WHERE {OBJ_DATE} IS NOT NULL{yf}') or 0
        real = _scalar(con, f'SELECT SUM("{COL["qty"]}") FROM {TABLE}{yf_d}') or 0
        diff = real - prev
        parts.append(
            f"Descente minerai :\n"
            f"  Prévu   (objectifs) : {prev:>12,.0f} T\n"
            f"  Réalisé             : {real:>12,.0f} T\n"
            f"  Écart               : {diff:>+12,.0f} T\n"
            f"  Taux accomplissement: {_taux(real, prev)}\n"
            f"{_TAUX_LEGEND}"
        )

    if kw_exc:
        prev_e = _scalar(con, f'SELECT SUM("{OBJ_EXCAV}") FROM {OBJ_TABLE} WHERE {OBJ_DATE} IS NOT NULL{yf}') or 0
        real_e = _scalar(con, f'SELECT SUM("{EXC_QTY}") FROM {EXC_TABLE} WHERE {EXC_DATE} IS NOT NULL' + (f' AND YEAR({EXC_DATE}) = {year}' if year else '')) or 0
        diff_e = real_e - prev_e
        parts.append(
            f"Excavation :\n"
            f"  Prévu   (objectifs) : {prev_e:>12,.0f} T\n"
            f"  Réalisé             : {real_e:>12,.0f} T\n"
            f"  Écart               : {diff_e:>+12,.0f} T\n"
            f"  Taux accomplissement: {_taux(real_e, prev_e)}\n"
            f"{_TAUX_LEGEND}"
        )

    return (f"Objectifs vs Réalisé ({lbl}) :\n\n" + "\n\n".join(parts)
            + f"\n\n_📋 {OBJ_TABLE}_") if parts else None


def handle_tonnage_excav(con, ql: str, year, months=None, quarter=None,
                          semester=None, iso_week=None, iso_range=None,
                          specific_date=None) -> str | None:
    """Tonnage excavé (table excavation) — déclenché par excavation/excavé/volume."""
    has_excav = any(w in ql for w in ["excavation", "excave", "excav",
                                       "volume extrait", "volume excave",
                                       "extrait", "extraction",
                                       "tonnage qd", " qd ", "tonnage bq", " bq ",
                                       "tonnage mq", " mq ", "lineaire", "profondeur"])
    if not has_excav:
        return None
    # "Tonnage excavé" nécessite un mot quantitatif ; "Excavation 2024" seul est accepté
    has_qty = any(w in ql for w in ["tonnage", "quantite", "tonne", "volume"])
    if not has_qty and not any(w in ql for w in ["excavation", "excave"]):
        return None

    # Construire le filtre temporel pour EXC_TABLE (colonne Date ≠ DATE de descente_minerai)
    w_parts = [f"{EXC_DATE} IS NOT NULL"]
    if specific_date:
        _d = f"{specific_date[8:10]}/{specific_date[5:7]}/{specific_date[:4]}"
        w_parts.append(f"CAST({EXC_DATE} AS DATE) = DATE '{specific_date}'")
        lbl = f"le {_d}"
    elif year:
        w_parts.append(f"YEAR({EXC_DATE}) = {year}")
        if semester:
            sem_m = {1: [1,2,3,4,5,6], 2: [7,8,9,10,11,12]}[semester]
            w_parts.append(f"MONTH({EXC_DATE}) IN ({','.join(map(str, sem_m))})")
        elif quarter:
            q_m = {1:[1,2,3], 2:[4,5,6], 3:[7,8,9], 4:[10,11,12]}[quarter]
            w_parts.append(f"MONTH({EXC_DATE}) IN ({','.join(map(str, q_m))})")
        elif months and len(months) == 1:
            w_parts.append(f"MONTH({EXC_DATE}) = {months[0]}")
        lbl = _label(year, months[0] if months and len(months) == 1 else None, quarter, semester)
    else:
        lbl = "toutes périodes"
    exc_w = "WHERE " + " AND ".join(w_parts)

    wants_monthly = ("par mois" in ql or "mensuel" in ql) and year and not specific_date
    if wants_monthly:
        rows = con.execute(f"""
            SELECT MONTH({EXC_DATE}) as m, SUM("{EXC_QTY}") as tonnage
            FROM {EXC_TABLE} WHERE {EXC_DATE} IS NOT NULL AND YEAR({EXC_DATE}) = {year}
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        if not rows:
            return (_no_data(EXC_TABLE, str(year), year=year, con=con)
                    + f"\n\n_📋 {EXC_TABLE}_")
        return _fmt_monthly(f"Tonnage excavé mensuel {year}", rows) + f"\n\n_📋 {EXC_TABLE}_"

    # Colonnes QD/BQ/MQ spécifiques
    wants_qd = bool(re.search(r'\bqd\b', ql)) or "tonnage qd" in ql
    wants_bq = bool(re.search(r'\bbq\b', ql)) or "tonnage bq" in ql
    wants_mq = bool(re.search(r'\bmq\b', ql)) or "tonnage mq" in ql
    if wants_qd or wants_bq or wants_mq:
        col_map = {"QD": "Tonnage QD", "BQ": "Tonnage BQ", "MQ": "Tonnage MQ"}
        selected = []
        if wants_qd: selected.append(("QD", "Tonnage QD"))
        if wants_bq: selected.append(("BQ", "Tonnage BQ"))
        if wants_mq: selected.append(("MQ", "Tonnage MQ"))
        parts = []
        for label_q, col_q in selected:
            try:
                v = con.execute(f'SELECT SUM("{col_q}") FROM {EXC_TABLE} {exc_w}').fetchone()[0] or 0
                parts.append(f"Tonnage {label_q} ({lbl}) : {v:,.0f} T")
            except Exception:
                pass
        if parts:
            return "\n".join(parts) + f"\n\n_📋 {EXC_TABLE}_"

    val = con.execute(f'SELECT SUM("{EXC_QTY}") FROM {EXC_TABLE} {exc_w}').fetchone()[0] or 0
    if val == 0:
        return _no_data(EXC_TABLE, lbl, year=year, con=con)
    return f"Tonnage **excavé** ({lbl}) : {val:,.0f} T\n_📋 {EXC_TABLE}_"


def handle_tonnage_transport(con, ql: str, year, months=None, quarter=None,
                              semester=None, specific_date=None) -> str | None:
    """Tonnage transporté mine→port ou arrivé au port ou chargé sur navire."""
    kw_navire = any(w in ql for w in ["navire", "navires", "bateau", "bateaux",
                                       "chargement navire", "productivite"])
    kw_port   = bool(re.search(r"arriv[eé]e?\s+(?:au\s+)?port|paa|reception port", ql, re.I))
    kw_trans  = any(w in ql for w in [
        "transporte", "camion mine", "charge mine",
        "rotation transport", "rotation camion", "voyage camion",
        "depart mine", "arrive port",
    ])
    # "transport" seul avec tonnage/quantité → tonnage transporté
    if not kw_trans and "transport" in ql and \
       any(w in ql for w in ["tonnage", "quantite", "tonne", "total", "par mois"]):
        kw_trans = True
    # "rotation" + "transport" dans la même question → transport PAA
    if not kw_trans and "rotation" in ql and "transport" in ql:
        kw_trans = True
    # "transport" + "mine" + "port" dans la même question → priorité côté mine
    # (l'utilisateur formule un trajet mine→port, pas une arrivée PAA)
    _kw_trans_mine_explicit = (
        not kw_trans and "transport" in ql and "mine" in ql and "port" in ql
    )
    if _kw_trans_mine_explicit:
        kw_trans = True
    # Contexte "mine + port" avec tonnage/volume → transport
    if not kw_trans and any(w in ql for w in ["mine", "depart"]) and \
       any(w in ql for w in ["port", "paa"]) and \
       any(w in ql for w in ["tonnage", "ecart", "difference", "perte"]):
        kw_trans = True

    if not (kw_navire or kw_port or kw_trans):
        return None
    # Navire ou contexte PAA : pas besoin de "tonnage" explicite
    if not kw_navire and not kw_port and not kw_trans and \
       not any(w in ql for w in ["tonnage", "quantite", "tonne", "charge"]):
        return None

    # Construire le label de période
    if specific_date:
        _d = f"{specific_date[8:10]}/{specific_date[5:7]}/{specific_date[:4]}"
        lbl = f"le {_d}"
    else:
        lbl = _label(year, months[0] if months and len(months) == 1 else None, quarter, semester)

    def _period_filter(date_col: str) -> str:
        """Retourne les conditions AND pour la période (sans WHERE)."""
        parts = []
        if specific_date:
            parts.append(f'CAST("{date_col}" AS DATE) = DATE \'{specific_date}\'')
        elif year:
            parts.append(f'YEAR("{date_col}") = {year}')
            if semester:
                sem_m = {1:[1,2,3,4,5,6], 2:[7,8,9,10,11,12]}[semester]
                parts.append(f'MONTH("{date_col}") IN ({",".join(map(str, sem_m))})')
            elif quarter:
                q_m = {1:[1,2,3],2:[4,5,6],3:[7,8,9],4:[10,11,12]}[quarter]
                parts.append(f'MONTH("{date_col}") IN ({",".join(map(str, q_m))})')
            elif months and len(months) == 1:
                parts.append(f'MONTH("{date_col}") = {months[0]}')
        return (" AND " + " AND ".join(parts)) if parts else ""

    if kw_navire:
        pf = _period_filter(LOAD_DATE)
        df = _q(con, f"""
            SELECT "NAVIRE", SUM("{LOAD_QTY}") AS tonnage
            FROM {LOAD_TABLE}
            WHERE {LOAD_DATE} IS NOT NULL{pf}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return _no_data(LOAD_TABLE, lbl, year=year, con=con)
        total = df['tonnage'].sum()
        rows = [(r['NAVIRE'], f"{r.tonnage:>12,.0f} T") for _, r in df.iterrows()]
        table = _fmt_table(f"Tonnage chargé par navire ({lbl})", rows, ["Navire", "Tonnage"])
        return f"{table}\n  {'TOTAL':<22} : {total:>12,.0f} T\n_📋 {LOAD_TABLE}_"

    # Côté mine vs côté port :
    # Si l'utilisateur a explicitement mentionné "mine" + "port" (trajet)
    # → données côté mine (départ), même si "paa" est aussi présent.
    if kw_port and not _kw_trans_mine_explicit:
        col_qty, date_col, label_type = TRANS_QTY_PORT, TRANS_DATE_PORT, "arrivé au port"
    else:
        col_qty, date_col, label_type = TRANS_QTY_MINE, TRANS_DATE_MINE, "transporté mine→port"

    pf = _period_filter(date_col)
    w  = f'WHERE "{date_col}" IS NOT NULL{pf}'
    val = con.execute(f'SELECT SUM("{col_qty}") / 1000 FROM {TRANS_TABLE} {w}').fetchone()[0] or 0

    # Si "différence" ou "écart" demandé, afficher les deux côtés
    if any(k in ql for k in ["difference", "ecart", "perte", "comparaison"]):
        pf_m = _period_filter(TRANS_DATE_MINE)
        pf_p = _period_filter(TRANS_DATE_PORT)
        v_m = con.execute(f'SELECT SUM("{TRANS_QTY_MINE}") / 1000 FROM {TRANS_TABLE} WHERE "{TRANS_DATE_MINE}" IS NOT NULL{pf_m}').fetchone()[0] or 0
        v_p = con.execute(f'SELECT SUM("{TRANS_QTY_PORT}") / 1000 FROM {TRANS_TABLE} WHERE "{TRANS_DATE_PORT}" IS NOT NULL{pf_p}').fetchone()[0] or 0
        diff = v_p - v_m
        return (
            f"Transport minerai ({lbl}) :\n"
            f"  Chargé à la mine        : {v_m:>12,.0f} T\n"
            f"  Réceptionné au port PAA : {v_p:>12,.0f} T\n"
            f"  Différence (écart)      : {diff:>+12,.0f} T\n"
            f"_📋 {TRANS_TABLE}_"
        )

    return f"Tonnage **{label_type}** ({lbl}) : {val:,.0f} T\n_📋 {TRANS_TABLE}_"


def handle_per_year(con, ql: str) -> str | None:
    kw = ["annee", "par annee", "chaque annee", "bilan annuel", "toutes les annees"]
    if not any(re.search(rf"\b{re.escape(k)}\b", ql) for k in kw):
        return None
    if not any(w in ql for w in ["tonnage", "quantite", "tonne", "voyage", "production"]):
        return None
    kw_voy = any(w in ql for w in ["voyage", "rotation"])
    sql = f"""
        SELECT YEAR({COL['date']}) as annee,
               SUM("{COL['qty']}") as tonnage,
               SUM("{COL['voy']}") as voyages
        FROM {TABLE}
        GROUP BY 1 ORDER BY 1
    """
    df = _q(con, sql)
    if df.empty:
        return "Aucune donnée."
    lines = []
    for _, r in df.iterrows():
        if kw_voy:
            lines.append(f"  {int(r.annee)} : {r.tonnage:,.0f} T | {r.voyages:,.0f} voyages")
        else:
            lines.append(f"  {int(r.annee)} : {r.tonnage:,.0f} T")
    return "Tonnage par annee :\n" + "\n".join(lines)


def _engin_norm_expr() -> str:
    """Normalise 'TOMBEREAU X' (ancienne nomenclature) → 'TOMBEREAU CAT N°X'.
    Approche LIKE uniquement (pas de REGEXP) — robuste sur toutes versions DuckDB."""
    e = COL['engin']
    # 'TOMBEREAU %' AND NOT '% CAT %' → ancienne forme "TOMBEREAU 1" etc.
    # SUBSTRING(str, 11) extrait ce qui suit "TOMBEREAU " (10 chars + espace = pos 11)
    return (
        f"CASE WHEN UPPER(TRIM(\"{e}\")) LIKE 'TOMBEREAU %'"
        f" AND UPPER(TRIM(\"{e}\")) NOT LIKE '% CAT %'"
        f" THEN 'TOMBEREAU CAT N°' || TRIM(SUBSTRING(UPPER(TRIM(\"{e}\")), 11))"
        f" ELSE UPPER(TRIM(\"{e}\")) END"
    )


def handle_tombereaux(con, ql: str) -> str | None:
    if "tombereau" not in ql:
        return None

    year = _year(ql)
    lbl  = _label(year, None, None, None)

    _filter = f"LOWER(\"{COL['engin']}\") LIKE '%tombereau%'"
    _norm   = _engin_norm_expr()

    # Clause de filtre année (optionnelle)
    yr_cond = f" AND YEAR(\"{COL['date']}\") = {year}" if year else ""

    # ── Intentions détectées indépendamment ──────────────────────────────────
    wants_utilisation = any(w in ql for w in [
        "utilisation", "utilise", "plus utilise", "combien de fois",
        "frequence", "fois", "actif", "sessions",
    ])
    wants_voyage = any(w in ql for w in [
        "voyage", "trajet", "rotation", "aller-retour",
    ])
    wants_tonnage = any(w in ql for w in [
        "tonnage", "quantite", "tonne", "production", "transport",
    ])
    # Pannes : UNIQUEMENT sur mots-clés pannes — "classement" seul ne suffit plus
    wants_panne = any(w in ql for w in [
        "panne", "incident", "probleme", "souvent", "frequen",
        "arret", "immobilise", "defaillance",
    ])
    wants_count = any(w in ql for w in ["combien", "nombre", "unique", "distinct"])
    wants_list  = any(w in ql for w in ["liste", "quels", "quelles", "noms", "tous"])

    # ── Priorité des branches : intention explicite d'abord ─────────────────
    # 1. Utilisation (COUNT lignes par engin)
    if wants_utilisation:
        df = _q(con, f"""
            SELECT {_norm} AS tombereau, COUNT(*) AS nb_utilisations
            FROM {TABLE}
            WHERE {_filter}
              AND "{COL['engin']}" IS NOT NULL
              AND TRIM("{COL['engin']}") != ''
              {yr_cond}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return f"Aucune donnée d'utilisation pour les tombereaux ({lbl})."
        rows = [(r['tombereau'], str(int(r.nb_utilisations))) for _, r in df.iterrows()]
        return _fmt_table(
            f"Tombereaux classés par utilisation ({lbl})", rows,
            ["Tombereau", "Nb utilisations"]
        )

    # 2. Voyages (SUM voyages par engin)
    if wants_voyage:
        df = _q(con, f"""
            SELECT {_norm} AS tombereau, SUM("{COL['voy']}") AS nb_voyages
            FROM {TABLE}
            WHERE {_filter}
              AND "{COL['voy']}" IS NOT NULL
              {yr_cond}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return f"Aucune donnée de voyages pour les tombereaux ({lbl})."
        rows = [(r['tombereau'], f"{r.nb_voyages:,.0f}") for _, r in df.iterrows()]
        return _fmt_table(
            f"Tombereaux classés par voyages ({lbl})", rows,
            ["Tombereau", "Nb voyages"]
        )

    # 3. Pannes (observations contenant "panne")
    if wants_panne:
        df = _q(con, f"""
            SELECT {_norm} AS tombereau, COUNT(*) AS nb_pannes
            FROM {TABLE}
            WHERE {_filter}
              AND "{COL['obs']}" IS NOT NULL
              AND LOWER("{COL['obs']}") LIKE '%panne%'
              {yr_cond}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return f"Aucune panne enregistrée pour les tombereaux ({lbl})."
        rows = [(r['tombereau'], str(int(r.nb_pannes))) for _, r in df.iterrows()]
        return _fmt_table(
            f"Tombereaux classés par nombre de pannes ({lbl})", rows,
            ["Tombereau", "Nb pannes"]
        )

    # 4. Tonnage
    if wants_tonnage:
        df = _q(con, f"""
            SELECT {_norm} AS tombereau, SUM("{COL['qty']}") AS tonnage
            FROM {TABLE}
            WHERE {_filter}
              {yr_cond}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return f"Aucune donnée de tonnage pour les tombereaux ({lbl})."
        rows = [(r['tombereau'], f"{r.tonnage:,.0f} T") for _, r in df.iterrows()]
        return _fmt_table(
            f"Tonnage par tombereau ({lbl})", rows, ["Tombereau", "Tonnage"]
        )

    # 5. Comptage distinct
    if wants_count:
        nb = _scalar(con, f"""
            SELECT COUNT(DISTINCT {_norm})
            FROM {TABLE}
            WHERE {_filter}
              {yr_cond}
        """)
        return f"Nombre de tombereaux distincts ({lbl}) : {nb}"

    # 6. Liste (défaut)
    df = _q(con, f"""
        SELECT DISTINCT {_norm} AS tombereau
        FROM {TABLE}
        WHERE {_filter}
        ORDER BY 1
    """)
    return _fmt_list("Tombereaux", df['tombereau'].tolist())


def handle_engins(con, ql: str, year, months=None) -> str | None:
    if not any(w in ql for w in ["engin", "vehicule", "immatriculation", "machine", "camion"]):
        return None
    # Ne pas intercepter les questions sur les heures machine / shifts
    if any(w in ql for w in ["heure machine", "heures machine", "hm", "shift", "horaire", "disponibilite"]):
        return None
    month = months[0] if months and len(months) == 1 else None
    w = _where(year=year, month=month)
    wants_top = any(w in ql for w in ["top", "meilleur", "plus"])
    n = 5
    m = re.search(r"\b(\d+)\b", ql)
    if m and wants_top:
        n = int(m.group(1))

    _norm = _engin_norm_expr()
    we = _ext(w, f'"{COL["engin"]}" IS NOT NULL')
    lbl = _label(year, month, None, None, None)

    if wants_top:
        df = _q(con, f"""
            SELECT {_norm} AS engin_norm, SUM("{COL['qty']}") as tonnage
            FROM {TABLE} {we}
            GROUP BY 1 ORDER BY 2 DESC LIMIT {n}
        """)
        rows = [(r['engin_norm'], f"{r.tonnage:,.0f} T") for _, r in df.iterrows()]
        return _fmt_table(f"Top {n} engins ({lbl})", rows, ["Engin", "Tonnage"])

    df = _q(con, f"""
        SELECT DISTINCT {_norm} AS engin_norm
        FROM {TABLE}
        {_ext("", f'"{COL["engin"]}" IS NOT NULL')}
        ORDER BY 1
    """)
    return _fmt_list("Engins / tombereaux", df['engin_norm'].tolist())


def handle_responsable(con, ql: str, year) -> str | None:
    if not any(w in ql for w in ["responsable", "chef de site", "superviseur",
                                  "supervise", "qui est", "qui gere", "directeur site"]):
        return None
    w = _ext(
        _where(year=year),
        f'"{COL["resp"]}" IS NOT NULL',
        f"TRIM(\"{COL['resp']}\") NOT IN ('', '-', '*', '?')",
    )
    df = _q(con, f"""
        SELECT DISTINCT "{COL['resp']}"
        FROM {TABLE} {w}
        ORDER BY 1
    """)
    vals = df.iloc[:, 0].dropna().tolist()
    if not vals:
        return "Aucun responsable trouvé pour cette période."
    lbl = _label(year, None, None, None, None)
    if len(vals) == 1:
        return f"Responsable du site ({lbl}) : {vals[0]}"
    lines = "\n".join(f"  • {v}" for v in vals)
    return f"Responsables du site ({lbl}) ({len(vals)}) :\n{lines}\nPlusieurs responsables trouvés — précisez la période ?"


def handle_transport(con, ql: str) -> str | None:
    kw = ["societe de transport", "transporteur", "prestataire", "societe"]
    if not any(k in ql for k in kw):
        return None
    w = _ext("", f'"{COL["trans"]}" IS NOT NULL', f"TRIM(\"{COL['trans']}\") NOT IN ('', '-')")
    df = _q(con, f"""
        SELECT DISTINCT "{COL['trans']}"
        FROM {TABLE} {w}
        ORDER BY 1
    """)
    return _fmt_list("Société(s) de transport", df.iloc[:, 0].tolist())


def handle_qualite(con, ql: str) -> str | None:
    """Qualités de minerai de la table descente_minerai (PREMIER CHOIX, MQ, BQ…)."""
    if not any(w in ql for w in ["qualite", "qualites", "grade", "categorie", "type de minerai"]):
        return None
    # Laisser handle_qualite_echantillons pour les analyses chimiques
    if any(w in ql for w in ["echantillon", "navire", "teneur", "al2o3", "sio2", "fe2o3",
                              "alumine", "silice", "fer", "analyse", "labo", "laboratoire",
                              "resultat", "poids", "echantillonnage"]):
        return None
    w = _ext("", f'"{COL["qual"]}" IS NOT NULL', f"TRIM(\"{COL['qual']}\") NOT IN ('', '-')")
    df = _q(con, f"""
        SELECT DISTINCT "{COL['qual']}"
        FROM {TABLE} {w}
        ORDER BY 1
    """)
    return _fmt_list("Qualité(s) de minerai", df.iloc[:, 0].tolist())


# Constantes table qualite_echantillons
_QUAL_ECH_TABLE   = "qualite_echantillons"
_QUAL_ECH_DATE    = "Date Echantillonnage"
_QUAL_ECH_ID      = "ID ECH"
_QUAL_ECH_ZONE    = "ZONE"
_QUAL_ECH_AL2O3   = "Al2O3"
_QUAL_ECH_SIO2    = "SiO2"
_QUAL_ECH_FE2O3   = "Fe2O3"
_QUAL_ECH_LABO    = "Laboratoire"
_QUAL_ECH_POIDS   = "POIDS"
_QUAL_ECH_STOCK   = "STOCK DSO"


def handle_qualite_echantillons(con, ql: str, year) -> str | None:
    """
    Analyses chimiques des échantillons — table qualite_echantillons.
    Couvre : teneurs Al2O3, SiO2, Fe2O3, résultats labo, par zone.
    """
    kw_ech = any(w in ql for w in [
        "echantillon", "echantillons", "teneur", "al2o3", "alumine", "sio2", "silice",
        "fe2o3", "fer", "analyse labo", "analyse chimique", "analyses chimiques",
        "analyse chimique", "labo", "laboratoire",
        "resultat labo", "resultat analyse", "resultats analyse", "resultats labo",
        "resultats analyses", "echantillonnage",
        "qualite echantillon", "qualite bauxite", "qualite minerai",
        "stock dso", "teneur al", "teneur si", "teneur fe",
        "poids echantillon", "id ech",
    ])
    if not kw_ech:
        return None
    if not _table_exists(con, _QUAL_ECH_TABLE):
        return None

    lbl = _label(year, None, None, None)
    w_parts: list[str] = []
    if year:
        w_parts.append(f'YEAR("{_QUAL_ECH_DATE}") = {year}')
    where = ("WHERE " + " AND ".join(w_parts)) if w_parts else ""

    # Déterminer les colonnes teneurs demandées
    wants_al  = any(w in ql for w in ["al2o3", "alumine", "al"])
    wants_si  = any(w in ql for w in ["sio2", "silice", "si"])
    wants_fe  = any(w in ql for w in ["fe2o3", "fer", "fe"])
    wants_all = not (wants_al or wants_si or wants_fe)

    # Par zone
    wants_zone = any(w in ql for w in ["par zone", "zone", "par stock", "par lot"])
    if wants_zone:
        sel_cols = []
        if wants_al or wants_all:
            sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_AL2O3}"), 2) AS "Al2O3 moy (%)"')
        if wants_si or wants_all:
            sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_SIO2}"), 2) AS "SiO2 moy (%)"')
        if wants_fe or wants_all:
            sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_FE2O3}"), 2) AS "Fe2O3 moy (%)"')
        sel_cols.append(f'COUNT(*) AS "Nb éch."')
        zone_filter = f'"{_QUAL_ECH_ZONE}" IS NOT NULL'
        w_zone = _ext(where, zone_filter)
        df = _q(con, f"""
            SELECT "{_QUAL_ECH_ZONE}" AS "Zone", {", ".join(sel_cols)}
            FROM {_QUAL_ECH_TABLE} {w_zone}
            GROUP BY 1 ORDER BY 1
        """)
        if df.empty:
            return _no_data(_QUAL_ECH_TABLE, lbl, year=year, con=con)
        rows = [tuple(str(v) for v in row) for row in df.itertuples(index=False)]
        return (_fmt_table(f"Qualité échantillons par zone ({lbl})", rows, list(df.columns))
                + f"\n\n_📋 {_QUAL_ECH_TABLE}_")

    # Moyennes générales
    sel_cols = []
    labels_h = []
    if wants_al or wants_all:
        sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_AL2O3}"), 2) AS al2o3')
        labels_h.append("Al2O3 moy (%)")
    if wants_si or wants_all:
        sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_SIO2}"), 2) AS sio2')
        labels_h.append("SiO2 moy (%)")
    if wants_fe or wants_all:
        sel_cols.append(f'ROUND(AVG("{_QUAL_ECH_FE2O3}"), 2) AS fe2o3')
        labels_h.append("Fe2O3 moy (%)")
    sel_cols.append(f'COUNT(*) AS nb')
    labels_h.append("Nb éch.")

    row = con.execute(
        f'SELECT {", ".join(sel_cols)} FROM {_QUAL_ECH_TABLE} {where}'
    ).fetchone()
    if not row or row[-1] == 0:
        return _no_data(_QUAL_ECH_TABLE, lbl, year=year, con=con)

    lines = [f"Qualité échantillons ({lbl}) — {row[-1]} échantillons :"]
    for i, lh in enumerate(labels_h[:-1]):
        v = row[i]
        lines.append(f"  {lh} : {v:.2f}%" if v is not None else f"  {lh} : N/D")
    return "\n".join(lines) + f"\n\n_📋 {_QUAL_ECH_TABLE}_"


def handle_zones(con, ql: str, year) -> str | None:
    if not any(w in ql for w in ["zone", "stock", "stockage", "depot"]):
        return None
    w = _where(year=year)
    wants_top = any(w in ql for w in ["top", "plus", "meilleur", "classement"])
    n = 10
    m = re.search(r"\b(\d+)\b", ql)
    if m and wants_top:
        n = int(m.group(1))
    lbl = _label(year, None, None, None, None)

    wz = _ext(w, f'"{COL["zone"]}" IS NOT NULL')
    if wants_top:
        df = _q(con, f"""
            SELECT "{COL['zone']}", SUM("{COL['qty']}") as tonnage
            FROM {TABLE} {wz}
            GROUP BY 1 ORDER BY 2 DESC LIMIT {n}
        """)
        rows = [(r[COL['zone']], f"{r.tonnage:,.0f} T") for _, r in df.iterrows()]
        return _fmt_table(f"Top {n} zones de stockage ({lbl})", rows, ["Zone", "Tonnage"])

    df = _q(con, f"""
        SELECT "{COL['zone']}", SUM("{COL['qty']}") as tonnage
        FROM {TABLE} {wz}
        GROUP BY 1 ORDER BY 2 DESC
    """)
    rows = [(r[COL['zone']], f"{r.tonnage:,.0f} T") for _, r in df.iterrows()]
    return _fmt_table(f"Zones de stockage ({lbl})", rows, ["Zone", "Tonnage"])


def handle_carburant(con, ql: str, year, months=None, quarter=None,
                     semester=None) -> str | None:
    """Consommation carburant — table carburant_citerne (Petro Ivoire)."""
    kw_fuel = any(w in ql for w in [
        "carburant", "gasoil", "diesel", "consomm", "citerne",
        "petro ivoire", "iveqi", "litre", "depotage", "approvisionnement",
    ])
    if not kw_fuel:
        return None
    # N'exclure que les vraies questions de pannes (ex: "panne de carburant")
    # "bilan carburant" ou "rapport carburant" restent dans ce handler
    if any(w in ql for w in ["panne", "incident"]) and \
       not any(w in ql for w in ["consomm", "litre", "par mois", "par engin", "servi",
                                  "citerne", "petro", "iveqi", "depotage"]):
        return None

    # Filtre de base : lignes de consommation uniquement (pas les dépotages)
    base = (f'"{CARB_QTY}" IS NOT NULL AND '
            f'UPPER(TRIM("{CARB_ENGIN}")) != \'DEPOTAGE\'')

    # Filtre temporel
    w_parts = [base]
    if year:
        w_parts.append(f'YEAR("{CARB_DATE}") = {year}')
        if semester:
            sm = {1:[1,2,3,4,5,6], 2:[7,8,9,10,11,12]}[semester]
            w_parts.append(f'MONTH("{CARB_DATE}") IN ({",".join(map(str,sm))})')
        elif quarter:
            qm = {1:[1,2,3],2:[4,5,6],3:[7,8,9],4:[10,11,12]}[quarter]
            w_parts.append(f'MONTH("{CARB_DATE}") IN ({",".join(map(str,qm))})')
        elif months and len(months) == 1:
            w_parts.append(f'MONTH("{CARB_DATE}") = {months[0]}')
    carb_w = "WHERE " + " AND ".join(w_parts)

    lbl = _label(year, months[0] if months and len(months)==1 else None, quarter, semester)
    wants_monthly  = any(w in ql for w in ["par mois", "mensuel", "mensuelle"])
    wants_by_engin = any(w in ql for w in ["par engin", "par machine", "par tombereau",
                                            "par chargeuse", "par type", "par vehicule",
                                            "quelle machine", "quel engin",
                                            "chaque engin", "chaque machine"])
    wants_depot    = any(w in ql for w in ["depotage", "approvisionnement", "recharge", "ravitaillement"])

    # Approvisionnement citerne (depotage)
    if wants_depot:
        wd = f'WHERE "{CARB_DEPOT}" IS NOT NULL AND "{CARB_DEPOT}" > 0'
        if year:
            wd += f' AND YEAR("{CARB_DATE}") = {year}'
        val_d = con.execute(f'SELECT SUM("{CARB_DEPOT}") FROM {CARB_TABLE} {wd}').fetchone()[0] or 0
        return f"Approvisionnement citerne ({lbl}) : {val_d:,.0f} L\n_📋 {CARB_TABLE}_"

    # Répartition par engin
    if wants_by_engin:
        df = _q(con, f"""
            SELECT "{CARB_ENGIN}" AS engin, SUM("{CARB_QTY}") AS litres
            FROM {CARB_TABLE} {carb_w}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return f"Aucune donnée carburant pour {lbl}.\n_📋 {CARB_TABLE} · Petro Ivoire / Iveqi_"
        rows = [(r['engin'], f"{r.litres:,.0f} L") for _, r in df.iterrows()]
        return (_fmt_table(f"Carburant servi par engin ({lbl})", rows, ["Engin", "Litres"])
                + f"\n_📋 {CARB_TABLE} · Petro Ivoire / Iveqi_")

    # Ventilation mensuelle
    if wants_monthly and year:
        rows = con.execute(f"""
            SELECT MONTH("{CARB_DATE}") AS m, SUM("{CARB_QTY}") AS litres
            FROM {CARB_TABLE} {carb_w}
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        if not rows:
            return _no_data(CARB_TABLE, lbl, year=year, con=con,
                            extra_hint="Essayez sans filtre engin : *Carburant par mois en 2024*")
        return (_fmt_monthly(f"Carburant consommé mensuel {year} (Litres)", rows)
                + f"\n_📋 {CARB_TABLE} · Petro Ivoire / Iveqi_")

    # Scalaire
    val = con.execute(f'SELECT SUM("{CARB_QTY}") FROM {CARB_TABLE} {carb_w}').fetchone()[0] or 0
    if val == 0:
        return _no_data(CARB_TABLE, lbl, year=year, con=con)
    return (f"Carburant consommé ({lbl}) : {val:,.0f} L"
            f"\n_📋 {CARB_TABLE} · source : Petro Ivoire (Quantité Servie)_")


# Catégories spécifiques (priorité décroissante) — utilisées pour :
#   1. La détection de mot-clé dans handle_observations
#   2. Le bilan par catégorie (CASE WHEN exclusif, "Autres" en fallback)
_SPECIFIC_CATEGORIES: dict[str, list[str]] = {
    "Direction":        ["direction"],
    "Pneu / Crevaison": ["pneu", "crevaison"],
    "Pluie":            ["pluie", "pluvieux", "pluvieuse"],
    "Carburant":        ["carburant", "gasoil"],
    "Flexible":         ["flexible"],
    "Climatisation":    ["climatisation", "clim"],
    "Piste":            ["piste"],
}

# Alias pour la détection de mot-clé spécifique dans handle_observations
_OBS_KEYWORDS = _SPECIFIC_CATEGORIES


def handle_observations(con, ql: str, year) -> str | None:
    has_panne_kw = any(w in ql for w in ["panne", "incident", "observation", "probleme"])
    # "bilan" déclenche les pannes uniquement combiné avec "panne"/"incident"
    kw_panne = has_panne_kw or ("bilan" in ql and any(w in ql for w in ["panne", "incident", "obs"]))
    kw_count = any(w in ql for w in ["combien", "nombre", "total", "compter"])

    found_kw = next((cat for cat, vs in _OBS_KEYWORDS.items() if any(v in ql for v in vs)), None)

    if not kw_panne and not found_kw:
        return None

    # Ne pas voler les questions de consommation carburant à handle_carburant
    if found_kw == "Carburant" and not has_panne_kw and any(
        w in ql for w in ["consomm", "litre", "citerne", "petro", "iveqi",
                           "par mois", "par engin", "depotage", "approvisionnement"]
    ):
        return None

    lbl = _label(year, None, None, None, None)

    if found_kw:
        variants = _OBS_KEYWORDS[found_kw]
        like_clauses = " OR ".join(f"LOWER(\"{COL['obs']}\") LIKE '%{v}%'" for v in variants)
        w = _ext(
            _where(year=year),
            f'({like_clauses})',
            f'"{COL["obs"]}" IS NOT NULL',
        )
        if kw_count or "combien" in ql:
            nb = _scalar(con, f"SELECT COUNT(*) FROM {TABLE} {w}")
            return f"Occurrences '{found_kw}' ({lbl}) : {nb}"
        df = _q(con, f"""
            SELECT {COL['date']}, "{COL['engin']}", "{COL['qty']}", "{COL['obs']}"
            FROM {TABLE} {w} ORDER BY {COL['date']} DESC LIMIT 20
        """)
        return _fmt_observations_df(f"Observations '{found_kw}' ({lbl})", df)

    if kw_count:
        w = _ext(_where(year=year), f'"{COL["obs"]}" IS NOT NULL', f"TRIM(\"{COL['obs']}\") != ''")
        nb = _scalar(con, f"SELECT COUNT(*) FROM {TABLE} {w}")
        return f"Nombre total d'observations / pannes ({lbl}) : {nb}"

    # Bilan par catégorie — CASE WHEN exclusif → les catégories ne se chevauchent pas
    obs_col = f'LOWER("{COL["obs"]}")'

    # Filtre : ne compter que les lignes contenant un mot-clé panne
    all_kws = ["panne", "incident"] + [k for kws in _SPECIFIC_CATEGORIES.values() for k in kws]
    panne_filter = " OR ".join(f"{obs_col} LIKE '%{k}%'" for k in all_kws)
    w_base = _ext(_where(year=year), f'({panne_filter})', f'"{COL["obs"]}" IS NOT NULL')

    # Expression CASE exclusive : première catégorie correspondante gagne
    when_parts = "\n        ".join(
        "WHEN " + " OR ".join(f"{obs_col} LIKE '%{k}%'" for k in kws) + f" THEN '{cat}'"
        for cat, kws in _SPECIFIC_CATEGORIES.items()
    )
    case_expr = f"CASE\n        {when_parts}\n        ELSE 'Panne générique'\n    END"

    df_bilan = _q(con, f"""
        SELECT {case_expr} AS categorie, COUNT(*) AS nb
        FROM {TABLE} {w_base}
        GROUP BY 1 ORDER BY 2 DESC
    """)
    if df_bilan.empty:
        return _no_data(TABLE, lbl, year=year, con=con,
                        extra_hint="Vérifiez que le fichier DESCENTE MINERAI.xlsx est bien chargé")
    total = int(df_bilan["nb"].sum())
    lines = [f"  {row['categorie']:<22} : {int(row['nb']):>5}" for _, row in df_bilan.iterrows()]
    lines.append(f"  {'─' * 30}")
    lines.append(f"  {'TOTAL':<22} : {total:>5}")
    return f"Bilan des pannes ({lbl}) :\n" + "\n".join(lines)


def _fmt_observations_df(title: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"{title} : aucun résultat."
    lines = [f"{title} ({len(df)} lignes) :"]
    for _, row in df.iterrows():
        date = row.iloc[0]
        d = date.strftime("%d/%m/%Y") if pd.notna(date) else "?"
        engin = str(row.iloc[1] or "?")
        qty = row.iloc[2]
        q = f"{qty:,.0f} T" if pd.notna(qty) else "-"
        obs = str(row.iloc[3] or "").strip()[:80]
        lines.append(f"  {d} | {engin} | {q} | {obs}")
    return "\n".join(lines)


def handle_tonnage_par_voyage(con, ql: str, year) -> str | None:
    kw = ["tonnage par voyage", "tonne par voyage", "tonnage/voyage",
          "par voyage", "t/voyage", "tonnage voyage"]
    if not any(k in ql for k in kw):
        return None
    wt = _ext(_where(year=year), f'"{COL["tv"]}" IS NOT NULL')
    wt_pos = _ext(_where(year=year), f'"{COL["tv"]}" > 0')
    df = _q(con, f'SELECT DISTINCT "{COL["tv"]}" FROM {TABLE} {wt} ORDER BY 1')
    avg = _scalar(con, f'SELECT AVG("{COL["tv"]}") FROM {TABLE} {wt_pos}')
    lbl = _label(year, None, None, None, None)
    vals = [str(int(v)) if v == int(v) else str(v) for v in df.iloc[:, 0]]
    return (
        f"Tonnage par voyage ({lbl}) :\n"
        f"  Valeurs possibles : {', '.join(vals)}\n"
        f"  Moyenne (hors 0)  : {avg:,.2f} T/voyage"
    ) if avg else f"Valeurs de tonnage/voyage : {', '.join(vals)}"


# ── Constantes tables secondaires ───────────────────────────────────────────
JOURNAL_TABLE        = "journal"
JOURNAL_COL_ENGIN    = "Equipement"
JOURNAL_ENGIN_DEFAUT = "TRENCHER TRS N°296"

SHIFTS_TABLE        = "shifts_horaires"
PERSONNEL_TABLE      = "personnel"
SHIFTS_PERS_TABLE    = "shifts_personnel"
SHIFTS_COL_ENGIN    = "Equipement"
SHIFTS_ENGIN_DEFAUT = "TRENCHER TRS N°296"


def _table_exists(con, table: str) -> bool:
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        return table in tables
    except Exception:
        return False


def _col_names(con, table: str) -> list[str]:
    try:
        return [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    except Exception:
        return []


def _col_info(con, table: str) -> dict[str, str]:
    """Retourne {nom_colonne: type_colonne} pour une table."""
    try:
        rows = con.execute(f"DESCRIBE {table}").fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _find_col(cols: list[str], *keywords: str) -> str | None:
    """Retourne le premier nom de colonne dont le nom (minuscule) contient un des keywords."""
    for kw in keywords:
        for c in cols:
            if kw in c.lower():
                return c
    return None


def _find_heure_expr(col_info: dict[str, str],
                     prefer: str | None = None) -> tuple[str | None, str | None]:
    """
    Trouve (col_name, sql_expr) pour calculer les heures depuis un schéma de table.
    sql_expr produit un FLOAT (heures décimales) pour SUM().

    prefer : 'tambour' | 'moteur' | None
      Si renseigné, cherche d'abord la colonne correspondant à ce type.

    Priorité par défaut :
    1. TIMESTAMP 'heure moteur' (sans 'total') → HOUR() + MINUTE()/60
    2. TIMESTAMP 'heure tambour' (sans 'total') → HOUR() + MINUTE()/60
    3. Diff timestamps début/fin excavation
    4. Colonne NUMERIC avec 'heure'/'hm'/'duree'/'temps' (pas 'total')
    """
    def _ts_expr(c: str) -> tuple[str, str]:
        return c, f'(HOUR("{c}") + MINUTE("{c}") / 60.0)'

    # Préférence explicite (ex: "tambour" ou "moteur" dans la question)
    if prefer:
        for c, t in col_info.items():
            cl = c.lower()
            if prefer in cl and "total" not in cl and "heure" in cl and "TIMESTAMP" in t.upper():
                return _ts_expr(c)

    # 1. Heure moteur per-shift
    for c, t in col_info.items():
        cl = c.lower()
        if "moteur" in cl and "total" not in cl and "heure" in cl and "TIMESTAMP" in t.upper():
            return _ts_expr(c)

    # 2. Heure tambour per-shift
    for c, t in col_info.items():
        cl = c.lower()
        if "tambour" in cl and "total" not in cl and "heure" in cl and "TIMESTAMP" in t.upper():
            return _ts_expr(c)

    # 3. Différence timestamps début/fin excavation
    col_debut = next((c for c in col_info if "debut" in c.lower() and "excav" in c.lower()), None)
    col_fin   = next((c for c in col_info if "fin" in c.lower() and "excav" in c.lower()), None)
    if col_debut and col_fin:
        return col_fin, (
            f'(EPOCH(TRY_CAST("{col_fin}" AS TIMESTAMP)'
            f' - TRY_CAST("{col_debut}" AS TIMESTAMP)) / 3600.0)'
        )

    # 4. Colonne NUMERIC avec mots-clés heures (pas total, pas timestamp)
    for c, t in col_info.items():
        cl, typ = c.lower(), t.upper()
        if any(kw in cl for kw in ("heure", "hm", "duree", "temps", "hour")):
            if "total" not in cl and any(tp in typ for tp in ("DOUBLE", "FLOAT", "INTEGER", "DECIMAL", "BIGINT")):
                return c, f'"{c}"'

    return None, None


def handle_personnel(con, ql: str, year=None) -> str | None:
    """
    Personnel de la mine — tables personnel (Métier/Nom) et shifts_personnel (Opérateur/Shift).

    Couvre :
    - Liste des employés avec métier
    - Recherche par nom ou métier
    - Opérateurs par shift / date
    - Effectif total
    """
    _PERS_KW = [
        "employe", "employes", "personnel", "effectif", "equipe", "equipes",
        "metier", "metiers", "poste", "postes", "fonction", "corps de metier",
        "qui travaille", "qui travaillent", "operateur", "operateurs",
        "travailleur", "travailleurs", "liste des employes", "liste du personnel",
        "superviseur", "superviseurs", "agent", "agents",
    ]
    if not any(w in ql for w in _PERS_KW):
        return None
    # Exclure les questions sur les responsables de site (descente_minerai)
    if any(w in ql for w in ["responsable site", "responsable du site", "chef de site"]):
        return None

    # ── Table personnel (Métier, Nom) ────────────────────────────────────────
    has_personnel = _table_exists(con, PERSONNEL_TABLE)
    has_shifts_p  = _table_exists(con, SHIFTS_PERS_TABLE)

    # Recherche individuelle : "métier de Agnero Liliane" / "poste de Armand"
    name_match = re.search(
        r"(?:metier|poste|fonction|travail(?:le)?|qui est)\s+(?:de|du|pour|d[eu])\s+([A-Za-zÀ-ÿ\s]{3,30})",
        ql, re.I
    )
    if name_match and has_personnel:
        search_name = re.sub(r"[\"';\\%_\[\]]", "", name_match.group(1).strip().split()[0])
        if not search_name:
            return None
        df = _q(con, f"""
            SELECT "Nom", "Métier" FROM {PERSONNEL_TABLE}
            WHERE LOWER("Nom") LIKE LOWER('%{search_name}%')
               OR (LOWER("Métier") LIKE LOWER('%{search_name}%') AND LENGTH('{search_name}') > 4)
            ORDER BY "Nom" LIMIT 10
        """)
        if not df.empty:
            lines = [f"Personnel correspondant à « {search_name} » :"]
            for _, r in df.iterrows():
                metier = r.get("Métier", "N/D") or "N/D"
                lines.append(f"  • {r['Nom']} — {metier}")
            return "\n".join(lines) + f"\n\n_📋 {PERSONNEL_TABLE}_"

    # Corps de métier / par catégorie
    wants_by_metier = any(w in ql for w in [
        "par metier", "par categorie", "corps de metier", "par poste",
        "quels metiers", "quels postes", "liste des metiers",
    ])
    if wants_by_metier and has_personnel:
        df = _q(con, f"""
            SELECT "Métier", COUNT(*) AS "Nb employés"
            FROM {PERSONNEL_TABLE}
            WHERE "Métier" IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if not df.empty:
            rows = [(r["Métier"], str(int(r["Nb employés"]))) for _, r in df.iterrows()]
            return (_fmt_table("Personnel par métier", rows, ["Métier", "Nb"])
                    + f"\n\n_📋 {PERSONNEL_TABLE}_")

    # Opérateurs par shift (shifts_personnel)
    wants_shift = any(w in ql for w in ["shift", "vacation", "par shift", "heure d arrivee"])
    if wants_shift and has_shifts_p:
        w_parts = ['"Opérateur" IS NOT NULL']
        if year:
            w_parts.append(f'YEAR("Date") = {year}')
        where = "WHERE " + " AND ".join(w_parts)
        lbl = str(year) if year else "toutes périodes"
        df = _q(con, f"""
            SELECT "Shift", COUNT(DISTINCT "Opérateur") AS "Nb opérateurs"
            FROM {SHIFTS_PERS_TABLE} {where}
            GROUP BY 1 ORDER BY 1
        """)
        if not df.empty:
            rows = [(f"Shift {int(r['Shift'])}", str(int(r["Nb opérateurs"]))) for _, r in df.iterrows()]
            return (_fmt_table(f"Opérateurs par shift ({lbl})", rows, ["Shift", "Nb opérateurs"])
                    + f"\n\n_📋 {SHIFTS_PERS_TABLE}_")

    # Liste complète du personnel
    if has_personnel:
        df = _q(con, f"""
            SELECT "Métier", "Nom"
            FROM {PERSONNEL_TABLE}
            WHERE "Nom" IS NOT NULL
            ORDER BY "Métier", "Nom"
        """)
        if df.empty:
            return _no_data(PERSONNEL_TABLE, "personnel", con=con)
        total = len(df)
        lines = [f"Personnel de la mine ({total} personnes) :"]
        cur_metier = None
        for _, r in df.iterrows():
            m = r.get("Métier") or "—"
            if m != cur_metier:
                lines.append(f"\n  [{m}]")
                cur_metier = m
            lines.append(f"    • {r['Nom']}")
        return "\n".join(lines) + f"\n\n_📋 {PERSONNEL_TABLE}_"

    # Fallback : opérateurs depuis shifts_personnel
    if has_shifts_p:
        df = _q(con, f"""
            SELECT DISTINCT "Opérateur" FROM {SHIFTS_PERS_TABLE}
            WHERE "Opérateur" IS NOT NULL ORDER BY 1
        """)
        if not df.empty:
            ops = df["Opérateur"].tolist()
            return (_fmt_list(f"Opérateurs ({len(ops)})", ops)
                    + f"\n\n_📋 {SHIFTS_PERS_TABLE}_")

    return None


def handle_journal(con, ql: str, year) -> str | None:
    """
    Pannes de la trencher (et engins lourds) — table 'journal'.

    Colonne clé : Equipement (défaut : TRENCHER TRS N°296 si non précisé).
    Seules les questions contenant des mots-clés spécifiques aux engins lourds
    ou à la trencher activent ce handler ; les pannes tombereaux restent dans
    handle_observations() (descente_minerai.OBSERVATION).
    """
    kw_trig = any(w in ql for w in [
        "trencher", "trs", "journal", "pelle", "foreuse", "bouteur",
        "engin lourd", "liebherr", "komatsu", "hm ", "heure moteur",
        "arret technique", "arrets techniques", "arret engin",
        "breakdown", "maintenance trencher", "incident engin",
        "panne gps", "gps", "panne mecanique", "panne hydraulique",
        "panne electrique", "panne moteur",
    ])
    if not kw_trig:
        return None
    # Ne pas intercepter les heures machine / shifts
    if any(w in ql for w in ["heure machine", "heures machine", "shift", "vacation",
                              "disponibilite engin", "taux disponibilite"]):
        return None
    # Ne pas intercepter les questions carburant/fuel même si "trencher" est présent
    if any(w in ql for w in ["carburant", "gasoil", "diesel", "fuel", "litre",
                              "depotage", "consomm", "citerne"]):
        return None
    if not _table_exists(con, JOURNAL_TABLE):
        return None

    cols     = _col_names(con, JOURNAL_TABLE)
    col_date = _find_col(cols, "date", "jour")
    col_type = _find_col(cols, "type", "categorie", "nature", "panne", "incident")
    col_obs  = _find_col(cols, "observation", "commentaire", "description", "detail")

    # Équipement ciblé : détecter un numéro TRS spécifique ou utiliser le défaut
    engin_cible = JOURNAL_ENGIN_DEFAUT
    m_trs = re.search(r"trs\s*n?°?\s*(\d+)", ql, re.I)
    if m_trs:
        engin_cible = f"TRENCHER TRS N°{m_trs.group(1)}"
    elif any(w in ql for w in ["pelle", "foreuse", "bouteur", "liebherr"]):
        engin_cible = None  # tous les engins
    elif any(w in ql for w in ["tous les engins", "tout engin", "par engin", "toutes pannes"]):
        engin_cible = None  # pas de filtre engin

    lbl = _label(year, None, None, None)

    # Construction de la clause WHERE
    w_parts: list[str] = []
    if year and col_date:
        w_parts.append(f'YEAR("{col_date}") = {year}')
    if engin_cible:
        w_parts.append(f'"{JOURNAL_COL_ENGIN}" = \'{engin_cible}\'')
    where = ("WHERE " + " AND ".join(w_parts)) if w_parts else ""

    engin_label = f" — {engin_cible}" if engin_cible else ""

    wants_count  = any(w in ql for w in ["combien", "nombre", "bilan", "total"])
    wants_detail = any(w in ql for w in ["liste", "detail", "quelles", "quels", "derniere", "recente"])

    # Bilan par type de panne
    if wants_count and col_type:
        w2 = _ext(where, f'"{col_type}" IS NOT NULL')
        df = _q(con, f"""
            SELECT "{col_type}" AS type_panne, COUNT(*) AS nb
            FROM {JOURNAL_TABLE} {w2}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 15
        """)
        if not df.empty:
            total = int(df["nb"].sum())
            rows  = [(r["type_panne"], str(int(r["nb"]))) for _, r in df.iterrows()]
            out   = _fmt_table(
                f"Pannes{engin_label} ({lbl})", rows, ["Type panne", "Nb"]
            )
            return f"{out}\n  TOTAL : {total}\n\n_📋 {JOURNAL_TABLE}_"

    # Détail des dernières occurrences
    if wants_detail and col_date:
        df = _q(con, f"""
            SELECT "{col_date}" AS date_j, "{JOURNAL_COL_ENGIN}" AS engin
                   {f', "{col_type}" AS type_panne' if col_type else ""}
                   {f', "{col_obs}"[:80] AS obs' if col_obs else ""}
            FROM {JOURNAL_TABLE} {where}
            ORDER BY "{col_date}" DESC LIMIT 20
        """)
        if not df.empty:
            lines = [f"Dernières entrées journal{engin_label} ({lbl}) :"]
            for _, r in df.iterrows():
                d = str(r["date_j"])[:10]
                typ = f" | {r['type_panne']}" if "type_panne" in r.index and pd.notna(r.get("type_panne")) else ""
                o   = f" | {str(r['obs'])[:60]}" if "obs" in r.index and pd.notna(r.get("obs")) else ""
                lines.append(f"  {d} | {r['engin']}{typ}{o}")
            return "\n".join(lines) + f"\n\n_📋 {JOURNAL_TABLE}_"

    # Résumé scalaire : nombre total d'entrées
    try:
        nb = _scalar(con, f"SELECT COUNT(*) FROM {JOURNAL_TABLE} {where}")
    except Exception:
        nb = 0
    if nb == 0:
        # Fallback : Equipement souvent NULL (2024-2025) → réessayer sans filtre engin
        if engin_cible:
            w_fallback_parts = [p for p in w_parts if JOURNAL_COL_ENGIN not in p]
            where_fb = ("WHERE " + " AND ".join(w_fallback_parts)) if w_fallback_parts else ""
            try:
                nb_fb = _scalar(con, f"SELECT COUNT(*) FROM {JOURNAL_TABLE} {where_fb}")
            except Exception:
                nb_fb = 0
            if nb_fb > 0:
                where = where_fb
                nb = nb_fb
                engin_label = ""  # plus de filtre engin
            else:
                return f"Aucune donnée dans le journal{engin_label} pour {lbl}."
        else:
            return f"Aucune donnée dans le journal pour {lbl}."

    # Si col_type disponible : mini-bilan automatique
    if col_type:
        w2 = _ext(where, f'"{col_type}" IS NOT NULL')
        df = _q(con, f"""
            SELECT "{col_type}" AS type_panne, COUNT(*) AS nb
            FROM {JOURNAL_TABLE} {w2}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """)
        if not df.empty:
            rows = [(r["type_panne"], str(int(r["nb"]))) for _, r in df.iterrows()]
            out  = _fmt_table(
                f"Journal{engin_label} ({lbl}) — {nb} entrées", rows, ["Type", "Nb"]
            )
            return f"{out}\n\n_📋 {JOURNAL_TABLE}_"

    return f"Journal{engin_label} ({lbl}) : {nb} entrées.\n\n_📋 {JOURNAL_TABLE}_"


def handle_shifts_horaires(con, ql: str, year, months=None, quarter=None,
                            semester=None) -> str | None:
    """
    Heures machine par équipement — table 'shifts_horaires'.

    Détecte automatiquement le schéma de la table via _find_heure_expr().
    Par défaut : agrège TOUS les équipements (pas de filtre par défaut).
    Filtre engin uniquement si l'utilisateur mentionne "trencher" ou "TRS XXX".
    """
    kw_shifts = any(w in ql for w in [
        "heure machine", "heures machine",
        "hm", "shift", "vacation",
        "poste de travail", "horaire",
        "disponibilite engin", "taux disponibilite",
        "disponibilite des engin",
        "temps travail", "temps de travail",
        # heures spécifiques par type (colonnes shifts_horaires)
        "tambour", "heure tambour", "heures tambour",
        "heure moteur", "heures moteur",
        "fonctionnement", "temps fonctionnement",
        "heure de marche", "heures de marche",
        "heure d'utilisation", "heures utilisation",
        "heure excavation", "heures excavation",
    ])
    if not kw_shifts:
        return None
    if any(w in ql for w in ["litre", "carburant", "gasoil", "depotage"]):
        return None
    if not _table_exists(con, SHIFTS_TABLE):
        return None

    ci        = _col_info(con, SHIFTS_TABLE)
    cols      = list(ci.keys())
    col_date  = _find_col(cols, "date", "jour", "periode")
    col_shift = _find_col(cols, "shift", "vacation", "poste", "equipe")
    # Préférer la colonne correspondant au type demandé (tambour / moteur)
    _heure_prefer = "tambour" if "tambour" in ql else ("moteur" if "moteur" in ql else None)
    col_heure, heure_expr = _find_heure_expr(ci, prefer=_heure_prefer)
    _heure_label = _heure_prefer if _heure_prefer else "machine"

    if not col_heure:
        return None  # schéma incompatible

    # Équipement ciblé — pas de filtre par défaut (agrège tout)
    engin_cible: str | None = None
    m_trs = re.search(r"trs\s*n?°?\s*(\d+)", ql, re.I)
    if m_trs:
        engin_cible = f"TRENCHER TRS N°{m_trs.group(1)}"
    elif "trencher" in ql and not any(w in ql for w in ["par engin", "chaque engin"]):
        engin_cible = SHIFTS_ENGIN_DEFAUT

    month = months[0] if months and len(months) == 1 else None
    lbl   = _label(year, month, quarter, semester)

    # Clause WHERE — inclut le filtre col_heure IS NOT NULL pour éviter les lignes vides
    w_parts: list[str] = [f'"{col_heure}" IS NOT NULL']
    if year and col_date:
        w_parts.append(f'YEAR("{col_date}") = {year}')
        if semester:
            sm = {1: [1,2,3,4,5,6], 2: [7,8,9,10,11,12]}[semester]
            w_parts.append(f'MONTH("{col_date}") IN ({",".join(map(str, sm))})')
        elif quarter:
            qm = {1:[1,2,3],2:[4,5,6],3:[7,8,9],4:[10,11,12]}[quarter]
            w_parts.append(f'MONTH("{col_date}") IN ({",".join(map(str, qm))})')
        elif month:
            w_parts.append(f'MONTH("{col_date}") = {month}')
    if engin_cible:
        w_parts.append(f'"{SHIFTS_COL_ENGIN}" = \'{engin_cible}\'')
    where = "WHERE " + " AND ".join(w_parts)

    engin_label = f" — {engin_cible}" if engin_cible else ""

    wants_monthly  = any(w in ql for w in ["par mois", "mensuel", "mensuelle"])
    wants_by_engin = any(w in ql for w in ["par engin", "par machine", "chaque engin"])
    wants_by_shift = col_shift and any(w in ql for w in ["shift", "vacation", "equipe", "poste"])

    # Annotation NULL engin si applicable
    _null_engin_ctx = _reg.null_context(SHIFTS_TABLE, SHIFTS_COL_ENGIN) or ""

    # Ventilation mensuelle
    if wants_monthly and year and col_date:
        df = _q(con, f"""
            SELECT MONTH("{col_date}") AS m, SUM({heure_expr}) AS heures
            FROM {SHIFTS_TABLE} {where}
            GROUP BY 1 ORDER BY 1
        """)
        if df.empty:
            return _no_data(SHIFTS_TABLE, lbl, year=year, con=con,
                            extra_hint="Essayez sans préciser d'engin : *Heures machine par mois en 2025*")
        result = _fmt_monthly(f"Heures {_heure_label}{engin_label} mensuel {year}", [
            (int(r.m), r.heures) for _, r in df.iterrows()
        ]) + f"\n\n_📋 {SHIFTS_TABLE}_"
        if not engin_cible and _null_engin_ctx:
            result += f"\n\n{_null_engin_ctx}"
        return result

    # Ventilation par engin
    if wants_by_engin:
        df = _q(con, f"""
            SELECT COALESCE("{SHIFTS_COL_ENGIN}", 'Non précisé') AS engin,
                   SUM({heure_expr}) AS heures
            FROM {SHIFTS_TABLE} {where}
            GROUP BY 1 ORDER BY 2 DESC
        """)
        if df.empty:
            return _no_data(SHIFTS_TABLE, lbl, year=year, con=con)
        rows = [(r["engin"], f"{r.heures:,.1f} h") for _, r in df.iterrows()]
        return (_fmt_table(f"Heures {_heure_label} par engin ({lbl})", rows, ["Engin", "Heures"])
                + f"\n\n_📋 {SHIFTS_TABLE}_")

    # Ventilation par shift/vacation
    if wants_by_shift:
        w2 = _ext(where, f'"{col_shift}" IS NOT NULL')
        df = _q(con, f"""
            SELECT "{col_shift}" AS shift, SUM({heure_expr}) AS heures
            FROM {SHIFTS_TABLE} {w2}
            GROUP BY 1 ORDER BY 1
        """)
        if not df.empty:
            rows = [(r["shift"], f"{r.heures:,.1f} h") for _, r in df.iterrows()]
            return (_fmt_table(f"Heures {_heure_label}{engin_label} par shift ({lbl})", rows,
                               ["Shift", "Heures"])
                    + f"\n\n_📋 {SHIFTS_TABLE}_")

    # Scalaire total
    val = con.execute(f'SELECT SUM({heure_expr}) FROM {SHIFTS_TABLE} {where}').fetchone()[0] or 0
    if val == 0:
        # Fallback : vérifier si des données existent sans filtre équipement
        if engin_cible and col_date and year:
            w_all = "WHERE " + " AND ".join(
                p for p in w_parts if SHIFTS_COL_ENGIN not in p
            )
            val_all = con.execute(f'SELECT SUM({heure_expr}) FROM {SHIFTS_TABLE} {w_all}').fetchone()[0] or 0
            if val_all > 0:
                null_ctx = _reg.null_context(SHIFTS_TABLE, SHIFTS_COL_ENGIN) or ""
                return (
                    f"Aucun enregistrement pour **{engin_cible}** en {year}.\n"
                    + (f"{null_ctx}\n\n" if null_ctx else "")
                    + f"Total tous équipements ({lbl}) : **{val_all:,.1f} h**"
                    + f"\n\n_📋 {SHIFTS_TABLE}_"
                )
        return (_no_data(SHIFTS_TABLE, lbl, year=year, con=con,
                         extra_hint=f"Essayez sans préciser d'engin : *Heures {_heure_label} en 2025*")
                + f"\n\n_📋 {SHIFTS_TABLE}_")
    result = f"Heures {_heure_label}{engin_label} ({lbl}) : {val:,.1f} h\n\n_📋 {SHIFTS_TABLE}_"
    if not engin_cible and _null_engin_ctx:
        result += f"\n\n{_null_engin_ctx}"
    return result


def handle_metadata(con, ql: str) -> str | None:
    """Infos générales sur le dataset (années, tables, sites…)."""
    kw = [
        "annee disponible", "dates disponibles", "combien annee",
        "quelles annees", "quelle periode", "periode couverte",
        "donnees disponibles", "tables disponibles", "quelles donnees",
        "quelles tables", "que contient", "quel est le contenu",
    ]
    if not any(k in ql for k in kw):
        return None
    df = _q(con, f"SELECT DISTINCT YEAR({COL['date']}) as a FROM {TABLE} WHERE {COL['date']} IS NOT NULL ORDER BY 1")
    years = df["a"].dropna().astype(int).tolist()

    # Résumé enrichi depuis le registre de schémas
    registry_summary = _reg.list_tables_with_context(con)
    if registry_summary:
        lines = [
            f"Années de données principales ({len(years)}) : {', '.join(map(str, years))}",
            "",
            "Tables disponibles :",
            registry_summary,
        ]
    else:
        try:
            tables_list = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        except Exception:
            tables_list = []
        lines = [f"Années de données disponibles ({len(years)}) : {', '.join(map(str, years))}"]
        if tables_list:
            lines.append(f"Tables chargées ({len(tables_list)}) : {', '.join(sorted(tables_list))}")
    return "\n".join(lines)


# ── Handler générique (adaptation nouvelles tables) ─────────────────────────

# Tables couvertes par des handlers spécifiques — dérivé des constantes de tables
# définies en haut du fichier pour rester synchronisé automatiquement.
# dim_date = vue calendrier générée par connection.py, pas de handler mais à exclure.
_HANDLED_TABLES: frozenset[str] = frozenset(filter(None, [
    TABLE,            # descente_minerai
    EXC_TABLE,        # excavation
    TRANS_TABLE,      # transport_minerai_paa
    LOAD_TABLE,       # productivite_loading
    CARB_TABLE,       # carburant_citerne
    _QUAL_ECH_TABLE,  # qualite_echantillons
    JOURNAL_TABLE,    # journal
    SHIFTS_TABLE,     # shifts_horaires
    OBJ_TABLE,        # objectifs
    SHIFTS_PERS_TABLE,  # shifts_personnel
    PERSONNEL_TABLE,    # personnel
    "pges_actions",   # handle_suivi_actions gère les deux
    "suivi_actions",
    "dim_date",       # vue calendrier, pas de handler
]))


def handle_generic_table(con: duckdb.DuckDBPyConnection, ql: str,
                          year: int | None = None) -> str | None:
    """
    Handler générique schema-aware pour les tables non couvertes par un handler spécifique.

    Utilisé comme filet de sécurité quand une nouvelle table est chargée dans DuckDB
    sans qu'un handler dédié ait été écrit. Utilise le schema_registry pour :
      - détecter quelle table correspond à la question (mots-clés dans le nom de table)
      - identifier la colonne de quantité principale (rôle 'quantity' ou 'hours')
      - construire une requête SQL générique adaptée au schéma réel

    Conditions de déclenchement strictes pour éviter les faux-positifs.
    """
    try:
        all_tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return None

    # Chercher une table non couverte dont le nom apparaît dans la question
    candidate: str | None = None
    for tbl in all_tables:
        if tbl in _HANDLED_TABLES:
            continue
        # Normaliser le nom de table pour la comparaison (underscores → espaces)
        tbl_words = set(tbl.replace("_", " ").split())
        # Correspondance si ≥1 mot significatif (>3 chars) du nom de table apparaît
        # en tant que token complet dans la question (word boundary pour éviter les faux positifs)
        significant = [w for w in tbl_words if len(w) > 3]
        if significant and any(
            re.search(rf"\b{re.escape(w)}\b", ql, re.IGNORECASE) for w in significant
        ):
            candidate = tbl
            break

    if not candidate:
        return None

    # Construire le schéma de la table candidate
    schema = _reg.get_or_build(con, candidate)
    if not schema:
        return None

    ci       = schema.col_info
    col_date = schema.col("date")
    col_qty  = schema.col("quantity") or schema.col("hours")

    # Filtrage temporel
    where_parts: list[str] = []
    if year and col_date:
        where_parts.append(f'YEAR("{col_date}") = {year}')
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    lbl   = str(year) if year else "toutes périodes"

    # Ventilation mensuelle ou scalaire
    wants_monthly = "par mois" in ql or "mensuel" in ql

    if col_qty and col_date and wants_monthly and year:
        try:
            rows = con.execute(f"""
                SELECT MONTH("{col_date}") AS m, SUM("{col_qty}") AS val
                FROM "{candidate}" {where}
                GROUP BY 1 ORDER BY 1
            """).fetchall()
            if rows:
                return (_fmt_monthly(f"{col_qty} mensuel {year} [{candidate}]", rows)
                        + f"\n\n_📋 {candidate}_")
        except Exception:
            pass

    if col_qty:
        try:
            val = con.execute(
                f'SELECT SUM("{col_qty}") FROM "{candidate}" {where}'
            ).fetchone()[0]
            if val is not None:
                return (f"**{col_qty}** ({lbl}) : {val:,.2f}\n\n_📋 {candidate}_"
                        f"\n_ℹ️ Requête générique — table `{candidate}` non encore configurée._")
        except Exception:
            pass

    # Sans colonne de quantité : afficher le nombre de lignes
    try:
        nb = con.execute(f'SELECT COUNT(*) FROM "{candidate}" {where}').fetchone()[0]
        if nb and nb > 0:
            desc = schema.description()
            return (f"**{desc}** ({lbl}) : {nb:,} enregistrements\n\n_📋 {candidate}_"
                    f"\n_ℹ️ Table `{candidate}` disponible — demandez une colonne spécifique._")
    except Exception:
        pass

    return None


# ── Point d'entrée ──────────────────────────────────────────────────────────

def _handle_single(con: duckdb.DuckDBPyConnection, question: str) -> str | None:
    """
    Traite une seule question — appelé par handle() après découpage multi-requête.

    Fonctionnement :
    1. La question est normalisée (minuscules, accents supprimés, abréviations
       développées : "T1" → "trimestre 1", "S2" → "semestre 2"…).
    2. Les informations temporelles sont extraites (année, mois, trimestre…).
    3. Les handlers sont essayés dans l'ordre de priorité.
       Le premier qui reconnaît la question retourne une réponse.
    4. Si aucun handler ne correspond → retourne None, ce qui déclenche
       le fallback RAG+LLM dans query_router.py.

    Chaque handler correspond à un domaine métier :
        handle_compare_years    → "comparer 2024 et 2025"
        handle_per_year         → "tonnage par année"
        handle_tombereaux       → "combien de tombereaux ?"
        handle_responsable      → "qui est responsable du site ?"
        handle_transport        → "société de transport ?"
        handle_qualite          → "qualité du minerai ?"
        handle_observations     → "pannes, incidents, bilan"
        handle_tonnage_par_voyage → "tonnage par voyage ?"
        handle_zones            → "zones de stockage, top 10"
        handle_engins           → "top 5 engins"
        handle_metadata         → "quelles années disponibles ?"
        handle_tonnage          → tonnage/voyages (toutes granularités)
    """
    # Étape 1 : normalisation et expansion des abréviations
    q  = preprocess(question)   # ex: "T1 2026" → "trimestre 1 2026"
    ql = _normaliser(q)         # accents + synonymes miniers → formes canoniques

    # Étape 2 : extraction temporelle
    year          = _year(ql)
    months        = _months(ql)
    quarter       = _quarter(ql)
    semester      = _semester(ql)
    iso_range     = _iso_week_range(ql)
    iso_week      = _single_week(ql) if not iso_range else None
    specific_date = _specific_date(ql)

    # Étape 3 : cascade de handlers — le premier qui répond gagne
    handlers = [
        lambda: handle_compare_years(con, ql),
        lambda: handle_suivi_actions(con, ql),
        lambda: handle_objectifs(con, ql, year),
        lambda: handle_tonnage_excav(con, ql, year, months, quarter, semester, iso_week, iso_range, specific_date),
        lambda: handle_tonnage_transport(con, ql, year, months, quarter, semester, specific_date),
        lambda: handle_per_year(con, ql),
        lambda: handle_tombereaux(con, ql),
        lambda: handle_shifts_horaires(con, ql, year, months, quarter, semester),
        lambda: handle_personnel(con, ql, year),          # nouveau
        lambda: handle_qualite_echantillons(con, ql, year),  # nouveau (avant handle_qualite)
        lambda: handle_journal(con, ql, year),
        lambda: handle_responsable(con, ql, year),
        lambda: handle_transport(con, ql),
        lambda: handle_qualite(con, ql),
        lambda: handle_carburant(con, ql, year, months, quarter, semester),
        lambda: handle_observations(con, ql, year),
        lambda: handle_tonnage_par_voyage(con, ql, year),
        lambda: handle_zones(con, ql, year),
        lambda: handle_engins(con, ql, year, months),
        lambda: handle_metadata(con, ql),
        lambda: handle_tonnage(con, ql, year, months, quarter, semester, iso_week, iso_range, specific_date),
    ]
    _hlog = logging.getLogger(__name__)
    for h in handlers:
        try:
            result = h()
        except Exception as exc:
            _hlog.warning("handler error on %r: %s", question[:80], exc)
            continue   # structure de données inconnue → essayer le handler suivant
        if result is not None:
            return _src(result)

    # Dernier recours : handler générique intelligent (SmartGenericHandler)
    # Couvre les nouvelles tables non encore déclarées dans les handlers dédiés.
    # Retourne un GenericHandlerResult (questions de suivi + alertes) que la page
    # affiche de manière enrichie ; les appels multi-requêtes reçoivent le texte brut.
    from src.engine.generic_handler import handle_new_table as _handle_new
    result = _handle_new(con, ql, _HANDLED_TABLES, year)
    if result is not None:
        return result   # GenericHandlerResult — passé en transparence à la page

    # Aucun handler n'a reconnu la question → fallback vers RAG+LLM
    return None


def _src(text: str, table: str = TABLE) -> str:
    """Ajoute l'attribution de source. Ne ré-ajoute pas si déjà présente."""
    if "_📋" in text:
        return text
    return f"{text}\n\n_📋 {table}_"


def _split_queries(question: str) -> list[str]:
    """
    Sépare les questions multiples séparées par virgule.

    Ex: "Tonnage par mois en 2026, bilan des pannes en 2023"
        → ["Tonnage par mois en 2026", "bilan des pannes en 2023"]

    Ne sépare PAS si :
      - moins de 2 parties ≥ 15 chars
      - toutes les parties ne contiennent pas une année (20XX) — ex: "descendu, excavé et transporté"
    """
    parts = [p.strip() for p in re.split(r"\s*,\s*", question) if p.strip()]
    if (len(parts) >= 2
            and all(len(p) >= 15 for p in parts)
            and all(re.search(r"\b20\d{2}\b", p) for p in parts)):
        return parts
    return [question]


def handle(con: duckdb.DuckDBPyConnection, question: str):
    """
    Point d'entrée public — supporte les questions multiples séparées par virgule.

    Retourne :
      - str                  pour les handlers dédiés
      - GenericHandlerResult pour le handler générique (table non encore couverte)
      - None                 si aucun handler n'a répondu

    Ex: "Tonnage par mois en 2026, bilan des pannes en 2023"
    """
    from src.engine.generic_handler import GenericHandlerResult as _GHR
    parts = _split_queries(question)
    if len(parts) == 1:
        return _handle_single(con, question)

    # Multi-requête : extraire le texte de chaque résultat (GenericHandlerResult ou str)
    results = [_handle_single(con, p) for p in parts]
    valid   = [r.response if isinstance(r, _GHR) else r for r in results if r]
    if not valid:
        return None
    return "\n\n" + "\n\n─────────────────────\n\n".join(valid)
