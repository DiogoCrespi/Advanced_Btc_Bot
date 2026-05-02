import requests
import logging
import os
import json
import asyncio
import websockets
from datetime import datetime, timedelta

logger = logging.getLogger("TVConnector")

class TVConnector:
    """
    Advanced TradingView Bridge (Institutional Grade).
    Uses Ticker Verification and Internal API paths to ensure data integrity.
    Inspired by: REFERENCIAS/tradingview-mcp
    """
    def __init__(self, host="host.docker.internal", port=9333):
        self.base_url = f"http://{host}:{port}"
        self.cache = {} # {asset: (timestamp, signal)}
        self.cache_ttl = 60
        
    async def _get_websocket_url(self, target_symbol):
        """Finds the TradingView tab and performs a regex match on the URL."""
        try:
            resp = requests.get(f"{self.base_url}/json", timeout=1.5)
            if resp.status_code == 200:
                tabs = resp.json()
                for tab in tabs:
                    url = tab.get('url', '').lower()
                    # A referência usa regex para garantir que é uma página de gráfico
                    if "tradingview.com/chart" in url and tab.get('type') == 'page':
                        return tab.get('webSocketDebuggerUrl')
            return None
        except:
            return None

    async def _evaluate_js(self, ws_url, script):
        """Injects JS with a strict timeout to prevent bot freezing."""
        try:
            # FIX CRITICO: O Chromium devolve 'localhost', mas no Docker precisamos do host.docker.internal
            if "localhost" in ws_url and "host.docker.internal" in self.base_url:
                ws_url = ws_url.replace("localhost", "host.docker.internal")

            # Timeout de 5s devido a alta carga no servidor remoto (wa 71%)
            async with asyncio.timeout(5.0):
                async with websockets.connect(ws_url) as websocket:
                    msg = {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": script,
                            "returnByValue": True
                        }
                    }
                    await websocket.send(json.dumps(msg))
                    resp = await websocket.recv()
                    data = json.loads(resp)
                    return data.get('result', {}).get('result', {}).get('value')
        except Exception as e:
            print(f"[TV-ERROR] JS Evaluation falhou: {e}", flush=True)
            return None

    def get_technical_summary(self, symbol="BTCBRL", interval="1h"):
        """
        Safe wrapper for technical signal extraction.
        """
        # print(f"[TV-DEBUG] Chamando get_technical_summary para {symbol}...", flush=True)
        now = datetime.now()
        if symbol in self.cache:
            ts, sig = self.cache[symbol]
            if now - ts < timedelta(seconds=self.cache_ttl):
                return sig

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            sig = loop.run_until_complete(self._fetch_signal(symbol))
            loop.close()
            
            self.cache[symbol] = (now, sig)
            return sig
        except Exception:
            return 0

    async def _fetch_signal(self, symbol):
        """Main logic with Ticker Verification."""
        ws_url = await self._get_websocket_url(symbol)
        if not ws_url:
            return 0
            
        # Script JS com Verificação de Ticker e Scroll para carregar widget
        script = f"""
        (function() {{
            try {{
                // 1. Scroll para garantir que o widget carregue
                var sidebar = document.querySelector('[class*="wrapper-Tv7LSjUz"]');
                if (sidebar) sidebar.scrollTop = sidebar.scrollHeight;

                var api = window.TradingViewApi._activeChartWidgetWV.value();
                var widget = api._chartWidget;
                var currentSymbol = widget.symbol().toUpperCase();
                var target = "{symbol}".toUpperCase();

                // 2. TICKER VERIFICATION
                if (!currentSymbol.includes(target)) {{
                    return "TICKER_MISMATCH:" + currentSymbol; 
                }}

                // 3. EXTRAÇÃO DE SINAL
                var technicals = document.querySelector('[class*="speedometer-"] [class*="counterText-"]');
                if (technicals) {{
                    var action = technicals.textContent.toUpperCase();
                    if (action.includes("STRONG BUY") || action.includes("COMPRA FORTE")) return 2;
                    if (action.includes("STRONG SELL") || action.includes("VENDA FORTE")) return -2;
                    if (action.includes("BUY") || action.includes("COMPRA")) return 1;
                    if (action.includes("SELL") || action.includes("VENDA")) return -1;
                    return "NEUTRAL";
                }}
                return "WIDGET_NOT_FOUND";
            }} catch(e) {{
                return "JS_ERROR:" + e.message;
            }}
        }})()
        """
        res = await self._evaluate_js(ws_url, script)
        
        # Debug Logs (Bypass logging filters)
        # if res:
        #    print(f"[TV] Ativo: {symbol} | Resposta: {res}", flush=True)
            
        try:
            if isinstance(res, (int, float)): return int(res)
            return 0
        except:
            return 0
