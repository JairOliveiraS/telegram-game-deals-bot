"""
Telegram bot command handlers.

When a user sends a message to our bot, Telegram sends an "update" to our
webhook. This module processes those updates and generates responses.

Commands:
  /start <game name>  — Search for a game and add it to the tracking list
  /delete <game name> — Remove a game from the tracking list
  /list               — Show all currently tracked games
  /help               — Show available commands
"""

import requests
from bot.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    PUBLISHER_WHITELIST,
    MIN_ORIGINAL_PRICE,
)
from bot.itad_api import search_game, get_game_info, check_publisher_allowed, get_prices
from bot.storage import (
    load_games,
    add_game,
    remove_game,
    find_game_by_title,
)


def send_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to a Telegram chat.

    Args:
        chat_id: The Telegram chat ID (a number like "123456789").
        text: Message text (supports HTML formatting).
        parse_mode: "HTML" or "Markdown" for formatting.

    Returns True if the message was sent successfully.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[Telegram] Error sending message: {e}")
        return False


# ─── Command Handlers ────────────────────────────────────────────────


def handle_help(chat_id: str) -> None:
    """Handle /help command."""
    text = (
        "🎮 <b>Game Deals Bot — Commands</b>\n\n"
        "/start &lt;game name&gt;\n"
        "  Search and track a game for deals\n\n"
        "/delete &lt;game name&gt;\n"
        "  Stop tracking a game\n\n"
        "/list\n"
        "  Show all tracked games\n\n"
        "/help\n"
        "  Show this message\n\n"
        "🔔 You'll receive notifications when tracked games have "
        "a deal with 35%+ discount."
    )
    send_message(chat_id, text)


def handle_start(chat_id: str, game_query: str) -> None:
    """Handle /start <game name> command.

    Flow:
    1. Search ITAD for the game title
    2. Show the top results so the user can pick
    3. Check publisher against whitelist
    4. Check original price >= R$150
    5. Add to tracking list (or offer manual override)
    """
    if not game_query.strip():
        send_message(chat_id, "Usage: /start &lt;game name&gt;\nExample: /start God of War")
        return

    # Step 1: Search for the game
    results = search_game(game_query, limit=5)
    if not results:
        send_message(chat_id, f"❌ No games found for \"{game_query}\". Try a different search.")
        return

    # Step 2: If multiple results, pick the first one (best match)
    # In a more advanced version, we could show buttons for the user to pick
    game = results[0]
    game_id = game["id"]
    game_title = game["title"]

    # Check if already tracked
    existing = find_game_by_title(game_title, mode="github")
    if existing:
        send_message(chat_id, f"ℹ️ <b>{game_title}</b> is already being tracked!")
        return

    # Step 3: Get game details (publisher, price info)
    info = get_game_info(game_id)
    if not info:
        send_message(chat_id, f"❌ Couldn't get details for \"{game_title}\". Try again later.")
        return

    # Step 4: Check publisher
    allowed, pub_name = check_publisher_allowed(info, PUBLISHER_WHITELIST)

    # Step 5: Get original price from ITAD
    prices = get_prices([game_id])
    original_price = 0.0
    if prices and prices[0].get("deals"):
        # Get the regular (full) price from the first deal
        first_deal = prices[0]["deals"][0]
        original_price = first_deal.get("regular", {}).get("amount", 0)

    # Step 6: Apply filters
    manual = False

    if not allowed:
        # Publisher not in whitelist — offer manual override
        text = (
            f"⚠️ <b>{game_title}</b>\n"
            f"Publisher: {pub_name}\n\n"
            f"This publisher is not in our whitelist.\n"
            f"Use /force_add {game_id} to add it manually."
        )
        send_message(chat_id, text)
        return

    if original_price < MIN_ORIGINAL_PRICE and original_price > 0:
        # Price too low — this is likely a smaller/indie title
        text = (
            f"⚠️ <b>{game_title}</b>\n"
            f"Original price: R$ {original_price:.2f}\n\n"
            f"This game's base price is below R$ {MIN_ORIGINAL_PRICE:.2f}, "
            f"so it looks like a smaller title.\n"
            f"Use /force_add {game_id} to add it manually anyway."
        )
        send_message(chat_id, text)
        return

    # Step 7: Add to tracking list
    success = add_game(
        game_id=game_id,
        title=game_title,
        slug=game.get("slug", ""),
        publisher=pub_name if isinstance(pub_name, str) else "Unknown",
        original_price=original_price,
        mode="github",
        manual=manual,
    )

    if success:
        price_str = f"R$ {original_price:.2f}" if original_price > 0 else "Unknown"
        text = (
            f"✅ Now tracking <b>{game_title}</b>\n"
            f"Publisher: {pub_name}\n"
            f"Original price: {price_str}\n\n"
            f"You'll be notified when it has a deal with 35%+ discount."
        )
        send_message(chat_id, text)
    else:
        send_message(chat_id, f"❌ Failed to save \"{game_title}\". Try again later.")


