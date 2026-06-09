"""
Miny — ⚙️ Paramètres
Guide de démarrage, upload, configuration Ollama, paramètres avancés.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from core.data_loader import get_db, get_index, load_css
from core.ollama_client import (
    is_available, active_model_name,
    lister_modeles_disponibles, assurer_modele_disponible,
    ollama_est_disponible, trouver_ollama_exe, is_remote_ollama,
    IS_WINDOWS, IS_STREAMLIT_CLOUD,
)
from src.db.connection import close as close_db
from src.engine.query_router import rebuild_index
from src.engine.clarification import CONSIGNES
from config.settings import (
    NUM_CTX_DEFAULT, NUM_CTX_MAX, TEMPERATURE_DEFAULT,
    RAM_LIMITE_GO, PRIMARY_MODEL, FALLBACK_MODEL,
)

st.set_page_config(
    page_title="⚙️ Paramètres — Miny",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

with st.sidebar:
    st.markdown("## ⛏ Miny")
    st.caption("Assistant BI · Mine de bauxite R2M CI")

st.markdown("## ⚙️ Paramètres")

# ── Redirection depuis l'Assistant (flag de session) ──────────────────────────
_nav_highlight = st.session_state.pop("params_highlight", None)
if _nav_highlight == "install":
    if IS_STREAMLIT_CLOUD:
        st.info(
            "**Ollama n'est pas accessible depuis ce serveur cloud.** "
            "Suivez le guide ci-dessous pour exposer votre Ollama local et configurer OLLAMA_HOST.",
            icon="☁️",
        )
    elif IS_WINDOWS:
        st.info(
            "**Ollama n'est pas encore installé.** "
            "Le guide ci-dessous vous accompagne en 4 étapes (5 min, gratuit).",
            icon="🚀",
        )
    else:
        st.info(
            "**Ollama n'est pas installé ou n'est pas démarré.** "
            "Suivez le guide ci-dessous pour l'installer et le démarrer.",
            icon="🐧",
        )
elif _nav_highlight == "model":
    st.info(
        "**Aucun modèle téléchargé.** "
        "Descendez jusqu'à **Modèle LLM actif** pour en télécharger un en un clic.",
        icon="⬇️",
    )
elif _nav_highlight == "check":
    st.info(
        "**Ollama ne répond pas.** "
        "Cliquez sur **Vérifier Ollama** dans la section ci-dessous.",
        icon="🔍",
    )

# ── Statut Ollama (utilisé dans tout ce fichier) ───────────────────────────────
_disponible  = ollama_est_disponible()
_exe         = trouver_ollama_exe()
_modeles     = lister_modeles_disponibles() if _disponible else []
_model_actif = active_model_name() if _modeles else "—"
_ollama_pret = _disponible and bool(_modeles)

# ── Guide de démarrage ─────────────────────────────────────────────────────────
with st.expander(
    "🚀 Démarrage — Configurer Ollama",
    expanded=(not _ollama_pret or _nav_highlight == "install"),
):
    st.info(
        "**⚡ Mode Analytique** fonctionne sans Ollama — réponses instantanées depuis DuckDB. "
        "Les modes 🔢 Calcul · 🏭 Expertise · 💬 Général · 🤖 Documents nécessitent Ollama.",
        icon="💡",
    )
    st.markdown("---")

    if IS_STREAMLIT_CLOUD:
        # ── Guide Streamlit Cloud ──────────────────────────────────────────────
        st.markdown("### 🌐 Guide — Connexion depuis Streamlit Cloud")
        st.info(
            "Miny tourne sur un serveur Streamlit qui n'a pas accès à votre PC. "
            "Pour activer les modes LLM, vous devez :\n\n"
            "**1.** Faire tourner Ollama sur votre PC *(gratuit)*\n\n"
            "**2.** Créer un tunnel public vers votre PC *(ngrok, gratuit)*\n\n"
            "**3.** Donner l'URL du tunnel à Miny via les Secrets Streamlit",
            icon="☁️",
        )

        st.markdown("---")
        st.markdown("#### Étape 1 — Installer Ollama sur votre PC")
        _e1a, _e1b = st.columns(2)
        with _e1a:
            st.markdown("**Windows**")
            st.markdown(
                "**1.** Téléchargez l'installateur → **[ollama.com](https://ollama.com)**\n\n"
                "**2.** Lancez-le, suivez les étapes (2 min)\n\n"
                "**3.** Ollama démarre — icône dans la barre des tâches"
            )
        with _e1b:
            st.markdown("**Mac / Linux**")
            st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")
        st.markdown("Puis téléchargez le modèle recommandé *(dans un terminal)* :")
        st.code("ollama pull qwen2.5:3b", language="bash")
        st.caption("Durée : 5–15 min selon votre connexion. Modèle léger (~2 Go), fonctionne avec 4 Go de RAM.")

        st.markdown("---")
        st.markdown("#### Étape 2 — Créer un tunnel public avec ngrok")
        st.markdown(
            "ngrok crée une URL publique qui redirige vers votre Ollama local. "
            "C'est gratuit et prend 3 minutes."
        )
        _ng1, _ng2 = st.columns([3, 2])
        with _ng1:
            st.markdown(
                "**1.** Créez un compte gratuit → **[dashboard.ngrok.com](https://dashboard.ngrok.com)**\n\n"
                "**2.** Dans le dashboard, copiez votre **Authtoken** (onglet *Your Authtoken*)\n\n"
                "**3.** Téléchargez ngrok → **[ngrok.com/download](https://ngrok.com/download)** "
                "*(installateur Windows ou archive Linux/Mac)*\n\n"
                "**4.** Ouvrez un terminal *(PowerShell sur Windows)* et authentifiez-le :"
            )
            st.code("ngrok config add-authtoken VOTRE_TOKEN_ICI", language="bash")
            st.markdown("**5.** Lancez le tunnel Ollama :")
            st.code("ngrok http 11434 --host-header=localhost", language="bash")
            st.markdown(
                "**6.** Dans la fenêtre ngrok qui s'ouvre, copiez la ligne **Forwarding** :\n\n"
                "```\nForwarding  https://abc123.ngrok-free.app → http://localhost:11434\n```\n\n"
                "Copiez uniquement la partie `https://abc123.ngrok-free.app`"
            )
        with _ng2:
            st.info(
                "**⚠️ Laissez la fenêtre ngrok ouverte** tant que vous utilisez Miny. "
                "Fermer ngrok coupe la connexion.\n\n"
                "**Alternatives à ngrok :**\n"
                "- Cloudflare Tunnel *(plus stable, gratuit)*\n"
                "- Tailscale Funnel\n"
                "- VPS avec port 11434 ouvert",
                icon="🔗",
            )
            st.info(
                "**L'URL change à chaque relance ngrok** *(version gratuite)*.\n\n"
                "Pour une URL fixe, souscrivez au plan payant ngrok "
                "ou utilisez Cloudflare Tunnel.",
                icon="ℹ️",
            )

        st.markdown("---")
        st.markdown("#### Étape 3 — Configurer OLLAMA_HOST dans Streamlit Cloud")
        st.markdown(
            "**1.** Allez sur **[share.streamlit.io](https://share.streamlit.io)**\n\n"
            "**2.** Votre app → menu **⋯** → **Settings** → **Secrets**\n\n"
            "**3.** Ajoutez la ligne suivante en remplaçant l'URL par celle de ngrok :"
        )
        st.code('OLLAMA_HOST = "https://abc123.ngrok-free.app"', language="toml")
        st.markdown(
            "**4.** Cliquez **Save** — l'app redémarre automatiquement (30 s)\n\n"
            "**5.** Revenez sur cette page et cliquez **🔍 Vérifier Ollama** ci-dessous"
        )
        st.success(
            "Une fois configuré, Miny se connecte à votre Ollama local via le tunnel "
            "— les 4 modes LLM deviennent disponibles.",
            icon="✅",
        )
        st.markdown("---")

    elif IS_WINDOWS:
        # ── Guide Windows local ────────────────────────────────────────────────
        st.markdown("### 🪟 Guide — Installation locale Windows")
        st.markdown(
            "Ollama est un moteur IA gratuit qui tourne **entièrement sur votre PC** "
            "— aucun abonnement, aucune donnée envoyée sur Internet."
        )
        st.markdown("---")

        st.markdown("#### Étape 1 — Installer Ollama (2 min)")
        c_dl, c_info = st.columns([3, 2])
        with c_dl:
            st.markdown(
                "**1.** Téléchargez l'installateur → **[ollama.com](https://ollama.com)**  \n"
                "*(bouton Download for Windows en haut de la page)*\n\n"
                "**2.** Ouvrez le fichier téléchargé et suivez les étapes — "
                "cliquez simplement *Suivant / Installer*\n\n"
                "**3.** Ollama démarre automatiquement — "
                "une petite icône 🦙 apparaît dans la barre des tâches (en bas à droite)"
            )
        with c_info:
            st.info(
                "🔒 **Vos données ne quittent jamais votre PC.**\n\n"
                "Après l'installation, **rechargez cette page** (touche F5) "
                "puis passez à l'étape 2.",
                icon="🔒",
            )
        st.markdown("---")

        st.markdown("#### Étape 2 — Télécharger un modèle IA")
        st.markdown(
            "Vérifiez d'abord votre RAM disponible : "
            "**Ctrl+Alt+Supr** → *Gestionnaire des tâches* → onglet *Performances* → *Mémoire*"
        )
        st.markdown("""
