# app.py
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import os
import re
from weather_collector import EthiopianWeatherForecast
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize services
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY)

# ===== DATA FETCHING FUNCTIONS =====

def get_exchange_rates():
    """Get real ETB exchange rates"""
    try:
        response = requests.get(
            "https://api.exchangerate-api.com/v4/latest/ETB",
            timeout=8
        )
        data = response.json()
        rates = data.get("rates", {})
        return {
            "USD": round(1 / rates.get("USD", 0), 2) if rates.get("USD") else "N/A",
            "EUR": round(1 / rates.get("EUR", 0), 2) if rates.get("EUR") else "N/A",
            "GBP": round(1 / rates.get("GBP", 0), 2) if rates.get("GBP") else "N/A"
        }
    except Exception as e:
        print(f"Exchange rate error: {e}")
        return {"USD": "N/A", "EUR": "N/A", "GBP": "N/A"}

def get_inflation_rate():
    """Get Ethiopia's latest inflation rate from World Bank"""
    try:
        response = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/FP.CPI.TOTL.ZG?format=json&per_page=1",
            timeout=8
        )
        data = response.json()
        if len(data) > 1 and len(data[1]) > 0:
            return f"{data[1][0]['value']}%" if data[1][0]['value'] else "N/A"
        return "N/A"
    except Exception as e:
        print(f"Inflation error: {e}")
        return "N/A"

def get_gdp_per_capita():
    """Get Ethiopia's GDP per capita"""
    try:
        response = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/NY.GDP.PCAP.CD?format=json&per_page=1",
            timeout=8
        )
        data = response.json()
        if len(data) > 1 and len(data[1]) > 0:
            value = data[1][0]['value']
            return f"${int(value):,}" if value else "N/A"
        return "N/A"
    except Exception as e:
        print(f"GDP error: {e}")
        return "N/A"

def get_population():
    """Get Ethiopia's population"""
    try:
        response = requests.get(
            "https://api.worldbank.org/v2/country/ETH/indicator/SP.POP.TOTL?format=json&per_page=1",
            timeout=8
        )
        data = response.json()
        if len(data) > 1 and len(data[1]) > 0:
            value = data[1][0]['value']
            return f"{int(value):,}" if value else "N/A"
        return "N/A"
    except Exception as e:
        print(f"Population error: {e}")
        return "N/A"

def get_agricultural_data(location):
    """Get crop data for Ethiopian regions (simplified)"""
    crops = {
        "Jimma": "Coffee, maize, teff",
        "Arba Minch": "Bananas, cotton, sorghum",
        "Hawassa": "Vegetables, fruits, dairy",
        "Bahir Dar": "Teff, maize, pulses",
        "Mekelle": "Wheat, barley, teff"
    }
    return crops.get(location, "Coffee, teff, maize (national staples)")

# ===== AI UNDERSTANDING =====

def translate_to_english(text: str) -> str:
    if not text.strip():
        return text
    try:
        response = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "auto", "target": "en"},
            timeout=10
        )
        return response.json().get("translatedText", text) if response.status_code == 200 else text
    except:
        return text

def detect_question_type(question: str):
    """Detect what kind of data the user wants"""
    q = question.lower()
    
    if any(word in q for word in ["exchange", "rate", "dollar", "usd", "eur", "currency"]):
        return "exchange"
    elif any(word in q for word in ["inflation", "price", "cpi"]):
        return "inflation"
    elif any(word in q for word in ["gdp", "economy", "economic", "status"]):
        return "economy"
    elif any(word in q for word in ["population", "people", "demographic"]):
        return "population"
    elif any(word in q for word in ["crop", "agri", "farm", "coffee", "teff"]):
        return "agriculture"
    else:
        return "weather"  # default

def extract_location_with_ai(question: str):
    """Extract Ethiopian city"""
    if not HF_API_TOKEN:
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"
    
    try:
        prompt = f"Extract only the Ethiopian city name. If none, return 'Ethiopia'. Question: {question}"
        response = requests.post(
            "https://api-inference.huggingface.co/models/google/flan-t5-large",
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 20}},
            timeout=12
        )
        result = response.json()
        text = result[0].get("generated_text", "") if isinstance(result, list) else result.get("generated_text", "Ethiopia")
        city = text.strip().split("\n")[0].split(".")[0].split(":")[-1].strip()
        return city if city and city != "Ethiopia" else "Addis Ababa"
    except:
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"

def translate_text(text: str, target_lang: str) -> str:
    if target_lang == "en" or not text:
        return text
    try:
        response = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "en", "target": target_lang},
            timeout=10
        )
        return response.json().get("translatedText", text) if response.status_code == 200 else text
    except:
        return text

# ===== MAIN ENDPOINT =====

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a question."}), 400

    # Translate input to English
    english_question = translate_to_english(user_question)
    question_type = detect_question_type(english_question)
    location = extract_location_with_ai(english_question) if question_type in ["weather", "agriculture"] else "Ethiopia"

    # Fetch data based on question type
    if question_type == "exchange":
        rates = get_exchange_rates()
        answer_en = f"Current exchange rates: 1 USD = {rates['USD']} ETB, 1 EUR = {rates['EUR']} ETB, 1 GBP = {rates['GBP']} ETB."
        
    elif question_type == "inflation":
        inflation = get_inflation_rate()
        answer_en = f"Ethiopia's latest annual inflation rate is {inflation}."
        
    elif question_type == "economy":
        gdp = get_gdp_per_capita()
        inflation = get_inflation_rate()
        answer_en = f"Ethiopia's economic status: GDP per capita is {gdp}. Annual inflation is {inflation}."
        
    elif question_type == "population":
        pop = get_population()
        answer_en = f"Ethiopia's population is approximately {pop}."
        
    elif question_type == "agriculture":
        crops = get_agricultural_data(location)
        answer_en = f"Main crops in {location}: {crops}."
        
    else:  # weather
        coords = weather_collector.get_location_coords(location)[1]
        live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
        if live_data and 'current' in live_data:
            current = live_data['current']
            today = live_data['forecast']['forecastday'][0]['day']
            answer_en = (
                f"Live weather in {location}: {current['temp_c']}°C, {current['condition']['text']}. "
                f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C."
            )
        else:
            answer_en = f"Sorry, couldn't fetch weather for {location}."

    # Translate response
    answer_translated = translate_text(answer_en, target_lang)

    return jsonify({
        "question_original": user_question,
        "question_english": english_question,
        "question_type": question_type,
        "location": location,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "language": target_lang
    })

# ===== SERVE FILES =====
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
