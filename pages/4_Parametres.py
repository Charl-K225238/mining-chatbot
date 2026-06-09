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
try:
    from core.ollama_client import (
        is_available, active_model_name,
        lister_modeles_disponibles, assurer_modele_disponible, assurer_ollama_disponible,
        ollama_est_disponible, trouver_ollama_exe, is_remote_ollama,
        groq_est_disponible,
        IS_WINDOWS, IS_STREAMLIT_CLOUD,
    )
    _OLLAMA_IMPORTABLE = True
except Exception:
    _OLLAMA_IMPORTABLE = False
    IS_WINDOWS = False
    IS_STREAMLIT_CLOUD = True
    def is_available(*a, **kw): return False          # noqa: E306
    def active_model_name(*a, **kw): return "—"
    def lister_modeles_disponibles(*a, **kw): return []
    def assurer_modele_disponible(*a, **kw): return False
    def assurer_ollama_disponible(*a, **kw): return False
    def ollama_est_disponible(*a, **kw): return False
    def trouver_ollama_exe(*a, **kw): return None
    def is_remote_ollama(*a, **kw): return False
    def groq_est_disponible(*a, **kw): return False
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
if groq_est_disponible():
    st.success(
        "**Service IA actif** — tous les modes sont disponibles.\n\n"
        "⚡ Analytique · 🔢 Calcul · 🏭 Expertise · 💬 Général",
        icon="✅",
    )