| RAM disponible | Modèle recommandé | Taille à télécharger |
|---|---|---|
| **Moins de 4 Go** | `phi3:mini` | ~2,2 Go |
| **4 à 8 Go** | `qwen2.5:3b` *(recommandé)* | ~2,0 Go |
| **8 à 16 Go** | `qwen2.5:7b` | ~4,7 Go |
| **Plus de 16 Go** | `qwen2.5:14b` | ~8,7 Go |
""")
        st.markdown("**Cliquez sur le bouton correspondant à votre RAM pour télécharger le modèle :**")
        _bc1, _bc2, _bc3, _bc4 = st.columns(4)
        for _col, _model, _ram in [
            (_bc1, "phi3:mini",    "< 4 Go"),
            (_bc2, "qwen2.5:3b",  "4–8 Go"),
            (_bc3, "qwen2.5:7b",  "8–16 Go"),
            (_bc4, "qwen2.5:14b", "> 16 Go"),
        ]:
            with _col:
                st.caption(_ram)
                if st.button(f"⬇️ {_model}", key=f"guide_dl_{_model}",
                             use_container_width=True):
                    if not _disponible:
                        st.warning(
                            "Ollama n'est pas encore détecté.\n\n"
                            "Si vous venez de l'installer : **rechargez cette page (F5)** "
                            "puis cliquez à nouveau sur ce bouton."
                        )
                    else:
                        assurer_modele_disponible(_model, placeholder=st.empty())
        st.markdown("---")

        st.success(
            "✅ **C'est tout !** Miny détecte et démarre Ollama automatiquement. "
            "Après le téléchargement du modèle, revenez dans l'Assistant et posez votre première question.",
            icon="✅",
        )
        st.markdown("---")

    else:
        # ── Guide Linux / Mac local ────────────────────────────────────────────
        st.markdown("### 🐧 Guide — Installation locale Linux / Mac")
        st.markdown(
            "Ollama est un moteur IA gratuit qui tourne **entièrement sur votre machine** "
            "— aucun abonnement, aucune donnée envoyée sur Internet."
        )
        st.markdown("---")

        st.markdown("#### Étape 1 — Installer Ollama")
        st.markdown("Ouvrez un terminal et collez la commande suivante :")
        st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")
        st.info(
            "L'installation place Ollama dans `/usr/local/bin/ollama` et le démarre "
            "**automatiquement comme service système** — vous n'avez pas besoin de le lancer manuellement.\n\n"
            "**Mac** : si curl n'est pas disponible, téléchargez l'installateur → **[ollama.com](https://ollama.com)**",
            icon="ℹ️",
        )

        st.markdown("#### Étape 2 — Télécharger un modèle IA")
        st.markdown("""
