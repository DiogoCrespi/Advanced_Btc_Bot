import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from logic.news_fetcher import NewsFetcher
from logic.news_fetcher import NewsFetcher

class IntelligenceManager:
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self.gold_ticker = "GC=F"
        self.sp500_ticker = "^GSPC"
        
        self.news_fetcher = NewsFetcher(
            query="Bitcoin BTC crypto market OR Macro Economics",
            max_articles=15
        )
        self.last_update = None
        self.cache = {}
        # Sentiment storage
        self._news_sentiment: dict = {"signal": "neutral", "score": 0.0, "article_count": 0}
        
    def fetch_macro_data(self):
        """Fetches DXY, Gold, and S&P500 to gauge global market regime."""
        try:
            # DXY: Higher DXY usually means Lower BTC (Inverse correlation)
            dxy = yf.Ticker(self.dxy_ticker).history(period="5d")
            # Gold: BTC often follows Gold in 'Digital Gold' regimes
            gold = yf.Ticker(self.gold_ticker).history(period="5d")
            # S&P500: High correlation with BTC in 'Risk-On' regimes
            sp500 = yf.Ticker(self.sp500_ticker).history(period="5d")
            
            if dxy.empty or gold.empty:
                return None
                
            # 4. News Sentiment (User's news_fetcher logic)
            sentiment_data = self.fetch_news_sentiment()
            
            data = {
                "dxy_close": dxy['Close'].iloc[-1],
                "dxy_change": (dxy['Close'].iloc[-1] / dxy['Close'].iloc[-2]) - 1,
                "gold_close": gold['Close'].iloc[-1],
                "gold_change": (gold['Close'].iloc[-1] / gold['Close'].iloc[-2]) - 1,
                "sp500_close": sp500['Close'].iloc[-1],
                "sp500_change": (sp500['Close'].iloc[-1] / sp500['Close'].iloc[-2]) - 1,
                "news_sentiment": sentiment_data['score'],
                "news_signal": sentiment_data['signal'],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.cache = data
            self.last_update = datetime.now()
            return data
        except Exception as e:
            print(f"[INTEL] Error fetching macro: {e}")
            return None

    def fetch_news_sentiment(self) -> dict:
        """Fetches latest news and returns keyword-based sentiment."""
        try:
            articles = self.news_fetcher.fetch()
            sentiment = self.news_fetcher.get_sentiment_keywords(articles)
            self._news_sentiment = sentiment
            provider = self.news_fetcher.active_provider
            return sentiment
        except Exception as e:
            print(f"[INTEL] News fetch error: {e}")
            return {"signal": "neutral", "score": 0.0, "article_count": 0}

    def calculate_macro_risk(self):
        """
        Calculates a risk score from 0 (Safe) to 1 (Extreme Risk).
        Logic:
        - Rising DXY (+0.5% day) increases risk for crypto.
        - Gold dumping (-1% day) might signal liquidity crunch.
        - S&P500 dumping (-2% day) usually correlates with BTC crash.
        - Bearish news sentiment increases risk; bullish sentiment decreases it.
        """
        data = self.cache if self.cache else self.fetch_macro_data()
        if not data:
            return 0.5  # Neutral fallback

        risk_score = 0.5  # Start at neutral

        # DXY Pressure (Inverse)
        if data['dxy_change'] > 0.005:
            risk_score += 0.2   # Strong Dollar = Weak BTC
        elif data['dxy_change'] < -0.005:
            risk_score -= 0.1   # Weak Dollar = Good for BTC

        # Equity Correlation (Positive)
        if data.get('sp500_change', 0) < -0.015:
            risk_score += 0.3 # Stock market crash = BTC crash (90% correlation in panics)
            
        # News Sentiment (Inverse to Risk)
        # Positive sentiment (0.5) reduces risk by 0.15
        sentiment_score = data.get('news_sentiment', 0)
        risk_score -= (sentiment_score * 0.3)
            
        # Clamp to 0-1
        return float(np.clip(risk_score, 0, 1))

    def get_market_regime(self):
        """Identifies the current macro regime."""
        data = self.cache if self.cache else self.fetch_macro_data()
        if not data: return "Unknown"
        
        dxy_up = data['dxy_change'] > 0
        sp_up = data['sp500_change'] > 0
        
        if dxy_up and not sp_up: return "Risk-Off / Strong Dollar"
        if not dxy_up and sp_up: return "Risk-On / Weak Dollar"
        if dxy_up and sp_up: return "Inflationary / Rare Correlation"
        return "Uncertain / Sideways"

    def get_summary(self):
        risk = self.calculate_macro_risk()
        regime = self.get_market_regime()
        news   = self._news_sentiment or {"signal": "neutral", "score": 0.0, "article_count": 0}
        return {
            "risk_score":      round(risk, 2),
            "regime":          regime,
            "dxy_trend":       "UP" if self.cache.get('dxy_change', 0) > 0 else "DOWN",
            "sp500_trend":     "UP" if self.cache.get('sp500_change', 0) > 0 else "DOWN",
            "dxy_change":      round(self.cache.get('dxy_change', 0) * 100, 2),
            "gold_change":     round(self.cache.get('gold_change', 0) * 100, 2),
            "sp500_change":    round(self.cache.get('sp500_change', 0) * 100, 2),
            "last_update":     self.cache.get('timestamp'),
            "news_signal":     news.get('signal', 'neutral'),
            "news_score":      news.get('score', 0.0),
            "news_articles":   news.get('article_count', 0),
            "news_provider":   self.news.active_provider,
        }

if __name__ == "__main__":
    mgr = IntelligenceManager()
    print("Fetching Macro Analysis...")
    print(mgr.get_summary())
