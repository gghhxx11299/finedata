# app.py
"""
Finedata Ethiopia AI Backend
- All-in-one data hub for Ethiopia: economic, demographic, agricultural, weather, exchange, forecasts
- Multilingual AI assistant (en, am, om, fr, es, ar)
- Dynamic context-aware responses via OpenRouter + Llama-3
- Fallback for unsupported queries
- Built for render.com deployment
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Any

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# ======================
# CONFIGURATION & SETUP
# ======================

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Environment variables
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LIBRETRANSLATE_URL = "https://libretranslate.de/translate"

# Validate critical keys
if not WEATHER_API_KEY:
    logger.warning("WEATHER_API_KEY not set – weather features will fail")
if not OPENROUTER_API_KEY:
    logger.warning("OPENROUTER_API_KEY not set – AI will be disabled")

# ======================
# CACHING UTILITY
# ======================

_CACHE = {}
_CACHE_TIMEOUT = 3600  # 1 hour

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
# DATA SOURCES — ECONOMIC
# ======================

@cached()
def get_gdp_per_capita() -> str:
    try:
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/NY.GDP.PCAP.CD?format=json&per_page=1",
            timeout=8
        )
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
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json&per_page=1",
            timeout=8
        )
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
            "GBP": round(1 / rates.get("GBP", 0), 2) if rates.get("GBP") else "N/A",
            "SAR": round(1 / rates.get("SAR", 0), 2) if rates.get("SAR") else "N/A"
        }
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
    return {"USD": "N/A", "EUR": "N/A", "GBP": "N/A", "SAR": "N/A"}

@cached()
def get_trade_balance() -> str:
    # Placeholder – could connect to UN Comtrade or NBE
    return "Ethiopia runs a trade deficit; imports exceed exports (mainly machinery, oil, chemicals)."

@cached()
def get_2025_economic_forecast() -> str:
    return (
        "2025 Outlook: GDP growth projected at 6.2%. Inflation expected to ease to 12-14%. "
        "Key drivers: industrial parks, services sector, and post-conflict recovery."
    )

# ======================
# DATA SOURCES — DEMOGRAPHIC
# ======================

@cached()
def get_population() -> str:
    try:
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/SP.POP.TOTL?format=json&per_page=1",
            timeout=8
        )
        data = resp.json()
        if len(data) > 1 and data[1]:
            val = data[1][0]["value"]
            return f"{int(val):,}" if val else "N/A"
    except Exception as e:
        logger.error(f"Population error: {e}")
    return "N/A"

@cached()
def get_urbanization_rate() -> str:
    return "22% of Ethiopians live in urban areas (2024 estimate)."

@cached()
def get_life_expectancy() -> str:
    return "67 years (World Bank, 2023)."

@cached()
def get_literacy_rate() -> str:
    return "52% adult literacy rate (UNESCO, latest)."

# ======================
# DATA SOURCES — AGRICULTURE
# ======================

def get_agricultural_data(location: str) -> str:
    crops = {
        "Addis Ababa": "Vegetables (onions, tomatoes), teff, enset (false banana)",
        "Jimma": "Coffee (Arabica), maize, teff, spices",
        "Hawassa": "Vegetables, fruits (avocado, mango), dairy, fish",
        "Bahir Dar": "Teff, maize, pulses, rice (near Lake Tana)",
        "Mekelle": "Wheat, barley, teff, sorghum",
        "Arba Minch": "Bananas, cotton, sorghum, maize",
        "Dire Dawa": "Khat, maize, vegetables",
        "Gondar": "Teff, wheat, pulses, honey"
    }
    return crops.get(location.title(), "Coffee, teff, maize, sorghum (national staples)")

def get_soil_info(location: str) -> str:
    soils = {
        "Addis Ababa": "Volcanic Andosols – deep, fertile, well-drained",
        "Jimma": "Nitisols – red, clay-rich, excellent for coffee",
        "Mekelle": "Vertisols (black cotton soil) – high fertility but hard when dry",
        "Arba Minch": "Vertisols & Cambisols – moderate fertility, irrigation needed",
        "Hawassa": "Andosols & Vertisols – good for horticulture"
    }
    return soils.get(location.title(), "Soil varies by agro-ecological zone.")

def get_planting_seasons(location: str) -> str:
    base = "Ethiopia uses two main rainy seasons for planting:"
    belg = "• **Belg** (Feb–Apr): Short rains – barley, wheat, pulses, early vegetables."
    kiremt = "• **Kiremt** (June–Sept): Long rains – teff, maize, sorghum, coffee."
    
    loc_lower = location.lower()
    if "addis" in loc_lower:
        return f"{base} {belg} {kiremt} In Addis Ababa, both seasons are used, with Kiremt being more reliable for teff."
    elif "jimma" in loc_lower or "coffee" in loc_lower:
        return f"{base} {kiremt} is critical for coffee flowering. Belg is less significant in the southwest."
    elif "mekelle" in loc_lower or "tigray" in loc_lower:
        return f"{base} {belg} is vital in Tigray due to shorter Kiremt. Drought risk is high."
    else:
        return f"{base} {belg} {kiremt} Local practices may vary by elevation and microclimate."

def get_2025_crop_forecast() -> str:
    return (
        "2025 Crop Forecast: Teff (+4%), Maize (+6%), Coffee (+3%) due to improved rainfall and extension services. "
        "Risks: locusts in eastern lowlands, price volatility."
    )

def get_livestock_data() -> str:
    return "Ethiopia has Africa’s largest livestock population: 65M cattle, 40M sheep, 50M goats."

# ======================
# DATA SOURCES — WEATHER & FORECASTS
# ======================

try:
    from weather_collector import EthiopianWeatherForecast
    weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY)
except Exception as e:
    logger.error(f"Failed to load weather_collector: {e}")
    weather_collector = None

def get_weather_data(location: str) -> Optional[str]:
    if not weather_collector:
        return None
    try:
        coords = weather_collector.get_location_coords(location)[1]
        live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
        if live_data and 'current' in live_data:  # ✅ FIXED SYNTAX
            current = live_data['current']
            today = live_data['forecast']['forecastday'][0]['day']
            return (
                f"Live weather in {location}: {current['temp_c']}°C, {current['condition']['text']}. "
                f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C."
            )
    except Exception as e:
        logger.error(f"Weather error for {location}: {e}")
    return None

def get_kiremt_forecast_2025() -> str:
    return (
        "Kiremt 2025 Outlook: Near-normal rainfall expected (June–Sept). "
        "Slight delay in onset possible in central highlands. Good conditions for teff and maize."
    )

# ======================
# TRANSLATION LAYER
# ======================

SUPPORTED_LANGUAGES = {
    "en": "English",
    "am": "Amharic",
    "om": "Oromo",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic"
}

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if not text or source_lang == target_lang or target_lang == "en":
        return text
    try:
        payload = {
            "q": text,
            "source": source_lang,
            "target": target_lang
        }
        resp = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("translatedText", text)
    except Exception as e:
        logger.warning(f"Translation failed ({source_lang}→{target_lang}): {e}")
    return text

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    """Returns (english_text, detected_source_lang)"""
    if not text.strip():
        return "", "en"
    try:
        # First, detect language
        detect_resp = requests.post(
            "https://libretranslate.de/detect",
            json={"q": text[:100]},  # limit for speed
            timeout=5
        )
        if detect_resp.status_code == 200:
            detections = detect_resp.json()
            if detections and isinstance(detections, list):
                detected = detections[0].get("language", "en")
                if detected != "en":
                    translated = translate_text(text, detected, "en")
                    return translated, detected
        return text, "en"
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return text, "en"

# ======================
# AI ENGINE — OPENROUTER
# ======================

def is_query_in_scope(question: str) -> bool:
    """Check if query is about Ethiopia and within our data domains"""
    q = question.lower()
    ethiopia_keywords = ["ethiopia", "addis", "jimma", "hawassa", "bahir", "mekelle", "teff", "birr", "etb", "kiremt", "belg"]
    domain_keywords = [
        "weather", "rain", "forecast", "plant", "crop", "soil", "agri", "farm",
        "gdp", "inflation", "economy", "exchange", "rate", "usd", "eur",
        "population", "people", "urban", "demographic",
        "2025", "outlook", "prediction"
    ]
    return any(kw in q for kw in ethiopia_keywords) or any(kw in q for kw in domain_keywords)

def generate_ai_response(question: str) -> str:
    if not OPENROUTER_API_KEY:
        return "AI assistant is not configured. Contact support."

    if not is_query_in_scope(question):
        return "We're still working on this! Please ask something about Ethiopia's economy, agriculture, weather, population, or exchange rates."

    # Gather all data
    gdp = get_gdp_per_capita()
    inflation = get_inflation_rate()
    exchange = get_exchange_rates()
    population = get_population()
    urban = get_urbanization_rate()
    life_exp = get_life_expectancy()
    literacy = get_literacy_rate()
    trade = get_trade_balance()
    econ_forecast = get_2025_economic_forecast()
    crop_forecast = get_2025_crop_forecast()
    kiremt_forecast = get_kiremt_forecast_2025()
    livestock = get_livestock_data()

    context = f"""
