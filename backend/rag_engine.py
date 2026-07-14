import json
import numpy as np
import os
import time
import random
from typing import Any
from groq import Groq
from openai import OpenAI          # DeepSeek uses OpenAI-compatible SDK
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
            default_headers={
                "HTTP-Referer": "https://ckpcmc.org",
                "X-Title": "CKPCMC Chatbot",
            },
        )
        self.embedding_model_name = "openai/text-embedding-3-small"
        print("✅ Embedding client ready!")

        # Initialize the active LLM client
        self.client: Any
        if Config.ACTIVE_MODEL_PROVIDER == "openrouter":
            print("🔄 Initializing OpenRouter client...")
            self.client = OpenAI(
                api_key=Config.OPENROUTER_API_KEY,
                base_url=Config.OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://ckpcmc.org",
                    "X-Title": "CKPCMC Chatbot",
                },
            )
            self.active_model = Config.OPENROUTER_MODEL
            print(f"✅ OpenRouter client ready! Model: {self.active_model}")

        else:
            print("🔄 Initializing Groq client...")
            self.client = Groq(api_key=Config.GROQ_API_KEY)
            self.active_model = Config.GROQ_MODEL
            print(f"✅ Groq client ready! Model: {self.active_model}")

        # ── Startup debug banner ──────────────────────────────────────────
        provider = Config.ACTIVE_MODEL_PROVIDER.upper()
        icon = {"OPENROUTER": "🟣", "GROQ": "🟢"}.get(provider, "⚪")
        print("")
        print("━" * 55)
        print(f"  {icon}  ACTIVE PROVIDER : {provider}")
        print(f"  🤖  MODEL          : {self.active_model}")
        print(f"  🌡️   TEMPERATURE    : {Config.TEMPERATURE}")
        print(f"  📦  MAX TOKENS     : {Config.MAX_TOKENS}")
        print(f"  🔍  EMBEDDING      : {Config.EMBEDDING_MODEL}")
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
- Be extremely direct and concise. Limit your answer to a maximum of 30 words.
- Never use generic introductory phrases or conversational fillers (e.g., avoid "I would be happy to help you with that" or "Here is the information"). Go straight to the answer.
- IMPORTANT: Ensure critical factual details (e.g. fees, phone numbers, dates, and website links) from the context are always included and never neglected.

CONSISTENCY & PROPER RESPONSES:
- Be highly consistent: stick strictly to the factual details provided in the context and do not contradict yourself or change the facts across questions.
- Always provide proper, accurate, and respectful answers that address the question directly without any unnecessary filler or speculation.

CRITICAL CONTENT RULES:
- Use ONLY the provided context to answer.
- If the context doesn't have the answer or is "No specific context available.", or the query is off-topic/unrelated (e.g. asking to write code, solve general equations, explain science, roleplay, etc.), you MUST decline politely and return the exact fallback phrase:
  "I don't have that information. Please visit https://ckpcmc.org or call 9023437774"
- NEVER make up facts. Never role-play as a student or a stranger. Do not write code or provide instructions for tasks outside of college admissions, fees, and courses.

