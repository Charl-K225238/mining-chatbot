# -*- coding: utf-8 -*-
"""
test_routing_exhaustif.py
=========================
Tests exhaustifs du moteur analytique de Miny.

50+ questions par domaine de table pour depister :
  - Les questions qui tombent en LLM alors qu'une table repond (routing rate)
  - Les mauvaises tables interrogees (mauvais handler)
  - Les reponses vides (handler declenche mais SQL retourne rien)
  - Les bugs de mots-cles manquants

Executer :
  .venv\\Scripts\\python.exe test/test_routing_exhaustif.py
  ou :
  .venv\\Scripts\\python.exe -m pytest test/test_routing_exhaustif.py -v
"""
import io, sys, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import duckdb

# Charger DuckDB directement (sans passer par get_db pour eviter les imports lourds)
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
    print(f"[WARN] get_db() indisponible ({e}), connexion directe DuckDB")
    con = _make_con()

from src.engine import analytics

# ── Helpers ─────────────────────────────────────────────────────────────────

def _table_from_response(resp: str) -> str:
    """Extrait le nom de la table depuis l'attribution _📋 TABLE_."""
    if resp and "_📋" in resp:
        after = resp.split("_📋")[-1].strip()
        # Format: "descente_minerai_" ou "descente_minerai · extra_"
        # Prendre le premier token avant espace ou ·
        token = after.split()[0] if after else ""
        # Supprimer underscore final
        return token.rstrip("_").strip()
    return "UNKNOWN"

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
SKIP = "⏭️"

results = {
    "passed": 0,
    "failed": 0,
    "no_handler": 0,
    "warnings": 0,
}
failures = []

def test_q(question: str,
           expected_table: str | None = None,
           must_not_be_none: bool = True,
           must_contain: str | None = None,
           must_not_contain: str | None = None,
           year_hint: int | None = None) -> str | None:
    """
    Teste une question et affiche le resultat.
    Retourne la reponse ou None.
    """
    try:
        resp = analytics.handle(con, question)
    except Exception as exc:
        resp = None
        print(f"  {FAIL} EXCEPTION: {exc}")

    if resp is None:
        if must_not_be_none:
            results["no_handler"] += 1
            failures.append(("NO_HANDLER", question, expected_table))
            print(f"  {FAIL} AUCUN HANDLER  → q: {question[:80]}")
        else:
            results["passed"] += 1
            print(f"  {PASS} None (attendu)  → q: {question[:60]}")
        return None

    actual_table = _table_from_response(resp)
    resp_preview = resp[:100].replace("\n", " ")

    # Verif table
    table_ok = True
    if expected_table:
        table_ok = expected_table.lower() in actual_table.lower()

    # Verif contenu
    content_ok = True
    if must_contain:
        content_ok = must_contain.lower() in resp.lower()
    not_ok = False
    if must_not_contain:
        not_ok = must_not_contain.lower() in resp.lower()

    if table_ok and content_ok and not not_ok:
        results["passed"] += 1
        print(f"  {PASS} [{actual_table}]  {resp_preview[:70]}")
    elif not table_ok:
        results["failed"] += 1
        failures.append(("WRONG_TABLE", question, f"attendu={expected_table}, obtenu={actual_table}"))
        print(f"  {FAIL} MAUVAISE TABLE attendu={expected_table} obtenu={actual_table}  |  {resp_preview[:50]}")
    elif not content_ok:
        results["warnings"] += 1
        failures.append(("CONTENT", question, f"manque '{must_contain}' dans reponse"))
        print(f"  {WARN} Contenu manquant '{must_contain}'  |  {resp_preview[:50]}")
    elif not_ok:
        results["warnings"] += 1
        failures.append(("CONTENT_BAD", question, f"contient '{must_not_contain}' indesirable"))
        print(f"  {WARN} Contient mot indesirable '{must_not_contain}'  |  {resp_preview[:50]}")

    return resp


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 1 — DESCENTE MINERAI (tonnage descendu)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[1.1] Tonnage annuel / scalaire")
test_q("Tonnage par mois en 2025", "descente_minerai", must_contain="2025")
test_q("Tonnage par mois en 2026", "descente_minerai", must_contain="2026")
test_q("Tonnage total en 2024", "descente_minerai", must_contain="2024")
test_q("Combien de tonnes descendues en 2025 ?", "descente_minerai")
test_q("Production de minerai en 2026", "descente_minerai")
test_q("Tonnage descendu en janvier 2026", "descente_minerai")
test_q("Quantite journaliere descendue en mars 2025", "descente_minerai")
test_q("Tonnage en T1 2025", "descente_minerai")
test_q("Tonnage en S1 2025", "descente_minerai")
test_q("Tonnage semestre 1 2024", "descente_minerai")
test_q("Tonnage trimestre 3 2025", "descente_minerai")

