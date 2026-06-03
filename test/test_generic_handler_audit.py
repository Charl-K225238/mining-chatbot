"""
test/test_generic_handler_audit.py

Audit complet du SmartGenericHandler — simule des fichiers Excel uploadés
avec structures variées (noms de colonnes inhabituels, types multiples,
référentiels, tables vides, accents…).

Métriques de scoring :
  - Table correcte identifiée           (poids 40%)
  - Réponse retournée vs attendue       (poids 30%)
  - Contenu attendu présent             (poids 20%)
  - Pas de faux positif                 (poids 10%)

Lancer :
    python -m pytest test/test_generic_handler_audit.py -v
    python test/test_generic_handler_audit.py          (mode standalone avec rapport)
"""

from __future__ import annotations

import sys
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import duckdb

from src.engine import schema_registry as reg
from src.engine.generic_handler import (
    SmartGenericHandler,
    handle_new_table,
    CONFIDENCE_THRESHOLD,
)


# ── Tables "gérées" simulées (comme dans analytics.py) ───────────────────────

_HANDLED = frozenset({
    "descente_minerai", "excavation", "transport_minerai_paa",
    "productivite_loading", "carburant_citerne", "qualite_echantillons",
    "journal", "shifts_horaires", "objectifs", "shifts_personnel",
    "personnel", "pges_actions", "suivi_actions", "dim_date",
})


# ── Construction de la DB de test ─────────────────────────────────────────────

def _build_test_db() -> duckdb.DuckDBPyConnection:
    """
    Crée une DB in-memory avec 9 tables simulant des uploads utilisateurs réels.
    Chaque table représente un scénario distinct (structure, colonnes, accents…).
    """
    con = duckdb.connect(":memory:")

    # ── 1. Série temporelle standard ──────────────────────────────────────────
    con.execute("""
        CREATE TABLE production_poste AS
        SELECT
            DATE '2025-01-01' + (i // 3)::INTEGER              AS date,
            CASE WHEN i%3=0 THEN 'Matin'
                 WHEN i%3=1 THEN 'Apres-midi' ELSE 'Nuit' END      AS poste,
            CASE WHEN i%5=0 THEN 'TRS 296' ELSE 'TRS 1347' END     AS equipement,
            (800 + (i * 7 % 400))::DOUBLE                          AS quantite_produite_T,
            (300 + (i * 3 % 150))::DOUBLE                          AS heures_machine
        FROM range(90) t(i)
    """)

    # ── 2. Colonne date avec nom inhabituel ────────────────────────────────────
    con.execute("""
        CREATE TABLE maintenance_log AS
        SELECT
            DATE '2025-01-01' + (i * 4)::INTEGER               AS date_intervention,
            CASE WHEN i%3=0 THEN 'Preventif'
                 WHEN i%3=1 THEN 'Correctif' ELSE 'Urgent' END     AS type_maintenance,
            ('Equipe ' || (i%4+1)::VARCHAR)                        AS equipe_responsable,
            (2.0 + (i % 6))::DOUBLE                                AS duree_heures,
            (500 + (i * 137 % 2000))::DOUBLE                       AS cout_fcfa
        FROM range(30) t(i)
    """)

    # ── 3. Plusieurs colonnes numériques — sélection pertinente ───────────────
    con.execute("""
        CREATE TABLE suivi_eau AS
        SELECT
            DATE '2024-01-01' + i::INTEGER                   AS date,
            (1000 + (i * 11 % 500))::DOUBLE                        AS volume_m3,
            (50  + (i * 3 % 30))::DOUBLE                           AS debit_l_s,
            (6.5 + (i % 3) * 0.5)::DOUBLE                         AS pH,
            (i * 2 % 50)::DOUBLE                                   AS turbidite_ntu
        FROM range(60) t(i)
    """)

    # ── 4. Référentiel sans date ───────────────────────────────────────────────
    con.execute("""
        CREATE TABLE fournisseurs AS
        SELECT
            ('F00' || i::VARCHAR)                                   AS code_fournisseur,
            CASE WHEN i%4=0 THEN 'Carburant'
                 WHEN i%4=1 THEN 'Pieces detachees'
                 WHEN i%4=2 THEN 'Services' ELSE 'Alimentation' END AS categorie,
            ('Fournisseur ' || i::VARCHAR)                         AS nom,
            CASE WHEN i%3=0 THEN 'Actif' ELSE 'Inactif' END       AS statut
        FROM range(20) t(i)
    """)

    # ── 5. Colonnes avec guillemets nécessaires ────────────────────────────────
    con.execute("""
        CREATE TABLE absences_personnel AS
        SELECT
            DATE '2025-01-01' + (i * 5)::INTEGER               AS "Date_absence",
            CASE WHEN i%3=0 THEN 'Maladie'
                 WHEN i%3=1 THEN 'Conge' ELSE 'Formation' END      AS "Motif",
            CASE WHEN i%4=0 THEN 'Exploitation'
                 WHEN i%4=1 THEN 'Maintenance'
                 WHEN i%4=2 THEN 'Administration'
                 ELSE 'Transport' END                              AS "Departement",
            (1 + i%10)::DOUBLE                                    AS "Nombre_jours"
        FROM range(24) t(i)
    """)

    # ── 6. Multiple colonnes qty — choisir selon la question ──────────────────
    con.execute("""
        CREATE TABLE inventaire_stock AS
        SELECT
            DATE '2025-01-01' + (i * 7)::INTEGER               AS date,
            (5000 + (i * 53 % 1000))::DOUBLE                       AS stock_initial_T,
            ((i * 77) % 2000)::DOUBLE                              AS entrees_T,
            ((i * 61) % 1500)::DOUBLE                              AS sorties_T,
            (4000 + (i * 41 % 2000))::DOUBLE                      AS stock_final_T
        FROM range(20) t(i)
    """)

    # ── 7. Nom de table à 3 segments ──────────────────────────────────────────
    con.execute("""
        CREATE TABLE analyse_eau_usine AS
        SELECT
            DATE '2024-01-01' + (i * 3)::INTEGER               AS date,
            ((i * 17 % 50) * 0.01)::DOUBLE                        AS "Teneur_mg_L",
            CASE WHEN i%2=0 THEN 'Entree' ELSE 'Sortie' END       AS "Point_mesure"
        FROM range(40) t(i)
    """)

    # ── 8. Table vide (edge case) ──────────────────────────────────────────────
    con.execute("""
        CREATE TABLE suivi_incidents AS
        SELECT
            DATE '2025-01-01'            AS date_incident,
            'test'::VARCHAR              AS type_incident,
            0.0::DOUBLE                  AS cout_fcfa
        WHERE 1=0
    """)

    # ── 9. Table données 2024 pour test bilan annuel ──────────────────────────
    con.execute("""
        CREATE TABLE rapport_mensuel AS
        SELECT
            DATE '2024-01-01' + (i * 15)::INTEGER              AS date,
            (1000 + (i * 23 % 800))::DOUBLE                        AS valeur_kpi,
            CASE WHEN i%3=0 THEN 'Production'
                 WHEN i%3=1 THEN 'Qualite' ELSE 'Securite' END    AS domaine
        FROM range(36) t(i)
    """)

    reg.build_registry(con)
    return con


