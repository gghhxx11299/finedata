# app.py
import os
import time
import logging
from datetime import datetime
from functools import wraps
from typing import Dict, Optional, Any, Tuple

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
            try:
                result = func(*args, **kwargs)
                _CACHE[key] = (result, now)
                return result
            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                # Return cached value even if expired if available
                if key in _CACHE:
                    return _CACHE[key][0]
                raise
        return wrapper
    return decorator

# ======================
# DATA FUNCTIONS
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
            "GBP": round(1 / rates.get("GBP", 0), 2) if rates.get("GBP") else "N/A"
        }
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
    return {"USD": "N/A", "EUR": "N/A", "GBP": "N/A"}

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

def get_agricultural_data(location: str) -> str:
    """Get agricultural data for a specific location in Ethiopia."""
    if not location or not isinstance(location, str):
        return "Coffee, teff, maize (national staples)"
    
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
    """Get planting season information for Ethiopia."""
    if not location or not isinstance(location, str):
        location = "Ethiopia"
    
    base = "Ethiopia uses two main rainy seasons:"
    belg = "• Belg (Feb–Apr): Short rains"
    kiremt = "• Kiremt (June–Sept): Long rains"
    
    if "addis" in location.lower():
        return f"{base} {belg} {kiremt}. In Addis Ababa, both are used."
    return f"{base} {belg} {kiremt}."

# ======================
# WEATHER
# ======================

try:
    from weather_collector import EthiopianWeatherForecast
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
    weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY) if WEATHER_API_KEY else None
    if weather_collector:
        logger.info("Weather collector initialized successfully")
    else:
        logger.warning("Weather API key not found - weather features disabled")
except ImportError:
    logger.warning("weather_collector module not available")
    weather_collector = None
except Exception as e:
    logger.error(f"Weather collector init failed: {e}")
    weather_collector = None

def get_weather_data(location: str) -> Optional[str]:
    """Get weather data for a specific location."""
    if not weather_collector or not location:
        return None
    try:
        coords_result = weather_collector.get_location_coords(location)
        if not coords_result or len(coords_result) < 2:
            return f"Weather data not available for {location}"
        
        coords = coords_result[1]
        live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
        
        if live_data and 'current' in live_data:
            current = live_data['current']
            
            # Safely get forecast data
            forecast_info = ""
            if 'forecast' in live_data and 'forecastday' in live_data['forecast']:
                try:
                    today = live_data['forecast']['forecastday'][0]['day']
                    forecast_info = f" Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C."
                except (KeyError, IndexError) as e:
                    logger.warning(f"Forecast data incomplete: {e}")
            
            return (
                f"Live weather in {location}: {current['temp_c']}°C, "
                f"{current['condition']['text']}.{forecast_info}"
            )
    except Exception as e:
        logger.error(f"Weather error for {location}: {e}")
    return None

# ======================
# TRANSLATION (LibreTranslate with fallback)
# ======================

SUPPORTED_LANGUAGES = {"en", "am", "om", "fr", "es", "ar"}

