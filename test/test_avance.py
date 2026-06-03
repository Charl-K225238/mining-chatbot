# -*- coding: utf-8 -*-
"""
test_avance.py
==============
Tests avancés et exigeants du moteur analytique Miny.

Cas couverts :
  - Questions ambiguës ou pièges : formulations qui pourraient tromper le router
  - Questions multi-angles : même info demandée de 10 façons différentes
  - Valeurs de réponse : vérification que les CHIFFRES sont plausibles
  - Frontières inter-handlers : questions qui chevauchent deux domaines
  - Robustesse année/période : S1-S4, T1-T4, semaines ISO, dates précises
  - Qualité de la réponse : pas de "Aucune donnée" pour des données connues existantes

Exécuter :
  .venv\\Scripts\\python.exe test/test_avance.py
"""
import io, sys, os, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import duckdb

def _make_con():
    con = duckdb.connect(":memory:")
    parquet_dir = ROOT / "data" / "parquet"
    for f in sorted(os.listdir(parquet_dir)):
        if f.endswith(".parquet"):
            name = f.replace(".parquet", "")
            path = (parquet_dir / f).as_posix()
            con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet(\'{path}\')')
    return con

try:
    from src.db.connection import get_db
    con = get_db()
    print("[INFO] Connexion via get_db()")
except Exception as e:
    print(f"[WARN] Connexion directe ({e})")
    con = _make_con()

from src.engine import analytics

PASS = "✅"; FAIL = "❌"; WARN = "⚠️"
results = {"passed": 0, "failed": 0, "no_handler": 0}
failures = []

def _table_from_response(resp):
    if resp and "_📋" in resp:
        after = resp.split("_📋")[-1].strip()
        token = after.split()[0] if after else ""
        return token.rstrip("_").strip()
    return "UNKNOWN"

def _extract_number(text):
    """
    Extrait le premier GRAND nombre de la réponse (tonnage, heures…).
    Priorité : nombres > 1000 avec séparateur de milliers, sinon premier nombre > 50.
    Ignore les années (2023-2030) et les petits nombres.
    """
    if not text:
        return None
    # Chercher des nombres avec séparateur milliers ex: 1,156,100 ou 650,154
    for m in re.finditer(r"\d{1,3}(?:[,]\d{3})+(?:\.\d+)?", text):
        try:
            v = float(m.group().replace(",", ""))
            if not (2020 <= v <= 2030):  # exclure les années
                return v
        except ValueError:
            pass
    # Sinon chercher tout nombre > 5 qui n'est pas une année ni petite quantité
    for m in re.finditer(r"\d+(?:[.,]\d+)?", text):
        try:
            v = float(m.group().replace(",", ""))
            if v >= 5 and not (2020 <= v <= 2030):
                return v
        except ValueError:
            pass
    return None

def test_q(question, expected_table=None, must_not_be_none=True,
           must_contain=None, min_value=None, max_value=None,
           must_not_contain=None, label=""):
    try:
        resp = analytics.handle(con, question)
    except Exception as exc:
        resp = None
        print(f"  {FAIL} EXCEPTION [{label or question[:50]}]: {exc}")
        results["failed"] += 1
        failures.append(("EXCEPTION", question[:60], str(exc)))
        return None

    tag = f"[{label}] " if label else ""

    if resp is None:
        if must_not_be_none:
            results["no_handler"] += 1
            failures.append(("NO_HANDLER", question[:70], expected_table or "?"))
            print(f"  {FAIL} AUCUN HANDLER  {tag}{question[:70]}")
        else:
            results["passed"] += 1
            print(f"  {PASS} None (correct)  {tag}{question[:50]}")
        return None

    actual_table = _table_from_response(resp)
    ok = True
    reasons = []

    if expected_table:
        if expected_table.lower() not in actual_table.lower():
            ok = False
            reasons.append(f"table attendu={expected_table} obtenu={actual_table}")

    if must_contain and must_contain.lower() not in resp.lower():
        ok = False
        reasons.append(f"manque '{must_contain}'")

    if must_not_contain and must_not_contain.lower() in resp.lower():
        ok = False
        reasons.append(f"contient '{must_not_contain}' indesirable")

    if min_value is not None or max_value is not None:
        num = _extract_number(resp)
        if num is None:
            ok = False
            reasons.append("aucun nombre dans la reponse")
        elif min_value is not None and num < min_value:
            ok = False
            reasons.append(f"valeur {num:,.0f} < min {min_value:,.0f}")
        elif max_value is not None and num > max_value:
            ok = False
            reasons.append(f"valeur {num:,.0f} > max {max_value:,.0f}")

    preview = resp[:80].replace("\n", " ")
    if ok:
        results["passed"] += 1
        print(f"  {PASS} [{actual_table}]  {tag}{preview}")
    else:
        results["failed"] += 1
        failures.append(("FAIL", question[:70], " | ".join(reasons)))
        print(f"  {FAIL} [{actual_table}]  {tag}{' | '.join(reasons)}  |  {preview[:50]}")
    return resp


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC A — VALEURS CHIFFRÉES PLAUSIBLES (vérification des données réelles)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[A.1] Tonnage annuel — fourchettes plausibles pour les données réelles")
# descente_minerai 2024=620785T, 2025=1156100T, 2026=475340T
test_q("Tonnage total en 2024", "descente_minerai", min_value=500_000, max_value=800_000, label="2024 620kT")
test_q("Tonnage total en 2025", "descente_minerai", min_value=900_000, max_value=1_500_000, label="2025 1.15MT")
test_q("Tonnage total en 2026", "descente_minerai", min_value=200_000, max_value=700_000, label="2026 475kT")
test_q("Tonnage descendu en 2025 ?", "descente_minerai", min_value=900_000, label="2025 min 900kT")

