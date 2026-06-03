"""
BI COPILOT INDUSTRIEL - v5
Python 3.10+ | LangChain + Ollama phi3:mini

Fusion v4-générique + v4-spécifique :
  - Architecture CATEGORICAL générique (detect_entities, _apply_filters, tonnage_by_dim)
  - Résolution floue des noms de colonnes au démarrage
  - Filtres composables multi-critères (site × produit × année × qualité × zone × ...)
  - Fonctions spécifiques conservées : engins_by_type, pannes_summary,
    voyages_month/year, voyages_by_zone
  - Validation LLM (_validate) avant exécution
  - Toutes les colonnes textuelles exploitables
"""

import pandas as pd
import numpy as np
import re
import json
import unicodedata
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from langchain_ollama import OllamaLLM

# ══════════════════════════════════════════════════════════════
# 1. LLM
# ══════════════════════════════════════════════════════════════

llm = OllamaLLM(model="phi3:mini", temperature=0, timeout=30)

# ══════════════════════════════════════════════════════════════
# 2. CHARGEMENT & NETTOYAGE DES DONNÉES
# ══════════════════════════════════════════════════════════════

FILE_PATH = Path(__file__).parent.parent / "data/clean/excel/DESCENTE MINERAI.csv"

df = None
for enc in ("cp1252", "utf-8", "latin-1"):
    try:
        df = pd.read_csv(FILE_PATH, encoding=enc, sep=";")
        break
    except (UnicodeDecodeError, Exception):
        continue

if df is None:
    raise RuntimeError(f"Impossible de lire {FILE_PATH}")
assert isinstance(df, pd.DataFrame)

df.columns = df.columns.str.strip()
df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
df = df.loc[:, df.columns != ""]

# --- Colonnes connues du domaine (avec résolution floue) -----
COLS = {
    "qty":         "QUANTITE JOURNALIERE DESCENDUE (T)",
    "truck":       "Code / Nom engin / Immatriculation",
    "site":        "Site",
    "date":        "DATE",
    "responsable": "Responsable site",
    "produit":     "Produit",
    "transport":   "SOCIETE DE TRANSPORT",
    "voyage":      "NOMBRE VOYAGE",
    "tonn_voy":    "TONNAGE / VOYAGE",
    "qualite":     "QUALITE",
    "zone":        "ZONE DE STOCKAGE",
    "observation": "OBSERVATION",
    "camion":      "N°CAMION",
}

def _resolve(name: str) -> str | None:
    if name in df.columns:
        return name
    close = get_close_matches(name, df.columns.tolist(), n=1, cutoff=0.7)
    return close[0] if close else None

for k, v in list(COLS.items()):
    resolved = _resolve(v)
    if resolved and resolved != v:
        COLS[k] = resolved

COL_QTY   = COLS["qty"]
COL_TRUCK = COLS["truck"]
COL_SITE  = COLS["site"]
COL_DATE  = COLS["date"]
COL_RESP  = COLS["responsable"]
COL_PROD  = COLS["produit"]
COL_TRANS = COLS["transport"]
COL_VOY   = COLS["voyage"]
COL_TV    = COLS["tonn_voy"]
COL_QUAL  = COLS["qualite"]
COL_ZONE  = COLS["zone"]
COL_OBS   = COLS["observation"]
COL_CAM   = COLS["camion"]

missing = [v for v in COLS.values() if v not in df.columns]
if missing:
    print(f"[AVERTISSEMENT] Colonnes absentes : {missing}")
    print(f"Colonnes disponibles : {list(df.columns)}")

# --- Nettoyage numérique ---
def clean_numeric(x):
    if pd.isna(x):
        return np.nan
    s = str(x).replace("\xa0", "").replace(" ", "").replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", "."):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan

for c in (COL_QTY, COL_VOY, COL_TV):
    if c in df.columns:
        df[c] = df[c].apply(clean_numeric)

# --- Nettoyage texte ---
for c in (COL_SITE, COL_RESP, COL_PROD, COL_TRANS, COL_QUAL,
          COL_ZONE, COL_CAM, COL_TRUCK, COL_OBS):
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({"nan": np.nan, "": np.nan, "NaN": np.nan})

# --- Ingénierie des dates ---
if COL_DATE in df.columns:
    df[COL_DATE]    = pd.to_datetime(df[COL_DATE], errors="coerce", dayfirst=True)
    df["MOIS"]      = df[COL_DATE].dt.month
    df["ANNEE"]     = df[COL_DATE].dt.year
    df["TRIMESTRE"] = df[COL_DATE].dt.quarter
    df["SEMAINE"]   = df[COL_DATE].dt.isocalendar().week.astype("Int64")
    df["SEMESTRE"]  = df[COL_DATE].dt.month.apply(
        lambda m: 1 if pd.notna(m) and m <= 6 else (2 if pd.notna(m) else np.nan)
    )

# --- Valeurs de référence ---
def _uniq(col):
    if col in df.columns:
        return sorted(df[col].dropna().unique().tolist())
    return []

SITES_DISPO        = _uniq(COL_SITE)
PRODUITS_DISPO     = _uniq(COL_PROD)
RESPONSABLES_DISPO = _uniq(COL_RESP)
TRANSPORTS_DISPO   = _uniq(COL_TRANS)
QUALITES_DISPO     = _uniq(COL_QUAL)
ZONES_DISPO        = _uniq(COL_ZONE)
CAMIONS_DISPO      = _uniq(COL_CAM)
TRUCKS_DISPO       = _uniq(COL_TRUCK)
TOMBEREAUX_DISPO   = [t for t in TRUCKS_DISPO if str(t).upper().startswith("TOMBEREAU")]
ANNEES_DISPO       = sorted(df["ANNEE"].dropna().unique().astype(int).tolist()) if "ANNEE" in df.columns else []
ANNEE_COURANTE     = datetime.now().year

CATEGORICAL = {
    "site":        (COL_SITE,  SITES_DISPO),
    "produit":     (COL_PROD,  PRODUITS_DISPO),
    "responsable": (COL_RESP,  RESPONSABLES_DISPO),
    "transport":   (COL_TRANS, TRANSPORTS_DISPO),
    "qualite":     (COL_QUAL,  QUALITES_DISPO),
    "zone":        (COL_ZONE,  ZONES_DISPO),
    "camion":      (COL_CAM,   CAMIONS_DISPO),
    "engin":       (COL_TRUCK, TRUCKS_DISPO),
}

DIM_SYNONYMS = {
    "site":        ["site", "sites", "mine", "exploitation"],
    "produit":     ["produit", "produits", "minerai", "minerais"],
    "responsable": ["responsable", "responsables", "chef", "superviseur", "manager"],
    "transport":   ["transport", "transporteur", "transporteurs", "societe de transport", "prestataire"],
    "qualite":     ["qualite", "qualites", "categorie", "grade"],
    "zone":        ["zone", "zones", "stock", "stockage", "depot"],
    "camion":      ["camion", "camions", "type de camion", "type engin"],
    "engin":       ["engin", "engins", "tombereau", "tombereaux", "vehicule", "immatriculation"],
}

# ══════════════════════════════════════════════════════════════
# 3. DICTIONNAIRES LINGUISTIQUES
# ══════════════════════════════════════════════════════════════

MOIS_FR: dict[str, int] = {
    "janvier": 1,  "jan": 1,
    "février": 2,  "fevrier": 2, "fev": 2,  "feb": 2,
    "mars": 3,     "mar": 3,
    "avril": 4,    "avr": 4,     "apr": 4,
    "mai": 5,
    "juin": 6,     "jun": 6,
    "juillet": 7,  "juil": 7,    "jul": 7,
    "août": 8,     "aout": 8,    "aou": 8,  "aug": 8,
    "septembre": 9, "sep": 9,   "sept": 9,
    "octobre": 10,  "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "dec": 12,
}

