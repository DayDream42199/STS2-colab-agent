from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Unrelenting(Card):
    DAMAGE = 14

    def __init__(self):
        super().__init__(
            card_id = "unrelenting",
            name = "Unrelenting",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # A plain counter on the ally, spent by Combat when the next Attack is
        # played. No deadline - the card does not say "this turn".
        context.source.free_next_attack += 1
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
