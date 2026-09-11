from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class DualWield(Card):
    COPIES = 1

    def __init__(self):
        super().__init__(
            card_id = "dual_wield",
            name = "Dual Wield",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        from ..Registry.card_registry import create_card

        ally = context.source
        # Dual Wield is out of hand by now, so it cannot copy itself.
        eligible = [ref for ref in ally.hand
                    if create_card(ref).card_type in (CardType.ATTACK,
                                                      CardType.POWER)]
        if not eligible:
            return []
        copies = self.COPIES

        def copy(chosen):
            # Copied from the ref, so an upgraded card is copied upgraded.
            return [InstantAddCard(
                source=ally, target=ally, card_id=chosen,
                pile=InstantAddCard.HAND, amount=copies)]

        context.ask(ally, "Choose an Attack or Power to copy", eligible, copy)
        return []
