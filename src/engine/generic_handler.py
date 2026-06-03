"""
src/engine/generic_handler.py — SmartGenericHandler v3

Handler générique paramétrique pour les tables non couvertes par des handlers dédiés.
Filet de sécurité pour les nouvelles tables uploadées : réponse utile immédiate.

Pourquoi pas de génération de code Python ?
  - Le routing (quelle question → quel handler) ne peut pas être auto-généré.
  - Le code généré est difficile à déboguer et nécessite une révision humaine.
  - Ce handler SQL dynamique couvre les cas d'usage essentiels sans ces risques.

Couverture par rapport aux handlers spécifiques (~25% de leurs capacités) :
  ✅ Couvert  : total, mensuel, trimestriel, annuel, catégorie, top-N, count, liste
  ✅ Couvert  : filtrage année, recherche LIKE sur colonnes texte, semestre
  ✅ Couvert  : sélection de colonne par pertinence question, tables référentiels
  ✅ Couvert  : questions de suivi contextuelles, alertes limites fonctionnelles
  ❌ Absent   : semaine ISO, date précise, métriques dérivées, requêtes multi-tables,
               CASE WHEN text mining, logique d'exclusion

Pour une table très interrogée, écrire un handler dédié reste la meilleure approche.

Score de confiance :
  Chaque table candidate reçoit un score 0..1 basé sur :
    - Mots du nom de table dans la question      (×0.40)
    - Mots de la description dans la question    (×0.20)
    - Tokens de noms de colonnes dans la question (×0.30, amplifié)
  Seuil : ≥ 0.35 pour être considéré.
  Le meilleur candidat est retenu (pas le premier).

Retour enrichi (v3) :
  handle_new_table() retourne un GenericHandlerResult avec :
    response         — texte Markdown
    response_type    — catégorie de réponse pour l'interface
    table            — table source
    confidence       — score de confiance (0..1)
    questions_suivi  — boutons contextuels pour affiner la question
    limit_notice     — alerte si une limite fonctionnelle a été atteinte
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime as _dt

import duckdb

from src.engine import schema_registry as _reg
from src.utils.text import norm as _norm

logger = logging.getLogger(__name__)


# ── Résultat enrichi ──────────────────────────────────────────────────────────

@dataclass
class GenericHandlerResult:
    """Résultat enrichi du SmartGenericHandler pour l'interface Streamlit."""
    response: str
    response_type: str               # "scalar"|"monthly"|"quarterly"|"semester"|"yearly"
                                     # |"grouped"|"count"|"list"|"search"|"summary"|"empty"
    table: str
    confidence: float
    questions_suivi: list[dict] = field(default_factory=list)
    limit_notice: str | None = None  # alerte limite fonctionnelle (None = aucune)


# ── Patterns de détection ──────────────────────────────────────────────────────

_GRANULARITY: list[tuple[str, list[str]]] = [
    ("monthly",   [r"par\s+mois", r"mensuel(?:le)?", r"mois\s+par\s+mois"]),
    ("quarterly", [r"par\s+trimestre", r"trimestriel(?:le)?", r"\bT[1-4]\b"]),
    ("semester",  [r"par\s+semestre", r"semestriel(?:le)?", r"\bS[12]\b"]),
    ("yearly",    [r"par\s+ann[eé]e", r"annuel(?:le)?", r"bilan\s+annuel",
                   r"ann[eé]e\s+par\s+ann[eé]e"]),
    ("weekly",    [r"par\s+semaine", r"hebdomadaire"]),
]

_COUNT_KW  = [r"\bcombien\b", r"\bnombre\s+de\b", r"\bcompter?\b"]
_TOP_PAT   = r"\btop\s*(\d+)\b|\b(\d+)\s+premiers?\b"
_LIST_KW   = [r"\bliste\b", r"\bdétail\b", r"\bdetail\b", r"\baffich\b", r"\bmontr\b"]

# Verbes d'existence / occurrence dans le texte
_EXISTENCE_KW = [r"\by\s+a-t-il\b", r"\bexiste\b", r"\boccurrence\b",
                 r"\btrouver\b", r"\bchercher\b", r"\bcontient\b"]

# G2 : défini ici (module-level) pour ne pas être recompilé à chaque appel
_SUMMARY_KW = [r"\bresum[eé]\b", r"\bbilan\b", r"\bsynth[eè]se\b",
               r"\bapercu\b", r"\baperçu\b", r"\bstatistique\b"]

