#!/usr/bin/env python3
"""World Order - A Geopolitics Strategy Game.

Lead your nation through the complexities of modern geopolitics,
economics, technology, and military strategy.

Usage:
    python main.py          # Start menu
    python main.py --new    # Start new game directly
"""

import sys

from rich.console import Console
from rich.prompt import IntPrompt
from rich import box
from rich.panel import Panel

from game.engine import GameEngine
from game.save_manager import list_saves, load_game

console = Console()


def show_main_menu():
    title = (
        "[bold white]W O R L D   O R D E R[/]\n"
        "[dim]A Geopolitics Strategy Game[/]\n\n"
        "[dim]Navigate diplomacy, economics, military power,[/]\n"
        "[dim]and technology in an interconnected world.[/]\n\n"
        "[dim]Each turn = 1 month. Play a few turns per session.[/]\n"
        "[dim]Your game auto-saves after every turn.[/]"
    )
    console.print(Panel(title, border_style="blue", box=box.DOUBLE))
    console.print()
    console.print("  1. [bold]New Game[/]")
    console.print("  2. [bold]Continue[/] (load save)")
    console.print("  3. [bold]Quit[/]")
    console.print()

    try:
        return IntPrompt.ask("[bold]Choice[/]", default=1)
    except (KeyboardInterrupt, EOFError):
        return 3


def show_load_menu() -> str | None:
    saves = list_saves()
    if not saves:
        console.print("[yellow]No save files found.[/]")
        return None

    console.print("\n[bold]Saved Games:[/]\n")
    for i, save in enumerate(saves, 1):
        console.print(
            f"  {i}. [bold]{save['country']}[/] ({save['player']}) - "
            f"Turn {save['turn']} - {save['modified']}"
        )
    console.print("  0. Back")
    console.print()

    try:
        choice = IntPrompt.ask("[bold]Load[/]", default=0)
    except (KeyboardInterrupt, EOFError):
        return None

    if choice == 0 or choice < 1 or choice > len(saves):
        return None
    return saves[choice - 1]["filename"]


def main():
    # Quick start option
    if "--new" in sys.argv:
        engine = GameEngine()
        engine.new_game()
        return

    while True:
        choice = show_main_menu()

        if choice == 1:
            engine = GameEngine()
            engine.new_game()
        elif choice == 2:
            filename = show_load_menu()
            if filename:
                world = load_game(filename)
                engine = GameEngine()
                engine.load_game(world)
        elif choice == 3:
            console.print("[dim]Goodbye.[/]")
            break
        else:
            console.print("[red]Invalid choice.[/]")


if __name__ == "__main__":
    main()
