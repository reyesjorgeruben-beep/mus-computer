from team import Team
from logging import Logger

logger = Logger("Player")

class Player():
    cards = []
    
    def __init__(self, name: str, team: Team):
        self.name = name
        self.team = team
        
    def receive_cards(self, cards: list):
        self.cards.extend(cards)
        logger.info(f"{self.name} received cards: {cards}. Current hand: {self.cards}")
        
    def throw_card(self, index: int):
        if 0 <= index < len(self.cards):
            card = self.cards.pop(index)
            logger.info(f"{self.name} threw card: {card}")
            return card
        else:
            raise ValueError(f"Player {self.name} does not have card at index {index}.")
    def throw_cards(self):
        self.cards = []
                
    def wager_action(self, current_bet: int, previous_bet: int)-> int:
        """How much do you want to raise the bet? 
        (Enter 0 to call, or a negative number to fold)
        """
        raise_amount = int(input(
            f"""{self.name} (Team {self.team.name}), current bet is {current_bet}.
            You have previously bet {previous_bet}. 
            How much do you want to raise?
            (Enter 0 to call, or a negative number to fold)"""))
        return raise_amount
    
    def mus_action(self) -> int:
        while True:
            card_indices_to_throw = input(
                f"{self.name} (Team {self.team.name}), your hand is {self.cards}. \n"
                "Enter the indices (starting from 1) separated by commas: "
            )

            try:
                indices = [int(i.strip()) - 1 for i in card_indices_to_throw.split(",") if i.strip()]
                
                if not indices:
                    logger.error("Please enter at least one index.")
                    continue
                
                if all(0 <= i < len(self.cards) for i in indices):
                    break # Success! Exit the loop.
                else:
                    logger.error(f"Error: Indices must be between 1 and {len(self.cards)}.")
                    
            except ValueError:
                logger.error("Error: Please use only numbers and commas.")

        for index in sorted(indices, reverse=True):
            self.throw_card(index)
        return len(indices)