You are Finedata AI, Ethiopia’s official data assistant. Use ONLY the following verified data.

ECONOMIC (2024–2025):
- GDP per capita: {gdp}
- Inflation: {inflation}
- Exchange: 1 USD = {exchange['USD']} ETB, 1 EUR = {exchange['EUR']} ETB
- Trade: {trade}
- 2025 Economic Forecast: {econ_forecast}

DEMOGRAPHIC:
- Population: {population}
- Urbanization: {urban}
- Life Expectancy: {life_exp}
- Literacy: {literacy}

AGRICULTURE:
- 2025 Crop Forecast: {crop_forecast}
- Livestock: {livestock}
- Planting Seasons: Belg (Feb–Apr), Kiremt (June–Sept)
- Soil & crops vary by region (e.g., Jimma: coffee/nitisols; Mekelle: teff/vertisols)

WEATHER & FORECASTS:
- Kiremt 2025: {kiremt_forecast}
- Live weather available for any Ethiopian city

RULES:
1. If user asks about a city, assume Ethiopia unless specified.
2. For planting/soil/weather, use regional data if known.
3. NEVER guess numbers. If data missing, say so.
4. Keep answers concise (1–3 sentences).
5. If question is outside Ethiopia or scope, say: "We're still working on this! Please ask something about Ethiopia..."

Question: {question}
Answer:
"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
            # Clean artifacts
            answer = answer.split("Question:")[0].split("Answer:")[0].strip()
            return answer if answer else "I couldn't generate a response."
        else:
            logger.error(f"OpenRouter error {resp.status_code}: {resp.text}")
            return "I'm having trouble processing your request right now."
    except Exception as e:
        logger.exception("OpenRouter exception")
        return "AI service is temporarily unavailable. Please try again."

# ======================
# MAIN API ENDPOINT
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

    # Step 1: Translate input to English + detect source
    english_question, detected_lang = detect_and_translate_to_english(user_question)

    # Step 2: Generate AI response in English
    answer_en = generate_ai_response(english_question)

    # Step 3: Translate answer to target language
    answer_translated = translate_text(answer_en, "en", target_lang)

    return jsonify({
        "question_original": user_question,
        "question_english": english_question,
        "detected_language": detected_lang,
        "target_language": target_lang,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "timestamp": datetime.utcnow().isoformat()
    })

# ======================
# STATIC FILE SERVING
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
# HEALTH CHECK
# ======================

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "weather_collector": weather_collector is not None,
        "openrouter_configured": bool(OPENROUTER_API_KEY)
    })

# ======================
# MAIN ENTRY
# ======================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