print("\n[A.2] Heures machine — fourchettes plausibles")
# shifts_horaires 2024=2200h, 2025=3223h, 2026=1205h
test_q("Heures machine en 2025", "shifts_horaires", min_value=2_000, max_value=5_000, label="2025 ~3200h")
test_q("Heures machine en 2024", "shifts_horaires", min_value=1_000, max_value=4_000, label="2024 ~2200h")
test_q("Heures tambour en 2025", "shifts_horaires", min_value=500, max_value=5_000, label="tambour 2025")
test_q("Heures moteur en 2025", "shifts_horaires", min_value=500, max_value=5_000, label="moteur 2025")

print("\n[A.3] Excavation — fourchettes plausibles")
# excavation 2024=650154T, 2025=1216242T, 2026=455623T
test_q("Tonnage excave en 2024", "excavation", min_value=500_000, max_value=900_000, label="excav 2024")
test_q("Tonnage excave en 2025", "excavation", min_value=1_000_000, max_value=1_500_000, label="excav 2025")

print("\n[A.4] Transport — fourchettes plausibles")
# transport_minerai_paa 2025: ~1.19MT mine, ~1.19MT port
test_q("Tonnage transporte en 2025", "transport_minerai_paa", min_value=900_000, max_value=1_500_000, label="trans 2025")
test_q("Tonnage arrive au port en 2025", "transport_minerai_paa", min_value=900_000, max_value=1_500_000, label="port 2025")

print("\n[A.5] Qualite echantillons — teneurs plausibles")
# Al2O3 ~47-51%, SiO2 ~3-6%, Fe2O3 ~18-21%
test_q("Teneur Al2O3 des echantillons en 2025", "qualite_echantillons",
       must_contain="Al2O3", label="Al2O3 dans reponse")
test_q("Teneur SiO2 en 2025", "qualite_echantillons",
       must_contain="SiO2", label="SiO2 dans reponse")
test_q("Teneur Fe2O3 en 2025", "qualite_echantillons",
       must_contain="Fe2O3", label="Fe2O3 dans reponse")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC B — QUESTIONS PIEGES (frontières inter-handlers)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[B.1] Ambiguïtés tonnage : descendu vs excavé vs transporté")
r1 = test_q("Quel tonnage en 2025 ?", must_not_be_none=True, label="general tonnage")
r2 = test_q("Tonnage excave en 2025", "excavation", label="doit aller en excavation")
r3 = test_q("Tonnage transporte en 2025", "transport_minerai_paa", label="doit aller en transport")
# Vérifier que les 3 réponses donnent des VALEURS DIFFÉRENTES (3 tables ≠)
if r1 and r2 and r3:
    n1, n2, n3 = _extract_number(r1), _extract_number(r2), _extract_number(r3)
    if n1 and n2 and n3 and n1 != n2 and n1 != n3:
        results["passed"] += 1
        print(f"  {PASS} [COHERENCE] 3 tonnages distincts : {n1:,.0f} / {n2:,.0f} / {n3:,.0f}")
    elif n1 and n2 and n3:
        results["failed"] += 1
        failures.append(("COHERENCE", "Tonnages descendu/excave/transporte identiques", f"{n1}/{n2}/{n3}"))
        print(f"  {FAIL} [COHERENCE] Tonnages identiques = probablement la meme table : {n1}/{n2}/{n3}")

