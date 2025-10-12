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

# Initialize Hugging Face client (lazy init; will error on use if token missing)
try:
    client = InferenceClient("facebook/nllb-200-distilled-600M", token=HF_TOKEN)
except Exception as e:
    client = None
    logger.error(f"Failed to initialize Hugging Face client: {e}")

# NLLB uses ISO 639-3 + script codes
NLLB_LANG_MAP = {
    "en": "eng_Latn",
    "am": "amh_Ethi",   # Amharic
    "om": "orm_Latn",   # Oromo (typically Latin script)
    "ti": "tir_Ethi",   # Tigrinya
    "so": "som_Latn",   # Somali
    "aa": "aar_Latn",   # Afar
    "sid": "sid_Latn",  # Sidamo
    "wal": "wal_Ethi",  # Wolaytta
}

SUPPORTED_LANGUAGES = set(NLLB_LANG_MAP.keys())

# ======================
# EMAIL SUBSCRIPTION (EmailOctopus)
# ======================

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    email = data.get("email", "").strip() if data else ""
    if not email:
        return jsonify({"error": "Email is required"}), 400

    api_key = os.getenv("EMAILOCTOPUS_API_KEY")
    list_id = os.getenv("EMAILOCTOPUS_LIST_ID")

    if not api_key or not list_id:
        logger.error("EmailOctopus API_KEY or LIST_ID missing in environment variables")
        return jsonify({"error": "Subscription service not configured"}), 500

    try:
        url = f"https://emailoctopus.com/api/1.6/lists/{list_id}/contacts?api_key={api_key}"
        response = requests.post(
            url,
            data={
                "email_address": email,
                "status": "SUBSCRIBED"
            },
            timeout=10
        )

        logger.info(f"EmailOctopus response {response.status_code}: {response.text}")

        if response.status_code in (200, 201):
            return jsonify({"message": "Subscribed successfully!"})
        elif response.status_code == 400:
            resp_json = response.json()
            error_code = resp_json.get("error", {}).get("code")
            if error_code == "MEMBER_EXISTS":
                return jsonify({"error": "Email already subscribed"}), 422
            else:
                logger.warning(f"EmailOctopus validation error: {resp_json}")
                return jsonify({"error": "Invalid email address"}), 400
        else:
            logger.error(f"EmailOctopus error {response.status_code}: {response.text}")
            return jsonify({"error": "Subscription failed"}), 500

    except Exception as e:
        logger.exception("EmailOctopus request failed")
        return jsonify({"error": "Email service unavailable"}), 500

# ======================
# NLLB TRANSLATION FUNCTIONS
# ======================

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    """Heuristic language detection + translate to English using NLLB."""
    if not text.strip():
        return "", "en"
    
    if client is None:
        return text, "en"

    # Prioritize Ethiopian languages + English
    candidate_langs = ["am", "om", "ti", "so", "aa", "sid", "wal", "en"]
    
    for lang_code in candidate_langs:
        if lang_code == "en":
            return text, "en"
        
        try:
            src_nllb = NLLB_LANG_MAP[lang_code]
            translated = client.translation(
                text,
                src_lang=src_nllb,
                tgt_lang="eng_Latn"
            )
            # If translation is different, assume it worked
            if translated.strip() != text.strip():
                return translated.strip(), lang_code
        except Exception:
            continue  # Try next language
    
    # Fallback: assume English
    return text, "en"


def translate_text(text: str, target_lang: str) -> str:
    """Translate English text to target language using NLLB."""
    if target_lang == "en" or not text.strip() or client is None:
        return text

    if target_lang not in NLLB_LANG_MAP:
        logger.warning(f"Unsupported target language: {target_lang}")
        return text

    try:
        result = client.translation(
            text,
            src_lang="eng_Latn",
            tgt_lang=NLLB_LANG_MAP[target_lang]
        )
        return result.strip()
    except Exception as e:
        logger.warning(f"NLLB translation to {target_lang} failed: {e}")
        return text

# ======================
# POE AI FUNCTION
# ======================

def ask_poe_ai(question: str) -> str:
    poe_token = os.getenv("POE_API_KEY")
    if not poe_token:
        return "AI is not configured. Please set POE_API_KEY."

    messages = [
        {
            "role": "system",
            "content": (
                "You are Finedata AI, Ethiopia's expert assistant. "
                "Answer ONLY about Ethiopia: economy, agriculture, weather, demographics, culture, history, cities, crops, languages, etc. do not mention anything about your time cutoff just answer when you know and say i dont have thag information when it is beyond what you have. "
                "If asked about non-Ethiopia topics, say: 'I specialize in Ethiopia. Please ask about Ethiopian data, agriculture, economy, or cities.' "
                "Keep answers concise (1-3 sentences), factual, and helpful. Never make up data."
            )
        },
        {"role": "user", "content": question}
    ]

    try:
        response = requests.post(
            "https://api.poe.com/bot/finedata-ai/chat",
            headers={
                "Authorization": f"Bearer {poe_token}",
                "Content-Type": "application/json"
            },
            json={
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 300
            },
            timeout=20
        )
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Poe AI error {response.status_code}: {response.text}")
            return "I'm having trouble thinking right now. Try again?"
    except Exception as e:
        logger.exception("Poe AI request failed")
        return "AI service is temporarily unavailable."

# ======================
# MAIN ENDPOINT
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a question."}), 400
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"

    english_question, detected_lang = detect_and_translate_to_english(user_question)
    answer_en = ask_poe_ai(english_question)
    answer_translated = translate_text(answer_en, target_lang)

    return jsonify({
        "question_original": user_question,
        "question_english": english_question,
        "detected_language": detected_lang,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "language": target_lang
    })

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
    if not os.getenv("POE_API_KEY"):
        logger.warning("POE_API_KEY is not set — AI will be disabled.")
    if not os.getenv("HF_API_KEY"):
        logger.warning("HF_API_KEY is not set — NLLB translation will be disabled.")

    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
