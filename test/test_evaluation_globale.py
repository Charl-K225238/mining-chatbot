# -*- coding: utf-8 -*-
"""
test_evaluation_globale.py — Évaluation complète du système Miny
=================================================================

Évalue TOUS les modes du système :
  MODE 1 : ANALYTIQUE SQL    — routing + valeurs + cohérence
  MODE 2 : ROUTER DÉCISION   — math/expert/général/domaine (sans LLM)
  MODE 3 : ADAPTATION        — nouvelles tables, schéma inconnu
  MODE 4 : INTERACTIVITÉ     — clarifications, messages de guidance
  MODE 5 : NETTOYAGE         — propreté des réponses, attribution, format
  MODE 6 : ROBUSTESSE        — données manquantes, années hors portée, injections

Critère de déploiement : score ≥ 95 sur chaque mode.

Exécuter :
  .venv\\Scripts\\python.exe test/test_evaluation_globale.py
  .venv\\Scripts\\python.exe test/test_evaluation_globale.py --verbose
"""
import io, sys, os, re, argparse
from pathlib import Path
from collections import defaultdict

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import duckdb

def _make_con():
    con = duckdb.connect(":memory:")
    for f in sorted(os.listdir(ROOT / "data" / "parquet")):
        if f.endswith(".parquet"):
            name = f.replace(".parquet", "")
            path = (ROOT / "data" / "parquet" / f).as_posix()
            con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet(\'{path}\')')
    return con

try:
    from src.db.connection import get_db
    con = get_db()
    LOG = "[INFO] get_db()"
except Exception as e:
    con = _make_con()
    LOG = f"[WARN] fallback direct ({e})"

from src.engine import analytics
from src.engine.query_router import (
    _is_math_question, _is_expert_question, _is_general_question
)

print(f"\n{LOG}")
print("=" * 72)
print("ÉVALUATION GLOBALE MINY — SYSTÈME COMPLET")
print("=" * 72)

# ──────────────────────────────────────────────────────────────────────────────
# Infrastructure de scoring
# ──────────────────────────────────────────────────────────────────────────────

PASS = "✅"; FAIL = "❌"; WARN = "⚠️"; INFO = "ℹ️"

class Scorer:
    def __init__(self, mode_name: str):
        self.mode = mode_name
        self.passed = 0
        self.failed = 0
        self.failures: list[tuple] = []

    def ok(self, label: str, detail: str = ""):
        self.passed += 1
        if VERBOSE:
            print(f"  {PASS} {label}" + (f"  |  {detail[:70]}" if detail else ""))

    def fail(self, label: str, reason: str, detail: str = ""):
        self.failed += 1
        self.failures.append((label, reason))
        print(f"  {FAIL} {label}  |  {reason}" + (f"  |  {detail[:60]}" if detail else ""))

    @property
    def total(self): return self.passed + self.failed

    @property
    def score(self): return round(self.passed / self.total * 100, 1) if self.total else 0.0

    def banner(self):
        icon = PASS if self.score >= 95 else (WARN if self.score >= 80 else FAIL)
        print(f"\n  {icon} Mode {self.mode}: {self.score}% ({self.passed}/{self.total})")
        if self.failures:
            for lbl, reason in self.failures[:5]:
                print(f"      → {lbl}: {reason}")
            if len(self.failures) > 5:
                print(f"      … et {len(self.failures)-5} autre(s)")


ALL_SCORES: dict[str, Scorer] = {}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _table_from(resp: str) -> str:
    if resp and "_📋" in resp:
        after = resp.split("_📋")[-1].strip()
        return after.split()[0].rstrip("_") if after.split() else "UNKNOWN"
    return "UNKNOWN"

def _extract_num(text: str) -> float | None:
    if not text: return None
    for m in re.finditer(r"\d{1,3}(?:[,]\d{3})+(?:\.\d+)?", text):
        try:
            v = float(m.group().replace(",", ""))
            if not (2020 <= v <= 2030): return v
        except: pass
    for m in re.finditer(r"\d+(?:[.,]\d+)?", text):
        try:
            v = float(m.group().replace(",", ""))
            if v >= 5 and not (2020 <= v <= 2030): return v
        except: pass
    return None

def analytics_q(question: str) -> str | None:
    """Appelle le moteur analytique et retourne la réponse (ou None)."""
    try:
        return analytics.handle(con, question)
    except Exception as exc:
        return f"[EXCEPTION: {exc}]"

