"""
Price checker — runs on a schedule (GitHub Actions every 4 hours).

This script:
1. Loads the list of tracked games
2. Fetches current prices from ITAD (in BRL)
3. Filters for deals with 35%+ discount
4. Sends Telegram notifications for qualifying deals
5. Records which deals we've notified about (to avoid spam)

Run from the repo root:
    python -m bot.price_checker
"""

import sys
from datetime import datetime, timezone

from bot.config import MIN_DISCOUNT_PCT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from bot.itad_api import get_prices
from bot.storage import load_games, save_games
from bot.commands import send_message


def format_deal_message(game_data: dict, deal: dict, history_low: dict = None) -> str:
    """Format a deal notification message for Telegram.

    Args:
        game_data: The tracked game info (title, publisher, etc.)
        deal: The deal dict from ITAD (shop, price, regular, cut, url)
        history_low: Historical low price info (optional)

    Returns an HTML-formatted message string.
    """
    title = game_data.get("title", "Unknown Game")
    shop_name = deal.get("shop", {}).get("name", "Unknown Store")
    current_price = deal.get("price", {}).get("amount", 0)
    regular_price = deal.get("regular", {}).get("amount", 0)
    discount = deal.get("cut", 0)
    deal_url = deal.get("url", "")

    # Build the message
    lines = [
        "🔥 <b>DEAL ALERT!</b>\n",
        f"🎮 <b>{title}</b>",
        f"💰 R$ {current_price:.2f} (was R$ {regular_price:.2f}) — <b>{discount}% OFF</b>",
        f"🏪 {shop_name}",
    ]

    # Add historical low if available
    if history_low:
        low_amount = history_low.get("amount", 0)
        if low_amount > 0:
            if current_price <= low_amount:
                lines.append(f"📉 <b>ALL-TIME LOW!</b> (previous low: R$ {low_amount:.2f})")
            else:
                lines.append(f"📉 Historical low: R$ {low_amount:.2f}")

    # Add the deal link
    if deal_url:
        lines.append(f"\n🔗 <a href=\"{deal_url}\">View Deal</a>")

    return "\n".join(lines)


def check_and_notify() -> None:
    """Main function: check prices for all tracked games and send notifications."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting price check...")

    # Load tracked games (from local file, since we're in GitHub Actions)
    data = load_games(mode="local")
    games = data.get("games", {})

    if not games:
        print("No games being tracked. Nothing to do.")
        return

    print(f"Checking prices for {len(games)} tracked game(s)...")

    # Get prices for all games in one batch (ITAD allows up to 200)
    game_ids = list(games.keys())
    prices_data = get_prices(game_ids)

    if not prices_data:
        print("No price data returned from ITAD.")
        return

    notifications_sent = 0

    for price_entry in prices_data:
        game_id = price_entry.get("id")
        deals = price_entry.get("deals", [])
        history_low = price_entry.get("historyLow", {}).get("all", {})

        if game_id not in games:
            continue

        game_data = games[game_id]
        game_title = game_data.get("title", "Unknown")

        if not deals:
            print(f"  {game_title}: No active deals")
            continue

        for deal in deals:
            discount = deal.get("cut", 0)
            shop_id = deal.get("shop", {}).get("id", 0)
            shop_name = deal.get("shop", {}).get("name", "Unknown")

            # Check discount threshold
            if discount < MIN_DISCOUNT_PCT:
                continue

            # Check if we already notified about this deal today
            notif_key = f"{game_id}_{shop_id}"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            last_notified = data.get("notified_deals", {}).get(notif_key)

            if last_notified == today:
                print(f"  {game_title}: Already notified about {shop_name} deal today")
                continue

            # This is a new qualifying deal — send notification!
            message = format_deal_message(game_data, deal, history_low)
            success = send_message(TELEGRAM_CHAT_ID, message)

            if success:
                print(f"  ✅ Notified: {game_title} — {discount}% off at {shop_name}")
                # Record that we notified about this deal
                data.setdefault("notified_deals", {})[notif_key] = today
                notifications_sent += 1
            else:
                print(f"  ❌ Failed to notify: {game_title} — {shop_name}")

    # Save updated notified_deals back to file
    save_games(data, mode="local")

    print(f"\nDone. Sent {notifications_sent} notification(s).")


if __name__ == "__main__":
    # Allow running directly: python -m bot.price_checker
    try:
        check_and_notify()
    except Exception as e:
        print(f"Error during price check: {e}", file=sys.stderr)
        sys.exit(1)
