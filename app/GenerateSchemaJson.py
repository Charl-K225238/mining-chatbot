import json
import os

from . import GenerateSchemaMd as md_parser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "..", "data", "schemas", "Schema.json")


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_column_json(block):
    columns = md_parser.extract_columns(block)
    missing = md_parser.extract_missing(block)
    missing_map = {col: {"count": int(n), "pct": float(pct), "level": lvl} for col, n, pct, lvl in missing}

    result = []
    seen = set()

    for col, dtype in columns:
        seen.add(col)
        info = {
            "name": col,
            "type": dtype,
            "missing_count": missing_map.get(col, {}).get("count", 0),
            "missing_pct": missing_map.get(col, {}).get("pct", 0.0),
            "missing_level": missing_map.get(col, {}).get("level", "OK"),
        }
        result.append(info)

    for col, n, pct, lvl in missing:
        if col not in seen:
            result.append({
                "name": col,
                "type": None,
                "missing_count": int(n),
                "missing_pct": float(pct),
                "missing_level": lvl,
            })

    return result


def build_sheet_json(sheet_name, block):
    rows, cols = md_parser.extract_shape(block)
    columns = build_column_json(block)
    has_date_columns = any(
        (col["type"] and col["type"].startswith("datetime"))
        or "date" in col["name"].lower()
        or "jour" in col["name"].lower()
        or "année" in col["name"].lower()
        or "year" in col["name"].lower()
        for col in columns
    )
    issues = md_parser.detect_issues(block)

    return {
        "name": sheet_name,
        "rows": int(rows) if rows else None,
        "columns_count": int(cols) if cols else None,
        "columns": columns,
        "has_date_columns": has_date_columns,
        "powerbi_calendar_hint": has_date_columns,
        "issues": issues,
    }


def build_file_json(file_name, content):
    sheets = md_parser.extract_sheets(content)
    file_key = os.path.splitext(file_name)[0]

    return {
        "file_name": file_name,
        "file_key": file_key,
        "description": md_parser.describe_file(file_name),
        "role": md_parser.get_file_role(file_name),
        "usage": md_parser.get_file_usage(file_name),
        "sheet_count": len(sheets),
        "sheets": [build_sheet_json(sheet_name, block) for sheet_name, block in sheets],
    }


def build_schema_json(text):
    files = md_parser.extract_files(text)

    return {
        "catalog": {
            "title": "DATA SCHEMA CATALOG",
            "version": "1.0",
            "objective": "documenter toutes les sources de données, leur rôle métier, leurs structures et leurs relations.",
        },
        "domain_model": md_parser.DOMAIN_FILE_MAP,
        "relations": md_parser.RELATION_GROUPS,
        "quality_summary": md_parser.QUALITY_SUMMARY,
        "usage_summary": md_parser.USAGE_SUMMARY,
        "calendar_table": {
            "description": "Table calendrier pour analyses temporelles",
            "columns": [
                "Date", "Année", "Mois", "Nom_Mois", "Jour",
                "Jour_Semaine", "Nom_Jour_Semaine", "Semaine_Année",
                "Trimestre", "Semestre", "Est_Weekend", "Est_Jour_Férié",
                "Fin_De_Mois", "Fin_De_Trimestre", "Fin_De_Semestre", "Fin_De_Année",
                "Mois_Année", "Trimestre_Année", "Semestre_Année", "Semaine_Mois",
                "Est_Jour_Ouvré", "Saison", "Période_Fiscale"
            ],
            "usage": "Relations temporelles dans Power BI et analyses par périodes"
        },
        "files": [build_file_json(file_name, content) for file_name, content in files],
    }


def main():
    input_file = md_parser.find_input_file()
    text = load_text(input_file)
    schema = build_schema_json(text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f"[OK] schema.json genere avec succes : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
