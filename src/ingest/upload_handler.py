"""
Gestion des fichiers uploadés via l'interface Streamlit.

Routage :
    .xlsx / .xls / .csv  →  data/raw/
    .pdf                 →  data/clean/pdf/
    .docx / .doc         →  data/clean/doc/
    .txt                 →  data/clean/txt/

À chaque upload de document (PDF/DOCX/TXT), les métadonnées sont enregistrées
dans doc_manifest.json (type détecté, date upload…).

Usage :
    from src.ingest.upload_handler import save_file, is_data_file, tables_for_file
    path = save_file(file_bytes, "DESCENTE MINERAI.xlsx")
    if is_data_file("DESCENTE MINERAI.xlsx"):
        from src.ingest.pipeline import run
        run(tables_for_file("DESCENTE MINERAI.xlsx") or None)  # None → toutes tables
"""

from pathlib import Path

_ROOT = Path(__file__).parents[2]

_ROUTING: dict[str, Path] = {
    ".xlsx": _ROOT / "data" / "raw",
    ".xls":  _ROOT / "data" / "raw",
    ".csv":  _ROOT / "data" / "raw",
    ".pdf":  _ROOT / "data" / "clean" / "pdf",
    ".docx": _ROOT / "data" / "clean" / "doc",
    ".doc":  _ROOT / "data" / "clean" / "doc",
    ".txt":  _ROOT / "data" / "clean" / "txt",
}

# Extensions de documents textuels (→ RAG) vs données structurées (→ ETL)
_DOC_EXTENSIONS  = frozenset({".pdf", ".docx", ".doc", ".txt"})
_DATA_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv"})

ACCEPTED_EXTENSIONS: frozenset[str] = frozenset(_ROUTING.keys())


def target_dir(filename: str) -> Path | None:
    """Retourne le répertoire cible pour un fichier, ou None si extension non supportée."""
    return _ROUTING.get(Path(filename).suffix.lower())


def save_file(file_bytes: bytes, filename: str) -> Path:
    """
    Sauvegarde un fichier dans le bon répertoire, le remplaçant s'il existe déjà.
    Pour les documents (PDF/DOCX/TXT), enregistre également les métadonnées
    dans doc_manifest.json (type de document, date d'upload…).

    Args:
        file_bytes : contenu binaire du fichier (ex: UploadedFile.getvalue()).
        filename   : nom du fichier avec extension.

    Returns:
        Path absolu du fichier sauvegardé.

    Raises:
        ValueError : si l'extension n'est pas dans ACCEPTED_EXTENSIONS.
    """
    dest_dir = target_dir(filename)
    if dest_dir is None:
        ext = Path(filename).suffix
        raise ValueError(
            f"Extension « {ext} » non supportée. "
            f"Formats acceptés : {', '.join(sorted(ACCEPTED_EXTENSIONS))}"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(file_bytes)

    # Enregistrer les métadonnées pour les documents textuels (RAG)
    if Path(filename).suffix.lower() in _DOC_EXTENSIONS:
        try:
            # Extraire un petit échantillon du contenu pour améliorer la détection
            content_sample = _extract_text_sample(file_bytes, filename)
            from src.rag.doc_manifest import register
            register(filename, content_sample=content_sample)
        except Exception:
            pass  # Non bloquant

    return dest


def _extract_text_sample(file_bytes: bytes, filename: str, max_chars: int = 500) -> str:
    """
    Extrait un court échantillon de texte d'un document pour la détection de type.
    Retourne une chaîne vide en cas d'échec (non bloquant).
    """
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".txt":
            return file_bytes[:max_chars].decode("utf-8", errors="replace")
        if ext == ".pdf":
            import io
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                text = ""
                for page in reader.pages[:2]:
                    text += page.extract_text() or ""
                    if len(text) >= max_chars:
                        break
                return text[:max_chars]
            except Exception:
                return ""
        if ext in (".docx", ".doc"):
            import io
            try:
                import docx
                doc = docx.Document(io.BytesIO(file_bytes))
                text = " ".join(p.text for p in doc.paragraphs[:10])
                return text[:max_chars]
            except Exception:
                return ""
    except Exception:
        pass
    return ""


def is_data_file(filename: str) -> bool:
    """True pour Excel/CSV — déclenche le pipeline ETL après upload."""
    return Path(filename).suffix.lower() in {".xlsx", ".xls", ".csv"}


def is_known_file(filename: str) -> bool:
    """
    True si le fichier est référencé dans la config ETL (src/ingest/config.py).

    Utiliser cette fonction AVANT tables_for_file() pour avertir l'utilisateur
    qu'un fichier inconnu déclenchera le re-traitement de TOUTES les tables.

    Exemple dans la page :
        if is_data_file(name) and not is_known_file(name):
            st.warning("Fichier non reconnu — toutes les tables seront re-traitées.")
    """
    from src.ingest.config import TABLES
    fname_lower = filename.strip().lower()
    return any(Path(cfg.file).name.lower() == fname_lower for cfg in TABLES.values())


def tables_for_file(filename: str) -> dict | None:
    """
    Retourne le sous-ensemble de TABLES correspondant au fichier uploadé.

    Si le fichier n'est pas référencé dans la config, retourne None —
    l'appelant DOIT avoir vérifié is_known_file() au préalable et averti
    l'utilisateur, car None déclenche le re-traitement de toutes les tables.

    Args:
        filename : nom du fichier uploadé (ex: "DESCENTE MINERAI.xlsx").

    Returns:
        dict {nom_table: TableConfig} si le fichier est connu, None sinon.
    """
    from src.ingest.config import TABLES
    fname_lower = filename.strip().lower()
    matched = {
        name: cfg
        for name, cfg in TABLES.items()
        if Path(cfg.file).name.lower() == fname_lower
    }
    return matched if matched else None
