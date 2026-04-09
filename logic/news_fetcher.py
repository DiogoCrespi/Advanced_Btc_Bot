# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
"""
logic/news_fetcher.py
─────────────────────────────────────────────────────────────────────────────
Dual-API News Fetcher with automatic failover.

Priority:  NewsAPI  →  Tavily  →  empty list
─────────────────────────────────────────────────────────────────────────────
Each article returned is a dict:
    {
        "title":       str,
        "description": str | None,
        "url":         str,
        "source":      str,          # "newsapi" | "tavily"
        "published_at": str          # ISO-8601 or raw string
    }
"""

from __future__ import annotations

import os
import logging
import time
import asyncio
from typing import List, Dict, Any

import aiohttp
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Environment keys ────────────────────────────────────────────────────────
NEWSAPI_KEY  = os.getenv("NEWSAPI_KEY",  "")
TAVILY_KEY   = os.getenv("TAVILY_KEY",   "")

# ─── Constants ────────────────────────────────────────────────────────────────
NEWSAPI_BASE = "https://newsapi.org/v2/everything"
TAVILY_BASE  = "https://api.tavily.com/search"

DEFAULT_QUERY   = "Bitcoin BTC crypto market"
DEFAULT_TIMEOUT = 10          # seconds per HTTP request
CACHE_TTL       = 300         # seconds – don't hammer the APIs (5 min)


