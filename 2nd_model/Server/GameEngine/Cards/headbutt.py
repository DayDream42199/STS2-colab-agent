from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class Headbutt(Card):
    DAMAGE = 9

    def __init__(self):
        super().__init__(
            card_id = "headbutt",
            name = "Headbutt",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        ally = context.source
        if ally.discard_pile:
            def stash(chosen):
                return [InstantMoveCard(
                    source=ally, target=ally, card_ids=[chosen],
                    from_pile=InstantMoveCard.DISCARD,
                    to_pile=InstantMoveCard.DRAW)]

            context.ask(ally, "Put a card from your Discard Pile on top of "
                              "your Draw Pile",
                        lambda: list(ally.discard_pile), stash)
        return [InstantDamage(
            source=ally, target=context.target, amount=self.DAMAGE)]
