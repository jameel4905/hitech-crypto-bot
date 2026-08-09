from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
from algo_bot import HitechAIBot  

app = FastAPI(title="Hitech Crypto Trading Engine")
ai_bot = HitechAIBot()  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Hitech Crypto Bot Backend Running Online!"}

@app.get("/api/live-prices")
def get_live_prices():
    try:
        resp = requests.get("https://api.coindcx.com/exchange/ticker")
        data = resp.json()
        target_markets = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'SHIBUSDT', 'DOTUSDT',
    'LINKUSDT', 'NEARUSDT', 'TRXUSDT', 'MATICUSDT', 'BCHUSDT', 'UNIUSDT', 'LTCUSDT', 'PEPEUSDT', 'ICPUSDT', 'APTUSDT',
    'SUIUSDT', 'LDOUSDT', 'FILUSDT', 'RENDERUSDT', 'HBARUSDT', 'ARBUSDT', 'VETUSDT', 'MKRUSDT', 'OPUSDT', 'GRTUSDT',
    'INJUSDT', 'KASUSDT', 'TIAUSDT', 'THETAUSDT', 'RUNEUSDT', 'FTMUSDT', 'AAVEUSDT', 'ALGOUSDT', 'FLOWUSDT', 'SANDUSDT',
    'MANAUSDT', 'EOSUSDT', 'GALAUSDT', 'WIFUSDT', 'BONKUSDT', 'FLOKIUSDT', 'FETUSDT', 'STXUSDT', 'SEIUSDT', 'XMRUSDT',
    'ETCUSDT', 'ATOMUSDT', 'IMXUSDT', 'AXSUSDT', 'CHZUSDT', 'CRVUSDT', 'EGLDUSDT', 'KSMUSDT', 'LUNCUSDT', 'NEOUSDT',
    'QNTUSDT', 'SNXUSDT', 'DYDXUSDT', 'ENSUSDT', 'GMTUSDT', 'JASMYUSDT', 'MINAUSDT', 'ORDIUSDT', '1INCHUSDT', 'ASTRUSDT',
    'APEUSDT', 'BLURUSDT', 'COMPUSDT', 'DASHUSDT', 'ENAUSDT', 'GMXUSDT', 'IDUSDT', 'JUPUSDT', 'KAVAUSDT', 'MANTAUSDT',
    'MASKUSDT', 'MEMEUSDT', 'NOTUSDT', 'NTRNUSDT', 'PENDLEUSDT', 'PYTHUSDT', 'QTUMUSDT', 'STRKUSDT', 'TWTUSDT', 'WLDUSDT',
    'WOOUSDT', 'YFIUSDT', 'ZECUSDT', 'ZKUSDT', 'AEVOUSDT', 'ALTUSDT', 'BOMEUSDT', 'ETHFIUSDT', 'ONDOUSDT', 'PIXELUSDT',
        ]
        result = []
        for item in data:
            if item.get('market') in target_markets:
                symbol = item['market'].replace('USDT', '/USDT')
                last_price = float(item.get('last_price', 0))
                change_24h = float(item.get('change_24_hour', 0))
                result.append({
                    "symbol": symbol,
                    "price": f"${last_price:.2f}",
                    "change": f"{change_24h:.2f}%",
                    "isUp": change_24h >= 0
                })
        result.sort(key=lambda x: target_markets.index(x['symbol'].replace('/', '')))
        return {"markets": result}
    except Exception as e:
        return {"markets": [], "error": str(e)}

@app.get("/api/bot-signal")
def get_bot_signal(symbol: str = "BTC/USDT"):
    signal_data = ai_bot.analyze_market(symbol)
    return signal_data

# 🔥 YAHAN FIX KIYA HAI: Ab ye Flutter se aane wale timeframe ko accept karega
@app.get("/api/chart-data")
def get_chart_data(symbol: str = "BTC/USDT", timeframe: str = "1h"):
    try:
        # Hardcoded '1h' hata kar dynamic timeframe lagaya hai
        ohlcv = ai_bot.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=40)
        chart_data = [{"time": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4], "volume": c[5]} for c in ohlcv]
        return {"status": "Success", "data": chart_data}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

@app.get("/api/place-order")
def place_order(symbol: str = "BTC/USDT", side: str = "buy"):
    order_result = ai_bot.execute_trade(symbol, side, 0.001) 
    return order_result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
