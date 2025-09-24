# app.py
from flask import Flask, render_template, jsonify, request, send_from_directory
import requests
import os
import re
from weather_collector import EthiopianWeatherForecast
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize with API keys from .env
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

if not WEATHER_API_KEY:
    raise ValueError("WEATHER_API_KEY not found in .env file!")

weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY)

def extract_location_with_ai(question: str) -> str:
    """Use Hugging Face AI to extract Ethiopian city from question"""
    if not HF_API_TOKEN:
        # Fallback: simple keyword matching
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"

    try:
        prompt = f"Extract only the Ethiopian city name from this question. If none, return 'Addis Ababa'. Question: {question}"
        response = requests.post(
            "https://api-inference.huggingface.co/models/google/flan-t5-large",
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 20, "temperature": 0.1}},
            timeout=12
        )
        result = response.json()
        
        # Handle different response formats
        if isinstance(result, list) and len(result) > 0:
            text = result[0].get("generated_text", "")
        else:
            text = result.get("generated_text", "Addis Ababa")
            
        # Clean the response
        city = text.strip().split("\n")[0].split(".")[0].split(":")[-1].strip()
        return city if city else "Addis Ababa"
    except Exception as e:
        print(f"AI extraction error: {e}")
        # Fallback to keyword matching
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"

def translate_text(text: str, target_lang: str) -> str:
    """Translate using LibreTranslate public API"""
    if target_lang == "en" or not text or not isinstance(text, str):
        return text
        
    try:
        response = requests.post(
            "https://libretranslate.de/translate",
            json={
                "q": text,
                "source": "en",
                "target": target_lang,
                "format": "text"
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("translatedText", text)
        else:
            print(f"Translation failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Translation error: {e}")
    return text

@app.route('/ai-chat.html')
def ai_chat_page():
    return send_from_directory('.', 'ai-chat.html')

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    question = data.get("question", "").strip()
    lang = data.get("language", "en")

    if not question:
        return jsonify({"error": "Please ask a question about Ethiopian weather."}), 400

    # Step 1: Extract location using AI
    city = extract_location_with_ai(question)
    
    # Step 2: Get coordinates
    location_name, coords = weather_collector.get_location_coords(city)
    
    # Step 3: Fetch LIVE weather data from WeatherAPI (online!)
    live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
    
    if not live_data or 'current' not in live_data:
        answer_en = f"Sorry, I couldn't fetch live weather data for {location_name}. Please try again later."
    else:
        current = live_data['current']
        today = live_data['forecast']['forecastday'][0]['day']
        answer_en = (
            f"🌤️ Live weather in {location_name}: {current['temp_c']}°C, {current['condition']['text']}. "
            f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C. "
            f"Chance of rain: {today['daily_chance_of_rain']}%. "
            f"Wind: {current['wind_kph']} km/h."
        )

    # Step 4: Translate to user's language
    answer_translated = translate_text(answer_en, lang)

    return jsonify({
        "question": question,
        "location": location_name,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "language": lang
    })

# Serve all static files (your existing HTML, CSS, JS, etc.)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    print("Starting Ethiopian AI Weather Assistant...")
    print("Visit http://localhost:5000/ai-chat.html")
    app.run(debug=True, port=5000, host='0.0.0.0')
