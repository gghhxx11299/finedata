# app.py
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import os
from weather_collector import EthiopianWeatherForecast
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Essential for GitHub Pages frontend

# Initialize with API keys
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

if not WEATHER_API_KEY:
    raise ValueError("WEATHER_API_KEY not found in environment variables!")

weather_collector = EthiopianWeatherForecast(WEATHER_API_KEY)

def translate_to_english(text: str) -> str:
    """Translate user input to English for AI processing"""
    if not text or not text.strip():
        return text
        
    try:
        response = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "auto", "target": "en"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("translatedText", text)
        print(f"Translation to English failed: {response.status_code}")
    except Exception as e:
        print(f"Translation error: {e}")
    return text

def extract_location_with_ai(question: str) -> str:
    """Extract Ethiopian city from English question"""
    if not HF_API_TOKEN or not question.strip():
        # Fallback to keyword matching
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"

    try:
        prompt = f"Extract only the Ethiopian city name from this question. If none, return 'Addis Ababa'. Question: {question}"
        response = requests.post(
            "https://api-inference.huggingface.co/models/google/flan-t5-large",
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 20}},
            timeout=12
        )
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            text = result[0].get("generated_text", "")
        else:
            text = result.get("generated_text", "Addis Ababa")
            
        city = text.strip().split("\n")[0].split(".")[0].split(":")[-1].strip()
        return city if city else "Addis Ababa"
    except Exception as e:
        print(f"AI extraction error: {e}")
        for loc in weather_collector.locations:
            if loc.lower() in question.lower():
                return loc
        return "Addis Ababa"

def translate_text(text: str, target_lang: str) -> str:
    """Translate response to user's language"""
    if target_lang == "en" or not text:
        return text
        
    try:
        response = requests.post(
            "https://libretranslate.de/translate",
            json={"q": text, "source": "en", "target": target_lang},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("translatedText", text)
        print(f"Translation failed: {response.status_code}")
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
        
    user_question = data.get("question", "").strip()
    target_lang = data.get("language", "en")

    if not user_question:
        return jsonify({"error": "Please ask a question about Ethiopian weather."}), 400

    # Step 1: Translate user input to English
    english_question = translate_to_english(user_question)
    print(f"Original: '{user_question}' → English: '{english_question}'")
    
    # Step 2: Extract location
    city = extract_location_with_ai(english_question)
    print(f"Extracted city: '{city}'")
    
    # Step 3: Get coordinates
    location_name, coords = weather_collector.get_location_coords(city)
    print(f"Using coordinates: {coords['lat']}, {coords['lon']} for {location_name}")
    
    # Step 4: Fetch live weather
    live_data = weather_collector.fetch_live_weather(coords['lat'], coords['lon'])
    
    if not live_
        answer_en = f"Sorry, I couldn't fetch live weather data for {location_name}. Please try again."
    elif 'current' not in live_ or 'forecast' not in live_
        answer_en = f"Weather data structure invalid for {location_name}."
    else:
        current = live_data['current']
        today = live_data['forecast']['forecastday'][0]['day']
        answer_en = (
            f"Live weather in {location_name}: {current['temp_c']}°C, {current['condition']['text']}. "
            f"Today's high: {today['maxtemp_c']}°C, low: {today['mintemp_c']}°C. "
            f"Chance of rain: {today['daily_chance_of_rain']}%."
        )

    # Step 5: Translate to user's language
    answer_translated = translate_text(answer_en, target_lang)

    return jsonify({
        "question_original": user_question,
        "question_english": english_question,
        "location": location_name,
        "answer_english": answer_en,
        "answer_translated": answer_translated,
        "language": target_lang
    })

# Serve all static files
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