# ── Définition des cas de test ─────────────────────────────────────────────────

@dataclass
class Case:
    id: str
    description: str
    question: str
    year: int | None
    expected_table: str       # "" = pas de table attendue
    expected_contains: list[str] = field(default_factory=list)
    should_return: bool = True


CASES: list[Case] = [
    # ── Série temporelle : total ───────────────────────────────────────────────
    Case("TC01", "série temporelle — total",
         "production poste 2025", 2025,
         "production_poste", ["quantite_produite_T", "production_poste"]),

    # ── Série temporelle : par mois ───────────────────────────────────────────
    Case("TC02", "par mois avec année",
         "production poste par mois 2025", 2025,
         "production_poste", ["Jan", "production_poste"]),

    # ── Colonne date inhabituellement nommée ──────────────────────────────────
    Case("TC03", "colonne date_intervention",
         "maintenance log 2025", 2025,
         "maintenance_log", ["maintenance_log"]),

    # ── Groupement par catégorie ──────────────────────────────────────────────
    Case("TC04", "groupement par type",
         "maintenance par type 2025", 2025,
         "maintenance_log", ["Preventif", "maintenance_log"]),

    # ── Bonne colonne qty sélectionnée ────────────────────────────────────────
    Case("TC05", "sélection colonne volume vs débit",
         "volume eau 2024", 2024,
         "suivi_eau", ["volume_m3", "suivi_eau"]),

    # ── Référentiel sans date ─────────────────────────────────────────────────
    Case("TC06", "référentiel — count",
         "liste des fournisseurs", None,
         "fournisseurs", ["fournisseurs"]),

    # ── Absences par département ──────────────────────────────────────────────
    Case("TC07", "absences total 2025",
         "absences personnel 2025", 2025,
         "absences_personnel", ["absences_personnel"]),

    Case("TC08", "absences par département",
         "absences par departement 2025", 2025,
         "absences_personnel", ["absences_personnel"]),

    # ── Multiple qty : choisir stock_final ────────────────────────────────────
    Case("TC09", "sélection stock_final vs stock_initial",
         "stock final inventaire 2025", 2025,
         "inventaire_stock", ["stock_final_T", "inventaire_stock"]),

    # ── Nom de table à 3 tokens ───────────────────────────────────────────────
    Case("TC10", "table 3 segments dans le nom",
         "analyse eau usine 2024", 2024,
         "analyse_eau_usine", ["analyse_eau_usine"]),

    # ── Top-N ─────────────────────────────────────────────────────────────────
    Case("TC11", "top-N",
         "top 3 equipements production 2025", 2025,
         "production_poste", ["production_poste"]),

    # ── Bilan annuel (par année) ──────────────────────────────────────────────
    Case("TC12", "par année",
         "production poste par annee", None,
         "production_poste", ["2025", "production_poste"]),

    # ── Table vide ────────────────────────────────────────────────────────────
    # G4 : doit retourner un message explicite "aucune donnée" et non une réponse vide
    Case("TC13", "table vide — message explicite aucune donnée",
         "suivi incidents 2025", 2025,
         "suivi_incidents", ["suivi_incidents", "aucune"]),

    # ── Comptage ─────────────────────────────────────────────────────────────
    Case("TC14", "combien",
         "combien de fournisseurs", None,
         "fournisseurs", ["20", "fournisseurs"]),

    # ── Par trimestre ────────────────────────────────────────────────────────
    Case("TC15", "par trimestre",
         "production poste par trimestre 2025", 2025,
         "production_poste", ["T1", "production_poste"]),

    # ── Pas de faux positif : table gérée ────────────────────────────────────
    Case("TC16", "ANTI — table déjà gérée ne passe pas",
         "tonnage descendu 2025", 2025,
         "", [],
         should_return=False),

    # ── Pas de faux positif : question trop vague ─────────────────────────────
    Case("TC17", "ANTI — question trop vague",
         "quelques données", None,
         "", [],
         should_return=False),

    # ── Par mois sans année ───────────────────────────────────────────────────
    Case("TC18", "par mois sans année — dégradé acceptable",
         "production poste par mois", None,
         "production_poste", ["production_poste"]),

    # ── Heures machine ────────────────────────────────────────────────────────
    Case("TC19", "sélection heures machine",
         "heures machine production poste 2025", 2025,
         "production_poste", ["heures_machine", "production_poste"]),

    # ── Bilan annuel multi-domaine ────────────────────────────────────────────
    Case("TC20", "rapport par domaine",
         "rapport mensuel par domaine 2024", 2024,
         "rapport_mensuel", ["rapport_mensuel"]),
]


