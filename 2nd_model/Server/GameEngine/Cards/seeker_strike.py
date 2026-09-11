from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class SeekerStrike(Card):
    DAMAGE = 9
    OFFER = 3

    def __init__(self):
        super().__init__(
            card_id = "seeker_strike",
            name = "Seeker Strike",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        ally = context.source
        draw = list(ally.draw_pile)
        if draw:
            offer = context.rng.sample(draw, min(self.OFFER, len(draw)))

            def take(chosen):
                return [InstantMoveCard(
                    source=ally, target=ally, card_ids=[chosen],
                    from_pile=InstantMoveCard.DRAW,
                    to_pile=InstantMoveCard.HAND)]

            context.ask(ally, "Choose a card from your Draw Pile", offer, take)
        return [InstantDamage(
            source=ally, target=context.target, amount=self.DAMAGE)]