MOIS_NUM_TO_FR: dict[int, str] = {
    1: "Janvier", 2: "Février",   3: "Mars",     4: "Avril",
    5: "Mai",     6: "Juin",      7: "Juillet",  8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

TRIMESTRES: dict[int, list[int]] = {1: [1,2,3], 2: [4,5,6], 3: [7,8,9], 4: [10,11,12]}
SEMESTRES:  dict[int, list[int]] = {1: [1,2,3,4,5,6], 2: [7,8,9,10,11,12]}

# ══════════════════════════════════════════════════════════════
# 4. PRÉ-TRAITEMENT
# ══════════════════════════════════════════════════════════════

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(s))
        if unicodedata.category(c) != "Mn"
    )

ABBREV_MAP = [
    (r"\bS1\b", "semestre 1"), (r"\bS2\b", "semestre 2"),
    (r"\b1er\s+semestre\b", "semestre 1"), (r"\b2eme\s+semestre\b", "semestre 2"),
    (r"\b2ème\s+semestre\b", "semestre 2"),
    (r"\bT1\b", "trimestre 1"), (r"\bT2\b", "trimestre 2"),
    (r"\bT3\b", "trimestre 3"), (r"\bT4\b", "trimestre 4"),
    (r"\bQ1\b", "trimestre 1"), (r"\bQ2\b", "trimestre 2"),
    (r"\bQ3\b", "trimestre 3"), (r"\bQ4\b", "trimestre 4"),
    (r"\b1er\s+trimestre\b", "trimestre 1"), (r"\b2eme\s+trimestre\b", "trimestre 2"),
    (r"\b3eme\s+trimestre\b", "trimestre 3"), (r"\b4eme\s+trimestre\b", "trimestre 4"),
    (r"\bS(\d{1,2})\b", r"semaine \1"),
    (r"\bsem\.?\s*(\d{1,2})\b", r"semaine \1"),
    (r"\bcette\s+ann[ée]e\b", str(ANNEE_COURANTE)),
    (r"\bl.ann[ée]e\s+derni[eè]re\b", str(ANNEE_COURANTE - 1)),
    (r"\bce\s+mois\b", MOIS_NUM_TO_FR.get(datetime.now().month, "").lower()),
    (r"\bqt[eé]\b", "quantite"),
    (r"\btns?\b", "tonnage"),
    # Normalise "zone 4" → "stock 4" pour matcher les valeurs ZONE DE STOCKAGE
    (r"\bzone\s+(\d+)\b", r"stock \1"),
]

def preprocess(question: str) -> str:
    q = question.strip()
    for pattern, replacement in ABBREV_MAP:
        q = re.sub(pattern, replacement, q, flags=re.IGNORECASE)
    return q

# ══════════════════════════════════════════════════════════════
# 5. DÉTECTION D'ENTITÉS
# ══════════════════════════════════════════════════════════════

def _match_value(needle: str, candidates: list[str], cutoff: float = 0.6) -> str | None:
    if not candidates:
        return None
    needle_n = strip_accents(needle).lower().strip()
    norm = {strip_accents(c).lower(): c for c in candidates}
    if needle_n in norm:
        return norm[needle_n]
    for k, original in norm.items():
        if needle_n in k or k in needle_n:
            return original
    close = get_close_matches(needle_n, list(norm.keys()), n=1, cutoff=cutoff)
    return norm[close[0]] if close else None

def detect_entities(question: str) -> dict[str, str]:
    q_norm = strip_accents(question).lower()
    found: dict[str, str] = {}
    for dim, (col, values) in CATEGORICAL.items():
        if not values:
            continue
        for v in values:
            v_norm = strip_accents(str(v)).lower()
            if len(v_norm) < 3:
                continue
            pattern = r"\b" + re.escape(v_norm) + r"\b"
            if re.search(pattern, q_norm):
                found[dim] = v
                break
    return found

def detect_dimension(question: str) -> str | None:
    q_norm = strip_accents(question).lower()
    for dim, syns in DIM_SYNONYMS.items():
        for syn in syns:
            if re.search(rf"\bpar\s+{re.escape(syn)}\b", q_norm):
                return dim
            if re.search(rf"\bselon\s+(le|la|les)?\s*{re.escape(syn)}\b", q_norm):
                return dim
            if re.search(rf"\bpour\s+chaque\s+{re.escape(syn)}\b", q_norm):
                return dim
    return None

# ══════════════════════════════════════════════════════════════
# 6. SEMANTIC LAYER
# ══════════════════════════════════════════════════════════════

def _col(col: str) -> bool:
    return col in df.columns

