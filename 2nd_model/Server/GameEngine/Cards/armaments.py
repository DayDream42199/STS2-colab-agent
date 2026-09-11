from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_ref import is_upgraded
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_upgrade_card import InstantUpgradeCard


class Armaments(Card):
    BLOCK = 5

    def __init__(self):
        super().__init__(
            card_id = "armaments",
            name = "Armaments",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        ally = context.source
        effects = [InstantBlock(source=ally, target=ally, amount=self.BLOCK)]
        candidates = [ref for ref in ally.hand if not is_upgraded(ref)]
        if not candidates:
            return effects
        if self.upgraded:
            # Upgraded it takes the whole hand, so there is nothing to ask.
            effects.append(InstantUpgradeCard(
                source=ally, target=ally, card_refs=candidates))
            return effects

        def upgrade(chosen):
            return [InstantUpgradeCard(
                source=ally, target=ally, card_refs=[chosen])]

        context.ask(ally, "Upgrade a card in your Hand", candidates, upgrade)
        return effects
