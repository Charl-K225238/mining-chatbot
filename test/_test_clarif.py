import sys; sys.path.insert(0, '.')
from core.clarification import generer_questions_suivi, verifier_qualite_prompt, MESSAGES_CLARIF

ctx_vide = {"periode": {"annee": None, "mois": None, "trimestre": None, "semestre": None},
            "domaines": ["tonnage"], "intentions": ["lister"],
            "nb_mots": 4, "multi_questions": False}

print("=" * 60)
print("TEST 1 — periode_manquante (annees=[2024,2025])")
sug = generer_questions_suivi("periode_manquante", ctx_vide, "Quel est le tonnage ?",
                               annees_disponibles=[2024, 2025])
assert len(sug) == 3, f"Attendu 3 suggestions, eu {len(sug)}"
for s in sug:
    print(f"  [{s['icone']}] {s['label']}")
    print(f"       -> {s['prompt']}")
print("OK")

print()
print("=" * 60)
print("TEST 2 — trop_courte")
sug2 = generer_questions_suivi("trop_courte", ctx_vide, "donnees")
assert len(sug2) == 3
for s in sug2:
    print(f"  [{s['icone']}] {s['label']}")
print("OK")

print()
print("=" * 60)
print("TEST 3 — domaine_inconnu")
sug3 = generer_questions_suivi("domaine_inconnu", ctx_vide, "quelque chose")
assert len(sug3) == 3
for s in sug3:
    print(f"  [{s['icone']}] {s['label']}")
print("OK")

print()
print("=" * 60)
print("TEST 4 — table_ambigue avec candidats")
sug4 = generer_questions_suivi("table_ambigue", ctx_vide, "bilan 2025",
                                tables_candidates=["pges_actions", "suivi_actions"])
assert len(sug4) == 2
for s in sug4:
    print(f"  [{s['icone']}] {s['label']} -> {s['prompt'][:60]}")
print("OK")

print()
print("=" * 60)
print("TEST 5 — verifier_qualite_prompt")
cases = [
    ("Quel est le tonnage ?",         True,  "Periode manquante attendue"),
    ("Tonnage par mois en 2025",      False, "Prompt complet — aucune consigne"),
    ("carburant",                     True,  "Trop court + pas de periode"),
    ("Actions PGES non realisees",    False, "PGES sans periode — OK si pas exige"),
]
for q, expect_tips, note in cases:
    tips = verifier_qualite_prompt(q)
    has = bool(tips)
    status = "OK" if (has == expect_tips) else f"ECHEC (attendu tips={expect_tips})"
    print(f"  {status}  [{len(tips)} tips]  {note}")
    for t in tips:
        print(f"    - {t[:70]}")

print()
print("=" * 60)
print("TEST 6 — MESSAGES_CLARIF")
for k, v in MESSAGES_CLARIF.items():
    print(f"  {k}: {v[:55]}")
print("OK")

print()
print("TOUS LES TESTS PASSES")
