from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Panache(StatusEffect):
    """Every 5th card you play in a turn, deal `amount` damage to every enemy.

    As the game's PanachePower: the count starts when Panache is played (the
    Panache card itself is not one of the five), goes back to 5 at the end of
    each turn, and the damage is unpowered - no Strength, no Vulnerable. Each
    Panache counts on its own, so `counts` holds [damage, cards left] per
    copy played."""

    EVERY = 5

    def __init__(self, source, target, amount):
        super().__init__("panache")
        self.source = source
        self.target = target
        self.amount = amount
        # The play that applied it is still finishing: its CARD_PLAYED is
        # the Panache card's own, which does not count.
        self.counts = [[amount, self.EVERY, True]]

    def absorb(self, other):
        self.counts.extend(other.counts)
        self.amount = sum(damage for damage, _, _ in self.counts)

    def on_owner_turn_end(self):
        for count in self.counts:
            count[1] = self.EVERY

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        effects = []
        for count in self.counts:
            if count[2]:
                count[2] = False
                continue
            count[1] -= 1
            if count[1] > 0:
                continue
            count[1] = self.EVERY
            effects += [
                InstantDamage(source=context.source, target=enemy,
                              amount=count[0], is_attack=False)
                for enemy in context.all_enemies
                if enemy.is_alive()
            ]
        return effects or None