# Patterns de noms de colonnes qui ressemblent à des identifiants techniques (G6)
_ID_COL_PATTERNS = re.compile(
    r"^(id|_id|num|numero|code|ref|reference|cle|key|pk|seq|sequence|rang|row)$"
)

CONFIDENCE_THRESHOLD = 0.35


# ── Pertinence d'une colonne vis-à-vis de la question ─────────────────────────

def _col_score(col_name: str, question_norm: str) -> int:
    """
    Score 0-10 : correspondance entre le nom de colonne et la question normalisée.
    Splitte sur '_' pour traiter "volume_m3" comme ["volume", "m3"].
    """
    cn = _norm(col_name).replace("_", " ")
    score = 0
    for word in cn.split():
        if len(word) >= 3 and re.search(rf"\b{re.escape(word)}\b", question_norm):
            score += 3
    # Bonus si le nom entier (sans underscores) apparaît dans la question
    if cn.strip() in question_norm:
        score += 4
    return min(score, 10)


def _best_qty_col(schema, question_norm: str) -> str | None:
    """Colonne numérique la plus pertinente pour la question.

    G6 : le fallback n'utilise plus num_cols[0] aveuglément —
    les colonnes qui ressemblent à des identifiants (id, code, ref…)
    sont exclues du fallback pour éviter de sommer des clés primaires.
    """
    num_cols = schema.numeric_cols()
    if not num_cols:
        return None
    scored = [(c, _col_score(c, question_norm)) for c in num_cols]
    best_score = max(s for _, s in scored)
    if best_score >= 3:
        return max(scored, key=lambda x: x[1])[0]
    # Fallback : rôle sémantique connu, sinon première colonne non-ID
    semantic = schema.col("quantity") or schema.col("hours")
    if semantic:
        return semantic
    non_id = [c for c in num_cols if not _ID_COL_PATTERNS.match(_norm(c))]
    return non_id[0] if non_id else num_cols[0]


def _best_cat_col(schema, question: str) -> str | None:
    """
    Colonne catégorielle pertinente si la question contient "par X".
    Sinon, retourne None (pas de groupement par catégorie demandé).
    """
    q = _norm(question)
    m = re.search(r"\bpar\s+(\w+)", q)
    if m:
        kw = m.group(1)
        for col in schema.varchar_cols():
            if kw in _norm(col):
                return col
    # Pas de "par X" explicite → pas de groupement par défaut
    return None


def _detect_granularity(question: str) -> str | None:
    q = _norm(question)
    for gname, patterns in _GRANULARITY:
        if any(re.search(p, q, re.I) for p in patterns):
            return gname
    return None


