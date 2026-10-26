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
            rarity = CardRarity.RARE,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card
        ally = context.source

        # The player picks, as the game's CardSelectCmd.FromCombatPile does -
        # it is not random. Read when the question is put.
        def attacks():
            return [c for c in ally.draw_pile
                    if create_card(c).card_type is CardType.ATTACK]

        if not attacks():
            return []

        def take(chosen):
            return [InstantMoveCard(
                source=ally, target=ally, card_ids=[chosen],
                from_pile=InstantMoveCard.DRAW, to_pile=InstantMoveCard.HAND)]

        context.ask(ally, "Put an Attack from your Draw Pile into your Hand", attacks, take)
        return []
