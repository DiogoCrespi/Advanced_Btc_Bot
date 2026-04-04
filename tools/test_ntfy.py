import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_ntfy():
    topic = os.getenv("NTFY_TOPIC", "btc_bot_trades")
    # For testing from inside container or remote host network
    url = f"http://localhost:8081/{topic}"
    
    message = "[TESTE] ✅ Bot de Trading enviando sinal para ntfy!"
    
    try:
        print(f"Enviando mensagem para {url}...")
        response = requests.post(url, 
                                data=message.encode('utf-8'),
                                headers={
                                    "Title": "TESTE BTC BOT",
                                    "Priority": "high",
                                    "Tags": "robot"
                                },
                                timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    test_ntfy()