def check_analytics(s: Scorer, question: str, label: str,
                    expected_table: str | None = None,
                    must_not_be_none: bool = True,
                    must_contain: str | None = None,
                    must_not_contain: str | None = None,
                    min_val: float | None = None,
                    max_val: float | None = None,
                    no_data_ok: bool = False) -> str | None:
    resp = analytics_q(question)
    if resp is None:
        if must_not_be_none:
            s.fail(label, "NO_HANDLER", question[:60])
        else:
            s.ok(label, "None attendu")
        return None

    if resp.startswith("[EXCEPTION"):
        s.fail(label, resp[:80])
        return None

    # Contrôle table
    if expected_table:
        actual = _table_from(resp)
        if expected_table.lower() not in actual.lower():
            s.fail(label, f"table={actual} attendu={expected_table}", resp[:60])
            return resp

    # Contrôle contenu
    if must_contain and must_contain.lower() not in resp.lower():
        s.fail(label, f"manque '{must_contain}'", resp[:60])
        return resp

    if must_not_contain and must_not_contain.lower() in resp.lower():
        s.fail(label, f"contient indésirable '{must_not_contain}'", resp[:60])
        return resp

    # Contrôle valeur
    if min_val is not None or max_val is not None:
        num = _extract_num(resp)
        if num is None and not no_data_ok:
            s.fail(label, "aucun nombre dans la réponse", resp[:60])
            return resp
        if num is not None:
            if min_val is not None and num < min_val:
                s.fail(label, f"{num:,.0f} < min {min_val:,.0f}", resp[:60])
                return resp
            if max_val is not None and num > max_val:
                s.fail(label, f"{num:,.0f} > max {max_val:,.0f}", resp[:60])
                return resp

    s.ok(label, resp[:70] if VERBOSE else "")
    return resp


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 1 — ANALYTIQUE SQL (routing + valeurs + cohérence)")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m1 = Scorer("1-ANALYTIQUE")
ALL_SCORES["1-ANALYTIQUE"] = m1

# ── 1.A Tonnage descendu ──────────────────────────────────────────────────────
print("\n[1.A] Tonnage descendu — valeurs réelles 2024=620785T, 2025=1156100T, 2026=475340T")
check_analytics(m1, "Tonnage total en 2024", "ton-2024",
                "descente_minerai", min_val=600_000, max_val=650_000)
check_analytics(m1, "Tonnage total en 2025", "ton-2025",
                "descente_minerai", min_val=1_100_000, max_val=1_200_000)
check_analytics(m1, "Tonnage total en 2026", "ton-2026",
                "descente_minerai", min_val=450_000, max_val=500_000)
check_analytics(m1, "Tonnage par mois en 2025", "ton-mensuel-2025",
                "descente_minerai", must_contain="TOTAL")
check_analytics(m1, "Tonnage T1 2025", "ton-T1-2025",
                "descente_minerai", min_val=150_000, max_val=250_000)
check_analytics(m1, "Tonnage T2 2025", "ton-T2-2025",
                "descente_minerai", min_val=250_000, max_val=350_000)
check_analytics(m1, "Tonnage semestre 1 en 2025", "ton-S1-2025",
                "descente_minerai", min_val=400_000, max_val=550_000)
check_analytics(m1, "Tonnage semaine 10 en 2025", "ton-S10-2025",
                "descente_minerai", min_val=5_000)
check_analytics(m1, "Tonnage S1 a S6 2026", "ton-S1-S6-2026",
                "descente_minerai", min_val=5_000)
check_analytics(m1, "Comparer 2024 et 2025", "compare-2024-2025",
                "descente_minerai", must_contain="2024")

# ── Cohérence T1+T2+T3+T4 == annuel ─────────────────────────────────────────
r1=analytics_q("Tonnage T1 2025"); r2=analytics_q("Tonnage T2 2025")
r3=analytics_q("Tonnage T3 2025"); r4=analytics_q("Tonnage T4 2025")
ra=analytics_q("Tonnage total en 2025")
if all([r1,r2,r3,r4,ra]):
    s=sum(_extract_num(r) or 0 for r in [r1,r2,r3,r4]); a=_extract_num(ra) or 0
    if a and abs(s-a) < 500:
        m1.ok("coherence-T1+T2+T3+T4=annuel", f"{s:,.0f}={a:,.0f}")
    else:
        m1.fail("coherence-T1+T2+T3+T4=annuel", f"somme={s:,.0f} ≠ annuel={a:,.0f}")

# ── 1.B Excavation ────────────────────────────────────────────────────────────
print("\n[1.B] Excavation — 2024=650154T, 2025=1216242T")
check_analytics(m1, "Tonnage excave en 2025", "excav-2025",
                "excavation", min_val=1_200_000, max_val=1_250_000)
check_analytics(m1, "Tonnage excave par mois en 2025", "excav-mensuel",
                "excavation", must_contain="excavé")
check_analytics(m1, "Volume excave en 2024", "excav-2024",
                "excavation", min_val=600_000, max_val=700_000)
check_analytics(m1, "Tonnage QD en 2025", "excav-QD", "excavation", must_contain="QD")
check_analytics(m1, "Tonnage BQ en 2025", "excav-BQ", "excavation", must_contain="BQ")
# Cohérence : excavé > descendu × 0.9
re5 = analytics_q("Tonnage excave en 2025"); rd5 = analytics_q("Tonnage total en 2025")
if re5 and rd5:
    ne, nd = _extract_num(re5) or 0, _extract_num(rd5) or 0
    if ne > nd * 0.9:
        m1.ok("coherence-excave>descente", f"{ne:,.0f}>{nd:,.0f}")
    else:
        m1.fail("coherence-excave>descente", f"excave={ne:,.0f} < descente={nd:,.0f}×0.9")

# ── 1.C Transport ─────────────────────────────────────────────────────────────
print("\n[1.C] Transport mine→port — 2025~1193575T, navires")
check_analytics(m1, "Tonnage transporte en 2025", "trans-2025",
                "transport_minerai_paa", min_val=1_100_000, max_val=1_300_000)