# ── Runner ────────────────────────────────────────────────────────────────────

@dataclass
class Result:
    case: Case
    passed: bool
    response: str | None
    detail: str
    score_breakdown: dict[str, bool] = field(default_factory=dict)

    @property
    def score(self) -> float:
        weights = {"table": 0.40, "returned": 0.30, "content": 0.20, "no_fp": 0.10}
        return sum(
            weights[k] * v
            for k, v in self.score_breakdown.items()
            if k in weights
        )


def run_case(con: duckdb.DuckDBPyConnection, case: Case) -> Result:
    """Exécute un cas de test et retourne le résultat détaillé."""
    from src.utils.text import norm as _norm
    from src.engine.generic_handler import GenericHandlerResult as _GHR

    _raw = handle_new_table(con, _norm(case.question), _HANDLED, case.year)
    # handle_new_table() retourne désormais GenericHandlerResult — extraire le texte
    response: str | None = _raw.response if isinstance(_raw, _GHR) else _raw

    breakdown: dict[str, bool] = {}

    if not case.should_return:
        # Cas anti-faux-positif
        no_fp = response is None
        breakdown = {"table": True, "returned": True, "content": True, "no_fp": no_fp}
        passed = no_fp
        detail = "✅ Aucun résultat (attendu)" if no_fp else f"❌ Faux positif : {response[:80] if response else '—'}"
    else:
        # Vérifier que la réponse est retournée
        returned = response is not None
        breakdown["returned"] = returned

        if not returned:
            breakdown.update({"table": False, "content": False, "no_fp": True})
            return Result(case, False, None, "❌ Aucune réponse retournée", breakdown)

        # Vérifier que la bonne table est citée dans la réponse
        table_ok = case.expected_table and case.expected_table in response
        breakdown["table"] = table_ok

        # Vérifier le contenu attendu
        missing = [s for s in case.expected_contains if s not in response]
        content_ok = len(missing) == 0
        breakdown["content"] = content_ok

        # Pas de faux positif (réponse retournée quand attendue = OK)
        breakdown["no_fp"] = True

        passed = returned and table_ok and content_ok
        parts: list[str] = []
        if not table_ok:
            parts.append(f"table attendue '{case.expected_table}' absente de la réponse")
        if not content_ok:
            parts.append(f"contenu manquant : {missing}")
        detail = "✅ OK" if passed else "❌ " + " | ".join(parts)

    return Result(case, passed, response, detail, breakdown)


