"""
Vercel serverless function — Telegram webhook endpoint.

Telegram sends updates (messages, commands) to this endpoint.
We parse them and route to the appropriate command handler.

Deployed at: https://your-project.vercel.app/api
Set this URL as your bot's webhook with Telegram.
"""

import sys
import json
import os

# Add the project root to the Python path so we can import our modules
# When Vercel runs this file, the working directory is the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def handler(request):
    """Vercel Python serverless function handler.

    Args:
        request: A Vercel Request object with method, body, headers, etc.

    Returns:
        A tuple of (status_code, headers, body) or a Response-like object.
    """
    # Handle GET requests (health check)
    if request.method == "GET":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "ok", "bot": "game-deals-bot"}),
        }

    # Handle POST requests (Telegram updates)
    if request.method == "POST":
        try:
            # Verify the request is from Telegram using secret token
            secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
            if secret:
                token_header = request.headers.get("x-telegram-bot-api-secret-token", "")
                if token_header != secret:
                    return {"statusCode": 403, "body": "Forbidden"}

            # Parse the Telegram update
            body = request.body
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            update = json.loads(body)

            # Process the update through our command handler
            from bot.commands import handle_update
            handle_update(update)

            # Always respond 200 to Telegram (they retry otherwise)
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": True}),
            }

        except Exception as e:
            print(f"[Webhook] Error: {e}")
            # Still return 200 to avoid Telegram retries on our bugs
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"ok": True}),
            }

    # Other methods
    return {"statusCode": 405, "body": "Method Not Allowed"}
