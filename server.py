from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/api/live-prices")
def get_live_prices():
    try:
        # CoinCap API (Render/AWS IP Block nahi hota)
        url = "https://api.coincap.io/v2/assets?limit=50"
        headers = {'Accept-Encoding': 'gzip'}
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json().get('data', [])

        result = []
        for item in data:
            symbol = item.get('symbol', '').upper()
            price = float(item.get('priceUsd', 0))
            change = float(item.get('changePercent24Hr', 0))

            result.append({
                'symbol': f"{symbol}/USDT",
                'price': f"{price:.4f}" if price < 1 else f"{price:.2f}",
                'isUp': change >= 0
            })

        return {"markets": result}

    except Exception as e:
        # Fallback dummy data agar API response slow ho
        return {
            "markets": [
                {"symbol": "BTC/USDT", "price": "64250.00", "isUp": True},
                {"symbol": "ETH/USDT", "price": "3450.50", "isUp": True},
                {"symbol": "SOL/USDT", "price": "145.20", "isUp": False}
            ],
            "error": str(e)
        }
