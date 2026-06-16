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
from http.server import BaseHTTPRequestHandler

# Add the project root to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class handler(BaseHTTPRequestHandler):
    """Vercel Python handler class.

    Vercel looks for a class named 'handler' with do_POST / do_GET methods.
    """

    def do_POST(self):
        """Handle incoming POST requests from Telegram."""
        try:
            # Read the request body
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            update = json.loads(body_bytes.decode("utf-8"))

            # Optional: Verify the request is from Telegram using secret token
            secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
            if secret:
                token_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if token_header != secret:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"Forbidden")
                    return

            # Process the update
            from bot.commands import handle_update
            handle_update(update)

            # Always respond 200 to Telegram (they retry otherwise)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        except Exception as e:
            print(f"[Webhook] Error: {e}")
            # Still return 200 to avoid Telegram retries on our bugs
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

    def do_GET(self):
        """Handle GET requests — useful for checking if the webhook is alive."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "bot": "game-deals-bot"}')
