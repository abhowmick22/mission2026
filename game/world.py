"""World state - manages all countries and global state."""

from __future__ import annotations
import json
from pathlib import Path

from game.country import Country


class World:
    def __init__(self):
        self.countries: dict[str, Country] = {}
        self.turn: int = 0
        self.year: int = 2025
        self.month: int = 1  # each turn = 1 month
        self.news_log: list[dict] = []  # history of news headlines
        self.player_code: str = ""
        self.game_over: bool = False
        self.victory_type: str | None = None

    @property
    def date_str(self) -> str:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months[self.month - 1]} {self.year}"

    def advance_date(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.turn += 1

    def load_countries(self):
        """Load country data from JSON."""
        data_path = Path(__file__).parent / "data" / "countries.json"
        with open(data_path) as f:
            data = json.load(f)
        for cdata in data["countries"]:
            country = Country.from_dict(cdata)
            self.countries[country.code] = country

    def get_player(self) -> Country:
        return self.countries[self.player_code]

    def apply_natural_changes(self):
        """Apply natural monthly changes to all countries."""
        for country in self.countries.values():
            # GDP grows/shrinks
            country.economy.gdp *= (1 + country.economy.gdp_growth / 100 / 12)

            # Inflation and unemployment naturally drift
            country.economy.inflation *= 0.98  # slight natural cooling
            country.economy.unemployment *= 0.99

            # Stability drifts toward 50
            if country.stability > 55:
                country.stability -= 0.3
            elif country.stability < 45:
                country.stability += 0.3

            # Approval drifts based on economy
            if country.economy.gdp_growth > 2:
                country.leader.approval += 0.2
            elif country.economy.gdp_growth < 0:
                country.leader.approval -= 0.5

            # Sanctions hurt over time
            sanction_pain = len(country.sanctioned_by) * 0.15
            country.economy.gdp_growth -= sanction_pain
            country.stability -= sanction_pain * 0.5

            # Tech naturally progresses slightly
            country.tech.level += 0.05

            # Clamp values
            country.stability = max(0, min(100, country.stability))
            country.influence = max(0, min(100, country.influence))
            country.leader.approval = max(0, min(100, country.leader.approval))
            country.military.power = max(0, min(100, country.military.power))
            country.tech.level = max(0, min(100, country.tech.level))
            country.economy.gdp = max(0.01, country.economy.gdp)
            country.economy.unemployment = max(0, min(50, country.economy.unemployment))
            country.economy.inflation = max(-5, min(100, country.economy.inflation))

            # Update score
            country.score = country.power_index()

    def get_rankings(self) -> list[tuple[str, float]]:
        """Return countries ranked by power index."""
        ranked = [(code, c.power_index()) for code, c in self.countries.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def check_victory(self) -> str | None:
        """Check if player has achieved any victory condition."""
        player = self.get_player()
        rankings = self.get_rankings()

        # Economic Victory: highest GDP
        gdps = [(code, c.economy.gdp) for code, c in self.countries.items()]
        gdps.sort(key=lambda x: x[1], reverse=True)
        if gdps[0][0] == self.player_code and player.economy.gdp > 35:
            return "economic"

        # Military Victory: highest military + nuclear
        mils = [(code, c.military.power) for code, c in self.countries.items()]
        mils.sort(key=lambda x: x[1], reverse=True)
        if (mils[0][0] == self.player_code and player.military.power > 95
                and player.military.nuclear):
            return "military"

        # Diplomatic Victory: highest influence + most alliances
        if player.influence > 90 and len(player.alliances) >= 8:
            return "diplomatic"

        # Tech Victory: all tech fields above 90
        if (player.tech.ai_research > 90 and player.tech.space > 90
                and player.tech.clean_energy > 90 and player.tech.biotech > 90
                and player.tech.semiconductors > 90):
            return "technological"

        # Domination: #1 in power index by large margin
        if rankings[0][0] == self.player_code:
            margin = rankings[0][1] - rankings[1][1]
            if margin > 50:
                return "domination"

        return None

    def check_defeat(self) -> str | None:
        """Check if player has lost."""
        player = self.get_player()
        if player.stability <= 0:
            return "Your country has collapsed into chaos. Game over."
        if player.economy.gdp < 0.05:
            return "Your economy has completely collapsed. Game over."
        if player.leader.approval <= 0:
            if player.government == "democracy":
                return "You've been voted out of office in a landslide. Game over."
            else:
                return "A revolution has overthrown your government. Game over."
        return None

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "year": self.year,
            "month": self.month,
            "player_code": self.player_code,
            "countries": {code: c.to_dict() for code, c in self.countries.items()},
            "news_log": self.news_log[-50:],  # keep last 50 entries
            "game_over": self.game_over,
            "victory_type": self.victory_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> World:
        world = cls()
        world.turn = data["turn"]
        world.year = data["year"]
        world.month = data["month"]
        world.player_code = data["player_code"]
        world.countries = {
            code: Country.from_dict(cdata)
            for code, cdata in data["countries"].items()
        }
        world.news_log = data.get("news_log", [])
        world.game_over = data.get("game_over", False)
        world.victory_type = data.get("victory_type")
        return world
