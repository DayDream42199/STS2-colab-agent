from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.vulnerable import Vulnerable
from ..Effects.StatusEffects.strength import Strength


class Dominate(Card):
    VULNERABLE = 1

    def __init__(self):
        super().__init__(
            card_id = "dominate",
            name = "Dominate",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # The Strength counts the Vulnerable this card is about to add, so it
        # is read after the new stack rather than before.
        existing = context.target.get_status("vulnerable")
        stacks = (existing.amount if existing else 0) + self.VULNERABLE
        return [
            Vulnerable(
                source=context.source, target=context.target, amount=self.VULNERABLE),
            Strength(
                source=context.source, target=context.source, amount=stacks),
        ]
