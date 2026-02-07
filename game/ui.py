"""Terminal UI using rich library."""

from __future__ import annotations
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich import box

from game.actions import ACTION_CATEGORIES, TECH_FIELDS

if TYPE_CHECKING:
    from game.world import World
    from game.country import Country

console = Console()

# ── Emoji-free icons ──────────────────────────────────────────────────────
FLAG = {
    "US": "[bold blue]US[/]", "CN": "[bold red]CN[/]", "RU": "[bold white]RU[/]",
    "EU": "[bold blue]EU[/]", "IN": "[bold yellow]IN[/]", "GB": "[bold blue]GB[/]",
    "JP": "[bold red]JP[/]", "BR": "[bold green]BR[/]", "SA": "[bold green]SA[/]",
    "AU": "[bold yellow]AU[/]", "KR": "[bold blue]KR[/]", "TR": "[bold red]TR[/]",
    "IL": "[bold blue]IL[/]", "NG": "[bold green]NG[/]", "ID": "[bold red]ID[/]",
}


def get_flag(code: str) -> str:
    return FLAG.get(code, f"[bold]{code}[/]")


def rel_color(value: float) -> str:
    if value >= 50:
        return "green"
    elif value >= 20:
        return "bright_green"
    elif value >= -20:
        return "yellow"
    elif value >= -50:
        return "red"
    return "bold red"


def stat_bar(value: float, max_val: float = 100, width: int = 15) -> str:
    filled = int(value / max_val * width)
    filled = max(0, min(width, filled))
    bar = "+" * filled + "-" * (width - filled)
    if value >= 70:
        color = "green"
    elif value >= 40:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{bar}[/] {value:.0f}"


def show_title_screen():
    title = Text()
    title.append("\n")
    title.append("  WORLD  ORDER\n", style="bold white on blue")
    title.append("  A Geopolitics Strategy Game\n\n", style="bold cyan")
    title.append("  Lead your nation through the complexities\n", style="dim")
    title.append("  of modern geopolitics, economics, and warfare.\n\n", style="dim")
    console.print(Panel(title, border_style="blue", box=box.DOUBLE))


def show_country_select(countries: dict[str, Country]) -> str:
    console.print("\n[bold cyan]Choose your nation:[/]\n")
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("#", style="bold", width=3)
    table.add_column("Nation", style="bold", width=20)
    table.add_column("Leader", width=25)
    table.add_column("GDP ($T)", justify="right", width=8)
    table.add_column("Military", justify="right", width=8)
    table.add_column("Tech", justify="right", width=6)
    table.add_column("Difficulty", width=12)

    codes = list(countries.keys())
    for i, code in enumerate(codes, 1):
        c = countries[code]
        # Difficulty based on starting position
        power = c.power_index()
        if power > 80:
            diff = "[green]Easy[/]"
        elif power > 50:
            diff = "[yellow]Medium[/]"
        elif power > 30:
            diff = "[red]Hard[/]"
        else:
            diff = "[bold red]Expert[/]"

        table.add_row(
            str(i),
            f"{get_flag(code)} {c.name}",
            f"{c.leader.name} ({c.leader.title})",
            f"${c.economy.gdp:.1f}T",
            f"{c.military.power:.0f}",
            f"{c.tech.level:.0f}",
            diff,
        )

    console.print(table)
    while True:
        try:
            choice = IntPrompt.ask(
                "\n[bold]Enter number[/]", default=1
            )
            if 1 <= choice <= len(codes):
                return codes[choice - 1]
            console.print("[red]Invalid choice.[/]")
        except (ValueError, KeyboardInterrupt):
            console.print("[red]Invalid input.[/]")


