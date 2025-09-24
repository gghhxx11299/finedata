# app.py
import os
import time
import logging
from datetime import datetime
from functools import wraps
from typing import Dict, Optional, Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ======================
# CACHING
# ======================

_CACHE = {}
_CACHE_TIMEOUT = 3600

def cached(timeout: int = _CACHE_TIMEOUT):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            now = time.time()
            if key in _CACHE:
                value, timestamp = _CACHE[key]
                if now - timestamp < timeout:
                    return value
            result = func(*args, **kwargs)
            _CACHE[key] = (result, now)
            return result
        return wrapper
    return decorator

# ======================
# DATA FUNCTIONS
# ======================

@cached()
def get_gdp_per_capita() -> str:
    try:
        resp = requests.get("https://api.worldbank.org/v2/country/ETH/indicator/NY.GDP.PCAP.CD?format=json&per_page=1", timeout=8)
        data = resp.json()
        if len(data) > 1 and data[1]:
            val = data[1][0]["value"]
            return f"${int(val):,}" if val else "N/A"
    except Exception as e:
        logger.error(f"GDP error: {e}")
    return "N/A"

@cached()
def get_inflation_rate() -> str:
    try:
        resp = requests.get("https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json&per_page=1", timeout=8)
        data = resp.json()
        if len(data) > 1 and data[1]:
            val = data[1][0]["value"]
            return f"{val:.1f}%" if val else "N/A"
    except Exception as e:
        logger.error(f"Inflation error: {e}")
    return "N/A"

@cached()
def get_exchange_rates() -> Dict[str, Any]:
    try:
        resp = requests.get("https://api.exchangerate-api.com/v4/latest/ETB", timeout=8)
        data = resp.json()
        rates = data.get("rates", {})
        return {
            "USD": round(1 / rates.get("USD", 0), 2) if rates.get("USD") else "N/A",
            "EUR": round(1 / rates.get("EUR", 0), 2) if rates.get("EUR") else "N/A",
            "GBP": round(1 / rates.get("GBP", 0), 2) if rates.get("GBP") else "N/A"
        }
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
    return {"USD": "N/A", "EUR": "N/A", "GBP": "N/A"}

@cached()
def get_population() -> str:
    try:
        resp = requests.get("https://api.worldbank.org/v2/country/ETH/indicator/SP.POP.TOTL?format=json&per_page=1", timeout=8)
        data = resp.json()
        if len(data) > 1 and data[1]:
            val = data[1][0]["value"]
            return f"{int(val):,}" if val else "N/A"
    except Exception as e:
        logger.error(f"Population error: {e}")
    return "N/A"

def get_agricultural_data(location: str) -> str:
    crops = {
        "Addis Ababa": "Vegetables, teff, enset",
        "Jimma": "Coffee, maize, teff",
        "Hawassa": "Vegetables, fruits, dairy",
        "Bahir Dar": "Teff, maize, pulses",
        "Mekelle": "Wheat, barley, teff",
        "Arba Minch": "Bananas, cotton, sorghum"
    }
    return crops.get(location.title(), "Coffee, teff, maize (national staples)")

def get_planting_seasons(location: str) -> str:
    base = "Ethiopia uses two main rainy seasons:"
    belg = "• **Belg** (Feb–Apr): Short rains"
    kiremt = "• **Kiremt** (June–Sept): Long rains"
    if "addis" in location.lower():
        return f"{base} {belg} {kiremt}. In Addis Ababa, both are used."
    return f"{base} {belg} {kiremt}."

# ======================
# WEATHER
# ======================

try:
    from weather_collector import EthiopianWeatherForecast
    weather_collector = EthiopianWeatherForecast(os.getenv("WEATHER_API_KEY"))
except Exception as e:
    logger.error(f"Weather collector init failed: {e}")
    weather_collector = None

def get_weather_data(location: str) -> Optional[str]:
    if not weather_collector:
        return None
    try:
        coords = weather_collector.get_location_coords(location)[1]
        live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
        if live_data and 'current' in live_:  # ✅ CORRECTED: complete variable name + colon
            current = live_data['current']
            today = live_data['forecast']['forecastday'][0]['day']
            return (
                f"Live weather in {location}: {current['temp_c']}°C, {current['condition']['text']}. "
                f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C."
            )
    except Exception as e:
        logger.error(f"Weather error: {e}")
    return None

# ======================
# TRANSLATION
# ======================

SUPPORTED_LANGUAGES = {"en", "am", "om", "fr", "es", "ar"}

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if not text or source_lang == target_lang or target_lang == "en":
        return text
    try:
        resp = requests.post("https://libretranslate.de/translate", json={
            "q": text, "source": source_lang, "target": target_lang
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("translatedText", text) if isinstance(data, dict) else text
    except Exception as e:
        logger.warning(f"Translation error: {e}")
    return text

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    if not text.strip():
        return "", "en"
    try:
        resp = requests.post("https://libretranslate.de/detect", json={"q": text[:100]}, timeout=5)
        detected = "en"
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:  # ✅ CORRECTED: complete condition + colon
                detected = data[0].get("language", "en")
        if detected != "en":
            trans_resp = requests.post("https://libretranslate.de/translate", json={
                "q": text, "source": detected, "target": "en"
            }, timeout=8)
            if trans_resp.status_code == 200:
                trans_data = trans_resp.json()
                if isinstance(trans_data, dict):
                    return trans_data.get("translatedText", text), detected
        return text, detected
    except Exception as e:
        logger.warning(f"Translation fallback: {e}")
        return text, "en"

# ======================
# AI RESPONSE
# ======================

def is_in_scope(question: str) -> bool:
    q = question.lower()
    keywords = ["ethiopia", "addis", "jimma", "weather", "crop", "plant", "gdp", "inflation", "population", "exchange", "teff", "kiremt", "belg"]
    return any(kw in q for kw in keywords)

def generate_ai_response(question: str) -> str:
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return "AI assistant is not configured. Contact support."

    if not is_in_scope(question):
        return "We're still working on this! Please ask something about Ethiopia's economy, agriculture, weather, or population."

    # Build context
    context = f"""
You are Finedata AI for Ethiopia. Use ONLY this data:
- GDP per capita: {get_gdp_per_capita()}
- Inflation: {get_inflation_rate()}
- Exchange: {get_exchange_rates()}
- Population: {get_population()}
- Planting: {get_planting_seasons("Addis Ababa")}
- Crops: {get_agricultural_data("Addis Ababa")}

Answer concisely in English. If unsure, say "I don't have that data."
Question: {question}
Answer:
"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "https://finedata.onrender.com",
                "X-Title": "Finedata Ethiopia AI"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": context}],
                "temperature": 0.2,
                "max_tokens": 250
            },
            timeout=25
        )
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"].strip()
            return answer.split("Question:")[0].strip() or "I couldn't generate a response."
        else:
            return "I'm having trouble processing your request."
    except Exception as e:
        logger.exception("OpenRouter error")
        return "AI service is temporarily unavailable."

# ======================
# ROUTES
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    if not data:  # ✅ CORRECTED: complete condition
        return jsonify({"error": "Invalid JSON"}), 400

    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a question."}), 400
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"

    english_question, _ = detect_and_translate_to_english(user_question)
    answer_en = generate_ai_response(english_question)
    answer_translated = translate_text(answer_en, "en", target_lang)

    return jsonify({
        "answer_translated": answer_translated,
        "answer_english": answer_en,
        "language": target_lang
    })

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
