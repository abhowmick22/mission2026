"""Flask web app for World Order game.

Game state persists to disk via the save system, so games survive
server restarts and redeployments. Each browser session gets a
persistent game ID stored in a cookie, mapped to a save file.
"""

from __future__ import annotations
import json
import os
import random
from pathlib import Path

from flask import Flask, render_template, jsonify, request, session

from game.world import World
from game.events import EventEngine
from game.ai import AIPlayer
from game.actions import execute_action, ACTION_CATEGORIES, TECH_FIELDS
from game.save_manager import save_game, load_game, list_saves, SAVE_DIR, ensure_save_dir
from game.auth import create_user, verify_user, add_game_to_user, get_user_games
from game.llm import enrich_action_result, enrich_world_event, enrich_ai_reaction, is_enabled as llm_enabled

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
        "ai_ap_used": game.get("ai_ap_used", {}),
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
        "ai_ap_used": session_meta.get("ai_ap_used", {}),
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
        "ai_ap_used": {},
    }
    sid = os.urandom(8).hex()
    session["game_id"] = sid
    _save_session_state(game)
    # Link game to user account if logged in
    username = session.get("username")
    if username:
        add_game_to_user(username, sid)
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
                       "traits": c.leader.traits},
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
        "llm_enabled": llm_enabled(),
    }


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _generate_contextual_event(game: dict) -> dict | None:
    """Generate a world event relevant to the player's current situation."""
    world = game["world"]
    p = world.get_player()

    # Build pool of candidate events based on game state
    pool = []  # list of (weight, event_dict)

    # ── Economy-driven events ──────────────────────────────────────────────
    if p.economy.gdp_growth > 3:
        pool.append((1.5, {
            "headline": f"Foreign investors flock to {p.name}",
            "description": "Strong economic performance attracts international capital.",
            "apply": lambda: (
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.2, 0.5)),
                setattr(p, 'influence', _clamp(p.influence + random.uniform(1, 3))),
            ),
        }))
    if p.economy.gdp_growth < 0.5:
        pool.append((2.0, {
            "headline": f"Credit agencies downgrade {p.name} outlook",
            "description": "Sluggish growth raises concerns about economic trajectory.",
            "apply": lambda: (
                setattr(p, 'influence', _clamp(p.influence - random.uniform(1, 3))),
                setattr(p.economy, 'debt_ratio', p.economy.debt_ratio + random.uniform(0.5, 1.5)),
            ),
        }))
    if p.economy.inflation > 8:
        pool.append((2.5, {
            "headline": f"Cost of living protests erupt in {p.name}",
            "description": "Rising prices drive citizens to the streets.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(3, 7))),
            ),
        }))
    if p.economy.debt_ratio > 100:
        pool.append((1.8, {
            "headline": f"Bond markets jitter over {p.name}'s debt burden",
            "description": "Investors demand higher yields on government bonds.",
            "apply": lambda: (
                setattr(p.economy, 'inflation', p.economy.inflation + random.uniform(0.3, 0.8)),
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.3)),
            ),
        }))
    if p.economy.unemployment > 8:
        pool.append((1.5, {
            "headline": f"Youth unemployment crisis deepens in {p.name}",
            "description": "Lack of jobs fuels social unrest among younger generation.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(2, 5))),
            ),
        }))
    if p.economy.trade_balance > 0.05:
        pool.append((1.0, {
            "headline": f"{p.name}'s trade surplus draws envy and ire",
            "description": "Trading partners accuse your country of unfair practices.",
            "apply": lambda: [
                p.relationships.__setitem__(c, _clamp(p.relationships.get(c, 0) - random.uniform(2, 5), -100, 100))
                for c in random.sample(list(p.relationships.keys()), min(2, len(p.relationships)))
            ],
        }))

    # ── Military-driven events ─────────────────────────────────────────────
    if p.military.power > 70:
        pool.append((1.2, {
            "headline": f"Global powers alarmed by {p.name}'s military expansion",
            "description": "Regional neighbors call for arms control talks.",
            "apply": lambda: (
                setattr(p, 'influence', _clamp(p.influence + random.uniform(1, 2))),
                [p.relationships.__setitem__(c, _clamp(p.relationships.get(c, 0) - random.uniform(2, 4), -100, 100))
                 for c in random.sample(list(p.relationships.keys()), min(3, len(p.relationships)))],
            ),
        }))
    if p.military.deployed_regions:
        region = random.choice(p.military.deployed_regions)
        pool.append((1.5, {
            "headline": f"Tensions flare in {region} over {p.name}'s military presence",
            "description": "Local factions demand withdrawal of foreign forces.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(1, 2))),
                setattr(p.economy, 'debt_ratio', p.economy.debt_ratio + random.uniform(0.2, 0.5)),
            ),
        }))
    if p.military.cyber_capability > 60:
        pool.append((1.0, {
            "headline": f"Major cyberattack targets {p.name}'s infrastructure",
            "description": "State-sponsored hackers probe critical systems.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(1, 3))),
                setattr(p.military, 'cyber_capability', _clamp(p.military.cyber_capability + random.uniform(1, 2))),
            ),
        }))

    # ── Tech-driven events ─────────────────────────────────────────────────
    if p.tech.ai_research > 60:
        pool.append((1.3, {
            "headline": f"AI breakthrough from {p.name} stuns the world",
            "description": "New capabilities raise both excitement and regulatory alarms.",
            "apply": lambda: (
                setattr(p.tech, 'ai_research', _clamp(p.tech.ai_research + random.uniform(1, 3))),
                setattr(p, 'influence', _clamp(p.influence + random.uniform(1, 3))),
            ),
        }))
    if p.tech.semiconductors > 55:
        pool.append((1.0, {
            "headline": f"{p.name}'s chip industry attracts supply chain partners",
            "description": "Global firms rush to secure semiconductor agreements.",
            "apply": lambda: (
                setattr(p.resources, 'manufacturing', _clamp(p.resources.manufacturing + random.uniform(1, 3))),
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.1, 0.4)),
            ),
        }))
    if p.tech.level < 30:
        pool.append((1.5, {
            "headline": f"Brain drain threatens {p.name}'s future",
            "description": "Top scientists and engineers emigrate for better opportunities.",
            "apply": lambda: (
                setattr(p.tech, 'level', _clamp(p.tech.level - random.uniform(0.5, 1.5))),
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.2)),
            ),
        }))
    if p.tech.clean_energy > 50:
        pool.append((1.0, {
            "headline": f"{p.name} hailed as clean energy leader at climate summit",
            "description": "Green transition draws international praise and investment.",
            "apply": lambda: (
                setattr(p, 'influence', _clamp(p.influence + random.uniform(2, 4))),
                setattr(p, 'stability', _clamp(p.stability + random.uniform(1, 2))),
            ),
        }))

    # ── Stability-driven events ────────────────────────────────────────────
    if p.stability < 35:
        pool.append((2.5, {
            "headline": f"Opposition protests intensify across {p.name}",
            "description": "Demonstrators demand government accountability.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(3, 6))),
                setattr(p, 'influence', _clamp(p.influence - random.uniform(1, 2))),
            ),
        }))
    if p.stability > 75:
        pool.append((1.0, {
            "headline": f"Political stability makes {p.name} a business magnet",
            "description": "Multinational corporations announce new investments.",
            "apply": lambda: (
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.2, 0.5)),
                setattr(p, 'influence', _clamp(p.influence + random.uniform(1, 2))),
            ),
        }))
    if p.stability < 25:
        pool.append((2.0, {
            "headline": f"Leadership crisis looms in {p.name}",
            "description": "Deepening instability emboldens rivals at home and abroad.",
            "apply": lambda: (
                setattr(p, 'stability', _clamp(p.stability - random.uniform(2, 4))),
                setattr(p, 'influence', _clamp(p.influence - random.uniform(2, 4))),
            ),
        }))

    # ── Relationship-driven events ─────────────────────────────────────────
    # Rival provocation
    rivals = [(c, v) for c, v in p.relationships.items()
              if v < -30 and c in world.countries]
    if rivals:
        rival_code, rival_rel = random.choice(rivals)
        rival = world.countries[rival_code]
        pool.append((2.0, {
            "headline": f"{rival.name} escalates rhetoric against {p.name}",
            "description": f"Diplomatic tensions worsen as {rival.leader.name} issues sharp warnings.",
            "apply": lambda: (
                p.relationships.__setitem__(rival_code, _clamp(rival_rel - random.uniform(3, 8), -100, 100)),
                setattr(p, 'stability', _clamp(p.stability - random.uniform(1, 2))),
            ),
        }))
    # Ally cooperation
    friends = [(c, v) for c, v in p.relationships.items()
               if v > 30 and c in world.countries]
    if friends:
        friend_code, friend_rel = random.choice(friends)
        friend = world.countries[friend_code]
        pool.append((1.5, {
            "headline": f"{friend.name} proposes joint initiative with {p.name}",
            "description": f"Warm relations lead to new cooperation in trade and security.",
            "apply": lambda: (
                p.relationships.__setitem__(friend_code, _clamp(friend_rel + random.uniform(2, 5), -100, 100)),
                setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.1, 0.3)),
            ),
        }))

    # Sanctioned-by consequences
    if p.sanctioned_by:
        sanctioner_code = random.choice(p.sanctioned_by)
        if sanctioner_code in world.countries:
            sanctioner = world.countries[sanctioner_code]
            pool.append((2.0, {
                "headline": f"{sanctioner.name}'s sanctions bite {p.name}'s economy",
                "description": "Import restrictions cause shortages in key sectors.",
                "apply": lambda: (
                    setattr(p.economy, 'inflation', p.economy.inflation + random.uniform(0.3, 0.8)),
                    setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.3)),
                ),
            }))

    # ── General world events (always available) ────────────────────────────
    pool.append((0.8, {
        "headline": "Global oil prices surge on supply concerns",
        "description": "OPEC cuts and geopolitical tensions drive energy costs higher.",
        "apply": lambda: (
            setattr(p.economy, 'inflation', p.economy.inflation + random.uniform(0.3, 0.7)),
            (setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.2, 0.5))
             if p.resources.oil > 50 else
             setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.3))),
        ),
    }))
    pool.append((0.6, {
        "headline": "Global semiconductor shortage worsens",
        "description": "Supply chain disruptions hit manufacturing worldwide.",
        "apply": lambda: (
            setattr(p.resources, 'manufacturing', _clamp(p.resources.manufacturing - random.uniform(1, 3))),
            (setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.2, 0.5))
             if p.tech.semiconductors > 60 else
             setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.2))),
        ),
    }))
    pool.append((0.7, {
        "headline": f"Severe weather event hits {p.region}",
        "description": "Climate-driven extreme weather causes economic disruption.",
        "apply": lambda: (
            setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.1, 0.4)),
            setattr(p, 'stability', _clamp(p.stability - random.uniform(1, 2))),
            setattr(p.resources, 'food', _clamp(p.resources.food - random.uniform(1, 3))),
        ),
    }))
    pool.append((0.5, {
        "headline": "UN General Assembly debates global reform",
        "description": f"Several nations call for changes affecting {p.name}'s interests.",
        "apply": lambda: (
            setattr(p, 'influence', _clamp(p.influence + random.uniform(-2, 2))),
        ),
    }))
    pool.append((0.6, {
        "headline": "Global markets rally on optimism",
        "description": "A wave of positive sentiment lifts economies worldwide.",
        "apply": lambda: (
            setattr(p.economy, 'gdp_growth', p.economy.gdp_growth + random.uniform(0.1, 0.3)),
            setattr(p, 'stability', _clamp(p.stability + random.uniform(0.5, 1.5))),
        ),
    }))
    pool.append((0.5, {
        "headline": "Pandemic scare rattles global health systems",
        "description": "A new pathogen variant triggers precautionary measures.",
        "apply": lambda: (
            setattr(p.economy, 'gdp_growth', p.economy.gdp_growth - random.uniform(0.2, 0.5)),
            setattr(p, 'stability', _clamp(p.stability - random.uniform(1, 3))),
            setattr(p.tech, 'biotech', _clamp(p.tech.biotech + random.uniform(0.5, 1.5))),
        ),
    }))
    pool.append((0.4, {
        "headline": "International space race heats up",
        "description": f"New milestones put pressure on {p.name}'s space program.",
        "apply": lambda: (
            setattr(p.tech, 'space', _clamp(p.tech.space + random.uniform(0.5, 1.0)))
            if p.tech.space > 40 else
            setattr(p, 'influence', _clamp(p.influence - random.uniform(0.5, 1.0))),
        ),
    }))

    if not pool:
        return None

    weights = [w for w, _ in pool]
    _, event = random.choices(pool, weights=weights, k=1)[0]

    # Apply the effects
    event["apply"]()

    headline, description = enrich_world_event(
        event["headline"], event["description"], p.name
    )

    return {
        "type": "world_event",
        "headline": headline,
        "description": description,
        "affects_player": True,
    }