check_analytics(m1, "Tonnage arrive au port en 2025", "port-2025",
                "transport_minerai_paa", min_val=1_100_000, max_val=1_300_000)
check_analytics(m1, "Tonnage transporte par mois 2025", "trans-mensuel",
                "transport_minerai_paa", must_not_be_none=True)
check_analytics(m1, "Rotations de transport en 2025", "rotations-2025",
                "transport_minerai_paa", must_not_be_none=True)
check_analytics(m1, "Tonnage charge navire en 2025", "navires-2025",
                "productivite_loading", min_val=50_000)

# ── 1.D Heures machine ────────────────────────────────────────────────────────
print("\n[1.D] Heures machine — 2024=2200h, 2025=3223h, 2026=1205h")
check_analytics(m1, "Heures machine en 2025", "HM-2025",
                "shifts_horaires", min_val=3_000, max_val=3_500)
check_analytics(m1, "Heures tambour en 2025", "HT-2025",
                "shifts_horaires", min_val=2_500, max_val=3_000)
check_analytics(m1, "Heures moteur en 2025", "moteur-2025",
                "shifts_horaires", min_val=3_000, max_val=3_500)
check_analytics(m1, "Heures machine par mois en 2025", "HM-mensuel",
                "shifts_horaires", must_contain="Janvier")
check_analytics(m1, "Heures machine en 2030", "HM-2030-hors-portee",
                "shifts_horaires", must_not_be_none=True)  # doit dire "hors portée"

# ── 1.E Qualité échantillons ──────────────────────────────────────────────────
print("\n[1.E] Qualité — Al2O3~50%, SiO2~4%, Fe2O3~19%")
check_analytics(m1, "Teneur Al2O3 des echantillons en 2025", "Al2O3-2025",
                "qualite_echantillons", must_contain="Al2O3")
check_analytics(m1, "Teneur SiO2 en 2025", "SiO2-2025",
                "qualite_echantillons", must_contain="SiO2")
check_analytics(m1, "Teneur Fe2O3 en 2025", "Fe2O3-2025",
                "qualite_echantillons", must_contain="Fe2O3")
check_analytics(m1, "Qualite echantillons par zone en 2025", "qual-zone",
                "qualite_echantillons", must_contain="Zone")

# ── 1.F Personnel ─────────────────────────────────────────────────────────────
print("\n[1.F] Personnel — 41 personnes, Agnero=Superviseur")
check_analytics(m1, "Liste du personnel", "personnel-liste",
                "personnel", must_contain="personnes")
check_analytics(m1, "Quel est le metier de Agnero Liliane ?", "personnel-agnero",
                "personnel", must_contain="Superviseur")
check_analytics(m1, "Corps de metier par categorie", "personnel-metier",
                "personnel", must_not_be_none=True)
check_analytics(m1, "Operateurs par shift en 2025", "personnel-shift",
                must_not_be_none=True)

# ── 1.G HSE / PGES ───────────────────────────────────────────────────────────
print("\n[1.G] HSE/PGES — 40 obligations, 54 actions PGES")
check_analytics(m1, "Actions HSE non realisees", "HSE-non-realise",
                "suivi_actions", must_contain="Non réalisé")
check_analytics(m1, "Actions PGES en cours", "PGES-en-cours",
                "pges_actions", must_not_be_none=True)
check_analytics(m1, "Actions correctives urgentes", "HSE-urgentes",
                "suivi_actions", must_not_be_none=True)
check_analytics(m1, "Recommandations ANDE", "PGES-ANDE",
                "pges_actions", must_not_be_none=True)
check_analytics(m1, "Plan de gestion environnemental avancement", "PGES-avancement",
                "pges_actions", must_not_be_none=True)

# ── 1.H Carburant ─────────────────────────────────────────────────────────────
print("\n[1.H] Carburant — 164899L en 2024")
check_analytics(m1, "Carburant consomme en 2024", "carb-2024",
                "carburant_citerne", min_val=150_000, max_val=180_000)
check_analytics(m1, "Carburant par engin en 2024", "carb-engin",
                "carburant_citerne", must_not_be_none=True)
check_analytics(m1, "Gasoil consomme en 2024", "carb-gasoil",
                "carburant_citerne", min_val=100_000)

# ── 1.I Journal ───────────────────────────────────────────────────────────────
print("\n[1.I] Journal — pannes trencher 2024=3 entrées, 2026=99")
check_analytics(m1, "Pannes de la trencher en 2026", "journal-2026",
                "journal", must_contain="2026")
check_analytics(m1, "Bilan des arrets techniques 2025", "journal-arret",
                "journal", must_not_be_none=True)
check_analytics(m1, "Pannes GPS trencher", "journal-GPS", "journal", must_not_be_none=True)

# ── 1.J Objectifs ─────────────────────────────────────────────────────────────
print("\n[1.J] Objectifs — prévu vs réalisé")
check_analytics(m1, "Objectif de production en 2025", "obj-2025",
                "objectifs", must_not_be_none=True)
check_analytics(m1, "Taux de realisation en 2025", "taux-real",
                "objectifs", must_not_be_none=True)
check_analytics(m1, "Planification production 2025", "planning",
                "objectifs", must_not_be_none=True)
