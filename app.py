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

# Use deep-translator for translation
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
# CONFIGURATION
# ======================

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Available Groq models
GROQ_MODELS = [
    "llama-3.1-8b-instant",  # Fast and free
    "mixtral-8x7b-32768",    # High quality
    "gemma2-9b-it",          # Good balance
]

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "am": "Amharic", 
    "om": "Oromo",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic"
}

# ======================
# TRANSLATION FUNCTIONS
# ======================

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text between languages using Google Translate.
    """
    if source_lang == target_lang or not text.strip():
        return text
    
    if not TRANSLATION_AVAILABLE:
        logger.warning("Translation service not available")
        return text
    
    try:
        # Google Translate language codes
        lang_codes = {
            'en': 'en', 'am': 'am', 'om': 'om', 
            'fr': 'fr', 'es': 'es', 'ar': 'ar'
        }
        
        source_code = lang_codes.get(source_lang, 'auto')
        target_code = lang_codes.get(target_lang, 'en')
        
        translated = GoogleTranslator(source=source_code, target=target_code).translate(text)
        return translated if translated else text
        
    except Exception as e:
        logger.error(f"Translation error from {source_lang} to {target_lang}: {e}")
        return text

def detect_language(text: str) -> str:
    """
    Detect the language of the input text.
    """
    if not text.strip():
        return "en"
    
    if not TRANSLATION_AVAILABLE:
        # Simple character-based detection as fallback
        if any('\u1200' <= char <= '\u137F' for char in text):  # Amharic characters
            return "am"
        elif any('\u0600' <= char <= '\u06FF' for char in text):  # Arabic script
            return "ar"
        return "en"
    
    try:
        # Use Google Translate for detection
        detected = GoogleTranslator().detect(text)
        detected_lang = detected.lang
        
        # Map to our supported languages
        lang_mapping = {
            'en': 'en', 'am': 'am', 'om': 'om',
            'fr': 'fr', 'es': 'es', 'ar': 'ar'
        }
        
        return lang_mapping.get(detected_lang, 'en')
        
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return "en"

def process_translation_flow(user_question: str, target_language: str) -> Tuple[str, str, str]:
    """
    Handle the complete translation flow:
    1. Detect input language
    2. Translate to English if needed
    3. After AI response, translate back to target language
    """
    # Detect the language of the user's question
    detected_lang = detect_language(user_question)
    
    # Translate to English if not already English
    if detected_lang != "en":
        english_question = translate_text(user_question, detected_lang, "en")
    else:
        english_question = user_question
    
    return english_question, detected_lang, target_language

# ======================
# GROQ AI FUNCTIONS
# ======================

def call_groq_api(prompt: str, model: str = None) -> str:
    """
    Call Groq API to get AI response.
    """
    if not GROQ_API_KEY:
        logger.error("Groq API key not configured")
        return "AI service is not configured. Please check your API key."
    
    # Use first available model if none specified
    if not model:
        model = GROQ_MODELS[0]
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are Finedata AI, an expert assistant specializing in Ethiopia. 
                    Provide accurate, concise information about Ethiopia's economy, agriculture, 
                    demographics, culture, and current affairs. Be factual and helpful."""
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
            "top_p": 0.9,
            "stream": False
        }
        
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return f"Sorry, I encountered an error. Please try again. (Error: {response.status_code})"
            
    except requests.exceptions.Timeout:
        logger.error("Groq API timeout")
        return "The AI service is taking too long to respond. Please try again."
    except Exception as e:
        logger.error(f"Groq API exception: {e}")
        return "AI service is temporarily unavailable. Please try again later."

def try_groq_models(prompt: str) -> str:
    """
    Try different Groq models until one works.
    """
    for model in GROQ_MODELS:
        try:
            logger.info(f"Trying Groq model: {model}")
            response = call_groq_api(prompt, model)
            
            if response and not response.startswith("Sorry, I encountered an error"):
                logger.info(f"✅ Success with model: {model}")
                return response
                
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            continue
    
    return "I'm unable to generate a response at the moment. Please try again later."

# ======================
# ENHANCED PROMPT ENGINEERING
# ======================

