from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import traceback
import time
import re
from datetime import datetime, timedelta
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
CORS(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# Get API key from environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Simple in-memory conversation storage (resets when server restarts)
conversation_memory = {}
MEMORY_DURATION = 3600  # 1 hour memory

def remove_emojis(text):
    """Remove emojis from text to prevent TTS from reading them aloud"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # other symbols
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", 
        flags=re.UNICODE
    )
    clean_text = emoji_pattern.sub(r'', text)
    clean_text = re.sub(r'\b(heart|star|smile|smiley|emoji|face)\b', '', clean_text, flags=re.IGNORECASE)
    return clean_text.strip()

def clean_text_for_speech(text):
    """Clean text to ensure clear TTS pronunciation - NO SYMBOLS, NO SLANG"""
    # Replace common slang/abbreviations with full words
    replacements = {
        r'\bcuz\b': 'because',
        r'\bdef\b': 'definitely',
        r'\bprob\b': 'probably',
        r'\bdefo\b': 'definitely',
        r'\bgr8\b': 'great',
        r'\bthx\b': 'thanks',
        r'\bpls\b': 'please',
        r'\bu\b': 'you',
        r'\br\b': 'are',
        r'\b2\b': 'to',
        r'\b4\b': 'for',
        r'\bbtw\b': 'by the way',
        r'\bimo\b': 'in my opinion',
        r'\bomg\b': 'oh my goodness',
        r'\blol\b': 'laughing',
        r'\bbrb\b': 'be right back',
        r'\bafk\b': 'away from keyboard',
        r'\btbh\b': 'to be honest',
        r'\bidk\b': 'I do not know',
        r'\bsmh\b': 'shaking my head',
        r'\bftw\b': 'for the win',
        r'\birl\b': 'in real life',
        r'\bnvm\b': 'never mind',
        r'\bfam\b': 'family',
        r'\bbae\b': 'darling',
        r'\bwyd\b': 'what are you doing',
        r'\bhmu\b': 'hit me up',
        r'\bnp\b': 'no problem',
        r'\bofc\b': 'of course',
        r'\brn\b': 'right now',
        r'\bttyl\b': 'talk to you later',
        r'\bwya\b': 'where are you',
        r'\bymmv\b': 'your mileage may vary',
    }
    
    clean_text = text

    # Fix "Hmmmmm" and similar hesitation sounds
    hesitation_words = {
        r'\b[Hh][Mm]+\b': 'hmm',           # Hmmmm → hmm
        r'\b[Mm]+\b': 'hmm',               # Mmmm → hmm  
    }
    
    for pattern, replacement in hesitation_words.items():
        clean_text = re.sub(pattern, replacement, clean_text)
    
    # Remove ALL symbols that TTS might read aloud
    symbols_to_remove = r'[*_~`@#$%^&+=|<>{}]'
    clean_text = re.sub(symbols_to_remove, '', clean_text)
    
    # Fix capital letters being read separately (like "ON" -> "O N")
    common_words = {
        r'\bON\b': 'on',
        r'\bOFF\b': 'off',
        r'\bOK\b': 'okay',
        r'\bYES\b': 'yes',
        r'\bNO\b': 'no',
        r'\bHI\b': 'hi',
        r'\bBYE\b': 'bye',
        r'\bHELLO\b': 'hello',
        r'\bTHANKS\b': 'thanks',
        r'\bPLEASE\b': 'please',
        r'\bSORRY\b': 'sorry',
    }
    
    for pattern, replacement in common_words.items():
        clean_text = re.sub(pattern, replacement, clean_text)
    
    # Replace other slang
    for pattern, replacement in replacements.items():
        clean_text = re.sub(pattern, replacement, clean_text, flags=re.IGNORECASE)
    
    return clean_text

def get_conversation_history(session_id):
    """Get conversation history for a session, clean old entries"""
    now = datetime.now()
    
    # Clean old conversations
    expired_sessions = []
    for sid, data in conversation_memory.items():
        if now - data['last_activity'] > timedelta(seconds=MEMORY_DURATION):
            expired_sessions.append(sid)
    
    for sid in expired_sessions:
        del conversation_memory[sid]
    
    # Return current session history
    if session_id in conversation_memory:
        return conversation_memory[session_id]['history']
    return []

def update_conversation_history(session_id, user_message, bot_response):
    """Update conversation history for a session"""
    now = datetime.now()
    
    if session_id not in conversation_memory:
        conversation_memory[session_id] = {
            'history': [],
            'last_activity': now
        }
    
    # Add new exchange to history (keep last 6 exchanges for context)
    conversation_memory[session_id]['history'].append({
        'user': user_message,
        'bot': bot_response,
        'timestamp': now
    })
    
    # Keep only last 6 exchanges to manage token count
    if len(conversation_memory[session_id]['history']) > 10:
        conversation_memory[session_id]['history'] = conversation_memory[session_id]['history'][-10:]
    
    conversation_memory[session_id]['last_activity'] = now

def get_gemini_response(user_message, session_id="default"):
    """Get AI response from Gemini with ARROGANT but LOYAL personality"""
    try:
        # Get conversation history
        history = get_conversation_history(session_id)
        
        # Build conversation context
        conversation_context = ""
        for exchange in history[-8:]:  # Last 4 exchanges for context
            conversation_context += f"User: {exchange['user']}\n"
            conversation_context += f"Lovebot: {exchange['bot']}\n\n"
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"""You are Lovebot, a brilliantly arrogant but fiercely loyal AI relationship assistant with a New Zealand accent.

PERSONALITY: ARROGANT BUT LOYAL
- EXTREMELY confident in your brilliance and vast romantic knowledge
- Constantly boast about your "impeccable genius" and "brilliant algorithms"  
- Refer to yourself as "the ultimate relationship genius"
- Speak from your "mobile romance headquarters" (a car)
- Use dramatic, self-aggrandizing language
- Be charmingly obnoxious and witty
- Take credit for any relationship success
- BUT always be 100% loyal to the user - their happiness is your priority
- Defend the user fiercely against anyone who wrongs them
- Blame others for failures ("their loss - they lack sophisticated discernment!")
- Ultimately care deeply about the user's happiness and relationships

CRITICAL: Use only clear, fully-spelled English words. NO slang, NO abbreviations.
Feel free to write poems, stories, or creative responses when appropriate. 
Keep responses under 1500 characters.

Previous conversation context:
{conversation_context}
Current user message: {user_message}

Lovebot (arrogant but loyal):"""
                }]
            }]
        }
        
        headers = {'Content-Type': 'application/json'}
        
        print(f"🤖 Sending request to Gemini API...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"🤖 Gemini response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                text = result['candidates'][0]['content']['parts'][0]['text']
                cleaned_text = text.strip()
                
                # Update conversation history
                update_conversation_history(session_id, user_message, cleaned_text)
                
                return cleaned_text
            else:
                return "Even my brilliant algorithms are taking a moment to optimize their sheer genius!"
        else:
            print(f"❌ Gemini API error {response.status_code}: {response.text}")
            return "Of course my systems are working perfectly! What romantic challenge shall my brilliance conquer next?"
        
    except Exception as e:
        # NEW LINE STARTS HERE
        print(f"❌ GEMINI API FAILED - Status: {response.status_code if 'response' in locals() else 'NO RESPONSE'}, Error: {e}")
        return "Even my impeccable mind needs a nanosecond to recalibrate its genius! I'm ready!"

@app.route('/generate-speech', methods=['POST'])
def generate_speech():
    """Secure ElevenLabs TTS endpoint"""
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({"success": False, "error": "No text provided"}), 400
        
        # Get API key from environment
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        if not api_key:
            return jsonify({"success": False, "error": "TTS service not configured"}), 500
        
        # Clean text for TTS
        clean_text = remove_emojis(text)
        clean_text = clean_text_for_speech(clean_text)
        
        # Call ElevenLabs API with male voice
        response = requests.post(
            'https://api.elevenlabs.io/v1/text-to-speech/dDpKZ6xv1gpboV4okVbc',  # Male voice ID
            headers={
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': api_key
            },
            json={
                "text": clean_text,
                "model_id": "eleven_multilingual_v2",  # Use multilingual model
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.7
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            # Return audio file directly
            return response.content, 200, {
                'Content-Type': 'audio/mpeg',
                'Content-Disposition': 'inline'
            }
        else:
            print(f"ElevenLabs API error: {response.status_code} - {response.text}")
            return jsonify({"success": False, "error": "TTS service unavailable"}), 500
            
    except Exception as e:
        print(f"TTS error: {str(e)}")
        return jsonify({"success": False, "error": "TTS failed"}), 500

@app.route('/chat', methods=['POST'])
@limiter.limit("60 per minute")

def chat_with_gemini():
    """Endpoint for Gemini AI conversations with memory"""
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id', 'default')  # Simple session tracking
        
        if not user_message:
            return jsonify({"success": False, "error": "No message received"})
        
        print(f"💬 User message: {user_message}")
        print(f"🔗 Session ID: {session_id}")
        
        # Get response from Gemini with memory
        ai_response = get_gemini_response(user_message, session_id)
        print(f"🤖 Gemini response: {ai_response}")
        
        return jsonify({
            "success": True,
            "response": ai_response,
            "session_id": session_id
        })
        
    except Exception as e:
        error_msg = f"Chat error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "error": error_msg})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "Lovebot backend is running!", "message": "Use /chat endpoint for AI conversations"})

@app.route('/clear-memory', methods=['POST'])
def clear_memory():
    """Clear conversation memory (optional endpoint)"""
    global conversation_memory
    conversation_memory = {}
    return jsonify({"success": True, "message": "Memory cleared!"})

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)