def show_dashboard(world: World):
    """Show the main game dashboard."""
    player = world.get_player()
    rankings = world.get_rankings()
    player_rank = next(i for i, (c, _) in enumerate(rankings, 1) if c == world.player_code)

    # Header
    console.print()
    header = (
        f"[bold white on blue]  {player.name}  [/]  "
        f"[bold]{world.date_str}[/]  |  Turn {world.turn}  |  "
        f"Rank #{player_rank} of {len(rankings)}"
    )
    console.print(header)
    console.print()

    # Leader info
    leader_info = (
        f"[bold]{player.leader.title} {player.leader.name}[/]\n"
        f"Approval: {stat_bar(player.leader.approval)}\n"
        f"Government: {player.government.title()}"
    )

    # Economy panel
    econ = player.economy
    econ_info = (
        f"GDP:         [bold]${econ.gdp:.2f}T[/]\n"
        f"Growth:      [{'green' if econ.gdp_growth > 0 else 'red'}]{econ.gdp_growth:+.1f}%[/]\n"
        f"Inflation:   [{'green' if econ.inflation < 5 else 'red'}]{econ.inflation:.1f}%[/]\n"
        f"Unemployment:[{'green' if econ.unemployment < 6 else 'red'}] {econ.unemployment:.1f}%[/]\n"
        f"Debt/GDP:    [{'green' if econ.debt_ratio < 80 else 'red'}]{econ.debt_ratio:.0f}%[/]\n"
        f"Trade Bal:   [{'green' if econ.trade_balance > 0 else 'red'}]{econ.trade_balance:+.2f}T[/]"
    )

    # Military panel
    mil = player.military
    nuke = "YES" if mil.nuclear else "No"
    deployed = ", ".join(mil.deployed_regions) if mil.deployed_regions else "None"
    mil_info = (
        f"Power:   {stat_bar(mil.power)}\n"
        f"Cyber:   {stat_bar(mil.cyber_capability)}\n"
        f"Nuclear: [{'bold red' if mil.nuclear else 'dim'}]{nuke}[/]\n"
        f"Deployed: {deployed}"
    )

    # Tech panel
    tech = player.tech
    tech_info = (
        f"Overall: {stat_bar(tech.level)}\n"
        f"AI:      {stat_bar(tech.ai_research)}\n"
        f"Space:   {stat_bar(tech.space)}\n"
        f"Energy:  {stat_bar(tech.clean_energy)}\n"
        f"Biotech: {stat_bar(tech.biotech)}\n"
        f"Chips:   {stat_bar(tech.semiconductors)}"
    )

    # Stability & Influence
    status_info = (
        f"Stability:  {stat_bar(player.stability)}\n"
        f"Influence:  {stat_bar(player.influence)}\n"
        f"Pop:        {player.population:.0f}M\n"
        f"Alliances:  {len(player.alliances)}\n"
        f"Sanctioning:{len(player.sanctions_on)} nations\n"
        f"Sanctioned: {len(player.sanctioned_by)} nations"
    )

    panels = [
        Panel(leader_info, title="[bold]Leader[/]", border_style="cyan", width=38),
        Panel(econ_info, title="[bold]Economy[/]", border_style="green", width=38),
        Panel(mil_info, title="[bold]Military[/]", border_style="red", width=38),
    ]
    console.print(Columns(panels, equal=True, expand=True))
    panels2 = [
        Panel(tech_info, title="[bold]Technology[/]", border_style="magenta", width=38),
        Panel(status_info, title="[bold]Status[/]", border_style="yellow", width=38),
    ]
    console.print(Columns(panels2, equal=True, expand=True))


def show_world_rankings(world: World):
    """Show world power rankings."""
    rankings = world.get_rankings()
    table = Table(title="[bold]World Power Rankings[/]", box=box.ROUNDED)
    table.add_column("#", width=3, style="bold")
    table.add_column("Nation", width=18)
    table.add_column("Power", justify="right", width=7)
    table.add_column("GDP", justify="right", width=8)
    table.add_column("Military", justify="right", width=8)
    table.add_column("Tech", justify="right", width=6)
    table.add_column("Stability", justify="right", width=9)
    table.add_column("Influence", justify="right", width=9)

    for i, (code, power) in enumerate(rankings, 1):
        c = world.countries[code]
        style = "bold white" if code == world.player_code else ""
        marker = " <<" if code == world.player_code else ""
        table.add_row(
            str(i),
            f"{get_flag(code)} {c.name}{marker}",
            f"{power:.0f}",
            f"${c.economy.gdp:.1f}T",
            f"{c.military.power:.0f}",
            f"{c.tech.level:.0f}",
            f"{c.stability:.0f}",
            f"{c.influence:.0f}",
            style=style,
        )

    console.print(table)


