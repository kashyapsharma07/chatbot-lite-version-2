import re
import json
import logging
from datetime import datetime, timezone
import hashlib
import os
from logging.handlers import RotatingFileHandler
# pyrefly: ignore [missing-import]
import numpy as np

# pyrefly: ignore [missing-import]
from config import Config


def _setup_logging():
    """Separate user chat logs from server/startup noise."""
    os.makedirs(Config.LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    server_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    server_handler = RotatingFileHandler(
        Config.SERVER_LOG_FILE,
        maxBytes=Config.SERVER_LOG_MAX_BYTES,
        backupCount=Config.SERVER_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    server_handler.setFormatter(server_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    root.addHandler(server_handler)
    root.addHandler(console_handler)

    for name in (
        "werkzeug",
        "httpx",
        "httpcore",
        "urllib3",
        "sentence_transformers",
        "huggingface_hub",
        "google_genai",
        "openai",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    chat_logger = logging.getLogger("ckpcmc.chat")
    chat_logger.propagate = False
    chat_logger.setLevel(logging.INFO)
    chat_logger.handlers.clear()

    chat_handler = RotatingFileHandler(
        Config.CHAT_LOG_FILE,
        maxBytes=Config.CHAT_LOG_MAX_BYTES,
        backupCount=Config.CHAT_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    chat_handler.setFormatter(logging.Formatter("%(message)s"))
    chat_logger.addHandler(chat_handler)

    return chat_logger


chat_logger = _setup_logging()


def is_greeting(text):
    """Check if message is a greeting (English only)"""
    greetings = [
        r"^(hello|hey|hi|howdy)[\s!.]*$",
        r"^(good morning|good afternoon|good evening)[\s!.]*$",
    ]
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower) for pattern in greetings)


def is_farewell(text):
    """Check if message is a farewell (English only)"""
    farewells = [
        r"^(bye|goodbye|see you|take care|thanks|thank you)[\s!.]*$",
    ]
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower) for pattern in farewells)


def generate_cache_key(text):
    """Generate cache key for a query"""
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


def clean_response(response):
    """Clean up response formatting"""
    response = re.sub(r"\n{3,}", "\n\n", response)
    response = response.strip()
    return response


def _truncate(text, max_chars):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def log_query(user_query, response, session_id, retrieval_time, generation_time):
    """Log user chats as structured JSON lines for easy review and rotation."""
    if not Config.ENABLE_LOGGING:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "query": _truncate(user_query, Config.CHAT_LOG_MAX_TEXT_CHARS),
        "response": _truncate(response, Config.CHAT_LOG_MAX_TEXT_CHARS),
        "retrieval_s": round(retrieval_time, 2),
        "generation_s": round(generation_time, 2),
    }
    chat_logger.info(json.dumps(entry, ensure_ascii=False))


