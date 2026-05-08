"""
RAG Engine for Mining Data Chatbot (Miny).

Optimized retrieval-augmented generation with intelligent table targeting,
caching, and compression for faster responses.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import json
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from DataDictionary import DataDictionary
from EntityMapping import EntityMapper
from FileProcessor import FileProcessor
from abbreviations import normalize_abbreviations, get_relevant_tables

logger = logging.getLogger(__name__)

# Configuration constants
MAX_SNIPPETS_PER_TABLE: int = 2  # Reduced from 3 for faster processing
MAX_TOTAL_SNIPPETS: int = 5
MIN_SNIPPET_LENGTH: int = 20
CONTEXT_COMPRESSION_RATIO: float = 0.7  # Keep 70% of context

# Mapping des noms courts pour les tables minières
TABLE_SHORT_NAMES = {
    "benene_0_chargeuses": "Chargeuses Q0",
    "benene_0_liste_engins": "Engins Q0",
    "benene_0_objectifs": "Objectifs Q0",
    "benene_0_personnel": "Personnel Q0",
    "benene_0_stocks": "Stocks Q0",
    "benene_0_valeurs_initiales": "Valeurs Initiales Q0",
    "benene_0_zone_excavation": "Zone Excavation Q0",
    "benene_1_excavation": "Excavation Q1",
    "benene_1_journal": "Journal Q1",
    "benene_1_shifts_horaires": "Shifts Horaires Q1",
    "benene_1_shifts_personnel": "Shifts Personnel Q1",
    "benene_2_qualite_echantillons": "Qualité Échantillons Q2",
    "benene_2_qualite_navires": "Qualité Navires Q2",
    "benene_3_regul_qté_stock": "Régul Quantité Stock Q3",
    "benene_3_regul_qualité_stock": "Régul Qualité Stock Q3",
    "budget": "Budget",
    "carburant": "Carburant",
    "descente_minerai": "Descente Minerai",
    "plan_actions_pges": "Plan Actions PGES",
    "productivite_port": "Productivité Port",
    "suivi_actions": "Suivi Actions",
    "transport_minerai_paa": "Transport Minerai PAA",
}

class RAGEngine:
    """Retrieval-Augmented Generation Engine."""

    def __init__(self, file_processor: FileProcessor = None):
        self.data_dict = DataDictionary()
        self.entity_mapper = EntityMapper()
        self.file_processor = file_processor or FileProcessor()
        logger.info("RAG Engine initialized")

    def retrieve_context(self, query: str) -> Dict[str, Any]:
        """Retrieve relevant context efficiently.
        
        Uses intelligent table targeting to fetch only necessary data,
        avoiding unnecessary file reads for better performance.
        
        Args:
            query: User query string
            
        Returns:
            Dict with entities, tables, snippets, and metadata
        """
        try:
            # Normalize abbreviations (T1 -> Q1, etc.)
            normalized_query, _ = normalize_abbreviations(query)
            
            # Extract entities from normalized query
            entities = self.entity_mapper.extract_entities(normalized_query)
            
            # Intelligently identify which tables are relevant
            relevant_tables = get_relevant_tables(normalized_query)
            
            context: Dict[str, Any] = {
                "entities": entities,
                "related_tables": [],
                "data_snippets": [],
                "table_metadata": [],
                "normalized_query": normalized_query
            }

            # Get related data only from relevant tables
            for entity in entities:
                related = self.entity_mapper.get_related_data(entity)
                context["related_tables"].extend(related.get("tables", []))
                context["data_snippets"].extend(related.get("snippets", []))

            # Fetch file context (optimized for relevant tables only)
            file_context, file_metadata = self._get_file_context(normalized_query, relevant_tables)
            context["data_snippets"].extend(file_context)
            context["table_metadata"].extend(file_metadata)

            logger.info(f"Query processed: {len(context['related_tables'])} tables, {len(context['data_snippets'])} snippets")
            return context

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return {"entities": [], "related_tables": [], "data_snippets": [], "table_metadata": [], "normalized_query": ""}

    def _get_file_context(self, query: str, relevant_tables: Optional[List[str]] = None) -> Tuple[List[str], List[Dict[str, str]]]:
        """Extract relevant snippets from targeted files only.
        
        Intelligently filters files to read based on query keywords,
        avoiding unnecessary file I/O for better performance.
        
        Args:
            query: Normalized user query
            relevant_tables: Pre-identified relevant table categories
            
        Returns:
            Tuple of (snippets, metadata)
        """
        snippets: List[str] = []
        metadata: List[Dict[str, str]] = []
        query_lower = query.lower()
        relevant_tables = relevant_tables or []
        
        # Get only JSON files
        clean_files = self.file_processor.list_clean_files()
        
        for sub_dir, files in clean_files.items():
            for filename in files:
                if not filename.endswith('_processed.json'):
                    continue
                
                # Skip if not in relevant tables (optimization)
                table_key = filename.replace('_processed.json', '').lower()
                if relevant_tables and not any(table in table_key for table in relevant_tables):
                    logger.debug(f"Skipping irrelevant table: {table_key}")
                    continue
                    
                file_path = self.file_processor.clean_dir / sub_dir / filename
                try:
                    file_stat = file_path.stat()
                    mod_date = datetime.fromtimestamp(file_stat.st_mtime).strftime('%d/%m/%Y %H:%M')
                    short_name = TABLE_SHORT_NAMES.get(table_key, table_key)
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        processed = json.load(f)
                        content = processed.get("content", "")
                        
                        # Keyword matching
                        if any(keyword in content.lower() for keyword in query_lower.split()):
                            # Extract and compress snippets
                            sentences = content.split('.')
                            relevant = [
                                s.strip() for s in sentences 
                                if s.strip() and len(s.strip()) >= MIN_SNIPPET_LENGTH
                                and any(kw in s.lower() for kw in query_lower.split())
                            ]
                            snippets.extend(relevant[:MAX_SNIPPETS_PER_TABLE])
                            
                            # Add metadata (avoid duplicates)
                            meta_entry = {"name": short_name, "date": mod_date}
                            if meta_entry not in metadata:
                                metadata.append(meta_entry)
                                
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed JSON: {filename}")
                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")

        return snippets[:MAX_TOTAL_SNIPPETS], metadata

    def augment_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Augment query with context (compressed format).
        
        Minimizes prompt size for faster LLM processing while preserving
        essential information.
        
        Args:
            query: Original user query
            context: Retrieved context dict
            
        Returns:
            Compressed augmented prompt string
        """
        if not context.get("data_snippets") and not context.get("related_tables"):
            return query

        # Use compressed format
        parts = []
        
        if context.get("related_tables"):
            parts.append(f"📊 Tables: {', '.join(context['related_tables'])}")
        
        if context.get("data_snippets"):
            parts.append("💡 Context:")
            for snippet in context["data_snippets"][:MAX_TOTAL_SNIPPETS]:
                # Compress snippet further if needed
                compressed = self._compress_text(snippet)
                parts.append(f"• {compressed}")
        
        parts.append(f"\nQ: {query}")
        return "\n".join(parts)
    
    @staticmethod
    def _compress_text(text: str, max_length: int = 150) -> str:
        """Compress text to max length, keeping key information.
        
        Args:
            text: Text to compress
            max_length: Maximum output length
            
        Returns:
            Compressed text
        """
        if len(text) <= max_length:
            return text
        # Truncate and add ellipsis
        return text[:max_length-3] + "..."

    def process_query(self, query: str) -> Tuple[str, List[Dict[str, str]], str]:
        """Process query with RAG augmentation and abbreviation normalization.
        
        Args:
            query: User query string
            
        Returns:
            Tuple of (augmented_prompt, table_metadata, normalized_query)
        """
        context = self.retrieve_context(query)
        augmented = self.augment_prompt(query, context)
        normalized = context.get("normalized_query", query)
        return augmented, context.get("table_metadata", []), normalized