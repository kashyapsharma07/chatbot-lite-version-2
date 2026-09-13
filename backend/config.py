import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load environment variables from .env file in the backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


class Config:
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Gemini is the primary LLM and Groq is its fallback.
    _GROQ_ON = os.getenv("GROQ", "OFF").strip().upper() == "ON"
    _GEMINI_ON = os.getenv("GEMINI", "OFF").strip().upper() == "ON"

    GEMINI_ENABLED = _GEMINI_ON and bool(GEMINI_API_KEY)
    GROQ_ENABLED = _GROQ_ON and bool(GROQ_API_KEY)

    # The existing RAG retrieval code uses OpenRouter for embeddings.
    OPENROUTER_EMBEDDINGS_ENABLED = bool(OPENROUTER_API_KEY)

    if not GEMINI_ENABLED:
        raise ValueError(
            "❌ Gemini is the primary LLM. Set GEMINI=ON and provide GEMINI_API_KEY."
        )

    if not GROQ_ENABLED:
        raise ValueError(
            "❌ Groq is the fallback LLM. Set GROQ=ON and provide GROQ_API_KEY."
        )

    if not OPENROUTER_EMBEDDINGS_ENABLED:
        raise ValueError(
            "❌ OPENROUTER_API_KEY is required by the current RAG embedding pipeline."
        )

    # Model names
    GEMINI_MODEL = "gemini-2.5-flash-lite"
    GROQ_MODEL = "openai/gpt-oss-20b"

    # Retained for the existing OpenRouter embedding client.
    OPENROUTER_MODEL = "nvidia/nemotron-3.5-lightning:free"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    MAX_TOKENS = 2048
    TEMPERATURE = 0.2

    # RAG Configuration
    # all-MiniLM-L6-v2 — English-only, 80MB (3.5× lighter than multilingual model)
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    TOP_K_RETRIEVAL = 5
    SIMILARITY_THRESHOLD = 0.35
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
