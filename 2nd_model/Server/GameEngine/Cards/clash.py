from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Clash(Card):
    DAMAGE = 14

    def __init__(self):
        super().__init__(
            card_id = "clash",
            name = "Clash",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ENEMY
        )

    def playable_now(self, ally):
        from ..Registry.card_registry import create_card

        # Clash is still in hand when this is asked, and it is an Attack, so it
        # never rules itself out. A Curse or a Status held does.
        return all(create_card(card_id).card_type is CardType.ATTACK
                   for card_id in ally.hand)

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
