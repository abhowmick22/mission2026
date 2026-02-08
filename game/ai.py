"""AI system for computer-controlled countries."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING

from game.actions import execute_action, TECH_FIELDS

if TYPE_CHECKING:
    from game.world import World
    from game.country import Country


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class AIPlayer:
    """Simple AI that picks actions based on country priorities and personality."""

    def __init__(self, country: Country):
        self.country = country
        self.personality = self._derive_personality()

    def _derive_personality(self) -> dict[str, float]:
        """Derive AI behavior weights from leader traits and government."""
        weights = {
            "diplomacy": 0.2,
            "economy": 0.3,
            "military": 0.15,
            "technology": 0.2,
            "domestic": 0.15,
        }
        traits = self.country.leader.traits
        if "aggressive" in traits or "hawkish" in traits:
            weights["military"] += 0.15
            weights["diplomacy"] -= 0.05
        if "diplomatic" in traits or "cautious" in traits:
            weights["diplomacy"] += 0.15
            weights["military"] -= 0.1
        if "dealmaker" in traits or "pragmatic" in traits:
            weights["economy"] += 0.1
        if "nationalist" in traits or "protectionist" in traits:
            weights["domestic"] += 0.1
            weights["economy"] -= 0.05
        if "authoritarian" in traits or "strongman" in traits:
            weights["military"] += 0.1
            weights["domestic"] += 0.05
        if "reformer" in traits or "modernizer" in traits:
            weights["technology"] += 0.1
            weights["economy"] += 0.05
        if "long_term_planner" in traits:
            weights["technology"] += 0.1
        if "tech_savvy" in traits:
            weights["technology"] += 0.15
        # Normalize
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}

    def _pick_target(self, world: World, friendly: bool = True) -> str | None:
        """Pick a target country based on relationship."""
        others = {c: r for c, r in self.country.relationships.items()
                  if c != self.country.code and c in world.countries}
        if not others:
            return None
        if friendly:
            # Pick from top-half relations
            sorted_rels = sorted(others.items(), key=lambda x: x[1], reverse=True)
            candidates = sorted_rels[:max(3, len(sorted_rels) // 2)]
        else:
            # Pick from bottom-half relations
            sorted_rels = sorted(others.items(), key=lambda x: x[1])
            candidates = sorted_rels[:max(3, len(sorted_rels) // 2)]
        return random.choice(candidates)[0]

    def _pick_rival(self, world: World) -> str | None:
        """Pick worst relationship."""
        return self._pick_target(world, friendly=False)

    def _pick_friend(self, world: World) -> str | None:
        """Pick best relationship."""
        return self._pick_target(world, friendly=True)

    def take_turn(self, world: World, action_points: int = 3) -> list[str]:
        """AI takes its turn, spending action points. Returns list of result messages."""
        results = []
        c = self.country
        remaining = action_points

        while remaining > 0:
            # Decide category based on personality weights + current needs
            adjusted = dict(self.personality)

            # Urgent needs override personality
            if c.stability < 35:
                adjusted["domestic"] += 0.3
            if c.economy.gdp_growth < 0:
                adjusted["economy"] += 0.25
            if c.economy.inflation > 15:
                adjusted["economy"] += 0.2
            if c.military.power < 25:
                adjusted["military"] += 0.15

            # Normalize
            total = sum(adjusted.values())
            adjusted = {k: v / total for k, v in adjusted.items()}

            # Pick category
            category = random.choices(
                list(adjusted.keys()),
                weights=list(adjusted.values()),
                k=1
            )[0]

            action, result = self._execute_category(world, category, remaining)
            if result:
                results.append(result)
                # Find action cost
                cost = 1
                if action == "deploy":
                    cost = 2
                remaining -= cost
            else:
                remaining -= 1  # prevent infinite loop

        return results

    def _execute_category(self, world: World, category: str, remaining: int) -> tuple[str, str | None]:
        c = self.country

        if category == "diplomacy":
            return self._ai_diplomacy(world)
        elif category == "economy":
            return self._ai_economy(world)
        elif category == "military":
            return self._ai_military(world, remaining)
        elif category == "technology":
            return self._ai_technology(world)
        elif category == "domestic":
            return self._ai_domestic(world)

        return ("skip", None)

    def _ai_diplomacy(self, world: World) -> tuple[str, str | None]:
        c = self.country
        roll = random.random()

        if roll < 0.3:
            # Try alliance with friend
            friend = self._pick_friend(world)
            if friend:
                return ("alliance", execute_action(world, c, "alliance", target_code=friend))
        elif roll < 0.5:
            # Sanction rival
            rival = self._pick_rival(world)
            if rival and c.relationships.get(rival, 0) < -30:
                return ("sanctions", execute_action(world, c, "sanctions", target_code=rival))
        elif roll < 0.7:
            # Improve relations
            target = self._pick_friend(world)
            if target:
                return ("diplomacy", execute_action(world, c, "diplomacy", target_code=target))
        elif roll < 0.85:
            # Denounce rival
            rival = self._pick_rival(world)
            if rival and c.relationships.get(rival, 0) < -20:
                return ("denounce", execute_action(world, c, "denounce", target_code=rival))
        else:
            # Lift sanctions if relations warming
            for sanctioned in list(c.sanctions_on):
                if c.relationships.get(sanctioned, -100) > -10:
                    return ("lift_sanctions", execute_action(world, c, "lift_sanctions", target_code=sanctioned))

        # Default: diplomacy with someone
        target = random.choice(list(world.countries.keys()))
        if target != c.code:
            return ("diplomacy", execute_action(world, c, "diplomacy", target_code=target))
        return ("skip", None)

    def _ai_economy(self, world: World) -> tuple[str, str | None]:
        c = self.country
        roll = random.random()

        if c.economy.gdp_growth < 1.0 or roll < 0.3:
            return ("reform", execute_action(world, c, "reform"))
        elif roll < 0.5:
            friend = self._pick_friend(world)
            if friend and friend not in c.sanctions_on:
                return ("trade", execute_action(world, c, "trade", target_code=friend))
        elif roll < 0.7:
            return ("infrastructure", execute_action(world, c, "infrastructure"))
        else:
            # Tariffs on rival
            rival = self._pick_rival(world)
            if rival and c.relationships.get(rival, 0) < -15:
                return ("tariffs", execute_action(world, c, "tariffs", target_code=rival))

        return ("infrastructure", execute_action(world, c, "infrastructure"))

    def _ai_military(self, world: World, remaining: int) -> tuple[str, str | None]:
        c = self.country
        roll = random.random()

        if c.military.power < 30 or roll < 0.4:
            return ("buildup", execute_action(world, c, "buildup"))
        elif roll < 0.6 and c.military.cyber_capability > 40:
            rival = self._pick_rival(world)
            if rival and c.relationships.get(rival, 0) < -25:
                return ("cyber", execute_action(world, c, "cyber", target_code=rival))
        elif roll < 0.8 and remaining >= 2 and c.military.power > 40:
            regions = ["Middle East", "East Asia", "Europe", "Africa",
                       "South Asia", "Pacific", "Central Asia"]
            region = random.choice(regions)
            if region not in c.military.deployed_regions:
                return ("deploy", execute_action(world, c, "deploy", region=region))

        return ("buildup", execute_action(world, c, "buildup"))

    def _ai_technology(self, world: World) -> tuple[str, str | None]:
        c = self.country
        roll = random.random()

        if roll < 0.6:
            # Research weakest field
            fields = {k: getattr(c.tech, v[0]) for k, v in TECH_FIELDS.items()}
            weakest = min(fields, key=fields.get)
            return ("research", execute_action(world, c, "research", field=weakest))
        else:
            friend = self._pick_friend(world)
            if friend:
                return ("tech_partner", execute_action(world, c, "tech_partner", target_code=friend))

        return ("research", execute_action(world, c, "research", field="ai"))

    def _ai_domestic(self, world: World) -> tuple[str, str | None]:
        c = self.country

        if c.stability < 40:
            if c.government == "authoritarian":
                return ("crackdown", execute_action(world, c, "crackdown"))
            else:
                return ("social", execute_action(world, c, "social"))
        elif c.stability < 55:
            return ("propaganda", execute_action(world, c, "propaganda"))
        elif random.random() < 0.5:
            return ("social", execute_action(world, c, "social"))
        else:
            return ("political_reform", execute_action(world, c, "political_reform"))
