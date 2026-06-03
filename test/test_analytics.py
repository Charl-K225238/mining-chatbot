"""
Batterie de tests analytics — couvre abbréviations, fautes, requêtes complexes.

Usage :
    .venv/Scripts/python.exe test/test_analytics.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from src.db.connection import get_db
from src.engine.analytics import handle, _split_queries
from src.engine.query_router import _is_followup

con = get_db()

# ── Helpers ───────────────────────────────────────────────────────────────────

def check(query: str, expect_contains: str | None = None,
          expect_none: bool = False, label: str = "") -> bool:
    r = handle(con, query)
    name = label or query[:55]
    if expect_none:
        ok = r is None
        status = "OK (→LLM)" if ok else f"FAIL got: {r[:60] if r else 'None'}"
    elif expect_contains:
        ok = r is not None and expect_contains.lower() in r.lower()
        status = "OK" if ok else f"FAIL — attendu '{expect_contains}' dans: {(r or '')[:80]}"
    else:
        ok = r is not None
        status = "OK" if ok else "FAIL — None inattendu"
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         ↳ {status}")
    return ok


results: list[bool] = []
def section(title: str):
    print(f"\n{'═'*55}\n{title}\n{'─'*55}")


# ════════════════════════════════════════════════════════
section("1. Tonnage — granularités temporelles")
# ════════════════════════════════════════════════════════
results += [
    check("Tonnage par mois en 2026",           "Janvier", label="Mensuel 2026"),
    check("Tonnage mensuel 2025",               "Janvier", label="Mensuel 2025 (abbr.)"),
    check("Tonnage S1-S6 2026",                 "S1",      label="Semaines ISO 1-6 (S1 inclus)"),
    check("Tonnage S17 2026",                   "S17",     label="Semaine ISO 17"),
    check("Tonnage W1 2026",                    "S",       label="W1 2026 → semaine 1"),
    check("Tonnage descendu par semaine en 2026", "S",     label="Hebdomadaire année entière"),
    check("Tonnage semaine par semaine en avril 2026", "S14", label="Semaines Avril 2026"),
    check("Tonnage de la 1ere semaine de janvier 2026", "Janvier", label="1ère semaine Janvier"),
    check("Tonnage T1 2026",                    "403",     label="Trimestre 1 2026"),
    check("Tonnage par trimestre en 2026",      "T1",      label="Par trimestre 2026"),
    check("Tonnage par semestre en 2025",       "S1",      label="Par semestre 2025"),
    check("Tonnage S1 et S2 2025",              "S1",      label="S1 et S2 2025"),
    check("Tonnage S1 e S2 2025",               "S1",      label="S1 e S2 2025 (typo 'e')"),
    check("Tonnage au mois de mai 2026",        "Aucune",  label="Mai 2026 (pas de données)"),
    check("Bilan annuel du tonnage",            "2023",    label="Bilan annuel"),
    check("Comparer 2024 et 2025",              "Voyage",  label="Comparaison complète"),
    check("Comparer le tonnage 2024 et 2025",   "Tonnage", label="Comparaison tonnage seul"),
    check("Tonnage excavé S1 2026",             "S1",      label="Excavé semestre 1 2026"),
    check("Tonnage le 03/02/2026",              "03/02/2026", label="Date précise descendu"),
]

# ════════════════════════════════════════════════════════
section("2. Objectifs & taux d'accomplissement")
# ════════════════════════════════════════════════════════
results += [
    check("Taux accomplissement 2025",          "86",      label="Taux 2025"),
    check("Taux d'accomplissement 2024",        "75",      label="Taux 2024"),
    check("Objectifs vs realise 2024",          "Prévu",   label="Objectifs 2024"),
    check("Objectifs excavation 2025",          "1,406",   label="Objectifs excav 2025"),
    check("Est-ce que les objectifs ont ete atteints en 2025", "86", label="Obj. atteints (formulation libre)"),
    check("Comparaison 2024 et 2025 taux",      "75",      label="Comparaison avec taux"),
    check("Taux accomplissement 2025",          "✅",      label="Légende icône présente"),
    check("Comparer 2024 et 2025",              "tombereau", label="Tombereaux libellé clair"),
]

# ════════════════════════════════════════════════════════
section("3. Tombereaux et engins")
# ════════════════════════════════════════════════════════
results += [
    check("Quels tombereaux ont le plus de pannes", "classés par nombre", label="Ranking pannes"),
    check("Quel est le nombre de pannes par tombereau", "classés par nombre", label="Nb pannes / tombereau"),
    check("Tombereaux avec le plus de pannes",   "TOMBEREAU", label="Plus de pannes (formulation 2)"),
    check("Combien de tombereaux distincts",     "13",      label="Count tombereaux (normalisé → 13)"),
    check("Tonnage par tombereaux",              "Tonnage", label="Tonnage par tombereau"),
    check("Top 5 engins par tonnage",            "Top 5",   label="Top 5 engins"),
    check("Top 10 engins",                       "Top 10",  label="Top 10 engins"),
    check("Meilleur engin 2025",                 "1",       label="Meilleur engin 2025"),
]

# ════════════════════════════════════════════════════════
section("4. Pannes et bilan")
# ════════════════════════════════════════════════════════
results += [
    check("Bilan des pannes en 2023",            "Direction",  label="Bilan 2023 (détaillé)"),
    check("Bilan des pannes en 2025",            "générique",  label="Bilan 2025 (générique)"),
    check("Combien de pannes de direction en 2023", "38",      label="Pannes direction 2023"),
    check("Pannes de pneu",                      "10",         label="Pannes pneu"),
    check("Y a t il eu des incidents pluie",     None,         label="Incidents pluie → LLM ok"),
]

# ════════════════════════════════════════════════════════
section("5. Abréviations et fautes d'orthographe")
# ════════════════════════════════════════════════════════
results += [
    check("Toneage par mois 2026",    None,   expect_none=True, label="'Toneage' → LLM (non reconnu)"),
    check("Tonnage T3 2025",          "T3",   label="T3 abréviation"),
    check("Tonnage T1 2026",          "403",  label="T1 2026"),
    check("Tonnage S1 2025",          "481",  label="S1 semestre 2025"),
    check("Tonnage W17 2026",         "S17",  label="W17 → semaine 17"),
    check("Tonnes par semaine avril 2026", "S14", label="'Tonnes' → tonnage"),
    check("Tonnage sem 3 2026",       "S3",   label="'Sem 3' → semaine 3"),
]

# ════════════════════════════════════════════════════════
section("6. Questions multi-requêtes (virgule)")
# ════════════════════════════════════════════════════════
r1 = handle(con, "Tonnage par mois en 2026, bilan des pannes en 2023")
results.append(r1 is not None and "Janvier" in r1 and "Direction" in r1)
status = "OK" if results[-1] else "FAIL"
print(f"  [{status}] Multi-requête: tonnage 2026 + pannes 2023")

r2 = handle(con, "Comparer 2024 et 2025, objectifs excavation 2025")
results.append(r2 is not None)
status = "OK" if results[-1] else "FAIL"
print(f"  [{status}] Multi-requête: comparaison + objectifs")

# ════════════════════════════════════════════════════════
section("7. Questions de suivi (_is_followup)")
# ════════════════════════════════════════════════════════
followup_cases = [
    ("en 2026",           True,  "Temporel simple"),
    ("en avril",          True,  "Mois"),
    ("de direction",      True,  "Type panne"),
    ("par mois",          True,  "Granularité"),
    ("par semaine",       True,  "Granularité semaine"),
    ("excavation",        True,  "Sujet"),
    ("de direction en 2023", True, "Type + année"),
    # Not follow-up
    ("Tonnage par mois en 2026 ?", False, "Question complète"),
    ("Comparer 2024 et 2025",      False, "Question complète"),
    ("Quels tombereaux ?",         False, "Question complète"),
]
for q, expected, lbl in followup_cases:
    got = _is_followup(q)
    ok = got == expected
    results.append(ok)
    print(f"  [{'OK' if ok else 'FAIL'}] is_followup('{q}') = {got} (attendu {expected}) — {lbl}")

# Follow-up chain test
print("\n  Chaîne de suivi (prev + suivi → analytics):")
chains = [
    ("Bilan des pannes", "en 2023",       "Direction"),
    ("Bilan des pannes", "de direction",  "Direction"),
    ("Tonnage par mois", "en 2026",       "Janvier"),
    ("Top 5 engins",     "en 2025",       "Top 5"),
]
for prev, suivi, expected_content in chains:
    combined = f"{prev} {suivi}"
    r = handle(con, combined)
    ok = r is not None and expected_content.lower() in r.lower()
    results.append(ok)
    print(f"  [{'OK' if ok else 'FAIL'}] '{prev}' + '{suivi}'")

# ════════════════════════════════════════════════════════
section("8. Autres domaines")
# ════════════════════════════════════════════════════════
results += [
    check("Qui est le responsable du site en 2026",   None,    label="Responsable 2026"),
    check("Quelle est la société de transport",        "IVEQI", label="Société transport"),
    check("Quel est le tonnage par voyage",            "voyage", label="Tonnage/voyage"),
    check("Top 10 zones de stockage",                  "Zone",  label="Zones stockage"),
    check("Quelles annees sont disponibles",           "2023",  label="Années disponibles"),
    check("_split_queries test",                       None, expect_none=True, label="split_queries: phrase courte"),
    # Carburant (données disponibles : 2024 janv–juil uniquement)
    check("Carburant consommé en 2024",                "L",       label="Carburant total 2024"),
    check("Carburant consommé par mois en 2024",       "Janvier", label="Carburant mensuel 2024"),
    check("Carburant par engin en 2024",               "Litres",  label="Carburant par engin"),
    check("Bilan des pannes de carburant en 2023",     "Carburant", label="Panne carburant → observations"),
    # Navires
    check("Tonnage chargé par navires en 2025",        "NAVIRE",  label="Navire breakdown"),
    # Actions HSE / PGES
    check("Quelles sont les actions non réalisées",    "Non réalisé", label="Actions HSE non réalisées"),
    check("Quelles sont les actions PGES non réalisées", "PGES",  label="Actions PGES"),
]
# Test _split_queries directly
parts = _split_queries("Tonnage par mois en 2026, bilan des pannes en 2023")
ok = len(parts) == 2
results.append(ok)
print(f"  [{'OK' if ok else 'FAIL'}] _split_queries → {len(parts)} parties (attendu 2)")

parts2 = _split_queries("S1, S2, S3")
ok2 = len(parts2) == 1  # trop court, ne split pas
results.append(ok2)
print(f"  [{'OK' if ok2 else 'FAIL'}] _split_queries 'S1, S2, S3' → {len(parts2)} partie (attendu 1)")

# ════════════════════════════════════════════════════════
# Résumé
# ════════════════════════════════════════════════════════
total   = len(results)
passed  = sum(results)
failed  = total - passed
rate    = passed / total * 100

print(f"\n{'═'*55}")
print(f"RÉSUMÉ : {passed}/{total} tests réussis ({rate:.0f}%)")
if failed:
    print(f"         {failed} échec(s) — voir détails ci-dessus")
print(f"{'═'*55}\n")
sys.exit(0 if failed == 0 else 1)
