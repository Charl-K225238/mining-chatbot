"""
test/test_step6_non_regression.py
===================================
Batterie de non-régression — Étape 6 — tests challengeants.

Chaque test est conçu pour piéger un modèle (qwen2.5:3b ou phi3:mini) ou un
composant du pipeline sur un cas limite réel issu du domaine minier.

Sections :
  A  NLP          — domaines / intentions / périodes (cas piégeux)
  B  Router       — décisions de routing, ambiguïté, cascade non-bloquante
  C  Clarification — qualité prompt + suggestions contextuelles
  D  Analytics    — handlers SQL : temporalité fine, chemin alternatif, limites
  E  Régression   — bugs préalablement corrigés (ne jamais régresser)
  F  Pièges LLM   — questions analytiques qui NE doivent PAS aller au LLM

Usage :
    .venv/Scripts/python.exe -X utf8 test/test_step6_non_regression.py
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from core.nlp import analyser_question, detecter_domaines, extraire_periode, analyser_intentions
from core.router import router
from core.clarification import generer_questions_suivi, verifier_qualite_prompt, MESSAGES_CLARIF
from src.db.connection import get_db
from src.engine.analytics import handle as ah

con = get_db()

ALL_TABLES = [
    "descente_minerai", "excavation", "journal", "carburant_citerne",
    "transport_minerai_paa", "productivite_loading", "pges_actions",
    "suivi_actions", "objectifs", "qualite_echantillons",
]

# ─── Framework ────────────────────────────────────────────────────────────────
_n = _ok = _fail = 0

def ok(cond: bool, name: str, detail: str = "") -> bool:
    global _n, _ok, _fail
    _n += 1
    if cond:
        _ok += 1
        print(f"  [OK]   {name}")
    else:
        _fail += 1
        extra = f"  ← {detail}" if detail else ""
        print(f"  [FAIL] {name}{extra}")
    return cond

def section(title: str):
    print(f"\n{'═'*65}")
    print(f"  {title}")
    print(f"{'─'*65}")


# ═══════════════════════════════════════════════════════════════════════════════
section("A — NLP : domaines, intentions, périodes (piégeux)")
# ═══════════════════════════════════════════════════════════════════════════════

# A1. Deux domaines dans la même question — PGES ET HSE
ctx = analyser_question("PGES et HSE en cours")
ok("pges" in ctx["domaines"] and "hse" in ctx["domaines"],
   "A1  PGES et HSE → domaines [pges, hse] tous deux détectés",
   f"domaines={ctx['domaines']}")

# A2. Indemnisation → domaine spécifique pges (pas générique)
ctx = analyser_question("indemnisation des populations affectées par le projet")
ok("indemnisation" in ctx["domaines"],
   "A2  'indemnisation des populations' → domaine 'indemnisation' détecté",
   f"domaines={ctx['domaines']}")

# A3. Abréviation BV (Bureau Veritas) → non_conformite
ctx = analyser_question("BV a remis son rapport d'inspection")
ok("non_conformite" in ctx["domaines"],
   "A3  'BV a remis son rapport' → domaine 'non_conformite' détecté",
   f"domaines={ctx['domaines']}")

# A4. NC dans le texte → non_conformite
ctx = analyser_question("Quelles sont les NC majeures relevées lors de l'audit ?")
ok("non_conformite" in ctx["domaines"],
   "A4  'NC majeures' → domaine 'non_conformite' détecté",
   f"domaines={ctx['domaines']}")

# A5. Période T1 2026 → trimestre=1, année=2026
p = extraire_periode("Quel est le tonnage au T1 2026 ?")
ok(p["trimestre"] == 1 and p["annee"] == 2026,
   "A5  'T1 2026' → trimestre=1 et annee=2026",
   f"periode={p}")

# A6. Semestre S1 2025 → semestre=1, année=2025 (S1 ne doit pas être confondu avec S1 semaine)
p = extraire_periode("Tonnage S1 2025")
ok(p["semestre"] == 1 and p["annee"] == 2025,
   "A6  'S1 2025' → semestre=1 (pas confondu avec une semaine)",
   f"periode={p}")

# A7. Intention "resumer" détectée
ctx = analyser_question("Fais-moi un résumé des actions PGES non réalisées")
ok("resumer" in ctx["intentions"],
   "A7  'résumé des actions' → intention 'resumer' détectée",
   f"intentions={ctx['intentions']}")

# A8. PIÈGE — 'realise' seul ne doit PAS déclencher le domaine 'statut'
#    (bug corrigé : "a realise l'inspection" ne voulait pas dire statut=En cours)
ctx = analyser_question("Quel organisme a réalisé l'inspection du site ?")
ok("statut" not in ctx["domaines"],
   "A8  'a réalisé l'inspection' → domaine 'statut' PAS détecté (piège)",
   f"domaines={ctx['domaines']}")

# A9. 'statut' dans une vraie question de suivi → domaine détecté
ctx = analyser_question("Quel est le statut des obligations non réalisées ?")
ok("statut" in ctx["domaines"],
   "A9  'statut des obligations non réalisées' → domaine 'statut' détecté",
   f"domaines={ctx['domaines']}")

# A10. Excavation décapage T2 2025 → domaine excavation + trimestre
ctx = analyser_question("Tonnage excavé décapage au T2 2025")
p = ctx["periode"]
ok("excavation" in ctx["domaines"],
   "A10 'excavé décapage T2 2025' → domaine 'excavation' détecté",
   f"domaines={ctx['domaines']}")
ok(p["trimestre"] == 2 and p["annee"] == 2025,
   "A10b 'T2 2025' → trimestre=2, annee=2025",
   f"periode={p}")


# ═══════════════════════════════════════════════════════════════════════════════
section("B — Router : décisions de pipeline et table cible")
# ═══════════════════════════════════════════════════════════════════════════════

# B1. PGES ET HSE ensemble → pges_actions GAGNE (pges > hse dans lever_ambiguite)
r = router("PGES et HSE en cours", ALL_TABLES)
ok(r["table"] == "pges_actions",
   "B1  'PGES et HSE en cours' → table=pges_actions (pges prioritaire sur hse)",
   f"table={r['table']}, clarif={r['clarif_type']}")

# B2. 'carburant' seul → analytique + clarif periode_manquante (PAS trop_courte)
r = router("carburant", ALL_TABLES)
ok(r["pipeline"] == "analytique" and r["clarif_type"] == "periode_manquante",
   "B2  'carburant' → pipeline=analytique + clarif=periode_manquante (pas trop_courte)",
   f"pipeline={r['pipeline']}, clarif={r['clarif_type']}")

# B3. 'Comparer 2024 et 2025' → analytique (tonnage par défaut), PAS domaine_inconnu
r = router("Comparer 2024 et 2025", ALL_TABLES)
ok(r["pipeline"] == "analytique" and r["table"] == "descente_minerai",
   "B3  'Comparer 2024 et 2025' → analytique/descente_minerai (pas domaine_inconnu)",
   f"pipeline={r['pipeline']}, table={r['table']}, clarif={r['clarif_type']}")

# B4. 'Actions PGES non réalisées' → pges_actions, PAS suivi_actions (pges wins)
r = router("Actions PGES non réalisées", ALL_TABLES)
ok(r["table"] == "pges_actions",
   "B4  'Actions PGES non réalisées' → table=pges_actions (pas suivi_actions)",
   f"table={r['table']}")

# B5. 'Quel organisme a réalisé l'inspection BV' → LLM (non_conformite→None)
r = router("Quel organisme a réalisé l'inspection BV ?", ALL_TABLES)
ok(r["pipeline"] == "llm" and r["table"] is None,
   "B5  'inspection BV' → pipeline=llm / table=None",
   f"pipeline={r['pipeline']}, table={r['table']}")

# B6. Intention prioriser sans table analytique → LLM
r = router("Si tu devais prioriser 3 actions correctives urgentes, lesquelles ?", ALL_TABLES)
ok(r["pipeline"] == "llm",
   "B6  'prioriser 3 actions correctives' → pipeline=llm (intention analytique pure)",
   f"pipeline={r['pipeline']}, table={r['table']}")

# B7. Tonnage excavé en 2025 → table=excavation, clarif=None (période présente)
r = router("Tonnage excavé en 2025", ALL_TABLES)
ok(r["table"] == "excavation" and r["clarif_type"] is None,
   "B7  'Tonnage excavé en 2025' → table=excavation, pas de clarif",
   f"table={r['table']}, clarif={r['clarif_type']}")

# B8. Pannes en 2023 → analytique, clarif=None (année présente, panne in NECESSITE_PERIODE)
r = router("Bilan des pannes en 2023", ALL_TABLES)
ok(r["pipeline"] == "analytique" and r["clarif_type"] is None,
   "B8  'Bilan des pannes en 2023' → analytique + pas de clarif",
   f"pipeline={r['pipeline']}, clarif={r['clarif_type']}")

# B9. Tombereaux travaillé en 2025 → descente_minerai (tombereau → descente), pas clarif
r = router("Quels tombereaux ont travaillé en 2025 ?", ALL_TABLES)
ok(r["table"] == "descente_minerai" and r["clarif_type"] is None,
   "B9  'tombereaux ont travaillé en 2025' → descente_minerai, pas de clarif",
   f"table={r['table']}, clarif={r['clarif_type']}")

# B10. Navire chargé en 2025 → productivite_loading, pas clarif
r = router("Tonnage navire chargé en 2025", ALL_TABLES)
ok(r["table"] == "productivite_loading" and r["clarif_type"] is None,
   "B10 'navire chargé en 2025' → productivite_loading, pas de clarif",
   f"table={r['table']}, clarif={r['clarif_type']}")


# ═══════════════════════════════════════════════════════════════════════════════
section("C — Clarification : qualité du prompt + suggestions")
# ═══════════════════════════════════════════════════════════════════════════════

# C1. Question complète → 0 tips
tips = verifier_qualite_prompt("Tonnage par mois en 2026")
ok(len(tips) == 0,
   "C1  'Tonnage par mois en 2026' → 0 conseils (question complète)",
   f"tips={tips}")

# C2. Sans période → au moins 1 tip
tips = verifier_qualite_prompt("Quel est le tonnage ?")
ok(len(tips) >= 1 and any("période" in t.lower() for t in tips),
   "C2  'Quel est le tonnage ?' → tip sur la période manquante",
   f"tips={tips}")

# C3. Question ultra courte → 2+ tips (période ET longueur)
tips = verifier_qualite_prompt("carburant")
ok(len(tips) >= 2,
   "C3  'carburant' (1 mot) → au moins 2 conseils (période + longueur)",
   f"nb_tips={len(tips)}")

# C4. Multi-questions → tip multi-questions
tips = verifier_qualite_prompt(
    "Quel est le tonnage en 2025 ? Et combien de pannes en 2023 ?"
)
ok(any("seule" in t.lower() or "une seule" in t.lower() for t in tips),
   "C4  Double question avec 2 '?' → tip 'une seule question à la fois'",
   f"tips={tips}")

# C5. periode_manquante → 3 suggestions avec annees_disponibles
ctx = analyser_question("Tonnage par mois")
sug = generer_questions_suivi("periode_manquante", ctx, "Tonnage par mois",
                               annees_disponibles=[2023, 2024, 2025])
ok(len(sug) == 3,
   "C5  generer_questions_suivi(periode_manquante, [2023,2024,2025]) → 3 suggestions",
   f"nb={len(sug)}")
ok(sug[0]["prompt"].endswith("en 2025") or "2025" in sug[0]["prompt"],
   "C5b Première suggestion contient l'année la plus récente (2025)",
   f"prompt0={sug[0]['prompt']}")

# C6. table_ambigue → labels lisibles (pas les noms bruts de tables)
ctx = analyser_question("bilan actions 2025")
sug = generer_questions_suivi("table_ambigue", ctx, "bilan actions 2025",
                               tables_candidates=["pges_actions", "suivi_actions"])
ok(len(sug) == 2,
   "C6  generer_questions_suivi(table_ambigue, [pges_actions, suivi_actions]) → 2 suggestions",
   f"nb={len(sug)}")
ok(all("pges_actions" not in s["label"] and "suivi_actions" not in s["label"] for s in sug),
   "C6b Labels lisibles (pas les noms bruts de tables DB)",
   f"labels={[s['label'] for s in sug]}")

# C7. MESSAGES_CLARIF contient les 5 clés attendues
expected_keys = {"periode_manquante", "table_ambigue", "domaine_inconnu",
                 "table_introuvable", "trop_courte"}
ok(expected_keys.issubset(set(MESSAGES_CLARIF.keys())),
   "C7  MESSAGES_CLARIF contient les 5 types de clarification",
   f"keys={set(MESSAGES_CLARIF.keys())}")


# ═══════════════════════════════════════════════════════════════════════════════
section("D — Analytics : cas limites temporels et chemins métier")
# ═══════════════════════════════════════════════════════════════════════════════

# D1. Bilan pannes par catégorie → contient 'Direction' (connue en 2023)
r = ah(con, "Bilan des pannes en 2023")
ok(r is not None and "Direction" in r,
   "D1  'Bilan des pannes en 2023' → contient la catégorie 'Direction'",
   f"r={r[:80] if r else None}")

# D2. Pannes de pneu (catégorie Pneu/Crevaison) → valeur non nulle
r = ah(con, "Combien de pannes de pneu en 2023 ?")
ok(r is not None and re.search(r"\d+", r or ""),
   "D2  'Pannes de pneu en 2023' → retourne un chiffre",
   f"r={r[:80] if r else None}")

# D3. Comparaison 2024 vs 2025 → contient 'Tonnage' ET une valeur positive
r = ah(con, "Comparer le tonnage 2024 et 2025")
ok(r is not None and "Tonnage" in r and re.search(r"20[0-9]{2}", r or ""),
   "D3  'Comparer tonnage 2024 et 2025' → tableau comparatif avec années",
   f"r={r[:100] if r else None}")

# D4. Tonnage T3 2025 → réponse scalaire contenant 'T3' (ou équivalent)
r = ah(con, "Tonnage T3 2025")
ok(r is not None and ("T3" in r or "trimestre" in (r or "").lower()),
   "D4  'Tonnage T3 2025' → réponse scalaire avec trimestre 3",
   f"r={r[:80] if r else None}")

# D5. Taux accomplissement 2025 → contient pourcentage ET icône qualitative
r = ah(con, "Taux accomplissement 2025")
ok(r is not None and "%" in r and any(icon in r for icon in ["✅", "⚠️", "❌"]),
   "D5  'Taux accomplissement 2025' → % ET icône qualitative (✅/⚠️/❌)",
   f"r={r[:80] if r else None}")

# D6. Objectifs excavation 2025 → section excavation présente
r = ah(con, "Objectifs excavation 2025")
ok(r is not None and ("xcav" in r.lower()),
   "D6  'Objectifs excavation 2025' → section Excavation présente",
   f"r={r[:80] if r else None}")

# D7. Carburant par engin en 2024 → tableau multi-lignes avec colonnes
r = ah(con, "Carburant par engin en 2024")
ok(r is not None and re.search(r"\d[\d,\.]+\s*L", r or ""),
   "D7  'Carburant par engin en 2024' → données en litres (L)",
   f"r={r[:80] if r else None}")

# D8. Tombereaux distincts → nombre 13 (connu d'après test_analytics.py)
r = ah(con, "Combien de tombereaux distincts ?")
ok(r is not None and "13" in r,
   "D8  'Combien de tombereaux distincts' → contient '13'",
   f"r={r[:80] if r else None}")

# D9. Tonnage S1 2025 → valeur connue '481' (d'après test_analytics.py)
r = ah(con, "Tonnage S1 2025")
ok(r is not None and "481" in r,
   "D9  'Tonnage S1 2025' → contient '481' (valeur de référence)",
   f"r={r[:80] if r else None}")

# D10. Piège : 'Tonnage' sans période → message d'aide (pas None, pas erreur)
r = ah(con, "Quel est le tonnage ?")
ok(r is not None and ("période" in r.lower() or "precis" in r.lower()
   or "annee" in r.lower() or "2024" in r or "2025" in r or "Tonnage" in r),
   "D10 'Quel est le tonnage ?' → message d'aide ou résultat (pas None silencieux)",
   f"r={r[:100] if r else 'None — tombé dans LLM sans explication'}")


# ═══════════════════════════════════════════════════════════════════════════════
section("E — Régression : bugs préalablement corrigés")
# ═══════════════════════════════════════════════════════════════════════════════

# E1. BUG#1 — 'a réalisé l'inspection' ne doit pas activer le domaine 'statut'
#    → était causé par le mot 'réalisé' seul dans la liste statut
ctx = analyser_question("Quel organisme a réalisé l'inspection du site ?")
ok("statut" not in ctx["domaines"],
   "E1  RÉGR: 'a réalisé l'inspection' → 'statut' PAS dans domaines",
   f"domaines={ctx['domaines']}")

# E2. BUG#2 — Conséquence : pipeline doit être 'llm' (non_conformite → None)
r = router("Quel organisme a réalisé l'inspection ?", ALL_TABLES)
ok(r["pipeline"] == "llm",
   "E2  RÉGR: 'a réalisé l'inspection' → pipeline=llm (pas analytique)",
   f"pipeline={r['pipeline']}, table={r['table']}")

# E3. BUG#3 — 'carburant' seul → periode_manquante (pas 'trop_courte')
r = router("carburant", ALL_TABLES)
ok(r["clarif_type"] == "periode_manquante",
   "E3  RÉGR: 'carburant' → clarif=periode_manquante (pas trop_courte)",
   f"clarif={r['clarif_type']}, pipeline={r['pipeline']}")

# E4. BUG#4 — 'Comparer 2024 et 2025' → analytique (pas domaine_inconnu)
r = router("Comparer 2024 et 2025", ALL_TABLES)
ok(r["pipeline"] != "clarification",
   "E4  RÉGR: 'Comparer 2024 et 2025' → PAS de clarification (domaine détecté)",
   f"pipeline={r['pipeline']}, clarif={r['clarif_type']}")

# E5. BUG#5 — 'actions PGES non réalisées' → pges_actions (pas suivi_actions)
r = router("actions PGES non réalisées", ALL_TABLES)
ok(r["table"] == "pges_actions",
   "E5  RÉGR: 'actions PGES non réalisées' → pges_actions (pges wins)",
   f"table={r['table']}")

# E6. BUG#6 — Route 'non_conformite' : lorsque None + suivi_actions coexistent,
#    LLM GAGNE (non_conformite → None l'emporte sur statut → suivi_actions)
r = router("Non-conformités : quel est le statut des levées ?", ALL_TABLES)
ok(r["pipeline"] == "llm" or r["table"] is None,
   "E6  RÉGR: 'Non-conformités + statut levées' → LLM (non_conformite l'emporte)",
   f"pipeline={r['pipeline']}, table={r['table']}")


# ═══════════════════════════════════════════════════════════════════════════════
section("F — Pièges LLM : analytique doit rester analytique")
# ═══════════════════════════════════════════════════════════════════════════════
# Ces questions DOIVENT aller en analytique — le LLM serait trop lent et imprécis.

analytical_must = [
    ("Tonnage par mois en 2026",                   "descente_minerai"),
    ("Bilan des pannes en 2023",                   "journal"),
    ("Carburant par engin en 2024",                "carburant_citerne"),
    ("Actions PGES non réalisées",                 "pges_actions"),
    ("Taux accomplissement 2025",                  "descente_minerai"),
    ("Carburant approvisionné janvier 2026",       "carburant_citerne"),
    ("Tombereaux ont travaillé en 2025",           "descente_minerai"),
    ("Tonnage transporté mine vers port en 2024",  "transport_minerai_paa"),
    ("Excavation décapage 2025",                   "excavation"),
    ("Obligations HSE non réalisées",              "suivi_actions"),
]

for q, expected_table in analytical_must:
    r = router(q, ALL_TABLES)
    ok(r["pipeline"] == "analytique",
       f"F   '{q[:52]}' → pipeline=analytique (pas LLM)",
       f"pipeline={r['pipeline']}, table={r['table']}, clarif={r['clarif_type']}")


# ═══════════════════════════════════════════════════════════════════════════════
# BILAN FINAL
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*65}")
print(f"  BILAN ÉTAPE 6 : {_ok}/{_n} tests OK  |  {_fail} ÉCHEC(S)")
print(f"{'═'*65}")

if _fail == 0:
    print("  Tous les tests sont passés.")
else:
    print(f"  {_fail} test(s) en échec — voir [FAIL] ci-dessus.")
    sys.exit(1)
