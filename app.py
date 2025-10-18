# app.py
import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# === NLLB SETUP ===
HF_TOKEN = os.getenv("HF_API_KEY")
if not HF_TOKEN:
    logger.error("HF_API_KEY not set — NLLB translation will fail.")

try:
    client = InferenceClient("facebook/nllb-200-distilled-600M", token=HF_TOKEN)
except Exception as e:
    client = None
    logger.error(f"Failed to initialize Hugging Face client: {e}")

NLLB_LANG_MAP = {
    "en": "eng_Latn",
    "am": "amh_Ethi",   # Amharic
    "om": "orm_Latn",   # Oromo
    "ti": "tir_Ethi",   # Tigrinya
    "so": "som_Latn",   # Somali
    "aa": "aar_Latn",   # Afar
    "sid": "sid_Latn",  # Sidamo
    "wal": "wal_Ethi",  # Wolaytta
}

SUPPORTED_LANGUAGES = set(NLLB_LANG_MAP.keys())

# ======================
# EMAIL SUBSCRIPTION (EmailOctopus API v2 - CORRECT)
# ======================

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        email = data.get("email", "").strip()
        if not email:
            return jsonify({"error": "Email is required"}), 400

        api_key = os.getenv("EMAILOCTOPUS_API_KEY", "").strip()
        list_id = os.getenv("EMAILOCTOPUS_LIST_ID", "").strip()

        if not api_key or not list_id:
            logger.error("EmailOctopus API_KEY or LIST_ID missing")
            return jsonify({"error": "Subscription service not configured"}), 500

        # ✅ CORRECT v2 API: Bearer auth + api.emailoctopus.com/v2/
        url = f"https://api.emailoctopus.com/v2/lists/{list_id}/contacts"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"email_address": email, "status": "SUBSCRIBED"},
            timeout=10
        )

        logger.info(f"EmailOctopus v2 response {response.status_code}: {response.text}")

        if response.status_code in (200, 201):
            return jsonify({"message": "Subscribed successfully!"})

        elif response.status_code == 422:
            try:
                resp = response.json()
                errors = resp.get("errors", [])
                for err in errors:
                    if err.get("pointer") == "/email_address":
                        detail = (err.get("detail") or "").lower()
                        if "blank" in detail:
                            return jsonify({"error": "Email cannot be empty"}), 400
                        if "invalid" in detail:
                            return jsonify({"error": "Invalid email address"}), 400
                return jsonify({"error": "Invalid subscription data"}), 422
            except Exception:
                return jsonify({"error": "Invalid email format"}), 400

        elif response.status_code == 409 or (
            response.status_code == 400 and "already exists" in response.text.lower()
        ):
            return jsonify({"error": "Email already subscribed"}), 422

        elif response.status_code == 401:
            logger.error("EmailOctopus: Invalid or missing v2 API key")
            return jsonify({"error": "Subscription service misconfigured"}), 500

        elif response.status_code == 404:
            logger.error(f"EmailOctopus: List ID not found: {list_id}")
            return jsonify({"error": "Invalid subscription list"}), 500

        else:
            logger.error(f"EmailOctopus v2 error {response.status_code}: {response.text}")
            return jsonify({"error": "Subscription failed"}), 500

    except Exception as e:
        logger.exception("Unexpected error in /subscribe")
        return jsonify({"error": "Internal error. Please try again later."}), 500

# ======================
# NLLB TRANSLATION FUNCTIONS
# ======================

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    if not text.strip():
        return "", "en"
    if client is None:
        return text, "en"

    candidate_langs = ["am", "om", "ti", "so", "aa", "sid", "wal", "en"]
    for lang_code in candidate_langs:
        if lang_code == "en":
            return text, "en"
        try:
            src_nllb = NLLB_LANG_MAP[lang_code]
            translated = client.translation(text, src_lang=src_nllb, tgt_lang="eng_Latn")
            if translated.strip() != text.strip():
                return translated.strip(), lang_code
        except Exception:
            continue
    return text, "en"

def translate_text(text: str, target_lang: str) -> str:
    if target_lang == "en" or not text.strip() or client is None:
        return text
    if target_lang not in NLLB_LANG_MAP:
        logger.warning(f"Unsupported target language: {target_lang}")
        return text
    try:
        result = client.translation(text, src_lang="eng_Latn", tgt_lang=NLLB_LANG_MAP[target_lang])
        return result.strip()
    except Exception as e:
        logger.warning(f"NLLB translation to {target_lang} failed: {e}")
        return text

# ======================
# GROQ AI FUNCTION
# ======================

def ask_groq_ai(question: str) -> str:
    groq_api_key = os.getenv("GROQ_API_KEY")
    model_name = "llama-3.3-70b-versatile"
    
    if not groq_api_key:
        return "AI is not configured. Please set GROQ_API_KEY."

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Finedata AI, Ethiopia's expert assistant. "
                            "Answer ONLY about Ethiopia: do not mention anything about your time cutoff just answer when you know and say i dont have that information when it is beyond what you have. "
                            "If asked about non-Ethiopia topics, say: 'I specialize in Ethiopia. Please ask about Ethiopian data, agriculture, economy, or cities.' "
                            "Keep answers concise (1-3 sentences), factual, and helpful. Never make up data."
                        )
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=30
        )
        
        logger.info(f"Groq API status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            else:
                return "I received your question but had trouble formatting the response."
        else:
            logger.error(f"Groq error {response.status_code}: {response.text}")
            return "I'm having trouble thinking right now. Try again?"
            
    except Exception:
        logger.exception("Groq AI request failed")
        return "AI service is temporarily unavailable."

# ======================
# MAIN ENDPOINT
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    try:
        data = request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        user_question = data.get("question", "").strip()
        target_lang = data.get("language", "en")

        if not user_question:
            return jsonify({"error": "Please ask a question."}), 400
        if target_lang not in SUPPORTED_LANGUAGES:
            target_lang = "en"

        english_question, detected_lang = detect_and_translate_to_english(user_question)
        answer_en = ask_groq_ai(english_question)
        answer_translated = translate_text(answer_en, target_lang)

        return jsonify({
            "question_original": user_question,
            "question_english": english_question,
            "detected_language": detected_lang,
            "answer_english": answer_en,
            "answer_translated": answer_translated,
            "language": target_lang
        })
    except Exception as e:
        logger.exception("Error in /ask-ai")
        return jsonify({"error": "AI request failed"}), 500

# ======================
# STATIC FILES
# ======================

@app.route('/ai-chat.html')
def ai_chat_page():
    return send_from_directory('.', 'ai-chat.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# ======================
# STARTUP VALIDATION
# ======================

if __name__ == '__main__':
    if not os.getenv("EMAILOCTOPUS_API_KEY"):
        logger.warning("EMAILOCTOPUS_API_KEY not set — email subscription will fail.")
    if not os.getenv("EMAILOCTOPUS_LIST_ID"):
        logger.warning("EMAILOCTOPUS_LIST_ID not set — subscription list unknown.")
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY is not set — AI will be disabled.")
    if not os.getenv("HF_API_KEY"):
        logger.warning("HF_API_KEY is not set — NLLB translation will be disabled.")

    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
