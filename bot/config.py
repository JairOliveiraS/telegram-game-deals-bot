import os

# ─── API Keys (loaded from environment variables) ────────────────────
ITAD_API_KEY = os.environ.get("ITAD_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─── GitHub Settings (for committing tracked_games.json changes) ─────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # e.g. "yourusername/telegram-game-deals-bot"

# ─── ITAD API ────────────────────────────────────────────────────────
ITAD_BASE_URL = "https://api.isthereanydeal.com"
ITAD_COUNTRY = "BR"

# ─── Deal Filters ────────────────────────────────────────────────────
MIN_ORIGINAL_PRICE = 150.0   # R$150 — games cheaper than this are skipped on auto-add
MIN_DISCOUNT_PCT = 35        # Only notify if discount is >= 35%

# ─── Publisher Whitelist ─────────────────────────────────────────────
# Only games from these publishers are auto-added via /start.
# Case-insensitive matching is used.
PUBLISHER_WHITELIST = [
    "ubisoft",
    "ea games",
    "electronic arts",
    "konami",
    "sony",
    "playstation mobile",
    "xbox game studios",
    "xbox games studios",
    "microsoft studios",
    "capcom",
    "square enix",
    "remedy entertainment",
    "frozen district",
    "505 games",
    "playway",
    "playway sa",
    "warner bros",
    "warner bros. games",
    "warner bros. interactive entertainment",
    "bloober team sa",
    "bloober team s.a.",
    "bloober team",
    "bloober team s.a",
    "techland",
    "bandai namco entertainment",
    "bandai namco us",
    "cyberconnect2",
    "bandai namco entertainment inc.",
    "bandai namco entertainment us",

]

# ─── Paths ───────────────────────────────────────────────────────────
TRACKED_GAMES_FILE = "tracked_games.json"