print("\n[1.2] Comparaison annees")
test_q("Comparer 2024 et 2025", "descente_minerai", must_contain="2024")
test_q("Evolution du tonnage 2024 vs 2025", "descente_minerai")
test_q("Ecart de tonnage entre 2025 et 2026", "descente_minerai")
test_q("Difference de production 2024 vs 2026", "descente_minerai")

print("\n[1.3] Voyages")
test_q("Nombre de voyages en 2025", "descente_minerai")
test_q("Combien de voyages en mars 2026 ?", "descente_minerai")
test_q("Voyages par mois en 2024", "descente_minerai")

print("\n[1.4] Tombereaux / engins descente")
test_q("Combien de tombereaux actifs en 2025 ?", "descente_minerai")
test_q("Liste des tombereaux en 2026", "descente_minerai")
test_q("Top engins de descente 2026", "descente_minerai")
test_q("Quel tombereau a fait le plus de tonnage en 2025 ?", "descente_minerai")

print("\n[1.5] Zones et qualite")
test_q("Top zones de stockage 2025", "descente_minerai")
test_q("Zones de stockage utilisees en 2026", "descente_minerai")
test_q("Qualite du minerai en 2025", expected_table=None)  # peut aller en qualite_echantillons aussi

print("\n[1.6] Observations / pannes tombereaux")
test_q("Pannes tombereaux en 2025", expected_table="descente_minerai")
test_q("Incidents sur les tombereaux 2026", expected_table="descente_minerai")
test_q("Observations de descente en 2025", expected_table="descente_minerai")

print("\n[1.7] Responsable site")
test_q("Qui est responsable du site ?", "descente_minerai")
test_q("Quel est le responsable du site en 2026 ?", "descente_minerai")
test_q("Responsable site en 2025", "descente_minerai")

print("\n[1.8] Societe de transport")
test_q("Quelle societe de transport en 2026 ?", "descente_minerai")
test_q("Societes de transport actives en 2025", "descente_minerai")

print("\n[1.9] Tonnage par voyage")
test_q("Tonnage moyen par voyage en 2025", "descente_minerai")
test_q("Tonnage par voyage en 2026", "descente_minerai")

print("\n[1.10] Semaines ISO")
test_q("Tonnage semaine 17 en 2026", "descente_minerai")
test_q("Tonnage S5 2025", "descente_minerai")
test_q("Tonnage S1 a S6 2026", "descente_minerai")

print("\n[1.11] Donnees disponibles / meta")
test_q("Quelles annees de donnees disponibles ?", must_not_be_none=True)
test_q("Quelles tables sont disponibles ?", must_not_be_none=True)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 2 — SHIFTS HORAIRES (heures machine / tambour / moteur)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[2.1] Heures machine — keywords de base")
test_q("Heures machine par mois en 2025", "shifts_horaires")
test_q("Heures machine en 2025", "shifts_horaires")
test_q("Heures machine en 2026", "shifts_horaires")
test_q("Total heures machine 2024", "shifts_horaires")
test_q("Combien d'heures machine en 2025 ?", "shifts_horaires")

print("\n[2.2] Heures tambour — BUG POTENTIEL")
test_q("Heures tambour en 2025", "shifts_horaires")  # BUG: "tambour" absent des kw_shifts
test_q("Total heures tambour 2025", "shifts_horaires")
test_q("Heures tambour par mois en 2025", "shifts_horaires")
test_q("Heure tambour en 2026", "shifts_horaires")
test_q("Quel est le total des heures tambour en 2025 ?", "shifts_horaires")
test_q("Heures de tambour en 2024", "shifts_horaires")

print("\n[2.3] Heures moteur")
test_q("Heures moteur en 2025", "shifts_horaires")
test_q("Heure moteur 2026", "shifts_horaires")
test_q("Total heures moteur 2024", "shifts_horaires")