# ── Rapport ───────────────────────────────────────────────────────────────────

def print_report(results: list[Result]) -> None:
    passed  = sum(1 for r in results if r.passed)
    total   = len(results)
    pct     = passed / total * 100

    # Score pondéré
    weighted = sum(r.score for r in results) / total * 100

    print("\n" + "=" * 68)
    print(f"  AUDIT SmartGenericHandler — {passed}/{total} cas passés")
    print(f"  Score binaire    : {pct:.0f}%")
    print(f"  Score pondéré    : {weighted:.1f}/100")
    grade = "A" if weighted >= 90 else "B" if weighted >= 80 else "C" if weighted >= 70 else "D"
    print(f"  Note             : {grade}")
    print("═" * 68)

    for r in results:
        icon = "✅" if r.passed else "❌"
        score_str = f"{r.score * 100:.0f}%"
        print(f"  {icon} [{r.case.id}] {r.case.description[:42]:<42}  {score_str}")
        if not r.passed:
            print(f"      → {r.detail}")
            if r.response:
                preview = r.response.replace("\n", " ")[:100]
                print(f"      Réponse : {preview}…")

    print("═" * 68)

    # Répartition par dimension
    dims = ["table", "returned", "content", "no_fp"]
    print("\n  Scores par dimension :")
    for dim in dims:
        vals = [r.score_breakdown.get(dim, False) for r in results]
        pct_dim = sum(vals) / len(vals) * 100
        bar = "█" * int(pct_dim // 5)
        print(f"    {dim:<10} {pct_dim:5.1f}%  {bar}")
    print()

    # Failles détectées
    failed = [r for r in results if not r.passed]
    if failed:
        print(f"  Failles à corriger ({len(failed)}) :")
        for r in failed:
            print(f"    [{r.case.id}] {r.case.description} — {r.detail}")
    else:
        print("  Aucune faille détectée — objectif 95 (A) atteint.")
    print()


# ── Tests pytest ─────────────────────────────────────────────────────────────

import pytest


@pytest.fixture(scope="module")
def db():
    return _build_test_db()


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case(db, case: Case):
    result = run_case(db, case)
    assert result.passed, (
        f"[{case.id}] {case.description}\n"
        f"  Question : {case.question}\n"
        f"  Détail   : {result.detail}\n"
        f"  Réponse  : {result.response}"
    )


def test_confidence_threshold():
    """Le seuil de confiance est calibré pour éviter les faux positifs."""
    assert CONFIDENCE_THRESHOLD == 0.35, (
        "Modifier CONFIDENCE_THRESHOLD nécessite de recalibrer les cas anti-FP."
    )


def test_best_candidate_wins():
    """Quand 2 tables matchent, le meilleur score gagne."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE eau_potable AS
        SELECT DATE '2025-01-01' AS date, 100.0::DOUBLE AS volume_m3
        FROM range(5) t(i)
    """)
    con.execute("""
        CREATE TABLE eau_usee AS
        SELECT DATE '2025-01-01' AS date, 50.0::DOUBLE AS volume_m3
        FROM range(5) t(i)
    """)
    reg.build_registry(con)

    from src.utils.text import norm as _norm
    from src.engine.generic_handler import GenericHandlerResult as _GHR
    _raw = handle_new_table(con, _norm("eau potable"), frozenset(), None)
    result = _raw.response if isinstance(_raw, _GHR) else _raw
    assert result is not None
    assert "eau_potable" in result, f"Attendu 'eau_potable', reçu : {result}"


