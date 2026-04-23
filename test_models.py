import asyncio
import os
import requests
from dotenv import load_dotenv

async def test_gemini():
    load_dotenv()
    keys = [os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 6) if os.getenv(f"GEMINI_KEY_{i}")]
    if not keys:
        print("Nenhuma chave Gemini encontrada.")
        return

    models = ["gemini-flash-latest", "gemini-pro-latest", "gemini-1.5-flash"]
    apis = ["v1beta"]
    
    for api in apis:
        for model in models:
            print(f"\nTestando API {api} com modelo {model}...")
            url = f"https://generativelanguage.googleapis.com/{api}/models/{model}:generateContent?key={keys[0]}"
            payload = {"contents": [{"parts": [{"text": "Diga Ola em uma palavra."}]}]}
            try:
                res = requests.post(url, json=payload, timeout=10)
                if res.status_code == 200:
                    print(f"✅ SUCESSO: {api}/{model}")
                else:
                    print(f"❌ FALHA {res.status_code}: {api}/{model} - {res.text[:100]}")
            except Exception as e:
                print(f"⚠️ ERRO: {api}/{model} - {e}")

if __name__ == '__main__':
    asyncio.run(test_gemini())
