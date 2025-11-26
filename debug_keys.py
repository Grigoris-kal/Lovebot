from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def debug_keys():
    return jsonify({
        "elevenlabs_key_exists": bool(os.environ.get('ELEVENLABS_API_KEY')),
        "gemini_key_exists": bool(os.environ.get('GEMINI_API_KEY')),
        "elevenlabs_key_length": len(os.environ.get('ELEVENLABS_API_KEY', '')),
        "gemini_key_length": len(os.environ.get('GEMINI_API_KEY', ''))
    })

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)