def show_relationships(world: World):
    """Show diplomatic relationships."""
    player = world.get_player()
    table = Table(title="[bold]Diplomatic Relations[/]", box=box.ROUNDED)
    table.add_column("Nation", width=20)
    table.add_column("Relation", justify="right", width=10)
    table.add_column("Status", width=15)
    table.add_column("Alliances", width=25)

    sorted_rels = sorted(
        player.relationships.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for code, value in sorted_rels:
        if code not in world.countries:
            continue
        c = world.countries[code]
        color = rel_color(value)
        if value >= 50:
            status = "[green]Friendly[/]"
        elif value >= 20:
            status = "[bright_green]Warm[/]"
        elif value >= -20:
            status = "[yellow]Neutral[/]"
        elif value >= -50:
            status = "[red]Tense[/]"
        else:
            status = "[bold red]Hostile[/]"

        sanctions = ""
        if code in player.sanctions_on:
            sanctions = " [red](sanctioning)[/]"
        if code in player.sanctioned_by:
            sanctions += " [red](sanctioned by)[/]"

        common_alliances = set(player.alliances) & set(c.alliances)
        alliance_str = ", ".join(common_alliances) if common_alliances else "-"

        table.add_row(
            f"{get_flag(code)} {c.name}",
            f"[{color}]{value:+.0f}[/]",
            f"{status}{sanctions}",
            alliance_str,
        )

    console.print(table)


def show_country_detail(world: World, code: str):
    """Show detailed info about a country."""
    c = world.countries[code]
    player = world.get_player()
    rel = player.relationships.get(code, 0)

    info = (
        f"[bold]{c.name}[/] ({c.government.title()})\n"
        f"Leader: {c.leader.title} {c.leader.name}\n"
        f"Traits: {', '.join(c.leader.traits)}\n"
        f"Region: {c.region} | Pop: {c.population:.0f}M\n\n"
        f"[bold]Economy[/]\n"
        f"  GDP: ${c.economy.gdp:.2f}T | Growth: {c.economy.gdp_growth:+.1f}%\n"
        f"  Inflation: {c.economy.inflation:.1f}% | Unemployment: {c.economy.unemployment:.1f}%\n\n"
        f"[bold]Military[/]\n"
        f"  Power: {c.military.power:.0f} | Cyber: {c.military.cyber_capability:.0f}\n"
        f"  Nuclear: {'Yes' if c.military.nuclear else 'No'}\n\n"
        f"[bold]Technology[/]: {c.tech.level:.0f}\n"
        f"  AI: {c.tech.ai_research:.0f} | Space: {c.tech.space:.0f} | "
        f"Energy: {c.tech.clean_energy:.0f}\n"
        f"  Biotech: {c.tech.biotech:.0f} | Chips: {c.tech.semiconductors:.0f}\n\n"
        f"[bold]Relations with you[/]: [{rel_color(rel)}]{rel:+.0f}[/]\n"
        f"Stability: {c.stability:.0f} | Influence: {c.influence:.0f}\n"
        f"Alliances: {', '.join(c.alliances) if c.alliances else 'None'}\n"
        f"Traits: {', '.join(c.traits)}"
    )
    console.print(Panel(info, title=f"{get_flag(code)} {c.name}", border_style="cyan"))


def show_news(events: list[dict], world: World):
    """Show news headlines from events."""
    if not events:
        console.print("[dim]A quiet month on the world stage.[/]")
        return

    console.print(f"\n[bold white on red]  WORLD NEWS - {world.date_str}  [/]\n")
    for event in events:
        if "country_code" in event:
            code = event["country_code"]
            flag = get_flag(code)
            is_player = code == world.player_code
            style = "bold yellow" if is_player else ""
            marker = " [bold yellow](!)[/]" if is_player else ""
            console.print(f"  {flag} [bold]{event['headline']}[/]{marker}", style=style)
        else:
            affected = event.get("affected", [])
            tags = ", ".join(event.get("tags", []))
            console.print(f"  [bold]{event['headline']}[/]  [dim]({tags})[/]")
            if affected:
                console.print(f"    [dim]Affected: {', '.join(affected[:6])}{'...' if len(affected) > 6 else ''}[/]")


def show_action_menu(world: World, action_points: int) -> tuple[str, dict]:
    """Show action menu and get player choice. Returns (action_id, params)."""
    player = world.get_player()
    console.print(f"\n[bold cyan]Action Points remaining: {action_points}[/]\n")

    # Show categories
    categories = list(ACTION_CATEGORIES.keys())
    console.print("[bold]Categories:[/]")
    for i, cat in enumerate(categories, 1):
        console.print(f"  {i}. {cat}")
    console.print(f"  {len(categories) + 1}. [dim]View Info (free)[/]")
    console.print(f"  {len(categories) + 2}. [dim]End Turn[/]")

    try:
        cat_choice = IntPrompt.ask("\n[bold]Category[/]", default=len(categories) + 2)
    except KeyboardInterrupt:
        return ("end_turn", {})

    if cat_choice == len(categories) + 2:
        return ("end_turn", {})

    if cat_choice == len(categories) + 1:
        return _info_menu(world)

    if cat_choice < 1 or cat_choice > len(categories):
        console.print("[red]Invalid choice.[/]")
        return ("invalid", {})

    category = categories[cat_choice - 1]
    actions = ACTION_CATEGORIES[category]

    console.print(f"\n[bold]{category} Actions:[/]")
    for i, action in enumerate(actions, 1):
        cost_str = f"[dim]({action['cost']} AP)[/]"
        available = action["cost"] <= action_points
        style = "" if available else "dim"
        console.print(f"  [{style}]{i}. {action['name']} {cost_str} - {action['desc']}[/]")
    console.print(f"  0. [dim]Back[/]")

    try:
        act_choice = IntPrompt.ask("[bold]Action[/]", default=0)
    except KeyboardInterrupt:
        return ("invalid", {})

    if act_choice == 0:
        return ("invalid", {})
    if act_choice < 1 or act_choice > len(actions):
        console.print("[red]Invalid choice.[/]")
        return ("invalid", {})

    action = actions[act_choice - 1]
    if action["cost"] > action_points:
        console.print("[red]Not enough action points![/]")
        return ("invalid", {})

    params = {"cost": action["cost"]}

    # Get target country if needed
    if action.get("needs_target"):
        target = _select_country(world, "Select target nation")
        if target is None:
            return ("invalid", {})
        params["target_code"] = target

    # Get region if needed
    if action.get("needs_region"):
        region = _select_region(world, player)
        if region is None:
            return ("invalid", {})
        params["region"] = region

    # Get tech field if needed
    if action.get("needs_field"):
        field = _select_tech_field()
        if field is None:
            return ("invalid", {})
        params["field"] = field

    return (action["id"], params)


def _info_menu(world: World) -> tuple[str, dict]:
    """Free information viewing."""
    console.print("\n[bold]View Info:[/]")
    console.print("  1. World Rankings")
    console.print("  2. Diplomatic Relations")
    console.print("  3. Inspect a Nation")
    console.print("  4. Recent News History")
    console.print("  0. Back")

    try:
        choice = IntPrompt.ask("[bold]Choice[/]", default=0)
    except KeyboardInterrupt:
        return ("invalid", {})

    if choice == 1:
        show_world_rankings(world)
    elif choice == 2:
        show_relationships(world)
    elif choice == 3:
        code = _select_country(world, "Select nation to inspect")
        if code:
            show_country_detail(world, code)
    elif choice == 4:
        _show_news_history(world)

    return ("invalid", {})  # free action, loop back


def _select_country(world: World, prompt: str) -> str | None:
    """Let player select a country."""
    codes = [c for c in world.countries if c != world.player_code]
    console.print(f"\n[bold]{prompt}:[/]")
    for i, code in enumerate(codes, 1):
        c = world.countries[code]
        rel = world.get_player().relationships.get(code, 0)
        color = rel_color(rel)
        console.print(f"  {i:2}. {get_flag(code)} {c.name:20s} [{color}]({rel:+.0f})[/]")
    console.print("   0. Cancel")

    try:
        choice = IntPrompt.ask("[bold]Nation[/]", default=0)
    except KeyboardInterrupt:
        return None
    if choice == 0 or choice < 1 or choice > len(codes):
        return None
    return codes[choice - 1]


def _select_region(world: World, player: Country) -> str | None:
    """Let player select a region."""
    regions = sorted(set(c.region for c in world.countries.values()))
    console.print("\n[bold]Select region:[/]")
    for i, region in enumerate(regions, 1):
        deployed = " [yellow](deployed)[/]" if region in player.military.deployed_regions else ""
        console.print(f"  {i}. {region}{deployed}")
    console.print("  0. Cancel")

    try:
        choice = IntPrompt.ask("[bold]Region[/]", default=0)
    except KeyboardInterrupt:
        return None
    if choice == 0 or choice < 1 or choice > len(regions):
        return None
    return regions[choice - 1]


def _select_tech_field() -> str | None:
    """Let player select a tech research field."""
    fields = list(TECH_FIELDS.items())
    console.print("\n[bold]Select research field:[/]")
    for i, (key, (_, name)) in enumerate(fields, 1):
        console.print(f"  {i}. {name}")
    console.print("  0. Cancel")

    try:
        choice = IntPrompt.ask("[bold]Field[/]", default=0)
    except KeyboardInterrupt:
        return None
    if choice == 0 or choice < 1 or choice > len(fields):
        return None
    return fields[choice - 1][0]


def _show_news_history(world: World):
    """Show recent news history."""
    if not world.news_log:
        console.print("[dim]No news recorded yet.[/]")
        return
    console.print("\n[bold]Recent News History:[/]")
    for entry in world.news_log[-15:]:
        console.print(f"  [dim]{entry.get('date', '?')}[/] {entry.get('headline', '?')}")


def show_victory(world: World, victory_type: str):
    """Show victory screen."""
    player = world.get_player()
    messages = {
        "economic": f"{player.name} has achieved economic supremacy!\nYour GDP dominates the global economy.",
        "military": f"{player.name}'s military might is unchallenged!\nThe world trembles before your armed forces.",
        "diplomatic": f"{player.name} leads a global coalition!\nYour diplomatic network spans the world.",
        "technological": f"{player.name} leads the technological revolution!\nYou've achieved breakthroughs in every field.",
        "domination": f"{player.name} stands as the undisputed world power!\nNo nation comes close to your combined strength.",
    }
    msg = messages.get(victory_type, "You win!")
    console.print(Panel(
        f"[bold green]{msg}[/]\n\nTurns: {world.turn} | Year: {world.date_str}",
        title="[bold yellow]VICTORY![/]",
        border_style="yellow",
        box=box.DOUBLE,
    ))


def show_defeat(message: str):
    """Show defeat screen."""
    console.print(Panel(
        f"[bold red]{message}[/]",
        title="[bold red]DEFEAT[/]",
        border_style="red",
        box=box.DOUBLE,
    ))


def show_ai_summary(world: World, ai_actions: dict[str, list[str]]):
    """Show a brief summary of what AI nations did."""
    console.print("\n[bold dim]--- Other Nations' Activities ---[/]")
    # Only show noteworthy actions (not all)
    interesting = []
    for code, actions in ai_actions.items():
        if code == world.player_code:
            continue
        c = world.countries[code]
        rel = world.get_player().relationships.get(code, 0)
        # Show actions from important/rival/allied nations
        if abs(rel) > 30 or c.power_index() > 50:
            for action_msg in actions[:1]:  # just first action
                if any(word in action_msg.lower() for word in
                       ["sanction", "alliance", "deploy", "cyber", "tariff", "denounce"]):
                    interesting.append(f"  {get_flag(code)} {c.name}: {action_msg}")

    if interesting:
        for line in interesting[:5]:
            console.print(line)
    else:
        console.print("  [dim]No major moves by other nations this turn.[/]")


def confirm(prompt: str) -> bool:
    return Prompt.ask(prompt, choices=["y", "n"], default="y") == "y"