else:
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

    # ── Bouton de vérification partagé entre les 3 guides ────────────────────
    def _verifier_ollama_btn(key: str) -> None:
        """Bouton 'J'ai installé — vérifier' : teste Ollama sans recharger la page."""
        if st.button("✅ J'ai installé Ollama — vérifier maintenant",
                     key=key, type="primary", use_container_width=True):
            with st.spinner("Détection en cours…"):
                _ok = assurer_ollama_disponible()
            if _ok:
                st.success("Ollama détecté ! Passez à l'étape suivante.")
                st.rerun()
            else:
                st.warning(
                    "Ollama n'est pas encore détecté.\n\n"
                    "Assurez-vous que l'installation est bien terminée, "
                    "puis cliquez à nouveau sur ce bouton."
                )

    # ── Sélection de modèle partagée entre Windows et Linux/Mac ──────────────
    def _section_modele(key_prefix: str) -> None:
        """Boutons de téléchargement de modèle — recommandé en premier, alternatives cachées."""
        _dispo = ollama_est_disponible()

        def _dl(model: str, btn_key: str) -> None:
            if st.button(f"⬇️ {model}", key=btn_key, use_container_width=True):
                if not _dispo:
                    st.warning(
                        "Ollama n'est pas encore actif.\n\n"
                        "Utilisez le bouton **'J'ai installé Ollama — vérifier'** "
                        "ci-dessus, puis réessayez."
                    )
                else:
                    assurer_modele_disponible(model, placeholder=st.empty())

        st.markdown("**Modèle recommandé** — fonctionne sur la plupart des PC :")
        _dl("qwen2.5:3b", f"{key_prefix}_rec")
        st.caption("Téléchargement unique ~2 Go · durée 5–15 min selon votre connexion")

        with st.expander("🐢 Mon PC est ancien ou lent (moins de 4 Go de mémoire)"):
            st.markdown("Ce modèle est plus léger, les réponses sont un peu moins précises :")
            _dl("phi3:mini", f"{key_prefix}_lite")

        with st.expander("🚀 Je veux les meilleures réponses (PC récent, 8 Go ou plus)"):
            _c1, _c2 = st.columns(2)
            with _c1:
                _dl("qwen2.5:7b", f"{key_prefix}_7b")
            with _c2:
                _dl("qwen2.5:14b", f"{key_prefix}_14b")

    if IS_STREAMLIT_CLOUD:
        # ── Guide Streamlit Cloud — Groq uniquement ────────────────────────────
        st.markdown("---")
        st.markdown("#### Étape 1 — Créer un compte Groq gratuit")
        _gc1, _gc2 = st.columns([3, 2])
        with _gc1:
            st.link_button("Créer un compte Groq", "https://console.groq.com/login",
                           type="primary", use_container_width=True)
            st.caption("Gratuit · sans carte bancaire · sans installation")
        with _gc2:
            st.info("Groq est une API IA cloud : aucun logiciel à installer sur votre PC.",
                    icon="☁️")
        st.markdown("---")
        st.markdown("#### Étape 2 — Générer une clé API")
        st.link_button("Mes clés API Groq", "https://console.groq.com/keys",
                       use_container_width=False)
        st.markdown(
            "Cliquez **Create API key**, donnez-lui un nom (ex: `miny`), "
            "puis copiez la clé affichée *(elle commence par `gsk_…`)*."
        )
        st.markdown("---")
        st.markdown("#### Étape 3 — Ajouter la clé dans Miny")
        st.link_button("Ouvrir les Secrets Streamlit", "https://share.streamlit.io",
                       use_container_width=False)
        st.markdown("Votre application → menu **⋯** → **Settings** → **Secrets**, puis collez :")
        st.code('GROQ_API_KEY = "gsk_votre_cle_ici"', language="toml")
        st.markdown("Cliquez **Save** — Miny redémarre automatiquement en 30 secondes.")
        st.success("C'est tout. Aucune installation, aucune fenêtre à laisser ouverte.", icon="✅")
        st.markdown("---")

    elif IS_WINDOWS:
        # ── Guide Windows local ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Étape 1 — Télécharger et installer Ollama")
        _w1, _w2 = st.columns([3, 2])
        with _w1:
            st.link_button(
                "⬇️ Télécharger Ollama pour Windows",
                "https://ollama.com/download/OllamaSetup.exe",
                type="primary",
                use_container_width=True,
            )
            st.markdown(
                "Ouvrez le fichier téléchargé et suivez les étapes "
                "*(cliquez simplement Suivant → Installer)*.\n\n"
                "Une fois installé, une petite icône 🦙 apparaît en bas à droite de l'écran."
            )
        with _w2:
            st.info("Vos données restent sur votre PC — rien n'est envoyé sur Internet.",
                    icon="🔒")
        st.markdown("Cliquez ici quand l'installation est terminée :")
        _verifier_ollama_btn("win_verif")
        st.markdown("---")

        st.markdown("#### Étape 2 — Télécharger un modèle IA")
        _section_modele("win")
        st.markdown("---")
        st.success(
            "C'est tout ! Miny détecte et démarre Ollama automatiquement à chaque utilisation.",
            icon="✅",
        )
        st.markdown("---")

    else:
        # ── Guide Linux / Mac local ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Étape 1 — Installer Ollama")
        _lx1, _lx2 = st.columns([3, 2])
        with _lx1:
            st.markdown("Dans un terminal, collez cette commande :")
            st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")
        with _lx2:
            st.link_button("Ou télécharger pour Mac",
                           "https://ollama.com/download/Ollama-darwin.zip",
                           use_container_width=True)
            st.info("Ollama démarre automatiquement après installation.", icon="✅")
        st.markdown("Cliquez ici quand l'installation est terminée :")
        _verifier_ollama_btn("lx_verif")
        st.markdown("---")

        st.markdown("#### Étape 2 — Télécharger un modèle IA")
        _section_modele("lx")
        st.markdown("---")
        st.success(
            "C'est tout ! Miny détecte Ollama automatiquement à chaque démarrage.",
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
        st.warning("`.doc` sauvegardé mais **non indexé**. Convertissez en `.docx`.", icon="⚠️")
    elif _ext == "csv":
        st.info("CSV sauvegardé — pour l'analyser, importez en `.xlsx`.", icon="ℹ️")
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

# ── Statut LLM Cloud ──────────────────────────────────────────────────────────
if IS_STREAMLIT_CLOUD:
    st.markdown("### ☁️ Connexion IA (Cloud)")

    try:
        _groq_key      = st.secrets.get("GROQ_API_KEY", "")
        _host_secret   = st.secrets.get("OLLAMA_HOST", "")
    except Exception:
        _groq_key, _host_secret = "", ""

    if _groq_key and groq_est_disponible():
        st.success(
            "**Groq API** connectée — modèles IA disponibles.\n\n"
            f"Modèle actif : **{active_model_name()}**",
            icon="✅",
        )
    elif _groq_key and not groq_est_disponible():
        st.warning(
            "**GROQ_API_KEY** présente mais le SDK `groq` n'est pas installé.\n\n"
            "Vérifiez que `groq>=0.9.0` est dans `requirements.txt` et redéployez.",
            icon="⚠️",
        )
    elif _host_secret:
        _host_display = _host_secret.rstrip("/")
        if _disponible:
            st.success(
                f"**OLLAMA_HOST** configuré : `{_host_display}` — connexion active.\n\n"
                f"Modèle actif : **{_model_actif}**",
                icon="✅",
            )
        else:
            st.warning(
                f"**OLLAMA_HOST** configuré : `{_host_display}` mais Ollama ne répond pas.\n\n"
                "Vérifiez qu'Ollama et ngrok tournent sur votre PC.",
                icon="⚠️",
            )
            if st.button("🔍 Tester la connexion", key="test_ollama_host"):
                with st.spinner("Test en cours…"):
                    _ok = assurer_ollama_disponible()
                if _ok:
                    st.success(f"Connexion établie — modèle : **{active_model_name()}**", icon="✅")
                    st.rerun()
                else:
                    st.error(
                        "Impossible de joindre Ollama. "
                        "Relancez ngrok et mettez à jour l'URL dans les Secrets Streamlit."
                    )
    else:
        st.error(
            "**Aucune clé IA configurée** — les modes 🔢 🏭 💬 🤖 sont désactivés.\n\n"
            "Suivez le **Guide de démarrage** ci-dessus pour activer l'IA.",
            icon="☁️",
        )

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
    if groq_est_disponible():
        st.success(f"**{active_model_name()}** via Groq — prêt", icon="🤖")
        st.caption("Les modes IA utilisent l'API Groq. Aucun modèle local requis.")
    elif _ollama_pret:
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
            "Aucun service IA configuré. "
            "Suivez le **Guide de démarrage** ci-dessus pour activer Groq.",
            icon="🤖",
        )
    else:
        st.error(
            "Ollama **non installé ou non démarré**. "
            "Seul ⚡ Analytique fonctionne. "
            "Suivez le **Guide de démarrage** ci-dessus.",
            icon="🤖",
        )

    if not groq_est_disponible():
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
        if st.button(f"⬇️ {PRIMARY_MODEL}", use_container_width=True, key="dl_primary",
                     disabled=groq_est_disponible()):
            if not _disponible:
                st.error("Démarrez Ollama d'abord.")
            else:
                assurer_modele_disponible(PRIMARY_MODEL, placeholder=st.empty())
    with _dl2:
        if st.button(f"⬇️ {FALLBACK_MODEL}", use_container_width=True, key="dl_fallback",
                     disabled=groq_est_disponible()):
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
