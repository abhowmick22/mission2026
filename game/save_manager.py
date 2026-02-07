"""Save/Load game state to JSON files."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from game.world import World

SAVE_DIR = Path(__file__).parent.parent / "saves"


def ensure_save_dir():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def list_saves() -> list[dict]:
    """Return list of save files with metadata."""
    ensure_save_dir()
    saves = []
    for f in sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f) as fp:
                data = json.load(fp)
            saves.append({
                "filename": f.name,
                "path": str(f),
                "player": data.get("player_code", "??"),
                "country": data.get("countries", {}).get(
                    data.get("player_code", ""), {}
                ).get("name", "Unknown"),
                "date": data.get("year", "?"),
                "month": data.get("month", 1),
                "turn": data.get("turn", 0),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return saves


def save_game(world: World, slot: str | None = None) -> str:
    """Save game state. Returns filename."""
    ensure_save_dir()
    if slot is None:
        slot = f"{world.player_code}_{world.year}_{world.month:02d}"
    filename = f"{slot}.json"
    filepath = SAVE_DIR / filename
    with open(filepath, "w") as f:
        json.dump(world.to_dict(), f, indent=2)
    return filename


def auto_save(world: World) -> str:
    """Auto-save to a fixed slot."""
    return save_game(world, slot=f"autosave_{world.player_code}")


def load_game(filename: str) -> World:
    """Load game from file."""
    filepath = SAVE_DIR / filename
    with open(filepath) as f:
        data = json.load(f)
    return World.from_dict(data)
