from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class SecretWeapon(Card):
    def __init__(self):
        super().__init__(
            card_id = "secret_weapon",
            name = "Secret Weapon",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card
        attacks = [c for c in context.source.draw_pile
                   if create_card(c).card_type is CardType.ATTACK]
        picked = [context.rng.choice(attacks)] if attacks else []
        if not picked:
            return []
        return [InstantMoveCard(
            source=context.source, target=context.source, card_ids=picked,
            from_pile=InstantMoveCard.DRAW, to_pile=InstantMoveCard.HAND,
        )]
