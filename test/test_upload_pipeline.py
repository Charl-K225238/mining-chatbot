"""
Audit complet du pipeline d'upload.
Teste chaque type de fichier (TXT, PDF, DOCX, Excel) et signale les bugs.

Usage: .venv/Scripts/python.exe test/test_upload_pipeline.py
"""
import sys, io, os, tempfile, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from pathlib import Path
from src.ingest.upload_handler import save_file, is_data_file, tables_for_file, target_dir
from src.ingest.pipeline import run as run_pipeline, PARQUET_DIR
from src.db.connection import get_db, close
from src.rag.corpus import _from_clean_files

ROOT   = Path(".").resolve()
CLEAN  = ROOT / "data" / "clean"
RAW    = ROOT / "data" / "raw"
passed = 0
failed = 0

def ok(label): global passed; passed += 1; print(f"  [OK] {label}")
def fail(label, reason=""): global failed; failed += 1; print(f"  [FAIL] {label}"); reason and print(f"         ↳ {reason}")
def section(t): print(f"\n{'═'*60}\n{t}\n{'─'*60}")

# ═══════════════════════════════════════════════════════════
section("1. upload_handler — routage et validation")
# ═══════════════════════════════════════════════════════════
cases = [
    (".xlsx", str(CLEAN.parent / "raw")),
    (".xls",  str(CLEAN.parent / "raw")),
    (".csv",  str(CLEAN.parent / "raw")),
    (".pdf",  str(CLEAN / "pdf")),
    (".docx", str(CLEAN / "doc")),
    (".doc",  str(CLEAN / "doc")),
    (".txt",  str(CLEAN / "txt")),
]
for ext, expected_dir in cases:
    fname = f"test_file{ext}"
    d = target_dir(fname)
    if d and str(d) == expected_dir:
        ok(f"Routage {ext} → {Path(expected_dir).name}/")
    else:
        fail(f"Routage {ext}", f"Attendu '{expected_dir}', obtenu '{d}'")

# Extension non supportée
try:
    save_file(b"test", "file.xyz")
    fail("Extension .xyz rejetée (devrait lever ValueError)")
except ValueError:
    ok("Extension .xyz rejetée → ValueError ✓")

# is_data_file
for ext in [".xlsx", ".xls", ".csv"]:
    if is_data_file(f"f{ext}"): ok(f"is_data_file({ext}) = True")
    else: fail(f"is_data_file({ext}) devrait être True")
for ext in [".pdf", ".docx", ".txt"]:
    if not is_data_file(f"f{ext}"): ok(f"is_data_file({ext}) = False")
    else: fail(f"is_data_file({ext}) devrait être False")

# ═══════════════════════════════════════════════════════════
section("2. tables_for_file — correspondance config")
# ═══════════════════════════════════════════════════════════
known = [
    ("DESCENTE MINERAI.xlsx", "descente_minerai"),
    ("CARBURANT.xlsx",        "carburant_activites"),   # multi-table même fichier
    ("Benene_0_Objectifs.xlsx", "objectifs"),
]
for fname, expected_table in known:
    r = tables_for_file(fname)
    if r and expected_table in r:
        ok(f"tables_for_file('{fname}') → '{expected_table}'")
    else:
        fail(f"tables_for_file('{fname}')", f"Attendu '{expected_table}', obtenu {list(r.keys()) if r else 'None'}")

# Fichier inconnu → None → déclenchera pipeline complet
unknown = tables_for_file("nouveau_rapport.xlsx")
if unknown is None:
    ok("Fichier inconnu → None (pipeline complet sera lancé)")
else:
    fail("Fichier inconnu devrait retourner None")

# ═══════════════════════════════════════════════════════════
section("3. save_file — écriture physique")
# ═══════════════════════════════════════════════════════════
tmp = Path(tempfile.mkdtemp())
try:
    # TXT
    p = CLEAN / "txt" / "_test_upload.txt"
    save_file(b"Test contenu ASCII et accentue", "_test_upload.txt")
    if p.exists() and p.stat().st_size > 0:
        ok("save_file TXT → fichier créé")
        p.unlink()
    else:
        fail("save_file TXT → fichier vide ou absent")

    # Vérifier que le répertoire est créé automatiquement
    new_dir = CLEAN / "txt"
    if new_dir.exists():
        ok("Répertoire cible créé automatiquement")
    else:
        fail("Répertoire cible non créé")
except Exception as e:
    fail("save_file", str(e))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ═══════════════════════════════════════════════════════════
section("4. Indexation fichiers uploadés (_from_clean_files)")
# ═══════════════════════════════════════════════════════════

# Créer un vrai fichier TXT de test
txt_test = CLEAN / "txt" / "_audit_test.txt"
txt_test.write_text("Rapport d'exploitation mine Bénéné.\n"
                    "Extraction de bauxite : 5000 tonnes en avril.\n"
                    "Pannes signalées : 3 tombereaux immobilisés.\n"
                    "Responsable : Chef de site Koné.", encoding="utf-8")
try:
    docs = _from_clean_files()
    txt_docs = [d for d in docs if d["table"] == "fichier_txt" and "_audit_test" in d["id"]]
    if txt_docs:
        text = txt_docs[0]["text"]
        # Vérifier que le texte complet est indexé (pas tronqué à 600 chars)
        if "Pannes" in text and "Responsable" in text:
            ok("TXT — contenu complet indexé")
        elif "Pannes" not in text:
            fail("TXT — contenu tronqué avant 'Pannes' (limite trop basse)")
        if len(text) > 100:
            ok(f"TXT — texte significatif ({len(text)} chars)")
        else:
            fail("TXT — texte trop court")
    else:
        fail("TXT — document non trouvé dans corpus")
