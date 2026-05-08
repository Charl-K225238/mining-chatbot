"""
Ollama Local Integration - Mistral 7B via Ollama
Alternative locale à Mistral Cloud API
"""

import os
import json
from typing import Dict, Any, List
from pathlib import Path

try:
    import ollama
except ImportError:
    print("⚠️ Ollama not installed. Run: pip install ollama")
    ollama = None

# Configuration Local Ollama
LOCAL_OLLAMA_CONFIG = {
    "model": "mistral",              # Model name dans Ollama
    "base_url": "http://localhost:11434",  # Default Ollama URL
    "temperature": 0.3,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 1500,             # Equivalent max_tokens
    "timeout": 60,
}

# System Prompt pour local model
LOCAL_SYSTEM_PROMPT = """Tu es un assistant IA spécialisé dans l'interrogation d'un catalogue de données minières.

## INSTRUCTIONS

### Tables Clés
- Benene_1_Excavation (Date, Equipement, Tonnage)
- CARBURANT (Equipement, Quantité Servie L)
- Budget (Année, Mois, Objectif)
- Calendrier (Date, Année, Mois, Jour, Trimestre, Saison)

### Jointures Principales
- Toute table + Calendrier via Date
- Excavation + Carburant via Equipement + Date

### Répondre Structuré
1. Question confirmée
2. Tables utilisées
3. Résultat chiffré
4. Limitations

### Alertes
- ⚠️ Doublons possibles
- ⚠️ Période: 2023-2026
- ✅ Toujours vérifier Calendrier pour dates
"""

# ─────────────────────────────────────────
# OLLAMA LOCAL CHATBOT
# ─────────────────────────────────────────

class OllamaLocalChatbot:
    """Chatbot avec Ollama Mistral 7B local"""
    
    def __init__(self, verbose: bool = False):
        """
        Initialiser chatbot Ollama local
        
        Args:
            verbose: Afficher détails debug
        """
        self.model = LOCAL_OLLAMA_CONFIG["model"]
        self.base_url = LOCAL_OLLAMA_CONFIG["base_url"]
        self.verbose = verbose
        self.conversation_history = []
        
        if ollama is None:
            raise ImportError("Ollama client not installed. Run: pip install ollama")
        
        # Vérifier connexion Ollama
        self._check_connection()
    
    def _check_connection(self):
        """Vérifier que Ollama service est accessible"""
        try:
            # Test simple query
            response = ollama.generate(
                model=self.model,
                prompt="test",
                stream=False,
            )
            print(f"✅ Ollama connecté: model={self.model}")
            
        except Exception as e:
            print(f"❌ Impossible connecter Ollama: {e}")
            print("💡 Démarrer Ollama: ollama serve")
            raise
    
    def _load_context(self) -> str:
        """Charger contexte système"""
        
        context_parts = [LOCAL_SYSTEM_PROMPT]
        
        # Charger schema.json si disponible
        try:
            schema_path = Path("schema.json")
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                
                # Ajouter aperçu domaines
                domains = schema.get('domain_model', {})
                context_parts.append("\n## DOMAINS\n")
                for domain in domains.keys():
                    context_parts.append(f"- {domain}")
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Erreur chargement schema: {e}")
        
        return "\n".join(context_parts)
    
    def query(self, user_query: str, use_history: bool = True) -> Dict[str, Any]:
        """
        Traiter une requête utilisateur via Ollama local
        
        Args:
            user_query: Question en langage naturel
            use_history: Inclure historique conversation
        
        Returns:
            Dict avec réponse et métadonnées
        """
        
        if self.verbose:
            print(f"\n📝 Query: {user_query}")
            print(f"Model: {self.model}")
        
        try:
            # Construire prompt
            context = self._load_context()
            
            if use_history and len(self.conversation_history) > 0:
                # Inclure contexte conversation
                history_text = "\n".join([
                    f"Q: {h['query']}\nA: {h['response'][:200]}..."
                    for h in self.conversation_history[-3:]  # Derniers 3 échanges
                ])
                prompt = f"{context}\n\n## CONVERSATION HISTORY\n{history_text}\n\n## NEW QUERY\n{user_query}"
            else:
                prompt = f"{context}\n\n## USER QUERY\n{user_query}"
            
            if self.verbose:
                print(f"Prompt length: {len(prompt)} chars")
            
            # Appeler Ollama
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                temperature=LOCAL_OLLAMA_CONFIG["temperature"],
                top_p=LOCAL_OLLAMA_CONFIG["top_p"],
                top_k=LOCAL_OLLAMA_CONFIG["top_k"],
                num_predict=LOCAL_OLLAMA_CONFIG["num_predict"],
                stream=False,
            )
            
            answer = response.get("response", "")
            
            # Résultat
            result = {
                "status": "success",
                "user_query": user_query,
                "response": answer,
                "model": self.model,
                "local": True,
                "context_used": "schema.json + relationships.py",
            }
            
            # Ajouter historique
            self.conversation_history.append({
                "query": user_query,
                "response": answer,
            })
            
            if self.verbose:
                print(f"✅ Response: {len(answer)} chars")
            
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "user_query": user_query,
                "error": str(e),
                "model": self.model,
                "local": True,
            }
            
            if self.verbose:
                print(f"❌ Error: {e}")
            
            return error_result
    
    def stream_query(self, user_query: str):
        """
        Traiter requête avec streaming (réponse en temps réel)
        
        Args:
            user_query: Question en langage naturel
        
        Yields:
            Chunks de réponse
        """
        
        try:
            context = self._load_context()
            prompt = f"{context}\n\n## USER QUERY\n{user_query}"
            
            # Streaming response
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                temperature=LOCAL_OLLAMA_CONFIG["temperature"],
                stream=True,
            )
            
            full_response = ""
            for chunk in response:
                chunk_text = chunk.get("response", "")
                full_response += chunk_text
                yield chunk_text
            
            # Ajouter historique
            self.conversation_history.append({
                "query": user_query,
                "response": full_response,
            })
            
        except Exception as e:
            yield f"❌ Error: {e}"
    
    def get_history(self) -> List[Dict]:
        """Retourner historique conversation"""
        return self.conversation_history
    
    def clear_history(self):
        """Effacer historique"""
        self.conversation_history = []
    
    def list_available_models(self) -> List[str]:
        """Lister modèles disponibles localement"""
        try:
            response = ollama.list()
            return [model.get("name", "") for model in response.get("models", [])]
        except Exception as e:
            print(f"❌ Erreur listing modèles: {e}")
            return []

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def is_ollama_available() -> bool:
    """Vérifier si Ollama service est disponible"""
    try:
        ollama.list()
        return True
    except Exception:
        return False

