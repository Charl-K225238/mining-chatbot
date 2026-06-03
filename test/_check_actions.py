import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
from src.db.connection import get_db
con = get_db()
for tbl in ["suivi_actions", "pges_actions"]:
    try:
        desc = con.execute(f"DESCRIBE {tbl}").df()
        n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"\n=== {tbl} ({n} lignes) ===")
        print(desc[["column_name","column_type"]].to_string(index=False))
        print("\nAperçu :")
        print(con.execute(f"SELECT * FROM {tbl} LIMIT 3").df().to_string())
    except Exception as e:
        print(f"ERREUR {tbl}: {e}")