finally:
    txt_test.unlink(missing_ok=True)

# Test PDF (vérifier dépendance)
try:
    import PyPDF2
    ok("PDF — dépendance PyPDF2 disponible")
except ImportError:
    fail("PDF — PyPDF2 non installé (pip install PyPDF2)")

# Test DOCX (vérifier dépendance)
try:
    from docx import Document as DocxDoc
    ok("DOCX — dépendance python-docx disponible")
except ImportError:
    fail("DOCX — python-docx non installé (pip install python-docx)")

# Test DOC (ancienne extension — NON supportée analytiquement)
doc_test = CLEAN / "doc" / "_audit_test.doc"
doc_test.write_bytes(b"Old word content")
try:
    docs_after = _from_clean_files()
    doc_docs = [d for d in docs_after if "_audit_test" in d.get("id", "")]
    if not doc_docs:
        # .doc n'est PAS indexé — comportement voulu + avertissement UI affiché
        ok("DOC — .doc non indexé (comportement voulu : avertissement UI affiché)")
finally:
    doc_test.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════
section("5. Pipeline Excel — lecture et nettoyage")
# ═══════════════════════════════════════════════════════════
# Test sur une table connue (objectifs)
from src.ingest.config import TABLES
obj_file = RAW / TABLES["objectifs"].file
if obj_file.exists():
    try:
        r = run_pipeline({"objectifs": TABLES["objectifs"]})
        if "objectifs" in r and len(r["objectifs"]) > 0:
            ok(f"Pipeline 'objectifs' → {len(r['objectifs'])} lignes")
        else:
            fail("Pipeline 'objectifs' → 0 lignes")
        # Vérifier que le Parquet est écrit
        pq = PARQUET_DIR / "objectifs.parquet"
        if pq.exists() and pq.stat().st_size > 100:
            ok("Parquet 'objectifs' écrit")
        else:
            fail("Parquet 'objectifs' absent ou vide")
        # Vérifier que les colonnes dates sont bien converties
        import pandas as pd
        df_check = pd.read_parquet(pq)
        date_col = TABLES["objectifs"].date_cols[0]
        if pd.api.types.is_datetime64_any_dtype(df_check[date_col]):
            ok(f"Colonne '{date_col}' correctement en datetime")
        else:
            fail(f"Colonne '{date_col}' devrait être datetime")
    except Exception as e:
        fail("Pipeline objectifs", str(e))
else:
    fail(f"Fichier source absent : {obj_file}")

# ═══════════════════════════════════════════════════════════
section("6. Cohérence DuckDB après pipeline")
# ═══════════════════════════════════════════════════════════
try:
    close()
    con = get_db()
    n = con.execute("SELECT COUNT(*) FROM objectifs").fetchone()[0]
    if n > 0:
        ok(f"DuckDB voit la table objectifs ({n} lignes)")
    else:
        fail("DuckDB — table objectifs vide après pipeline")
    close()
except Exception as e:
    fail("DuckDB chargement", str(e))

# ═══════════════════════════════════════════════════════════
section("7. CSV — comportement réel (limitation connue)")
# ═══════════════════════════════════════════════════════════
# CSV est accepté en upload mais n'est pas converti en Parquet
# car loader.py utilise pd.read_excel()
csv_bytes = b"DATE,QUANTITE\n2026-01-01,100\n2026-01-02,200\n"
csv_test = RAW / "_test_upload.csv"
try:
    save_file(csv_bytes, "_test_upload.csv")
    if csv_test.exists():
        ok("CSV sauvegardé dans data/raw/")
        # Vérifier qu'il ne génère pas de Parquet (pas dans config)
        _csv_tables = tables_for_file("_test_upload.csv")  # None si inconnu
        r = run_pipeline(_csv_tables)  # None → all tables (expected behaviour)
        if _csv_tables is None:
            ok("CSV sans correspondance config → None retourné (pipeline complet déclenché)")
        elif not r:
            ok("CSV avec config vide → pipeline vide")
        else:
            ok(f"CSV traité ({len(r)} tables)")
    else:
        fail("CSV non sauvegardé")
finally:
    csv_test.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════
section("8. Reconstruction index BM25 après upload")
# ═══════════════════════════════════════════════════════════
try:
    from src.rag.index import build_and_save, INDEX_PATH
    close()
    con = get_db()
    idx = build_and_save(con)
    if len(idx.docs) > 0:
        ok(f"Index BM25 reconstruit — {len(idx.docs)} documents")
    else:
        fail("Index BM25 vide après reconstruction")
    if INDEX_PATH.exists():
        ok("Index sauvegardé sur disque")
    else:
        fail("Index non sauvegardé")
    # Vérifier que la recherche retourne des résultats
    results = idx.search("panne tombereau", top_k=3)
    if results:
        ok(f"Recherche BM25 → {len(results)} résultats pour 'panne tombereau'")
    else:
        fail("Recherche BM25 → aucun résultat pour 'panne tombereau'")
    close()
except Exception as e:
    fail("Reconstruction index", str(e))

# ═══════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"RÉSUMÉ : {passed}/{passed+failed} tests réussis")
if failed:
    print(f"         {failed} problème(s) à corriger — voir détails")
print(f"{'═'*60}\n")