def _apply_filters(data: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = data
    for dim, value in filters.items():
        if value is None:
            continue
        if dim == "year" and "ANNEE" in out.columns:
            out = out[out["ANNEE"] == int(value)]
        elif dim == "month" and "MOIS" in out.columns:
            out = out[out["MOIS"] == int(value)]
        elif dim == "quarter" and "TRIMESTRE" in out.columns:
            out = out[out["TRIMESTRE"] == int(value)]
        elif dim == "semester" and "SEMESTRE" in out.columns:
            out = out[out["SEMESTRE"] == int(value)]
        elif dim == "week" and "SEMAINE" in out.columns:
            out = out[out["SEMAINE"] == int(value)]
        elif dim in CATEGORICAL:
            col, _ = CATEGORICAL[dim]
            if col in out.columns:
                out = out[out[col].astype(str).str.lower() == str(value).lower()]
    return out

# --- Agrégations numériques ---
def total_tonnage(filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    return _apply_filters(df, filters or {})[COL_QTY].sum()

def avg_tonnage(filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    return _apply_filters(df, filters or {})[COL_QTY].mean()

def total_voyages(filters: dict | None = None) -> float | None:
    if not _col(COL_VOY): return None
    return _apply_filters(df, filters or {})[COL_VOY].sum()

def avg_voyages(filters: dict | None = None) -> float | None:
    if not _col(COL_VOY): return None
    return _apply_filters(df, filters or {})[COL_VOY].mean()

# --- Temporel ---
def tonnage_month(year: int, month: int, filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    return total_tonnage({"year": year, "month": month, **(filters or {})})

def tonnage_year(year: int, filters: dict | None = None) -> dict[int, float] | None:
    if not _col(COL_QTY): return None
    sub = _apply_filters(df, {"year": year, **(filters or {})})
    return sub.groupby("MOIS")[COL_QTY].sum().to_dict()

def tonnage_quarter(year: int, quarter: int, filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    months = TRIMESTRES.get(quarter, [])
    sub = _apply_filters(df, {"year": year, **(filters or {})})
    return sub[sub["MOIS"].isin(months)][COL_QTY].sum()

def tonnage_semester(year: int, semester: int, filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    months = SEMESTRES.get(semester, [])
    sub = _apply_filters(df, {"year": year, **(filters or {})})
    return sub[sub["MOIS"].isin(months)][COL_QTY].sum()

def tonnage_week(year: int, week: int, filters: dict | None = None) -> float | None:
    if not _col(COL_QTY): return None
    return total_tonnage({"year": year, "week": week, **(filters or {})})

def voyages_month(year: int, month: int, filters: dict | None = None) -> float | None:
    if not _col(COL_VOY): return None
    return total_voyages({"year": year, "month": month, **(filters or {})})

def voyages_year(year: int, filters: dict | None = None) -> dict[int, float] | None:
    if not _col(COL_VOY): return None
    sub = _apply_filters(df, {"year": year, **(filters or {})})
    return sub.groupby("MOIS")[COL_VOY].sum().to_dict()

# --- Agrégations génériques par dimension ---
def tonnage_by_dim(dim: str, filters: dict | None = None,
                   top_n: int | None = None) -> pd.Series | None:
    if dim not in CATEGORICAL or not _col(COL_QTY): return None
    col, _ = CATEGORICAL[dim]
    if not _col(col): return None
    sub = _apply_filters(df, filters or {})
    result = sub.groupby(col)[COL_QTY].sum().sort_values(ascending=False)
    return result.head(top_n) if top_n else result

def voyages_by_dim(dim: str, filters: dict | None = None,
                   top_n: int | None = None) -> pd.Series | None:
    if dim not in CATEGORICAL or not _col(COL_VOY): return None
    col, _ = CATEGORICAL[dim]
    if not _col(col): return None
    sub = _apply_filters(df, filters or {})
    result = sub.groupby(col)[COL_VOY].sum().sort_values(ascending=False)
    return result.head(top_n) if top_n else result

# --- Comptages catégoriels ---
def distinct_count(dim: str, filters: dict | None = None) -> int | None:
    if dim not in CATEGORICAL: return None
    col, _ = CATEGORICAL[dim]
    if not _col(col): return None
    sub = _apply_filters(df, filters or {})
    return sub[col].dropna().nunique()

def list_values(dim: str, filters: dict | None = None) -> list[str] | None:
    if dim not in CATEGORICAL: return None
    col, _ = CATEGORICAL[dim]
    if not _col(col): return None
    sub = _apply_filters(df, filters or {})
    return sorted(sub[col].dropna().unique().tolist())

def distinct_years() -> int | None:
    return df["ANNEE"].nunique() if "ANNEE" in df.columns else None

def values_for(target_dim: str, filters: dict) -> list[str] | None:
    if target_dim not in CATEGORICAL: return None
    col, _ = CATEGORICAL[target_dim]
    if not _col(col): return None
    sub = _apply_filters(df, filters)
    return sorted(sub[col].dropna().unique().tolist())

# --- Helpers spécifiques ---
def unique_trucks() -> int | None:
    return distinct_count("engin")

def count_sites() -> int | None:
    return distinct_count("site")

def top_sites(n: int = 5) -> pd.Series | None:
    return tonnage_by_dim("site", top_n=n)

def tonnage_site(site: str) -> tuple[float | None, str | None]:
    matched = _match_value(site, SITES_DISPO)
    if not matched: return None, None
    return total_tonnage({"site": matched}), matched

def list_engins() -> list[str]:
    return list_values("engin") or []

def count_tombereaux() -> int:
    return len(TOMBEREAUX_DISPO)

def avg_tonnage_per_voyage(filters: dict | None = None) -> float | None:
    if not _col(COL_TV): return None
    sub = _apply_filters(df, filters or {})
    return sub[COL_TV].mean()

def engins_by_type(type_camion: str) -> pd.Series | None:
    """Filtre par N°CAMION (ex. TOMBEREAU ou BENNE)."""
    if not _col(COL_CAM) or not _col(COL_QTY): return None
    t = type_camion.strip().upper()
    sub = df[df[COL_CAM].astype(str).str.upper() == t]
    if sub.empty: return None
    return sub.groupby(COL_TRUCK)[COL_QTY].sum().nlargest(10)

# --- Observations ---
def search_observation(keyword: str, filters: dict | None = None,
                       limit: int = 15) -> pd.DataFrame | None:
    if not _col(COL_OBS): return None
    sub = _apply_filters(df, filters or {})
    if sub.empty: return sub
    mask = sub[COL_OBS].fillna("").astype(str).apply(
        lambda x: strip_accents(keyword).lower() in strip_accents(x).lower()
    )
    cols_show = [c for c in (COL_DATE, COL_SITE, COL_TRUCK, COL_QTY, COL_OBS)
                 if c in sub.columns]
    return sub.loc[mask, cols_show].head(limit)

def count_observations(keyword: str, filters: dict | None = None) -> int | None:
    if not _col(COL_OBS): return None
    sub = _apply_filters(df, filters or {})
    mask = sub[COL_OBS].fillna("").astype(str).apply(
        lambda x: strip_accents(keyword).lower() in strip_accents(x).lower()
    )
    return int(mask.sum())

def list_observations(filters: dict | None = None, limit: int = 20) -> pd.DataFrame | None:
    if not _col(COL_OBS): return None
    sub = _apply_filters(df, filters or {})
    sub = sub[sub[COL_OBS].notna() & (sub[COL_OBS].astype(str).str.strip() != "")]
    cols_show = [c for c in (COL_DATE, COL_SITE, COL_TRUCK, COL_QTY, COL_OBS)
                 if c in sub.columns]
    return sub[cols_show].head(limit)

def pannes_summary(filters: dict | None = None) -> dict:
    if not _col(COL_OBS): return {}
    sub = _apply_filters(df, filters or {})
    categories = {
        "panne_mecanique": ["panne", "panne mecanique"],
        "pluie":           ["pluvieux", "pluie", "pluvieuse"],
        "climatisation":   ["climatisation"],
        "pneu":            ["pneu"],
        "carburant":       ["carburant"],
        "flexible":        ["flexible"],
        "direction":       ["direction"],
        "piste":           ["piste"],
        "depart":          ["depart"],
    }
    result = {}
    obs_series = sub[COL_OBS].dropna().str.lower().apply(strip_accents)
    for cat, keywords in categories.items():
        count = obs_series.apply(lambda x: any(k in x for k in keywords)).sum()
        if count > 0:
            result[cat] = int(count)
    return result

def jours_avec_incidents(filters: dict | None = None) -> int:
    if not _col(COL_OBS): return 0
    sub = _apply_filters(df, filters or {})
    return int(sub[COL_OBS].notna().sum())

# ══════════════════════════════════════════════════════════════
# 7. FORMATTERS
# ══════════════════════════════════════════════════════════════

def _fmt_filters(filters: dict) -> str:
    parts = []
    for k, v in filters.items():
        if v is None: continue
        if k == "year":       parts.append(f"{v}")
        elif k == "month":    parts.append(f"{MOIS_NUM_TO_FR.get(int(v), v)}")
        elif k == "quarter":  parts.append(f"T{v}")
        elif k == "semester": parts.append(f"S{v}")
        elif k == "week":     parts.append(f"semaine {v}")
        else:                 parts.append(f"{k}={v}")
    return " | ".join(parts) if parts else "tous les enregistrements"

def fmt_month(year, month):
    return f"{MOIS_NUM_TO_FR.get(month, month)}/{year}"

def _fmt_tonnage_month(year: int, month: int, filters: dict | None = None) -> str:
    val = tonnage_month(year, month, filters)
    if val is None: return "Données indisponibles."
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return f"Tonnage {fmt_month(year, month)}{extra} : {val:,.0f} T"

def _fmt_tonnage_year(year: int, filters: dict | None = None) -> str:
    data = tonnage_year(year, filters)
    if not data: return f"Aucune donnée pour {year}."
    lines = [f"  {MOIS_NUM_TO_FR[int(m)]:>10} : {v:>12,.0f} T"
             for m, v in sorted(data.items()) if pd.notna(m) and v > 0]
    total = sum(v for v in data.values() if pd.notna(v))
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return (f"Tonnage mensuel {year}{extra} :\n"
            + "\n".join(lines)
            + f"\n  {'TOTAL':>10} : {total:>12,.0f} T")

def _fmt_tonnage_quarter(year: int, quarter: int, filters: dict | None = None) -> str:
    val = tonnage_quarter(year, quarter, filters)
    if val is None: return "Données indisponibles."
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return f"Tonnage T{quarter} {year}{extra} : {val:,.0f} T"

def _fmt_tonnage_semester(year: int, semester: int, filters: dict | None = None) -> str:
    val = tonnage_semester(year, semester, filters)
    if val is None: return "Données indisponibles."
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return f"Tonnage S{semester} {year}{extra} : {val:,.0f} T"

def _fmt_tonnage_week(year: int, week: int, filters: dict | None = None) -> str:
    val = tonnage_week(year, week, filters)
    if val is None: return "Données indisponibles."
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return f"Tonnage semaine {week}/{year}{extra} : {val:,.0f} T"

def _fmt_compare_quarters(year1: int, q1: int, year2: int, q2: int) -> str:
    v1 = tonnage_quarter(year1, q1); v2 = tonnage_quarter(year2, q2)
    if v1 is None or v2 is None: return "Données insuffisantes pour la comparaison."
    diff = v2 - v1; pct = (diff / v1) * 100
    sens = "▲ hausse" if diff > 0 else "▼ baisse"
    return (
        f"Comparaison T{q1} {year1} vs T{q2} {year2} :\n"
        f"  T{q1} {year1} : {v1:,.0f} T\n"
        f"  T{q2} {year2} : {v2:,.0f} T\n"
        f"  Écart      : {diff:+,.0f} T  ({pct:+.1f} % — {sens})"
    )

def _fmt_compare_semesters(year1: int, s1: int, year2: int, s2: int) -> str:
    v1 = tonnage_semester(year1, s1); v2 = tonnage_semester(year2, s2)
    if v1 is None or v2 is None: return "Données insuffisantes pour la comparaison."
    diff = v2 - v1; pct = (diff / v1) * 100
    sens = "▲ hausse" if diff > 0 else "▼ baisse"
    return (
        f"Comparaison S{s1} {year1} vs S{s2} {year2} :\n"
        f"  S{s1} {year1} : {v1:,.0f} T\n"
        f"  S{s2} {year2} : {v2:,.0f} T\n"
        f"  Écart      : {diff:+,.0f} T  ({pct:+.1f} % — {sens})"
    )

def _fmt_compare_months_2(year: int, m1: int, m2: int) -> str:
    v1 = tonnage_month(year, m1); v2 = tonnage_month(year, m2)
    if v1 is None: return f"Données vides pour {fmt_month(year, m1)}."
    if v2 is None: return f"Données vides pour {fmt_month(year, m2)}."
    diff = v2 - v1; pct = ((v2 - v1) / v1) * 100
    sens = "▲ hausse" if diff > 0 else "▼ baisse"
    return (
        f"Comparaison {fmt_month(year, m1)} vs {fmt_month(year, m2)} :\n"
        f"  {MOIS_NUM_TO_FR[m1]} : {v1:,.0f} T\n"
        f"  {MOIS_NUM_TO_FR[m2]} : {v2:,.0f} T\n"
        f"  Écart      : {diff:+,.0f} T  ({pct:+.1f} % — {sens})"
    )

def _fmt_series(title: str, s: pd.Series | None, unit: str = "T") -> str:
    if s is None or s.empty: return f"{title} : aucune donnée."
    width = max(len(str(i)) for i in s.index) + 2
    lines = [f"  {str(idx):<{width}} : {val:>12,.0f} {unit}" for idx, val in s.items()]
    total = s.sum()
    return f"{title} :\n" + "\n".join(lines) + f"\n  {'TOTAL':<{width}} : {total:>12,.0f} {unit}"

def _fmt_top_sites(n: int) -> str:
    return _fmt_series(f"Top {n} sites", tonnage_by_dim("site", top_n=n))

def _fmt_site(site: str) -> str:
    val, matched = tonnage_site(site)
    if val is None:
        close = get_close_matches(site.lower(), [s.lower() for s in SITES_DISPO], n=3, cutoff=0.4)
        sug = f"  Vouliez-vous dire : {close} ?" if close else ""
        return f"Site '{site}' introuvable.{sug}"
    return f"Tonnage site '{matched}' : {val:,.0f} T"

def _fmt_list(title: str, values: list[str]) -> str:
    if not values: return f"{title} : aucune valeur."
    lines = [f"  • {v}" for v in values]
    return f"{title} ({len(values)}) :\n" + "\n".join(lines)

def _fmt_observations_df(title: str, rows: pd.DataFrame) -> str:
    if rows is None or rows.empty:
        return f"{title} : aucun résultat."
    lines = [f"{title} ({len(rows)} affichés) :"]
    for _, row in rows.iterrows():
        date = row.get(COL_DATE)
        d = date.strftime("%d/%m/%Y") if pd.notna(date) else "?"
        site = row.get(COL_SITE, "?") or "?"
        engin = row.get(COL_TRUCK, "?") or "?"
        qty = row.get(COL_QTY)
        q = f"{qty:,.0f} T" if pd.notna(qty) else "-"
        obs = (row.get(COL_OBS) or "").strip()
        lines.append(f"  - {d} | {site} | {engin} | {q} | {obs}")
    return "\n".join(lines)

def _fmt_pannes(filters: dict | None = None) -> str:
    summary = pannes_summary(filters)
    if not summary: return "Aucun incident enregistré dans les observations."
    lines = [f"  {cat:20s} : {cnt} occurrence(s)"
             for cat, cnt in sorted(summary.items(), key=lambda x: -x[1])]
    total = jours_avec_incidents(filters)
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return (f"Résumé des incidents{extra} ({total} entrées avec observation) :\n"
            + "\n".join(lines))

def _fmt_incidents_kw(keyword: str, filters: dict | None = None) -> str:
    rows = search_observation(keyword, filters, limit=20)
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return _fmt_observations_df(f"Incidents '{keyword}'{extra}", rows)

def _fmt_voyages_month(year: int, month: int, filters: dict | None = None) -> str:
    val = voyages_month(year, month, filters)
    if val is None: return "Données indisponibles."
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return f"Voyages {fmt_month(year, month)}{extra} : {val:,.0f} voyages"

def _fmt_voyages_year(year: int, filters: dict | None = None) -> str:
    data = voyages_year(year, filters)
    if not data: return f"Aucune donnée pour {year}."
    lines = [f"  {MOIS_NUM_TO_FR[int(m)]:>10} : {v:>10,.0f} voyages"
             for m, v in sorted(data.items()) if pd.notna(m) and v > 0]
    total = sum(v for v in data.values() if pd.notna(v))
    extra = f" ({_fmt_filters(filters)})" if filters else ""
    return (f"Voyages mensuels {year}{extra} :\n"
            + "\n".join(lines)
            + f"\n  {'TOTAL':>10} : {total:>10,.0f} voyages")

def _fmt_zone(zone: str) -> str:
    matched = _match_value(zone, ZONES_DISPO)
    if not matched:
        close = get_close_matches(zone.lower(), [z.lower() for z in ZONES_DISPO], n=3, cutoff=0.4)
        sug = f"  Vouliez-vous dire : {close} ?" if close else ""
        return f"Zone '{zone}' introuvable.{sug}"
    val = total_tonnage({"zone": matched})
    v_voyage = total_voyages({"zone": matched})
    voyage_line = f"\n  Voyages : {v_voyage:,.0f}" if v_voyage is not None else ""
    return f"Zone '{matched}' :\n  Tonnage : {val:,.0f} T{voyage_line}"

def _fmt_engin(engin: str) -> str:
    matched = _match_value(engin, TRUCKS_DISPO)
    if not matched:
        close = get_close_matches(engin.lower(), [e.lower() for e in TRUCKS_DISPO], n=3, cutoff=0.4)
        sug = f"  Vouliez-vous dire : {close} ?" if close else ""
        return f"Engin '{engin}' introuvable.{sug}"
    val = total_tonnage({"engin": matched})
    return f"Tonnage engin '{matched}' : {val:,.0f} T"

def _fmt_responsable(resp: str) -> str:
    matched = _match_value(resp, RESPONSABLES_DISPO, cutoff=0.4)
    if not matched:
        close = get_close_matches(resp.lower(), [r.lower() for r in RESPONSABLES_DISPO], n=3, cutoff=0.4)
        sug = f"  Vouliez-vous dire : {close} ?" if close else ""
        return f"Responsable '{resp}' introuvable.{sug}"
    val = total_tonnage({"responsable": matched})
    return f"Tonnage sous '{matched}' : {val:,.0f} T"

# ══════════════════════════════════════════════════════════════
# 8. PARSER DE RÈGLES
# ══════════════════════════════════════════════════════════════

def _extract_year(q: str) -> int | None:
    m = re.search(r"20\d{2}", q)
    return int(m.group()) if m else (ANNEES_DISPO[-1] if ANNEES_DISPO else None)

def _extract_months(q: str) -> list[int]:
    found = []
    for nom, num in MOIS_FR.items():
        if re.search(rf"\b{re.escape(strip_accents(nom))}\b", strip_accents(q).lower()):
            if num not in found:
                found.append(num)
    for m in re.finditer(r"\bmois\s+(\d{1,2})\b", q):
        n = int(m.group(1))
        if 1 <= n <= 12 and n not in found:
            found.append(n)
    return found

def _extract_quarter(q: str) -> int | None:
    m = re.search(r"trimestre\s+(\d)", q, re.I)
    return int(m.group(1)) if m else None

def _extract_semester(q: str) -> int | None:
    m = re.search(r"semestre\s+(\d)", q, re.I)
    return int(m.group(1)) if m else None

def _extract_week(q: str) -> int | None:
    m = re.search(r"semaine\s+(\d{1,2})", q, re.I)
    return int(m.group(1)) if m else None

def _wants_voyages(ql: str) -> bool:
    return any(w in ql for w in ["voyage", "rotation", "trajet"])

def _wants_list(ql: str) -> bool:
    return any(w in ql for w in ["liste", "lister", "quels", "quelles", "donne",
                                   "noms", "afficher", "montre", "tous", "toutes"])

def _wants_count(ql: str) -> bool:
    return any(w in ql for w in ["combien", "nombre", "compte", "count"])

def _wants_distinct(ql: str) -> bool:
    return any(w in ql for w in ["distinct", "unique", "different"])

def rule_based_parse(question: str) -> str | None:
    q  = preprocess(question)
    ql = strip_accents(q).lower()

    year     = _extract_year(ql)
    months   = _extract_months(ql)
    quarter  = _extract_quarter(ql)
    semester = _extract_semester(ql)
    week     = _extract_week(ql)

    entities = detect_entities(q)
    by_dim   = detect_dimension(q)

    base_filters = dict(entities)
    if year:
        base_filters["year"] = year

    # ── Info colonnes ─────────────────────────────────────────
    if any(w in ql for w in ["colonnes", "champs", "variables"]):
        return "Colonnes disponibles :\n  " + "\n  ".join(df.columns.tolist())

    # ── Responsables ──────────────────────────────────────────
    if any(w in ql for w in ["responsable", "responsables", "chef de site", "superviseur"]):
        if _wants_list(ql) or _wants_count(ql):
            vals = list_values("responsable", base_filters)
            if _wants_count(ql):
                return f"Nombre de responsables ({_fmt_filters(base_filters)}) : {len(vals or [])}"
            return _fmt_list(f"Responsables de site ({_fmt_filters(base_filters)})", vals or [])
        site_filter = {k: v for k, v in entities.items() if k == "site"}
        if site_filter and ("qui" in ql or "quel" in ql):
            names = values_for("responsable", site_filter)
            if names:
                return _fmt_list(f"Responsable(s) — {_fmt_filters(site_filter)}", names)
        for resp in RESPONSABLES_DISPO:
            if strip_accents(resp.lower()) in ql:
                return _fmt_responsable(resp)

    # ── BENNE (type d'engin) ──────────────────────────────────
    if "benne" in ql:
        result = engins_by_type("BENNE")
        if result is not None:
            return _fmt_series("Engins BENNE (top tonnage)", result)

    # ── Tombereaux (strictement) ──────────────────────────────
    if "tombereau" in ql:
        if any(w in ql for w in ["top", "meilleur", "classement"]):
            m_n = re.search(r"\d+", ql)
            n = int(m_n.group()) if m_n else 5
            sub = tonnage_by_dim("engin", base_filters) or pd.Series(dtype=float)
            sub = sub[sub.index.str.upper().str.startswith("TOMBEREAU")].head(n)
            return _fmt_series(f"Top {n} tombereaux ({_fmt_filters(base_filters)})", sub)
        if _wants_list(ql):
            return _fmt_list("Tombereaux", TOMBEREAUX_DISPO)
        if _wants_count(ql) or _wants_distinct(ql):
            return f"Tombereaux uniques : {count_tombereaux()}"

    # ── Engins (tous types) ───────────────────────────────────
    if any(w in ql for w in ["engin", "vehicule", "immatriculation"]):
        if any(w in ql for w in ["top", "meilleur", "plus", "classement"]):
            m_n = re.search(r"\d+", ql)
            n = int(m_n.group()) if m_n else 5
            return _fmt_series(f"Top {n} engins ({_fmt_filters(base_filters)})",
                               tonnage_by_dim("engin", base_filters, top_n=n) or pd.Series(dtype=float))
        if _wants_list(ql):
            vals = list_values("engin")
            return _fmt_list("Engins / tombereaux", vals or [])
        if _wants_count(ql) or _wants_distinct(ql):
            return f"Engins uniques : {unique_trucks()}"
        for engin in TRUCKS_DISPO:
            if strip_accents(engin.lower()) in ql:
                return _fmt_engin(engin)

    # ── Observations / Incidents / Pannes ─────────────────────
    obs_triggers = ["observation", "incident", "panne", "arret", "probleme",
                    "bris", "avarie", "accident", "depannage"]
    if any(w in ql for w in obs_triggers):
        if any(w in ql for w in ["resume", "bilan", "total", "rapport", "synthese"]):
            return _fmt_pannes(base_filters)
        obs_kws = ["pluie", "pluvi", "pneu", "carburant", "flexible", "direction",
                   "climatisation", "piste", "depart", "depannage",
                   "casse", "reparation", "feu", "blessure", "retard"]
        for kw in obs_kws:
            if kw in ql:
                if _wants_count(ql):
                    n = count_observations(kw, base_filters)
                    return f"Occurrences '{kw}' ({_fmt_filters(base_filters)}) : {n}"
                return _fmt_incidents_kw(kw, base_filters)
        if _wants_list(ql):
            rows = list_observations(base_filters, limit=20)
            return _fmt_observations_df("Observations enregistrées", rows)
        for word in ql.split():
            if len(word) > 4 and word not in obs_triggers + ["liste", "toutes"]:
                rows = search_observation(word, base_filters, limit=15)
                if rows is not None and not rows.empty:
                    return _fmt_observations_df(f"Observations '{word}'", rows)

    # ── Liste / Compter pour une dimension ────────────────────
    for dim, syns in DIM_SYNONYMS.items():
        if any(re.search(rf"\b{re.escape(s)}\b", ql) for s in syns):
            if _wants_list(ql) or _wants_distinct(ql):
                vals = list_values(dim, base_filters)
                return _fmt_list(f"Valeurs '{dim}'", vals or [])
            if _wants_count(ql):
                n = distinct_count(dim, base_filters)
                return f"Nombre de '{dim}' distincts ({_fmt_filters(base_filters)}) : {n}"

    # ── Zones de stockage ─────────────────────────────────────
    if any(w in ql for w in ["zone", "stock"]):
        if _wants_count(ql) or _wants_distinct(ql):
            n = distinct_count("zone", base_filters)
            return f"Nombre de zones ({_fmt_filters(base_filters)}) : {n}"
        if any(w in ql for w in ["plus eleve", "plus haut", "maximum", "max",
                                   "le plus", "premier"]):
            s = tonnage_by_dim("zone", base_filters, top_n=1) or pd.Series(dtype=float)
            return _fmt_series(f"Zone avec le tonnage le plus élevé ({_fmt_filters(base_filters)})", s)
        if any(w in ql for w in ["top", "meilleur", "plus actif"]):
            m_n = re.search(r"\d+", ql)
            n = int(m_n.group()) if m_n else 10
            return _fmt_series(f"Top {n} zones ({_fmt_filters(base_filters)})",
                               tonnage_by_dim("zone", base_filters, top_n=n))
        zone_match = re.search(r"stock\s*\d+(?:\s*bis)?", ql, re.I)
        if zone_match:
            return _fmt_zone(zone_match.group().strip())
        if "zone" in entities:
            return _fmt_zone(entities["zone"])

    # ── "Qui est le responsable de X ?" ──────────────────────
    if "responsable" in ql and entities:
        f = {k: v for k, v in entities.items() if k != "responsable"}
        names = values_for("responsable", f)
        if names:
            return _fmt_list(f"Responsable(s) — {_fmt_filters(f)}", names)

    # ── "Quels produits / qualités / zones au site X ?" ───────
    for target in ("produit", "qualite", "zone", "transport", "camion", "engin"):
        if any(re.search(rf"\b{re.escape(s)}\b", ql) for s in DIM_SYNONYMS[target]):
            f = {k: v for k, v in entities.items() if k != target}
            if f and (_wants_list(ql) or "quel" in ql):
                vals = values_for(target, f)
                if vals:
                    return _fmt_list(f"{target.capitalize()} — {_fmt_filters(f)}", vals)

    # ── Agrégation par dimension ──────────────────────────────
    if by_dim:
        period_filters = {k: v for k, v in base_filters.items()
                          if k in ("year", "month", "quarter", "semester", "week")
                          or k in CATEGORICAL}
        if _wants_voyages(ql):
            s = voyages_by_dim(by_dim, period_filters)
            return _fmt_series(
                f"Voyages par {by_dim} ({_fmt_filters(period_filters)})", s, unit="voyages"
            )
        s = tonnage_by_dim(by_dim, period_filters)
        return _fmt_series(f"Tonnage par {by_dim} ({_fmt_filters(period_filters)})", s)

    # ── Tonnage par voyage (T/voyage) ─────────────────────────
    if "par voyage" in ql and "tonnage" in ql:
        v = avg_tonnage_per_voyage(base_filters)
        if v is None: return "Données TONNAGE/VOYAGE indisponibles."
        return f"Tonnage moyen par voyage ({_fmt_filters(base_filters)}) : {v:,.2f} T/voyage"

    # ── Voyages ───────────────────────────────────────────────
    if _wants_voyages(ql):
        if any(w in ql for w in ["par mois", "mensuel", "chaque mois"]) and year:
            return _fmt_voyages_year(year, entities or None)
        if "moyenne" in ql or "moyen" in ql:
            v = avg_voyages(base_filters)
            if v is None: return "Données voyages indisponibles."
            return f"Moyenne voyages/jour ({_fmt_filters(base_filters)}) : {v:,.2f}"
        if months and year:
            return _fmt_voyages_month(year, months[0], entities or None)
        v = total_voyages(base_filters)
        if v is None: return "Données voyages indisponibles."
        return f"Total voyages ({_fmt_filters(base_filters)}) : {v:,.0f}"

    # ── Années distinctes ─────────────────────────────────────
    if any(w in ql for w in ["annee", "annees", "an"]) and (_wants_distinct(ql) or _wants_count(ql)):
        return f"Années distinctes : {distinct_years()}"

    # ── Top N <dimension> ─────────────────────────────────────
    m_top = re.search(r"top\s*(\d+)?", ql)
    if m_top:
        n = int(m_top.group(1)) if m_top.group(1) else 5
        for dim, syns in DIM_SYNONYMS.items():
            if any(re.search(rf"\b{re.escape(s)}\b", ql) for s in syns):
                s = tonnage_by_dim(dim, base_filters, top_n=n)
                return _fmt_series(f"Top {n} {dim} ({_fmt_filters(base_filters)})", s)
        s = tonnage_by_dim("site", base_filters, top_n=n)
        return _fmt_series(f"Top {n} sites ({_fmt_filters(base_filters)})", s)

    # ── Moyenne tonnage ───────────────────────────────────────
    if any(w in ql for w in ["moyenne", "moyen", "moy"]):
        v = avg_tonnage(base_filters)
        if v is None: return "Données indisponibles."
        return f"Moyenne journalière ({_fmt_filters(base_filters)}) : {v:,.2f} T"

    # ── Tonnage total (avec filtres) ──────────────────────────
    if "total" in ql and not any(k in ql for k in
                                  ["site", "trimestre", "semestre", "mois", "annee",
                                   "voyage", "zone", "engin", "tombereau"]):
        v = total_tonnage(base_filters)
        if v is None: return "Données indisponibles."
        return f"Tonnage total ({_fmt_filters(base_filters)}) : {v:,.0f} T"

    # ── Comparaison année vs année ────────────────────────────
    years_in_q = [int(y) for y in re.findall(r"20\d{2}", ql)]
    compare_words = ["comparer", "comparaison", "versus", " vs ", " et ", "par rapport"]
    if len(years_in_q) == 2 and any(w in ql for w in compare_words):
        y1, y2 = years_in_q[0], years_in_q[1]
        if len(months) == 1:
            # même mois, deux années différentes
            m = months[0]
            v1 = tonnage_month(y1, m); v2 = tonnage_month(y2, m)
            if v1 is not None and v2 is not None:
                diff = v2 - v1; pct = (diff / v1 * 100) if v1 else 0
                sens = "▲ hausse" if diff > 0 else "▼ baisse"
                return (
                    f"Comparaison {MOIS_NUM_TO_FR.get(m, m)} {y1} vs {y2} :\n"
                    f"  {y1} : {v1:,.0f} T\n"
                    f"  {y2} : {v2:,.0f} T\n"
                    f"  Écart : {diff:+,.0f} T  ({pct:+.1f} % — {sens})"
                )
        else:
            # comparaison annuelle totale
            v1 = total_tonnage({"year": y1}); v2 = total_tonnage({"year": y2})
            if v1 is not None and v2 is not None:
                diff = v2 - v1; pct = (diff / v1 * 100) if v1 else 0
                sens = "▲ hausse" if diff > 0 else "▼ baisse"
                return (
                    f"Comparaison {y1} vs {y2} :\n"
                    f"  {y1} : {v1:,.0f} T\n"
                    f"  {y2} : {v2:,.0f} T\n"
                    f"  Écart : {diff:+,.0f} T  ({pct:+.1f} % — {sens})"
                )

    # ── Comparaison de trimestres ─────────────────────────────
    qt_matches = re.findall(r"trimestre\s+(\d)\s+(20\d{2})", ql)
    if len(qt_matches) == 2:
        q1, y1 = int(qt_matches[0][0]), int(qt_matches[0][1])
        q2, y2 = int(qt_matches[1][0]), int(qt_matches[1][1])
        return _fmt_compare_quarters(y1, q1, y2, q2)
    if len(qt_matches) == 1:
        return _fmt_tonnage_quarter(int(qt_matches[0][1]), int(qt_matches[0][0]), entities)

    # ── Comparaison de semestres ──────────────────────────────
    sem_matches = re.findall(r"semestre\s+(\d)\s+(20\d{2})", ql)
    if len(sem_matches) == 2:
        s1, y1 = int(sem_matches[0][0]), int(sem_matches[0][1])
        s2, y2 = int(sem_matches[1][0]), int(sem_matches[1][1])
        return _fmt_compare_semesters(y1, s1, y2, s2)
    if len(sem_matches) == 1:
        return _fmt_tonnage_semester(int(sem_matches[0][1]), int(sem_matches[0][0]), entities)

    # ── Trimestre / Semestre / Semaine ────────────────────────
    if quarter and year:
        return _fmt_tonnage_quarter(year, quarter, entities)
    if semester and year:
        return _fmt_tonnage_semester(year, semester, entities)
    if week and year:
        return _fmt_tonnage_week(year, week, entities)

    # ── Comparaison de mois ───────────────────────────────────
    if len(months) >= 2 and year:
        if len(months) == 2:
            return _fmt_compare_months_2(year, months[0], months[1])
        lines = [f"  {_fmt_tonnage_month(year, m, entities)}" for m in months]
        return f"Tonnages ({year}) :\n" + "\n".join(lines)

    # ── Tonnage d'un mois précis ──────────────────────────────
    if len(months) == 1 and year:
        return _fmt_tonnage_month(year, months[0], entities)

    # ── Tonnage par mois d'une année ─────────────────────────
    if year and any(w in ql for w in ["par mois", "chaque mois", "tous les mois", "mensuel"]):
        return _fmt_tonnage_year(year, entities)

    # ── Site spécifique ───────────────────────────────────────
    if "site" in entities and not by_dim:
        return _fmt_site(entities["site"])

    # ── Tonnage annuel ────────────────────────────────────────
    if year and any(w in ql for w in ["tonnage", "quantite", "produit", "extrait", "descend"]):
        return _fmt_tonnage_year(year, entities)

    # ── Tonnage total global ──────────────────────────────────
    if "tonnage" in ql and not entities and not year:
        v = total_tonnage()
        if v is None: return "Données indisponibles."
        return f"Tonnage total global : {v:,.0f} T"

    # ── Valeurs distinctes génériques ─────────────────────────
    if _wants_distinct(ql):
        for col in df.columns:
            if strip_accents(col.lower()) in ql:
                return f"Valeurs distinctes '{col}' : {df[col].nunique()}"

    return None

# ══════════════════════════════════════════════════════════════
# 9. SAFE JSON PARSER
# ══════════════════════════════════════════════════════════════

def safe_json(text: str) -> dict | None:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None

# ══════════════════════════════════════════════════════════════
# 10. EXTRACTION D'INTENTION LLM
# ══════════════════════════════════════════════════════════════

FEW_SHOT = f"""
Exemples :
Q: "tonnage total"
R: {{"type":"total","params":{{}}}}

Q: "moyenne journalière"
R: {{"type":"mean","params":{{}}}}

Q: "combien de tombereaux"
R: {{"type":"distinct","params":{{"dim":"engin"}}}}

Q: "liste des engins"
R: {{"type":"list","params":{{"dim":"engin"}}}}

Q: "top 5 engins"
R: {{"type":"top","params":{{"dim":"engin","n":5}}}}

Q: "engins de type BENNE"
R: {{"type":"engins_by_type","params":{{"type":"BENNE"}}}}

Q: "tonnage mars 2026"
R: {{"type":"tonnage_month","params":{{"year":2026,"month":3}}}}

Q: "voyages mars 2026"
R: {{"type":"voyages_month","params":{{"year":2026,"month":3}}}}

Q: "comparer jan et fev 2026"
R: {{"type":"compare_months","params":{{"year":2026,"m1":1,"m2":2}}}}

Q: "tonnage par mois 2026"
R: {{"type":"tonnage_year","params":{{"year":2026}}}}

Q: "voyages par mois 2026"
R: {{"type":"voyages_year","params":{{"year":2026}}}}

Q: "tonnage par produit 2024"
R: {{"type":"tonnage_by","params":{{"dim":"produit","year":2024}}}}

Q: "voyages par site 2024"
R: {{"type":"voyages_by","params":{{"dim":"site","year":2024}}}}

Q: "tonnage stock 4"
R: {{"type":"tonnage_zone","params":{{"zone":"STOCK 4"}}}}

Q: "top 10 zones"
R: {{"type":"top","params":{{"dim":"zone","n":10}}}}

Q: "tonnage site Kone"
R: {{"type":"tonnage_site","params":{{"site":"Kone"}}}}

Q: "top 3 sites 2025"
R: {{"type":"top","params":{{"dim":"site","n":3,"year":2025}}}}

Q: "tonnage T1 2024 vs T1 2023"
R: {{"type":"compare_quarters","params":{{"year1":2023,"q1":1,"year2":2024,"q2":1}}}}

Q: "tonnage semaine 12 2026"
R: {{"type":"tonnage_week","params":{{"year":2026,"week":12}}}}

Q: "qui est responsable du site Bénéné ?"
R: {{"type":"values_for","params":{{"target":"responsable","site":"Bénéné"}}}}

Q: "quelles qualités à Bénéné en 2024"
R: {{"type":"values_for","params":{{"target":"qualite","site":"Bénéné","year":2024}}}}

Q: "liste des responsables"
R: {{"type":"list","params":{{"dim":"responsable"}}}}

Q: "tonnage Traore Hamed"
R: {{"type":"tonnage_responsable","params":{{"responsable":"TRAORE Hamed"}}}}

Q: "bilan des pannes"
R: {{"type":"pannes_summary","params":{{}}}}

Q: "incidents pluie 2024"
R: {{"type":"obs_search","params":{{"keyword":"pluie","year":2024}}}}

Q: "combien d'incidents de pluie"
R: {{"type":"obs_count","params":{{"keyword":"pluie"}}}}

Q: "total voyages 2024"
R: {{"type":"voyages_total","params":{{"year":2024}}}}

Q: "tonnage total bauxite 2024"
R: {{"type":"total","params":{{"produit":"BAUXITE","year":2024}}}}
"""

def interpret(question: str) -> dict | None:
    q_prep = preprocess(question)
    prompt = f"""
Tu es un assistant BI industriel minier. Retourne UNIQUEMENT un JSON valide, sans texte autour.

Dimensions disponibles : site, produit, responsable, transport, qualite, zone, camion, engin

Types : total, mean, tonnage_month, tonnage_year, tonnage_quarter, tonnage_semester,
tonnage_week, compare_months, compare_quarters, compare_semesters,
tonnage_by, voyages_by, voyages_total, voyages_month, voyages_year,
top, distinct, list, tonnage_site, tonnage_zone, tonnage_responsable,
values_for, obs_search, obs_count, pannes_summary, engins_by_type

Sites : {SITES_DISPO}
Produits : {PRODUITS_DISPO}
Qualités : {QUALITES_DISPO}
Zones : {ZONES_DISPO}
Responsables : {RESPONSABLES_DISPO[:8]}
Années : {ANNEES_DISPO}

{FEW_SHOT}

Question (prétraitée) : {q_prep}
JSON :"""
    try:
        result = llm.invoke(prompt)
        return safe_json(result)
    except Exception as e:
        print(f"[LLM ERREUR] {e}")
        return None

# ══════════════════════════════════════════════════════════════
# 11. VALIDATION + EXÉCUTION DES INTENTIONS LLM
# ══════════════════════════════════════════════════════════════

def _validate(intent: dict) -> tuple[bool, str]:
    t = intent.get("type")
    p = intent.get("params", {}) or {}
    required = {
        "tonnage_month":       ["year", "month"],
        "compare_months":      ["year", "m1", "m2"],
        "tonnage_site":        ["site"],
        "tonnage_zone":        ["zone"],
        "tonnage_responsable": ["responsable"],
        "compare_quarters":    ["year1", "q1", "year2", "q2"],
        "compare_semesters":   ["year1", "s1", "year2", "s2"],
        "tonnage_quarter":     ["year", "quarter"],
        "tonnage_semester":    ["year", "semester"],
        "tonnage_week":        ["year", "week"],
        "tonnage_year":        ["year"],
        "voyages_month":       ["year", "month"],
        "voyages_year":        ["year"],
        "obs_search":          ["keyword"],
        "obs_count":           ["keyword"],
        "engins_by_type":      ["type"],
        "values_for":          ["target"],
    }
    for key in required.get(t, []):
        if key not in p or p[key] is None:
            return False, f"Paramètre manquant : '{key}'"
    for k in ["year", "year1", "year2", "month", "m1", "m2", "n",
              "quarter", "q1", "q2", "semester", "s1", "s2", "week"]:
        if k in p and p[k] is not None:
            try:
                intent["params"][k] = int(p[k])
            except (ValueError, TypeError):
                return False, f"'{k}' invalide : {p[k]}"
    return True, ""

def _extract_filters_from_params(p: dict) -> dict:
    out = {}
    for k in ("year", "month", "quarter", "semester", "week"):
        if k in p and p[k] is not None:
            out[k] = int(p[k])
    for dim, (col, values) in CATEGORICAL.items():
        if dim in p and p[dim]:
            matched = _match_value(str(p[dim]), values)
            if matched:
                out[dim] = matched
    return out

def execute(intent: dict | None) -> str | None:
    if not intent:
        return None
    ok, err = _validate(intent)
    if not ok:
        return None

    t = intent.get("type")
    p = intent.get("params", {}) or {}
    filters = _extract_filters_from_params(p)

    try:
        match t:
            case "total":
                v = total_tonnage(filters)
                if v is None: return "Données indisponibles."
                return f"Tonnage total ({_fmt_filters(filters)}) : {v:,.0f} T"
            case "mean":
                v = avg_tonnage(filters)
                if v is None: return "Données indisponibles."
                return f"Moyenne journalière ({_fmt_filters(filters)}) : {v:,.2f} T"
            case "tonnage_month":
                return _fmt_tonnage_month(p["year"], p["month"], filters)
            case "tonnage_year":
                return _fmt_tonnage_year(p["year"], filters)
            case "tonnage_quarter":
                return _fmt_tonnage_quarter(p["year"], p["quarter"], filters)
            case "tonnage_semester":
                return _fmt_tonnage_semester(p["year"], p["semester"], filters)
            case "tonnage_week":
                return _fmt_tonnage_week(p["year"], p["week"], filters)
            case "compare_months":
                return _fmt_compare_months_2(p["year"], p["m1"], p["m2"])
            case "compare_quarters":
                return _fmt_compare_quarters(p["year1"], p["q1"], p["year2"], p["q2"])
            case "compare_semesters":
                return _fmt_compare_semesters(p["year1"], p["s1"], p["year2"], p["s2"])
            case "tonnage_by":
                s = tonnage_by_dim(p["dim"], filters)
                return _fmt_series(f"Tonnage par {p['dim']} ({_fmt_filters(filters)})", s)
            case "voyages_by":
                s = voyages_by_dim(p["dim"], filters)
                return _fmt_series(
                    f"Voyages par {p['dim']} ({_fmt_filters(filters)})", s, unit="voyages"
                )
            case "voyages_total":
                v = total_voyages(filters)
                if v is None: return "Données voyages indisponibles."
                return f"Total voyages ({_fmt_filters(filters)}) : {v:,.0f}"
            case "voyages_month":
                return _fmt_voyages_month(p["year"], p["month"], filters)
            case "voyages_year":
                return _fmt_voyages_year(p["year"], filters)
            case "top":
                s = tonnage_by_dim(p["dim"], filters, top_n=p.get("n", 5))
                return _fmt_series(
                    f"Top {p.get('n', 5)} {p['dim']} ({_fmt_filters(filters)})", s
                )
            case "distinct":
                n = distinct_count(p["dim"], filters)
                return f"Nombre de '{p['dim']}' distincts ({_fmt_filters(filters)}) : {n}"
            case "list":
                vals = list_values(p["dim"], filters)
                return _fmt_list(f"Valeurs '{p['dim']}' ({_fmt_filters(filters)})", vals or [])
            case "tonnage_site":
                return _fmt_site(p["site"])
            case "tonnage_zone":
                return _fmt_zone(p["zone"])
            case "tonnage_responsable":
                return _fmt_responsable(p["responsable"])
            case "values_for":
                target = p["target"]
                f = {k: v for k, v in filters.items() if k != target}
                vals = values_for(target, f)
                return _fmt_list(f"{target.capitalize()} — {_fmt_filters(f)}", vals or [])
            case "obs_search":
                return _fmt_incidents_kw(p["keyword"], filters)
            case "obs_count":
                n = count_observations(p["keyword"], filters)
                return f"Occurrences '{p['keyword']}' ({_fmt_filters(filters)}) : {n}"
            case "pannes_summary":
                return _fmt_pannes(filters)
            case "engins_by_type":
                result = engins_by_type(p["type"])
                return _fmt_series(f"Engins {p['type']} (top tonnage)", result)
            case _:
                return None
    except KeyError as e:
        return f"[Paramètre manquant] {e}"
    except Exception as e:
        return f"[Erreur d'exécution] {e}"

# ══════════════════════════════════════════════════════════════
# 12. PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def answer(question: str) -> str:
    response = rule_based_parse(question)
    if response is None:
        intent   = interpret(question)
        response = execute(intent)
    if response is None:
        exemples = [
            "tonnage total",
            f"tonnage par produit {ANNEES_DISPO[-1] if ANNEES_DISPO else '2026'}",
            "qui est responsable du site Bénéné ?",
            "liste des qualités",
            "bilan des pannes",
            "incidents pluie 2024",
            "top 5 engins",
            "voyages par mois 2026",
        ]
        response = (
            "Je n'ai pas pu répondre à cette question avec les données disponibles.\n"
            f"Exemples : {' | '.join(exemples)}\n"
            f"Colonnes disponibles : {', '.join(df.columns.tolist()[:10])}..."
        )
    return response

# ══════════════════════════════════════════════════════════════
# 13. BOUCLE INTERACTIVE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("   BI COPILOT INDUSTRIEL  v5 (générique + spécifique)")
    print("═" * 60)
    print(f"  Sites         : {len(SITES_DISPO)} | {', '.join(map(str, SITES_DISPO[:4]))}")
    print(f"  Produits      : {len(PRODUITS_DISPO)} | {', '.join(map(str, PRODUITS_DISPO[:4]))}")
    print(f"  Qualités      : {len(QUALITES_DISPO)} | {', '.join(map(str, QUALITES_DISPO[:4]))}")
    print(f"  Zones stock.  : {len(ZONES_DISPO)} | {', '.join(map(str, ZONES_DISPO[:4]))}")
    print(f"  Responsables  : {len(RESPONSABLES_DISPO)}")
    print(f"  Transporteurs : {len(TRANSPORTS_DISPO)}")
    print(f"  Engins        : {len(TRUCKS_DISPO)}")
    print(f"  Années        : {ANNEES_DISPO}")
    print(f"  Lignes        : {len(df):,}")
    print("─" * 60)
    print("  Commandes : 'exit', 'cols', 'sites', 'zones', 'engins', 'aide'")
    print("═" * 60 + "\n")

    AIDE = """
Questions supportées (formulation libre) :

  TONNAGE
    "tonnage total" | "tonnage 2026" | "tonnage jan 2026"
    "tonnage total bauxite 2024" | "tonnage Bénéné premier choix"

  PÉRIODES
    "T1 2024" | "S2 2025" | "semaine 12 2026"
    "tonnage par mois 2026"

  COMPARAISONS
    "T1 2024 vs T1 2023" | "comparer jan et fev 2026"

  AGRÉGATIONS PAR DIMENSION
    "tonnage par site"           "tonnage par produit 2024"
    "tonnage par qualité"        "tonnage par zone de stockage"
    "tonnage par responsable"    "tonnage par transporteur"
    "voyages par site 2024"

  DONNÉES TEXTUELLES
    "qui est responsable du site Bénéné ?"
    "quelles qualités à Bénéné en 2024"
    "liste des produits" | "liste des qualités"

  ENGINS
    "combien de tombereaux" | "liste engins" | "top 5 engins"
    "engins de type BENNE"

  ZONES DE STOCKAGE
    "top 10 zones" | "tonnage stock 4"

  VOYAGES
    "total voyages" | "voyages mars 2026" | "voyages par mois 2026"

  INCIDENTS / PANNES
    "bilan des pannes" | "incidents pluie"
    "incidents climatisation" | "combien d'incidents de pluie"

  CLASSEMENTS
    "top 5 sites" | "top 3 produits 2024"
"""

    while True:
        try:
            q = input("Question > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir.")
            break

        if not q:
            continue

        match q.lower():
            case "exit" | "quit":
                print("Au revoir.")
                break
            case "cols":
                print("Colonnes :", list(df.columns))
            case "sites":
                print("Sites :", SITES_DISPO)
            case "zones":
                print(f"Zones ({len(ZONES_DISPO)}) :", ZONES_DISPO[:20], "...")
            case "engins":
                print(f"Engins ({unique_trucks()}) :", list_engins()[:20])
            case "produits":
                print("Produits :", PRODUITS_DISPO)
            case "qualites" | "qualités":
                print("Qualités :", QUALITES_DISPO)
            case "responsables":
                print("Responsables :", RESPONSABLES_DISPO)
            case "aide" | "help":
                print(AIDE)
            case _:
                print("Réponse :", answer(q))
                print()
