# World Order - A Geopolitics Strategy Game

A turn-based strategy game modeling contemporary geopolitics. Lead one of 15 real nations through diplomacy, economics, military operations, and technological advancement.

## Quick Start

### Web App (recommended)
```bash
pip install -r requirements.txt
python web_app.py
```
Then open http://localhost:5000 in your browser.

### Terminal Version
```bash
pip install -r requirements.txt
python main.py
```

## How to Play

- **Choose a nation** from 15 real-world powers (US, China, EU, India, Russia, etc.)
- **Each turn = 1 month** — you get 4 action points per turn
- **Pick actions** across 5 categories: Diplomacy, Economy, Military, Technology, Domestic
- **AI-controlled nations** pursue their own strategies based on leader personalities
- **Random events** based on real-world scenarios (oil shocks, cyber attacks, tech breakthroughs, etc.)
- **Game auto-saves** every turn — play a few turns per session

## Actions

| Category | Actions |
|----------|---------|
| **Diplomacy** | Alliance, Sanctions, Lift Sanctions, Diplomatic Outreach, Denounce |
| **Economy** | Trade Deal, Economic Reform, Infrastructure, Raise Tariffs |
| **Military** | Buildup, Cyber Ops, Deploy Forces, Withdraw Forces |
| **Technology** | Research (AI/Space/Energy/Bio/Chips), Tech Partnership |
| **Domestic** | Social Program, Political Reform, Media Campaign, Crackdown |

## Victory Conditions

- **Economic**: Achieve highest GDP exceeding $35T
- **Military**: Reach max military power with nuclear capability
- **Diplomatic**: 90+ influence with 8+ alliance memberships
- **Technological**: All 5 tech fields above 90
- **Domination**: #1 power index with 50+ point lead

## Nations

15 playable nations with real leaders, economies, militaries, and diplomatic relationships: US, China, Russia, EU, India, UK, Japan, Brazil, Saudi Arabia, Australia, South Korea, Turkey, Israel, Nigeria, Indonesia.

## Architecture

```
web_app.py           # Flask web app (recommended)
main.py              # Terminal entry point
templates/
  index.html         # Single-page web frontend
game/
  engine.py          # Game loop and turn processing
  world.py           # World state, rankings, victory/defeat
  country.py         # Country data model
  actions.py         # 19 player actions across 5 categories
  events.py          # 30 events (18 global + 12 country-specific)
  ai.py              # AI with personality-driven decision making
  save_manager.py    # JSON save/load with auto-save
  ui.py              # Rich terminal UI
  data/
    countries.json   # Real-world country data
    events.json      # Event definitions
```