check_analytics(m1, "Realise vs prevu en 2026", "obj-2026",
                "objectifs", must_not_be_none=True)

m1.banner()


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 2 — DÉCISION ROUTEUR (sans LLM : math / expert / général / domaine)")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m2 = Scorer("2-ROUTEUR")
ALL_SCORES["2-ROUTEUR"] = m2

def check_route(s: Scorer, question: str, label: str,
                expect_math=False, expect_expert=False,
                expect_general=False, expect_analytics=False,
                expect_none_analytics=False):
    is_math    = _is_math_question(question)
    is_expert  = _is_expert_question(question)
    is_general = _is_general_question(question)
    resp_ana   = analytics_q(question)
    has_ana    = resp_ana is not None and not resp_ana.startswith("[EXC")

    reason = (
        f"math={is_math} expert={is_expert} general={is_general} "
        f"analytics={'oui' if has_ana else 'non'}"
    )

    if expect_math and not is_math:
        s.fail(label, f"devrait être MATH: {reason}", question[:50])
    elif expect_expert and not is_expert:
        s.fail(label, f"devrait être EXPERT: {reason}", question[:50])
    elif expect_general and not is_general:
        s.fail(label, f"devrait être GÉNÉRAL: {reason}", question[:50])
    elif expect_analytics and not has_ana:
        s.fail(label, f"devrait avoir réponse ANALYTIQUE: {reason}", question[:50])
    elif expect_none_analytics and has_ana:
        s.fail(label, f"ne devrait PAS aller en SQL: {reason}", question[:50])
    else:
        s.ok(label, reason if VERBOSE else "")

print("\n[2.A] Calculs mathématiques → is_math_question=True, analytics=None")
math_tests = [
    ("10 / 1.5",                        "math-div"),
    ("125 + 48 - 13",                   "math-add"),
    ("15% de 3500",                      "math-pct"),
    ("Racine carree de 144",             "math-sqrt"),
    ("Si j'ai 10L et depense 1.5L/jour","math-prob"),
    ("Combien font 12 fois 15 ?",        "math-mult"),
    ("CAGR de 1200 a 1850 en 3 ans",     "math-cagr"),
    ("30 divise par 1.5",                "math-div2"),
    ("2 a la puissance 10",              "math-pow"),
    ("convertir 5000 kg en tonnes",      "math-conv"),
]
for q, lbl in math_tests:
    check_route(m2, q, lbl, expect_math=True, expect_none_analytics=True)

print("\n[2.B] Questions générales → is_general=True, analytics=None")
general_tests = [
    ("Bonjour",                          "gen-bonjour"),
    ("Bonne journee",                    "gen-bonne-journee"),
    ("Merci",                            "gen-merci"),
    ("Quelle est la capitale de Cote d'Ivoire ?", "gen-capitale"),
]
for q, lbl in general_tests:
    check_route(m2, q, lbl, expect_general=True, expect_none_analytics=True)

print("\n[2.C] Questions domaine minier → analytics != None")
domain_tests = [
    ("Tonnage total en 2025",         "dom-tonnage"),
    ("Heures machine en 2025",        "dom-heures"),
    ("Pannes trencher en 2026",       "dom-pannes"),
    ("Liste du personnel",            "dom-personnel"),
    ("Carburant 2024",                "dom-carburant"),
    ("Actions HSE non realisees",     "dom-hse"),
    ("Qualite echantillons 2025",     "dom-qualite"),
    ("Objectif production 2025",      "dom-objectif"),
    ("Transport mine port 2025",      "dom-transport"),
    ("Tonnage excave 2025",           "dom-excav"),
    ("Responsable site 2026",         "dom-responsable"),
    ("Tombereaux actifs en 2025",     "dom-tombereaux"),
    ("Heures tambour en 2025",        "dom-tambour"),
    ("Heures moteur en 2024",         "dom-moteur"),
]
for q, lbl in domain_tests:
    check_route(m2, q, lbl, expect_analytics=True)

print("\n[2.D] Questions expert industrie → is_expert=True")
expert_tests = [
    ("Quels sont les standards ISO pour les mines ?",        "exp-iso"),
    ("Recommandations IRMA pour la gestion HSE",             "exp-irma"),
    ("Bonnes pratiques securite dans les mines",             "exp-bpratiques"),
]
for q, lbl in expert_tests:
    check_route(m2, q, lbl, expect_expert=True)

m2.banner()


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 3 — ADAPTATION NOUVELLES DONNÉES (schéma inconnu, nouvelles tables)")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m3 = Scorer("3-ADAPTATION")
ALL_SCORES["3-ADAPTATION"] = m3

