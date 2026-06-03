import sys; sys.path.insert(0, '.')
from core.router import router

TABLES = [
    'descente_minerai','excavation','journal','carburant_citerne',
    'transport_minerai_paa','productivite_loading','pges_actions',
    'suivi_actions','objectifs','qualite_echantillons',
]

TESTS = [
    # (question, pipeline_attendu, table_attendue_ou_None)
    ("carburant approvisionne janvier 2026",  "analytique",    "carburant_citerne"),
    ("tombereaux ont travaille en 2025",       "analytique",    "descente_minerai"),
    ("actions PGES non realisees",            "analytique",    "pges_actions"),
    ("si tu devais prioriser 3 actions",      "llm",           None),
    ("quel organisme a realise inspection",   "llm",           None),
    ("Quel est le tonnage ?",                 "analytique",    "descente_minerai"),
    ("donnees",                               "clarification", None),
    ("carburant",                             "analytique",    "carburant_citerne"),
    ("pannes de direction en 2023",           "analytique",    "journal"),
    ("Comparer 2024 et 2025",                 "analytique",    "descente_minerai"),
]

ok_count = 0
for q, exp_p, exp_t in TESTS:
    r = router(q, TABLES)
    p_ok = r["pipeline"] == exp_p
    t_ok = (exp_t is None) or (r["table"] == exp_t)
    status = "OK" if (p_ok and t_ok) else "ECHEC"
    if p_ok and t_ok:
        ok_count += 1
    clarif = r["clarif_type"] or ""
    print(f"{status}  pipeline={r['pipeline']:15}  table={str(r['table']):25}  clarif={clarif:20}  | {q[:55]}")

print()
print(f"RESULTAT : {ok_count}/{len(TESTS)} OK")