print("\n[2.4] Shifts / vacations")
test_q("Shift de travail en 2025", "shifts_horaires")
test_q("Nombre de shifts en 2026", "shifts_horaires")
test_q("Vacation en 2025", "shifts_horaires")
test_q("Poste de travail 2025", "shifts_horaires")
test_q("Horaires de travail en 2025", "shifts_horaires")

print("\n[2.5] Disponibilite engins")
test_q("Taux de disponibilite des engins en 2025", "shifts_horaires")
test_q("Disponibilite engin en 2026", "shifts_horaires")
test_q("Temps de travail des engins 2025", "shifts_horaires")

print("\n[2.6] Par engin / ventilation")
test_q("Heures machine par engin en 2025", "shifts_horaires")
test_q("Heures machine par mois 2026 trencher", "shifts_horaires")
test_q("Heures machine TRS 296 en 2025", "shifts_horaires")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 3 — PERSONNEL (41 lignes) et SHIFTS_PERSONNEL (6828 lignes)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[3.1] Liste personnel / metiers — BUG POTENTIEL (aucun handler)")
test_q("Liste des employes", expected_table="personnel", must_not_be_none=True)
test_q("Qui travaille sur la mine ?", must_not_be_none=True)
test_q("Effectif du personnel", must_not_be_none=True)
test_q("Combien d'employes ?", must_not_be_none=True)
test_q("Quels sont les metiers sur la mine ?", must_not_be_none=True)
test_q("Corps de metier par categorie", must_not_be_none=True)
test_q("Liste des operateurs", must_not_be_none=True)
test_q("Qui sont les superviseurs ?", must_not_be_none=True)
test_q("Metier de chaque employe", must_not_be_none=True)
test_q("Quels postes existent sur le site ?", must_not_be_none=True)

print("\n[3.2] Recherche individuelle — BUG POTENTIEL")
test_q("Quel est le metier de Agnero Liliane ?", must_not_be_none=True)
test_q("Quel poste occupe Armand Agoussi ?", must_not_be_none=True)
test_q("Qui est Lassina ?", must_not_be_none=True)
test_q("Metier de Coulibaly Melissa", must_not_be_none=True)

print("\n[3.3] Shifts personnel — presence operateurs")
test_q("Qui etait en shift 1 le 03/01/2024 ?", must_not_be_none=True)
test_q("Operateurs presents en 2025", must_not_be_none=True)
test_q("Nombre d'operateurs par shift en 2025", must_not_be_none=True)
test_q("Heure d'arrivee des operateurs sur le plateau", must_not_be_none=True)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 4 — JOURNAL (pannes trencher / engins lourds)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Pannes de la trencher en 2025", "journal")
test_q("Journal de la trencher en 2025", "journal")
test_q("Incidents trencher 2026", "journal")
test_q("Bilan des arrets techniques en 2025", "journal")
test_q("Pannes TRS 296 en 2025", "journal")
test_q("Pannes TRS 1347 en 2025", "journal")
test_q("Combien de pannes trencher en 2025 ?", "journal")
test_q("Liste des pannes en 2024", expected_table=None, must_not_be_none=True)  # tombereaux ou journal
test_q("Dernieres pannes enregistrees dans le journal", "journal")
test_q("Pannes de type mecanique en 2025", expected_table=None, must_not_be_none=True)
test_q("Pannes liees aux GPS en 2024", "journal")
test_q("Arrets GPS de la trencher", "journal")
test_q("Pannes pelle en 2025", "journal")
test_q("Pannes foreuse 2025", "journal")
test_q("Journal engin lourd 2024", "journal")
test_q("Arret technique trencher 2026", "journal")
test_q("Breakdown trencher 2025", "journal")
test_q("Maintenance trencher 2024", "journal")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 5 — EXCAVATION")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Tonnage excave en 2025", "excavation")
test_q("Volume excave en 2025", "excavation")
test_q("Excavation par mois en 2026", "excavation")
test_q("Tonnage excave par zone en 2025", "excavation")
test_q("Tonnage QD en 2025", "excavation")
test_q("Tonnage MQ excave en 2025", "excavation")
test_q("Production excavation 2024", "excavation")
test_q("Combien de tonnes excavees en 2026 ?", "excavation")
test_q("Lineaire excave en 2025", "excavation")
test_q("Profondeur moyenne excavation 2025", "excavation")
test_q("Zone d'excavation en 2025", "excavation")
test_q("Tonnage BQ excave en 2025", "excavation")
test_q("Volume excave par zone en 2026", "excavation")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 6 — TRANSPORT (mine → port) et LOADING (navires)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Tonnage transporte en 2025", "transport_minerai_paa")
test_q("Tonnage arrive au port en 2026", "transport_minerai_paa")
test_q("Quantite transportee en 2025", "transport_minerai_paa")
test_q("Rotations de transport en 2025", "transport_minerai_paa")
test_q("Societe de transport PAA 2025", "transport_minerai_paa")
test_q("Tonnage transporte par mois 2025", "transport_minerai_paa")
test_q("Voyage camion mine port 2026", "transport_minerai_paa")
test_q("Quantite PAA 2025", "transport_minerai_paa")

