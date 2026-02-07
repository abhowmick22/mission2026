"""Core game engine - manages the game loop."""

from __future__ import annotations

from game.world import World
from game.events import EventEngine
from game.ai import AIPlayer
from game.actions import execute_action
from game.save_manager import auto_save, save_game
from game import ui


class GameEngine:
    def __init__(self):
        self.world = World()
        self.event_engine = EventEngine()
        self.ai_players: dict[str, AIPlayer] = {}
        self.action_points_per_turn = 4

    def new_game(self):
        """Start a new game."""
        ui.show_title_screen()
        self.world.load_countries()
        code = ui.show_country_select(self.world.countries)
        self.world.player_code = code

        # Create AI players for all non-player countries
        for c_code, country in self.world.countries.items():
            if c_code != code:
                self.ai_players[c_code] = AIPlayer(country)

        player = self.world.get_player()
        ui.console.print(f"\n[bold green]You are now leading {player.name}![/]")
        ui.console.print(f"[dim]Leader: {player.leader.title} {player.leader.name}[/]")
        ui.console.print(f"[dim]Government: {player.government.title()}[/]")
        ui.console.print(f"[dim]Starting GDP: ${player.economy.gdp:.1f}T[/]")
        ui.console.print()

        auto_save(self.world)
        self.game_loop()

    def load_game(self, world: World):
        """Resume a saved game."""
        self.world = world
        for c_code, country in self.world.countries.items():
            if c_code != self.world.player_code:
                self.ai_players[c_code] = AIPlayer(country)
        self.game_loop()

    def game_loop(self):
        """Main game loop."""
        while not self.world.game_over:
            try:
                self._play_turn()
            except KeyboardInterrupt:
                ui.console.print("\n[yellow]Game paused.[/]")
                if ui.confirm("Save and quit?"):
                    filename = save_game(self.world)
                    ui.console.print(f"[green]Game saved: {filename}[/]")
                    return
                continue

    def _play_turn(self):
        """Execute one turn of the game."""
        # 1. Show dashboard
        ui.show_dashboard(self.world)

        # 2. Player actions
        action_points = self.action_points_per_turn
        while action_points > 0:
            action_id, params = ui.show_action_menu(self.world, action_points)

            if action_id == "end_turn":
                break
            if action_id == "invalid":
                continue

            # Execute the action
            cost = params.pop("cost", 1)
            result = execute_action(
                self.world,
                self.world.get_player(),
                action_id,
                target_code=params.get("target_code"),
                region=params.get("region"),
                field=params.get("field"),
            )
            ui.console.print(f"\n[bold]>> {result}[/]\n")
            action_points -= cost

        # 3. AI turns
        ui.console.print("\n[dim]Processing other nations...[/]")
        ai_actions = {}
        for code, ai in self.ai_players.items():
            results = ai.take_turn(self.world, action_points=3)
            ai_actions[code] = results

        # Show AI summary
        ui.show_ai_summary(self.world, ai_actions)

        # 4. Events
        events = self.event_engine.process_turn(self.world)
        ui.show_news(events, self.world)

        # Store news in log
        for event in events:
            self.world.news_log.append({
                "date": self.world.date_str,
                "headline": event.get("headline", event.get("title", "?")),
                "turn": self.world.turn,
            })

        # 5. Natural world changes
        self.world.apply_natural_changes()

        # 6. Advance time
        self.world.advance_date()

        # 7. Check victory/defeat
        victory = self.world.check_victory()
        if victory:
            self.world.game_over = True
            self.world.victory_type = victory
            ui.show_victory(self.world, victory)
            save_game(self.world, slot=f"victory_{self.world.player_code}")
            return

        defeat = self.world.check_defeat()
        if defeat:
            self.world.game_over = True
            ui.show_defeat(defeat)
            return

        # 8. Auto-save
        auto_save(self.world)

        # 9. Turn summary
        ui.console.print(f"\n[dim]--- End of {self.world.date_str} ---[/]")
        ui.console.print("[dim]Press Enter to continue...[/]")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
