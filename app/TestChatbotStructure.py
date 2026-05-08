"""
Test Suite - Validation Chatbot Structure
Vérifie que tous les fichiers sont optimisés pour LLM
"""

import json
import sys
from pathlib import Path

def test_schema_json():
    """Valider structure schema.json"""
    print("📋 Test: schema.json structure...")
    
    try:
        with open("schema.json", 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Vérifier sections clés
        required_keys = ['catalog', 'domain_model', 'relations', 'files', 'calendar_table']
        for key in required_keys:
            assert key in schema, f"Clé manquante: {key}"
            print(f"  ✅ Section '{key}' présente")
        
        # Vérifier files
        files_count = len(schema.get('files', []))
        print(f"  ✅ {files_count} fichiers documentés")
        
        # Vérifier calendrier
        calendar = schema.get('calendar_table', {})
        columns = calendar.get('columns', [])
        assert len(columns) > 0, "Calendrier sans colonnes"
        print(f"  ✅ Calendrier: {len(columns)} colonnes temporelles")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_relationships():
    """Valider relationships.py"""
    print("\n🔗 Test: relationships.py structure...")
    
    try:
        from ..docs.Relations import RELATIONSHIPS, get_related_tables, get_join_keys
        
        # Vérifier dictionnaire
        assert len(RELATIONSHIPS) > 0, "RELATIONSHIPS vide"
        print(f"  ✅ {len(RELATIONSHIPS)} tables avec relations")
        
        # Test get_related_tables
        relations = get_related_tables("Benene_1_Excavation")
        assert len(relations) > 0, "Pas de relations trouvées"
        print(f"  ✅ Benene_1_Excavation a {len(relations)} relations")
        
        # Test get_join_keys
        keys = get_join_keys("Benene_1_Excavation", "Calendrier")
        assert len(keys) > 0, "Pas de clé de jointure"
        print(f"  ✅ Clés jointure Excavation-Calendrier: {keys}")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_calendar_csv():
    """Valider calendar.csv"""
    print("\n📅 Test: calendar.csv...")
    
    try:
        import pandas as pd
        
        df = pd.read_csv("calendar.csv")
        
        # Vérifier dimensions
        print(f"  ✅ {len(df)} lignes")
        print(f"  ✅ {len(df.columns)} colonnes")
        
        # Vérifier colonnes clés
        required_cols = ['Date', 'Année', 'Mois', 'Trimestre']
        for col in required_cols:
            assert col in df.columns, f"Colonne manquante: {col}"
        print(f"  ✅ Colonnes clés présentes")
        
        # Vérifier dates
        assert df['Date'].notna().sum() > 0, "Pas de dates"
        date_range = f"{df['Date'].min()} à {df['Date'].max()}"
        print(f"  ✅ Période: {date_range}")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_context_files():
    """Valider fichiers contexte"""
    print("\n📚 Test: Fichiers contexte...")
    
    files_to_check = [
        ("chatbot_context.md", "Contexte système"),
        ("query_patterns.md", "Patterns requêtes"),
        ("mistral_config.py", "Configuration LLM"),
        ("entity_mapping.py", "Mapping entités"),
        ("llm_formatter.py", "Formatter LLM"),
        ("requirements.txt", "Dépendances"),
    ]
    
    results = []
    for filename, desc in files_to_check:
        try:
            path = Path(filename)
            if path.exists():
                size = path.stat().st_size
                print(f"  ✅ {desc}: {filename} ({size} bytes)")
                results.append(True)
            else:
                print(f"  ❌ {desc}: {filename} NOT FOUND")
                results.append(False)
        except Exception as e:
            print(f"  ❌ {desc}: Erreur {e}")
            results.append(False)
    
    return all(results)

def test_mistral_config():
    """Valider configuration Mistral"""
    print("\n⚙️ Test: mistral_config.py...")
    
    try:
        from .MistralConfig import (
            MISTRAL_CONFIG,
            LLM_PARAMETERS,
            SYSTEM_PROMPT,
            PROMPT_TEMPLATES
        )
        
        # Vérifier config
        assert "model" in MISTRAL_CONFIG, "Model non défini"
        print(f"  ✅ Modèle: {MISTRAL_CONFIG['model']}")
        
        # Vérifier paramètres
        assert "temperature" in LLM_PARAMETERS, "Temperature non définie"
        print(f"  ✅ Temperature: {LLM_PARAMETERS['temperature']}")
        
        # Vérifier system prompt
        assert len(SYSTEM_PROMPT) > 100, "System prompt trop court"
        print(f"  ✅ System prompt: {len(SYSTEM_PROMPT)} chars")
        
        # Vérifier templates
        assert len(PROMPT_TEMPLATES) > 0, "Pas de templates"
        print(f"  ✅ {len(PROMPT_TEMPLATES)} prompt templates")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_entity_mapping():
    """Valider entity_mapping.py"""
    print("\n🏷️ Test: entity_mapping.py...")
    
    try:
        from .EntityMapping import (
            TABLE_ALIASES,
            COLUMN_ALIASES,
            resolve_table_alias,
            resolve_column_alias,
            resolve_metric
        )
        
        # Vérifier aliases
        assert len(TABLE_ALIASES) > 0, "Pas de table aliases"
        print(f"  ✅ {len(TABLE_ALIASES)} tables mappées")
        
        assert len(COLUMN_ALIASES) > 0, "Pas de column aliases"
        print(f"  ✅ {len(COLUMN_ALIASES)} colonnes mappées")
        
        # Test resolvers
        result = resolve_table_alias("donnez moi excavation")
        assert result != "", "Resolver table échoué"
        print(f"  ✅ resolve_table_alias: OK")
        
        result = resolve_column_alias("tonnage")
        assert result != "", "Resolver colonne échoué"
        print(f"  ✅ resolve_column_alias: OK")
        
        result = resolve_metric("efficacité")
        assert result is not None, "Resolver metric échoué"
        print(f"  ✅ resolve_metric: OK")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_streamlit_app():
    """Valider streamlit_app.py syntax"""
    print("\n🎨 Test: streamlit_app.py...")
    
    try:
        # Vérifier syntax
        with open("streamlit_app.py", 'r', encoding='utf-8') as f:
            code = f.read()
            compile(code, "streamlit_app.py", "exec")
        
        print(f"  ✅ Syntax valide ({len(code)} chars)")
        
        # Vérifier imports
        assert "import streamlit" in code, "Import streamlit manquant"
        assert "load_schema" in code, "Function load_schema manquante"
        assert "load_calendar" in code, "Function load_calendar manquante"
        print(f"  ✅ Fonctions principales présentes")
        
        return True
    except SyntaxError as e:
        print(f"  ❌ Erreur syntax: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def test_llm_formatter():
    """Valider llm_formatter.py"""
    print("\n📐 Test: llm_formatter.py...")
    
    try:
        from .LlmFormatter import CatalogFormatter
        
        # Initialiser formatter
        formatter = CatalogFormatter("schema.json")
        
        # Test get_table_summary
        summary = formatter.get_table_summary("Benene_1_Excavation")
        assert "Rôle métier" in summary, "Rôle manquant"
        print(f"  ✅ get_table_summary: OK")
        
        # Test get_all_tables_list
        tables_list = formatter.get_all_tables_list()
        assert len(tables_list) > 0, "Liste vide"
        print(f"  ✅ get_all_tables_list: OK")
        
        # Test get_llm_optimized_json
        optimized = formatter.get_llm_optimized_json()
        assert "tables" in optimized, "Section tables manquante"
        print(f"  ✅ get_llm_optimized_json: OK")
        
        return True
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

# ─────────────────────────────────────────
# MAIN TEST RUNNER
# ─────────────────────────────────────────

def run_all_tests():
    """Exécuter tous les tests"""
    print("=" * 60)
    print("🧪 SUITE DE TESTS - VALIDATION CHATBOT")
    print("=" * 60)
    
    tests = [
        test_schema_json,
        test_relationships,
        test_calendar_csv,
        test_context_files,
        test_mistral_config,
        test_entity_mapping,
        test_streamlit_app,
        test_llm_formatter,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test échoué: {e}")
            results.append(False)
    
    # Résumé
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"📊 RÉSULTATS: {passed}/{total} tests passés")
    
    if passed == total:
        print("✅ TOUS LES TESTS PASSÉS - PRÊT POUR DÉPLOIEMENT")
        return 0
    else:
        print(f"❌ {total - passed} test(s) échoué(s) - VÉRIFIER ERREURS")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