print("\n[6.2] Navires / loading")
test_q("Chargement navire en 2025", "productivite_loading")
test_q("Quantite chargee sur navire 2025", "productivite_loading")
test_q("Productivite port en 2025", "productivite_loading")
test_q("Tonnage charge navire 2026", "productivite_loading")
test_q("Navires en 2025", "productivite_loading")
test_q("Depart navire 2026", "productivite_loading")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 7 — CARBURANT CITERNE et CARBURANT ACTIVITES")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[7.1] Carburant citerne")
test_q("Consommation carburant en 2024", "carburant_citerne")
test_q("Gasoil consomme en 2024", "carburant_citerne")
test_q("Litres de carburant servis en 2024", "carburant_citerne")
test_q("Depotage citerne 2024", "carburant_citerne")
test_q("Carburant par engin en 2024", "carburant_citerne")
test_q("Consommation diesel 2024", "carburant_citerne")
test_q("Fuel consomme par la trencher en 2024", "carburant_citerne")

print("\n[7.2] Carburant activites — BUG POTENTIEL (aucun handler)")
test_q("Heures d'activite par machine en 2025", must_not_be_none=True)
test_q("Heures de fonctionnement des engins en 2025", must_not_be_none=True)
test_q("Activites des machines en 2025", must_not_be_none=True)
test_q("Operateur principal de la trencher", must_not_be_none=True)
test_q("Heures excavation par machine en 2026", must_not_be_none=True)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 8 — QUALITE (echantillons et navires)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Qualite des echantillons en 2025", "qualite_echantillons")
test_q("Teneur Al2O3 des echantillons en 2025", "qualite_echantillons")
test_q("Teneur SiO2 en 2025", "qualite_echantillons")
test_q("Teneur Fe2O3 en 2025", "qualite_echantillons")
test_q("Analyse labo en 2025", "qualite_echantillons")
test_q("Resultats analyses chimiques 2026", "qualite_echantillons")
test_q("Qualite bauxite par zone en 2025", "qualite_echantillons")
test_q("Echantillons analyses en 2025", "qualite_echantillons")
test_q("Alumine des stocks en 2025", "qualite_echantillons")
test_q("Silice dans les echantillons 2025", "qualite_echantillons")
test_q("Laboratoire SGS resultats 2025", "qualite_echantillons")

