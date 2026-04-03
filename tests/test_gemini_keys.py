import os
import google.generativeai as genai
import time

# Lista de chaves fornecidas pelo usuario
KEYS = [
    {"name": "Gemini 1", "key": os.environ.get("GEMINI_KEY_1")},
    {"name": "Gemini 2", "key": os.environ.get("GEMINI_KEY_2")},
    {"name": "Gemini 3", "key": os.environ.get("GEMINI_KEY_3")},
    {"name": "Gemini 4", "key": os.environ.get("GEMINI_KEY_4")}
]

def test_gemini_key(name, api_key):
    print(f"\n--- Testando {name} ---")
    genai.configure(api_key=api_key)
    # Usando o modelo mais comum para teste
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content("Diga apenas 'OK' se voce estiver funcionando.")
        print(f"RESPOSTA: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"ERRO: {e}")
        return False

if __name__ == "__main__":
    results = {}
    for item in KEYS:
        success = test_gemini_key(item['name'], item['key'])
        results[item['name']] = "FUNCIONANDO" if success else "FALHA"
        time.sleep(1) # Evitar spam
    
    print("\n" + "="*30)
    print("RESUMO DOS TESTES GEMINI")
    print("="*30)
    for name, status in results.items():
        print(f"{name}: {status}")
