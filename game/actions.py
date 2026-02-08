"""Player actions - diplomacy, economy, military, technology, domestic."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.world import World
    from game.country import Country


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ── Diplomacy ──────────────────────────────────────────────────────────────

def propose_alliance(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    rel = actor.relationships.get(target_code, 0)
    if rel < 10:
        return f"{target.name} rejects alliance proposal — relations too poor ({rel:+.0f})."
    # Check if already allied through same org
    common = set(actor.alliances) & set(target.alliances)
    if common:
        return f"Already share alliance membership: {', '.join(common)}."
    # Success chance based on relationship
    chance = min(0.9, 0.3 + rel / 200)
    if random.random() < chance:
        alliance_name = f"{actor.code}-{target_code} Pact"
        actor.alliances.append(alliance_name)
        target.alliances.append(alliance_name)
        actor.relationships[target_code] = clamp(rel + 15, -100, 100)
        target.relationships[actor.code] = clamp(
            target.relationships.get(actor.code, 0) + 15, -100, 100
        )
        actor.influence = clamp(actor.influence + 2)
        return f"Alliance formed: {alliance_name}! Relations improve with {target.name}."
    else:
        actor.relationships[target_code] = clamp(rel - 5, -100, 100)
        return f"{target.name} politely declines the alliance proposal."


def impose_sanctions(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    if target_code in actor.sanctions_on:
        return f"Already sanctioning {target.name}."
    actor.sanctions_on.append(target_code)
    target.sanctioned_by.append(actor.code)
    # Economic impact
    severity = actor.economy.gdp / (actor.economy.gdp + target.economy.gdp)
    target.economy.gdp_growth -= severity * 1.5
    target.economy.inflation += severity * 2.0
    # Relationship damage
    actor.relationships[target_code] = clamp(
        actor.relationships.get(target_code, 0) - 20, -100, 100
    )
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) - 25, -100, 100
    )
    # Rally allies against target
    for code, c in world.countries.items():
        if code in (actor.code, target_code):
            continue
        common_alliances = set(actor.alliances) & set(c.alliances)
        if common_alliances:
            c.relationships[target_code] = clamp(
                c.relationships.get(target_code, 0) - 5, -100, 100
            )
    return (f"Sanctions imposed on {target.name}! Their GDP growth hit by "
            f"{severity * 1.5:.1f}%, inflation up {severity * 2:.1f}%.")


def lift_sanctions(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    if target_code not in actor.sanctions_on:
        return f"Not currently sanctioning {target.name}."
    actor.sanctions_on.remove(target_code)
    target.sanctioned_by.remove(actor.code)
    actor.relationships[target_code] = clamp(
        actor.relationships.get(target_code, 0) + 10, -100, 100
    )
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) + 8, -100, 100
    )
    target.economy.gdp_growth += 0.5
    return f"Sanctions on {target.name} lifted. Relations warming."


def improve_relations(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    rel = actor.relationships.get(target_code, 0)
    boost = random.uniform(5, 15)
    actor.relationships[target_code] = clamp(rel + boost, -100, 100)
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) + boost * 0.6, -100, 100
    )
    actor.influence = clamp(actor.influence + 1)
    return (f"Diplomatic outreach to {target.name} succeeds! "
            f"Relations improved by {boost:.0f} points.")


def denounce(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    actor.relationships[target_code] = clamp(
        actor.relationships.get(target_code, 0) - 15, -100, 100
    )
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) - 20, -100, 100
    )
    # Allies join in
    for code, c in world.countries.items():
        if code in (actor.code, target_code):
            continue
        if set(actor.alliances) & set(c.alliances):
            c.relationships[target_code] = clamp(
                c.relationships.get(target_code, 0) - 3, -100, 100
            )
    actor.influence = clamp(actor.influence + 1)
    return f"You publicly denounce {target.name}. Global opinion shifts."


# ── Economy ────────────────────────────────────────────────────────────────

def trade_deal(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    rel = actor.relationships.get(target_code, 0)
    if rel < -20:
        return f"Relations with {target.name} too hostile for trade ({rel:+.0f})."
    if target_code in actor.sanctions_on:
        return f"Cannot trade with {target.name} while sanctions active."
    # Trade benefits proportional to economic complementarity
    actor_boost = target.economy.gdp * 0.02
    target_boost = actor.economy.gdp * 0.02
    actor.economy.gdp_growth += actor_boost
    actor.economy.trade_balance += 0.01
    target.economy.gdp_growth += target_boost * 0.5  # smaller benefit for target
    actor.relationships[target_code] = clamp(rel + 8, -100, 100)
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) + 5, -100, 100
    )
    return (f"Trade deal with {target.name}! GDP growth boosted by {actor_boost:.2f}%. "
            f"Relations improve.")


def economic_reform(world: World, actor: Country) -> str:
    if actor.stability < 30:
        return "Country too unstable for economic reform — risk of backlash."
    # Short term pain, long term gain
    actor.economy.gdp_growth += random.uniform(0.3, 1.0)
    actor.economy.unemployment -= random.uniform(0.2, 0.8)
    actor.economy.inflation -= random.uniform(0.2, 0.5)
    actor.stability -= random.uniform(1, 4)  # reforms cause some instability
    return ("Economic reform package implemented. Growth improved, unemployment down, "
            "but some instability from changes.")


def invest_infrastructure(world: World, actor: Country) -> str:
    cost_ratio = 0.5  # % of GDP
    actor.economy.gdp_growth += random.uniform(0.2, 0.6)
    actor.economy.debt_ratio += cost_ratio
    actor.stability += random.uniform(1, 3)
    actor.resources.manufacturing += random.uniform(1, 3)
    return ("Major infrastructure investment announced. Growth boosted, "
            "manufacturing capacity up, stability rises.")


def raise_tariffs(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    actor.economy.trade_balance += 0.02
    actor.economy.inflation += 0.5
    target.economy.gdp_growth -= 0.3
    target.economy.trade_balance -= 0.02
    actor.relationships[target_code] = clamp(
        actor.relationships.get(target_code, 0) - 10, -100, 100
    )
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) - 12, -100, 100
    )
    return (f"Tariffs raised on {target.name} imports. Trade balance improves but "
            f"inflation ticks up. {target.name} is displeased.")


# ── Military ───────────────────────────────────────────────────────────────

def military_buildup(world: World, actor: Country) -> str:
    cost = 0.3  # debt increase
    actor.military.power = clamp(actor.military.power + random.uniform(2, 5))
    actor.economy.debt_ratio += cost
    actor.economy.gdp_growth -= 0.1
    # Neighbors get nervous
    for code, c in world.countries.items():
        if code == actor.code:
            continue
        if c.region == actor.region:
            c.relationships[actor.code] = clamp(
                c.relationships.get(actor.code, 0) - 3, -100, 100
            )
    return ("Military buildup underway. Power increased, but defense spending "
            "adds to debt. Regional neighbors take notice.")


def cyber_operation(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    # Success based on cyber capability differential
    success_chance = 0.3 + (actor.military.cyber_capability - target.military.cyber_capability) / 200
    success_chance = clamp(success_chance, 0.1, 0.9)
    if random.random() < success_chance:
        damage = random.uniform(2, 8)
        target.stability -= damage
        target.economy.gdp_growth -= random.uniform(0.1, 0.4)
        # Small chance of getting caught
        if random.random() < 0.3:
            actor.relationships[target_code] = clamp(
                actor.relationships.get(target_code, 0) - 15, -100, 100
            )
            target.relationships[actor.code] = clamp(
                target.relationships.get(actor.code, 0) - 20, -100, 100
            )
            return (f"Cyber operation against {target.name} succeeds but is attributed! "
                    f"Stability hit: {damage:.0f}. Diplomatic fallout ensues.")
        return (f"Covert cyber operation against {target.name} succeeds. "
                f"Target stability -{damage:.0f}.")
    else:
        actor.military.cyber_capability = clamp(actor.military.cyber_capability + 1)
        if random.random() < 0.4:
            actor.relationships[target_code] = clamp(
                actor.relationships.get(target_code, 0) - 10, -100, 100
            )
            return f"Cyber operation against {target.name} fails and is detected! Relations damaged."
        return f"Cyber operation against {target.name} fails to achieve objectives."


def deploy_forces(world: World, actor: Country, region: str) -> str:
    if actor.military.power < 20:
        return "Military too weak for force deployment."
    actor.military.deployed_regions.append(region)
    actor.military.power = clamp(actor.military.power - 2)  # strain
    actor.economy.debt_ratio += 0.5
    actor.influence = clamp(actor.influence + 3)
    # Affect countries in region
    for code, c in world.countries.items():
        if code == actor.code:
            continue
        if c.region == region:
            rel = c.relationships.get(actor.code, 0)
            if rel > 20:  # allies welcome it
                c.stability += 2
            else:  # rivals get nervous
                c.relationships[actor.code] = clamp(rel - 10, -100, 100)
    return (f"Forces deployed to {region}. Influence rises but military strained. "
            f"Regional reactions are mixed.")


def withdraw_forces(world: World, actor: Country, region: str) -> str:
    if region not in actor.military.deployed_regions:
        return f"No forces deployed in {region}."
    actor.military.deployed_regions.remove(region)
    actor.military.power = clamp(actor.military.power + 1)
    actor.economy.debt_ratio -= 0.2
    return f"Forces withdrawn from {region}. Military readiness improves."


# ── Technology ─────────────────────────────────────────────────────────────

TECH_FIELDS = {
    "ai": ("ai_research", "AI Research"),
    "space": ("space", "Space Program"),
    "energy": ("clean_energy", "Clean Energy"),
    "bio": ("biotech", "Biotechnology"),
    "chips": ("semiconductors", "Semiconductors"),
}


def research_initiative(world: World, actor: Country, field: str) -> str:
    if field not in TECH_FIELDS:
        return f"Unknown research field: {field}. Options: {', '.join(TECH_FIELDS.keys())}"
    attr, name = TECH_FIELDS[field]
    current = getattr(actor.tech, attr)
    # Diminishing returns at higher levels
    gain = random.uniform(2, 5) * (1.0 - current / 150)
    setattr(actor.tech, attr, clamp(current + gain))
    actor.tech.level = clamp(actor.tech.level + gain * 0.3)
    actor.economy.debt_ratio += 0.2
    return f"{name} initiative launched! Progress: +{gain:.1f}. Total: {current + gain:.0f}."


def tech_partnership(world: World, actor: Country, target_code: str) -> str:
    target = world.countries[target_code]
    rel = actor.relationships.get(target_code, 0)
    if rel < 0:
        return f"Relations with {target.name} too poor for tech partnership ({rel:+.0f})."
    # Both benefit, weaker side benefits more
    actor_gain = max(0, (target.tech.level - actor.tech.level) * 0.1 + 1)
    target_gain = max(0, (actor.tech.level - target.tech.level) * 0.1 + 0.5)
    actor.tech.level = clamp(actor.tech.level + actor_gain)
    target.tech.level = clamp(target.tech.level + target_gain)
    actor.relationships[target_code] = clamp(rel + 5, -100, 100)
    target.relationships[actor.code] = clamp(
        target.relationships.get(actor.code, 0) + 5, -100, 100
    )
    return (f"Tech partnership with {target.name} established! "
            f"Your tech +{actor_gain:.1f}, their tech +{target_gain:.1f}.")


# ── Domestic ───────────────────────────────────────────────────────────────

def social_program(world: World, actor: Country) -> str:
    actor.stability = clamp(actor.stability + random.uniform(3, 7))
    actor.economy.debt_ratio += 0.3
    actor.economy.unemployment -= random.uniform(0.2, 0.5)
    return ("Social program launched. Stability up, "
            "unemployment down, but adds to national debt.")


def political_reform(world: World, actor: Country) -> str:
    if actor.government == "authoritarian":
        risk = random.random()
        if risk < 0.3:
            actor.stability -= random.uniform(5, 12)
            return "Political reform attempt backfires — hardliners resist. Stability drops."
    actor.stability = clamp(actor.stability + random.uniform(2, 5))
    actor.influence = clamp(actor.influence + random.uniform(1, 3))
    return "Political reforms enacted. Stability and global standing improve."


def propaganda_campaign(world: World, actor: Country) -> str:
    actor.stability = clamp(actor.stability + random.uniform(3, 8))
    actor.influence = clamp(actor.influence + random.uniform(1, 3))
    if actor.government == "democracy":
        # Can backfire in democracies
        if random.random() < 0.3:
            actor.stability -= random.uniform(3, 5)
            return "Media campaign exposed by free press! Stability drops."
    return "Media campaign boosts national unity. Stability rises."


def crack_down(world: World, actor: Country) -> str:
    """Authoritarian stability move."""
    actor.stability = clamp(actor.stability + random.uniform(5, 10))
    actor.influence = clamp(actor.influence - random.uniform(2, 5))
    # Democracies condemn
    for code, c in world.countries.items():
        if code == actor.code:
            continue
        if c.government == "democracy":
            c.relationships[actor.code] = clamp(
                c.relationships.get(actor.code, 0) - 3, -100, 100
            )
    return ("Crackdown restores order but draws international condemnation. "
            "Stability up, global influence down.")


# ── Action Registry ────────────────────────────────────────────────────────

ACTION_CATEGORIES = {
    "Diplomacy": [
        {"id": "alliance", "name": "Propose Alliance", "cost": 1, "needs_target": True,
         "desc": "Form a bilateral pact with another nation"},
        {"id": "sanctions", "name": "Impose Sanctions", "cost": 1, "needs_target": True,
         "desc": "Economic sanctions on a rival"},
        {"id": "lift_sanctions", "name": "Lift Sanctions", "cost": 1, "needs_target": True,
         "desc": "Remove existing sanctions"},
        {"id": "diplomacy", "name": "Diplomatic Outreach", "cost": 1, "needs_target": True,
         "desc": "Improve relations through diplomacy"},
        {"id": "denounce", "name": "Public Denouncement", "cost": 1, "needs_target": True,
         "desc": "Publicly condemn a nation"},
    ],
    "Economy": [
        {"id": "trade", "name": "Trade Deal", "cost": 1, "needs_target": True,
         "desc": "Negotiate a trade agreement"},
        {"id": "reform", "name": "Economic Reform", "cost": 1, "needs_target": False,
         "desc": "Restructure economy for growth"},
        {"id": "infrastructure", "name": "Infrastructure Investment", "cost": 1, "needs_target": False,
         "desc": "Build infrastructure, boost manufacturing"},
        {"id": "tariffs", "name": "Raise Tariffs", "cost": 1, "needs_target": True,
         "desc": "Protectionist trade barriers"},
    ],
    "Military": [
        {"id": "buildup", "name": "Military Buildup", "cost": 1, "needs_target": False,
         "desc": "Increase military power"},
        {"id": "cyber", "name": "Cyber Operation", "cost": 1, "needs_target": True,
         "desc": "Covert cyber attack on target"},
        {"id": "deploy", "name": "Deploy Forces", "cost": 2, "needs_target": False, "needs_region": True,
         "desc": "Deploy military to a region"},
        {"id": "withdraw", "name": "Withdraw Forces", "cost": 1, "needs_target": False, "needs_region": True,
         "desc": "Withdraw from a region"},
    ],
    "Technology": [
        {"id": "research", "name": "Research Initiative", "cost": 1, "needs_target": False, "needs_field": True,
         "desc": "Invest in a tech field (ai/space/energy/bio/chips)"},
        {"id": "tech_partner", "name": "Tech Partnership", "cost": 1, "needs_target": True,
         "desc": "Joint research with another nation"},
    ],
    "Domestic": [
        {"id": "social", "name": "Social Program", "cost": 1, "needs_target": False,
         "desc": "Boost stability and reduce unemployment"},
        {"id": "political_reform", "name": "Political Reform", "cost": 1, "needs_target": False,
         "desc": "Enact governance reforms"},
        {"id": "propaganda", "name": "Media Campaign", "cost": 1, "needs_target": False,
         "desc": "Boost stability through media"},
        {"id": "crackdown", "name": "Crackdown", "cost": 1, "needs_target": False,
         "desc": "Restore order through force (risky)"},
    ],
}


def execute_action(
    world: World,
    actor: Country,
    action_id: str,
    target_code: str | None = None,
    region: str | None = None,
    field: str | None = None,
) -> str:
    """Execute a player action and return result description."""
    dispatch = {
        "alliance": lambda: propose_alliance(world, actor, target_code),
        "sanctions": lambda: impose_sanctions(world, actor, target_code),
        "lift_sanctions": lambda: lift_sanctions(world, actor, target_code),
        "diplomacy": lambda: improve_relations(world, actor, target_code),
        "denounce": lambda: denounce(world, actor, target_code),
        "trade": lambda: trade_deal(world, actor, target_code),
        "reform": lambda: economic_reform(world, actor),
        "infrastructure": lambda: invest_infrastructure(world, actor),
        "tariffs": lambda: raise_tariffs(world, actor, target_code),
        "buildup": lambda: military_buildup(world, actor),
        "cyber": lambda: cyber_operation(world, actor, target_code),
        "deploy": lambda: deploy_forces(world, actor, region),
        "withdraw": lambda: withdraw_forces(world, actor, region),
        "research": lambda: research_initiative(world, actor, field),
        "tech_partner": lambda: tech_partnership(world, actor, target_code),
        "social": lambda: social_program(world, actor),
        "political_reform": lambda: political_reform(world, actor),
        "propaganda": lambda: propaganda_campaign(world, actor),
        "crackdown": lambda: crack_down(world, actor),
    }
    handler = dispatch.get(action_id)
    if handler is None:
        return f"Unknown action: {action_id}"
    return handler()
