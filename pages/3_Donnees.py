"""
Miny — 📊 Données
Explorateur de tables + gestion des documents indexés.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from core.data_loader import get_db, load_css, sidebar_stats, max_date
from src.db.connection import list_tables

st.set_page_config(
    page_title="📊 Données — Miny",
    page_icon="⛏",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()

with st.sidebar:
    st.markdown("## ⛏ Miny")
    st.caption("Assistant BI · Mine de bauxite R2M CI")

st.markdown("## 📊 Données")

con = get_db()

# ── Explorateur de tables ──────────────────────────────────────────────────────
st.markdown("### Tables disponibles")

_s = sidebar_stats()
if _s.get("error"):
    st.error(f"Données indisponibles : {_s['error']}")
else:
    _yr = " · ".join(str(y) for y in _s["years"])
    st.info(f"Années couvertes : **{_yr}**", icon="📅")

    # Tables actives (avec date) vs référentiels (sans date)
    ops_d  = [(n, nb, last) for n, nb, last in _s["tables"] if last]
    refs_d = [(n, nb)       for n, nb, last in _s["tables"] if not last]

    # Selectbox pour explorer une table
    all_tables = [t for t, _, _ in _s["tables"]]
    if all_tables:
        selected = st.selectbox(
            "Choisir une table à explorer",
            options=all_tables,
            format_func=lambda t: f"{t}",
        )
        if selected and selected in all_tables:
            try:
                df_preview = con.execute(
                    f'SELECT * FROM "{selected}" LIMIT 10'
                ).fetchdf()
                nb_rows = con.execute(
                    f'SELECT COUNT(*) FROM "{selected}"'
                ).fetchone()[0]
                nb_cols = len(df_preview.columns)
                last_d  = max_date(con, selected)

                meta_parts = [f"**{nb_rows:,}** lignes", f"**{nb_cols}** colonnes"]
                if last_d:
                    meta_parts.append(f"dernière date : **{last_d}**")
                st.caption(" · ".join(meta_parts))

                st.dataframe(df_preview, use_container_width=True)
            except Exception as exc:
                st.error(f"Impossible de charger `{selected}` : {exc}")

    st.divider()

    # Tables actives dans un accordéon (même style que Référentiels)
    if ops_d:
        with st.expander(f"📊 Tables opérationnelles ({len(ops_d)} tables)", expanded=False):
            _replace_target = st.session_state.get("replace_table_target")
            cols_hdr = st.columns([3, 1, 2, 2])
            cols_hdr[0].markdown("**Table**")
            cols_hdr[1].markdown("**Lignes**")
            cols_hdr[2].markdown("**Dernière date**")
            cols_hdr[3].markdown("**Actions**")
            for name, nb, last in ops_d:
                c1, c2, c3, c4 = st.columns([3, 1, 2, 2])
                c1.code(name, language=None)
                c2.write(f"{nb:,}")
                c3.write(f"📅 {last}")
                if c4.button("🔄 Remplacer", key=f"repl_tbl_{name}",
                             use_container_width=True):
                    st.session_state["replace_table_target"] = name
                    st.rerun()

            # Zone de remplacement inline — affichée directement sous la liste, bien visible
            if _replace_target and _replace_target in [n for n, _, _ in ops_d]:
                from src.ingest.config import TABLES as _INGEST_TABLES
                _target_cfg  = _INGEST_TABLES.get(_replace_target)
                _source_file = _target_cfg.file if _target_cfg else None
                _siblings    = [
                    t for t, cfg in _INGEST_TABLES.items()
                    if _source_file and cfg.file == _source_file and t != _replace_target
                ]

                st.markdown('<div id="replace-zone"></div>', unsafe_allow_html=True)

                if _siblings:
                    _sibling_str = ", ".join(f"`{t}`" for t in _siblings)
                    st.info(
                        f"**Fichier source : `{_source_file}`**\n\n"
                        f"Ce fichier contient plusieurs onglets. L'importation mettra à jour "
                        f"**toutes** ces tables simultanément : `{_replace_target}`, {_sibling_str}.\n\n"
                        f"Importez le fichier **`{_source_file}`** ci-dessous.",
                        icon="ℹ️",
                    )
                else:
                    st.info(
                        f"**Vous remplacez `{_replace_target}`** (`{_source_file}`) — "
                        f"choisissez le fichier Excel (.xlsx) et cliquez **⬆️ Importer**.",
                        icon="🔄",
                    )

                _up = st.file_uploader(
                    f"Choisir {_source_file or 'fichier Excel (.xlsx)'}",
                    type=["xlsx", "xls"],
                    key=f"up_tbl_{_replace_target}",
                )
                if _up:
                    if st.button("⬆️ Importer et remplacer", key=f"do_repl_{_replace_target}",
                                 use_container_width=True):
                        from src.ingest.upload_handler import save_file, tables_for_file
                        from src.ingest.pipeline import run as run_pipeline
                        from src.engine.query_router import rebuild_index
                        from src.db.connection import close as close_db
                        try:
                            save_file(_up.getvalue(), _up.name)
                            _subset = tables_for_file(_up.name)
                            with st.spinner(f"Mise à jour de {len(_subset)} table(s)…"):
                                run_pipeline(_subset)
                                close_db()
                                st.cache_resource.clear()
                                st.cache_data.clear()
                                rebuild_index()
                            _updated = ", ".join(f"`{t}`" for t in _subset)
                            st.success(
                                f"Importation réussie. Tables mises à jour : {_updated}. "
                                f"Réindexation effectuée."
                            )
                            del st.session_state["replace_table_target"]
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Erreur : {_e}")
                if st.button("✖ Annuler", key=f"cancel_repl_{_replace_target}"):
                    del st.session_state["replace_table_target"]
                    st.rerun()

    if refs_d:
        with st.expander(f"📁 Référentiels ({len(refs_d)} tables)", expanded=False):
            for name, nb in refs_d:
                st.write(f"`{name}` — {nb:,} lignes")

st.divider()

# ── Section Documents indexés ──────────────────────────────────────────────────
st.markdown("### Documents indexés")
st.caption("PDF, Word et fichiers texte disponibles pour la recherche documentaire.")

_CLEAN_DIR = ROOT / "data" / "clean"
_DOC_TYPES  = {
    "pdf":  ("📄 PDF",  ".pdf"),
    "doc":  ("📝 Word", ".docx"),
    "txt":  ("📃 Texte", ".txt"),
}

_all_docs: list[tuple[str, str, Path]] = []  # (label_type, nom, path)
for _folder, (_label, _ext) in _DOC_TYPES.items():
    _dir = _CLEAN_DIR / _folder
    if _dir.exists():
        for _f in sorted(_dir.glob(f"*{_ext}")):
            _all_docs.append((_label, _f.name, _f))

if not _all_docs:
    st.info("Aucun document indexé. Chargez des fichiers PDF, DOCX ou TXT dans **⚙️ Paramètres**.", icon="📂")
else:
    _replace_doc = st.session_state.get("replace_doc_target")
    _doc_cols_hdr = st.columns([1, 4, 3])
    _doc_cols_hdr[0].markdown("**Type**")
    _doc_cols_hdr[1].markdown("**Nom**")
    _doc_cols_hdr[2].markdown("**Actions**")

    for _ltype, _fname, _fpath in _all_docs:
        _dc1, _dc2, _dc3 = st.columns([1, 4, 3])
        _dc1.write(_ltype)
        _dc2.write(_fname)
        _btn_cols = _dc3.columns(2)

        if _btn_cols[0].button("🗑️", key=f"del_doc_{_fname}", help="Supprimer ce document"):
            try:
                _fpath.unlink()
                from src.engine.query_router import rebuild_index
                rebuild_index()
                st.success(f"`{_fname}` supprimé. Index mis à jour.")
                st.rerun()
            except Exception as _e:
                st.error(f"Erreur suppression : {_e}")

        if _btn_cols[1].button("🔄", key=f"repl_doc_{_fname}", help="Remplacer ce document"):
            st.session_state["replace_doc_target"] = _fname
            st.rerun()

        # Zone de remplacement inline
        if _replace_doc == _fname:
            _ext_map = {"📄 PDF": ["pdf"], "📝 Word": ["docx"], "📃 Texte": ["txt"]}
            _allowed = _ext_map.get(_ltype, ["pdf", "docx", "txt"])
            _up_doc = st.file_uploader(
                f"Nouveau fichier pour remplacer `{_fname}`",
                type=_allowed,
                key=f"up_doc_{_fname}",
            )
            if _up_doc:
                if st.button("⬆️ Remplacer", key=f"do_repl_doc_{_fname}",
                             use_container_width=True):
                    from src.ingest.upload_handler import save_file
                    from src.engine.query_router import rebuild_index
                    try:
                        _fpath.unlink(missing_ok=True)
                        save_file(_up_doc.getvalue(), _up_doc.name)
                        with st.spinner("Réindexation…"):
                            rebuild_index()
                        st.success(
                            f"`{_fname}` remplacé par `{_up_doc.name}`. Réindexation effectuée."
                        )
                        del st.session_state["replace_doc_target"]
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Erreur : {_e}")
            if st.button("✖ Annuler", key=f"cancel_doc_{_fname}"):
                del st.session_state["replace_doc_target"]
                st.rerun()

    st.caption(
        "💡 Pour charger de nouveaux documents, rendez-vous dans **⚙️ Paramètres → Charger un fichier**."
    )
