"""
Abbreviations handler for common mining data terms.

Translates common abbreviations like T1, T2, T3, T4 to Q1, Q2, Q3, Q4
and handles confirmations when ambiguous.
"""

from typing import Tuple, Optional

# Abbreviations mapping
ABBREVIATIONS_MAP: dict[str, str] = {
    "t1": "Q1",
    "t2": "Q2", 
    "t3": "Q3",
    "t4": "Q4",
    "q1": "Q1",
    "q2": "Q2",
    "q3": "Q3",
    "q4": "Q4",
    "t1 2024": "Q1 2024",
    "t2 2024": "Q2 2024",
    "t3 2024": "Q3 2024",
    "t4 2024": "Q4 2024",
    "t1 2023": "Q1 2023",
    "t2 2023": "Q2 2023",
    "t3 2023": "Q3 2023",
    "t4 2023": "Q4 2023",
    "premier trimestre": "Q1",
    "deuxième trimestre": "Q2",
    "troisième trimestre": "Q3",
    "quatrième trimestre": "Q4",
    "1er trim": "Q1",
    "2e trim": "Q2",
    "3e trim": "Q3",
    "4e trim": "Q4",
}

# Table-specific aliases
TABLE_ALIASES: dict[str, list[str]] = {
    "excavation": ["extraction", "creusement", "excavation", "tonnage"],
    "carburant": ["carburant", "essence", "fuel", "consommation", "energie", "efficacite"],
    "qualite": ["qualite", "echantillon", "navire", "controle"],
    "personnel": ["personnel", "employe", "shift", "horaire", "equipe"],
    "budget": ["budget", "cout", "depense", "finance"],
    "transport": ["transport", "minerai", "logistique", "descente"],
    "productivite": ["productivite", "rendement", "output", "performance"],
}

def normalize_abbreviations(query: str) -> Tuple[str, bool]:
    """
    Normalize abbreviations in query to standard format.
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (normalized_query, is_confirmed) where is_confirmed indicates
        if the normalization was certain (not ambiguous)
    """
    normalized = query.lower()
    was_modified = False
    
    # Replace abbreviations
    for abbr, replacement in ABBREVIATIONS_MAP.items():
        if abbr in normalized:
            normalized = normalized.replace(abbr, replacement)
            was_modified = True
    
    return normalized, was_modified

def confirm_abbreviation(original_query: str, normalized_query: str) -> str:
    """
    Generate confirmation message if abbreviations were normalized.
    
    Args:
        original_query: Original query
        normalized_query: Normalized query
        
    Returns:
        Confirmation message or empty string
    """
    if original_query.lower() != normalized_query.lower():
        return f"📝 J'ai interprete votre question comme: \"{normalized_query}\". C'est correct? (Vous aviez demande: \"{original_query}\")"
    return ""

def get_relevant_tables(query: str) -> list[str]:
    """
    Identify relevant tables based on query keywords.
    
    Args:
        query: User query string
        
    Returns:
        List of relevant table names
    """
    query_lower = query.lower()
    relevant = []
    
    for table, keywords in TABLE_ALIASES.items():
        for keyword in keywords:
            if keyword in query_lower:
                relevant.append(table)
                break  # Found this table, move to next
    
    return list(set(relevant))  # Remove duplicates
