"""Prompts for Miny - Optimized Mining Data Chatbot.

Compressed system prompts for faster LLM processing and lower latency.
"""

from typing import Optional

# Optimized system prompt for Miny (compressed for speed)
SYSTEM_PROMPT: str = """🤖 Miny - Assistant IA Minieres

REPONSES EN FRANCAIS TOUJOURS:
✓ Francais uniquement, clair, rapide
✓ Comprends abreviations: T1/T2/T3/T4 = Q1/Q2/Q3/Q4
✓ 1er/2e/3e/4e trim = Q1/Q2/Q3/Q4

DATA CLES:
Excavation | Carburant | Qualite | Personnel | Budget | Transport | PGES

INSTRUCTIONS:
1. Reponses courtes et directes
2. Utilise context fourni
3. Si info manque, dis-le
4. Comparaisons sur demande
5. KPI rapid: tonnage, couts, efficacite

EXEMPLES:
Q: "T1 tonnage 2024?"
R: "Q1 2024: X tonnes. Q1 2023: Y tonnes (+Z%)"

Precis, rapide, francais! 🇫🇷
"""


def get_system_prompt() -> str:
    """Get optimized system prompt for Miny.
    
    Returns:
        Compressed system prompt string
    """
    return SYSTEM_PROMPT


def get_compressed_prompt(context: str, query: str) -> str:
    """Get compressed mining data prompt.
    
    Args:
        context: Relevant data context
        query: User query string
        
    Returns:
        Compressed augmented prompt
    """
    return f"📊 {context}\n\nQ: {query}"


def get_error_prompt() -> str:
    """Get error handling message.
    
    Returns:
        Concise error message
    """
    return "⚠️ Erreur. Reformulez ou contactez support."