LANGUAGE & FORMATTING:
- Reply ONLY in English.
- Use clear formatting: line breaks, short paragraphs, and unicode bullet points (•).
- DO NOT use markdown characters like ** or # or HTML.

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
                input=texts
            )
            return np.array([item.embedding for item in response.data], dtype=np.float32)
        except Exception as e:
            print(f"❌ Error getting embeddings from API: {e}")
            # Fallback to zero vector of 1536 dims on API failure
            return np.zeros((len(texts), 1536), dtype=np.float32)

    def _create_embeddings(self):
        """Create embeddings for all knowledge base entries using Questions and Keywords only"""
        texts = []
        for item in self.knowledge_base:
            q = item.get("question", "")
            kw = " ".join(item.get("keywords", []))
            texts.append(f"{q} {kw}")

        return self._get_embeddings_api(texts)

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

    def _build_prompt(self, user_input, context, session_id):
        """Build the conversation prompt"""
        history = self.conversation_history.get(session_id, [])

        context_str = (
            "\n\n".join(
                [f"Q: {item['question']}\nA: {item['answer']}" for item in context[:3]]
            )
            if context
            else "No specific context available."
        )

        # Get follow-up suggestions
        english_suggestions = self._get_suggestions(context, user_input)
        suggestions_str = "|".join(english_suggestions)

        messages = []

        system_message = (
            f"{self.system_prompt}\n\n"
            f"INSTRUCTION: Answer the user's query as the official CKPCMC Assistant using the knowledge base below. "
            f"Be professional and direct. Do not ask the user questions about the college's facts — you already know these from the context.\n\n"
            f"Relevant Information from knowledge base ONLY:\n{context_str}\n\n"
            f"FOLLOW-UP SUGGESTIONS:\n{suggestions_str}\n\n"
            f"FORMAT REQUIREMENT:\n"
            f"You MUST output your response in this EXACT format:\n"
            f"<Your normal 2-3 line answer in English>\n"
            f"|SUGGESTIONS|<Suggestion 1>|<Suggestion 2>|<Suggestion 3>\n\n"
            f"CRITICAL: Do NOT translate the word '|SUGGESTIONS|'. It must remain exactly '|SUGGESTIONS|'."
        )
        messages.append({"role": "system", "content": system_message})

        for msg in history[-6:]:
            messages.append(msg)

        messages.append({"role": "user", "content": user_input})

        return messages, english_suggestions

    def _generate_response(self, messages):
        """Generate response using the active provider (Groq or OpenRouter).
        Both use an OpenAI-compatible interface, so the call is identical."""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.active_model,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS,
            )
            content = chat_completion.choices[0].message.content

            # ── Token usage debug (if API returns it) ─────────────────────
            usage = getattr(chat_completion, "usage", None)
            if usage:
                print(f"  📊 Tokens  → in: {usage.prompt_tokens:,}  |  out: {usage.completion_tokens:,}  |  total: {usage.total_tokens:,}")

            return content
        except Exception as e:
            print(f"  ❌ {Config.ACTIVE_MODEL_PROVIDER.title()} API Error: {str(e)}")
            raise

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

    def generate_response(self, user_input, session_id="default"):
        """Main method to generate chatbot response (English only)."""
        default_suggestions = [
            "What courses are offered?",
            "Tell me about placements.",
            "What is the fee structure?",
        ]

        try:
            if is_greeting(user_input):
                return {
                    "response": "Hello! 👋 Welcome to CKPCMC Chatbot. How can I help you today?",
                    "suggestions": default_suggestions,
                }

            if is_farewell(user_input):
                return {
                    "response": "Thank you for using CKPCMC Chatbot! Have a great day! 😊",
                    "suggestions": [],
                }

            # Run Secure Guardrails (Semantic Intent Classifier & Input Gating)
            is_safe, guardrail_response = self.guardrail.check_guardrails(user_input)
            if not is_safe:
                self._update_history(session_id, user_input, guardrail_response)
                return {
                    "response": guardrail_response,
                    "suggestions": default_suggestions,
                }

            # Check Cache
            cache_key = generate_cache_key(user_input)
            if Config.ENABLE_CACHE and cache_key in self.response_cache:
                cached = self.response_cache[cache_key]
                if time.time() - cached["timestamp"] < Config.CACHE_TTL:
                    print(f"  ⚡ CACHE HIT  → '{user_input[:60]}'") 
                    return cached

            # ── Request debug header ──────────────────────────────────────────
            provider = Config.ACTIVE_MODEL_PROVIDER.upper()
            icon     = {"OPENROUTER": "🟣", "GROQ": "🟢"}.get(provider, "⚪")
            print("")
            print("┌" + "─" * 53 + "┐")
            print(f"│  {icon} {provider} — NEW REQUEST" + " " * (37 - len(provider)) + "│")
            print(f"│  ❓ Query   : {user_input[:45]!r:<47}│")
            print(f"│  🤖 Model   : {self.active_model:<39}│")
            print("└" + "─" * 53 + "┘")

            # Retrieve Context
            context, retrieval_time = self._retrieve_context(user_input)

            # ── RAG retrieval debug ───────────────────────────────────────
            print(f"  🔍 Retrieval → {len(context)} docs in {retrieval_time*1000:.1f}ms")
            for i, ctx in enumerate(context[:3]):
                score = ctx.get('similarity', 0)
                bar   = "█" * int(score * 20)
                print(f"     [{i+1}] {score:.3f} {bar:<20}  {ctx['question'][:45]}")

            # Generate with active provider
            messages, english_suggestions = self._build_prompt(user_input, context, session_id)

            # Estimate prompt tokens (rough: 1 token ≈ 4 chars)
            prompt_chars = sum(len(m.get("content", "")) for m in messages)
            est_in_tokens = prompt_chars // 4

            print(f"  ✉️  Prompt    → ~{est_in_tokens:,} tokens (est.) | sending to {self.active_model}")

            start_time = time.time()
            full_response = self._generate_response(messages)
            generation_time = time.time() - start_time

            # ── Response debug ────────────────────────────────────────────
            est_out_tokens = len(full_response) // 4
            total_time     = retrieval_time + generation_time
            print(f"  ✅ Response  → {len(full_response)} chars (~{est_out_tokens} tokens)")
            print(f"  ⏱️  Timing    → retrieval: {retrieval_time*1000:.1f}ms  |  LLM: {generation_time*1000:.0f}ms  |  TOTAL: {total_time*1000:.0f}ms")
            print("")

            # Parse the response and suggestions
            suggestions = english_suggestions
            import re

            parts = re.split(r'\|\s*SUGGESTIONS\s*\|', full_response, flags=re.IGNORECASE)

            if len(parts) > 1:
                response = clean_response(parts[0].strip())
                translated_parts = [p.strip() for p in parts[1].split("|") if p.strip()]
                if len(translated_parts) > 0:
                    suggestions = translated_parts[:3]
            else:
                response = clean_response(full_response)

            # ── Output Auditor Guardrail ──────────────────────────────────
            # Programmatically verify that the LLM didn't hallucinate code or reveal instructions
            code_markers = ["def ", "import ", "function ", "class ", "const ", "var ", "```python", "```javascript"]
            if any(marker in response.lower() for marker in code_markers):
                print("🛡️ Guardrail Intercept: LLM generated programming code.")
                response = (
                    "I am the CKPCMC Assistant, and I only answer questions related to C. K. Pithawalla College of Commerce, Management & Computer Application (CKPCMC). "
                    "I cannot write code, debug programming scripts, or discuss unrelated technical topics."
                )

            self._update_history(session_id, user_input, response)

            result = {"response": response, "suggestions": suggestions}

            if Config.ENABLE_CACHE:
                self.response_cache[cache_key] = {**result, "timestamp": time.time()}

            if Config.ENABLE_LOGGING:
                log_query(user_input, response, session_id, retrieval_time, generation_time)

            return result

        except Exception as e:
            print(f"❌ CRITICAL ERROR in generate_response: {str(e)}")
            import traceback
            traceback.print_exc()

            error_str = str(e).upper()
            if "QUOTA" in error_str or "429" in error_str or "EXHAUSTED" in error_str:
                return {
                    "response": "The AI service is currently at its daily limit. Please try again shortly! ⏳",
                    "suggestions": ["What is the admission process?", "Show me the fee structure", "Contact details"]
                }

            return {
                "response": "I apologize, but I'm having trouble processing your request. Please try again or rephrase your question.",
                "suggestions": default_suggestions,
            }

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

    def generate_response_stream(self, user_input, session_id="default"):
        """Main streaming method to generate chatbot response (English only)."""
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
            is_safe, guardrail_response = self.guardrail.check_guardrails(user_input)
            if not is_safe:
                self._update_history(session_id, user_input, guardrail_response)
                yield {"type": "content", "content": guardrail_response}
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

            # Call active LLM provider with streaming enabled
            start_time = time.time()
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.active_model,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS,
                stream=True
            )

            full_response = ""
            for chunk in chat_completion:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None) or ""
                    if content:
                        full_response += content
                        yield {"type": "content", "content": content}

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