def _detect_top_n(question: str) -> int | None:
    m = re.search(_TOP_PAT, question, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    return None


# ── Formatage ─────────────────────────────────────────────────────────────────

_MOIS_ABBR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
               "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def _fmt_scalar(col: str, val, label: str, table: str) -> str:
    if val is None:
        return f"**{col}** ({label}) : _aucune donnée_\n\n_📋 {table}_"
    try:
        return f"**{col}** ({label}) : **{float(val):,.2f}**\n\n_📋 {table}_"
    except (TypeError, ValueError):
        return f"**{col}** ({label}) : **{val}**\n\n_📋 {table}_"


def _fmt_monthly(col: str, year: int, rows: list, table: str) -> str:
    lines = [f"**{col} — {year}**", ""]
    total = 0.0
    for row in rows:
        m_num, val = row[0], row[1]
        if val is None:
            continue
        nom = _MOIS_ABBR[int(m_num) - 1] if 1 <= int(m_num) <= 12 else str(m_num)
        lines.append(f"  {nom} : {float(val):,.2f}")
        total += float(val)
    lines += ["", f"  **Total : {total:,.2f}**"]
    return "\n".join(lines) + f"\n\n_📋 {table}_"


def _fmt_quarterly(col: str, year: int, rows: list, table: str) -> str:
    lines = [f"**{col} par trimestre — {year}**", ""]
    total = 0.0
    for q_num, val in rows:
        if val is None:
            continue
        lines.append(f"  T{q_num} : {float(val):,.2f}")
        total += float(val)
    lines += ["", f"  **Total : {total:,.2f}**"]
    return "\n".join(lines) + f"\n\n_📋 {table}_"


def _fmt_yearly(col: str, rows: list, table: str) -> str:
    lines = [f"**{col} par année**", ""]
    for yr, val in rows:
        if val is None:
            continue
        lines.append(f"  {int(yr)} : {float(val):,.2f}")
    return "\n".join(lines) + f"\n\n_📋 {table}_"


def _fmt_grouped(col_cat: str, col_qty: str, rows: list, label: str, table: str) -> str:
    lines = [f"**{col_qty} par {col_cat}** ({label})", ""]
    total = 0.0
    for cat, val in rows:
        if val is None:
            continue
        cat_s = str(cat) if cat is not None else "—"
        lines.append(f"  {cat_s} : {float(val):,.2f}")
        total += float(val)
    if rows:
        lines += ["", f"  **Total : {total:,.2f}**"]
    return "\n".join(lines) + f"\n\n_📋 {table}_"


def _fmt_count(table: str, nb: int, label: str, schema) -> str:
    desc     = schema.description()
    col_list = ", ".join(list(schema.col_info.keys())[:6])
    note     = f"\n_Colonnes : {col_list}{' …' if len(schema.col_info) > 6 else ''}_"
    return (f"**{desc}** ({label}) : **{nb:,}** enregistrements"
            + f"\n\n_📋 {table}_" + note)


def _fmt_list(table: str, rows: list, schema) -> str:
    desc  = schema.description()
    lines = [f"**{desc}** (aperçu)", ""]
    cols  = list(schema.col_info.keys())[:4]
    lines.append("  " + " | ".join(cols))
    lines.append("  " + " | ".join(["---"] * len(cols)))
    for row in rows[:15]:
        # G5 : échapper les "|" dans les valeurs pour ne pas casser le tableau Markdown
        cells = (str(v).replace("|", "\\|") if v is not None else "—" for v in row)
        lines.append("  " + " | ".join(cells))
    if len(rows) > 15:
        lines.append(f"  _… {len(rows) - 15} lignes supplémentaires_")
    return "\n".join(lines) + f"\n\n_📋 {table}_"


# ── Questions de suivi contextuelles ─────────────────────────────────────────

def _suggest_followups(
    question: str,
    schema,
    table: str,
    year: int | None,
    response_type: str,
    col_qty: str | None,
    col_cat: str | None,
    col_date: str | None,
) -> list[dict]:
    """
    Génère des questions de suivi contextuelles selon le type de réponse obtenu.
    Maximum 3 suggestions pour ne pas surcharger l'interface.
    """
    cur_year = _dt.now().year
    q_base   = question.rstrip("?").strip()
    desc     = schema.description()
    suivi: list[dict] = []

    if response_type == "empty":
        return [{"icone": "⚙️", "label": "Importer des données",
                 "prompt": "Comment importer des données dans Miny ?"}]

    if response_type == "scalar":
        if col_date and not year:
            suivi.append({"icone": "📅", "label": f"Par mois {cur_year}",
                          "prompt": f"{q_base} par mois en {cur_year}"})
            suivi.append({"icone": "📅", "label": "Par année",
                          "prompt": f"{q_base} par année"})
        elif col_date and year:
            suivi.append({"icone": "📅", "label": f"Par mois {year}",
                          "prompt": f"{q_base} par mois en {year}"})
            suivi.append({"icone": "📅", "label": f"Comparer {year - 1}",
                          "prompt": f"{q_base} en {year - 1}"})
        if col_cat:
            cat_label = col_cat.replace("_", " ").split("(")[0].strip()[:20]
            suivi.append({"icone": "📊", "label": f"Par {cat_label}",
                          "prompt": f"{q_base} par {col_cat}"})

    elif response_type == "monthly":
        if year:
            suivi.append({"icone": "📅", "label": f"Comparer {year - 1}",
                          "prompt": f"{q_base} en {year - 1}"})
        suivi.append({"icone": "📊", "label": "Par trimestre",
                      "prompt": f"{q_base} par trimestre" + (f" en {year}" if year else "")})
        if col_cat:
            cat_label = col_cat.replace("_", " ").split("(")[0].strip()[:20]
            suivi.append({"icone": "📊", "label": f"Par {cat_label}",
                          "prompt": f"{q_base} par {col_cat}"})

    elif response_type == "quarterly":
        if year:
            suivi.append({"icone": "📅", "label": f"Comparer {year - 1}",
                          "prompt": f"{q_base} en {year - 1}"})
        suivi.append({"icone": "📊", "label": "Par mois",
                      "prompt": f"{q_base} par mois" + (f" en {year}" if year else "")})

    elif response_type == "semester":
        if year:
            suivi.append({"icone": "📅", "label": f"Comparer {year - 1}",
                          "prompt": f"{q_base} en {year - 1}"})
        suivi.append({"icone": "📊", "label": "Par mois",
                      "prompt": f"{q_base} par mois" + (f" en {year}" if year else "")})

    elif response_type == "yearly":
        suivi.append({"icone": "📅", "label": f"Détail {cur_year}",
                      "prompt": f"{q_base} par mois en {cur_year}"})
        if col_cat:
            cat_label = col_cat.replace("_", " ").split("(")[0].strip()[:20]
            suivi.append({"icone": "📊", "label": f"Par {cat_label}",
                          "prompt": f"{q_base} par {col_cat}"})

    elif response_type == "grouped":
        if col_date:
            suivi.append({"icone": "📅", "label": f"Par mois {cur_year}",
                          "prompt": f"{q_base} par mois en {cur_year}"})
        suivi.append({"icone": "🔢", "label": f"Total {desc[:20]}",
                      "prompt": f"Total {desc}"})

    elif response_type == "count":
        suivi.append({"icone": "📋", "label": "Voir la liste",
                      "prompt": f"Liste {desc}"})
        if col_date:
            suivi.append({"icone": "📅", "label": f"En {cur_year}",
                          "prompt": f"{q_base} en {cur_year}"})

    elif response_type == "list":
        if col_qty:
            qty_label = col_qty.replace("_", " ").split("(")[0].strip()[:25]
            suivi.append({"icone": "🔢", "label": f"Total {qty_label}",
                          "prompt": f"Total {col_qty} de {desc}"})
        if col_date:
            suivi.append({"icone": "📅", "label": f"En {cur_year}",
                          "prompt": f"{q_base} en {cur_year}"})

    elif response_type == "search":
        suivi.append({"icone": "📋", "label": "Voir toutes les lignes",
                      "prompt": f"Liste {desc}"})
        if col_date:
            suivi.append({"icone": "📅", "label": f"En {cur_year}",
                          "prompt": f"{q_base} en {cur_year}"})

    elif response_type == "summary":
        if col_date:
            suivi.append({"icone": "📅", "label": f"Par mois {cur_year}",
                          "prompt": f"{q_base} par mois en {cur_year}"})
        suivi.append({"icone": "📋", "label": "Voir la liste",
                      "prompt": f"Liste {desc}"})

    return suivi[:3]


# ── Handler principal ─────────────────────────────────────────────────────────

class SmartGenericHandler:
    """
    Handler générique intelligent paramétré par le schéma d'une table.

    Ne génère pas de code Python — répond dynamiquement via SQL basé sur
    l'analyse du schéma + la question.

    v3 : expose _handle_internal() retournant (text, type, notice, ctx)
         et handle_full() retournant un GenericHandlerResult enrichi
         avec questions de suivi et alertes de limite.
    """

    def __init__(self, table: str) -> None:
        self.table = table

    # ── Score de confiance ────────────────────────────────────────────────────

    def confidence(self, question: str, schema) -> float:
        """
        Score 0..1 estimant la pertinence de cette table pour la question.

        Trois signaux complémentaires pour réduire les faux positifs :
          - nom de table             (poids 0.40)
          - description sémantique   (poids 0.20)
          - noms de colonnes         (poids 0.30, amplifié si plusieurs matches)

        Corrections vs v1 :
          - len >= 3 (inclut "eau", "log"…)
          - split sur "_" pour nom de table, description, colonnes
          - substring match pour colonnes (couvre les pluriels : "equipements" ⊃ "equipement")
          - amplification du signal colonnes : 1/3 des colonnes matchées → score max
        """
        q = _norm(question)

        # Signal 1 : mots du nom de table (split sur _ inclus)
        tbl_words = [
            w for w in self.table.replace("_", " ").split()
            if len(w) >= 3
        ]
        s1 = 0.0
        if tbl_words:
            matched = sum(
                1 for w in tbl_words
                if re.search(rf"\b{re.escape(_norm(w))}\b", q)
            )
            s1 = 0.40 * (matched / len(tbl_words))

        # Signal 2 : description sémantique (split sur _ pour les nouvelles tables)
        raw_desc = schema.description().lower().replace("_", " ")
        desc_words = [w for w in raw_desc.split() if len(w) >= 3]
        s2 = 0.0
        if desc_words:
            matched = sum(1 for w in desc_words if _norm(w) in q)
            s2 = 0.20 * (matched / len(desc_words))

        # Signal 3 : noms de colonnes (split sur _, substring pour couvrir pluriels)
        col_unique: set[str] = set()
        for col in schema.col_info:
            for w in _norm(col).replace("_", " ").split():
                if len(w) >= 3:
                    col_unique.add(w)
        s3 = 0.0
        if col_unique:
            # substring match : "equipement" in "equipements" → True
            matched_set = {w for w in col_unique if w in q}
            ratio = len(matched_set) / len(col_unique)
            # Amplification : 33% des tokens matchés → signal maximal
            s3 = 0.30 * min(ratio * 3, 1.0)

        return min(s1 + s2 + s3, 1.0)

    # ── Réponse interne ───────────────────────────────────────────────────────

    def _handle_internal(
        self,
        con: duckdb.DuckDBPyConnection,
        question: str,
        year: int | None = None,
    ) -> tuple[str | None, str, str | None, dict]:
        """
        Retourne (text, response_type, limit_notice, ctx).

        ctx contient {col_qty, col_cat, col_date, granularity} pour la
        génération de questions de suivi sans re-calculer le schéma.
        """
        schema = _reg.get_or_build(con, self.table)
        if not schema:
            return None, "none", None, {}

        # G3 : valider year — rejeter les valeurs hors de la plage attendue
        if year is not None and (not isinstance(year, int) or not 1900 <= year <= 2200):
            logger.warning("SmartGenericHandler: year invalide %r — ignoré", year)
            year = None

        # G4 : table vide → réponse explicite immédiate
        try:
            row_count = con.execute(f'SELECT COUNT(*) FROM "{self.table}"').fetchone()[0]
            if row_count == 0:
                text = (f"**{schema.description()}** : la table `{self.table}` "
                        f"ne contient aucune donnée pour l'instant.\n\n_📋 {self.table}_")
                return text, "empty", None, {}
        except Exception:
            pass

        q_norm      = _norm(question)
        col_date    = schema.col("date")
        col_qty     = _best_qty_col(schema, q_norm)
        col_cat     = _best_cat_col(schema, question)
        label       = str(year) if year else "toutes périodes"
        granularity = _detect_granularity(question)

        ctx = {
            "col_qty": col_qty, "col_cat": col_cat,
            "col_date": col_date, "granularity": granularity,
        }

        # ── Alertes de limite fonctionnelle ───────────────────────────────────
        limit_notice: str | None = None
        if granularity and not col_date:
            limit_notice = (
                "⚠️ Filtrage temporel demandé, mais aucune colonne date n'a été "
                "reconnue dans cette table — résultat sur toutes périodes."
            )
        elif granularity in ("quarterly", "semester") and col_date and not year:
            gran_fr = "trimestriel" if granularity == "quarterly" else "semestriel"
            limit_notice = (
                f"💡 Pour un résultat {gran_fr}, précisez l'année. "
                f"Ex : *{question} {_dt.now().year}*"
            )
        else:
            # Ambiguïté sur la colonne quantitative (plusieurs colonnes disponibles)
            num_cols = schema.numeric_cols()
            if len(num_cols) > 2 and col_qty:
                others = [c for c in num_cols if c != col_qty][:2]
                limit_notice = (
                    f"💡 Plusieurs mesures disponibles : **{col_qty}** (utilisée ici)"
                    + (f", {', '.join(others)}…" if others else "")
                    + " — précisez la colonne pour un résultat ciblé."
                )

        where_parts: list[str] = []
        if year and col_date:
            where_parts.append(f'YEAR("{col_date}") = {year}')
        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # ── Liste / détail ─────────────────────────────────────────────────────
        if any(re.search(p, question, re.I) for p in _LIST_KW) and not col_qty:
            try:
                cols_sel = ", ".join(
                    f'"{c}"' for c in list(schema.col_info.keys())[:4]
                )
                rows = con.execute(
                    f"SELECT {cols_sel} FROM \"{self.table}\" {where} LIMIT 20"
                ).fetchall()
                return _fmt_list(self.table, rows, schema), "list", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler list error: %s", exc)

        # ── Top-N ─────────────────────────────────────────────────────────────
        top_n = _detect_top_n(question)
        if top_n and col_qty:
            cat_for_top = col_cat or schema.col("equipment") or schema.col("category")
            if cat_for_top:
                try:
                    rows = con.execute(f"""
                        SELECT "{cat_for_top}", SUM("{col_qty}") AS val
                        FROM "{self.table}" {where}
                        GROUP BY 1 ORDER BY 2 DESC LIMIT {top_n}
                    """).fetchall()
                    if rows:
                        return (_fmt_grouped(cat_for_top, col_qty, rows, label, self.table),
                                "grouped", limit_notice, ctx)
                except Exception as exc:
                    logger.debug("SmartGenericHandler top-N error: %s", exc)

        # ── Groupement par catégorie ───────────────────────────────────────────
        if col_cat and col_qty and not granularity:
            try:
                rows = con.execute(f"""
                    SELECT "{col_cat}", SUM("{col_qty}") AS val
                    FROM "{self.table}" {where}
                    GROUP BY 1 ORDER BY 2 DESC
                """).fetchall()
                if rows:
                    return (_fmt_grouped(col_cat, col_qty, rows, label, self.table),
                            "grouped", limit_notice, ctx)
            except Exception as exc:
                logger.debug("SmartGenericHandler grouped error: %s", exc)

        # ── Mensuel ───────────────────────────────────────────────────────────
        if granularity == "monthly" and col_qty and col_date:
            if year:
                try:
                    rows = con.execute(f"""
                        SELECT MONTH("{col_date}"), SUM("{col_qty}")
                        FROM "{self.table}" {where}
                        GROUP BY 1 ORDER BY 1
                    """).fetchall()
                    if rows:
                        return _fmt_monthly(col_qty, year, rows, self.table), "monthly", limit_notice, ctx
                except Exception as exc:
                    logger.debug("SmartGenericHandler monthly error: %s", exc)
            # Sans année : total par mois toutes années
            try:
                rows = con.execute(f"""
                    SELECT YEAR("{col_date}"), MONTH("{col_date}"), SUM("{col_qty}")
                    FROM "{self.table}"
                    GROUP BY 1, 2 ORDER BY 1, 2
                """).fetchall()
                if rows:
                    lines = [f"**{col_qty} par mois (toutes années)**", ""]
                    for yr, m_num, val in rows:
                        if val is None:
                            continue
                        nom = _MOIS_ABBR[int(m_num) - 1] if 1 <= int(m_num) <= 12 else str(m_num)
                        lines.append(f"  {int(yr)}/{nom} : {float(val):,.2f}")
                    text = "\n".join(lines) + f"\n\n_📋 {self.table}_"
                    return text, "monthly", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler monthly-all error: %s", exc)

        # ── Par trimestre ─────────────────────────────────────────────────────
        if granularity == "quarterly" and col_qty and col_date and year:
            try:
                rows = con.execute(f"""
                    SELECT QUARTER("{col_date}"), SUM("{col_qty}")
                    FROM "{self.table}" {where}
                    GROUP BY 1 ORDER BY 1
                """).fetchall()
                if rows:
                    return _fmt_quarterly(col_qty, year, rows, self.table), "quarterly", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler quarterly error: %s", exc)

        # ── Par semestre ──────────────────────────────────────────────────────
        if granularity == "semester" and col_qty and col_date and year:
            try:
                rows = con.execute(f"""
                    SELECT CASE WHEN MONTH("{col_date}") <= 6 THEN 1 ELSE 2 END AS sem,
                           SUM("{col_qty}") AS val
                    FROM "{self.table}" {where}
                    GROUP BY 1 ORDER BY 1
                """).fetchall()
                if rows:
                    _SEM = {1: "Jan–Juin", 2: "Juil–Déc"}
                    lines = [f"**{col_qty} par semestre — {year}**", ""]
                    total = 0.0
                    for s_num, val in rows:
                        if val is None:
                            continue
                        lines.append(f"  S{s_num} ({_SEM.get(s_num, '')}) : {float(val):,.2f}")
                        total += float(val)
                    lines += ["", f"  **Total : {total:,.2f}**"]
                    text = "\n".join(lines) + f"\n\n_📋 {self.table}_"
                    return text, "semester", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler semester error: %s", exc)

        # ── Par année ─────────────────────────────────────────────────────────
        if granularity == "yearly" and col_qty and col_date:
            try:
                rows = con.execute(f"""
                    SELECT YEAR("{col_date}"), SUM("{col_qty}")
                    FROM "{self.table}"
                    GROUP BY 1 ORDER BY 1
                """).fetchall()
                if rows:
                    return _fmt_yearly(col_qty, rows, self.table), "yearly", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler yearly error: %s", exc)

        # ── Recherche texte (LIKE) sur colonnes texte ─────────────────────────
        if any(re.search(p, question, re.I) for p in _EXISTENCE_KW):
            obs_cols = schema.varchar_cols()
            if obs_cols:
                _stop = {"pour", "dans", "avec", "cette", "annee", "mois", "semaine",
                         "table", "donnee", "données", "quelle", "quels", "liste",
                         "combien", "nombre", "total", "tous", "toutes"}
                q_words = [
                    w for w in q_norm.split()
                    if len(w) > 3 and not re.match(r"^\d+$", w) and w not in _stop
                ]
                tbl_words_set = {_norm(w) for w in self.table.replace("_", " ").split()}
                search_terms = [w for w in q_words if w not in tbl_words_set][:3]
                if search_terms:
                    col_obs = schema.col("observation") or obs_cols[0]
                    # G1 : paramètres DuckDB (?) au lieu d'interpolation de chaîne —
                    # évite l'injection SQL quel que soit le contenu des termes.
                    placeholders = " OR ".join(
                        f'LOWER("{col_obs}") LIKE ?' for _ in search_terms
                    )
                    params = [f"%{t}%" for t in search_terms]
                    try:
                        nb = con.execute(
                            f'SELECT COUNT(*) FROM "{self.table}" WHERE ({placeholders})',
                            params,
                        ).fetchone()[0]
                        term_str = ", ".join(f"«{t}»" for t in search_terms)
                        text = (f"**{schema.description()}** : **{nb:,}** ligne(s) "
                                f"contenant {term_str}\n\n_📋 {self.table}_")
                        return text, "search", limit_notice, ctx
                    except Exception as exc:
                        logger.debug("SmartGenericHandler LIKE error: %s", exc)

        # ── Multi-colonnes numériques : résumé toutes colonnes qty ─────────────
        if any(re.search(p, question, re.I) for p in _SUMMARY_KW):
            num_cols = schema.numeric_cols()
            if len(num_cols) > 1:
                try:
                    aggs = ", ".join(f'SUM("{c}") AS "{c}"' for c in num_cols[:5])
                    row = con.execute(
                        f'SELECT {aggs} FROM "{self.table}" {where}'
                    ).fetchone()
                    if row:
                        lines = [f"**{schema.description()}** ({label})", ""]
                        for col_n, val in zip(num_cols[:5], row):
                            v_str = f"{float(val):,.2f}" if val is not None else "—"
                            lines.append(f"  {col_n} : **{v_str}**")
                        text = "\n".join(lines) + f"\n\n_📋 {self.table}_"
                        # Le résumé montre toutes les colonnes → pas d'alerte ambiguïté
                        return text, "summary", None, ctx
                except Exception as exc:
                    logger.debug("SmartGenericHandler summary error: %s", exc)

        # ── Comptage ──────────────────────────────────────────────────────────
        if any(re.search(p, question, re.I) for p in _COUNT_KW):
            try:
                nb = con.execute(
                    f'SELECT COUNT(*) FROM "{self.table}" {where}'
                ).fetchone()[0]
                return _fmt_count(self.table, nb, label, schema), "count", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler count error: %s", exc)

        # ── Total scalaire (fallback principal) ───────────────────────────────
        if col_qty:
            try:
                val = con.execute(
                    f'SELECT SUM("{col_qty}") FROM "{self.table}" {where}'
                ).fetchone()[0]
                # Afficher aussi les années disponibles comme contexte
                years_avail = _reg.available_years(con, self.table)
                note = (f"\n_ℹ️ Requête générique — table `{self.table}`. "
                        f"Précisez la colonne pour plus de détails._")
                if years_avail and not year:
                    note += f"\n_Années disponibles : {', '.join(map(str, years_avail))}_"
                return _fmt_scalar(col_qty, val, label, self.table) + note, "scalar", limit_notice, ctx
            except Exception as exc:
                logger.debug("SmartGenericHandler scalar error: %s", exc)

        # ── Référentiel sans quantité : count + colonnes ───────────────────────
        try:
            nb = con.execute(f'SELECT COUNT(*) FROM "{self.table}" {where}').fetchone()[0]
            return _fmt_count(self.table, nb, label, schema), "count", limit_notice, ctx
        except Exception as exc:
            logger.debug("SmartGenericHandler ref-count error: %s", exc)

        return None, "none", None, ctx

    # ── Interface publique ────────────────────────────────────────────────────

    def handle(
        self,
        con: duckdb.DuckDBPyConnection,
        question: str,
        year: int | None = None,
    ) -> str | None:
        """Rétrocompatibilité : retourne uniquement le texte (sans méta-données)."""
        text, _, _, _ = self._handle_internal(con, question, year)
        return text

    def handle_full(
        self,
        con: duckdb.DuckDBPyConnection,
        question: str,
        year: int | None = None,
        confidence: float = 0.0,
    ) -> GenericHandlerResult | None:
        """
        Retourne un GenericHandlerResult enrichi avec :
          - response       : texte Markdown
          - questions_suivi: boutons de suivi contextuels
          - limit_notice   : alerte si une limite fonctionnelle a été atteinte
          - confidence     : score de confiance (pour signaler une faible certitude)
        """
        schema = _reg.get_or_build(con, self.table)
        if not schema:
            return None

        text, rtype, limit_notice, ctx = self._handle_internal(con, question, year)
        if text is None:
            return None

        questions_suivi = _suggest_followups(
            question, schema, self.table, year, rtype,
            ctx.get("col_qty"), ctx.get("col_cat"), ctx.get("col_date"),
        )

        return GenericHandlerResult(
            response=text,
            response_type=rtype,
            table=self.table,
            confidence=confidence,
            questions_suivi=questions_suivi,
            limit_notice=limit_notice,
        )


# ── Registre ──────────────────────────────────────────────────────────────────

_registry: dict[str, SmartGenericHandler] = {}


def _get_handler(table: str) -> SmartGenericHandler:
    if table not in _registry:
        _registry[table] = SmartGenericHandler(table)
    return _registry[table]


def invalidate(table: str | None = None) -> None:
    """Vide le registre (toutes tables ou une seule) après rechargement."""
    if table:
        _registry.pop(table, None)
    else:
        _registry.clear()


# ── Point d'entrée public ─────────────────────────────────────────────────────

def handle_new_table(
    con: duckdb.DuckDBPyConnection,
    question: str,
    handled_tables: frozenset,
    year: int | None = None,
) -> GenericHandlerResult | None:
    """
    Fallback générique intelligent — appelé depuis analytics._handle_single().

    Parcourt toutes les tables non couvertes par des handlers dédiés,
    calcule un score de confiance pour chacune, et retourne un
    GenericHandlerResult avec réponse + questions de suivi + alerte limite.

    Args:
        con            : connexion DuckDB active.
        question       : question normalisée (minuscules, sans accents).
        handled_tables : tables déjà couvertes par des handlers dédiés.
        year           : année extraite de la question, ou None.

    Returns:
        GenericHandlerResult ou None si aucune table n'est suffisamment pertinente.
    """
    try:
        all_tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return None

    best_conf    = 0.0
    best_handler: SmartGenericHandler | None = None

    for tbl in all_tables:
        if tbl in handled_tables:
            continue
        schema = _reg.get_or_build(con, tbl)
        if not schema:
            continue
        handler = _get_handler(tbl)
        conf    = handler.confidence(question, schema)
        if conf > best_conf:
            best_conf    = conf
            best_handler = handler

    if best_handler is None or best_conf < CONFIDENCE_THRESHOLD:
        return None

    logger.debug(
        "SmartGenericHandler: table=%s conf=%.2f question=%r",
        best_handler.table, best_conf, question[:60],
    )
    return best_handler.handle_full(con, question, year, confidence=best_conf)
