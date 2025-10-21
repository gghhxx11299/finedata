# app.py
import os
import logging
import re
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Optional: Only import anthropic if you plan to use it
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logging.warning("anthropic package not installed. Farming AI will be disabled.")

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# === NLLB SETUP ===
HF_TOKEN = os.getenv("HF_API_KEY")
if not HF_TOKEN:
    logger.warning("HF_API_KEY not set — NLLB translation will be disabled.")

client = None
if HF_TOKEN:
    try:
        client = InferenceClient("facebook/nllb-200-distilled-600M", token=HF_TOKEN)
    except Exception as e:
        logger.error(f"Failed to initialize Hugging Face client: {e}")

# NLLB uses ISO 639-3 + script codes
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
        logger.error("EmailOctopus API_KEY or LIST_ID missing")
        return jsonify({"error": "Subscription service not configured"}), 500

    try:
        # ✅ FIXED: No extra spaces in URL
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
                return jsonify({"error": "Invalid email address"}), 400
        else:
            logger.error(f"EmailOctopus error {response.status_code}: {response.text}")
            return jsonify({"error": "Subscription failed"}), 500

    except Exception as e:
        logger.exception("EmailOctopus request failed")
        return jsonify({"error": "Email service unavailable"}), 500

# ======================
# TRANSLATION FUNCTIONS
# ======================

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    if not text.strip():
        return "", "en"
    
    if client is None:
        return text, "en"

    candidate_langs = ["am", "om", "ti", "so", "aa", "sid", "wal"]
    for lang_code in candidate_langs:
        try:
            src_nllb = NLLB_LANG_MAP[lang_code]
            translated = client.translation(
                text,
                src_lang=src_nllb,
                tgt_lang="eng_Latn"
            ).strip()
            if translated and translated != text.strip():
                return translated, lang_code
        except Exception as e:
            logger.debug(f"Translation from {lang_code} failed: {e}")
            continue
    
    return text, "en"

def translate_text(text: str, target_lang: str) -> str:
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
# GROQ AI FUNCTION — GENERAL PURPOSE
# ======================

def ask_groq_ai(question: str) -> str:
    groq_api_key = os.getenv("GROQ_API_KEY")
    model_name = "qwen/qwen3-32b"

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
                            "Answer ONLY about Ethiopia. NEVER show your reasoning, thoughts, or internal process. "
                            "NEVER say 'Okay', 'I think', 'Let me check', or explain how you got the answer. "
                            "If asked about non-Ethiopia topics, respond exactly: "
                            "'I specialize in Ethiopia. Please ask about Ethiopian data, agriculture, economy, or cities.' "
                            "Keep answers concise (1–3 sentences), factual, and helpful. Never make up data."
                        )
                    },
                    {"role": "user", "content": question}
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
                raw_reply = data["choices"][0]["message"]["content"].strip()
                cleaned = re.sub(r'(\<think\>.*?\<\/think\>)', '', raw_reply, flags=re.DOTALL | re.IGNORECASE)
                return cleaned.strip()
            else:
                logger.warning(f"Groq response missing choices: {data}")
                return "I received your question but had trouble generating a response."
        else:
            try:
                error_msg = response.json().get("error", {}).get("message", response.text)
            except:
                error_msg = response.text
            logger.error(f"Groq error {response.status_code}: {error_msg}")
            return "I'm having trouble thinking right now. Try again?"
            
    except Exception as e:
        logger.exception("Groq AI request failed")
        return "AI service is temporarily unavailable."

# ======================
# ANTHROPIC AI FOR FARMING 
# ======================

def ask_claude_farmer(question: str) -> str:
    if not ANTHROPIC_AVAILABLE:
        return "Farming AI requires the 'anthropic' package. Not available."

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        return "Farming AI is not configured. Please set ANTHROPIC_API_KEY."

    try:
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        message = client.messages.create(
            model="Claude-Sonnet-4.5",  
            max_tokens=400,
            temperature=0.2,
            system=(
                "You are the FineData Ethiopia Farming Advisor. Provide practical, safe, and locally relevant advice based ONLY on Ethiopian agricultural guidelines from EIAR, Ministry of Agriculture, FAO Ethiopia, and NMA.\n"
                "- Reference Ethiopia’s three seasons: Kiremt (Jun–Sep), Belg (Feb–May), Bega (Oct–Jan)\n"
                "- Mention regional risks: e.g., 'Fall armyworm in Benishangul', 'Frost in Amhara highlands'\n"
                "- Recommend ONLY inputs available in Ethiopia (e.g., DAP, urea, neem oil—not banned or imported chemicals)\n"
                "- If the user mentions a region, tailor advice to that woreda’s typical conditions\n"
                "- NEVER hallucinate chemical names, yields, or policy details\n"
                "- If unsure, say: 'Consult your woreda agronomist.'\n"
                "- Keep answers concise (1–3 sentences)."
            ),
            messages=[{"role": "user", "content": question}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.exception("Anthropic farming AI failed")
        return "Farming advisor is temporarily unavailable. Please try again."

# ======================
# MAIN AI ENDPOINT (GENERAL)
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

# ======================
# FARMING-SPECIFIC AI ENDPOINT
# ======================

@app.route('/ask-farmer', methods=['POST'])
def ask_farmer():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a farming question."}), 400
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"

    english_question, detected_lang = detect_and_translate_to_english(user_question)
    answer_en = ask_claude_farmer(english_question)
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
# STATIC FILE SERVING
# ======================

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/ai-chat.html')
def ai_chat_page():
    return send_from_directory('.', 'ai-chat.html')

@app.route('/weather.html')
def weather_page():
    return send_from_directory('.', 'weather.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# ======================
# STARTUP VALIDATION
# ======================

if __name__ == '__main__':
    required_vars = ["GROQ_API_KEY"]
    optional_vars = ["HF_API_KEY", "EMAILOCTOPUS_API_KEY", "EMAILOCTOPUS_LIST_ID", "ANTHROPIC_API_KEY"]
    
    for var in required_vars:
        if not os.getenv(var):
            logger.critical(f"Missing required environment variable: {var}")
    
    for var in optional_vars:
        if not os.getenv(var):
            logger.warning(f"Optional variable missing: {var}")

    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
