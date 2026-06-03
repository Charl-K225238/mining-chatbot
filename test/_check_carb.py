import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
from src.db.connection import get_db
con = get_db()
print("Années et totaux carburant_citerne:")
print(con.execute("""
    SELECT YEAR("Date") AS annee,
           COUNT(*) AS lignes,
           SUM("Quantité Servie (L)") AS total_servi_L,
           SUM("Depotage") AS total_depotage_L
    FROM carburant_citerne
    GROUP BY 1 ORDER BY 1
""").df().to_string())
print("\nPremière et dernière date:")
print(con.execute('SELECT MIN("Date"), MAX("Date") FROM carburant_citerne').fetchone())