def _trigger_ai_country_action(game: dict) -> dict | None:
    """Pick one AI nation to take a single action. Returns a reaction dict or None."""
    world = game["world"]
    player = world.get_player()
    ai_ap_used = game.setdefault("ai_ap_used", {})

    # Build list of AI nations that still have AP left (each gets 3 per turn)
    candidates = []
    weights = []
    for code, ai in game["ai_players"].items():
        used = ai_ap_used.get(code, 0)
        if used >= 3:
            continue
        c = world.countries[code]
        w = c.power_index() / 40.0 + abs(player.relationships.get(code, 0)) / 40.0
        candidates.append((code, ai))
        weights.append(max(0.1, w))

    if not candidates:
        return None

    (reactor_code, reactor_ai), = random.choices(candidates, weights=weights, k=1)
    reactor_country = world.countries[reactor_code]

    results = reactor_ai.take_turn(world, action_points=1)
    ai_ap_used[reactor_code] = ai_ap_used.get(reactor_code, 0) + 1

    if not results:
        return None

    action_text = results[0]
    affects_player = (
        player.name.lower() in action_text.lower()
        or player.code in action_text
    )

    rel = player.relationships.get(reactor_code, 0)
    enriched_text = enrich_ai_reaction(
        reactor_country.name, action_text, player.name, rel
    )

    return {
        "type": "country_action",
        "country": reactor_country.name,
        "code": reactor_code,
        "action": enriched_text,
        "affects_player": affects_player,
    }


