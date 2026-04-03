import openai
import os
from google import genai
import time

GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEYS = [
    os.environ.get("GEMINI_KEY_1"),
    os.environ.get("GEMINI_KEY_2"),
    os.environ.get("GEMINI_KEY_3"),
    os.environ.get("GEMINI_KEY_4")
]

def test_groq():
    print("\n--- Testando GROQ ---")
    client = openai.OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")
    try:
        resp = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"user", "content":"OK?"}])
        print(f"GROQ: OK")
        return True
    except Exception as e:
        print(f"GROQ FALHOU: {e}")
        return False

def test_gemini(key_index, key):
    print(f"\n--- Testando Gemini {key_index+1} ---")
    try:
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(model="gemini-1.5-flash", contents="OK")
        print(f"GEMINI {key_index+1}: OK")
        return True
    except Exception as e:
        print(f"GEMINI {key_index+1} FALHOU: {e}")
        return False

if __name__ == "__main__":
    test_groq()
    for i, k in enumerate(GEMINI_KEYS):
        test_gemini(i, k)
