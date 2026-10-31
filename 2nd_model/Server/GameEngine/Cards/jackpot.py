from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_add_card import InstantAddCard
from ._card_ref import CardRef


class Jackpot(Card):
    DAMAGE = 25
    COUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "jackpot",
            name = "Jackpot",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.RARE,
            cost = 3,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import create_card, generatable_card_ids

        effects = [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
        # "0 Energy cards" are cards printed at 0, not cards made free: the
        # game's Jackpot picks among the cards whose cost is 0 (never X), and
        # upgraded it upgrades them.
        pool = [card_id for card_id in generatable_card_ids(
                    card_class=CardClass.IRONCLAD, solo=context.solo)
                if create_card(card_id).cost == 0]
        for _ in range(self.COUNT):
            if not pool:
                break
            picked = context.rngs.card_generation.choice(pool)
            effects.append(InstantAddCard(
                source=context.source, target=context.source,
                card_id=CardRef(picked, upgraded=self.upgraded),
                pile=InstantAddCard.HAND))
        return effects