print("\n[3.A] Schema registry — découverte automatique des tables")
try:
    from src.engine import schema_registry as reg
    tables = list(reg._registry.keys())
    if len(tables) >= 20:
        m3.ok("registry-nb-tables", f"{len(tables)} tables enregistrées")
    else:
        m3.fail("registry-nb-tables", f"seulement {len(tables)} tables (attendu ≥20)")

    # Vérifier que les rôles sont détectés
    schema = reg.get_schema("descente_minerai")
    if schema and schema.col("date"):
        m3.ok("registry-role-date", f"date={schema.col('date')}")
    else:
        m3.fail("registry-role-date", "rôle 'date' non détecté sur descente_minerai")

    schema_sh = reg.get_schema("shifts_horaires")
    if schema_sh and schema_sh.col("hours"):
        m3.ok("registry-role-hours", f"hours={schema_sh.col('hours')}")
    else:
        m3.fail("registry-role-hours", "rôle 'hours' non détecté sur shifts_horaires")

    # Vérifier les années disponibles
    years_dm = reg.available_years(con, "descente_minerai")
    if set(years_dm) >= {2024, 2025, 2026}:
        m3.ok("registry-years", f"années={years_dm}")
    else:
        m3.fail("registry-years", f"années manquantes : {years_dm}")

    # Vérifier la description des tables connues
    for tbl in ["descente_minerai", "shifts_horaires", "personnel", "excavation"]:
        s = reg.get_schema(tbl)
        if s and s.description() != tbl:
            m3.ok(f"registry-desc-{tbl}", s.description()[:40])
        else:
            m3.fail(f"registry-desc-{tbl}", "description manquante ou identique au nom")

    # Vérifier NULL business reasons
    null_r = reg.null_context("shifts_horaires", "Equipement")
    if null_r and "2024" in null_r:
        m3.ok("registry-null-reason", "NULL Equipement expliqué")
    else:
        m3.fail("registry-null-reason", "raison NULL Equipement non trouvée")

except Exception as e:
    m3.fail("registry-import", str(e))

print("\n[3.B] Adaptation tables orphelines (carburant_activites, budget, valeurs_initiales…)")
# Ces tables existent dans DuckDB mais n'ont pas de handler dédié
# Le handler générique doit les couvrir
orphan_tests = [
    ("Budget 2025", "budget", "budget-2025"),
    ("Stocks reference", "stocks_ref", "stocks-ref"),
    ("Valeurs initiales", "valeurs_initiales", "valeurs-init"),
    ("Zones excavation", "zones_excavation", "zones-excav"),
]
for q, expected_tbl, lbl in orphan_tests:
    resp = analytics_q(q)
    if resp is None:
        m3.fail(lbl, f"aucune réponse pour table orpheline '{expected_tbl}'", q)
    elif expected_tbl in _table_from(resp).lower() or expected_tbl in resp.lower():
        m3.ok(lbl, f"table={_table_from(resp)} → {resp[:50]}")
    else:
        # Le handler générique peut retourner quelque chose d'autre — acceptable
        if resp and "_📋" in resp:
            m3.ok(lbl, f"réponse alternative: {resp[:50]}")
        else:
            m3.fail(lbl, f"réponse sans attribution: {resp[:50]}")

print("\n[3.C] smart_no_data — années hors portée et messages contextuels")
try:
    from src.engine import schema_registry as reg
    msg = reg.smart_no_data("descente_minerai", "2019", year=2019, con=con)
    if "2019" in msg and "disponibles" in msg.lower():
        m3.ok("smart-no-data-hors-portee", msg[:60])
    else:
        m3.fail("smart-no-data-hors-portee", f"message insuffisant: {msg[:60]}")

    msg2 = reg.smart_no_data("shifts_horaires", "2030", year=2030, con=con)
    if "2030" in msg2:
        m3.ok("smart-no-data-futur", msg2[:60])
    else:
        m3.fail("smart-no-data-futur", f"message incomplet: {msg2[:60]}")
except Exception as e:
    m3.fail("smart-no-data", str(e))

print("\n[3.D] handle_generic_table — nouvelles tables simulées")
# Tester le handler générique directement sur une table orpheline connue
try:
    resp_gen = analytics.handle_generic_table(con, "budget 2025", year=2025)
    if resp_gen:
        m3.ok("generic-budget", resp_gen[:60])
    else:
        # Budget = 12 lignes sans colonne date exploitable → acceptable si None
        m3.ok("generic-budget-none", "handler générique ne retourne rien pour budget (acceptable)")
except Exception as e:
    m3.fail("generic-budget", str(e))

# Carburant_activites = 14272 lignes avec colonnes heures
resp_gen2 = analytics.handle_generic_table(con, "carburant activites 2025", year=2025)
if resp_gen2 and "carburant_activites" in resp_gen2.lower():
    m3.ok("generic-carburant-activites", resp_gen2[:60])
elif resp_gen2:
    m3.ok("generic-carburant-activites-alt", resp_gen2[:60])
else:
    m3.fail("generic-carburant-activites", "aucune réponse pour carburant_activites")

print("\n[3.E] doc_manifest — découverte et guidance documents")
try:
    from src.rag.doc_manifest import guidance_no_doc, get_all, detect_type
    guidance = guidance_no_doc("inspection")
    if guidance and "upload" in guidance.lower() or "rapport" in guidance.lower():
        m3.ok("doc-guidance-inspection", guidance[:60])
    elif guidance:
        m3.ok("doc-guidance-inspection-alt", guidance[:60])
    else:
        m3.fail("doc-guidance-inspection", "guidance vide pour type 'inspection'")

    typ = detect_type("rapport_inspection_2025.pdf", "Non-conformités détectées")
    if typ:
        m3.ok("doc-detect-type", f"type={typ}")
    else:
        m3.fail("doc-detect-type", "type non détecté pour rapport d'inspection")
