from typing import List
from mus_computer.game.team import Team
from mus_computer.game.player_base import PlayerBase
from mus_computer.bots.strategies.actions import MusAction, WagerAction, legal_wager_actions


class HumanPlayer(PlayerBase):
    def vote_mus(self, global_context=None, player_context=None):
        ans = input(f"{self.name}: ¿Mus? (y/n): ").strip().lower()
        return MusAction.CORTA if ans == "n" else MusAction.MUS

    def choose_discards(self, global_context=None, player_context=None):
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

    def wager_action(self, global_context, player_context=None):
        while True:
            wager = global_context.wager
            has_offer = wager is not None and wager.offering_team is not None
            current = wager.current_total if wager is not None else 0
            accepted = wager.previous_accepted_total if wager is not None else 0
            if wager is not None and wager.ordago_offered:
                options = "0=quiero (accept ordago), -1=fold"
            elif has_offer:
                options = (f"2-5=add to current offer, 0=quiero (accept {current}), "
                           "-1=fold, ordago")
            else:
                options = "2-5=opening total, 0=pass, ordago"
            raw = input(
                f"{global_context.phase_name} | {self.name} (Team {self.team.name}): "
                f"current offer={'ordago' if wager and wager.ordago_offered else current if has_offer else 'none'}, "
                f"previously accepted={accepted}. {options}: "
            ).strip().lower()
            actions = {"0": WagerAction.MATCH_OR_PASS, "-1": WagerAction.FOLD,
                       "ordago": WagerAction.ORDAGO,
                       **{str(n): WagerAction[f"RAISE_{n}"] for n in range(2,6)}}
            action = actions.get(raw)
            if action in legal_wager_actions(global_context.wager):
                return action
            print("Choose a legal action for this wager.")


# Alias for backward compatibility
Player = HumanPlayer
