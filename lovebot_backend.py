from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import traceback
import time
import re
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)


import os
api_key = os.environ.get("GEMINI_API_KEY")

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
    
    # Remove ALL symbols that TTS might read aloud
    symbols_to_remove = r'[*_~`@#$%^&+=|<>{}]'
    clean_text = re.sub(symbols_to_remove, '', clean_text)
    
    # Fix capital letters being read separately (like "ON" -> "O N")
    # Only fix if it's a common word in all caps, not acronyms with dots
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
        print(f"❌ Gemini API exception: {e}")
        return "Even my impeccable mind needs a nanosecond to recalibrate its genius! I'm ready!"

def check_movie_status(project_id):
    """Check if movie is ready using the correct endpoint"""
    headers = {'x-api-key': JSON2VIDEO_API_KEY}
    
    for i in range(10):
        try:
            response = requests.get(
                "https://api.json2video.com/v2/movies",
                params={"project": project_id},
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                movie_data = result.get('movie', {})
                status = movie_data.get('status')
                
                if status == 'done':
                    download_url = movie_data.get('url')
                    if download_url:
                        return {
                            'status': 'ready', 
                            'url': download_url,
                            'duration': movie_data.get('duration')
                        }
                
                elif status in ['pending', 'running']:
                    time.sleep(1)
                    continue
                    
                elif status == 'error':
                    return {'status': 'error', 'message': 'Movie rendering failed'}
                else:
                    time.sleep(1)
                    continue
            
            else:
                return {'status': 'error', 'message': f"Status check failed: {response.text}"}
                
        except Exception as e:
            return {'status': 'error', 'message': f"Status check error: {str(e)}"}
    
    return {'status': 'timeout', 'message': 'Movie rendering timed out'}

@app.route('/generate-speech', methods=['POST'])
def generate_speech():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No JSON data received"})
            
        text = data.get('text', 'Hello from Lovebot!')
        print(f"🔊 Original text: {text}")
        print(f"🔊 Original text length: {len(text)} characters")
        
        # Remove emojis before sending to TTS
        clean_text = remove_emojis(text)
        
        # Clean text for clear pronunciation (NO SYMBOLS, NO SLANG)
        clean_text = clean_text_for_speech(clean_text)
        
        # ORIGINAL WORKING TEXT LIMIT
        if len(clean_text) > 200:
            clean_text = clean_text[:200] + "..."
            print(f"🔊 Trimmed text to {len(clean_text)} characters")
        
        print(f"🔊 Final text for TTS: {clean_text}")
        
        payload = {
            "resolution": "full-hd",
            "scenes": [
                {
                    "elements": [
                        {
                            "type": "voice",
                            "text": clean_text,
                            "voice": "en-NZ-MitchellNeural",
                            "model": "azure"
                        }
                    ]
                }
            ]
        }
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': JSON2VIDEO_API_KEY
        }
        
        print("📡 Sending request to JSON2Video API...")
        response = requests.post(
            "https://api.json2video.com/v2/movies", 
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"✅ Create movie response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            project_id = result.get('project')
            print(f"🎬 Project created with ID: {project_id}")
            
            # Quick status check
            status_result = check_movie_status(project_id)
            
            if status_result['status'] == 'ready':
                return jsonify({
                    "success": True,
                    "audio_url": status_result['url'],
                    "movie_id": project_id,
                    "message": "Audio generated successfully!"
                })
            else:
                return jsonify({
                    "success": True,
                    "audio_url": f"https://assets.json2video.com/videos/{project_id}.mp4",
                    "movie_id": project_id,
                    "message": "Audio generation started!"
                })
                
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            print(f"❌ {error_msg}")
            return jsonify({
                "success": False,
                "error": error_msg
            })
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"success": False, "error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"Stack trace: {traceback.format_exc()}")
        return jsonify({"success": False, "error": error_msg})

@app.route('/chat', methods=['POST'])
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
    return jsonify({"status": "Backend is running!"})

@app.route('/clear-memory', methods=['POST'])
def clear_memory():
    """Clear conversation memory (optional endpoint)"""
    global conversation_memory
    conversation_memory = {}
    return jsonify({"success": True, "message": "Memory cleared!"})

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)