"""
Miny — 📖 Documentation
Guides d'utilisation, capacités, exemples de questions.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from core.data_loader import load_css

st.set_page_config(
    page_title="📖 Documentation — Miny",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

with st.sidebar:
    st.markdown("## ⛏ Miny")
    st.caption("Assistant BI · Mine de bauxite R2M CI")

st.markdown("## 📖 Documentation")


def _try_in_assistant(q: str) -> None:
    """Pré-remplit la question dans l'Assistant et bascule vers cette page."""
    st.session_state["pending_question"] = q
    st.switch_page("pages/1_Assistant.py")

# ── Questions de suivi ─────────────────────────────────────────────────────────
with st.expander("🔄 Questions de suivi — comment ça marche ?", expanded=False):
    st.markdown("""
**Principe**

Miny mémorise votre dernière question. Si vous tapez une réponse courte après
(période, type ou granularité), Miny la combine automatiquement avec la question précédente
pour affiner la réponse — sans avoir à tout retaper.
""")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Exemples de chaînes**

| 1ʳᵉ question | Suivi | Résultat |
|---|---|---|
| `Bilan des pannes` | `en 2023` | Bilan 2023 |
| `Bilan des pannes` | `de direction` | Pannes direction |
| `Bilan des pannes en 2023` | `de direction` | Pannes direction 2023 |
| `Tonnage descendu` | `en 2026` | Tonnage 2026 |
| `Tonnage descendu` | `par mois` | Tonnage mensuel |
| `Top 5 engins` | `en 2025` | Top 5 pour 2025 |
| `Carburant` | `par engin en 2024` | Conso. par engin |
| `Actions PGES` | `non réalisées` | Actions en retard |
""")
    with col2:
        st.markdown("""
**Ce qui est reconnu comme suivi**

- **Période** : `en 2026`, `en avril`, `janvier 2025`
- **Granularité** : `par mois`, `par semaine`, `par trimestre`
- **Type** : `de direction`, `de pneu`, `excavation`
- **Combiné** : `de direction en 2023`, `par mois en 2026`

**Conditions** : le suivi doit être court (≤ 60 car.).

**Pas reconnu comme suivi :**
- `Tonnage par mois en 2026 ?` → trop complet, traité directement
- `Comparer 2024 et 2025` → question indépendante
""")
    st.info(
        "**Astuce** — si Miny ne reconnaît pas votre suivi, reformulez la question "
        "complète : *« Top 5 engins pour le mois de janvier 2026 »*",
        icon="💡",
    )

# ── Capacités & limites ────────────────────────────────────────────────────────
with st.expander("📖 Capacités et types de tonnage", expanded=False):
    st.markdown("""
**Comment Miny répond**

Miny analyse votre question en langage naturel et interroge directement les données
chargées — les réponses sont instantanées (< 1 s).
""")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
**Ce que Miny sait faire ✅**
- **Tonnage** : descendu, excavé, transporté, arrivé port, navire
- **Pannes** : bilan tombereaux par catégorie ; pannes de la trencher (TRS N°296 par défaut)
- **Heures machine** : disponibilité engins, shifts/vacations
- **Objectifs & taux** : prévu vs réalisé, taux d'accomplissement
- **Carburant** : par mois, par engin, approvisionnement citerne
- **PGES & HSE** : actions, statuts, responsables, domaines

**Limites ⚠️**
- Données uniquement importées — pas d'accès Internet
- PDFs scannés (images) non pris en charge
""")
    with col_b:
        st.markdown("""
**Les 5 types de tonnage ⚖️**

| Mot-clé | Type | Source |
|---------|------|--------|
| *(aucun)* ou `descendu` | Tonnage descendu | `descente_minerai` |
| `excavé` / `excavation` | Tonnage excavé | `excavation` |
| `transporté` / `camion` | Chargé à la mine | `transport_minerai_paa` |
| `arrivé port` / `PAA` | Réceptionné au port | `transport_minerai_paa` |
| `navire` | Chargé sur navire | `productivite_loading` |
""")