| RAM disponible | Modèle recommandé | Commande |
|---|---|---|
| **Moins de 4 Go** | `phi3:mini` | `ollama pull phi3:mini` |
| **4 à 8 Go** | `qwen2.5:3b` *(recommandé)* | `ollama pull qwen2.5:3b` |
| **8 à 16 Go** | `qwen2.5:7b` | `ollama pull qwen2.5:7b` |
| **Plus de 16 Go** | `qwen2.5:14b` | `ollama pull qwen2.5:14b` |
""")
        st.markdown("**Cliquez sur le bouton correspondant à votre RAM :**")
        _bc1, _bc2, _bc3, _bc4 = st.columns(4)
        for _col, _model, _ram in [
            (_bc1, "phi3:mini",    "< 4 Go"),
            (_bc2, "qwen2.5:3b",  "4–8 Go"),
            (_bc3, "qwen2.5:7b",  "8–16 Go"),
            (_bc4, "qwen2.5:14b", "> 16 Go"),
        ]:
            with _col:
                st.caption(_ram)
                if st.button(f"⬇️ {_model}", key=f"guide_dl_{_model}",
                             use_container_width=True):
                    if not _disponible:
                        st.warning(
                            "Ollama n'est pas encore détecté.\n\n"
                            "Si vous venez de l'installer : **rechargez cette page** "
                            "puis cliquez à nouveau sur ce bouton.\n\n"
                            "Si Ollama est installé mais inactif, lancez : `ollama serve`"
                        )
                    else:
                        assurer_modele_disponible(_model, placeholder=st.empty())
        st.markdown("---")

        st.success(
            "Miny détecte Ollama automatiquement au démarrage. "
            "Si Ollama n'est pas lancé, Miny tentera de le démarrer via `ollama serve`.",
            icon="✅",
        )
        st.markdown("---")

    # Modèles en ligne (futur)
    with st.expander("📡 Plus tard — Modèles en ligne plus performants (optionnel)", expanded=False):
        st.markdown("""