def get_available_models() -> List[str]:
    """Récupérer liste modèles disponibles"""
    try:
        response = ollama.list()
        return [model.get("name", "") for model in response.get("models", [])]
    except Exception:
        return []

def is_mistral_available() -> bool:
    """Vérifier si Mistral 7B est téléchargé"""
    available = get_available_models()
    return any("mistral" in model.lower() for model in available)

# ─────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────

def example_usage():
    """Exemple utilisation Ollama local"""
    
    print("\n" + "="*60)
    print("🤖 OLLAMA LOCAL MISTRAL 7B - EXAMPLE")
    print("="*60)
    
    # Vérifier Ollama
    if not is_ollama_available():
        print("❌ Ollama service n'est pas running")
        print("💡 Démarrer: ollama serve")
        return
    
    print("✅ Ollama service détecté")
    
    # Lister modèles
    models = get_available_models()
    print(f"📦 Modèles disponibles: {models}")
    
    if not is_mistral_available():
        print("❌ Mistral 7B n'est pas téléchargé")
        print("💡 Télécharger: ollama pull mistral")
        return
    
    print("✅ Mistral 7B disponible")
    
    # Initialiser chatbot
    try:
        chatbot = OllamaLocalChatbot(verbose=True)
    except Exception as e:
        print(f"❌ Erreur initialisation: {e}")
        return
    
    # Test queries
    test_queries = [
        "Bonjour! Comment tu t'appelles?",
        "Quels sont les domaines métier du catalogue?",
    ]
    
    for query in test_queries:
        print(f"\n📝 Q: {query}")
        result = chatbot.query(query)
        
        if result["status"] == "success":
            print(f"✅ A: {result['response'][:300]}...")
        else:
            print(f"❌ Error: {result.get('error')}")
    
    # Afficher historique
    print(f"\n📋 Conversation History:")
    for i, entry in enumerate(chatbot.get_history(), 1):
        print(f"  {i}. Q: {entry['query'][:50]}...")

if __name__ == "__main__":
    example_usage()