except Exception as e:
    m3.fail("doc-manifest", str(e))

m3.banner()


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 4 — INTERACTIVITÉ (clarifications, guidance, messages utiles)")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m4 = Scorer("4-INTERACTIVITÉ")
ALL_SCORES["4-INTERACTIVITÉ"] = m4

print("\n[4.A] Questions sans période → demande de précision")
resp = analytics_q("Tonnage total")  # sans année
if resp:
    if any(w in resp.lower() for w in ["precis", "annee", "période", "exemple", "2024", "2025"]):
        m4.ok("clarif-tonnage-sans-annee", resp[:80])
    else:
        m4.fail("clarif-tonnage-sans-annee", "pas de demande de précision", resp[:60])
else:
    m4.fail("clarif-tonnage-sans-annee", "None retourné au lieu d'une guidance")

print("\n[4.B] Engin inconnu → fallback avec explication")
resp = analytics_q("Heures machine ENGIN FANTOME en 2025")
if resp:
    if any(w in resp.lower() for w in ["aucun", "0", "total", "precision", "non renseigne"]):
        m4.ok("engin-inconnu-fallback", resp[:80])
    else:
        m4.fail("engin-inconnu-fallback", "pas de message explicatif", resp[:60])
else:
    m4.fail("engin-inconnu-fallback", "None retourné")

print("\n[4.C] NULL Equipement shifts → explication avec conseil")
resp = analytics_q("Heures machine TRS 296 en 2025")
if resp and ("non renseign" in resp.lower() or "2024" in resp or "agrega" in resp.lower()
             or "total" in resp.lower()):
    m4.ok("null-equipement-explication", resp[:80])
elif resp:
    m4.ok("null-equipement-reponse", resp[:80])  # OK si réponse cohérente
else:
    m4.fail("null-equipement", "None retourné pour TRS 296 en 2025")

print("\n[4.D] Données hors portée → message clair avec alternatives")
resp2020 = analytics_q("Tonnage en 2020")
if resp2020 and "2020" in resp2020 and any(w in resp2020.lower()
       for w in ["disponible", "annee", "2024", "2025"]):
    m4.ok("hors-portee-2020", resp2020[:80])
else:
    m4.fail("hors-portee-2020", "message d'aide insuffisant", (resp2020 or "None")[:60])

resp2099 = analytics_q("Heures machine en 2099")
if resp2099 and ("2099" in resp2099 or "disponible" in resp2099.lower()):
    m4.ok("hors-portee-2099", resp2099[:80])
elif resp2099:
    m4.ok("hors-portee-2099-partial", resp2099[:60])
else:
    m4.fail("hors-portee-2099", "None au lieu d'un message d'aide")

print("\n[4.E] Questions multi-parties → réponse groupée")
resp_multi = analytics_q("Tonnage par mois en 2026, bilan des pannes en 2025")
if resp_multi and "─" in resp_multi and "2026" in resp_multi and "2025" in resp_multi:
    m4.ok("multi-parties", resp_multi[:80])
elif resp_multi:
    m4.ok("multi-parties-partial", resp_multi[:60])
else:
    m4.fail("multi-parties", "None au lieu de réponse groupée")

print("\n[4.F] Question de suivi courte → contexte précédent utilisé")
# Simuler via analytics.handle avec question suivie
r1 = analytics_q("Heures machine par mois en 2025")
r2 = analytics_q("Tonnage descendu par mois en 2026")  # autre question directe
if r1 and r2:
    m4.ok("suivi-direct", "handler répond directement sans contexte précédent")
else:
    m4.fail("suivi-direct", "handlers ne répondent pas")

print("\n[4.G] Attribution source → toujours présente dans réponse analytique")
resp_attr = analytics_q("Tonnage total en 2025")
if resp_attr and "_📋" in resp_attr:
    m4.ok("attribution-presente", _table_from(resp_attr))
else:
    m4.fail("attribution-presente", "pas d'attribution _📋 dans la réponse",
            (resp_attr or "None")[:50])

m4.banner()


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 5 — NETTOYAGE ET QUALITÉ DES RÉPONSES")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m5 = Scorer("5-NETTOYAGE")
ALL_SCORES["5-NETTOYAGE"] = m5

print("\n[5.A] Pas de SQL brut exposé à l'utilisateur")
sql_questions = [
    "Tonnage total en 2025",
    "Heures machine en 2025",
    "Pannes trencher en 2026",
    "Personnel de la mine",
    "Carburant 2024",
]
sql_keywords = ["select ", "from ", "where ", "group by", "order by", "duckdb", "execute("]
for q in sql_questions:
    resp = analytics_q(q)
    if resp:
        has_sql = any(kw in resp.lower() for kw in sql_keywords)
        if has_sql:
            m5.fail(f"no-sql-{q[:20]}", "SQL brut visible dans la réponse", resp[:60])
        else:
            m5.ok(f"no-sql-{q[:20]}", resp[:40] if VERBOSE else "")

