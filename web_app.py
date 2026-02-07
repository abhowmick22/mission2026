"""Flask web app for World Order game.

Game state persists to disk via the save system, so games survive
server restarts and redeployments. Each browser session gets a
persistent game ID stored in a cookie, mapped to a save file.
"""

from __future__ import annotations
import json
import os
from pathlib import Path

from flask import Flask, render_template, jsonify, request, session

from game.world import World
from game.events import EventEngine
from game.ai import AIPlayer
from game.actions import execute_action, ACTION_CATEGORIES, TECH_FIELDS
from game.save_manager import save_game, load_game, list_saves, SAVE_DIR, ensure_save_dir

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "worldorder-dev-key-change-in-prod")


# ── Session-persistent game management ─────────────────────────────────────

def _session_save_path() -> Path | None:
    """Get the save file path for the current session."""
    sid = session.get("game_id")
    if not sid:
        return None
    ensure_save_dir()
    return SAVE_DIR / f"session_{sid}.json"


def _save_session_state(game: dict):
    """Persist full game state (world + action points + log) to disk."""
    path = _session_save_path()
    if not path:
        return
    data = game["world"].to_dict()
    data["_session"] = {
        "action_points": game["action_points"],
        "turn_phase": game["turn_phase"],
        "turn_log": game["turn_log"],
    }
    with open(path, "w") as f:
        json.dump(data, f)


def _load_session_state() -> dict | None:
    """Load game state from disk for the current session."""
    path = _session_save_path()
    if not path or not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    session_meta = data.pop("_session", {})
    world = World.from_dict(data)
    ai_players = {
        code: AIPlayer(country)
        for code, country in world.countries.items()
        if code != world.player_code
    }
    return {
        "world": world,
        "ai_players": ai_players,
        "event_engine": EventEngine(),
        "action_points": session_meta.get("action_points", 4),
        "turn_phase": session_meta.get("turn_phase", "actions"),
        "turn_events": [],
        "turn_ai_actions": {},
        "turn_log": session_meta.get("turn_log", []),
    }


def _get_game() -> dict | None:
    return _load_session_state()


def _create_game(player_code: str) -> dict:
    world = World()
    world.load_countries()
    world.player_code = player_code
    ai_players = {
        code: AIPlayer(country)
        for code, country in world.countries.items()
        if code != player_code
    }
    game = {
        "world": world,
        "ai_players": ai_players,
        "event_engine": EventEngine(),
        "action_points": 4,
        "turn_phase": "actions",
        "turn_events": [],
        "turn_ai_actions": {},
        "turn_log": [],
    }
    sid = os.urandom(8).hex()
    session["game_id"] = sid
    _save_session_state(game)
    return game


