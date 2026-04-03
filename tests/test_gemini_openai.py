import os
import openai

def test_gemini_openai_compat(api_key):
    if not api_key:
        print("Erro: Chave nao fornecida via GEMINI_KEY_1")
        return False
    print(f"Testando chave Gemini {api_key[:10]}... via interface OpenAI")
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    try:
        response = client.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[{"role": "user", "content": "Olá, você é o Gemini via OpenAI SDK?"}]
        )
        print("SUCESSO!")
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"FALHA: {e}")
        return False

if __name__ == "__main__":
    key = os.environ.get("GEMINI_KEY_1")
    test_gemini_openai_compat(key)
