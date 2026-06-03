import json
import re

input_file = r"data/clean/excel/DESCENTE MINERAI_processed.json"

with open(input_file, "r", encoding="utf-8") as f:
    content = f.read()

# Remplacer NaN par null
content = re.sub(r'\bNaN\b', 'null', content)

# Sauvegarder version corrigée
fixed_file = r"data/clean/excel/DESCENTE_MINERAI_fixed.json"

with open(fixed_file, "w", encoding="utf-8") as f:
    f.write(content)

print("JSON corrigé.")