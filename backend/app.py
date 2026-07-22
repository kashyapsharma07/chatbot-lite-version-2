from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS  # type: ignore
import os
import json
# pyrefly: ignore [missing-import]
from config import Config
# pyrefly: ignore [missing-import]
from utils import log_query
# pyrefly: ignore [missing-import]
from rag_engine import RAGEngine
import uuid

print("=" * 50)
print("🚀 Starting CKPCMC Chatbot...")
print("=" * 50)

# Disable default static folder to prevent routing conflicts with the SPA fallback
app = Flask(
    __name__,
    static_folder=None
)

STATIC_FOLDER = os.path.join(os.path.dirname(__file__), "../frontend/dist")
CORS(app)  # type: ignore
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

os.makedirs("logs", exist_ok=True)

print("🔄 Initializing RAG Engine...")
rag_engine = RAGEngine()
print("✅ RAG Engine Ready!")
print("=" * 50)


# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/api", methods=["POST"])
def chatbot():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    session_id = data.get("session_id", str(uuid.uuid4()))

    if not user_input:
        return jsonify({"response": "Please enter a message.", "session_id": session_id, "suggestions": []})

    def generate_stream():
        try:
            for event in rag_engine.generate_response_stream(user_input, session_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            print(f"❌ Error in SSE stream generation: {str(e)}")
            yield f"data: {json.dumps({'type': 'content', 'content': 'An error occurred during generation.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    response = Response(generate_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/clear_history", methods=["POST"])
def clear_history():
    data = request.get_json()
    session_id = data.get("session_id", "default")
    success = rag_engine.clear_history(session_id)
    return jsonify({
        "message": "Conversation history cleared" if success else "No history found",
        "session_id": session_id,
        "success": success,
    })


@app.route("/get_faqs", methods=["GET"])
def get_faqs():
    faqs = [
        {"question": "What courses are offered at CKPCMC?", "preview": "CKPCMC offers B.Com, BBA, and BCA undergraduate courses...", "stream": "Academics"},
        {"question": "What is the fee structure for B.Com, BBA, and BCA?", "preview": "B.Com ₹7,490, BBA ₹13,065, BCA ₹17,865 for Semester-1...", "stream": "Fees"},
        {"question": "What is the intake capacity for BCA?", "preview": "BCA has an intake capacity of 510 seats...", "stream": "Academics"},
        {"question": "How can I pay fees or get an EMI option?", "preview": "CKPCMC partners with GrayQuest for monthly installments/EMI...", "stream": "Fees"},
        {"question": "How can I contact CKPCMC?", "preview": "Call 9023437774 or 9023679721, or email ckpcmc@gmail.com...", "stream": "Contact"},
    ]
    return jsonify({"faqs": faqs})


@app.route("/api/autocomplete", methods=["GET"])
def autocomplete():
    query = request.args.get("q", "").strip().lower()
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})

    # Collect questions from knowledge base
    questions = [item.get("question", "") for item in rag_engine.knowledge_base if item.get("question")]

    # Collect other templates
    for category, suggs in rag_engine.follow_up_suggestions.items():
        questions.extend(suggs)

    unique_questions = sorted(list(set(questions)))

    # Filter by substring match
    matches = []
    for q in unique_questions:
        if query in q.lower():
            matches.append(q)
            if len(matches) >= 5:
                break

    return jsonify({"suggestions": matches})


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "provider": Config.ACTIVE_MODEL_PROVIDER,
        "model": rag_engine.active_model,
        "knowledge_base_entries": len(rag_engine.knowledge_base),
        "active_sessions": len(rag_engine.conversation_history),
        "cache_size": len(rag_engine.response_cache),
    })


# ── Serve React Frontend ──────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    full_path = os.path.join(STATIC_FOLDER, path)
    if path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(STATIC_FOLDER, path)
    return send_from_directory(STATIC_FOLDER, "index.html")


# ── Security Headers ──────────────────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src * 'self' data: 'unsafe-inline' 'unsafe-eval'; "
        "script-src * 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src * 'self' 'unsafe-inline'; "
        "font-src * 'self' data:; "
        "connect-src * 'self' ws: wss:; "
        "img-src * 'self' data: blob:; "
        "media-src * 'self' data: blob:; "
    )
    return response


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"🌐 Starting Flask server on http://localhost:{port}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=True)