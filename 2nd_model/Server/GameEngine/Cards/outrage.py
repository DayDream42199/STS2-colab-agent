from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class Outrage(Card):
    DAMAGE = 9

    def __init__(self):
        super().__init__(
            card_id = "outrage",
            name = "Outrage",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Everyone's discard pile, the caster included - it is a co-op curse.
        effects = [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
        for ally in context.all_allies:
            if ally.is_alive():
                effects.append(InstantAddCard(
                    source=context.source, target=ally, card_id=self.card_id))
        return effects
