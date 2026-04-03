import os
from google import genai
import time

KEYS = [
    {"name": "Gemini 1", "key": os.environ.get("GEMINI_KEY_1")},
    {"name": "Gemini 2", "key": os.environ.get("GEMINI_KEY_2")},
    {"name": "Gemini 3", "key": os.environ.get("GEMINI_KEY_3")},
    {"name": "Gemini 4", "key": os.environ.get("GEMINI_KEY_4")}
]

def test_google_genai_key(name, api_key):
    print(f"\n--- Testando {name} (New SDK) ---")
    try:
        client = genai.Client(api_key=api_key)
        # Usando o modelo solicitado pelo usuario
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Diga OK.",
        )
        print(f"RESPOSTA: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"ERRO: {e}")
        return False

if __name__ == "__main__":
    results = {}
    for item in KEYS:
        success = test_google_genai_key(item['name'], item['key'])
        results[item['name']] = "FUNCIONANDO" if success else "FALHA"
        time.sleep(1)
    
    print("\n" + "="*30)
    print("RESUMO DOS TESTES NEW GOOGLE GENAI")
    print("="*30)
    for name, status in results.items():
        print(f"{name}: {status}")