print("\n[B.2] Carburant : citerne vs activités vs trencher")
test_q("Carburant consomme en 2024", "carburant_citerne", label="citerne")
test_q("Fuel consomme par la trencher en 2024", "carburant_citerne", label="fuel trencher → citerne pas journal")
test_q("Gasoil en 2024", "carburant_citerne", label="gasoil → citerne")
test_q("Pannes de la trencher en 2025", must_not_contain="carburant", label="pannes ≠ carburant")

print("\n[B.3] Personnel vs responsable site")
test_q("Qui est responsable du site en 2025 ?", "descente_minerai",
       must_not_contain="Agnero", label="responsable site → descente pas personnel")
test_q("Liste du personnel de la mine", "personnel", label="personnel → table personnel")
test_q("Quels metiers sur la mine ?", "personnel", label="metiers → table personnel")

print("\n[B.4] Qualité : descente vs echantillons")
test_q("Qualite du minerai", "descente_minerai",
       must_contain="PREMIER CHOIX", label="qualite descente = PREMIER CHOIX")
test_q("Teneur Al2O3 en 2025", "qualite_echantillons",
       must_not_contain="PREMIER CHOIX", label="Al2O3 → echantillons pas descente")
test_q("Analyse labo 2025", "qualite_echantillons", label="labo → echantillons")

print("\n[B.5] Journal vs observations tombereaux")
test_q("Pannes de la trencher en 2026", "journal",
       must_not_be_none=True, label="trencher → journal")
test_q("Pannes tombereaux en 2025", "descente_minerai",
       must_not_be_none=True, label="tombereaux → descente")
test_q("Bilan des arrets techniques 2025", "journal",
       must_not_be_none=True, label="arret technique → journal")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC C — GRANULARITÉS TEMPORELLES AVANCÉES")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[C.1] Semaines ISO")
test_q("Tonnage S1 2025", "descente_minerai", min_value=1_000, label="S1=semaine1")
test_q("Tonnage semaine 10 en 2025", "descente_minerai", min_value=500, label="semaine 10")
test_q("Tonnage S1 a S12 2025", "descente_minerai", min_value=10_000, label="plage S1-S12")
test_q("Tonnage W5 2026", "descente_minerai", min_value=100, label="W5=semaine5")

print("\n[C.2] Trimestres et semestres")
test_q("Tonnage T1 2025", "descente_minerai", min_value=50_000, label="T1 2025")
test_q("Tonnage T2 2025", "descente_minerai", min_value=50_000, label="T2 2025")
test_q("Tonnage T3 2025", "descente_minerai", min_value=100_000, label="T3 2025")
test_q("Tonnage T4 2025", "descente_minerai", min_value=50_000, label="T4 2025")
test_q("Tonnage S1 2025 (premier semestre)", "descente_minerai", min_value=100_000, label="S1=semestre1")
test_q("Tonnage S2 2025 (deuxieme semestre)", "descente_minerai", min_value=100_000, label="S2=semestre2")
# T1+T2 doit ≈ S1
r_t1 = test_q("Tonnage T1 2025", "descente_minerai", label="T1")
r_t2 = test_q("Tonnage T2 2025", "descente_minerai", label="T2")
r_s1 = test_q("Tonnage semestre 1 2025", "descente_minerai", label="S1")
if r_t1 and r_t2 and r_s1:
    n_t1, n_t2, n_s1 = _extract_number(r_t1), _extract_number(r_t2), _extract_number(r_s1)
    if n_t1 and n_t2 and n_s1:
        diff = abs((n_t1 + n_t2) - n_s1)
        if diff < 100:
            results["passed"] += 1
            print(f"  {PASS} [COHERENCE] T1+T2={n_t1+n_t2:,.0f} ≈ S1={n_s1:,.0f} (diff={diff:.0f})")
        else:
            results["failed"] += 1
            failures.append(("COHERENCE", "T1+T2 ≠ Semestre 1", f"T1={n_t1} T2={n_t2} S1={n_s1} diff={diff:.0f}"))
            print(f"  {FAIL} [COHERENCE] T1({n_t1:,.0f})+T2({n_t2:,.0f})={n_t1+n_t2:,.0f} ≠ S1({n_s1:,.0f}) diff={diff:.0f}")

