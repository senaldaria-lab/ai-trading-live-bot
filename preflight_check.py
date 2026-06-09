"""
preflight_check.py — AI_TRADING_AGENT project readiness check.

Safe to run at any time.  Does NOT:
  - import any project module
  - connect to Binance
  - send Telegram messages
  - execute any orders
  - modify any files
  - print .env values

Usage:
    python preflight_check.py
"""

import os
import re
import sys

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REQUIRED_FILES = [
    "main.py",
    ".env",
    ".env.example",
    "config/settings.py",
    "services/binance_service.py",
    "services/telegram_service.py",
    "agents/market_watcher.py",
    "agents/technical_analysis.py",
    "agents/news_agent.py",
    "agents/risk_manager.py",
    "agents/signal_decision.py",
]

REQUIRED_FOLDERS = [
    "agents",
    "services",
    "config",
    "data",
    "logs",
    "skills",
    "backup_original",
]

# Exact variable names the task spec requires; the code currently reads
# TELEGRAM_TOKEN — that mismatch is reported explicitly in section 3.
REQUIRED_ENV_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "TRADE_MODE",
]

# Variable names the code actually reads (may differ from spec above)
CODE_ENV_VARS = {
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "TRADE_MODE",
}

# Python files to scan for forbidden keywords (backup_original excluded)
SCAN_FILES = [
    "main.py",
    "config/settings.py",
    "services/binance_service.py",
    "services/telegram_service.py",
    "agents/market_watcher.py",
    "agents/technical_analysis.py",
    "agents/news_agent.py",
    "agents/risk_manager.py",
    "agents/signal_decision.py",
]

# Keywords that must never appear as real API calls
FORBIDDEN_KEYWORDS = [
    "create_order",
    "order_market_buy",
    "order_market_sell",
    "futures_create_order",
    "margin",
    "leverage",
]

# For broad English words, require a trading-API pattern to avoid false positives
# on legitimate comments like "# no margin allowed"
_STRICT_PATTERN_KEYWORDS = {
    "margin": re.compile(
        r"(?:client\.|\.)(margin)|"
        r"margin_(?:buy|sell|order|trade)|"
        r"create_margin_order|"
        r"order_margin",
        re.IGNORECASE,
    ),
    "leverage": re.compile(
        r"(?:client\.|\.)(leverage)|"
        r"leverage\s*=\s*[1-9]|"
        r"set_leverage|"
        r"change_leverage",
        re.IGNORECASE,
    ),
}

# ── Display helpers ───────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_USE_COLOR = sys.stdout.isatty()


def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}" if _USE_COLOR else text


def _ok(msg: str) -> None:
    print(f"  {_c(GREEN, '[OK]')}      {msg}")


def _fail(msg: str) -> None:
    print(f"  {_c(RED, '[MISSING]')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_c(YELLOW, '[WARN]')}    {msg}")


def _err(msg: str) -> None:
    print(f"  {_c(RED, '[ERROR]')}   {msg}")


def _info(msg: str) -> None:
    print(f"  {_c(CYAN, '[INFO]')}    {msg}")


def _section(title: str) -> None:
    print(f"\n{'─' * 62}")
    print(f"  {_c(BOLD, title)}")
    print(f"{'─' * 62}")


# ── Check 1: required files ───────────────────────────────────────────────────

def check_files() -> list[str]:
    _section("1. REQUIRED FILES")
    failures: list[str] = []
    for rel in REQUIRED_FILES:
        path = os.path.join(BASE_DIR, rel)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            _ok(f"{rel}  ({size:,} bytes)")
        else:
            _fail(f"{rel}")
            failures.append(rel)
    return failures


# ── Check 2: required folders ─────────────────────────────────────────────────

def check_folders() -> list[str]:
    _section("2. REQUIRED FOLDERS")
    failures: list[str] = []
    for rel in REQUIRED_FOLDERS:
        path = os.path.join(BASE_DIR, rel)
        if os.path.isdir(path):
            _ok(f"{rel}/")
        else:
            _fail(f"{rel}/")
            failures.append(rel)
    return failures


