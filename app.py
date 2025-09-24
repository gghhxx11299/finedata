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

# Use deep-translator instead of googletrans
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    print("Warning: deep-translator not available")

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
# TRANSLATION - USING DEEP-TRANSLATOR (MORE RELIABLE)
# ======================

SUPPORTED_LANGUAGES = {"en", "am", "om", "fr", "es", "ar"}

# Language code mapping for deep-translator
LANG_MAP = {
    "am": "am",    # Amharic
    "om": "om",    # Oromo
    "fr": "fr",    # French
    "es": "es",    # Spanish
    "ar": "ar",    # Arabic
    "en": "en"     # English
}

def translate_text(text: str, target_lang: str) -> str:
    """Translate text from English to target language."""
    if target_lang == "en" or not text:
        return text
    
    if target_lang not in SUPPORTED_LANGUAGES or not TRANSLATION_AVAILABLE:
        return text
    
    try:
        translated = GoogleTranslator(source='en', target=target_lang).translate(text)
        return translated if translated else text
    except Exception as e:
        logger.warning(f"Translation to {target_lang} failed: {e}")
        return text

def detect_and_translate_to_english(text: str) -> Tuple[str, str]:
    """Simple language detection and translation to English."""
    if not text.strip():
        return "", "en"
    
    # Simple detection based on character ranges
    # Amharic characters: U+1200 to U+137F
    if any('\u1200' <= char <= '\u137F' for char in text):
        # Likely Amharic
        if TRANSLATION_AVAILABLE:
            try:
                translated = GoogleTranslator(source='am', target='en').translate(text)
                return translated if translated else text, "am"
            except:
                pass
        return text, "am"
    
    # Arabic script (for Arabic and some other languages)
    elif any('\u0600' <= char <= '\u06FF' for char in text):
        if TRANSLATION_AVAILABLE:
            try:
                translated = GoogleTranslator(source='auto', target='en').translate(text)
                return translated if translated else text, "ar"
            except:
                pass
        return text, "ar"
    
    # Default to English
    return text, "en"

# ======================
# AI RESPONSE
# ======================

AVAILABLE_MODELS = [
    "google/gemma-2-2b-it:free",
    "microsoft/phi-3-medium-4k-instruct:free", 
    "huggingfaceh4/zephyr-7b-beta:free",
]

def is_in_scope(question: str) -> bool:
    """Check if the question is within the scope of Ethiopia-focused data."""
    if not question or not isinstance(question, str):
        return False
    
    q = question.lower()
    keywords = [
        "ethiopia", "addis", "jimma", "hawassa", "bahir dar", "mekelle", 
        "weather", "crop", "plant", "agriculture", "farm", "gdp", "inflation", 
        "population", "exchange", "currency", "teff", "kiremt", "belg", 
        "rain", "season", "economy", "demographic", "africa", "ethiopian"
    ]
    return any(kw in q for kw in keywords)

def try_ai_models(question: str, context: str) -> str:
    """Try different AI models until one works."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return "AI service is not configured. Please check your API key."
    
    for model in AVAILABLE_MODELS:
        try:
            logger.info(f"Trying model: {model}")
            
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "https://finedata.onrender.com", 
                "X-Title": "Finedata Ethiopia AI",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": context}],
                "temperature": 0.3,
                "max_tokens": 300,
                "top_p": 0.9
            }
            
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=25
            )
            
            if resp.status_code == 200:
                response_data = resp.json()
                answer = response_data["choices"][0]["message"]["content"].strip()
                cleaned_answer = answer.split("Question:")[0].split("User Question:")[0].strip()
                
                if cleaned_answer and len(cleaned_answer) > 10:
                    logger.info(f"Success with model: {model}")
                    return cleaned_answer
            
            elif resp.status_code == 404:
                logger.warning(f"Model not available: {model}")
                continue
            else:
                logger.warning(f"Model {model} returned status {resp.status_code}")
                
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            continue
    
    return "I'm unable to generate a response at the moment. Please try again later."

def generate_ai_response(question: str) -> str:
    """Generate AI response using OpenRouter API."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return "AI assistant is not configured. Please add your OpenRouter API key."

    if not is_in_scope(question):
        return "I specialize in Ethiopia-related questions about economy, agriculture, weather, and demographics."

    context = f"""You are Finedata AI, an expert assistant for Ethiopia. Use ONLY the verified data below:

ECONOMIC DATA:
- GDP per capita: {get_gdp_per_capita()}
- Inflation rate: {get_inflation_rate()}
- Exchange rates (ETB to): {get_exchange_rates()}

DEMOGRAPHIC DATA:
- Population: {get_population()}

AGRICULTURAL INFORMATION:
- Planting seasons: {get_planting_seasons("Ethiopia")}
- Common crops: {get_agricultural_data("Ethiopia")}

RULES:
1. Answer concisely in 1-3 sentences
2. Use only the data provided above
3. If data is not available, say "I don't have that specific data"
4. Keep answers factual and Ethiopia-focused

Question: {question}

Answer:"""

    return try_ai_models(question, context)

# ======================
# ROUTES
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    """Main endpoint for AI questions with translation support."""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please provide a question"}), 400
    
    if len(user_question) > 1000:
        return jsonify({"error": "Question too long (max 1000 characters)"}), 400

    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "en"

    try:
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
            "translation": "available" if TRANSLATION_AVAILABLE else "disabled",
            "ai": "available" if os.getenv("OPENROUTER_API_KEY") else "disabled"
        },
        "supported_languages": list(SUPPORTED_LANGUAGES)
    })

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/ai-chat.html')
def ai_chat_page():
    return send_from_directory('.', 'ai-chat.html')

@app.route('/<path:filename>')
def static_files(filename):
    if '..' in filename or filename.startswith('/'):
        return "Invalid path", 400
    return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting Finedata Ethiopia AI server on {host}:{port}")
    logger.info(f"Translation available: {TRANSLATION_AVAILABLE}")
    
    app.run(debug=False, host=host, port=port)
