from fastapi import FastAPI
import requests

app = FastAPI()

# Standard Universal Coin List
symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'SHIBUSDT', 'DOTUSDT',
    'LINKUSDT', 'NEARUSDT', 'TRXUSDT', 'MATICUSDT', 'BCHUSDT', 'UNIUSDT', 'LTCUSDT', 'PEPEUSDT', 'ICPUSDT', 'APTUSDT',
    'SUIUSDT', 'LDOUSDT', 'FILUSDT', 'RENDERUSDT', 'HBARUSDT', 'ARBUSDT', 'VETUSDT', 'MKRUSDT', 'OPUSDT', 'GRTUSDT',
    'INJUSDT', 'TIAUSDT', 'THETAUSDT', 'RUNEUSDT', 'FTMUSDT', 'AAVEUSDT', 'ALGOUSDT', 'FLOWUSDT', 'SANDUSDT', 'MANAUSDT'
]

@app.get("/api/live-prices")
def get_live_prices():
    try:
        # Binance Global Ticker API (Fast & Universal)
        url = "https://api.binance.com/api/v3/ticker/24hr"
        resp = requests.get(url, timeout=5)
        data = resp.json()

        data_dict = {item['symbol']: item for item in data if 'symbol' in item}

        result = []
        for sym in symbols:
            if sym in data_dict:
                item = data_dict[sym]
                last_price = float(item.get('lastPrice', 0))
                change_val = float(item.get('priceChangePercent', 0))

                # Display Name (Universal format: BTC/USDT)
                base = sym.replace('USDT', '')
                display_name = f"{base}/USDT"

                result.append({
                    'symbol': display_name,
                    'price': f"{last_price:.4f}" if last_price < 1 else f"{last_price:.2f}",
                    'isUp': change_val >= 0
                })

        return {"markets": result}

    except Exception as e:
        return {"markets": [], "error": str(e)}