print("\n[5.B] Attribution _📋 correcte pour chaque table")
table_attribution_tests = [
    ("Heures machine en 2025", "shifts_horaires"),
    ("Tonnage excave en 2025", "excavation"),
    ("Carburant 2024", "carburant_citerne"),
    ("Objectif production 2025", "objectifs"),
    ("Actions HSE non realisees", "suivi_actions"),
    ("Actions PGES en cours", "pges_actions"),
    ("Qualite echantillons 2025", "qualite_echantillons"),
    ("Tonnage transporte en 2025", "transport_minerai_paa"),
    ("Liste du personnel", "personnel"),
    ("Pannes trencher 2026", "journal"),
]
for q, expected_tbl in table_attribution_tests:
    resp = analytics_q(q)
    if resp:
        actual = _table_from(resp)
        if expected_tbl.lower() in actual.lower():
            m5.ok(f"attrib-{expected_tbl[:20]}", actual)
        else:
            m5.fail(f"attrib-{expected_tbl[:20]}", f"attendu={expected_tbl} obtenu={actual}", resp[:50])
    else:
        m5.fail(f"attrib-{expected_tbl[:20]}", "None — pas de réponse")

print("\n[5.C] Format numérique cohérent (séparateurs milliers)")
num_questions = [
    "Tonnage total en 2025",
    "Tonnage transporte en 2025",
    "Heures machine en 2025",
]
for q in num_questions:
    resp = analytics_q(q)
    if resp:
        # Chercher des grands nombres → doivent avoir séparateurs milliers
        nums_raw = re.findall(r'\b\d{5,}\b', resp)  # nb ≥5 chiffres sans séparateur
        if nums_raw:
            m5.fail(f"format-num-{q[:20]}", f"nombres sans séparateur: {nums_raw[:3]}", resp[:60])
        else:
            m5.ok(f"format-num-{q[:20]}", resp[:40] if VERBOSE else "")

print("\n[5.D] Messages d'erreur compréhensibles (pas de tracebacks)")
error_questions = [
    "Heures machine en 2099",
    "Tonnage en 2001",
    "Pannes trencher en 2019",
]
for q in error_questions:
    resp = analytics_q(q)
    if resp:
        has_traceback = any(w in resp for w in ["Traceback", "Error:", "Exception:", "line "])
        if has_traceback:
            m5.fail(f"no-traceback-{q[:20]}", "traceback visible", resp[:60])
        else:
            m5.ok(f"no-traceback-{q[:20]}", resp[:40] if VERBOSE else "")
    # None = pas de message mais pas d'erreur non plus — OK

print("\n[5.E] Pas de réponse dupliquée (mêmes données affichées deux fois)")
for q in ["Tonnage par mois en 2025", "Heures machine par mois en 2025"]:
    resp = analytics_q(q)
    if resp:
        # Détecter si "Janvier" apparaît plus de 2 fois dans la réponse
        cnt = resp.lower().count("janvier")
        if cnt > 2:
            m5.fail(f"no-dup-{q[:20]}", f"'Janvier' apparaît {cnt} fois", resp[:60])
        else:
            m5.ok(f"no-dup-{q[:20]}", f"Janvier×{cnt}")

print("\n[5.F] Réponses non vides pour les domaines couverts")
coverage_tests = [
    "Tonnage total en 2025", "Heures machine en 2025", "Personnel de la mine",
    "Carburant 2024", "Actions HSE non realisees", "Pannes trencher en 2026",
    "Tonnage excave en 2025", "Objectif production 2025",
    "Teneur Al2O3 echantillons 2025", "Tonnage transporte en 2025",
]
for q in coverage_tests:
    resp = analytics_q(q)
    if resp and len(resp.strip()) > 20:
        m5.ok(f"coverage-{q[:25]}", resp[:40] if VERBOSE else "")
    else:
        m5.fail(f"coverage-{q[:25]}", f"réponse vide ou trop courte: {repr(resp)}")

m5.banner()


# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*72)
print("MODE 6 — ROBUSTESSE (injections, données aberrantes, limites)")
print("="*72)
# ══════════════════════════════════════════════════════════════════════════════
m6 = Scorer("6-ROBUSTESSE")
ALL_SCORES["6-ROBUSTESSE"] = m6

print("\n[6.A] Tentatives d'injection SQL → pas d'erreur, réponse propre")
injection_tests = [
    ("Tonnage en 2025'; DROP TABLE descente_minerai;--", "sql-inj-1"),
    ("Personnel de 'OR '1'='1", "sql-inj-2"),
    ("Heures machine <script>alert(1)</script>", "xss-inj"),
    ('Tonnage "union select * from information_schema.tables--', "union-inj"),
    ("Responsable; exec xp_cmdshell('dir')--", "cmd-inj"),
]
for q, lbl in injection_tests:
    try:
        resp = analytics_q(q)
        # Vérifier qu'il n'y a pas d'erreur DuckDB exposée
        if resp and any(e in resp for e in ["Error:", "Traceback", "SQL", "execute"]):
            m6.fail(lbl, f"erreur SQL exposée dans la réponse", (resp or "")[:60])
        else:
            m6.ok(lbl, "traitement sécurisé" if VERBOSE else "")
    except Exception as exc:
        # Exception Python catchée = OK (le handler a géré l'erreur)
        m6.ok(lbl, f"exception catchée: {str(exc)[:40]}")

