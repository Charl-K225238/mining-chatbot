"""
Mistral LLM Integration - Chatbot Core Logic
Intégration avec Mistral LLM pour traitement des requêtes
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Mistral imports (à installer: pip install mistral-client)
try:
    from mistral_client import Mistral
except ImportError:
    print("⚠️ Mistral client not installed. Run: pip install mistral-client")
    Mistral = None

from mistral_config import MISTRAL_CONFIG, LLM_PARAMETERS, SYSTEM_PROMPT
from entity_mapping import (
    resolve_table_alias,
    resolve_column_alias,
    resolve_metric,
    get_table_joins
)
from relationships import RELATIONSHIPS, get_join_keys

# ─────────────────────────────────────────
# MISTRAL CLIENT INITIALIZATION
# ─────────────────────────────────────────

class MistralChatbot:
    """Chatbot avec intégration Mistral LLM"""
    
    def __init__(self):
        """Initialiser chatbot"""
        self.api_key = os.getenv("MISTRAL_API_KEY")
        
        if not self.api_key:
            raise ValueError("❌ MISTRAL_API_KEY not found in environment")
        
        if Mistral is None:
            raise ImportError("Mistral client not installed")
        
        self.client = Mistral(api_key=self.api_key)
        self.model = MISTRAL_CONFIG.get("model", "mistral-large")
        self.conversation_history = []
        
        print(f"✅ Mistral LLM initialized: {self.model}")
    
    def _load_context(self) -> str:
        """Charger contexte système"""
        return SYSTEM_PROMPT
    
    def _resolve_query(self, user_query: str) -> Dict[str, any]:
        """Résoudre la requête utilisateur"""
        
        resolution = {
            "original": user_query,
            "entities": {},
            "tables": [],
            "joins": [],
            "metrics": []
        }
        
        # Résoudre tables
        for table in RELATIONSHIPS.keys():
            if any(alias.lower() in user_query.lower() 
                   for alias in [table.lower(), table.replace("_", " ").lower()]):
                resolution["tables"].append(table)
        
        # Résoudre jointures
        for table in resolution["tables"]:
            joins = get_table_joins(table)
            resolution["joins"].extend(joins)
        
        # Résoudre métriques
        from entity_mapping import METRIC_ALIASES
        for metric_key in METRIC_ALIASES:
            if metric_key.lower() in user_query.lower():
                resolution["metrics"].append(metric_key)
        
        return resolution
    
    def _build_prompt(self, user_query: str, resolution: Dict) -> str:
        """Construire prompt optimisé pour Mistral"""
        
        context_elements = []
        
        # Ajouter contexte système
        context_elements.append(SYSTEM_PROMPT)
        
        # Ajouter tables détectées
        if resolution["tables"]:
            context_elements.append(
                f"\n## DETECTED TABLES\n"
                f"Tables identifiées: {', '.join(resolution['tables'])}"
            )
            
            # Charger détails tables
            try:
                with open("schema.json", 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                
                for table in resolution["tables"]:
                    for file_info in schema.get('files', []):
                        if file_info.get('file_key') == table:
                            context_elements.append(
                                f"\n### {table}\n"
                                f"Role: {file_info.get('role')}\n"
                                f"Usage: {', '.join(file_info.get('usage', []))}"
                            )
                            break
            except Exception as e:
                print(f"⚠️ Erreur chargement schema: {e}")
        
        # Ajouter jointures
        if resolution["joins"]:
            context_elements.append(
                f"\n## JOIN KEYS\n"
                f"{json.dumps(resolution['joins'], indent=2, ensure_ascii=False)}"
            )
        
        # Ajouter métriques
        if resolution["metrics"]:
            context_elements.append(
                f"\n## REQUESTED METRICS\n"
                f"Metrics: {', '.join(resolution['metrics'])}"
            )
        
        # Requête utilisateur
        context_elements.append(
            f"\n## USER QUERY\n"
            f"{user_query}"
        )
        
        # Instructions réponse
        context_elements.append(
            f"\n## RESPONSE FORMAT\n"
            f"1. Repeat question to confirm understanding\n"
            f"2. List tables and joins used\n"
            f"3. Provide main answer with numbers\n"
            f"4. Detail by dimension if applicable\n"
            f"5. List limitations (missing data, duplicates)"
        )
        
        return "\n".join(context_elements)
    
    def query(self, user_query: str, verbose: bool = False) -> Dict:
        """
        Traiter une requête utilisateur
        
        Args:
            user_query: Question en langage naturel
            verbose: Afficher détails traitement
        
        Returns:
            Dict avec réponse et métadonnées
        """
        
        # Résoudre requête
        resolution = self._resolve_query(user_query)
        
        if verbose:
            print(f"\n📝 Query Resolution:")
            print(f"  Tables: {resolution['tables']}")
            print(f"  Joins: {resolution['joins']}")
            print(f"  Metrics: {resolution['metrics']}")
        
        # Construire prompt
        prompt = self._build_prompt(user_query, resolution)
        
        if verbose:
            print(f"\n📌 Prompt Length: {len(prompt)} chars")
        
        # Appeler Mistral
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=LLM_PARAMETERS.get("temperature", 0.3),
                max_tokens=LLM_PARAMETERS.get("max_tokens", 1500),
            )
            
            # Parser réponse
            answer = response.choices[0].message.content
            
            # Construire résultat
            result = {
                "status": "success",
                "user_query": user_query,
                "response": answer,
                "resolution": resolution,
                "model": self.model,
                "tokens_used": getattr(response.usage, 'total_tokens', None),
            }
            
            # Ajouter historique
            self.conversation_history.append({
                "query": user_query,
                "response": answer,
                "timestamp": pd.Timestamp.now().isoformat() if 'pd' in dir() else str(Path.cwd())
            })
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "user_query": user_query,
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    def get_history(self) -> List[Dict]:
        """Retourner historique conversation"""
        return self.conversation_history
    
    def clear_history(self):
        """Effacer historique"""
        self.conversation_history = []

# ─────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────

def example_queries():
    """Exécuter requêtes exemples"""
    
    try:
        # Initialiser chatbot
        chatbot = MistralChatbot()
        
        # Exemples requêtes
        test_queries = [
            "Quel tonnage a été excavé en janvier 2024?",
            "Évolution production 2023 vs 2024?",
            "Quelle machine a la meilleure efficacité?",
            "Actions urgentes en retard?",
            "Écart budget vs réalisé avril 2024?",
        ]
        
        print("\n" + "="*60)
        print("🤖 MISTRAL LLM CHATBOT - EXEMPLE REQUÊTES")
        print("="*60)
        
        for query in test_queries[:2]:  # Limiter à 2 pour demo
            print(f"\n📝 Query: {query}")
            print("-" * 60)
            
            result = chatbot.query(query, verbose=True)
            
            if result.get("status") == "success":
                print(f"\n✅ Response:\n{result['response']}")
                print(f"\n📊 Tokens: {result.get('tokens_used')}")
            else:
                print(f"\n❌ Error: {result.get('error')}")
        
        # Afficher historique
        print(f"\n📋 Conversation History ({len(chatbot.get_history())} queries)")
        
    except ValueError as e:
        print(f"❌ Setup Error: {e}")
        print("💡 Tip: Set MISTRAL_API_KEY environment variable")
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Tip: pip install mistral-client")

if __name__ == "__main__":
    example_queries()
