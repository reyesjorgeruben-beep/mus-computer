from enum import Enum
from functools import total_ordering

@total_ordering
class Card(str, Enum):
    A = 'A'
    _4 = '4'
    _5 = '5'
    _6 = '6'
    _7 = '7'
    S = 'S'
    C = 'C'
    R = 'R'

    @property
    def strongness(self) -> int:
        order = {
            'A': 1,
            '4': 4, '5': 5, '6': 6, '7': 7,
            'S':10, 'C': 11, 'R':12
        }
        return order[self.value]
    
    @property
    def juego_value(self) -> int:
        juego_order = {
            'A': 1,
            '4': 4, '5': 5, '6': 6, '7': 7,
            'S': 10, 'C': 10, 'R': 10
        }
        return juego_order[self.value]
    
    def __hash__(self):
        return hash(self.value)

    def __lt__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        return self.strongness < other.strongness

    def __eq__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        return self.strongness == other.strongness
    
    def __gt__(self, other):
        if not isinstance(other, Card): return NotImplemented
        return self.strongness > other.strongness

    def __le__(self, other):
        if not isinstance(other, Card): return NotImplemented
        return self.strongness <= other.strongness

    def __ge__(self, other):
        if not isinstance(other, Card): return NotImplemented
        return self.strongness >= other.strongness