def create_enhanced_prompt(question: str, context: Dict[str, Any] = None) -> str:
    """
    Create an enhanced prompt with Ethiopia-specific context.
    """
    base_context = """
IMPORTANT: You are Finedata AI, an expert assistant for Ethiopia. Follow these rules:

1. Provide accurate, factual information about Ethiopia
2. Be concise but informative (2-4 sentences typically)
3. If you don't know something, admit it rather than guessing
4. Focus on these key areas:
   - Economy (GDP, inflation, development)
   - Agriculture (crops, seasons, farming practices)
   - Demographics (population, ethnic groups, languages)
   - Culture (traditions, food, holidays)
   - Current affairs and development
   - Geography and climate

5. For specific queries:
   - Economic data: Reference World Bank, IMF when possible
   - Agricultural info: Mention regional variations
   - Cultural questions: Be respectful and accurate
   - Current events: Stick to verified information

6. Always maintain a helpful, professional tone
"""

    # Add dynamic context if available
    dynamic_context = ""
    if context:
        if context.get('location'):
            dynamic_context += f"\nUser is asking about: {context['location']}"
        if context.get('topic'):
            dynamic_context += f"\nTopic focus: {context['topic']}"
    
    prompt = f"""{base_context}{dynamic_context}

USER QUESTION: {question}

Finedata AI Response:"""
    
    return prompt

# ======================
# MAIN AI PROCESSING
# ======================

def generate_ai_response(english_question: str) -> str:
    """
    Generate AI response using Groq API with enhanced prompting.
    """
    # Create enhanced prompt
    prompt = create_enhanced_prompt(english_question)
    
    # Get response from Groq
    return try_groq_models(prompt)

# ======================
# FLASK ROUTES
# ======================

@app.route('/ask-ai', methods=['POST'])
def ask_ai():
    """
    Main endpoint for AI questions with full translation support.
    """
    # Validate request
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    # Extract parameters
    user_question = data.get("question", "").strip()
    target_language = data.get("language", "en")

    # Validate input
    if not user_question:
        return jsonify({"error": "Please provide a question"}), 400
    
    if len(user_question) > 2000:
        return jsonify({"error": "Question too long (max 2000 characters)"}), 400

    if target_language not in SUPPORTED_LANGUAGES:
        target_language = "en"

    try:
        # Process translation flow
        english_question, detected_language, target_lang = process_translation_flow(
            user_question, target_language
        )
        
        logger.info(f"Translation flow: {detected_language} -> en -> {target_lang}")
        
        # Generate AI response in English
        english_response = generate_ai_response(english_question)
        
        # Translate response back to target language if needed
        if target_lang != "en":
            final_response = translate_text(english_response, "en", target_lang)
        else:
            final_response = english_response

        return jsonify({
            "answer": final_response,
            "answer_english": english_response if target_lang != "en" else final_response,
            "detected_language": detected_language,
            "target_language": target_lang,
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing AI request: {e}")
        return jsonify({
            "error": "Internal server error processing your question",
            "success": False
        }), 500

@app.route('/languages', methods=['GET'])
def get_languages():
    """Get list of supported languages."""
    return jsonify({
        "supported_languages": SUPPORTED_LANGUAGES,
        "default_language": "en"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    groq_health = "unknown"
    
    if GROQ_API_KEY:
        try:
            # Test Groq API connectivity
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            test_payload = {
                "model": GROQ_MODELS[0],
                "messages": [{"role": "user", "content": "Say 'hello'"}],
                "max_tokens": 5
            }
            resp = requests.post(GROQ_API_URL, headers=headers, json=test_payload, timeout=10)
            groq_health = "healthy" if resp.status_code == 200 else "unhealthy"
        except:
            groq_health = "unhealthy"
    else:
        groq_health = "not_configured"
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "groq_ai": groq_health,
            "translation": "available" if TRANSLATION_AVAILABLE else "disabled",
            "supported_languages": len(SUPPORTED_LANGUAGES)
        }
    })

@app.route('/models', methods=['GET'])
def get_models():
    """Get available Groq models."""
    return jsonify({
        "available_models": GROQ_MODELS,
        "current_default": GROQ_MODELS[0]
    })

# Static file serving
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

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Validate configuration
    if not GROQ_API_KEY:
        logger.error("❌ GROQ_API_KEY environment variable is required!")
        logger.info("💡 Get your API key from: https://console.groq.com")
    else:
        logger.info("✅ Groq API key found")
    
    if not TRANSLATION_AVAILABLE:
        logger.warning("⚠️ Translation features limited - install deep-translator")
    
    # Start server
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting Finedata Ethiopia AI Server on {host}:{port}")
    logger.info(f"🌍 Supported languages: {list(SUPPORTED_LANGUAGES.keys())}")
    logger.info(f"🤖 Available AI models: {GROQ_MODELS}")
    
    app.run(debug=False, host=host, port=port)
