from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw


class HuddleUp(Card):
    MULTIPLAYER_ONLY = True         # a co-op card: not made at random solo
    CARDS = 2

    def __init__(self):
        super().__init__(
            card_id = "huddle_up",
            name = "Huddle Up",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALL_ALLIES,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Affects the whole party including the caster, so unlike the
        # "another player" cards there is no self-target guard here.
        return [
            InstantDraw(source=context.source, target=ally,
                        amount=self.CARDS, rng=context.rngs.shuffle)
            for ally in context.all_allies
            if ally.is_alive()
        ]
