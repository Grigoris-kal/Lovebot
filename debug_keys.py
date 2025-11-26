from flask import Flask, jsonify, request
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

# ADD THIS NEW ENDPOINT:
@app.route('/test-elevenlabs', methods=['POST'])
def test_elevenlabs():
    """Test ElevenLabs API directly"""
    try:
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        
        if not api_key:
            return jsonify({"error": "No API key found"}), 500
        
        response = requests.post(
            'https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb',
            headers={
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': api_key
            },
            json={
                "text": "Hello this is a test of ElevenLabs API",
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.7
                }
            },
            timeout=10
        )
        
        return jsonify({
            "api_key_exists": bool(api_key),
            "api_key_length": len(api_key),
            "elevenlabs_status": response.status_code,
            "elevenlabs_response": response.text if response.status_code != 200 else "SUCCESS - Audio received",
            "audio_size": len(response.content) if response.status_code == 200 else 0
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)