def _trigger_world_reaction(game: dict) -> dict | None:
    """Trigger either an AI country action or a contextual world event."""
    # ~45% world event, ~55% country action
    if random.random() < 0.45:
        event = _generate_contextual_event(game)
        if event:
            return event
    return _trigger_ai_country_action(game)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ping")
def ping():
    """Health check endpoint. Also used by keep-alive."""
    return jsonify({"status": "ok"})


# ── Auth routes ────────────────────────────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, msg = create_user(username, password)
    if not ok:
        return jsonify({"error": msg}), 400
    session["username"] = username
    return jsonify({"username": username, "message": msg})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, msg = verify_user(username, password)
    if not ok:
        return jsonify({"error": msg}), 401
    session["username"] = username
    # Restore most recent game if available
    game_ids = get_user_games(username)
    if game_ids:
        session["game_id"] = game_ids[-1]
    return jsonify({"username": username, "has_game": bool(game_ids)})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    session.pop("game_id", None)
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def me():
    username = session.get("username")
    if not username:
        return jsonify({"logged_in": False})
    game_ids = get_user_games(username)
    has_game = bool(session.get("game_id"))
    return jsonify({"logged_in": True, "username": username,
                    "has_game": has_game, "game_count": len(game_ids)})


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

    player = world.get_player()
    result = execute_action(world, player, action_id,
                            target_code=target_code, region=region, field=field)
    enriched_result = enrich_action_result(player.name, result)
    game["action_points"] -= cost
    game["turn_log"].append(result)  # log stores the original concise text

    # World reaction: either a country action or a world event
    ai_reaction = _trigger_world_reaction(game)

    _save_session_state(game)
    return jsonify({
        "result": enriched_result,
        "state": _world_state(game),
        "ai_reaction": ai_reaction,
    })


@app.route("/api/end_turn", methods=["POST"])
def end_turn():
    game = _get_game()
    if not game:
        return jsonify({"error": "no_game"}), 404
    world = game["world"]

    # AI turns — give each nation only their remaining AP (some already reacted)
    ai_ap_used = game.get("ai_ap_used", {})
    ai_actions = {}
    for code, ai in game["ai_players"].items():
        remaining_ap = max(0, 3 - ai_ap_used.get(code, 0))
        if remaining_ap > 0:
            results = ai.take_turn(world, action_points=remaining_ap)
            ai_actions[code] = results
        else:
            ai_actions[code] = []
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
    game["ai_ap_used"] = {}

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
        "ai_ap_used": {},
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
