from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_upgrade_card import InstantUpgradeCard


class Apotheosis(Card):
    def __init__(self):
        super().__init__(
            card_id = "apotheosis",
            name = "Apotheosis",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 2,
            target_type = TargetType.SELF,
            properties = CardProperties(innate=True, exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import can_upgrade

        ally = context.source
        # Every pile, the exhaust pile too, as the game's PlayerCombatState
        # .AllCards - and only what can be upgraded (no Status, no Curse).
        everything = [ref
                      for pile in (ally.hand, ally.draw_pile, ally.discard_pile,
                                   ally.exhaust_pile)
                      for ref in pile if can_upgrade(ref)]
        return [InstantUpgradeCard(
            source=ally, target=ally, card_refs=everything)]
