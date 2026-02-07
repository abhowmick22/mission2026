"""Country model representing a nation-state in the game."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Leader:
    name: str
    title: str
    traits: list[str] = field(default_factory=list)
    approval: float = 50.0  # 0-100


@dataclass
class Military:
    power: float = 0.0          # overall military strength index
    nuclear: bool = False
    cyber_capability: float = 0.0  # 0-100
    deployed_regions: list[str] = field(default_factory=list)


@dataclass
class Economy:
    gdp: float = 0.0              # trillions USD
    gdp_growth: float = 0.0       # percentage
    debt_ratio: float = 0.0       # debt as % of GDP
    trade_balance: float = 0.0    # billions USD
    unemployment: float = 0.0     # percentage
    inflation: float = 0.0        # percentage


@dataclass
class Technology:
    level: float = 0.0       # 0-100 overall tech index
    ai_research: float = 0.0
    space: float = 0.0
    clean_energy: float = 0.0
    biotech: float = 0.0
    semiconductors: float = 0.0


@dataclass
class Resources:
    oil: float = 0.0         # relative production capacity
    natural_gas: float = 0.0
    minerals: float = 0.0
    food: float = 0.0
    manufacturing: float = 0.0


@dataclass
class Country:
    name: str
    code: str                    # 2-letter code
    region: str
    leader: Leader
    government: str              # democracy, authoritarian, etc.
    population: float            # millions
    military: Military = field(default_factory=Military)
    economy: Economy = field(default_factory=Economy)
    tech: Technology = field(default_factory=Technology)
    resources: Resources = field(default_factory=Resources)
    stability: float = 50.0      # 0-100 internal stability
    influence: float = 50.0      # 0-100 global diplomatic influence
    relationships: dict[str, float] = field(default_factory=dict)  # country_code -> -100 to 100
    alliances: list[str] = field(default_factory=list)
    sanctions_on: list[str] = field(default_factory=list)  # country codes we sanction
    sanctioned_by: list[str] = field(default_factory=list)  # country codes sanctioning us
    traits: list[str] = field(default_factory=list)  # special country traits
    score: float = 0.0

    def power_index(self) -> float:
        """Composite power score."""
        return (
            self.economy.gdp * 2.0
            + self.military.power * 1.5
            + self.tech.level * 1.0
            + self.influence * 0.5
            + self.stability * 0.3
            + (self.population / 100) * 0.2
        )

    def to_dict(self) -> dict:
        """Serialize to dict for saving."""
        return {
            "name": self.name,
            "code": self.code,
            "region": self.region,
            "leader": {
                "name": self.leader.name,
                "title": self.leader.title,
                "traits": self.leader.traits,
                "approval": self.leader.approval,
            },
            "government": self.government,
            "population": self.population,
            "military": {
                "power": self.military.power,
                "nuclear": self.military.nuclear,
                "cyber_capability": self.military.cyber_capability,
                "deployed_regions": self.military.deployed_regions,
            },
            "economy": {
                "gdp": self.economy.gdp,
                "gdp_growth": self.economy.gdp_growth,
                "debt_ratio": self.economy.debt_ratio,
                "trade_balance": self.economy.trade_balance,
                "unemployment": self.unemployment if hasattr(self, 'unemployment') else self.economy.unemployment,
                "inflation": self.economy.inflation,
            },
            "tech": {
                "level": self.tech.level,
                "ai_research": self.tech.ai_research,
                "space": self.tech.space,
                "clean_energy": self.tech.clean_energy,
                "biotech": self.tech.biotech,
                "semiconductors": self.tech.semiconductors,
            },
            "resources": {
                "oil": self.resources.oil,
                "natural_gas": self.resources.natural_gas,
                "minerals": self.resources.minerals,
                "food": self.resources.food,
                "manufacturing": self.resources.manufacturing,
            },
            "stability": self.stability,
            "influence": self.influence,
            "relationships": self.relationships,
            "alliances": self.alliances,
            "sanctions_on": self.sanctions_on,
            "sanctioned_by": self.sanctioned_by,
            "traits": self.traits,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Country:
        """Deserialize from dict."""
        return cls(
            name=data["name"],
            code=data["code"],
            region=data["region"],
            leader=Leader(**data["leader"]),
            government=data["government"],
            population=data["population"],
            military=Military(**data["military"]),
            economy=Economy(**data["economy"]),
            tech=Technology(**data["tech"]),
            resources=Resources(**data["resources"]),
            stability=data["stability"],
            influence=data["influence"],
            relationships=data.get("relationships", {}),
            alliances=data.get("alliances", []),
            sanctions_on=data.get("sanctions_on", []),
            sanctioned_by=data.get("sanctioned_by", []),
            traits=data.get("traits", []),
            score=data.get("score", 0.0),
        )
