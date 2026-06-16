"""
IsThereAnyDeal API wrapper.

This module handles all communication with the ITAD API.
We use three main endpoints:
  - /games/search/v1  → Find games by title
  - /games/info/v2    → Get game details (publisher, tags, etc.)
  - /games/prices/v3  → Get current prices and deals

Docs: https://docs.isthereanydeal.com/
"""

import requests
from bot.config import ITAD_API_KEY, ITAD_BASE_URL, ITAD_COUNTRY


def _api_get(endpoint: str, params: dict = None) -> dict | list | None:
    """Helper to make GET requests to the ITAD API.

    Every ITAD request needs the API key as a query parameter.
    Returns the JSON response, or None if the request fails.
    """
    if params is None:
        params = {}
    params["key"] = ITAD_API_KEY

    try:
        resp = requests.get(f"{ITAD_BASE_URL}{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[ITAD API] Error calling {endpoint}: {e}")
        return None


def _api_post(endpoint: str, json_body: list, params: dict = None) -> dict | list | None:
    """Helper to make POST requests to the ITAD API.

    Some endpoints (like /games/prices/v3) use POST because the
    request body is a list of game IDs.
    """
    if params is None:
        params = {}
    params["key"] = ITAD_API_KEY

    try:
        resp = requests.post(
            f"{ITAD_BASE_URL}{endpoint}",
            params=params,
            json=json_body,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[ITAD API] Error calling {endpoint}: {e}")
        return None


# ─── Public Functions ────────────────────────────────────────────────


def search_game(title: str, limit: int = 5) -> list[dict]:
    """Search for games by title.

    Returns a list of search results, each with:
      - id:   ITAD game ID (UUID string)
      - slug: URL-friendly name
      - title: Display name

    Example:
      search_game("God of War") → [{"id": "...", "slug": "god-of-war", "title": "God of War"}, ...]
    """
    data = _api_get("/games/search/v1", {"title": title, "limit": limit})
    # API returns a raw list of games, not an object with a "games" key
    if isinstance(data, list):
        return data
    return []


def get_game_info(game_id: str) -> dict | None:
    """Fetch detailed info about a game.

    Returns a dict with:
      - title, slug, type
      - publishers: [{"id": 123, "name": "Sony"}, ...]
      - developers: [{"id": 456, "name": "Santa Monica Studio"}, ...]
      - tags: ["Action", "Adventure", ...]
      - releaseDate, earlyAccess, reviews, etc.

    This is what we use to check the publisher whitelist.
    """
    return _api_get("/games/info/v2", {"id": game_id})


def get_prices(game_ids: list[str]) -> list[dict]:
    """Fetch current prices and deals for a list of games.

    Args:
        game_ids: List of ITAD game IDs (up to 200 per request).

    Returns a list of price objects, each with:
      - id:         Game ID
      - historyLow: {all: {amount, currency}, y1: {...}, m3: {...}}
      - deals: [{
          shop: {id, name},
          price: {amount, currency},       ← current deal price
          regular: {amount, currency},     ← original full price
          cut: 75,                         ← discount percentage
          url: "https://...",              ← link to the deal
        }, ...]

    We use country=BR to get prices in BRL (R$).
    """
    if not game_ids:
        return []

    data = _api_post("/games/prices/v3", game_ids, {
        "country": ITAD_COUNTRY,
        "deals": "true",      # Only return entries that have a discount
        "vouchers": "true",   # Include voucher-based discounts
    })
    return data if data else []


def check_publisher_allowed(game_info: dict, whitelist: list[str]) -> tuple[bool, str]:
    """Check if a game's publisher is in the whitelist.

    Args:
        game_info: The dict returned by get_game_info().
        whitelist: List of allowed publisher names (lowercase).

    Returns:
        (True, publisher_name) if allowed, (False, reason) if not.
    """
    publishers = game_info.get("publishers", [])
    if not publishers:
        return False, "No publisher info found"

    for pub in publishers:
        pub_name = pub.get("name", "").lower()
        for allowed in whitelist:
            if allowed in pub_name or pub_name in allowed:
                return True, pub["name"]

    pub_names = ", ".join(p["name"] for p in publishers)
    return False, f"Publisher(s) [{pub_names}] not in whitelist"