def handle_force_add(chat_id: str, game_id: str) -> None:
    """Handle /force_add <game_id> — manually add a game bypassing filters."""
    if not game_id.strip():
        send_message(chat_id, "Usage: /force_add &lt;game_id&gt;")
        return

    info = get_game_info(game_id.strip())
    if not info:
        send_message(chat_id, "❌ Game not found.")
        return

    game_title = info.get("title", "Unknown")
    publishers = info.get("publishers", [])
    pub_name = publishers[0]["name"] if publishers else "Unknown"

    # Get original price
    prices = get_prices([game_id.strip()])
    original_price = 0.0
    if prices and prices[0].get("deals"):
        original_price = prices[0]["deals"][0].get("regular", {}).get("amount", 0)

    success = add_game(
        game_id=game_id.strip(),
        title=game_title,
        slug=info.get("slug", ""),
        publisher=pub_name,
        original_price=original_price,
        mode="github",
        manual=True,  # Bypasses filters in future checks
    )

    if success:
        send_message(chat_id, f"✅ Manually added <b>{game_title}</b> to tracking list.")
    else:
        send_message(chat_id, f"ℹ️ <b>{game_title}</b> is already being tracked.")


def handle_delete(chat_id: str, game_query: str) -> None:
    """Handle /delete <game name> command.

    Finds the game by partial title match and removes it.
    """
    if not game_query.strip():
        send_message(chat_id, "Usage: /delete &lt;game name&gt;\nExample: /delete God of War")
        return

    result = find_game_by_title(game_query, mode="github")
    if not result:
        send_message(chat_id, f"❌ No tracked game matching \"{game_query}\". Use /list to see tracked games.")
        return

    game_id, game_data = result
    success = remove_game(game_id, mode="github")

    if success:
        send_message(chat_id, f"🗑️ Stopped tracking <b>{game_data['title']}</b>.")
    else:
        send_message(chat_id, "❌ Failed to remove game. Try again later.")


def handle_list(chat_id: str) -> None:
    """Handle /list command — show all tracked games."""
    data = load_games(mode="github")
    games = data.get("games", {})

    if not games:
        send_message(chat_id, "📋 No games are being tracked yet.\n\nUse /start &lt;game name&gt; to add one!")
        return

    lines = ["📋 <b>Tracked Games:</b>\n"]
    for i, (gid, gdata) in enumerate(games.items(), 1):
        price_str = f"R$ {gdata['original_price']:.2f}" if gdata.get("original_price") else "N/A"
        manual_tag = " 🔧" if gdata.get("manual") else ""
        lines.append(
            f"{i}. <b>{gdata['title']}</b>{manual_tag}\n"
            f"   Publisher: {gdata.get('publisher', 'N/A')} | Base: {price_str}"
        )

    lines.append(f"\n🔧 = manually added (bypasses filters)")
    lines.append(f"\nTotal: {len(games)} game(s)")

    send_message(chat_id, "\n".join(lines))


# ─── Update Router ───────────────────────────────────────────────────


def handle_update(update: dict) -> None:
    """Process a single Telegram update.

    Telegram sends updates in this format:
    {
        "update_id": 123,
        "message": {
            "message_id": 456,
            "from": {"id": 789, "first_name": "User"},
            "chat": {"id": 789, "type": "private"},
            "text": "/start God of War"
        }
    }

    We extract the command and arguments, then route to the right handler.
    """
    message = update.get("message")
    if not message:
        return  # Not a text message (could be a sticker, photo, etc.)

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()

    if not text or not chat_id:
        return

    # Parse command and arguments
    # e.g., "/start God of War" → command="/start", args="God of War"
    if text.startswith("/"):
        parts = text.split(" ", 1)
        command = parts[0].lower().split("@")[0]  # Remove @botname if present
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "/start":
            handle_start(chat_id, args)
        elif command == "/force_add":
            handle_force_add(chat_id, args)
        elif command == "/delete":
            handle_delete(chat_id, args)
        elif command == "/list":
            handle_list(chat_id)
        elif command == "/help":
            handle_help(chat_id)
        else:
            send_message(chat_id, f"Unknown command: {command}\nType /help for available commands.")
