# app.py
import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Supported languages (LibreTranslate codes)
SUPPORTED_LANGUAGES = {"en", "am", "om", "fr", "es", "ar"}

# ======================
# EMAIL SUBSCRIPTION (Buttondown - Free & Simple)
# ======================

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    email = data.get("email", "").strip() if data else ""
    if not email:
        return jsonify({"error": "Email is required"}), 400

    api_key = os.getenv("BUTTONDOWN_API_KEY")
    if not api_key:
        logger.error("Buttondown API key missing")
        return jsonify({"error": "Subscription service not configured"}), 500

    try:
        response = requests.post(
            "https://api.buttondown.email/v1/subscribers",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json"
            },
            json={"email": email},
            timeout=10
        )
        if response.status_code == 201:
            return jsonify({"message": "Subscribed successfully!"})
        elif response.status_code == 400 and "already exists" in response.text:
            return jsonify({"error": "Email already subscribed"}), 422
        else:
            logger.error(f"Buttondown error {response.status_code}: {response.text}")
            return jsonify({"error": "Subscription failed"}), 500
    except Exception as e:
        logger.exception("Buttondown request failed")
        return jsonify({"error": "Email service unavailable"}), 500

# ======================
# TRANSLATION FUNCTIONS
# ======================

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    """Returns (english_text, detected_lang)"""
    if not text.strip():
        return "", "en"
    
    try:
        # Detect language
        detect_resp = requests.post(
            "https://libretranslate.de/detect",
            json={"q": text[:100]},
            timeout=5
        )
        detected = "en"
        if detect_resp.status_code == 200:
            data = detect_resp.json()
            if isinstance(data, list) and len(data) > 0:
                detected = data[0].get("language", "en")
        
        # Translate to English if needed
        if detected != "en":
            trans_resp = requests.post(
                "https://libretranslate.de/translate",
                json={"q": text, "source": detected, "target": "en"},
                timeout=8
            )
            if trans_resp.status_code == 200:
                trans_data = trans_resp.json()
                if isinstance(trans_data, dict):
                    return trans_data.get("translatedText", text), detected
        
        return text, detected
    except Exception as e:
        logger.warning(f"Translation fallback: {e}")
        return text, "en"

def translate_text(text: str, target_lang: str) -> str:
    """Translate English text to target language"""
    if target_lang == "en" or not text:
        return text
    try:
        resp = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "en", "target": target_lang},
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("translatedText", text) if isinstance(data, dict) else text
    except Exception as e:
        logger.warning(f"Translation to {target_lang} failed: {e}")
    return text

# ======================
# GROQ AI FUNCTION
# ======================

def ask_groq_ai(question: str) -> str:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return "AI is not configured. Please set GROQ_API_KEY."

    messages = [
        {
            "role": "system",
            "content": (
                "You are Finedata AI, Ethiopia's expert assistant. "
                "Answer ONLY about Ethiopia: economy, agriculture, weather, demographics, culture, history, cities, crops, languages, etc. "
                "If asked about non-Ethiopia topics, say: 'I specialize in Ethiopia. Please ask about Ethiopian data, agriculture, economy, or cities.' "
                "Keep answers concise (1-3 sentences), factual, and helpful. Never make up data."
            )
        },
        {"role": "user", "content": question}
    ]

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
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
            logger.error(f"Groq error {response.status_code}: {response.text}")
            return "I'm having trouble thinking right now. Try again?"
    except Exception as e:
        logger.exception("Groq request failed")
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

    # Step 1: Translate input to English
    english_question, detected_lang = detect_and_translate_to_english(user_question)

    # Step 2: Ask Groq AI
    answer_en = ask_groq_ai(english_question)

    # Step 3: Translate answer to user's language
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
