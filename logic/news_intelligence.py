import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class NewsIntelligence:
    """
    Agente de Inteligência de Notícias (Inspirado no @worldmonitor).
    Coleta notícias do mercado cripto e macro para gerar um 'Sentiment Score'.
    """

    def __init__(self):
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.tavily_key = os.getenv("TAVILY_KEY")
        
        # Léxico básico de sentimento (Heurística rápida)
        self.bullish_keywords = [
            "bullish", "rally", "growth", "all-time high", "etf approval", 
            "adoption", "moon", "pumping", "support", "breakout", "accumulating",
            "whale buy", "inflow", "halving", "buy the dip"
        ]
        self.bearish_keywords = [
            "bearish", "crash", "correction", "ban", "regulation", "fud", 
            "dumping", "liquidation", "sell-off", "outflow", "hacked", 
            "scam", "resistance", "inflation", "recession", "rate hike"
        ]

    def fetch_btc_news(self):
        """
        Busca notícias recentes de BTC e Macro via NewsAPI com fallback para Tavily.
        """
        print("[NOTICIAS] Coletando manchetes do mercado...")
        headlines = []
        
        if self.newsapi_key:
            try:
                # Busca notícias das últimas 24h
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                url = f"https://newsapi.org/v2/everything?q=bitcoin+OR+crypto+OR+fed+OR+inflation&from={yesterday}&sortBy=publishedAt&language=en&apiKey={self.newsapi_key}"
                res = requests.get(url, timeout=10)
                data = res.json()
                if data.get("status") == "ok":
                    for art in data.get("articles", [])[:10]:
                        headlines.append(f"{art['title']} - {art['description']}")
            except Exception as e:
                print(f"[LOG] Falha NewsAPI: {e}")

        # Fallback ou Enriquecimento via Tavily
        if not headlines and self.tavily_key:
            try:
                url = "https://api.tavily.com/search"
                payload = {
                    "api_key": self.tavily_key,
                    "query": "latest bitcoin and crypto macro news sentiment",
                    "search_depth": "basic",
                    "max_results": 5
                }
                res = requests.post(url, json=payload, timeout=10)
                data = res.json()
                for result in data.get("results", []):
                    headlines.append(f"{result['title']} - {result['content']}")
            except Exception as e:
                print(f"[LOG] Falha Tavily: {e}")

        return headlines

    def get_sentiment_score(self):
        """
        Calcula o sentiment score baseado em palavras-chave.
        Retorno: -1.0 (Extremo Medo) a 1.0 (Extrema Ganância)
        """
        headlines = self.fetch_btc_news()
        if not headlines:
            return 0.0 # Neutro
        
        score = 0.0
        text_corpus = " ".join(headlines).lower()
        
        # Contagem simples de hits
        bull_hits = sum(1 for word in self.bullish_keywords if word in text_corpus)
        bear_hits = sum(1 for word in self.bearish_keywords if word in text_corpus)
        
        total_hits = bull_hits + bear_hits
        if total_hits > 0:
            score = (bull_hits - bear_hits) / total_hits
            
        print(f"[SENTIMENTO] Bull Hits: {bull_hits} | Bear Hits: {bear_hits} | Score: {score:.2f}")
        return score

if __name__ == "__main__":
    ni = NewsIntelligence()
    score = ni.get_sentiment_score()
    print(f"Final Sentiment Score: {score}")
