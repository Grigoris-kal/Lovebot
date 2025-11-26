import os
import requests

def test_elevenlabs():
    print("🧪 Testing ElevenLabs API Key...")
    
    # Get API key from environment
    api_key = os.environ.get('ELEVENLABS_API_KEY')
    
    print(f"🔑 API Key exists: {bool(api_key)}")
    print(f"📏 API Key length: {len(api_key) if api_key else 0}")
    
    if api_key:
        print(f"🔐 API Key starts with: {api_key[:10]}...")
        
        # Test the API key with ElevenLabs
        try:
            response = requests.post(
                'https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb',
                headers={
                    'Accept': 'audio/mpeg',
                    'Content-Type': 'application/json',
                    'xi-api-key': api_key
                },
                json={
                    "text": "Hello this is a test of the ElevenLabs API",
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.3,
                        "similarity_boost": 0.7
                    }
                },
                timeout=10
            )
            
            print(f"📡 ElevenLabs Response Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCCESS! API key is working!")
                print(f"🎵 Audio size: {len(response.content)} bytes")
            else:
                print(f"❌ FAILED! ElevenLabs error: {response.status_code}")
                print(f"📄 Error details: {response.text}")
                
        except Exception as e:
            print(f"💥 Exception: {str(e)}")
    else:
        print("❌ No API key found in environment!")
    
    print("🧪 Test complete!")

if __name__ == '__main__':
    test_elevenlabs()
