from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class Jackpot(Card):
    DAMAGE = 25
    COUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "jackpot",
            name = "Jackpot",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import generatable_card_ids

        effects = [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
        pool = generatable_card_ids(card_class=CardClass.IRONCLAD)
        # "0 Energy cards" means cards made free, not cards that already cost
        # nothing - the reference picks from the whole pool and zeroes the cost.
        for _ in range(self.COUNT):
            if not pool:
                break
            picked = context.rng.choice(pool)
            context.source.free_this_turn.append(picked)
            effects.append(InstantAddCard(
                source=context.source, target=context.source,
                card_id=picked, pile=InstantAddCard.HAND))
        return effects
