from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class NeowsFury(Card):
    DAMAGE = 10
    COUNT = 2

    def __init__(self):
        super().__init__(
            card_id = "neows_fury",
            name = "Neow's Fury",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        ally = context.source

        # "Up to 2", asked one at a time; fewer is fine when the pile is short.
        def ask(left):
            if left <= 0 or not ally.discard_pile:
                return

            def take(chosen):
                ask(left - 1)
                return [InstantMoveCard(
                    source=ally, target=ally, card_ids=[chosen],
                    from_pile=InstantMoveCard.DISCARD,
                    to_pile=InstantMoveCard.HAND)]

            context.ask(ally,
                        f"Take a card from your Discard Pile ({left} left)",
                        lambda: list(ally.discard_pile), take)

        ask(self.COUNT)
        return [InstantDamage(
            source=ally, target=context.target, amount=self.DAMAGE)]