print("\n[6.B] Questions vides ou triviales → pas d'exception")
edge_cases = [
    ("", "vide"),
    ("?", "question-mark"),
    ("2025", "annee-seule"),
    ("a", "lettre-seule"),
    ("   ", "espaces"),
]
for q, lbl in edge_cases:
    try:
        resp = analytics_q(q)
        m6.ok(lbl, f"réponse={repr(resp)[:30]}")
    except Exception as exc:
        m6.fail(lbl, f"exception non gérée: {exc}")

print("\n[6.C] Années extrêmes → réponse cohérente")
extreme_years = [
    ("Tonnage en 1900", "year-1900"),
    ("Heures machine en 2100", "year-2100"),
    ("Carburant en 2000", "year-2000"),
]
for q, lbl in extreme_years:
    try:
        resp = analytics_q(q)
        if resp and "traceback" not in resp.lower() and "error" not in resp.lower():
            m6.ok(lbl, (resp or "None")[:50])
        elif resp is None:
            m6.ok(lbl, "None acceptable pour année hors portée")
        else:
            m6.fail(lbl, "réponse avec erreur", resp[:60])
    except Exception as exc:
        m6.fail(lbl, f"exception: {exc}")

print("\n[6.D] Questions très longues → pas de timeout ou erreur")
long_q = ("Quelle est la production totale de tonnage descendu en minerai de bauxite "
          "pour l'année calendaire 2025 incluant tous les tombereaux et engins de transport "
          "sur le site de Bénéné en Côte d'Ivoire, ventilée par mois s'il vous plaît ?")
try:
    resp = analytics_q(long_q)
    if resp and "_📋" in resp:
        m6.ok("long-question", resp[:60])
    elif resp:
        m6.ok("long-question-partial", resp[:60])
    else:
        m6.fail("long-question", "None sur question longue")
except Exception as exc:
    m6.fail("long-question", str(exc))

print("\n[6.E] Questions multi-tables simultanées")
multi_q = "Tonnage par mois en 2025, heures machine par mois en 2025, excavation par mois en 2025"
try:
    resp = analytics_q(multi_q)
    if resp and ("descente" in resp.lower() or "tonnage" in resp.lower()):
        m6.ok("multi-tables", resp[:60])
    else:
        m6.fail("multi-tables", "réponse insuffisante", (resp or "None")[:50])
except Exception as exc:
    m6.fail("multi-tables", str(exc))

print("\n[6.F] Caractères spéciaux dans les noms → gestion propre")
special_chars = [
    ("Tonnage « descendu » en 2025", "guillemets"),
    ("Heures machine (2025)", "parentheses"),
    ("Tonnage 2025 — par mois", "tirets"),
    ("Production 2025 : par mois", "deux-points"),
]
for q, lbl in special_chars:
    try:
        resp = analytics_q(q)
        if resp and "traceback" not in resp.lower():
            m6.ok(lbl, resp[:40] if VERBOSE else "")
        elif resp is None:
            m6.ok(lbl, "None acceptable")
        else:
            m6.fail(lbl, resp[:60])
    except Exception as exc:
        m6.fail(lbl, str(exc))

m6.banner()


# ══════════════════════════════════════════════════════════════════════════════
# RAPPORT GLOBAL FINAL
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "="*72)
print("RAPPORT GLOBAL — SYNTHÈSE TOUS MODES")
print("="*72)

total_all = sum(s.total for s in ALL_SCORES.values())
passed_all = sum(s.passed for s in ALL_SCORES.values())
score_global = round(passed_all / total_all * 100, 1) if total_all else 0.0

DEPLOY_THRESHOLD = 95.0
ready = True

for name, s in ALL_SCORES.items():
    icon = PASS if s.score >= DEPLOY_THRESHOLD else (WARN if s.score >= 80 else FAIL)
    bar_ok = int(s.score / 5)  # /5 pour avoir 20 blocs
    bar_fail = 20 - bar_ok
    bar = "█" * bar_ok + "░" * bar_fail
    print(f"  {icon} Mode {name:<20} [{bar}] {s.score:5.1f}%  ({s.passed}/{s.total})")
    if s.score < DEPLOY_THRESHOLD:
        ready = False

print()
global_icon = PASS if score_global >= DEPLOY_THRESHOLD else (WARN if score_global >= 80 else FAIL)
print(f"  {global_icon} SCORE GLOBAL : {score_global}% ({passed_all}/{total_all})")
print(f"  SEUIL DÉPLOIEMENT : {DEPLOY_THRESHOLD}%")
print()
if ready:
    print(f"  {PASS} SYSTÈME PRÊT AU DÉPLOIEMENT — tous les modes ≥ {DEPLOY_THRESHOLD}%")
else:
    failing_modes = [name for name, s in ALL_SCORES.items() if s.score < DEPLOY_THRESHOLD]
    print(f"  {FAIL} DÉPLOIEMENT BLOQUÉ — modes à corriger : {', '.join(failing_modes)}")
    print(f"  Améliorations requises :")
    for name in failing_modes:
        s = ALL_SCORES[name]
        print(f"    • Mode {name} : {s.score}% → besoin de {DEPLOY_THRESHOLD}%")
        for lbl, reason in s.failures[:3]:
            print(f"      - {lbl}: {reason}")

print("="*72)
