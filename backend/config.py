import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables from .env file in the backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

class Config:
    # API Keys
    GROQ_API_KEY        = os.getenv("GROQ_API_KEY",        "")
    OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY",  "")
    GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY",      "")

    # ── ON/OFF Toggles (set in .env) ───────────────────────────────────────
    _GROQ_ON        = os.getenv("GROQ",        "OFF").strip().upper() == "ON"
    _OPENROUTER_ON  = os.getenv("OPENROUTER",  "OFF").strip().upper() == "ON"
    _GEMINI_ON      = os.getenv("GEMINI",      "OFF").strip().upper() == "ON"

    # ── Resolve active provider ─────────────────────────────────────────────
    _on_count = sum([_GROQ_ON, _OPENROUTER_ON, _GEMINI_ON])
    if _on_count > 1:
        raise ValueError("❌ More than one provider is ON in .env — only ONE should be ON at a time.")
    elif _GROQ_ON:
        ACTIVE_MODEL_PROVIDER = "groq"
        if not GROQ_API_KEY or "your_" in GROQ_API_KEY:
            raise ValueError("❌ GROQ=ON but GROQ_API_KEY is missing or invalid in .env!")
    elif _OPENROUTER_ON:
        ACTIVE_MODEL_PROVIDER = "openrouter"
        if not OPENROUTER_API_KEY or "your-key" in OPENROUTER_API_KEY:
            raise ValueError("❌ OPENROUTER=ON but OPENROUTER_API_KEY is missing in .env!")
    elif _GEMINI_ON:
        ACTIVE_MODEL_PROVIDER = "gemini"
        if not GEMINI_API_KEY or "your_" in GEMINI_API_KEY:
            raise ValueError("❌ GEMINI=ON but GEMINI_API_KEY is missing or invalid in .env!")
    else:
        raise ValueError(
            "❌ No provider is ON in .env!\n"
            "Set one of:  GROQ=ON  |  OPENROUTER=ON  |  GEMINI=ON"
        )

    # Model names
    GROQ_MODEL        = "llama-3.3-70b-versatile"
    GEMINI_MODEL      = "gemini-2.0-flash"
    # OpenRouter model slug — use :free suffix for free tier (rate-limited)
    OPENROUTER_MODEL  = "nvidia/nemotron-3-ultra-550b-a55b:free"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"



    MAX_TOKENS = 2048
    TEMPERATURE = 0.2


    # RAG Configuration
    # all-MiniLM-L6-v2 — English-only, 80MB (3.5× lighter than multilingual model)
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    TOP_K_RETRIEVAL = 5
    SIMILARITY_THRESHOLD = 0.38
    MAX_HISTORY_LENGTH = 5
    SESSION_TIMEOUT = 3600

    # Dataset Configuration — resolve relative to this file so it works
    # regardless of what directory you run `python app.py` from.
    DATASET_PATH = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "ckpcmcdataset.json")
    )

    # Logging — chat logs are separate from server/startup noise
    LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
    CHAT_LOG_FILE = os.path.join(LOG_DIR, "chat.log")
    SERVER_LOG_FILE = os.path.join(LOG_DIR, "server.log")
    ENABLE_LOGGING = os.getenv("ENABLE_LOGGING", "ON").strip().upper() == "ON"
    CHAT_LOG_MAX_BYTES = 2 * 1024 * 1024      # 2 MB per chat log file
    CHAT_LOG_BACKUP_COUNT = 10                  # ~20 MB total chat history on disk
    SERVER_LOG_MAX_BYTES = 1 * 1024 * 1024    # 1 MB per server log file
    SERVER_LOG_BACKUP_COUNT = 3
    CHAT_LOG_MAX_TEXT_CHARS = 500             # truncate long query/response text in logs

    # Cache Configuration
    ENABLE_CACHE = True
    CACHE_TTL = 300
