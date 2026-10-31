from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class Catastrophe(Card):
    COUNT = 2

    def __init__(self):
        super().__init__(
            card_id = "catastrophe",
            name = "Catastrophe",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card

        # One at a time, as the game's Catastrophe: each pick is made from the
        # pile the last one left, and a playable card is taken over an
        # Unplayable one whenever there is one.
        for _ in range(self.COUNT):
            draw = list(context.source.draw_pile)
            if not draw:
                return
            playable = [c for c in draw if create_card(c).properties.playable]
            yield InstantPlayCard(
                source=context.source, target=context.source,
                card_id=context.rngs.shuffle.choice(playable or draw),
                from_pile=InstantPlayCard.DRAW)