def translate_text(text: str, target_lang: str) -> str:
    """Translate text from English to target language."""
    if target_lang == "en" or not text:
        return text
    
    if target_lang not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported target language: {target_lang}")
        return text
    
    try:
        resp = requests.post(
            "https://libretranslate.de/translate",
            json={
                "q": text, 
                "source": "en", 
                "target": target_lang
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data.get("translatedText", text)
        else:
            logger.warning(f"Translation API returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Translation to {target_lang} failed: {e}")
    
    return text

def detect_and_translate_to_english(text: str) -> Tuple[str, str]:
    """Detect language and translate to English if needed."""
    if not text or not text.strip():
        return "", "en"
    
    # If text is already short or looks like English, return as is
    if len(text.split()) <= 3 or all(ord(c) < 128 for c in text):
        return text, "en"
    
    try:
        # Detect language
        resp = requests.post(
            "https://libretranslate.de/detect",
            json={"q": text[:100]},  # Limit detection text length
            timeout=5
        )
        
        detected_lang = "en"
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                detected_lang = data[0].get("language", "en")
        
        # Translate to English if not already English
        if detected_lang != "en" and detected_lang in SUPPORTED_LANGUAGES:
            trans_resp = requests.post(
                "https://libretranslate.de/translate",
                json={
                    "q": text, 
                    "source": detected_lang, 
                    "target": "en"
                },
                timeout=8
            )
            if trans_resp.status_code == 200:
                trans_data = trans_resp.json()
                if isinstance(trans_data, dict):
                    translated_text = trans_data.get("translatedText", text)
                    return translated_text, detected_lang
        
        return text, detected_lang
        
    except Exception as e:
        logger.warning(f"Translation detection error: {e}")
        return text, "en"

# ======================
# AI RESPONSE
# ======================

def is_in_scope(question: str) -> bool:
    """Check if the question is within the scope of Ethiopia-focused data."""
    if not question or not isinstance(question, str):
        return False
    
    q = question.lower()
    keywords = [
        "ethiopia", "addis", "jimma", "hawassa", "bahir dar", "mekelle", 
        "weather", "crop", "plant", "agriculture", "farm", "gdp", "inflation", 
        "population", "exchange", "currency", "teff", "kiremt", "belg", 
        "rain", "season", "economy", "demographic"
    ]
    return any(kw in q for kw in keywords)

def generate_ai_response(question: str) -> str:
    """Generate AI response using OpenRouter API."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        logger.error("OPENROUTER_API_KEY is missing in environment!")
        return "AI assistant is not configured. Please contact support."

    if not is_in_scope(question):
        return (
            "I specialize in Ethiopia-related questions about economy, agriculture, "
            "weather, and demographics. Please ask something about Ethiopia!"
        )

    # Build comprehensive context with all available data
    context = f"""
You are Finedata AI, an expert assistant for Ethiopia. Use ONLY the verified data below:

ECONOMIC DATA:
- GDP per capita: {get_gdp_per_capita()}
- Inflation rate: {get_inflation_rate()}
- Exchange rates (ETB to): {get_exchange_rates()}

DEMOGRAPHIC DATA:
- Population: {get_population()}

AGRICULTURAL INFORMATION:
- Planting seasons: {get_planting_seasons("Ethiopia")}
- Common crops: {get_agricultural_data("Ethiopia")}

WEATHER DATA:
- Current weather available for major Ethiopian cities

IMPORTANT RULES:
1. Answer concisely in 1-3 sentences maximum
2. Use only the data provided above - never invent or guess numbers
3. If specific data is not available, say "I don't have that specific data point"
4. Keep answers factual and focused on Ethiopia
5. Reference the data sources when possible

User Question: {question}

Assistant Answer:
"""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "https://finedata.onrender.com",
                "X-Title": "Finedata Ethiopia AI",
                "Content-Type": "application/json"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": context}],
                "temperature": 0.2,
                "max_tokens": 250,
                "top_p": 0.9
            },
            timeout=30
        )
        
        if resp.status_code == 200:
            response_data = resp.json()
            answer = response_data["choices"][0]["message"]["content"].strip()
            # Clean up the response
            cleaned_answer = answer.split("Question:")[0].split("User Question:")[0].strip()
            return cleaned_answer or "I couldn't generate a response for that question."
        else:
            logger.error(f"OpenRouter API error: {resp.status_code} - {resp.text}")
            return "I'm having trouble processing your request right now. Please try again shortly."
            
    except requests.exceptions.Timeout:
        logger.error("OpenRouter API timeout")
        return "The AI service is taking too long to respond. Please try again."
    except Exception as e:
        logger.exception("OpenRouter request failed")
        return "AI service is temporarily unavailable. Please try again later."

# ======================
# ROUTES
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    """Main endpoint for AI questions with translation support."""
    # Validate request
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    # Extract and validate parameters
    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please provide a question"}), 400
    
    if len(user_question) > 1000:
        return jsonify({"error": "Question too long (max 1000 characters)"}), 400

    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"

    try:
        # Process the question
        english_question, detected_lang = detect_and_translate_to_english(user_question)
        answer_en = generate_ai_response(english_question)
        answer_translated = translate_text(answer_en, target_lang)

        return jsonify({
            "answer_translated": answer_translated,
            "answer_english": answer_en,
            "language": target_lang,
            "detected_language": detected_lang,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error processing AI request: {e}")
        return jsonify({
            "error": "Internal server error processing your question",
            "success": False
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "translation": "available",
            "ai": "available" if os.getenv("OPENROUTER_API_KEY") else "disabled",
            "weather": "available" if weather_collector else "disabled"
        }
    })

@app.route('/ai-chat.html')
def ai_chat_page():
    """Serve the AI chat interface."""
    return send_from_directory('.', 'ai-chat.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files."""
    # Basic security check
    if '..' in filename or filename.startswith('/'):
        return "Invalid path", 400
    return send_from_directory('.', filename)

@app.route('/')
def home():
    """Serve the main page."""
    return send_from_directory('.', 'index.html')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Validate required environment variables
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("OPENROUTER_API_KEY not set - AI features will be disabled")
    
    # Start the application
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting Finedata Ethiopia AI server on {host}:{port}")
    app.run(debug=False, host=host, port=port)
