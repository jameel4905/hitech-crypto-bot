from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import FastAPI, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
from algo_bot import HitechAIBot
import os

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
        target_markets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'LINKUSDT', 'AVAXUSDT', 'TRXUSDT']
        result = []
        for item in data:
            if item.get('market') in target_markets:
                symbol = item['market'].replace('USDT', '/USDT')
                last_price = float(item.get('last_price', 0))
                change_24h = float(item.get('change_24_hour', 0))
                result.append({"symbol": symbol, "price": f"${last_price:.2f}", "change": f"{change_24h:.2f}%", "isUp": change_24h >= 0})
        return {"markets": result}
    except Exception as e:
        return {"markets": [], "error": str(e)}

@app.get("/api/bot-signal")
def get_bot_signal(symbol: str = "BTC/USDT"):
    return ai_bot.analyze_market(symbol)


# --- YAHAN MONGODB WALI BIMARI KO HATA DIYA HAI ---
class TradeRequest(BaseModel):
    user_id: str
    broker: str
    symbol: str
    side: str
    amount: float
    api_key: str
    secret_key: str
    is_futures: bool

@app.post("/api/trade/execute")
def execute_real_trade(trade: TradeRequest):
    try:
        # Calls algo_bot
        result = ai_bot.execute_trade(trade.symbol, trade.side, trade.amount)
        
        if result.get("status") == "Success":
            return {"status": "success", "message": result.get("message")}
        else:
            return {"status": "error", "message": result.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/trade/history/{user_id}")
def get_trade_history(user_id: str):
    history = [{"symbol": "BTC/USDT", "side": "BUY", "price": 64200.50, "stop_loss": 57780.45}]
    return {"status": "success", "history": history}

@app.post("/api/bot/toggle")
def toggle_bot(data: dict):
    return {"status": "success", "message": "Bot status updated"}


# --- ADMIN PANEL ---
pending_activations = []

@app.post("/api/payment/submit")
def submit_payment(user_id: str, utr: str):
    pending_activations.append({"user_id": user_id, "utr": utr, "status": "Pending"})
    return {"status": "Success", "message": "Payment submitted successfully!"}

@app.get("/admin/panel", response_class=HTMLResponse)
def admin_panel():
    return HTMLResponse(content="<html><body><h2>Admin Panel Running</h2></body></html>")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
