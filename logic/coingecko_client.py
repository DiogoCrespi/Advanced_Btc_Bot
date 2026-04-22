# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import requests
import time

class CoinGeckoClient:
    def __init__(self, cache_timeout=180):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache_timeout = cache_timeout
        self.last_dominance = 50.0 # Neutral fallback
        self.last_fetch_time = 0

    def get_btc_dominance(self):
        """
        Retorna a Dominancia do Bitcoin atual, cacheados por X segundos para evitar rate limits agressivos.
        """
        now = time.time()
        if now - self.last_fetch_time < self.cache_timeout:
            return self.last_dominance

        try:
            headers = {"accept": "application/json"}
            url = f"{self.base_url}/global"
            r = requests.get(url, headers=headers, timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                if data and 'data' in data and 'market_cap_percentage' in data['data']:
                    self.last_dominance = float(data['data']['market_cap_percentage'].get('btc', self.last_dominance))
                    self.last_fetch_time = now
                else:
                    print(f"[CoinGecko] Resposta inesperada: {data}")
            else:
               print(f"[CoinGecko] Falha HTTP: {r.status_code}") 
               # Nao atualizamos o fetch_time no caso de fallbacks intermitentes.
        except Exception as e:
            print(f"[CoinGecko] Erro ao extrair dominancia: {e}")

        return self.last_dominance