Les modèles locaux sont gratuits et suffisants pour l'analyse quotidienne.
Si vous souhaitez des réponses encore plus riches, voici les options cloud :

| Service | Coût | Avantage |
|---------|------|----------|
| **Groq** | Gratuit (limité) | Ultra-rapide, modèles open-source |
| **OpenAI GPT-4o** | ~0,01 $/question | Très performant |
| **Anthropic Claude** | ~0,01 $/question | Excellent pour l'analyse |
| **Ollama.com Cloud** | Variable | Vos modèles hébergés |

Ces options nécessitent une modification de `core/ollama_client.py` pour pointer
vers l'API choisie. Contactez votre équipe technique pour la mise en place.
""")

st.divider()

# ── Upload fichiers ────────────────────────────────────────────────────────────
st.markdown("### Charger un fichier")
st.markdown(
    '<div class="upload-hint">'
    "📁 <b>Formats acceptés :</b> Excel (.xlsx), PDF, Word (.docx), texte (.txt)<br>"
    "⚙️ Les fichiers <b>Excel</b> sont automatiquement convertis pour l'analyse SQL.<br>"
    "📄 Les <b>PDF et documents</b> sont indexés pour la recherche documentaire.<br>"
    "<small>⚠️ <code>.csv</code> : préférez .xlsx · <code>.doc</code> : convertissez en .docx</small>"
    "</div>",
    unsafe_allow_html=True,
)
st.info(
    "💡 Pour **remplacer** un fichier existant, allez dans **📊 Données** "
    "et cliquez sur 🔄 Remplacer.",
    icon="ℹ️",
)

uploaded = st.file_uploader(
    "Fichier",
    type=["xlsx", "xls", "csv", "pdf", "docx", "doc", "txt"],
    label_visibility="collapsed",
    key="file_uploader_params",
)
if uploaded:
    _ext = uploaded.name.rsplit(".", 1)[-1].lower()
    if _ext == "doc":
        st.warning("⚠️ `.doc` sauvegardé mais **non indexé**. Convertissez en `.docx`.")
    elif _ext == "csv":
        st.info("ℹ️ CSV sauvegardé — pour l'analyser, importez en `.xlsx`.")
    st.write(f"📄 **{uploaded.name}** ({uploaded.size // 1024 or 1} Ko)")
    if st.button("⬆️ Importer et traiter", key="btn_import_params", use_container_width=True):
        from src.ingest.upload_handler import (
            save_file, is_data_file, is_known_file, tables_for_file,
        )
        try:
            save_file(uploaded.getvalue(), uploaded.name)

            if is_data_file(uploaded.name):
                _subset = tables_for_file(uploaded.name)
                if _subset is None:
                    st.warning(
                        f"**{uploaded.name}** n'est pas référencé dans la configuration — "
                        "toutes les tables seront re-traitées (opération plus longue). "
                        "Pour un traitement ciblé, nommez le fichier exactement comme "
                        "dans `src/ingest/config.py`.",
                        icon="⚠️",
                    )
                _label  = ", ".join(_subset.keys()) if _subset else "toutes les tables"
                with st.spinner(f"Mise à jour de {_label}…"):
                    from src.ingest.pipeline import run as run_pipeline
                    run_pipeline(_subset)
                    close_db()
                    st.cache_resource.clear()
                    st.cache_data.clear()
                    rebuild_index()
                st.success(f"Données ({_label}) et index mis à jour !")
            else:
                with st.spinner("Mise à jour de l'index documentaire…"):
                    rebuild_index()
                # Afficher le type de document détecté
                try:
                    from src.rag.doc_manifest import get as _get_meta
                    _meta = _get_meta(uploaded.name)
                    if _meta:
                        st.success(
                            f"**{uploaded.name}** indexé — "
                            f"Type détecté : **{_meta['type_label']}**"
                        )
                    else:
                        st.success(f"{uploaded.name} indexé !")
                except Exception:
                    st.success(f"✅ {uploaded.name} indexé !")

        except Exception as _e:
            st.error(f"Erreur lors de l'import : {_e}")

st.divider()

# ── Documents indexés (manifeste) ─────────────────────────────────────────────
try:
    from src.rag.doc_manifest import get_all as _get_all_docs, type_label as _type_label
    _all_docs = _get_all_docs()
    if _all_docs:
        with st.expander(f"📄 Documents indexés ({len(_all_docs)})", expanded=False):
            for _fname, _meta in _all_docs.items():
                _c1, _c2, _c3 = st.columns([4, 3, 2])
                _c1.markdown(f"`{_fname}`")
                _c2.caption(_meta.get("type_label", "—"))
                _c3.caption(_meta.get("uploaded_at", "—")[:10])
except Exception:
    pass

st.divider()

# ── Modèle Ollama ──────────────────────────────────────────────────────────────
if _nav_highlight in ("model", "check"):
    st.markdown('<div id="section-modele"></div>', unsafe_allow_html=True)
    st.markdown(
        """<script>
        setTimeout(function(){
            var el = document.getElementById('section-modele');
            if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
        }, 300);
        </script>""",
        unsafe_allow_html=True,
    )
st.markdown("### Modèle LLM actif")

col_m1, col_m2 = st.columns(2)
with col_m1:
    if _ollama_pret:
        st.success(f"**{_model_actif}** — prêt", icon="🤖")
    elif _disponible and not _modeles:
        st.warning(
            "Ollama accessible mais **aucun modèle disponible**.\n\n"
            "Téléchargez-en un via le **Guide de démarrage** ci-dessus.",
            icon="🤖",
        )
    elif _exe:
        st.info(
            "Ollama installé — démarre automatiquement à la prochaine question LLM.",
            icon="🤖",
        )
    elif IS_STREAMLIT_CLOUD:
        st.error(
            "Ollama **non accessible** depuis le serveur cloud. "
            "Configurez **OLLAMA_HOST** dans les Secrets Streamlit pour activer les modes LLM. "
            "Seul ⚡ Analytique fonctionne actuellement.",
            icon="🤖",
        )
    else:
        st.error(
            "Ollama **non installé ou non démarré**. "
            "Seul ⚡ Analytique fonctionne. "
            "Suivez le **Guide de démarrage** ci-dessus.",
            icon="🤖",
        )

    if st.button("🔍 Vérifier Ollama", use_container_width=True):
        with st.spinner("Test en cours…"):
            from core.ollama_client import assurer_ollama_disponible
            _ok = assurer_ollama_disponible()
        if _ok:
            st.success(f"Ollama disponible — modèle : **{active_model_name()}**", icon="🤖")
        else:
            st.warning(
                "Ollama n'a pas répondu.\n\n"
                "_⚡ Analytique fonctionne sans Ollama. "
                "Modes 🔢 🏭 💬 🤖 nécessitent Ollama._"
            )

    if _modeles:
        st.selectbox("Modèles installés", options=_modeles, index=0, key="selected_model")
    else:
        st.caption("Aucun modèle installé — voir le Guide de démarrage.")

    st.markdown("**Télécharger rapidement :**")
    _dl1, _dl2 = st.columns(2)
    with _dl1:
        if st.button(f"⬇️ {PRIMARY_MODEL}", use_container_width=True, key="dl_primary"):
            if not _disponible:
                st.error("Démarrez Ollama d'abord.")
            else:
                assurer_modele_disponible(PRIMARY_MODEL, placeholder=st.empty())
    with _dl2:
        if st.button(f"⬇️ {FALLBACK_MODEL}", use_container_width=True, key="dl_fallback"):
            if not _disponible:
                st.error("Démarrez Ollama d'abord.")
            else:
                assurer_modele_disponible(FALLBACK_MODEL, placeholder=st.empty())

with col_m2:
    st.markdown("""
