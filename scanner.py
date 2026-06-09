from binance.client import Client

def get_active_symbols(client, min_volume=100000000, min_change=3, limit=5):
    tickers = client.get_ticker()
    active = []

    for ticker in tickers:
        symbol = ticker.get("symbol", "")

        if not symbol.endswith("USDT"):
            continue

        if symbol in ["USDCUSDT", "BUSDUSDT", "TUSDUSDT", "FDUSDUSDT"]:
            continue

        try:
            quote_volume = float(ticker.get("quoteVolume", 0))
            price_change = float(ticker.get("priceChangePercent", 0))
        except:
            continue

        if quote_volume >= min_volume and abs(price_change) >= min_change:
            active.append({
                "symbol": symbol,
                "quoteVolume": quote_volume,
                "priceChangePercent": price_change
            })

    active = sorted(active, key=lambda x: x["quoteVolume"], reverse=True)
    return [item["symbol"] for item in active[:limit]]