# ── .env parser (values never printed) ───────────────────────────────────────

def _parse_env(env_path: str) -> dict[str, str]:
    """Return {KEY: raw_value} from a .env file without loading into os.environ."""
    result: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    result[key] = value
    return result


# ── Check 3: env variable names ───────────────────────────────────────────────

def check_env_vars() -> tuple[list[str], str | None]:
    """Return (missing_spec_vars, trade_mode_value_or_None)."""
    _section("3. ENVIRONMENT VARIABLES (.env)")

    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        _fail(".env file not found — cannot verify variables")
        return REQUIRED_ENV_VARS.copy(), None

    env = _parse_env(env_path)
    missing: list[str] = []
    trade_mode: str | None = None

    for var in REQUIRED_ENV_VARS:
        if var in env:
            has_value = bool(env[var])
            note = "(set)" if has_value else "(name present but value is empty)"
            if has_value:
                _ok(f"{var}  {note}")
            else:
                _warn(f"{var}  {note}")
            if var == "TRADE_MODE":
                trade_mode = env[var]
        else:
            _fail(f"{var}  ← NOT FOUND in .env")
            missing.append(var)

    # Detect the TELEGRAM_TOKEN vs TELEGRAM_BOT_TOKEN naming mismatch
    if "TELEGRAM_BOT_TOKEN" in missing and "TELEGRAM_TOKEN" in env:
        _warn(
            "TELEGRAM_TOKEN is present in .env but the spec requires TELEGRAM_BOT_TOKEN. "
            "The current code reads TELEGRAM_TOKEN — consider aligning the names."
        )
        missing.remove("TELEGRAM_BOT_TOKEN")   # advisory, not a blocker

    # Report variables used by the code but absent from .env
    code_missing = [v for v in CODE_ENV_VARS if v not in env]
    if code_missing:
        for v in code_missing:
            _warn(f"{v}  ← used by the code but not found in .env")

    return missing, trade_mode


# ── Check 4: TRADE_MODE value ─────────────────────────────────────────────────

def check_trade_mode(trade_mode: str | None) -> bool:
    _section("4. TRADE_MODE SAFETY CHECK")
    if trade_mode is None:
        _fail("TRADE_MODE not found in .env — safety gate in main.py will block the bot")
        return False
    if trade_mode == "SIGNALS_ONLY":
        _ok(f"TRADE_MODE={trade_mode!r}  — safe mode confirmed")
        return True
    _err(f"TRADE_MODE={trade_mode!r}  — must be exactly 'SIGNALS_ONLY'")
    _err("The safety gate in main.py will call sys.exit(1) before the bot does anything.")
    return False


# ── Check 5: forbidden keyword scan ──────────────────────────────────────────

def _keyword_is_real_call(line: str, keyword: str) -> bool:
    """Return True if the keyword looks like an actual API call, not a guard/comment."""
    # Broad-pattern keywords use their own stricter regex
    if keyword in _STRICT_PATTERN_KEYWORDS:
        return bool(_STRICT_PATTERN_KEYWORDS[keyword].search(line))

    # For the others: flag if the keyword is preceded by '.' (method call)
    # or immediately followed by '(' (direct function call)
    # and NOT wrapped in quotes on this line
    idx = line.find(keyword)
    if idx == -1:
        return False

    before = line[:idx]
    after  = line[idx + len(keyword):]

    # Preceded by dot → real method call
    if before.rstrip().endswith("."):
        return True

    # Keyword is inside a string literal → part of a guard / safety list
    single_quoted = re.search(r"'" + re.escape(keyword) + r"'", line)
    double_quoted = re.search(r'"'  + re.escape(keyword) + r'"', line)
    if single_quoted or double_quoted:
        return False

    # Followed by ( without being in a string → direct call
    if after.lstrip().startswith("("):
        return True

    return False