def _world_state(game: dict) -> dict:
    """Serialize world state for the frontend."""
    world = game["world"]
    player = world.get_player()
    rankings = world.get_rankings()
    player_rank = next(i for i, (c, _) in enumerate(rankings, 1) if c == world.player_code)

    countries = {}
    for code, c in world.countries.items():
        countries[code] = {
            "name": c.name,
            "code": c.code,
            "region": c.region,
            "leader": {"name": c.leader.name, "title": c.leader.title,
                       "traits": c.leader.traits, "approval": round(c.leader.approval, 1)},
            "government": c.government,
            "population": round(c.population, 1),
            "economy": {
                "gdp": round(c.economy.gdp, 2),
                "gdp_growth": round(c.economy.gdp_growth, 1),
                "debt_ratio": round(c.economy.debt_ratio, 1),
                "trade_balance": round(c.economy.trade_balance, 2),
                "unemployment": round(c.economy.unemployment, 1),
                "inflation": round(c.economy.inflation, 1),
            },
            "military": {
                "power": round(c.military.power, 1),
                "nuclear": c.military.nuclear,
                "cyber_capability": round(c.military.cyber_capability, 1),
                "deployed_regions": c.military.deployed_regions,
            },
            "tech": {
                "level": round(c.tech.level, 1),
                "ai_research": round(c.tech.ai_research, 1),
                "space": round(c.tech.space, 1),
                "clean_energy": round(c.tech.clean_energy, 1),
                "biotech": round(c.tech.biotech, 1),
                "semiconductors": round(c.tech.semiconductors, 1),
            },
            "resources": {
                "oil": round(c.resources.oil, 1),
                "natural_gas": round(c.resources.natural_gas, 1),
                "minerals": round(c.resources.minerals, 1),
                "food": round(c.resources.food, 1),
                "manufacturing": round(c.resources.manufacturing, 1),
            },
            "stability": round(c.stability, 1),
            "influence": round(c.influence, 1),
            "relationships": {k: round(v, 1) for k, v in c.relationships.items()},
            "alliances": c.alliances,
            "sanctions_on": c.sanctions_on,
            "sanctioned_by": c.sanctioned_by,
            "traits": c.traits,
            "power_index": round(c.power_index(), 1),
            "is_player": code == world.player_code,
        }

    return {
        "player_code": world.player_code,
        "player_rank": player_rank,
        "turn": world.turn,
        "date": world.date_str,
        "year": world.year,
        "month": world.month,
        "countries": countries,
        "rankings": [{"code": c, "power": round(p, 1), "name": world.countries[c].name}
                     for c, p in rankings],
        "action_points": game["action_points"],
        "turn_phase": game["turn_phase"],
        "turn_events": game["turn_events"],
        "turn_log": game["turn_log"],
        "game_over": world.game_over,
        "victory_type": world.victory_type,
        "actions": ACTION_CATEGORIES,
        "tech_fields": {k: v[1] for k, v in TECH_FIELDS.items()},
        "regions": sorted(set(c.region for c in world.countries.values())),
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ping")
def ping():
    """Health check endpoint. Also used by keep-alive."""
    return jsonify({"status": "ok"})


@app.route("/api/countries", methods=["GET"])
def get_countries():
    """Get list of playable countries for selection screen."""
    world = World()
    world.load_countries()
    countries = []
    for code, c in world.countries.items():
        power = c.power_index()
        if power > 80:
            diff = "Easy"
        elif power > 50:
            diff = "Medium"
        elif power > 30:
            diff = "Hard"
        else:
            diff = "Expert"
        countries.append({
            "code": code, "name": c.name,
            "leader": f"{c.leader.title} {c.leader.name}",
            "gdp": round(c.economy.gdp, 1),
            "military": round(c.military.power, 0),
            "tech": round(c.tech.level, 0),
            "difficulty": diff, "government": c.government,
            "region": c.region, "traits": c.traits,
        })
    return jsonify(countries)


@app.route("/api/new_game", methods=["POST"])
def new_game():
    data = request.json
    code = data.get("country_code", "US")
    game = _create_game(code)
    return jsonify(_world_state(game))


@app.route("/api/state", methods=["GET"])
def get_state():
    game = _get_game()
    if not game:
        return jsonify({"error": "no_game"}), 404
    return jsonify(_world_state(game))


@app.route("/api/action", methods=["POST"])
def do_action():
    game = _get_game()
    if not game:
        return jsonify({"error": "no_game"}), 404
    world = game["world"]
    if game["action_points"] <= 0:
        return jsonify({"error": "No action points remaining"}), 400

    data = request.json
    action_id = data.get("action_id")
    target_code = data.get("target_code")
    region = data.get("region")
    field = data.get("field")

    # Lookup cost
    cost = 1
    for cat_actions in ACTION_CATEGORIES.values():
        for a in cat_actions:
            if a["id"] == action_id:
                cost = a["cost"]
                break

    if cost > game["action_points"]:
        return jsonify({"error": "Not enough action points"}), 400

    result = execute_action(world, world.get_player(), action_id,
                            target_code=target_code, region=region, field=field)
    game["action_points"] -= cost
    game["turn_log"].append(result)

    _save_session_state(game)
    return jsonify({"result": result, "state": _world_state(game)})


@app.route("/api/end_turn", methods=["POST"])
def end_turn():
    game = _get_game()
    if not game:
        return jsonify({"error": "no_game"}), 404
    world = game["world"]

    # AI turns
    ai_actions = {}
    for code, ai in game["ai_players"].items():
        results = ai.take_turn(world, action_points=3)
        ai_actions[code] = results
    game["turn_ai_actions"] = ai_actions

    # Collect noteworthy AI actions
    ai_headlines = []
    player = world.get_player()
    for code, actions in ai_actions.items():
        c = world.countries[code]
        rel = player.relationships.get(code, 0)
        if abs(rel) > 30 or c.power_index() > 50:
            for msg in actions[:1]:
                if any(w in msg.lower() for w in
                       ["sanction", "alliance", "deploy", "cyber", "tariff", "denounce"]):
                    ai_headlines.append({"country": c.name, "code": code, "action": msg})

    # Events
    events = game["event_engine"].process_turn(world)
    game["turn_events"] = events
    for event in events:
        world.news_log.append({
            "date": world.date_str,
            "headline": event.get("headline", event.get("title", "?")),
            "turn": world.turn,
        })

    # Natural changes
    world.apply_natural_changes()
    world.advance_date()

    # Victory/defeat
    victory = world.check_victory()
    defeat = world.check_defeat()
    if victory:
        world.game_over = True
        world.victory_type = victory
    elif defeat:
        world.game_over = True
        world.victory_type = None

    # Reset for next turn
    game["action_points"] = 4
    game["turn_log"] = []

    _save_session_state(game)

    return jsonify({
        "state": _world_state(game),
        "events": events,
        "ai_headlines": ai_headlines,
        "victory": victory,
        "defeat": defeat,
    })


@app.route("/api/saves", methods=["GET"])
def get_saves():
    return jsonify(list_saves())


@app.route("/api/load", methods=["POST"])
def load():
    data = request.json
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "No filename"}), 400
    world = load_game(filename)
    ai_players = {
        code: AIPlayer(country)
        for code, country in world.countries.items()
        if code != world.player_code
    }
    game = {
        "world": world,
        "ai_players": ai_players,
        "event_engine": EventEngine(),
        "action_points": 4,
        "turn_phase": "actions",
        "turn_events": [],
        "turn_ai_actions": {},
        "turn_log": [],
    }
    sid = os.urandom(8).hex()
    session["game_id"] = sid
    _save_session_state(game)
    return jsonify(_world_state(game))


# ── Keep-alive (prevents Render free tier from sleeping) ───────────────────

def _start_keep_alive():
    """Background thread that pings the app every 10 minutes."""
    import threading
    import urllib.request

    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return  # only run on Render

    def ping_loop():
        import time
        url = f"{render_url}/api/ping"
        while True:
            time.sleep(600)  # 10 minutes
            try:
                urllib.request.urlopen(url, timeout=10)
            except Exception:
                pass

    t = threading.Thread(target=ping_loop, daemon=True)
    t.start()


with app.app_context():
    _start_keep_alive()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