print("\n[C.3] Mois précis")
test_q("Tonnage janvier 2025", "descente_minerai", min_value=1_000, label="jan 2025")
test_q("Tonnage en decembre 2025", "descente_minerai", min_value=1_000, label="dec 2025")
test_q("Tonnage mars 2026", "descente_minerai", min_value=1_000, label="mars 2026")
test_q("Heures machine en janvier 2025", "shifts_horaires", min_value=50, label="HM jan 2025")
test_q("Heures tambour en fevrier 2025", "shifts_horaires", min_value=10, label="tambour fev 2025")

print("\n[C.4] Date précise")
test_q("Tonnage le 03/02/2026", must_not_be_none=True, label="03/02/2026")
test_q("Quel tonnage le 15/01/2025 ?", must_not_be_none=True, label="15/01/2025")

print("\n[C.5] Comparaison multi-années")
test_q("Comparer 2024 et 2025", "descente_minerai",
       must_contain="2024", label="compare 2024/2025")
test_q("Evolution tonnage 2024 vs 2026", "descente_minerai", must_contain="2024", label="2024 vs 2026")
test_q("Ecart de production entre 2024 et 2025", "descente_minerai", label="ecart 2024-2025")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC D — QUESTIONS MULTI-ANGLES (10+ formulations du même fait)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[D.1] Heures machine 2025 — 10 formulations différentes")
HM_2025_QUESTIONS = [
    ("Heures machine en 2025", "shifts_horaires"),
    ("Heures machine par mois en 2025", "shifts_horaires"),
    ("Total heures machine 2025", "shifts_horaires"),
    ("Combien d'heures machine en 2025 ?", "shifts_horaires"),
    ("Temps de travail des engins en 2025", "shifts_horaires"),
    ("HM en 2025", "shifts_horaires"),
    ("Shift 2025 heures", "shifts_horaires"),
    ("Vacation 2025", "shifts_horaires"),
    ("Disponibilite engin 2025", "shifts_horaires"),
    ("Taux disponibilite des engins en 2025", "shifts_horaires"),
]
for q, tbl in HM_2025_QUESTIONS:
    test_q(q, tbl, min_value=500, label="HM-multi")

print("\n[D.2] Tonnage descendu 2025 — 10 formulations")
TON_2025_QUESTIONS = [
    "Tonnage par mois en 2025",
    "Combien de tonnes en 2025 ?",
    "Production journaliere 2025",
    "Quantite de minerai descendue en 2025",
    "Descente 2025",
    "Tonnage 2025",
    "Minerai produit en 2025",
    "Tonnes descendues en 2025",
    "Production 2025",
    "Volume descente 2025",
]
for q in TON_2025_QUESTIONS:
    # "par mois" retourne un tableau — on vérifie juste la table, pas la valeur
    is_monthly = "par mois" in q.lower() or "mensuel" in q.lower()
    test_q(q, "descente_minerai",
           min_value=None if is_monthly else 50_000,
           label="TON-multi")

print("\n[D.3] Actions HSE non réalisées — 5 formulations")
for q in [
    "Actions HSE non realisees",
    "Obligations non realisees",
    "Quelles obligations sont encore a faire ?",
    "Bilan des actions non faites HSE",
    "Statut non realise des obligations",
]:
    test_q(q, "suivi_actions", must_contain="Non réalisé", label="HSE-multi")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC E — COHÉRENCE LOGIQUE DES RÉPONSES")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[E.1] Tonnage par mois doit sommer au total annuel (±5%)")
r_total = test_q("Tonnage total en 2025", "descente_minerai", label="total 2025")
r_mois  = test_q("Tonnage par mois en 2025", "descente_minerai", label="par mois 2025")
if r_total and r_mois:
    total_annuel = _extract_number(r_total)
    # Extraire TOTAL depuis la réponse mensuelle
    m = re.search(r"TOTAL\s*:\s*([\d,]+)", r_mois)
    if m:
        total_mois = float(m.group(1).replace(",", ""))
        if total_annuel and abs(total_mois - total_annuel) / total_annuel < 0.05:
            results["passed"] += 1
            print(f"  {PASS} [COHERENCE] Total mensuel {total_mois:,.0f} ≈ total annuel {total_annuel:,.0f}")
        elif total_annuel:
            results["failed"] += 1
            ecart_pct = abs(total_mois - total_annuel) / total_annuel * 100
            failures.append(("COHERENCE", "Total mois ≠ total annuel", f"{total_mois:,.0f} vs {total_annuel:,.0f} ({ecart_pct:.1f}%)"))
            print(f"  {FAIL} [COHERENCE] Total mois {total_mois:,.0f} ≠ annuel {total_annuel:,.0f} ({ecart_pct:.1f}%)")