def check_forbidden_keywords() -> list[tuple[str, int, str, str]]:
    """Return list of (file, line_no, keyword, line) for real violations."""
    _section("5. FORBIDDEN KEYWORD SCAN")
    real_violations: list[tuple[str, int, str, str]] = []
    advisory_hits:   list[tuple[str, int, str, str]] = []

    for rel in SCAN_FILES:
        path = os.path.join(BASE_DIR, rel)
        if not os.path.isfile(path):
            _warn(f"{rel}  — file not found, skipped")
            continue

        file_real: list[tuple[int, str, str]] = []
        file_advisory: list[tuple[int, str, str]] = []

        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            # Skip blank lines and full-line comments
            if not stripped or stripped.startswith("#"):
                continue
            for kw in FORBIDDEN_KEYWORDS:
                if kw not in raw:
                    continue
                if _keyword_is_real_call(raw, kw):
                    file_real.append((lineno, kw, raw.rstrip()))
                    real_violations.append((rel, lineno, kw, raw.rstrip()))
                else:
                    file_advisory.append((lineno, kw, raw.rstrip()))
                    advisory_hits.append((rel, lineno, kw, raw.rstrip()))

        if not file_real and not file_advisory:
            _ok(rel)
        else:
            for lineno, kw, content in file_real:
                _err(
                    f"{rel}:{lineno}  keyword={kw!r}"
                    f"\n           → {content.strip()}"
                )
            for lineno, kw, content in file_advisory:
                _warn(
                    f"{rel}:{lineno}  keyword={kw!r} in guard/string (advisory)"
                    f"\n           → {content.strip()}"
                )

    if advisory_hits:
        print()
        _info(
            "Advisory items are keywords found inside string literals or safety guards,"
        )
        _info(
            "not real API calls.  They are expected in guard code (e.g. binance_service.py)."
        )

    return real_violations


# ── Final report ──────────────────────────────────────────────────────────────

def _final_banner(ready: bool, issues: list[str]) -> None:
    print(f"\n{'═' * 62}")
    if ready:
        status = _c(GREEN + BOLD, "✓  READY")
        print(f"  FINAL STATUS:  {status}")
        print(f"  All preflight checks passed.")
        print(f"  Run with:  python main.py")
    else:
        status = _c(RED + BOLD, "✗  NOT READY")
        print(f"  FINAL STATUS:  {status}")
        print(f"  {len(issues)} issue(s) must be resolved before running:")
        for issue in issues:
            print(f"    • {issue}")
    print(f"{'═' * 62}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print(_c(BOLD, "╔══════════════════════════════════════════════════════════╗"))
    print(_c(BOLD, "║        AI_TRADING_AGENT — PREFLIGHT CHECK                ║"))
    print(_c(BOLD, "║        Mode: SIGNALS_ONLY safety verification            ║"))
    print(_c(BOLD, "╚══════════════════════════════════════════════════════════╝"))
    print(f"  Base directory: {BASE_DIR}")

    issues: list[str] = []

    # 1. Files
    missing_files = check_files()
    for f in missing_files:
        issues.append(f"Missing file: {f}")

    # 2. Folders
    missing_folders = check_folders()
    for d in missing_folders:
        issues.append(f"Missing folder: {d}/")

    # 3. Env vars
    missing_vars, trade_mode = check_env_vars()
    for v in missing_vars:
        issues.append(f"Missing .env variable: {v}")

    # 4. TRADE_MODE
    trade_mode_ok = check_trade_mode(trade_mode)
    if not trade_mode_ok:
        issues.append("TRADE_MODE is not set to SIGNALS_ONLY")

    # 5. Forbidden keywords
    violations = check_forbidden_keywords()
    for rel, lineno, kw, _ in violations:
        issues.append(f"Forbidden call in {rel}:{lineno} — keyword={kw!r}")

    # Final verdict
    _final_banner(ready=len(issues) == 0, issues=issues)


if __name__ == "__main__":
    main()
