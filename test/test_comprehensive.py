"""
Batterie de tests complète — questions variées comme un utilisateur réel.
Couvre toutes les tables et cas limites.

Usage: .venv/Scripts/python.exe test/test_comprehensive.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from src.db.connection import get_db
from src.engine.analytics import handle, _split_queries
from src.engine.query_router import _is_followup

con = get_db()
results: list[bool] = []

def check(query: str, expect_contains: str | None = None,
          expect_none: bool = False, label: str = "") -> bool:
    r = handle(con, query)
    name = label or query[:55]
    if expect_none:
        ok = r is None
        status = "OK (→LLM)" if ok else f"FAIL got: {(r or '')[:70]}"
    elif expect_contains:
        ok = r is not None and expect_contains.lower() in r.lower()
        status = "OK" if ok else f"FAIL — attendu '{expect_contains}' dans:\n         {(r or '')[:120]}"
    else:
        ok = r is not None
        status = "OK" if ok else "FAIL — None inattendu"
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         ↳ {status}")
    return ok

def section(title):
    print(f"\n{'═'*60}\n{title}\n{'─'*60}")

# ════════════════════════════════════════════════════════════
section("A. DESCENTE MINERAI — questions variées")
# ════════════════════════════════════════════════════════════
results += [
    check("C'est quoi le tonnage de 2026 ?",        "475",       label="Formulation familière"),
    check("Combien de tonnes en janvier 2026 ?",     "108",       label="'Combien de tonnes'"),
    check("Production de la mine en 2025",           "1,156",     label="'Production' → tonnage"),
    check("Quelle est la descente en mars 2026 ?",   "146",       label="'descente' mois précis"),
    check("Bilan de production 2024 vs 2025",        "Écart",     label="'bilan' + 'vs'"),
    check("Tonnage T1 2026",                         "403",       label="Trimestre 1 2026"),
    check("Combien de voyages en 2025 ?",            "voyage",    label="Voyages 2025"),
    check("Quel tombereau transporte le plus ?",     "Tonnage",   label="Top 1 tombereau tonnage"),
    check("Y a-t-il eu de la pluie en 2023 ?",      None,        label="Pluie → LLM ok"),
    check("Qui supervise le site en 2025 ?",         None,        label="Responsable site 2025"),
    check("Quelle société assure le transport ?",    "IVEQI",     label="Société transport formulation libre"),
    check("Où est stocké le minerai ?",              "Zone",      label="Zones stockage toutes années"),
    check("Qualité du produit extrait",              "Qualit",    label="'produit extrait' → qualité"),
]

# ════════════════════════════════════════════════════════════
section("B. TONNAGES ALTERNATIFS (excavé, transporté, navire)")
# ════════════════════════════════════════════════════════════
results += [
    check("Volume excavé en 2025",                   "excavé",    label="'Volume excavé' → excavation"),
    check("Excavation 2024",                         "T",         label="'Excavation' seul + année"),
    check("Tonnage part PAA 2025",                   "port",      label="PAA → arrivé port"),
    check("Chargement navires 2025",                 "NAVIRE",    label="'Chargement navires' → breakdown"),
    check("Quel bateau a chargé le plus en 2024 ?",  "NAVIRE",    label="'Bateau' → navire"),
    check("Tonnage mine vers port en 2025",          "mine",      label="'mine vers port' formulation"),
    check("Écart tonnage mine et port 2025",         "Écart",     label="Écart mine/port"),
    check("Tonnage excavé et descendu 2025",         "excavé",    label="Multi-type (prend premier reconnu)"),
]

# ════════════════════════════════════════════════════════════
section("C. OBJECTIFS & PERFORMANCE")
# ════════════════════════════════════════════════════════════
results += [
    check("Est-ce que le plan 2025 a été atteint ?", "86",        label="'plan atteint' → taux"),
    check("Écart objectif réalisé 2024",             "Prévu",     label="Formulation directe"),
    check("On est à combien du budget 2025 ?",        "86",        label="Informel → taux"),
    check("Prévisions d'excavation 2025",            "1,406",     label="'prévisions excavation'"),
    check("Taux d'exécution 2025",                   "86",        label="'taux d'exécution' → accomplissement"),
]

# ════════════════════════════════════════════════════════════
section("D. PANNES & OBSERVATIONS")
# ════════════════════════════════════════════════════════════
results += [
    check("Bilan des incidents en 2023",             "Direction", label="'incidents' → pannes"),
    check("Pannes pneu sur toute la période",        "10",        label="Pannes pneu toutes années"),
    check("Quel tombereau tombe le plus souvent en panne ?", "classés", label="'tombe en panne'"),
    check("Pannes de direction 2023",                "direction", label="Direction obs 2023"),
    check("Combien de fois la piste a causé des arrêts ?", "Piste", label="Piste → observations"),
]

# ════════════════════════════════════════════════════════════
section("E. CARBURANT (données 2024 uniquement)")
# ════════════════════════════════════════════════════════════
results += [
    check("Consommation gasoil 2024",                "L",         label="'gasoil' → carburant"),
    check("Carburant par mois en 2024",              "Janvier",   label="Mensuel carburant"),
    check("Litre servis aux engins en 2024",         "L",         label="'litres servis'"),
    check("Dépotage de carburant en 2024",           "L",         label="Depotage citerne"),
    check("Quelle machine consomme le plus de carburant ?", "Litres", label="Classement conso carburant"),
    check("Carburant en 2025",                       "Aucune",    label="2025 sans données → Aucune"),
    check("Panne de carburant 2023",                 "Carburant", label="Panne carburant → obs, pas citerne"),
]

# ════════════════════════════════════════════════════════════
section("F. ACTIONS HSE & PGES")
# ════════════════════════════════════════════════════════════
results += [
    check("Obligations non respectées",              "Non réalisé", label="'obligations non respectées'"),
    check("Combien d'actions restent à faire ?",     "Non réalisé", label="'restent à faire'"),
    check("Actions en cours de réalisation",         "En cours",  label="Actions en cours"),
    check("Actions environnementales non faites",    "PGES",      label="'environnementales' → pges"),
    check("Quelles tâches HSE sont terminées ?",     "Réalisé",   label="'tâches terminées'"),
]

# ════════════════════════════════════════════════════════════
section("G. TOMBEREAUX & ENGINS")
# ════════════════════════════════════════════════════════════
results += [
    check("Tombereaux classés par tonnage",          "Tonnage",   label="Tonnage par tombereau"),
    check("Les 3 meilleurs engins de 2025",          "Top",       label="Top 3 engins 2025"),
    check("Top 10 camions de 2026",                  "Top",       label="'camions' → engins"),
    check("Combien de tombereaux y a-t-il ?",        "13",        label="Count tombereaux normalisé"),
    check("Quel engin a fait le plus de voyages ?",  "Top",       label="'voyages' → engins par tonnage"),
]

# ════════════════════════════════════════════════════════════
section("H. GRANULARITÉS TEMPORELLES VARIÉES")
# ════════════════════════════════════════════════════════════
results += [
    check("Tonnage semaine 14 en 2026",              "S14",       label="'semaine 14' textuel"),
    check("Tonnage de la semaine du 6 avril 2026",   "S",         label="Semaine d'une date"),
    check("Tonnage 1er semestre 2025",               "S1",        label="'1er semestre' textuel"),
    check("Production du deuxième semestre 2025",    "S2",        label="'deuxième semestre'"),
    check("Tonnage du 3ème trimestre 2025",          "T3",        label="'3ème trimestre' textuel"),
    check("Tonnage par semestre pour 2025",          "S1",        label="'par semestre' 2025"),
    check("Tonnage hebdomadaire 2026",               "S",         label="'hebdomadaire' → semaine"),
]

# ════════════════════════════════════════════════════════════
section("I. QUESTIONS AMBIGUËS / PIÈGES")
# ════════════════════════════════════════════════════════════
results += [
    check("Tonnage",                                 "période",   label="Tonnage seul → demande période"),
    check("Carburant",                               "L",         label="Carburant seul → total disponible"),
    check("Comparer le transport en 2024 et 2025",   "Écart",     label="'comparer transport'"),
    check("Quel est le bilan 2025 ?",                None, expect_none=True, label="'bilan 2025' seul → LLM"),
    check("Tout sur 2026",                           None, expect_none=True, label="Trop vague → LLM"),
    check("Tonnage navire et descendu 2025",         "NAVIRE",    label="Multi-type: navire gagne (handler prio)"),
]

# ════════════════════════════════════════════════════════════
section("J. MULTI-QUESTIONS (virgule)")
# ════════════════════════════════════════════════════════════
r1 = handle(con, "Tonnage descendu par mois en 2025, tonnage excavé par mois en 2025")
ok1 = r1 is not None and "Janvier" in r1 and "excavé" in r1.lower()
results.append(ok1)
print(f"  [{'OK' if ok1 else 'FAIL'}] Descendu + excavé 2025 mensuels")

r2 = handle(con, "Bilan pannes 2023, taux accomplissement 2025")
ok2 = r2 is not None and "Direction" in r2 and "86" in r2
results.append(ok2)
print(f"  [{'OK' if ok2 else 'FAIL'}] Pannes 2023 + taux 2025")

# ════════════════════════════════════════════════════════════
section("K. QUESTIONS DE SUIVI (is_followup)")
# ════════════════════════════════════════════════════════════
followup_tests = [
    ("pour le mois de janvier 2026", True,  "Temporel long"),
    ("au mois de mars 2025",         True,  "Temporel 'au mois de'"),
    ("uniquement en 2025",           True,  "Temporel + qualificatif"),
    ("par engin",                    True,  "Granularité engin"),
    ("de pneu",                      True,  "Type pneu"),
    ("en semestre 2",                True,  "Semestre"),
    # Non follow-up
    ("Quel est le bilan complet ?",  False, "Question complète"),
    ("Comparer 2023 et 2024",        False, "Question indépendante"),
    ("Donne-moi les données 2026",   False, "Question complète"),
]
for q, exp, lbl in followup_tests:
    got = _is_followup(q)
    ok = got == exp
    results.append(ok)
    print(f"  [{'OK' if ok else 'FAIL'}] is_followup('{q}') = {got} (attendu {exp}) — {lbl}")

# ════════════════════════════════════════════════════════════
section("L. DOUBLE SOURCE (_src) — pas de doublons")
# ════════════════════════════════════════════════════════════
src_tests = [
    ("Carburant consommé en 2024",          "carburant_citerne", "Carburant → source carburant"),
    ("Tonnage excavé 2025",                 "excavation",        "Excavé → source excavation"),
    ("Tonnage transporté 2025",             "transport",         "Transport → source transport"),
    ("Tonnage chargé par navires en 2025",  "loading",           "Navires → source loading"),
    ("Actions non réalisées",               "suivi",             "Actions → source suivi"),
]
for q, expected_src, lbl in src_tests:
    r = handle(con, q)
    ok = r is not None and expected_src in r
    # Also check that descente_minerai is NOT added when another source is present
    no_dup = r is None or r.count("_📋") <= 1
    results.append(ok and no_dup)
    mark = "OK" if ok and no_dup else "FAIL"
    print(f"  [{mark}] {lbl}")
    if not (ok and no_dup):
        if not ok:
            print(f"         ↳ Source '{expected_src}' absente")
        if not no_dup:
            print(f"         ↳ Source doublée (_📋 apparaît {r.count('_📋')} fois)")

# ════════════════════════════════════════════════════════════
# RÉSUMÉ
# ════════════════════════════════════════════════════════════
total  = len(results)
passed = sum(results)
failed = total - passed
rate   = passed / total * 100

print(f"\n{'═'*60}")
print(f"RÉSUMÉ : {passed}/{total} tests réussis ({rate:.0f}%)")
if failed:
    print(f"         {failed} échec(s) — voir détails ci-dessus")
print(f"{'═'*60}\n")
sys.exit(0 if failed == 0 else 1)
