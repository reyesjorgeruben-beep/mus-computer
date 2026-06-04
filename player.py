from typing import List
from team import Team
from player_base import PlayerBase
from game_context import GameContext


class HumanPlayer(PlayerBase):
    def vote_mus(self) -> bool:
        ans = input(f"{self.name}: ¿Mus? (y/n): ").strip().lower()
        return ans != "n"

    def choose_discards(self) -> List[int]:
        while True:
            raw = input(
                f"{self.name} (Team {self.team.name}), hand: {self.cards}\n"
                "Indices to discard (1-based, comma-separated): "
            )
            try:
                indices = [int(i.strip()) - 1 for i in raw.split(",") if i.strip()]
                if not indices:
                    print("Enter at least one index.")
                    continue
                if all(0 <= i < len(self.cards) for i in indices):
                    return indices
                print(f"Indices must be between 1 and {len(self.cards)}.")
            except ValueError:
                print("Use only numbers and commas.")

    def wager_action(self, context: GameContext) -> int:
        return int(input(
            f"{self.name} (Team {self.team.name}): bet={context.current_bet}, "
            f"prev={context.previous_bet}. Raise? (0=call, neg=fold): "
        ))


# Alias for backward compatibility
Player = HumanPlayer
