"""
Storage layer for tracked games.

The tracked games list lives in tracked_games.json at the repo root.
Two contexts need to access it:

1. GitHub Actions (price checker) — reads the file directly from disk
   after the repo is checked out.

2. Vercel webhook (bot commands) — can't write to disk, so it uses
   the GitHub API to read and commit changes to the file.

This module handles both modes transparently.
"""

import json
import base64
import requests
from datetime import datetime, timezone

from bot.config import TRACKED_GAMES_FILE, GITHUB_TOKEN, GITHUB_REPO


# ─── GitHub API helpers ──────────────────────────────────────────────


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _fetch_file_from_github() -> tuple[dict | None, str | None]:
    """Fetch tracked_games.json from the GitHub repo.

    Returns:
        (data, sha) — the parsed JSON and the file's SHA (needed for commits).
        (None, None) if the file doesn't exist yet.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TRACKED_GAMES_FILE}"
    try:
        resp = requests.get(url, headers=_github_headers(), timeout=15)
        if resp.status_code == 404:
            return None, None
        resp.raise_for_status()
        file_data = resp.json()
        content = base64.b64decode(file_data["content"]).decode("utf-8")
        return json.loads(content), file_data["sha"]
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"[Storage] Error fetching from GitHub: {e}")
        return None, None


def _commit_to_github(data: dict, sha: str | None, message: str) -> bool:
    """Commit updated tracked_games.json to the GitHub repo.

    Args:
        data: The new content to write.
        sha: The current file's SHA (None if creating for the first time).
        message: Commit message.

    Returns True on success, False on failure.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{TRACKED_GAMES_FILE}"
    content_b64 = base64.b64encode(
        json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")

    body = {
        "message": message,
        "content": content_b64,
    }
    if sha:
        body["sha"] = sha  # Required for updating an existing file

    try:
        resp = requests.put(url, headers=_github_headers(), json=body, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[Storage] Error committing to GitHub: {e}")
        return False


# ─── Local file helpers (used by GitHub Actions) ─────────────────────


def load_local() -> dict:
    """Load tracked_games.json from the local filesystem.

    Used by the GitHub Actions price checker, which has the repo checked out.
    """
    try:
        with open(TRACKED_GAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"games": {}, "notified_deals": {}}


def save_local(data: dict) -> None:
    """Save tracked_games.json to the local filesystem."""
    with open(TRACKED_GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── High-level operations ───────────────────────────────────────────


def empty_state() -> dict:
    """Return an empty tracked games state."""
    return {"games": {}, "notified_deals": {}}


def load_games(mode: str = "local") -> dict:
    """Load the tracked games state.

    Args:
        mode: "local" reads from disk, "github" reads via GitHub API.

    Returns dict with:
        - games: {game_id: {title, slug, publisher, added_at, original_price, manual}}
        - notified_deals: {game_id_shop_id: "2024-01-15"} — tracks which deals
                          we've already notified about (to avoid duplicates)
    """
    if mode == "github":
        data, _ = _fetch_file_from_github()
        if data is None:
            return empty_state()
        # Ensure required keys exist
        data.setdefault("games", {})
        data.setdefault("notified_deals", {})
        return data
    return load_local()


def save_games(data: dict, mode: str = "local", commit_message: str = "Update tracked games") -> bool:
    """Save the tracked games state.

    Args:
        data: The state dict to save.
        mode: "local" writes to disk, "github" commits via GitHub API.
        commit_message: Git commit message (only used in github mode).

    Returns True on success, False on failure.
    """
    if mode == "github":
        _, sha = _fetch_file_from_github()
        return _commit_to_github(data, sha, commit_message)
    save_local(data)
    return True


def add_game(game_id: str, title: str, slug: str, publisher: str,
             original_price: float, mode: str = "local", manual: bool = False) -> bool:
    """Add a game to the tracking list.

    Args:
        game_id: ITAD game UUID.
        title: Display name.
        slug: URL-friendly name.
        publisher: Publisher name.
        original_price: Full price in BRL.
        mode: "local" or "github".
        manual: True if user manually added (bypasses price filter).

    Returns True if added successfully.
    """
    data = load_games(mode)

    # Don't add duplicates
    if game_id in data["games"]:
        return False

    data["games"][game_id] = {
        "title": title,
        "slug": slug,
        "publisher": publisher,
        "original_price": original_price,
        "manual": manual,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }

    return save_games(data, mode, f"Add game: {title}")


def remove_game(game_id: str, mode: str = "local") -> bool:
    """Remove a game from the tracking list.

    Returns True if removed, False if not found.
    """
    data = load_games(mode)

    if game_id not in data["games"]:
        return False

    title = data["games"][game_id]["title"]
    del data["games"][game_id]

    # Also clean up any notified deals for this game
    keys_to_remove = [k for k in data["notified_deals"] if k.startswith(game_id)]
    for key in keys_to_remove:
        del data["notified_deals"][key]

    return save_games(data, mode, f"Remove game: {title}")


def find_game_by_title(title: str, mode: str = "local") -> tuple[str, dict] | None:
    """Find a tracked game by its title (case-insensitive partial match).

    Returns (game_id, game_data) or None if not found.
    """
    data = load_games(mode)
    title_lower = title.lower()

    for gid, gdata in data["games"].items():
        if title_lower in gdata["title"].lower() or gdata["title"].lower() in title_lower:
            return gid, gdata

    return None


def was_notified(game_id: str, shop_id: int, mode: str = "local") -> bool:
    """Check if we already sent a notification for this game+shop combo today."""
    data = load_games(mode)
    key = f"{game_id}_{shop_id}"
    last_notified = data.get("notified_deals", {}).get(key)
    if not last_notified:
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return last_notified == today


def mark_notified(game_id: str, shop_id: int, mode: str = "local") -> None:
    """Record that we sent a notification for this game+shop today."""
    data = load_games(mode)
    key = f"{game_id}_{shop_id}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data.setdefault("notified_deals", {})[key] = today
    save_games(data, mode, f"Mark notified: {game_id} shop {shop_id}")
