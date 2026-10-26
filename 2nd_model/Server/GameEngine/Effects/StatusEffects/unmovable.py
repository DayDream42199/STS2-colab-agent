from ._status_effect import StatusEffect
from ...Units.Enemies._enemy import Enemy


class Unmovable(StatusEffect):
    """Block from your cards is doubled, until this turn has seen `amount`
    Block gains from other plays. The game's UnmovablePower:

    - only Block from a card or a move: a power's own Block (Toric
      Toughness's later turns, Plating) is never doubled;
    - only your own cards' Block, but whoever it goes to - a teammate's
      card giving you Block is not doubled, your card giving them Block is;
    - every gain in one play is doubled (Second Wind, Stack), because the
      count is of gains from other plays this turn;
    - stacks: Unmovable 2 doubles until two such gains are on record;
    - never for an enemy."""

    def __init__(self, source, target, amount):
        super().__init__("unmovable")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def modify_card_block(self, amount, target, play_id):
        if isinstance(target, Enemy):
            return amount
        others = sum(1 for gained in target.card_blocks if gained != play_id)
        return amount if others >= self.amount else amount * 2
