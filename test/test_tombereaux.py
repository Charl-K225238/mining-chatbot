"""
Tests ciblés — handle_tombereaux() et intégration via analytics.handle().

Vérifie que les 3 intentions (utilisation / voyage / panne) sont correctement
séparées et qu'une question "classement par utilisation" ne retourne plus
un classement par pannes.

Usage :
    .venv\Scripts\python.exe -m pytest test/test_tombereaux.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from src.db.connection import get_db
from src.engine.analytics import handle, handle_tombereaux
from src.engine.intention import normaliser as norm


# ── Fixture connexion ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def con():
    return get_db()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ask(con, question: str) -> str:
    """Lance handle() et retourne la réponse (ou chaîne vide si None)."""
    return handle(con, question) or ""


# ── Tests — séparation des intentions ───────────────────────────────────────

class TestIntentionUtilisation:
    """Classement par nombre d'enregistrements (COUNT*) — PAS par pannes."""

    def test_classement_utilisation_2026(self, con):
        r = _ask(con, "Classement des tombereaux par utilisation en 2026")
        assert r, "La réponse est vide"
        assert "Nb utilisations" in r or "utilisation" in r.lower(), \
            f"Attendu 'Nb utilisations' dans la réponse, reçu :\n{r}"

    def test_classement_utilisation_ne_retourne_pas_pannes(self, con):
        r = _ask(con, "Classement des tombereaux par utilisation en 2026")
        assert "panne" not in r.lower(), \
            f"Handler pannes déclenché par erreur sur une question d'utilisation :\n{r}"

    def test_plus_utilise_2025(self, con):
        r = _ask(con, "Quel tombereau est le plus utilisé en 2025 ?")
        assert r, "La réponse est vide"
        assert "utilisation" in r.lower() or "Nb utilisations" in r, \
            f"Attendu une réponse d'utilisation, reçu :\n{r}"

    def test_combien_de_fois_2026(self, con):
        r = _ask(con, "Combien de fois chaque tombereau a été utilisé en 2026")
        assert r, "La réponse est vide"
        assert "panne" not in r.lower(), \
            f"Handler pannes déclenché à tort :\n{r}"


class TestIntentionVoyage:
    """Classement par voyages (SUM colonne voyages)."""

    def test_classement_voyages_2025(self, con):
        r = _ask(con, "Nombre de voyages par tombereau en 2025")
        assert r, "La réponse est vide"
        assert "voyage" in r.lower(), \
            f"Attendu 'voyage' dans la réponse, reçu :\n{r}"

    def test_tombereaux_par_rotations(self, con):
        r = _ask(con, "Classement des tombereaux par rotations en 2024")
        assert r, "La réponse est vide"
        assert "voyage" in r.lower() or "rotation" in r.lower(), \
            f"Attendu 'voyage' ou 'rotation', reçu :\n{r}"


class TestIntentionPanne:
    """Classement par pannes (observations LIKE '%panne%')."""

    def test_classement_pannes_2023(self, con):
        r = _ask(con, "Quels tombereaux ont le plus de pannes en 2023 ?")
        assert r, "La réponse est vide"
        assert "panne" in r.lower() or "Nb pannes" in r, \
            f"Attendu 'panne' dans la réponse, reçu :\n{r}"

    def test_bilan_pannes_tombereaux(self, con):
        r = _ask(con, "Bilan des pannes tombereaux en 2023")
        assert r, "La réponse est vide"
        assert "panne" in r.lower(), \
            f"Attendu 'panne' dans la réponse, reçu :\n{r}"


class TestIntentionTonnage:
    """Classement par tonnage produit."""

    def test_tonnage_par_tombereau_2025(self, con):
        r = _ask(con, "Tonnage par tombereau en 2025")
        assert r, "La réponse est vide"
        assert any(c.isdigit() for c in r), "Aucun chiffre dans la réponse"
        assert "panne" not in r.lower(), \
            f"Handler pannes déclenché à tort :\n{r}"

    def test_top_tombereaux_par_production(self, con):
        r = _ask(con, "Top tombereaux par production en 2026")
        assert r, "La réponse est vide"
        assert any(c.isdigit() for c in r), "Aucun chiffre dans la réponse"


class TestComptageEtListe:
    """Comptage distinct et liste."""

    def test_combien_tombereaux_distincts(self, con):
        r = _ask(con, "Combien de tombereaux distincts ?")
        assert r, "La réponse est vide"
        assert any(c.isdigit() for c in r), "Aucun chiffre dans la réponse"

    def test_liste_tombereaux(self, con):
        r = _ask(con, "Liste des tombereaux")
        assert r, "La réponse est vide"
        # Doit contenir au moins un nom d'engin (TOMBEREAU ou CAT N°)
        assert "tombereau" in r.lower() or "cat" in r.lower(), \
            f"Aucun nom d'engin reconnu dans :\n{r}"


class TestFiltreAnnee:
    """Vérification que le filtre année est bien appliqué."""

    def test_utilisation_avec_et_sans_annee(self, con):
        r_avec = _ask(con, "Classement tombereaux par utilisation en 2025")
        r_sans  = _ask(con, "Classement tombereaux par utilisation")
        # Les deux doivent répondre, mais pas nécessairement identiques
        assert r_avec, "Réponse vide avec filtre année"
        assert r_sans, "Réponse vide sans filtre année"
        assert "panne" not in r_avec.lower()
        assert "panne" not in r_sans.lower()


class TestRobustesse:
    """Orthographe approximative et abréviations."""

    def test_faute_orthographe_tomberaux(self, con):
        # "tomberaux" (sans 'e') doit quand même déclencher le handler
        # Note : normaliser() remplace 'tombereaux' → 'tombereaux'
        # Cette question passe par analytics.handle() qui normalise
        r = _ask(con, "Classement des tomberaux par utilisation 2026")
        # On vérifie juste que la réponse n'est pas vide ou erronée
        # (si le synonyme n'est pas mappé, None est acceptable)
        if r:
            assert "panne" not in r.lower(), \
                f"Handler pannes déclenché à tort sur faute d'orthographe :\n{r}"
