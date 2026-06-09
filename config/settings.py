"""Constantes globales de Miny."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
DATA_DIR     = PROJECT_ROOT / "data"
ASSETS_DIR   = PROJECT_ROOT / "assets"
PARQUET_DIR  = DATA_DIR / "parquet"

# ── Ollama ─────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL  = "http://localhost:11434"
PRIMARY_MODEL    = "qwen2.5:3b"
FALLBACK_MODEL   = "phi3:mini"

# Chemins potentiels vers ollama.exe (Windows)
OLLAMA_EXE_PATHS: list[str] = [
    r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe",
    r"%PROGRAMFILES%\Ollama\ollama.exe",
    r"%PROGRAMFILES(X86)%\Ollama\ollama.exe",
]

# ── Engins ─────────────────────────────────────────────────────────────────
ENGIN_DEFAUT = "TRENCHER TRS N°296"

# ── Groq Cloud ─────────────────────────────────────────────────────────────
GROQ_PRIMARY_MODEL  = "llama-3.1-8b-instant"   # rapide, gratuit
GROQ_FALLBACK_MODEL = "gemma2-9b-it"            # backup si quota dépassé

# ── Paramètres LLM (défauts) ───────────────────────────────────────────────
NUM_CTX_DEFAULT       = 2048   # recommandé pour 8 Go RAM
NUM_CTX_MAX           = 8192
TEMPERATURE_DEFAULT   = 0.1
RAM_LIMITE_GO         = 8
