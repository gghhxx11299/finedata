# app.py
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import os
from weather_collector import EthiopianWeatherForecast
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize services
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY)

# ===== DATA FETCHING FUNCTIONS (unchanged) =====

def get_exchange_rates():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/ETB", timeout=8)
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
    crops = {
        "Jimma": "Coffee, maize, teff",
        "Arba Minch": "Bananas, cotton, sorghum",
        "Hawassa": "Vegetables, fruits, dairy",
        "Bahir Dar": "Teff, maize, pulses",
        "Mekelle": "Wheat, barley, teff"
    }
    return crops.get(location, "Coffee, teff, maize (national staples)")

def get_weather_data(location):
    coords = weather_collector.get_location_coords(location)[1]
    live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
    if live_data and 'current' in live_
        current = live_data['current']
        today = live_data['forecast']['forecastday'][0]['day']
        return (
            f"Live weather in {location}: {current['temp_c']}°C, {current['condition']['text']}. "
            f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C."
        )
    return None

# ===== TRANSLATION (unchanged) =====

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

# ===== DYNAMIC AI WITH OPENROUTER =====

def ask_ai_with_openrouter(question: str):
    if not OPENROUTER_API_KEY:
        return "AI is not configured. Please set OPENROUTER_API_KEY."

    # Pre-fetch all relevant data
    exchange = get_exchange_rates()
    inflation = get_inflation_rate()
    gdp = get_gdp_per_capita()
    population = get_population()

    context_prompt = f"""
You are an expert AI assistant for Ethiopia. Use ONLY the following real-time data to answer the user's question accurately and concisely.

Available Data:
- Exchange Rates (1 foreign = X ETB): {exchange}
- Inflation Rate: {inflation}
- GDP per Capita: {gdp}
- Population: {population}
- Agricultural regions: Jimma, Arba Minch, Hawassa, Bahir Dar, Mekelle
- Weather: available for any Ethiopian city

Rules:
1. If the question mentions a city and weather/crops, assume it's about that city.
2. If no city is given for weather, use "Addis Ababa".
3. Do NOT invent data. If unsure, say "I don't have that information."
4. Keep answers short and factual.
5. Respond in plain English without markdown.

User Question: {question}
Answer:
"""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://yourwebsite.com",  # ← REPLACE with your actual site URL
                "X-Title": "Ethiopia AI Assistant"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": context_prompt}],
                "temperature": 0.3,
                "max_tokens": 300
            },
            timeout=20
        )
        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
            # Clean up common repetition
            return answer.split("User Question")[0].strip()
        else:
            print(f"OpenRouter error {response.status_code}: {response.text}")
            return "I'm having trouble processing your request right now."
    except Exception as e:
        print(f"OpenRouter exception: {e}")
        return "AI service is temporarily unavailable."

# ===== MAIN ENDPOINT =====

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    if not 
        return jsonify({"error": "Invalid JSON"}), 400

    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a question."}), 400

    # Translate to English if needed
    english_question = translate_to_english(user_question) if target_lang != "en" else user_question

    # Use OpenRouter for dynamic understanding
    answer_en = ask_ai_with_openrouter(english_question)

    # Translate back if needed
    answer_translated = translate_text(answer_en, target_lang) if target_lang != "en" else answer_en

    return jsonify({
        "question_original": user_question,
        "question_english": english_question,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "language": target_lang
    })

# ===== STATIC FILE SERVING =====

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