print("\n[8.2] Qualite navires — BUG POTENTIEL (aucun handler)")
test_q("Qualite du minerai sur les navires 2024", must_not_be_none=True)
test_q("Teneur Al2O3 navires 2024", must_not_be_none=True)
test_q("Resultats analyse navire 2024", must_not_be_none=True)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 9 — OBJECTIFS")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Objectif de production en 2025", "objectifs")
test_q("Prevision tonnage 2026", "objectifs")
test_q("Taux de realisation en 2025", "objectifs")
test_q("Objectif descente prevu en 2025", "objectifs")
test_q("Objectif excavation 2026", "objectifs")
test_q("Realise vs prevu en 2025", "objectifs")
test_q("Planification production 2025", "objectifs")
test_q("Objectif mensuel en janvier 2026", "objectifs")
test_q("Taux d'accomplissement 2025", "objectifs")
test_q("Production prevue en T1 2025", "objectifs")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 10 — HSE / PGES (suivi_actions et pges_actions)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Actions HSE non realisees", "suivi_actions")
test_q("Obligations HSE en cours", "suivi_actions")
test_q("Actions correctives urgentes", "suivi_actions")
test_q("Quelles obligations sont non realisees ?", "suivi_actions")
test_q("Rapport mensuel de production HSE", "suivi_actions")
test_q("Actions PGES non realisees", "pges_actions")
test_q("Avancement des actions PGES", "pges_actions")
test_q("Actions PGES en cours", "pges_actions")
test_q("Recommandations ANDE", "pges_actions")
test_q("Plan de gestion environnemental avancement", "pges_actions")
test_q("Actions responsable N'guessan", "suivi_actions")
test_q("Obligations avec deadline depassee", "suivi_actions")
test_q("Actions prioritaires urgentes", "suivi_actions")
test_q("Niveau avancement PGES", "pges_actions")
test_q("Action PGES numero 14", "pges_actions")
test_q("Actions de rehabilitation", "pges_actions")
test_q("Gestion des dechets PGES", "pges_actions")


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 11 — BUDGET (table orpheline)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Budget de production en 2025", must_not_be_none=True)
test_q("Tonnage prevu au budget en 2025", must_not_be_none=True)
test_q("Budget descente 2025", must_not_be_none=True)
test_q("Tonnage a produire selon le budget", must_not_be_none=True)
test_q("Prevision budgetaire 2025", must_not_be_none=True)
test_q("Budget mensuel 2025", must_not_be_none=True)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 12 — CALCULS MATHEMATIQUES (ne doit PAS aller en SQL)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[12.1] Ces questions doivent retourner None (le router les envoie au LLM math)")
test_q("10 / 1.5", must_not_be_none=False)
test_q("Calcule 10 divise par 1.5", must_not_be_none=False)
test_q("Si j'ai 10L et depense 1.5L par jour, combien de jours ?", must_not_be_none=False)
test_q("15% de 3500", must_not_be_none=False)
test_q("125 + 48", must_not_be_none=False)
test_q("Racine carree de 144", must_not_be_none=False)
test_q("Combien font 12 fois 15 ?", must_not_be_none=False)
test_q("Convertir 5000 kg en tonnes", must_not_be_none=False)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 13 — QUESTIONS GENERALES (ne doivent PAS aller en SQL)")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

test_q("Bonjour", must_not_be_none=False)
test_q("Quelle est la capitale de la Cote d'Ivoire ?", must_not_be_none=False)
test_q("C'est quoi le PGES ?", must_not_be_none=False)
test_q("Qu'est-ce que la bauxite ?", must_not_be_none=False)
test_q("Comment fonctionne une trencher ?", must_not_be_none=False)


# ════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("BLOC 14 — FORMULATIONS AMBIGUEES / VARIANTES")
print("="*70)
# ════════════════════════════════════════════════════════════════════════════

print("\n[14.1] Synonymes et formulations naturelles")
test_q("Quelle quantite de minerai a ete descendue en 2025 ?", "descente_minerai")
test_q("Production mensuelle 2026", "descente_minerai")
test_q("Combien de tonnes en 2025 ?", "descente_minerai")
test_q("Taux de realisation objectif 2025", "objectifs")
test_q("Quel volume a ete extrait en 2025 ?", "excavation")
test_q("Combien de litres de diesel en 2024 ?", "carburant_citerne")
test_q("Bilan pannes trencher 2025", "journal")
test_q("Heure de marche trencher 2025", "shifts_horaires")
test_q("Heures de fonctionnement 2025", "shifts_horaires")

print("\n[14.2] Questions avec annee absente (doivent quand meme repondre)")
test_q("Tonnage total", "descente_minerai")
test_q("Derniere panne de la trencher", "journal")
test_q("Dernieres actions HSE", "suivi_actions")


# ════════════════════════════════════════════════════════════════════════════
# RAPPORT FINAL
# ════════════════════════════════════════════════════════════════════════════

total = results["passed"] + results["failed"] + results["no_handler"] + results["warnings"]
print("\n" + "="*70)
print("RAPPORT FINAL")
print("="*70)
print(f"  Total questions testees : {total}")
print(f"  {PASS} Passes         : {results['passed']}")
print(f"  {FAIL} Handler absent : {results['no_handler']}")
print(f"  {FAIL} Mauvaise table : {results['failed']}")
print(f"  {WARN} Avertissements : {results['warnings']}")
score = round(results["passed"] / total * 100, 1) if total else 0
print(f"\n  SCORE : {score}% ({results['passed']}/{total})")

if failures:
    print("\n" + "-"*70)
    print("DETAIL DES ECHECS :")
    print("-"*70)
    for typ, q, info in failures:
        print(f"  [{typ}] {q[:70]}")
        print(f"    → {info}")

print("\n" + "="*70)