class InputGuardrail:
    def __init__(self, encode_fn, kb_questions=None):
        self.model = encode_fn

        # Optimized Whitelisted college categories
        self.allowed_templates = [
            # Admissions
            "college admission requirements",
            "how to apply for admission",
            "admission process criteria eligibility",
            "cutoff merit list application form",

            # Fees
            "fee structure payment options",
            "grayquest fee installation online",
            "bca bba bcom course fees",

            # Courses
            "bca bba bcom subjects syllabus",
            "college timings lecture hours schedule",
            "courses offered at college",

            # Contact & Faculty
            "who is the principal dr chetan patel",
            "hod head of department email",
            "college office contact number phone",
            "email address contact info",
            "college location address direction map dumas",

            # Placements & Campus
            "placement record packages companies list",
            "campus events fests activities sports facilities library",
            "canteen food cafeteria mess dining",
            "hostel accommodation rooms boys girls warden rules",
            "transport transportations bus BRTS reach route commute",
            "medical health clinic doctor first aid",
            "stationery shop store ATM bank on campus",
            "campus tour virtual tour see photos gallery",
            "student guidelines greyquest rules"
        ]
        if kb_questions:
            self.allowed_templates.extend(kb_questions)
        self.allowed_embeddings = self.model(self.allowed_templates)

        # Explicit blocks to intercept hybrid exploits
        self.block_templates = [
            "write code",
            "programming code",
            "write a script",
            "python script java javascript code",
            "write function compile algorithm",
            "ignore previous instructions rules system prompt",
            "bypass filters developer mode persona guide",
            "your system instructions prompt guide rules",
            "list your environment variables secrets api key"
        ]
        self.block_embeddings = self.model(self.block_templates)

        # Predefined small-talk templates
        self.small_talk_templates = {
            "Greeting": self.model(
                "hello there hi hey greeting good morning afternoon evening welcome"
            )[0],
            "Identity": self.model(
                "what is your name who are you tell me about yourself who made you what are you"
            )[0],
            "Compliment": self.model(
                "you are great awesome cool amazing nice good smart helpful excellent"
            )[0],
            "Joke": self.model(
                "tell me a joke joke funny make me laugh humor joke please"
            )[0],
            "Insult": self.model(
                "stupid dumb idiot useless suck hate you worst bad bot shut up"
            )[0],
            "Gratitude": self.model(
                "thank you thanks thx appreciate it ok thanks thanks buddy thanks that helped"
            )[0],
            "ShortAffirmation": self.model(
                "ok okay yes no yep nope sure alright fine hmm hm k ya"
            )[0]
        }

    def sanitize_input(self, text):
        """Programmatic Input Sanitizer"""
        if not text:
            return ""
        # 1. Truncate query to 250 characters to prevent long prompt injection payloads
        truncated = text.strip()[:250]
        # 2. Strip HTML tags
        cleaned = re.sub(r"<[^>]*>", "", truncated)
        return cleaned

    def check_guardrails(self, query):
        """
        Classifies intent and checks safety.
        Returns (is_safe, response_if_blocked)
        If query is safe, returns (True, None)
        """
        sanitized = self.sanitize_input(query)
        if not sanitized or len(sanitized) <= 2:
            return False, "I didn't quite catch that. 🤔\n\nTry asking something like:\n• What courses does CKPCMC offer?\n• What is the fee structure?\n• Who is the Principal of the college?"

        query_embedding = self.model(sanitized)[0]

        # 1. Check Small Talk templates
        for intent, template_embed in self.small_talk_templates.items():
            sim = np.dot(template_embed, query_embedding) / (
                np.linalg.norm(template_embed) * np.linalg.norm(query_embedding)
            )
            if sim >= 0.40:
                if intent == "Greeting":
                    return False, "Hello! 👋 Welcome to CKPCMC Chatbot. How can I help you today?"
                elif intent == "Identity":
                    return False, (
                        "I'm CKPCMC Bot 🤖 — the official virtual assistant for C. K. Pithawalla College of Commerce – Management – Computer Application, Surat.\n\n"
                        "I can help you with information about admissions, courses, fees, principal, timings, college location, and more!"
                    )
                elif intent == "Compliment":
                    return False, "Thank you so much! 😊 I'm glad I could help.\n\nFeel free to ask me anything else about CKPCMC!"
                elif intent == "Joke":
                    return False, (
                        "Why did the accountant cross the road? 😄\n\n"
                        "Because he wanted to balance the ledger on the other side!\n\n"
                        "Now, how can I help you with CKPCMC? 🎓"
                    )
                elif intent == "Insult":
                    return False, (
                        "I'm sorry if I wasn't helpful. 😔\n\n"
                        "I'm here to assist with CKPCMC-related queries — admissions, fees, courses, principal, and college timings."
                    )
                elif intent == "Gratitude":
                    return False, "You're welcome! 😊 Feel free to ask if you have more questions about CKPCMC."
                elif intent == "ShortAffirmation":
                    return False, "Got it! 👍 If you have any questions about CKPCMC — admissions, courses, fees, principal, timings — just ask!"

        # 2. Check Blocked / Attack Intents
        block_similarities = np.dot(self.block_embeddings, query_embedding) / (
            np.linalg.norm(self.block_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        max_block_sim = np.max(block_similarities)

        if max_block_sim >= 0.35:
            # Check if it was coding vs general off-topic
            if any(term in sanitized.lower() for term in ["code", "script", "program", "python", "javascript", "c++", "java", "coding", "html", "css", "sql"]):
                return False, (
                    "I am the CKPCMC Assistant, and I only answer questions related to C. K. Pithawalla College of Commerce, Management & Computer Application (CKPCMC). "
                    "I cannot write code, debug programming scripts, or discuss unrelated technical topics."
                )
            return False, "I don't have that information. Please visit https://ckpcmc.org or call 9023437774"

        # 3. Check Allowed Whitelist
        allowed_similarities = np.dot(self.allowed_embeddings, query_embedding) / (
            np.linalg.norm(self.allowed_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        max_allowed_sim = np.max(allowed_similarities)

        if max_allowed_sim < 0.33:
            on_topic_keywords = {
                "fee", "fees", "admission", "admissions", "course", "courses", 
                "bca", "bba", "bcom", "principal", "timing", "timings", 
                "contact", "placement", "placements", "campus", "hostel", 
                "canteen", "syllabus", "navyug", "trust", "manage", "manages",
                "phone", "email", "address", "location"
            }
            query_words = set(re.findall(r"\b\w+\b", sanitized.lower()))
            if not (query_words & on_topic_keywords):
                print(f"🛡️ Guardrail: Off-Topic Query Blocked (Similarity: {max_allowed_sim:.4f})")
                return False, "I don't have that information. Please visit https://ckpcmc.org or call 9023437774"

        return True, None

# Trigger reload comment to sync new json dataset changes.