**Routes automatiques :**

| Mode | Badge | Requiert |
|------|-------|---------|
| ⚡ Analytique | vert | Rien (DuckDB) |
| 🔢 Calcul | bleu | Ollama |
| 🏭 Expertise | orange | Ollama |
| 💬 Général | violet | Ollama |
| 🤖 Documents | bleu | Ollama |

_Miny choisit automatiquement le bon mode selon votre question._
""")

st.divider()

# ── Paramètres avancés ─────────────────────────────────────────────────────────
with st.expander("🔧 Paramètres avancés", expanded=False):
    st.markdown("""
**Réglages pré-configurés pour 8 Go de RAM** — modifiez uniquement si nécessaire.

| Votre RAM | Mémoire de conversation | Modèle conseillé |
|-----------|------------------------|-----------------|
| < 4 Go | 512–1024 | `phi3:mini` |
| 4–8 Go | 1024–2048 | `qwen2.5:3b` |
| **8 Go (défaut)** | **2048** | `qwen2.5:3b` |
| > 16 Go | 3072–4096 | `qwen2.5:7b` ou `qwen2.5:14b` |
""")

    num_ctx = st.slider(
        "Mémoire de conversation (tokens)",
        min_value=512, max_value=NUM_CTX_MAX,
        value=st.session_state.get("adv_num_ctx", NUM_CTX_DEFAULT),
        step=256,
        key="adv_num_ctx",
        help=(
            "Défaut : 2048 (8 Go RAM). "
            "Augmentez pour des questions plus longues, diminuez si le modèle plante."
        ),
    )
    if num_ctx < 1024:
        st.info("Valeur basse : réponses rapides mais contexte limité. Idéal pour < 4 Go.", icon="💾")
    elif num_ctx > 3072:
        st.warning(
            f"Valeur élevée ({num_ctx} tokens) — nécessite > 8 Go de RAM disponible. "
            "Fermez d'autres applications si le modèle plante.",
            icon="⚠️",
        )

    temperature = st.slider(
        "Créativité des réponses",
        min_value=0.0, max_value=1.0,
        value=st.session_state.get("adv_temperature", TEMPERATURE_DEFAULT),
        step=0.05,
        key="adv_temperature",
        help=(
            "0.1 = réponses précises et factuelles (recommandé pour l'analyse). "
            "0.5–0.7 = réponses plus variées et créatives."
        ),
    )

    st.caption(
        f"Valeurs actuelles : mémoire **{num_ctx}** tokens · créativité **{temperature:.2f}**"
    )

st.divider()

# ── Conseils de formulation ────────────────────────────────────────────────────
st.markdown("### Conseils de formulation")
for tip in CONSIGNES:
    st.markdown(f"- {tip}")

st.divider()

# ── Statistiques de session ────────────────────────────────────────────────────
st.markdown("### Session en cours")
_rts  = st.session_state.get("response_times", [])
_msgs = [m for m in st.session_state.get("messages", []) if m["role"] == "user"]
if _rts:
    avg_t = sum(_rts) / len(_rts)
    _secs = f"{avg_t:.0f} s" if avg_t < 60 else f"{int(avg_t)//60} min {int(avg_t)%60:02d} s"
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions posées",      len(_msgs))
    c2.metric("Temps moyen / réponse", _secs)
    c3.metric("Réponses totales",      len(_rts))
else:
    st.caption("Aucune question posée dans cette session.")

st.divider()

# ── Cache ──────────────────────────────────────────────────────────────────────
st.markdown("### Cache")
if st.button("🗑️ Vider le cache", use_container_width=False):
    st.cache_resource.clear()
    st.cache_data.clear()
    st.success("Cache vidé. Rechargez la page pour recréer les connexions.")
