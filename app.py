# app.py
import os
import time
import logging
import re
from datetime import datetime
from functools import wraps
from typing import Dict, Optional, Any, Tuple, List

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
# ENHANCED DATA FUNCTIONS
# ======================

@cached()
def get_gdp_per_capita() -> Dict[str, Any]:
    try:
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/NY.GDP.PCAP.CD?format=json&per_page=5", 
            timeout=8
        )
        data = resp.json()
        if len(data) > 1 and data[1]:
            latest = data[1][0]
            historical = data[1][:3]  # Last 3 years
            return {
                "value": f"${int(latest['value']):,}" if latest['value'] else "N/A",
                "year": latest['date'],
                "historical": [{"year": item['date'], "value": f"${int(item['value']):,}" if item['value'] else "N/A"} for item in historical]
            }
    except Exception as e:
        logger.error(f"GDP error: {e}")
    return {"value": "N/A", "year": "N/A", "historical": []}

@cached()
def get_inflation_rate() -> Dict[str, Any]:
    try:
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json&per_page=5", 
            timeout=8
        )
        data = resp.json()
        if len(data) > 1 and data[1]:
            latest = data[1][0]
            historical = data[1][:3]
            return {
                "value": f"{latest['value']:.1f}%" if latest['value'] else "N/A",
                "year": latest['date'],
                "historical": [{"year": item['date'], "value": f"{item['value']:.1f}%" if item['value'] else "N/A"} for item in historical]
            }
    except Exception as e:
        logger.error(f"Inflation error: {e}")
    return {"value": "N/A", "year": "N/A", "historical": []}

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
            "last_updated": datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
    return {"USD": "N/A", "EUR": "N/A", "GBP": "N/A", "last_updated": "N/A"}

@cached()
def get_population() -> Dict[str, Any]:
    try:
        resp = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/SP.POP.TOTL?format=json&per_page=5", 
            timeout=8
        )
        data = resp.json()
        if len(data) > 1 and data[1]:
            latest = data[1][0]
            historical = data[1][:3]
            return {
                "value": f"{int(latest['value']):,}" if latest['value'] else "N/A",
                "year": latest['date'],
                "historical": [{"year": item['date'], "value": f"{int(item['value']):,}" if item['value'] else "N/A"} for item in historical]
            }
    except Exception as e:
        logger.error(f"Population error: {e}")
    return {"value": "N/A", "year": "N/A", "historical": []}

def get_agricultural_data(location: str) -> Dict[str, Any]:
    """Get comprehensive agricultural data for a specific location."""
    crops_data = {
        "Addis Ababa": {
            "main_crops": ["Vegetables", "Teff", "Enset"],
            "season": "Year-round (highland climate)",
            "rainfall": "Moderate to high",
            "farming_type": "Urban and peri-urban agriculture"
        },
        "Jimma": {
            "main_crops": ["Coffee", "Maize", "Teff", "Spices"],
            "season": "March-September",
            "rainfall": "High (1500-2000mm)",
            "farming_type": "Coffee plantation and mixed farming"
        },
        "Hawassa": {
            "main_crops": ["Vegetables", "Fruits", "Dairy", "Maize"],
            "season": "Year-round",
            "rainfall": "Moderate",
            "farming_type": "Commercial farming and fisheries"
        },
        "Bahir Dar": {
            "main_crops": ["Teff", "Maize", "Pulses", "Sorghum"],
            "season": "June-December",
            "rainfall": "High",
            "farming_type": "Lake-side agriculture"
        },
        "Mekelle": {
            "main_crops": ["Wheat", "Barley", "Teff", "Pulses"],
            "season": "July-November",
            "rainfall": "Low to moderate",
            "farming_type": "Highland cereal farming"
        },
        "Arba Minch": {
            "main_crops": ["Bananas", "Cotton", "Sorghum", "Maize"],
            "season": "Year-round",
            "rainfall": "Moderate",
            "farming_type": "Tropical fruit farming"
        }
    }
    
    default_data = {
        "main_crops": ["Coffee", "Teff", "Maize", "Sorghum"],
        "season": "Varies by region",
        "rainfall": "Diverse across regions",
        "farming_type": "Mixed farming (national staples)"
    }
    
    return crops_data.get(location.title(), default_data)