print("\n[E.2] T1+T2+T3+T4 doit sommer à l'annuel 2025")
totaux = []
for q_trim in ["Tonnage T1 2025", "Tonnage T2 2025", "Tonnage T3 2025", "Tonnage T4 2025"]:
    r = analytics.handle(con, q_trim)
    n = _extract_number(r) if r else None
    totaux.append(n)
    print(f"    {q_trim}: {n:,.0f}" if n else f"    {q_trim}: N/A")
if all(totaux):
    somme = sum(totaux)
    r_ann = analytics.handle(con, "Tonnage total en 2025")
    n_ann = _extract_number(r_ann) if r_ann else None
    if n_ann:
        diff = abs(somme - n_ann)
        if diff < 500:
            results["passed"] += 1
            print(f"  {PASS} [COHERENCE] T1+T2+T3+T4={somme:,.0f} ≈ annuel={n_ann:,.0f} (diff={diff:.0f})")
        else:
            results["failed"] += 1
            failures.append(("COHERENCE", "T1+T2+T3+T4 ≠ annuel 2025", f"{somme:,.0f} vs {n_ann:,.0f}"))
            print(f"  {FAIL} [COHERENCE] T1+T2+T3+T4={somme:,.0f} ≠ annuel={n_ann:,.0f} diff={diff:.0f}")

print("\n[E.3] Excavation > Descente (on excave plus qu'on descend)")
r_exc = analytics.handle(con, "Tonnage excave en 2025")
r_des = analytics.handle(con, "Tonnage total en 2025")
n_exc = _extract_number(r_exc) if r_exc else None
n_des = _extract_number(r_des) if r_des else None
if n_exc and n_des:
    if n_exc > n_des * 0.8:
        results["passed"] += 1
        print(f"  {PASS} [COHERENCE] Excavé({n_exc:,.0f}) > Descendu({n_des:,.0f}) × 0.8")
    else:
        results["failed"] += 1
        failures.append(("COHERENCE", "Excavé < Descendu×0.8", f"Exc={n_exc:,.0f} Desc={n_des:,.0f}"))
        print(f"  {FAIL} [COHERENCE] Excavé({n_exc:,.0f}) < Descendu({n_des:,.0f}) × 0.8")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC F — DONNÉES HORS PORTÉE (doit retourner message clair)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[F.1] Années inexistantes dans les données")
# Les données sont 2023-2026, donc 2020 et 2030 n'existent pas
test_q("Tonnage en 2020", must_not_be_none=True,
       must_not_contain="1,156", label="2020 doit dire annee inconnue")
test_q("Heures machine en 2030", "shifts_horaires",
       must_not_be_none=True, label="2030 message no data")
test_q("Tonnage en 2019", must_not_be_none=True, label="2019 hors portée")

print("\n[F.2] Questions sans données → message utile (pas None)")
test_q("Heures tambour TRS N°999 en 2025", must_not_be_none=True,
       must_not_contain="None", label="TRS 999 inexistant")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC G — QUESTIONS COMPLEXES ET SPÉCIFIQUES")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[G.1] Questions spécifiques sur les données personnel")
test_q("Quel est le metier de Agnero Liliane ?", "personnel",
       must_contain="Superviseur", label="Agnero=Superviseur")
test_q("Liste des superviseurs", "personnel",
       must_contain="Agnero", label="superviseurs liste")
test_q("Effectif de la mine", "personnel",
       must_contain="personnes", label="effectif nb personnes")
test_q("Metiers sur la mine", "personnel", must_not_be_none=True, label="liste metiers")

print("\n[G.2] Questions PGES et HSE spécifiques")
test_q("Actions PGES non realisees", "pges_actions",
       must_not_be_none=True, label="PGES non realise")
test_q("Recommandations ANDE avancement", "pges_actions",
       must_not_be_none=True, label="ANDE avancement")
test_q("Obligations HSE en cours de realisation", "suivi_actions",
       must_not_be_none=True, label="HSE en cours")