class NewsFetcher:
    """
    Fetches crypto/financial news from NewsAPI, falling back to Tavily
    automatically if NewsAPI fails, is exhausted, or returns no results.
    """

    def __init__(
        self,
        query: str = DEFAULT_QUERY,
        max_articles: int = 10,
        timeout: int = DEFAULT_TIMEOUT,
        cache_ttl: int = CACHE_TTL,
    ):
        self.query        = query
        self.max_articles = max_articles
        self.timeout      = timeout
        self.cache_ttl    = cache_ttl

        # Simple in-process cache
        self._cache: List[Dict[str, Any]] = []
        self._cache_ts: float = 0.0

        # Runtime API status flags – reset every hour
        self._newsapi_ok   = True
        self._tavily_ok    = True
        self._flags_reset  = time.time()

        # MiroFish Integration
        self.mirofish_url = os.getenv("MIROFISH_API_URL")
        self.simulation_id = os.getenv("MIROFISH_SIMULATION_ID", "live_bot_sim")
        if self.mirofish_url:
            from logic.mirofish_client import MiroFishClient
            self.miro_client = MiroFishClient(self.mirofish_url)
        else:
            self.miro_client = None

    # ─── Public Interface ────────────────────────────────────────────────────

    def fetch(self, query: str | None = None) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for fetch_async.
        Returns a list of articles. Uses cache if still fresh.
        """
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                raise RuntimeError(
                    "fetch() was called from a running event loop. "
                    "Use fetch_async() instead in async contexts."
                )
        except RuntimeError:
            pass
        return asyncio.run(self.fetch_async(query))

    async def fetch_async(self, query: str | None = None) -> List[Dict[str, Any]]:
        """
        Returns a list of articles asynchronously. Uses cache if still fresh.
        Falls back automatically:  NewsAPI → Tavily → []
        """
        if time.time() - self._cache_ts < self.cache_ttl and self._cache:
            logger.debug("[NEWS] Returning cached articles (%d)", len(self._cache))
            return self._cache

        self._maybe_reset_flags()
        effective_query = query or self.query
        articles: List[Dict[str, Any]] = []

        async with aiohttp.ClientSession() as session:
            # ── Attempt 1: NewsAPI ────────────────────────────────────────────
            if self._newsapi_ok and NEWSAPI_KEY:
                articles = await self._fetch_newsapi(session, effective_query)
                if articles:
                    logger.info("[NEWS] NewsAPI returned %d articles.", len(articles))
                    self._update_cache(articles)
                    return articles
                else:
                    logger.warning("[NEWS] NewsAPI returned nothing – switching to Tavily.")
                    self._newsapi_ok = False

            # ── Attempt 2: Tavily ─────────────────────────────────────────────
            if self._tavily_ok and TAVILY_KEY:
                articles = await self._fetch_tavily(session, effective_query)
                if articles:
                    logger.info("[NEWS] Tavily returned %d articles.", len(articles))
                    self._update_cache(articles)
                    return articles
                else:
                    logger.warning("[NEWS] Tavily returned nothing – all APIs exhausted.")
                    self._tavily_ok = False

        # ── Total failure ─────────────────────────────────────────────────
        if not NEWSAPI_KEY and not TAVILY_KEY:
            logger.error("[NEWS] No API keys configured. Set NEWSAPI_KEY or TAVILY_KEY in .env")
        
        return self._cache or []   # return stale cache if available

    def _calculate_keyword_score(self, arts: List[Dict[str, Any]]) -> float:
        """Helper to calculate keyword-based sentiment score from articles."""
        BULLISH = {"rally", "surge", "soar", "bull", "breakout", "all-time high", "ath",
                   "recover", "adoption", "etf", "approval", "gain", "pump"}
        BEARISH = {"crash", "dump", "bear", "drop", "hack", "ban", "lawsuit", "sec",
                   "collapse", "fear", "liquidation", "fall", "crisis", "recession"}

        score = 0.0
        for a in arts:
            text = f"{a.get('title','')} {a.get('description','')}".lower()
            for w in BULLISH:
                if w in text:
                    score += 1
            for w in BEARISH:
                if w in text:
                    score -= 1

        return float(max(-1.0, min(1.0, score / max(len(arts), 1))))

    def _fetch_miro_score(self) -> tuple[float, bool]:
        """Helper to fetch sentiment from MiroFish if available."""
        miro_score = 0.0
        has_miro = False
        if self.miro_client:
            try:
                miro_summary = self.miro_client.get_sentiment_summary(self.simulation_id)
                sentiment = miro_summary.get("sentiment", "Neutral")
                confidence = miro_summary.get("confidence", 0.5)
                
                if sentiment == "Bullish":
                    miro_score = confidence
                elif sentiment == "Bearish":
                    miro_score = -confidence
                
                has_miro = True
                logger.debug("[MIROFISH] Simulation: %s | Sentiment: %s | Confidence: %.2f", self.simulation_id, sentiment, confidence)
            except Exception as e:
                logger.warning("[MIROFISH] Sentiment fetch failed: %s", e)

        return miro_score, has_miro

    def get_sentiment_keywords(self, articles: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """
        Returns a simple keyword-based sentiment summary from headlines.
        Useful for IntelligenceManager without an LLM.
        """
        arts = articles if articles is not None else self.fetch()
        if not arts:
            return {"signal": "neutral", "score": 0.0, "article_count": 0}

        normalized = self._calculate_keyword_score(arts)

        # ─── Attempt 3: MiroFish Integration (Advanced) ──────────────────────
        miro_score, has_miro = self._fetch_miro_score()

        # Combine scores (70/30 weight if MiroFish is available)
        if has_miro:
            final_score = (0.3 * normalized) + (0.7 * miro_score)
        else:
            final_score = normalized

        # Clamp again
        final_score = float(max(-1.0, min(1.0, final_score)))
        signal = "bullish" if final_score > 0.1 else ("bearish" if final_score < -0.1 else "neutral")

        return {
            "signal":        signal,
            "score":         round(final_score, 3),
            "keyword_score": round(normalized, 3),
            "miro_score":    round(miro_score, 3) if has_miro else None,
            "article_count": len(arts),
        }

    # ─── Private: NewsAPI ─────────────────────────────────────────────────────

    async def _fetch_newsapi(self, session: aiohttp.ClientSession, query: str) -> List[Dict[str, Any]]:
        """Calls NewsAPI /v2/everything asynchronously and normalizes response."""
        params = {
            "q":        query,
            "language": "en",
            "sortBy":   "publishedAt",
            "pageSize": str(self.max_articles),
            "apiKey":   NEWSAPI_KEY,
        }
        try:
            async with session.get(NEWSAPI_BASE, params=params, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                data = await resp.json()

                if resp.status == 429 or data.get("code") in ("rateLimited", "maximumResultsReached"):
                    logger.warning("[NEWS][NewsAPI] Rate-limit / quota hit (HTTP %s).", resp.status)
                    self._newsapi_ok = False
                    return []

                if resp.status != 200 or data.get("status") != "ok":
                    logger.warning("[NEWS][NewsAPI] Non-OK response: %s", data.get("message", resp.status))
                    self._newsapi_ok = False
                    return []

                return [
                    {
                        "title":        a.get("title", ""),
                        "description":  a.get("description"),
                        "url":          a.get("url", ""),
                        "source":       "newsapi",
                        "published_at": a.get("publishedAt", ""),
                    }
                    for a in data.get("articles", [])
                ]

        except asyncio.TimeoutError:
            logger.warning("[NEWS][NewsAPI] Request timed out.")
            self._newsapi_ok = False
        except Exception as exc:
            logger.warning("[NEWS][NewsAPI] Unexpected error: %s", exc)
            self._newsapi_ok = False

        return []

    # ─── Private: Tavily ──────────────────────────────────────────────────────

    async def _fetch_tavily(self, session: aiohttp.ClientSession, query: str) -> List[Dict[str, Any]]:
        """Calls Tavily Search API asynchronously and normalizes response."""
        payload = {
            "api_key":              TAVILY_KEY,
            "query":                query,
            "search_depth":         "basic",
            "include_answer":       False,
            "include_raw_content":  False,
            "max_results":          self.max_articles,
            "topic":                "news",
        }
        try:
            async with session.post(TAVILY_BASE, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                if resp.status == 429:
                    logger.warning("[NEWS][Tavily] Rate-limit hit.")
                    self._tavily_ok = False
                    return []

                if resp.status != 200:
                    text = await resp.text()
                    logger.warning("[NEWS][Tavily] HTTP %s – %s", resp.status, text[:200])
                    self._tavily_ok = False
                    return []

                data = await resp.json()
                return [
                    {
                        "title":        r.get("title", ""),
                        "description":  r.get("content", "")[:280] if r.get("content") else None,
                        "url":          r.get("url", ""),
                        "source":       "tavily",
                        "published_at": r.get("published_date", ""),
                    }
                    for r in data.get("results", [])
                ]

        except asyncio.TimeoutError:
            logger.warning("[NEWS][Tavily] Request timed out.")
            self._tavily_ok = False
        except Exception as exc:
            logger.warning("[NEWS][Tavily] Unexpected error: %s", exc)
            self._tavily_ok = False

        return []

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _update_cache(self, articles: List[Dict[str, Any]]) -> None:
        self._cache    = articles
        self._cache_ts = time.time()

    def _maybe_reset_flags(self) -> None:
        """Reset API-failure flags every hour so transient errors don't last forever."""
        if time.time() - self._flags_reset > 3600:
            self._newsapi_ok  = True
            self._tavily_ok   = True
            self._flags_reset = time.time()
            logger.debug("[NEWS] API status flags reset.")

    @property
    def active_provider(self) -> str:
        """Returns which provider would be used right now."""
        if self._newsapi_ok and NEWSAPI_KEY:
            return "newsapi"
        if self._tavily_ok and TAVILY_KEY:
            return "tavily"
        return "none"


# ─── Quick smoke-test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    fetcher  = NewsFetcher()
    articles = fetcher.fetch()
    print(f"\n[Provider: {fetcher.active_provider}]  {len(articles)} articles fetched\n")
    for i, a in enumerate(articles[:5], 1):
        print(f"  {i}. [{a['source'].upper()}] {a['title']}")

    print("\n--- Sentiment Analysis ---")
    print(json.dumps(fetcher.get_sentiment_keywords(articles), indent=2))