def get_planting_seasons(location: str) -> Dict[str, Any]:
    """Get detailed planting season information."""
    seasons_data = {
        "general": {
            "belg_season": {"months": "February-April", "purpose": "Short rains for short-cycle crops"},
            "kiremt_season": {"months": "June-September", "purpose": "Main rainy season for most crops"},
            "dry_season": {"months": "October-January", "purpose": "Harvesting and land preparation"}
        },
        "addis ababa": {
            "description": "Two distinct rainy seasons suitable for diverse crops",
            "recommended_crops": ["Vegetables", "Teff", "Barley"]
        },
        "jimma": {
            "description": "Extended rainy season ideal for coffee cultivation",
            "recommended_crops": ["Coffee", "Maize", "Beans"]
        }
    }
    
    loc_key = location.lower() if location.lower() in seasons_data else "general"
    return {**seasons_data["general"], **seasons_data.get(loc_key, {})}

# ======================
# ENHANCED QUESTION PROCESSING
# ======================

def extract_location(question: str) -> str:
    """Extract location from question."""
    locations = ["addis ababa", "addis", "jimma", "hawassa", "bahir dar", 
                "mekelle", "arba minch", "dire dawa", "harar", "gondar"]
    
    question_lower = question.lower()
    for loc in locations:
        if loc in question_lower:
            return loc.title()
    return "Ethiopia"

def extract_topic(question: str) -> Dict[str, bool]:
    """Extract topics from question."""
    question_lower = question.lower()
    
    return {
        "economy": any(word in question_lower for word in ["gdp", "economy", "economic", "growth", "development"]),
        "inflation": any(word in question_lower for word in ["inflation", "price", "cost", "cpi"]),
        "population": any(word in question_lower for word in ["population", "people", "demographic", "census"]),
        "exchange": any(word in question_lower for word in ["exchange", "currency", "dollar", "euro", "etb"]),
        "agriculture": any(word in question_lower for word in ["crop", "farm", "agriculture", "harvest", "plant"]),
        "weather": any(word in question_lower for word in ["weather", "rain", "temperature", "climate"]),
        "season": any(word in question_lower for word in ["season", "planting", "raining", "belg", "kiremt"]),
        "specific_crop": any(word in question_lower for word in ["teff", "coffee", "maize", "wheat", "barley"])
    }

def understand_question_intent(question: str) -> Dict[str, Any]:
    """Understand what the user is asking for."""
    question_lower = question.lower()
    
    intent = {
        "type": "general",  # general, comparison, historical, specific, how_to
        "location": extract_location(question),
        "topics": extract_topic(question),
        "is_comparison": any(word in question_lower for word in ["compare", "vs", "difference", "versus"]),
        "is_historical": any(word in question_lower for word in ["history", "trend", "over time", "last year", "previous"]),
        "is_how_to": any(word in question_lower for word in ["how to", "best way", "recommend", "should i"]),
        "needs_follow_up": False
    }
    
    # Determine intent type
    if intent["is_comparison"]:
        intent["type"] = "comparison"
    elif intent["is_historical"]:
        intent["type"] = "historical"
    elif intent["is_how_to"]:
        intent["type"] = "how_to"
    elif sum(intent["topics"].values()) == 1:
        intent["type"] = "specific"
    
    # Check if we need more information
    if intent["topics"]["weather"] and intent["location"] == "Ethiopia":
        intent["needs_follow_up"] = True
    if intent["topics"]["agriculture"] and not any(intent["topics"].values()):
        intent["needs_follow_up"] = True
        
    return intent

