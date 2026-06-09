from services.binance_service import get_ohlcv


def fetch_market_data(symbols: list[str], interval: str, limit: int) -> dict:
    market_data = {}
    for symbol in symbols:
        df = get_ohlcv(symbol, interval=interval, limit=limit)
        market_data[symbol] = df
    return market_data


def fetch_4h_data(symbols: list[str], limit: int = 100) -> dict:
    """Fetch 4-hour OHLCV for macro trend filter (EMA20 vs EMA50 alignment)."""
    data = {}
    for symbol in symbols:
        df = get_ohlcv(symbol, interval="4h", limit=limit)
        data[symbol] = df
    return data
