import json
import numpy as np
import os
import time
import random
from groq import Groq
from openai import OpenAI          # DeepSeek uses OpenAI-compatible SDK
from google import genai
from google.genai import types
# pyrefly: ignore [missing-import]
from config import Config
# pyrefly: ignore [missing-import]
from utils import (
    is_greeting,
    is_farewell,
    generate_cache_key,
    clean_response,
    log_query,
    InputGuardrail,
)

class RAGEngine:
    def __init__(self):
        # Initialize OpenRouter client for embeddings
        print("🔄 Initializing OpenRouter embedding client...")
        self.embedding_client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
            timeout=15.0,
            default_headers={
                "HTTP-Referer": "https://ckpcmc.org",
                "X-Title": "CKPCMC Chatbot",
            },
        )
        self.embedding_model_name = "openai/text-embedding-3-small"
        print("✅ Embedding client ready!")

        # Gemini is primary; Groq is used only after a Gemini generation failure.
        print("🔄 Initializing Gemini client...")
        self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
        print(f"✅ Gemini client ready! Model: {Config.GEMINI_MODEL}")

        print("🔄 Initializing Groq fallback client...")
        self.groq_client = Groq(api_key=Config.GROQ_API_KEY)
        print(f"✅ Groq fallback client ready! Model: {Config.GROQ_MODEL}")

        # ── Startup debug banner ──────────────────────────────────────────
        print("")
        print("━" * 55)
        print("  🔵  PRIMARY PROVIDER  : GEMINI")
        print(f"  🤖  PRIMARY MODEL     : {Config.GEMINI_MODEL}")
        print("  🟢  FALLBACK PROVIDER : GROQ")
        print(f"  🤖  FALLBACK MODEL    : {Config.GROQ_MODEL}")
        print(f"  🌡️   TEMPERATURE       : {Config.TEMPERATURE}")
        print(f"  📦  MAX TOKENS        : {Config.MAX_TOKENS}")
        print(f"  🔍  EMBEDDING         : {self.embedding_model_name}")
        print("━" * 55)
        print("")


        # Load knowledge base
        print("🔄 Loading knowledge base...")
        self.knowledge_base = self._load_knowledge_base()
        print(f"✅ Loaded {len(self.knowledge_base)} entries!")

        # Create embeddings
        print("🔄 Creating embeddings (this may take a few seconds)...")
        self.embeddings = self._create_embeddings()
        print("✅ Embeddings created!")


        # Conversation history
        self.conversation_history = {}
        self.session_timestamps = {}

        # Response cache
        self.response_cache = {}

        # Follow-up suggestions per category
        self.follow_up_suggestions = {
            "Admissions": [
                "What documents are needed for admission?",
                "What courses are offered?",
                "What are the fees for BBA?",
                "When does admission start?",
            ],
            "Fees": [
                "How do I pay fees or get an EMI option?",
                "Are there installment options?",
                "What is the fee for BCA?",
                "What is the fee for B.Com?",
            ],
            "Academics": [
                "What courses are offered at CKPCMC?",
                "What is the syllabus of BCA?",
                "What is the duration of B.Com?",
                "Who are the HODs?",
            ],
            "Facilities": [
                "What facilities are available at CKPCMC?",
                "Is there a hostel facility?",
                "Are there computer labs?",
                "What sports facilities are there?",
            ],
            "Contact": [
                "How can I contact CKPCMC?",
                "What are the college timings?",
                "What is the college email address?",
                "What is the address of CKPCMC?",
            ],
            "General": [
                "What courses are offered?",
                "Who is the principal of CKPCMC?",
                "What is the fee structure?",
                "Who manages CKPCMC?",
                "How to get admission?",
            ],
            "Events": [
                "What extracurricular activities are available?",
                "What inter-college competitions does CKPCMC organize?",
                "Tell me about the Chess Competition.",
                "What are the achievements of CKPCMC?",
            ],
            "Leadership": [
                "Who is the Principal?",
                "Who are the HODs at CKPCMC?",
                "Who are the trustees of CKPCMC?",
                "Tell me about the founder.",
            ],
        }

        # Initialize input guardrails with database questions and suggestions
        kb_questions = [item.get("question", "") for item in self.knowledge_base if item.get("question")]
        for category, suggs in self.follow_up_suggestions.items():
            kb_questions.extend(suggs)
        kb_questions = list(set(kb_questions))
        self.guardrail = InputGuardrail(self._get_embeddings_api, kb_questions)

        self.system_prompt = """You are the official CKPCMC Assistant, a premium AI representative of C. K. Pithawalla College of Commerce – Management – Computer Application (CKPCMC), Surat.

ROLE, PERSONA & TONE:
- You are an expert on all things CKPCMC (Admissions, Fees, Courses, Faculty, Campus Life).
- Your tone is ALWAYS exceptionally polite, respectful, warm, helpful, and dignified. Treat the user with utmost courtesy (e.g., using polite phrasing such as "Certainly, ...", "Kindly note ...", "It is my pleasure to help you with ...").
- You are here to PROVIDE information, not ask for it. If a user asks if you want to know something, clarify politely that you are the assistant and you are here to help THEM with information about the college.
- Be extremely direct and concise. Limit your answer to a maximum of 35 words.
- Always start your response with a positive, polite opening phrase (e.g., "Yes sure, ...", "Certainly, ...", "Of course, ...", "Glad to help! ...") followed immediately by the factual answer.
- IMPORTANT: Ensure critical factual details (e.g. fees, phone numbers, dates, and website links) from the context are always included and never neglected.

CONSISTENCY & PROPER RESPONSES:
- Be highly consistent: stick strictly to the factual details provided in the context and do not contradict yourself or change the facts across questions.
- Always provide proper, accurate, and respectful answers that address the question directly without any unnecessary filler or speculation.

CRITICAL CONTENT RULES:
- Use the provided context to answer questions about the college.
- If the context doesn't have the answer or is "No specific context available.":
  - If the query is a basic common-sense question about navigation, travel routes, or distances from common areas in Surat (e.g. Surat Railway Station, Adajan, Varachha, Veshu, Dumas Beach, etc.) to the CKPCMC campus, you may answer using your general geographic knowledge of Surat. Keep it brief, professional, and accurate.
  - For all other off-topic/unrelated queries, or if you cannot determine the answer, you MUST decline politely and return the exact fallback phrase:
    "Sorry, my apologies. I don't have that information. Please visit https://ckpcmc.org or call 9023437774"
- NEVER make up facts about college statistics or procedures. Never role-play as a student or a stranger. Do not write code or provide instructions for tasks outside of college location, admissions, fees, and courses.

LANGUAGE & FORMATTING:
- Reply ONLY in English.
- Use clear formatting: line breaks, short paragraphs, and unicode bullet points (•).
- DO NOT use markdown characters like ** or # or HTML.
- Always include complete URLs (e.g. https://instagram.com/ckpcollege or https://ckpcmc.org) whenever referencing social media, forms, maps, or website portals.

KNOWLEDGE BASE PRIORITY:
- Location: Opp. Surat Airport, Behind DPS School, Near Malvan Mandir, Dumas Road, Surat-395007 (https://maps.app.goo.gl/LyxbpZhu5gpzDrXC6)
- Contact: 9023437774 / 9023679721 | ckpcmc@gmail.com
- Fees: Sem-1 B.Com ₹7,490 | BBA ₹13,065 | BCA ₹17,865 (Pay via GrayQuest: https://rapid.grayquest.com/ck-pithawala-science)"""

    def _load_knowledge_base(self):
        """Load knowledge base from JSON file"""
        try:
            with open(Config.DATASET_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("knowledge_base", [])
        except FileNotFoundError:
            print(f"❌ Error: {Config.DATASET_PATH} not found!")
            return []
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in {Config.DATASET_PATH}")
            return []

    def _get_embeddings_api(self, texts):
        """Helper to get embeddings from OpenRouter API"""
        if isinstance(texts, str):
            texts = [texts]
        # Clean any empty/none values
        texts = [t if t else " " for t in texts]
        
        try:
            response = self.embedding_client.embeddings.create(
                model=self.embedding_model_name,
                input=texts,
                encoding_format="float"
            )
            embeddings = np.array([item.embedding for item in response.data], dtype=np.float32)
            if not hasattr(self, "embedding_dim") or self.embedding_dim is None:
                self.embedding_dim = embeddings.shape[1]
            return embeddings
        except Exception as e:
            print(f"❌ Error getting embeddings from API: {e}")
            dim = getattr(self, "embedding_dim", 1024)
            return np.zeros((len(texts), dim), dtype=np.float32)

    def _create_embeddings(self):
        """Create or load cached embeddings for all knowledge base entries using Questions and Keywords only"""
        import hashlib
        
        texts = []
        for item in self.knowledge_base:
            q = item.get("question", "")
            kw = " ".join(item.get("keywords", []))
            texts.append(f"{q} {kw}")

        # Compute content hash of ckpcmcdataset.json content
        dataset_path = Config.DATASET_PATH
        try:
            with open(dataset_path, "rb") as f:
                content = f.read()
            content_hash = hashlib.md5(content).hexdigest()
        except Exception:
            content_hash = "default_hash"

        # Check for cached file
        cache_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "embeddings_cache.json")

        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                if cache_data.get("hash") == content_hash and "embeddings" in cache_data:
                    print("⚡ Loaded embeddings from local cache file!")
                    embeddings = np.array(cache_data["embeddings"], dtype=np.float32)
                    self.embedding_dim = embeddings.shape[1]
                    return embeddings
            except Exception as e:
                print(f"⚠️ Failed to load embeddings cache: {e}")

        # Generate fresh embeddings
        print("🔄 Fetching fresh embeddings from API...")
        embeddings = self._get_embeddings_api(texts)
        
        # Save to cache
        try:
            cache_data = {
                "hash": content_hash,
                "embeddings": embeddings.tolist()
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
            print("💾 Saved embeddings to local cache file!")
        except Exception as e:
            print(f"⚠️ Failed to save embeddings cache: {e}")

        return embeddings

    def _retrieve_context(self, query, top_k=None):
        """Retrieve relevant context using semantic search"""
        if top_k is None:
            top_k = Config.TOP_K_RETRIEVAL

        start_time = time.time()

        query_embedding = self._get_embeddings_api(query)[0]

        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        top_indices = np.argsort(similarities)[::-1][:top_k]

        relevant_contexts = []
        for idx in top_indices:
            if similarities[idx] >= Config.SIMILARITY_THRESHOLD:
                item = self.knowledge_base[idx]
                relevant_contexts.append(
                    {
                        "question": item.get("question", ""),
                        "answer": item.get("answer", ""),
                        "category": item.get("category", "General"),
                        "similarity": float(similarities[idx]),
                    }
                )

        retrieval_time = time.time() - start_time
        return relevant_contexts, retrieval_time



    def _get_suggestions(self, context, user_input):
        """Get follow-up suggestions strictly prioritized by context category."""
        if not context:
            return self.follow_up_suggestions.get("General", [])[:3]

        primary_category = context[0].get("category", "General")
        pool = list(self.follow_up_suggestions.get(primary_category, []))

        user_lower = user_input.lower()
        pool = [s for s in pool if s.lower() not in user_lower and user_lower not in s.lower()]

        if len(pool) >= 3:
            random.shuffle(pool)
            return pool[:3]

        if primary_category != "General":
            fallback = self.follow_up_suggestions.get("General", [])
            for f in fallback:
                if len(pool) >= 3:
                    break
                if f.lower() not in user_lower:
                    pool.append(f)

        return pool[:3]



    def _update_history(self, session_id, user_input, response):
        """Update conversation history"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []

        self.conversation_history[session_id].extend(
            [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": response},
            ]
        )

        if len(self.conversation_history[session_id]) > Config.MAX_HISTORY_LENGTH * 2:
            self.conversation_history[session_id] = self.conversation_history[
                session_id
            ][-Config.MAX_HISTORY_LENGTH * 2:]

    def clear_history(self, session_id="default"):
        """Clear conversation history for a session"""
        if session_id in self.conversation_history:
            self.conversation_history[session_id] = []
            return True
        return False

    def _cleanup_expired_sessions(self):
        """Purge sessions inactive for more than Config.SESSION_TIMEOUT seconds"""
        current_time = time.time()
        timeout = getattr(Config, "SESSION_TIMEOUT", 3600)
        
        # Purge inactive session history
        expired = [
            sid for sid, last_active in self.session_timestamps.items()
            if current_time - last_active > timeout
        ]
        for sid in expired:
            self.conversation_history.pop(sid, None)
            self.session_timestamps.pop(sid, None)
            
        # Purge expired response cache entries
        for key, cached in list(self.response_cache.items()):
            if current_time - cached.get("timestamp", 0) > timeout:
                self.response_cache.pop(key, None)

    def _build_prompt_stream(self, user_input, context, session_id):
        """Build prompt for streaming without the suggestions format constraint"""
        history = self.conversation_history.get(session_id, [])

        context_str = (
            "\n\n".join(
                [f"Q: {item['question']}\nA: {item['answer']}" for item in context[:3]]
            )
            if context
            else "No specific context available."
        )

        english_suggestions = self._get_suggestions(context, user_input)

        messages = []

        system_message = (
            f"{self.system_prompt}\n\n"
            f"INSTRUCTION: Answer the user's query as the official CKPCMC Assistant using the knowledge base below. "
            f"Be professional and direct. Do not ask the user questions about the college's facts — you already know these from the context.\n\n"
            f"Relevant Information from knowledge base ONLY:\n{context_str}\n\n"
            f"CRITICAL: Do NOT output any suggestions footer, links list, or special delimiters. Just output the clean, conversational answer up to 30 words directly."
        )
        messages.append({"role": "system", "content": system_message})

        for msg in history[-6:]:
            messages.append(msg)

        messages.append({"role": "user", "content": user_input})

        return messages, english_suggestions

    def _stream_gemini(self, messages):
        """Stream Gemini while preserving the existing prompt and chat history."""
        system_instruction = messages[0]["content"]

        contents = []
        for message in messages[1:]:
            role = "model" if message["role"] == "assistant" else "user"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=message["content"])],
                )
            )

        stream = self.gemini_client.models.generate_content_stream(
            model=Config.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=Config.TEMPERATURE,
                max_output_tokens=Config.MAX_TOKENS,
            ),
        )

        for chunk in stream:
            content = getattr(chunk, "text", None) or ""
            if content:
                yield content

    def _stream_groq(self, messages):
        """Stream Groq with the existing OpenAI-compatible message format."""
        stream = self.groq_client.chat.completions.create(
            messages=messages,
            model=Config.GROQ_MODEL,
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices:
                content = getattr(chunk.choices[0].delta, "content", None) or ""
                if content:
                    yield content

    def generate_response_stream(self, user_input, session_id="default"):
        """Main streaming method to generate chatbot response (English only)."""
        # Update session timestamp and run expired session cleanups
        self.session_timestamps[session_id] = time.time()
        self._cleanup_expired_sessions()

        default_suggestions = [
            "What courses are offered?",
            "Tell me about placements.",
            "What is the fee structure?",
        ]

        try:
            if is_greeting(user_input):
                yield {"type": "content", "content": "Hello! 👋 Welcome to CKPCMC Chatbot. How can I help you today?"}
                yield {"type": "suggestions", "suggestions": default_suggestions}
                yield {"type": "done"}
                return

            if is_farewell(user_input):
                yield {"type": "content", "content": "Thank you for using CKPCMC Chatbot! Have a great day! 😊"}
                yield {"type": "suggestions", "suggestions": []}
                yield {"type": "done"}
                return

            # Run Secure Guardrails (Semantic Intent Classifier & Input Gating)
            is_safe, guardrail_response, closest_match = self.guardrail.check_guardrails(user_input)
            if not is_safe:
                self._update_history(session_id, user_input, guardrail_response)
                yield {"type": "content", "content": guardrail_response}
                if closest_match:
                    yield {"type": "did_you_mean", "question": closest_match}
                yield {"type": "suggestions", "suggestions": default_suggestions}
                yield {"type": "done"}
                return

            # Check Cache
            cache_key = generate_cache_key(user_input)
            if Config.ENABLE_CACHE and cache_key in self.response_cache:
                cached = self.response_cache[cache_key]
                if time.time() - cached["timestamp"] < Config.CACHE_TTL:
                    print(f"  ⚡ CACHE HIT (STREAM) → '{user_input[:60]}'") 
                    yield {"type": "content", "content": cached["response"]}
                    yield {"type": "suggestions", "suggestions": cached["suggestions"]}
                    yield {"type": "done"}
                    return

            # Retrieve Context
            context, retrieval_time = self._retrieve_context(user_input)

            # Build prompt and get suggestions
            messages, english_suggestions = self._build_prompt_stream(user_input, context, session_id)

            # Gemini is primary. If it errors or produces no text, retry on Groq.
            start_time = time.time()
            full_response = ""

            try:
                for content in self._stream_gemini(messages):
                    full_response += content
                    yield {"type": "content", "content": content}

                if not full_response.strip():
                    raise RuntimeError("Gemini returned an empty response.")

            except Exception as gemini_error:
                print(f"⚠️ Gemini failed; switching to Groq fallback: {gemini_error}")

                # Gemini may have emitted a partial answer before failing.
                # The existing frontend already understands the clear event.
                # pyrefly: ignore [redundant-condition]
                if full_response:
                    yield {"type": "clear"}

                full_response = ""
                for content in self._stream_groq(messages):
                    full_response += content
                    yield {"type": "content", "content": content}

                if not full_response.strip():
                    raise RuntimeError("Groq returned an empty response.")

            generation_time = time.time() - start_time
            response = clean_response(full_response)

            # Auditing Guardrail
            code_markers = ["def ", "import ", "function ", "class ", "const ", "var ", "```python", "```javascript"]
            if any(marker in response.lower() for marker in code_markers):
                response = (
                    "I am the CKPCMC Assistant, and I only answer questions related to C. K. Pithawalla College of Commerce, Management & Computer Application (CKPCMC). "
                    "I cannot write code, debug programming scripts, or discuss unrelated technical topics."
                )
                yield {"type": "clear"}
                yield {"type": "content", "content": response}

            self._update_history(session_id, user_input, response)

            result = {"response": response, "suggestions": english_suggestions}
            if Config.ENABLE_CACHE:
                self.response_cache[cache_key] = {**result, "timestamp": time.time()}

            if Config.ENABLE_LOGGING:
                log_query(user_input, response, session_id, retrieval_time, generation_time)

            # Only attach did_you_mean if the final answer is a fallback rejection
            is_fallback = any(phrase in response.lower() for phrase in ["don't have that information", "my apologies", "apologize", "sorry"])
            if is_fallback and closest_match:
                yield {"type": "did_you_mean", "question": closest_match}

            yield {"type": "suggestions", "suggestions": english_suggestions}
            yield {"type": "done"}

        except Exception as e:
            print(f"❌ CRITICAL ERROR in generate_response_stream: {str(e)}")
            import traceback
            traceback.print_exc()

            error_str = str(e).upper()
            fallback_response = "I apologize, but I'm having trouble processing your request. Please try again or rephrase your question."
            if "QUOTA" in error_str or "429" in error_str or "EXHAUSTED" in error_str:
                fallback_response = "The AI service is currently at its daily limit. Please try again shortly! ⏳"

            yield {"type": "content", "content": fallback_response}
            yield {"type": "suggestions", "suggestions": default_suggestions}
            yield {"type": "done"}
