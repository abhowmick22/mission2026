"""Events system - random and scripted events that shape the world."""

from __future__ import annotations
import json
import random
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.world import World
    from game.country import Country


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


class EventEngine:
    def __init__(self):
        data_path = Path(__file__).parent / "data" / "events.json"
        with open(data_path) as f:
            data = json.load(f)
        self.global_events = data["global_events"]
        self.country_events = data["country_events"]

    def _apply_effects(self, country: Country, effects: dict):
        """Apply a dict of dotted-path effects to a country."""
        for path, value in effects.items():
            parts = path.split(".")
            obj = country
            for part in parts[:-1]:
                obj = getattr(obj, part)
            attr = parts[-1]
            current = getattr(obj, attr)
            if isinstance(current, bool):
                setattr(obj, attr, bool(value))
            else:
                setattr(obj, attr, clamp(current + value, -200, 200))

    def _is_oil_producer(self, c: Country) -> bool:
        return c.resources.oil >= 40

    def _is_oil_importer(self, c: Country) -> bool:
        return c.resources.oil < 30

    def _is_tech_leader(self, c: Country) -> bool:
        return c.tech.level >= 70

    def _is_chip_producer(self, c: Country) -> bool:
        return c.tech.semiconductors >= 60

    def _is_chip_importer(self, c: Country) -> bool:
        return c.tech.semiconductors < 40

    def _is_green_leader(self, c: Country) -> bool:
        return c.tech.clean_energy >= 55

    def _is_space_leader(self, c: Country) -> bool:
        return c.tech.space >= 55

    def _is_mineral_rich(self, c: Country) -> bool:
        return c.resources.minerals >= 50

    def _is_food_exporter(self, c: Country) -> bool:
        return c.resources.food >= 65

    def _is_food_importer(self, c: Country) -> bool:
        return c.resources.food < 35

    def _is_financial_center(self, c: Country) -> bool:
        return "financial_center" in c.traits or "reserve_currency" in c.traits

    def _check_condition(self, country: Country, condition: str) -> bool:
        """Evaluate a simple condition string like 'stability < 40'."""
        if not condition:
            return True
        parts = condition.split()
        if len(parts) != 3:
            return True
        path, op, threshold = parts
        threshold = float(threshold)
        obj = country
        for part in path.split("."):
            obj = getattr(obj, part)
        value = float(obj)
        if op == "<":
            return value < threshold
        elif op == ">":
            return value > threshold
        elif op == ">=":
            return value >= threshold
        elif op == "<=":
            return value <= threshold
        return True

    def process_global_events(self, world: World) -> list[dict]:
        """Roll for and apply global events. Returns list of triggered events."""
        triggered = []
        for event in self.global_events:
            if random.random() > event["probability"]:
                continue

            headlines = [event["headline"]]
            affected_countries = []

            for effect_group, effects in event["effects"].items():
                targets = []
                if effect_group == "all":
                    targets = list(world.countries.values())
                elif effect_group == "oil_producers":
                    targets = [c for c in world.countries.values() if self._is_oil_producer(c)]
                elif effect_group == "oil_importers":
                    targets = [c for c in world.countries.values() if self._is_oil_importer(c)]
                elif effect_group == "tech_leaders":
                    targets = [c for c in world.countries.values() if self._is_tech_leader(c)]
                elif effect_group == "chip_producers":
                    targets = [c for c in world.countries.values() if self._is_chip_producer(c)]
                elif effect_group == "chip_importers":
                    targets = [c for c in world.countries.values() if self._is_chip_importer(c)]
                elif effect_group == "green_leaders":
                    targets = [c for c in world.countries.values() if self._is_green_leader(c)]
                elif effect_group == "space_leaders":
                    targets = [c for c in world.countries.values() if self._is_space_leader(c)]
                elif effect_group == "mineral_rich":
                    targets = [c for c in world.countries.values() if self._is_mineral_rich(c)]
                elif effect_group == "mineral_poor":
                    targets = [c for c in world.countries.values() if not self._is_mineral_rich(c)]
                elif effect_group == "food_exporters":
                    targets = [c for c in world.countries.values() if self._is_food_exporter(c)]
                elif effect_group == "food_importers":
                    targets = [c for c in world.countries.values() if self._is_food_importer(c)]
                elif effect_group == "financial_centers":
                    targets = [c for c in world.countries.values() if self._is_financial_center(c)]
                elif effect_group == "low_cyber":
                    targets = [c for c in world.countries.values() if c.military.cyber_capability < 40]
                elif effect_group == "high_cyber":
                    targets = [c for c in world.countries.values() if c.military.cyber_capability >= 60]
                elif effect_group == "low_stability":
                    targets = [c for c in world.countries.values() if c.stability < 45]
                elif effect_group == "high_stability":
                    targets = [c for c in world.countries.values() if c.stability >= 55]
                elif effect_group == "neighboring":
                    # Pick a random region for the crisis
                    regions = list(set(c.region for c in world.countries.values()))
                    crisis_region = random.choice(regions)
                    targets = [c for c in world.countries.values() if c.region == crisis_region]
                elif effect_group == "distant":
                    targets = list(world.countries.values())

                for target in targets:
                    self._apply_effects(target, effects)
                    affected_countries.append(target.name)

            triggered.append({
                "title": event["title"],
                "headline": event["headline"],
                "description": event["description"],
                "affected": list(set(affected_countries)),
                "tags": event.get("tags", []),
            })

        return triggered

    def process_country_events(self, world: World) -> list[dict]:
        """Roll for country-specific events. Returns list of triggered events."""
        triggered = []
        for country in world.countries.values():
            for event in self.country_events:
                if random.random() > event["probability"]:
                    continue
                # Check government type
                applicable = event.get("applicable", ["all"])
                if "all" not in applicable and country.government not in applicable:
                    continue
                # Check condition
                condition = event.get("condition", "")
                if condition and not self._check_condition(country, condition):
                    continue
                # Apply effects
                self._apply_effects(country, event["effects"])
                headline = event["headline"].replace("{country}", country.name)
                triggered.append({
                    "title": event["title"],
                    "headline": headline,
                    "country": country.name,
                    "country_code": country.code,
                })

        return triggered

    def process_turn(self, world: World) -> list[dict]:
        """Process all events for a turn."""
        events = []
        events.extend(self.process_global_events(world))
        events.extend(self.process_country_events(world))
        return events
