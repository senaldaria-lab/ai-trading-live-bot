import logging

from binance.client import Client

from config.settings import SETTINGS

logger = logging.getLogger(__name__)

# Safety marker: this module is MARKET DATA ONLY.
# No order-execution functions are defined here.
# Importing code must never call create_order / order_market_buy / order_market_sell
# or any other write operation on the Binance client.
READONLY_MODE: bool = True

# Momentum / price-movement signals must always come from real OHLCV candles
# (get_ohlcv → klines endpoint).  Never use get_symbol_ticker() or
# get_ticker_24h() / priceChangePercent for trade decisions — 24h rolling
# statistics include overnight/weekend gaps and do not reflect recent 1h momentum.

_FORBIDDEN_CLIENT_METHODS = frozenset({
    "create_order",
    "order_market_buy",
    "order_market_sell",
    "order_limit_buy",
    "order_limit_sell",
    "cancel_order",
    "order_oco_buy",
    "order_oco_sell",
    "create_test_order",
})


def _assert_readonly(method_name: str) -> None:
    if method_name in _FORBIDDEN_CLIENT_METHODS:
        raise RuntimeError(
            f"[SAFETY BLOCK] Attempt to call forbidden Binance method '{method_name}'. "
            "This bot is SIGNALS_ONLY and must never execute orders."
        )


client = Client(SETTINGS.BINANCE_API_KEY, SETTINGS.BINANCE_API_SECRET)


def get_ohlcv(symbol: str, interval: str = "1h", limit: int = 200):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    if not klines:
        return None

    df = __build_dataframe(klines)
    return df


def __build_dataframe(klines):
    import pandas as pd

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "num_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ],
    )
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


def get_latest_price(symbol: str) -> float:
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])