# ── Exemples de questions par domaine ─────────────────────────────────────────
with st.expander("💬 Exemples de questions par domaine", expanded=False):
    st.caption("Copiez-collez ces questions dans l'**Assistant**.")

    EXEMPLES: dict[str, list[str]] = {
        "📦 Tonnage": [
            "Tonnage descendu par mois en 2026",
            "Tonnage par semaine en 2026",
            "Tonnage S1-S6 2026",
            "Tonnage par trimestre en 2025",
            "Tonnage excavation 2025",
            "Comparer 2024 et 2025",
        ],
        "⚠️ Pannes": [
            "Bilan des pannes en 2023",
            "Combien de pannes de direction en 2023 ?",
            "Quels tombereaux ont le plus de pannes ?",
            "Pannes de pneu en 2023",
            "Pannes de la trencher TRS 296",
            "Bilan des pannes trencher",
        ],
        "⏱ Heures machine": [
            "Heures machine en 2025",
            "Heures machine par mois en 2025",
            "Heures machine de la trencher en 2025",
            "Taux de disponibilité des engins en 2025",
        ],
        "🛢️ Carburant": [
            "Carburant consommé en 2024",
            "Carburant par mois en 2024",
            "Carburant par engin en 2024",
            "Carburant par engin en 2024 tombereau",
            "Approvisionnement citerne en 2024",
        ],
        "📋 PGES & HSE": [
            "Actions PGES",
            "Obligations non réalisées",
            "Actions en cours",
            "Actions gestion des déchets",
            "Action n°14",
        ],
        "📊 Objectifs": [
            "Taux accomplissement 2025",
            "Objectifs vs réalisé 2025",
            "Objectifs excavation 2025",
        ],
    }

    ex_cols = st.columns(2)
    for ci, (cat, questions) in enumerate(EXEMPLES.items()):
        with ex_cols[ci % 2]:
            st.markdown(f"**{cat}**")
            for qi, q in enumerate(questions):
                _qc1, _qc2 = st.columns([5, 1])
                _qc1.markdown(f"`{q}`")
                _qc2.button(
                    "→", key=f"try_{ci}_{qi}",
                    on_click=_try_in_assistant, args=(q,),
                    help="Essayer dans l'Assistant",
                    use_container_width=True,
                )

# ── Abréviations ───────────────────────────────────────────────────────────────
with st.expander("🔤 Abréviations reconnues", expanded=False):
    st.markdown("""
| Abréviation | Signification |
|-------------|---------------|
| `BH-`, `CAT N°` | Références tombereaux (ex: BH-5, CAT N°3) |
| `TRS N°296` | Trencher (référence par défaut) |
| `PE-` | Pelle excavatrice |
| `SP-` | Scrapers |
| `T1`…`T4` | Trimestres 1 à 4 |
| `Q1`…`Q4` | Équivalents anglais des trimestres |
| `S1`, `S2` | Semestres 1 et 2 |
| `S3`…`S53` | Semaines ISO (S17 = semaine 17) |
| `S1-S6` | Plage de semaines (semaines 1 à 6) |
| `PGES` | Plan de Gestion Environnementale et Sociale |
| `ANDE` | Agence Nationale de l'Environnement |
| `HSE` | Hygiène, Sécurité, Environnement |
| `NC` | Non-conformité (rapport d'inspection) |
| `HM` | Heures Moteur / Heures machine (shifts_horaires) |
| `PAA` | Port Autonome d'Abidjan |
""")

# ── Conseils de formulation ────────────────────────────────────────────────────
with st.expander("✍️ Conseils de formulation", expanded=False):
    from src.engine.clarification import CONSIGNES
    st.markdown("Respectez ces conseils pour obtenir des réponses précises :")
    for tip in CONSIGNES:
        st.markdown(f"- {tip}")
    st.info(
        "**Format recommandé :** `[Sujet] + [Période] + [Détail]`\n\n"
        "Ex : *Tonnage descendu par mois en 2026*",
        icon="✍️",
    )