test_q("Action n 5 PGES", "pges_actions", must_not_be_none=True, label="PGES action 5")
test_q("Actions correctives urgentes", "suivi_actions", must_not_be_none=True, label="urgentes")

print("\n[G.3] Questions transport spécifiques")
test_q("Rotations de transport en 2025", "transport_minerai_paa",
       must_not_be_none=True, label="rotations PAA")
test_q("Societe de transport en 2026", must_not_be_none=True, label="societe transport")
test_q("Tonnage transporte par mois 2025", "transport_minerai_paa",
       min_value=50_000, label="transport mensuel")
test_q("Tonnage arrive au port en 2025", "transport_minerai_paa",
       min_value=900_000, label="port 2025")

print("\n[G.4] Questions journal spécifiques")
test_q("Bilan des pannes trencher en 2025", "journal",
       must_not_be_none=True, label="pannes trencher 2025")
test_q("Journal de la trencher en 2026", "journal",
       min_value=90, max_value=500, label="journal 2026 ~99 entrees")
test_q("Pannes GPS trencher 2024", "journal",
       must_not_be_none=True, label="GPS 2024")
test_q("Liste des pannes mecaniques en 2025", must_not_be_none=True, label="mecanique 2025")

print("\n[G.5] Questions qualité navires")
test_q("Tonnage charge sur navire en 2025", "productivite_loading",
       min_value=50_000, label="loading 2025")
test_q("Quels navires en 2025 ?", "productivite_loading",
       must_not_be_none=True, label="liste navires 2025")

print("\n[G.6] Questions carburant détaillées")
test_q("Carburant par engin en 2024", "carburant_citerne",
       must_not_be_none=True, label="carburant par engin")
test_q("Total carburant consomme en 2024", "carburant_citerne",
       min_value=50_000, max_value=500_000, label="total carburant 2024")
test_q("Depotage citerne 2024", "carburant_citerne",
       must_not_be_none=True, label="depotage")

print("\n[G.7] Questions excavation détaillées")
test_q("Volume excave par zone en 2025", "excavation", must_not_be_none=True, label="zone excav")
test_q("Tonnage excave par mois en 2025", "excavation",
       must_contain="excavé", label="mois excav 2025")
test_q("Tonnage QD en 2025", "excavation", must_contain="QD", label="QD 2025")
test_q("Tonnage BQ en 2025", "excavation", must_contain="BQ", label="BQ 2025")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC H — QUESTIONS QUI NE DOIVENT PAS ALLER EN SQL")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[H.1] Math purs → None (pas SQL)")
math_questions = [
    "10 / 1.5",
    "125 + 48 - 13",
    "15% de 3500",
    "Racine carree de 144",
    "2 puissance 10",
    "Combien font 12 fois 15 ?",
    "CAGR si on passe de 1200 a 1850 en 3 ans",
    "Convertir 5000 kg en tonnes",
    "Si un camion fait 30T par voyage, combien de voyages pour 1000T ?",
    "30 divise par 1.5",
]
for q in math_questions:
    test_q(q, must_not_be_none=False, label="math→None")

print("\n[H.2] Questions générales → None (pas SQL)")
general_questions = [
    "Bonjour",
    "Quel temps fait-il ?",
    "Quelle est la capitale de la Cote d'Ivoire ?",
    "Qu'est-ce que la bauxite ?",
    "Comment fonctionne un tombereau ?",
    "Bonne journee",
    "Merci",
]
for q in general_questions:
    test_q(q, must_not_be_none=False, label="general→None")


# ════════════════════════════════════════════════════════════════════════════
# RAPPORT FINAL
# ════════════════════════════════════════════════════════════════════════════

total = results["passed"] + results["failed"] + results["no_handler"]
print("\n" + "="*70)
print("RAPPORT FINAL — TESTS AVANCÉS")
print("="*70)
print(f"  Total questions testées : {total}")
print(f"  {PASS} Passés         : {results['passed']}")
print(f"  {FAIL} Handler absent : {results['no_handler']}")
print(f"  {FAIL} Échecs         : {results['failed']}")
score = round(results["passed"] / total * 100, 1) if total else 0
print(f"\n  SCORE : {score}% ({results['passed']}/{total})")

if failures:
    print("\n" + "-"*70)
    print("DÉTAIL DES ÉCHECS :")
    for typ, q, info in failures:
        print(f"  [{typ}] {q}")
        print(f"    → {info}")

print("="*70)