# ── Tests unitaires sur les corrections G1-G6 ────────────────────────────────

def test_g1_like_injection_safe():
    """G1 : une tentative d'injection SQL via LIKE ne crashe pas."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE obs_test AS
        SELECT
            DATE '2025-01-01' AS date,
            'commentaire normal'::VARCHAR AS observation,
            100.0::DOUBLE AS valeur
        FROM range(5) t(i)
    """)
    reg.build_registry(con)
    # Terme malicieux : apostrophe + DROP TABLE
    malicious = "y a-t-il des '; DROP TABLE obs_test; --"
    try:
        from src.engine.generic_handler import GenericHandlerResult as _GHR
        result = handle_new_table(con, malicious, frozenset(), None)
        # Doit ne pas lever d'exception et retourner None, str, ou GenericHandlerResult
        assert result is None or isinstance(result, (str, _GHR)), \
            "Le handler doit retourner str/GenericHandlerResult ou None, pas lever d'exception"
    except Exception as exc:
        raise AssertionError(f"G1 : injection SQL non neutralisée — {exc}") from exc
    # La table doit toujours exister après la requête
    count = con.execute("SELECT COUNT(*) FROM obs_test").fetchone()[0]
    assert count == 5, "G1 : la table obs_test a été modifiée — injection possible"


def test_g3_year_validation():
    """G3 : year hors plage [1900, 2200] est ignoré sans erreur SQL."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE mesures_test AS
        SELECT DATE '2025-06-01' AS date, 42.0::DOUBLE AS mesure
        FROM range(3) t(i)
    """)
    reg.build_registry(con)
    handler = SmartGenericHandler("mesures_test")
    schema  = reg.get_or_build(con, "mesures_test")
    # year invalide (string) — doit retourner une réponse sans lever d'exception
    try:
        result = handler.handle(con, "mesures test", year=99999)
        assert result is not None, "G3 : year invalide a bloqué la réponse"
        # year=99999 ignoré → réponse "toutes périodes"
        assert "toutes" in result or "mesures_test" in result
    except Exception as exc:
        raise AssertionError(f"G3 : year invalide a levé une exception — {exc}") from exc


def test_g5_pipe_escaped_in_list():
    """G5 : les | dans les valeurs sont échappés — le tableau Markdown est valide."""
    from src.engine.generic_handler import _fmt_list

    class _FakeSchema:
        col_info = {"colonne_a": "VARCHAR", "colonne_b": "VARCHAR"}
        def description(self): return "Table test"

    rows = [("valeur avec | pipe", "normal"), ("autre | val | ici", "ok")]
    result = _fmt_list("table_test", rows, _FakeSchema())
    # Aucun | non-échappé ne doit rester dans les données (hors séparateurs de colonnes)
    lines = result.split("\n")
    for line in lines:
        if line.startswith("  ") and "---" not in line and "|" in line:
            # Les séparateurs Markdown attendus : "  cell | cell"
            # Les | dans les cellules doivent être "\\|"
            assert "valeur avec \\| pipe" in result, \
                f"G5 : le | n'est pas échappé dans la ligne : {line!r}"
            break


def test_g6_id_column_excluded():
    """G6 : une colonne 'id' numérique n'est pas choisie comme colonne qty."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE contrats_test AS
        SELECT
            (i + 1)::INTEGER              AS id,
            DATE '2025-01-01' + (i * 10)::INTEGER AS date,
            (5000 + i * 100)::DOUBLE       AS montant_fcfa,
            'fournisseur'::VARCHAR         AS libelle
        FROM range(10) t(i)
    """)
    reg.build_registry(con)
    handler = SmartGenericHandler("contrats_test")
    result  = handler.handle(con, "contrats test 2025", year=2025)
    assert result is not None, "G6 : aucune réponse pour la table contrats_test"
    # La réponse doit porter sur montant_fcfa, pas sur la colonne id
    assert "id" not in result.lower().split("**")[1] if "**" in result else True, \
        f"G6 : la colonne id a été choisie comme qty : {result}"


# ── Mode standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    con     = _build_test_db()
    results = [run_case(con, c) for c in CASES]
    print_report(results)

    # Exit code non-nul si score < 95
    weighted = sum(r.score for r in results) / len(results) * 100
    sys.exit(0 if weighted >= 95 else 1)