# ======================
# ENHANCED RESPONSE GENERATION
# ======================

def generate_comprehensive_response(question: str) -> str:
    """Generate detailed, context-aware responses."""
    intent = understand_question_intent(question)
    question_lower = question.lower()
    
    # Get current data
    gdp_data = get_gdp_per_capita()
    inflation_data = get_inflation_rate()
    population_data = get_population()
    exchange_data = get_exchange_rates()
    ag_data = get_agricultural_data(intent["location"])
    season_data = get_planting_seasons(intent["location"])
    
    # Economic questions
    if intent["topics"]["economy"]:
        if intent["is_historical"]:
            hist_info = ". ".join([f"{item['year']}: {item['value']}" for item in gdp_data["historical"]])
            return f"Ethiopia's GDP per capita trends: {hist_info}. Current ({gdp_data['year']}): {gdp_data['value']}"
        return f"Ethiopia's GDP per capita is {gdp_data['value']} ({gdp_data['year']} data)."
    
    elif intent["topics"]["inflation"]:
        if intent["is_historical"]:
            hist_info = ". ".join([f"{item['year']}: {item['value']}" for item in inflation_data["historical"]])
            return f"Inflation trends: {hist_info}. Current rate: {inflation_data['value']}"
        return f"Ethiopia's inflation rate is {inflation_data['value']} ({inflation_data['year']})."
    
    elif intent["topics"]["population"]:
        if intent["is_historical"]:
            hist_info = ". ".join([f"{item['year']}: {item['value']}" for item in population_data["historical"]])
            return f"Population trends: {hist_info}. Current estimate: {population_data['value']} people"
        return f"Ethiopia's population is approximately {population_data['value']} people ({population_data['year']})."
    
    elif intent["topics"]["exchange"]:
        rates = exchange_data
        return f"Current exchange rates (1 ETB): {rates['USD']} USD, {rates['EUR']} EUR, {rates['GBP']} GBP. Updated {rates['last_updated']}."
    
    # Agriculture questions
    elif intent["topics"]["agriculture"]:
        location_info = f" in {intent['location']}" if intent["location"] != "Ethiopia" else ""
        
        if intent["topics"]["specific_crop"]:
            if "teff" in question_lower:
                return f"Teff is Ethiopia's staple grain{location_info}, used for injera. Grown mainly during {season_data['kiremt_season']['months']}."
            elif "coffee" in question_lower:
                return f"Coffee is Ethiopia's main export{location_info}. Arabica coffee grows best in highland areas like Jimma."
        
        if intent["is_how_to"]:
            return f"For {intent['location']}: Main crops are {', '.join(ag_data['main_crops'])}. Planting season: {ag_data['season']}. Rainfall: {ag_data['rainfall']}."
        
        return f"In {intent['location']}, main crops include {', '.join(ag_data['main_crops'])}. {ag_data['farming_type']}."
    
    # Weather and seasons
    elif intent["topics"]["weather"] or intent["topics"]["season"]:
        if intent["location"] == "Ethiopia":
            return "Ethiopia has diverse climate zones. Please specify a region (like Addis Ababa, Jimma, etc.) for specific weather information."
        
        season_info = f"Seasons in {intent['location']}: Belg ({season_data['belg_season']['months']}) for short crops, Kiremt ({season_data['kiremt_season']['months']}) main season."
        if "description" in season_data:
            season_info += f" {season_data['description']}"
        return season_info
    
    # Follow-up needed
    if intent["needs_follow_up"]:
        if intent["topics"]["weather"]:
            return "I'd be happy to provide weather information! Could you specify which city or region in Ethiopia you're interested in?"
        elif intent["topics"]["agriculture"]:
            return "I can help with agricultural information! Are you interested in a specific region, crop, or farming practice?"
    
    # General Ethiopia information
    general_info = [
        f"Population: {population_data['value']} people",
        f"GDP per capita: {gdp_data['value']}",
        f"Inflation: {inflation_data['value']}",
        f"Main crops: {', '.join(ag_data['main_crops'])}",
        f"Seasons: Belg ({season_data['belg_season']['months']}) and Kiremt ({season_data['kiremt_season']['months']})"
    ]
    
    return f"Ethiopia overview: {'; '.join(general_info)}. Ask about specific topics like economy, agriculture, or regions for more details!"

