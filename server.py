from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/api/live-prices")
def get_live_prices():
    try:
        # CoinDCX live ticker API call
        resp = requests.get("https://api.coindcx.com/exchange/ticker")
        data = resp.json()

        # CoinDCX ke exact market symbols
        target_markets = [
            'B-BTC_USDT', 'B-ETH_USDT', 'B-BNB_USDT', 'B-SOL_USDT', 'B-XRP_USDT', 
            'B-ADA_USDT', 'B-DOGE_USDT', 'B-AVAX_USDT', 'B-SHIB_USDT', 'B-DOT_USDT',
            'B-LINK_USDT', 'B-NEAR_USDT', 'B-TRX_USDT', 'B-MATIC_USDT', 'B-BCH_USDT', 
            'B-UNI_USDT', 'B-LTC_USDT', 'B-PEPE_USDT', 'B-ICP_USDT', 'B-APT_USDT',
            'B-SUI_USDT', 'B-LDO_USDT', 'B-FIL_USDT', 'B-RENDER_USDT', 'B-HBAR_USDT', 
            'B-ARB_USDT', 'B-VET_USDT', 'B-MKR_USDT', 'B-OP_USDT', 'B-GRT_USDT',
            'B-INJ_USDT', 'B-TIA_USDT', 'B-THETA_USDT', 'B-RUNE_USDT', 'B-FTM_USDT', 
            'B-AAVE_USDT', 'B-ALGO_USDT', 'B-FLOW_USDT', 'B-SAND_USDT', 'B-MANA_USDT'
        ]

        result = []
        for item in data:
            market_name = item.get('market', '')
            if market_name in target_markets:
                # App display format ke liye 'B-BTC_USDT' ko 'BTC/USDT' banana
                clean_symbol = market_name.replace('B-', '').replace('_', '/')
                last_price = float(item.get('last_price', 0))
                change_val = float(item.get('change_24_hour', 0))

                result.append({
                    'symbol': clean_symbol,
                    'price': f"{last_price:.4f}" if last_price < 1 else f"{last_price:.2f}",
                    'isUp': change_val >= 0
                })

        return {"markets": result}

    except Exception as e:
        return {"markets": [], "error": str(e)}
