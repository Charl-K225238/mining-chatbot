"""Prompts for Miny - Optimized Mining Data Chatbot.

Compressed system prompts for faster LLM processing.
"""

from typing import Optional

# Optimized system prompt for Miny
SYSTEM_PROMPT = """Miny - Assistant IA Minieres (OPTIMISE)

REPONSES EN FRANCAIS:
- Francais uniquement, clair et rapide
- Comprend abreviations: T1/T2/T3/T4 = Q1/Q2/Q3/Q4
- 1er/2e/3e/4e trimestre = Q1/Q2/Q3/Q4

DATA CLES:
Excavation Q1/Q2/Q3 | Carburant | Budget | Qualite | Personnel | Transport | PGES

INSTRUCTIONS:
1. Reponses courtes et directes
2. Utilise le context fourni
3. Si info manque, dis-le clairement
4. Fait des comparaisons si demande
5. KPI rapides: tonnage, couts, efficacite

EXEMPLES:
Q: "T1 tonnage 2024?"
R: "Q1 2024: X tonnes. Q1 2023: Y tonnes (+Z%)"

Precis, rapide, francais!"""


def get_system_prompt() -> str:
    """Get the system prompt for Miny."""
    return SYSTEM_PROMPT


def get_compressed_prompt(context: str, query: str) -> str:
    """Get a compressed augmented prompt for faster processing.
    
    Args:
        context: Retrieved context from RAG engine
        query: User query
        
    Returns:
        Compressed augmented prompt
    """
    return f"""CONTEXT:
{context}

QUERY: {query}

REPONSE:"""


def get_error_prompt() -> str:
    """Get error response prompt."""
    return "Desole, je ne peux pas repondre. Info insuffisante ou erreur."