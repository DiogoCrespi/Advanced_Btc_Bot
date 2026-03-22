import websocket
import json
import threading

class BinanceWS:
    def __init__(self, symbol="btcusdt", callback=None):
        self.symbol = symbol.lower()
        self.callback = callback
        self.ws = None
        self.socket = f"wss://stream.binance.com:9443/ws/{self.symbol}@miniTicker"

    def on_message(self, ws, message):
        data = json.loads(message)
        if self.callback:
            # Format: {'symbol': 'BTCUSDT', 'price': 50000.0, 'time': 1612345678}
            ticker = {
                'symbol': data['s'],
                'price': float(data['c']),
                'time': data['E']
            }
            self.callback(ticker)

    def on_error(self, ws, error):
        print(f"WS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("### WS Closed ###")

    def on_open(self, ws):
        print(f"Opened connection to {self.symbol} MiniTicker")

    def start(self):
        self.ws = websocket.WebSocketApp(
            self.socket,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        # Start WS in a separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def stop(self):
        if self.ws:
            self.ws.close()

if __name__ == "__main__":
    def print_ticker(ticker):
        print(f"Live Price: {ticker['price']}")

    ws = BinanceWS(callback=print_ticker)
    ws.start()
    
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        ws.stop()
