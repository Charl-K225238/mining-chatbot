"""
Utility pour LLM - Parser et Formatter les données du catalogue
Rend le schéma facilement interprétable par les agents LLM
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any

class CatalogFormatter:
    """Formatte le catalogue pour optimisation LLM"""
    
    def __init__(self, schema_json_path: str):
        """Charger le schéma JSON"""
        with open(schema_json_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)
    
    def get_table_summary(self, table_key: str) -> str:
        """Résumé concis d'une table pour le LLM"""
        
        files = self.schema.get('files', [])
        for file_info in files:
            if file_info.get('file_key') == table_key:
                table_name = file_info.get('file_name', table_key)
                role = file_info.get('role', 'N/A')
                usage = file_info.get('usage', [])
                
                # Compter colonnes
                sheet_count = 0
                total_columns = 0
                for sheet in file_info.get('sheets', []):
                    sheet_count += 1
                    total_columns += len(sheet.get('columns', []))
                
                summary = f"""
Table: {table_name}
Rôle métier: {role}
Feuilles: {sheet_count}
Colonnes totales: {total_columns}
Utilisations principales: {', '.join(usage) if usage else 'N/A'}
"""
                return summary.strip()
        
        return f"Table {table_key} non trouvée"
    
    def get_all_tables_list(self) -> str:
        """Liste structurée de toutes les tables"""
        output = "## 🗂️ CATALOGUE TABLES\n\n"
        
        domains = self.schema.get('domain_model', {})
        
        for domain, table_keys in domains.items():
            output += f"### {domain}\n"
            for key in table_keys:
                output += f"- `{key}`\n"
            output += "\n"
        
        return output
    
    def get_join_graph(self) -> str:
        """Graphe de relations pour le LLM"""
        from relationships import RELATIONSHIPS
        
        output = "## 🔗 RELATIONS TABLE\n\n"
        
        for source_table, targets in RELATIONSHIPS.items():
            if targets:
                output += f"**{source_table}** →\n"
                for target_info in targets:
                    target_table = target_info.get('table')
                    join_keys = target_info.get('join_on', [])
                    output += f"  - {target_table} (clé: {', '.join(join_keys)})\n"
            output += "\n"
        
        return output
    
    def get_column_reference(self, table_key: str) -> str:
        """Référence complète colonnes d'une table"""
        
        files = self.schema.get('files', [])
        
        for file_info in files:
            if file_info.get('file_key') == table_key:
                output = f"## Colonnes {file_info.get('file_name')}\n\n"
                
                for sheet in file_info.get('sheets', []):
                    output += f"### Feuille: {sheet.get('name')}\n"
                    output += f"Dimensions: {sheet.get('rows')} × {sheet.get('columns_count')}\n\n"
                    
                    output += "| Colonne | Type | Manques | État |\n"
                    output += "|---------|------|---------|------|\n"
                    
                    for col in sheet.get('columns', []):
                        col_name = col.get('name')
                        col_type = col.get('type', 'N/A')
                        missing_pct = col.get('missing_pct', 0)
                        missing_level = col.get('missing_level', 'N/A')
                        
                        output += f"| {col_name} | {col_type} | {missing_pct:.1f}% | {missing_level} |\n"
                    
                    output += "\n"
                    
                    issues = sheet.get('issues', [])
                    if issues:
                        output += "**Problèmes détectés:**\n"
                        for issue in issues:
                            output += f"- {issue}\n"
                        output += "\n"
                
                return output
        
        return f"Table {table_key} non trouvée"
    
    def get_llm_optimized_json(self) -> Dict[str, Any]:
        """JSON optimisé pour LLM - simplifié et structuré"""
        
        optimized = {
            "catalog_meta": {
                "title": self.schema['catalog']['title'],
                "version": self.schema['catalog']['version'],
            },
            "domains": {},
            "tables": {},
            "relationships": {},
        }
        
        # Domaines
        for domain, tables in self.schema.get('domain_model', {}).items():
            optimized["domains"][domain] = {
                "table_count": len(tables),
                "tables": tables
            }
        
        # Tables résumées
        files = self.schema.get('files', [])
        for file_info in files:
            key = file_info.get('file_key', '')
            optimized["tables"][key] = {
                "name": file_info.get('file_name'),
                "role": file_info.get('role'),
                "column_count": sum(
                    len(sheet.get('columns', []))
                    for sheet in file_info.get('sheets', [])
                ),
                "has_dates": file_info.get('sheets', [{}])[0].get('has_date_columns', False),
            }
        
        # Relations
        from relationships import RELATIONSHIPS
        for source, targets in RELATIONSHIPS.items():
            optimized["relationships"][source] = [
                {"to": t.get('table'), "via": t.get('join_on')}
                for t in targets
            ]
        
        # Calendrier
        optimized["calendar"] = {
            "columns": self.schema.get('calendar_table', {}).get('columns', []),
            "description": "Dimension temporelle - Clé pour toutes analyses temps"
        }
        
        return optimized
    
    def export_llm_context(self, output_file: str = None):
        """Exporter contexte optimal pour LLM"""
        
        context = {
            "version": "1.0",
            "last_updated": "2024",
            
            "system_info": {
                "model_type": "Star Schema",
                "central_table": "Calendrier",
                "period_covered": "2023-2026",
                "total_files": len(self.schema.get('files', [])),
                "total_domains": len(self.schema.get('domain_model', {})),
            },
            
            "quick_reference": {
                "production_table": "Benene_1_Excavation",
                "carburant_table": "CARBURANT",
                "budget_table": "Budget",
                "actions_table": "PLAN D'ACTIONS DU PGES",
                "calendar_table": "Calendrier",
                "equipment_reference": "Benene_0_Liste_engins",
                "personnel_reference": "Benene_0_Personnel",
            },
            
            "key_joins": {
                "Excavation_to_Carburant": {
                    "tables": ["Benene_1_Excavation", "CARBURANT"],
                    "join_keys": ["Equipement", "Date"]
                },
                "Any_to_Calendar": {
                    "temporal_key": "Date",
                    "alternative_keys": ["Année", "Mois", "Trimestre"]
                },
                "Budget_to_Period": {
                    "tables": ["Budget", "Calendrier"],
                    "join_keys": ["Année", "Mois"]
                },
            },
            
            "common_metrics": {
                "efficiency": "SUM(Tonnage) / SUM(Carburant_L)",
                "performance": "Réalisé / Objectif * 100",
                "delay_days": "DATEDIFF(TODAY(), Échéance)",
            },
            
            "data_quality": self.schema.get('quality_summary', []),
        }
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(context, f, indent=2, ensure_ascii=False)
            print(f"Contexte LLM exporté: {output_file}")
        
        return context

if __name__ == "__main__":
    # Usage
    formatter = CatalogFormatter("schema.json")
    
    # Afficher résumé table
    print(formatter.get_table_summary("Benene_1_Excavation"))
    
    # Exporter pour LLM
    formatter.export_llm_context("llm_context.json")
