import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    MODE = "SIGNALS_ONLY"
    TRADE_MODE: str = os.getenv("TRADE_MODE", "SIGNALS_ONLY")
    MAX_SIGNALS_PER_DAY: int = 3

    # ── Auto-trade layer (isolated, disabled by default) ─────────────────────
    LIVE_TRADING_ENABLED: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    MAX_POSITION_USDT: float   = float(os.getenv("MAX_POSITION_USDT", "8"))    # first live test: 8 USDT
    MAX_TRADES_PER_DAY: int    = int(os.getenv("MAX_TRADES_PER_DAY", "3"))     # max 3 auto-trades/day
    MAX_DAILY_LOSS_USDT: float = float(os.getenv("MAX_DAILY_LOSS_USDT", "2"))  # hard stop at $2 loss
    KILL_SWITCH: bool          = os.getenv("KILL_SWITCH", "false").lower() == "true"
    # ─────────────────────────────────────────────────────────────────────────

    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    SCANNER_SYMBOLS = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT", "XRPUSDT",
        "BNBUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT",
        "DOTUSDT", "LTCUSDT", "NEARUSDT", "INJUSDT", "APTUSDT",
    ]
    TIMEFRAME = "1h"
    LIMIT = 200

    DATA_DIR = "data"
    LOGS_DIR = "logs"
    TRADES_CSV = os.path.join(DATA_DIR, "trades_log.csv")
    SIGNALS_CSV = os.path.join(DATA_DIR, "signals_log.csv")
    SCANNER_LOG_CSV = os.path.join(DATA_DIR, "scanner_log.csv")
    DAILY_STATS_JSON = os.path.join(DATA_DIR, "daily_stats.json")
    LOG_FILE = os.path.join(LOGS_DIR, "bot.log")


SETTINGS = Settings()
