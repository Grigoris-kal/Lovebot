from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

@app.route('/')
def debug_keys():
    return jsonify({
        "elevenlabs_key_exists": bool(os.environ.get('ELEVENLABS_API_KEY')),
        "gemini_key_exists": bool(os.environ.get('GEMINI_API_KEY')),
        "elevenlabs_key_length": len(os.environ.get('ELEVENLABS_API_KEY', '')),
        "gemini_key_length": len(os.environ.get('GEMINI_API_KEY', ''))
    })

@app.route('/test-elevenlabs-debug', methods=['POST'])
def test_elevenlabs_debug():
    """Debug ElevenLabs API call"""
    try:
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        
        print(f"🔧 DEBUG: API Key exists: {bool(api_key)}")
        if api_key:
            print(f"🔧 DEBUG: API Key length: {len(api_key)}")
        
        # Test ElevenLabs API directly
        response = requests.post(
            'https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB',
            headers={
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': api_key or 'missing'
            },
            json={
                "text": "Hello this is a debug test",
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.7
                }
            },
            timeout=10
        )
        
        print(f"🔧 DEBUG: ElevenLabs status: {response.status_code}")
        
        return jsonify({
            "api_key_exists": bool(api_key),
            "elevenlabs_status": response.status_code,
            "error_details": response.text if response.status_code != 200 else "SUCCESS"
        })
        
    except Exception as e:
        print(f"🔧 DEBUG: Exception: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)
