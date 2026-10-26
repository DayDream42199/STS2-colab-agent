from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class SecretTechnique(Card):
    def __init__(self):
        super().__init__(
            card_id = "secret_technique",
            name = "Secret Technique",
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
        def skills():
            return [c for c in ally.draw_pile
                    if create_card(c).card_type is CardType.SKILL]

        if not skills():
            return []

        def take(chosen):
            return [InstantMoveCard(
                source=ally, target=ally, card_ids=[chosen],
                from_pile=InstantMoveCard.DRAW, to_pile=InstantMoveCard.HAND)]

        context.ask(ally, "Put a Skill from your Draw Pile into your Hand", skills, take)
        return []
