"""Simple file-based user authentication.

Stores users as JSON files in a users/ directory. Passwords are hashed
with bcrypt-like security using hashlib (no extra dependencies).
"""

from __future__ import annotations
import hashlib
import json
import os
import secrets
from pathlib import Path

USERS_DIR = Path(__file__).parent.parent / "users"


def _ensure_dir():
    USERS_DIR.mkdir(parents=True, exist_ok=True)


def _user_path(username: str) -> Path:
    # Sanitize username for filesystem
    safe = "".join(c for c in username.lower() if c.isalnum() or c in "-_")
    return USERS_DIR / f"{safe}.json"


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash password with salt. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex(), salt


def create_user(username: str, password: str) -> tuple[bool, str]:
    """Create a new user. Returns (success, message)."""
    _ensure_dir()
    username = username.strip()
    if not username or len(username) < 2:
        return False, "Username must be at least 2 characters."
    if len(username) > 20:
        return False, "Username must be 20 characters or less."
    if not all(c.isalnum() or c in "-_" for c in username):
        return False, "Username can only contain letters, numbers, hyphens, underscores."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."

    path = _user_path(username)
    if path.exists():
        return False, "Username already taken."

    pw_hash, salt = _hash_password(password)
    data = {
        "username": username,
        "pw_hash": pw_hash,
        "salt": salt,
        "game_ids": [],  # list of session game IDs belonging to this user
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return True, "Account created."


def verify_user(username: str, password: str) -> tuple[bool, str]:
    """Verify login credentials. Returns (success, message)."""
    _ensure_dir()
    path = _user_path(username.strip())
    if not path.exists():
        return False, "User not found."

    with open(path) as f:
        data = json.load(f)

    pw_hash, _ = _hash_password(password, data["salt"])
    if pw_hash != data["pw_hash"]:
        return False, "Wrong password."
    return True, "OK"


def get_user_data(username: str) -> dict | None:
    """Get user data."""
    _ensure_dir()
    path = _user_path(username.strip())
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_user_data(username: str, data: dict):
    """Update user data."""
    _ensure_dir()
    path = _user_path(username.strip())
    with open(path, "w") as f:
        json.dump(data, f)


def add_game_to_user(username: str, game_id: str):
    """Associate a game session with a user."""
    data = get_user_data(username)
    if data is None:
        return
    if game_id not in data["game_ids"]:
        data["game_ids"].append(game_id)
        # Keep last 10 games
        data["game_ids"] = data["game_ids"][-10:]
        save_user_data(username, data)


def get_user_games(username: str) -> list[str]:
    """Get list of game IDs for a user."""
    data = get_user_data(username)
    if data is None:
        return []
    return data.get("game_ids", [])