# ======================
# TRANSLATION (same as before)
# ======================

SUPPORTED_LANGUAGES = {"en", "am", "om", "fr", "es", "ar"}

def translate_text(text: str, target_lang: str) -> str:
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
    if not text.strip():
        return "", "en"
    if any('\u1200' <= char <= '\u137F' for char in text):
        if TRANSLATION_AVAILABLE:
            try:
                translated = GoogleTranslator(source='auto', target='en').translate(text)
                return translated if translated else text, "am"
            except:
                pass
        return text, "am"
    elif any('\u0600' <= char <= '\u06FF' for char in text):
        if TRANSLATION_AVAILABLE:
            try:
                translated = GoogleTranslator(source='auto', target='en').translate(text)
                return translated if translated else text, "ar"
            except:
                pass
        return text, "ar"
    return text, "en"

# ======================
# AI RESPONSE WITH ENHANCED LOGIC
# ======================

def try_openrouter_ai(question: str, context: str) -> Optional[str]:
    """Try to get response from OpenRouter API."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return None
    
    models_to_try = ["google/gemma-2-2b-it", "microsoft/phi-3-medium-4k-instruct"]
    
    for model in models_to_try:
        try:
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
            }
            
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20
            )
            
            if resp.status_code == 200:
                response_data = resp.json()
                answer = response_data["choices"][0]["message"]["content"].strip()
                cleaned_answer = answer.split("Question:")[0].split("User Question:")[0].strip()
                
                if cleaned_answer and len(cleaned_answer) > 10:
                    logger.info(f"✅ OpenRouter success with model: {model}")
                    return cleaned_answer
            
        except Exception as e:
            logger.debug(f"Model {model} error: {e}")
            continue
    
    return None

def generate_ai_response(question: str) -> str:
    """Generate intelligent response with enhanced understanding."""
    # First try OpenRouter if available
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    if openrouter_key:
        context = f"""You are Finedata AI, an expert assistant for Ethiopia. Use this data:

ECONOMIC DATA:
- GDP per capita: {get_gdp_per_capita()['value']} ({get_gdp_per_capita()['year']})
- Inflation rate: {get_inflation_rate()['value']} ({get_inflation_rate()['year']})
- Exchange rates: {get_exchange_rates()}

DEMOGRAPHIC DATA:
- Population: {get_population()['value']} ({get_population()['year']})

AGRICULTURAL INFORMATION:
- Planting seasons: Belg (Feb-Apr) and Kiremt (Jun-Sept)
- Common crops: Varies by region

Answer concisely and factually. If you need more specific information, ask follow-up questions.

Question: {question}

Answer:"""
        
        ai_response = try_openrouter_ai(question, context)
        if ai_response:
            return ai_response
    
    # Fallback to enhanced comprehensive responses
    return generate_comprehensive_response(question)

# ======================
# ROUTES (same as before)
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
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
    openrouter_working = False
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    if openrouter_key:
        try:
            headers = {"Authorization": f"Bearer {openrouter_key}"}
            resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=10)
            openrouter_working = resp.status_code == 200
        except:
            openrouter_working = False
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "translation": "available" if TRANSLATION_AVAILABLE else "disabled",
            "ai_openrouter": "available" if openrouter_working else "disabled",
            "enhanced_responses": "available",
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
    
    logger.info(f"Starting Enhanced Finedata Ethiopia AI server on {host}:{port}")
    app.run(debug=False, host=host, port=port)