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

# ── Démarrage rapide ───────────────────────────────────────────────────────────
with st.expander("🚀 Démarrage rapide — Ollama et modèles (si pas encore configuré)", expanded=False):
    st.markdown("""
**1. Installer Ollama** — [ollama.com](https://ollama.com) → Download for Windows → installer

**2. Choisir son modèle selon sa RAM**

| RAM | Modèle | Commande |
|-----|--------|----------|
| < 4 Go | `phi3:mini` | `ollama pull phi3:mini` |
| 4–8 Go | `qwen2.5:3b` *(défaut)* | `ollama pull qwen2.5:3b` |
| 8–16 Go | `qwen2.5:7b` | `ollama pull qwen2.5:7b` |
| > 16 Go | `qwen2.5:14b` | `ollama pull qwen2.5:14b` |

**3. Coller la commande dans PowerShell** (Windows → tapez `powershell` → Entrée)

**4. C'est prêt** — Miny démarre Ollama automatiquement à chaque question LLM.

> Avec 8 Go : téléchargez `qwen2.5:3b` + `phi3:mini`. Miny bascule automatiquement sur le plus léger si nécessaire.

👉 Guide complet et téléchargement depuis l'app : **⚙️ Paramètres → Guide de démarrage**
""")

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
with st.expander("📖 Capacités, 4 modes de réponse et types de tonnage", expanded=False):
    st.markdown("""
**Les 4 modes de réponse — Miny choisit automatiquement**

| Mode | Badge | Délai typique | Utilisé pour |
|------|-------|--------------|-------------|
| ⚡ Analytique | vert | < 1 s | Tonnage, pannes, heures machine, objectifs, carburant, PGES |
| 🔢 Calcul | bleu | 10–40 s | Arithmétique, pourcentages, CAGR, ROI, conversions d'unités |
| 🏭 Expertise | orange | 15–60 s | Normes ISO, référentiels, bonnes pratiques, réglementation minière |
| 💬 Général | violet | 8–30 s | Salutations, dates, définitions, culture générale |
| 🤖 LLM/Documents | bleu | 15–60 s | Recherche dans PDF, DOCX, TXT uploadés |

> **Délais variables** selon la RAM disponible et le modèle choisi. Avec `phi3:mini` (< 4 Go) : divisez les délais LLM par 2.

> Les modes 🔢 🏭 💬 🤖 nécessitent **Ollama** en local. Sur Streamlit Cloud, seul ⚡ Analytique fonctionne.
""")

    st.divider()
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
- **Calculs** : CAGR, ROI, pourcentages, arithmétique, conversions
- **Expertise** : normes ISO, référentiels, bonnes pratiques minières
- **Documents uploadés** : recherche dans PDF, DOCX, TXT

**Limites ⚠️**
- Données uniquement importées — pas d'accès Internet
- LLM requis pour tous les modes sauf ⚡ Analytique
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

# ── Recherche documentaire ─────────────────────────────────────────────────────
with st.expander("📄 Recherche dans vos documents uploadés", expanded=False):
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("""
**Formats acceptés :**
- 📄 **PDF** — rapports d'inspection, audits *(PDF textuel, non scanné)*
- 📝 **DOCX** — rapports Word
- 🗒️ **TXT** — textes bruts, exports

**Comment uploader :**
1. Page **⚙️ Paramètres** → section *Charger un fichier*
2. Sélectionnez votre fichier
3. Cliquez **⬆️ Importer et traiter**

**Questions types :**
- *"Quel organisme a réalisé l'inspection ?"*
- *"Quelles sont les non-conformités majeures ?"*
- *"Délais de levée des non-conformités ?"*
- *"Prioriser les actions correctives urgentes"*
""")
    with col_d2:
        st.markdown("""
**Points importants ⚠️**
- Les réponses sur documents passent par **Ollama** (5–30 s)
- Les PDFs **scannés** (images) ne sont **pas lisibles**
- Si Miny répond "je n'ai pas trouvé" → vérifiez le fichier et réindexez

**Différence données / documents :**

| | Données Excel | Documents PDF/DOCX |
|--|--|--|
| Moteur | ⚡ Analytique | 🤖 Ollama |
| Délai | < 1 s | 5–30 s |
| Type | Chiffres, tableaux | Texte libre |
""")

# ── Exemples de questions par domaine ─────────────────────────────────────────
with st.expander("💬 Exemples de questions par domaine", expanded=False):
    st.caption("Copiez-collez ces questions dans l'**Assistant**.")

    EXEMPLES: dict[str, list[str]] = {
        "🔢 Calcul & Expertise": [
            "Calculer le CAGR si le tonnage passe de 1200 à 1850 en 3 ans",
            "15% de 3500",
            "Convertir 15 km/h en m/s",
            "Quels référentiels qualité pour une mine de bauxite ?",
            "Quelles normes ISO s'appliquent à une exploitation minière ?",
            "Quelles meilleures pratiques HSE pour une mine en Afrique de l'Ouest ?",
        ],
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
        "📄 Documents": [
            "Quel organisme a réalisé l'inspection ?",
            "Quelles sont les non-conformités majeures ?",
            "Délais de levée des non-conformités",
            "Quelles actions correctives prioriser en urgence ?",
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
