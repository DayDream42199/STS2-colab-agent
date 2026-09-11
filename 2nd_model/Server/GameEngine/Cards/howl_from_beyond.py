from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.howl_echo import HowlEcho


class HowlFromBeyond(Card):
    DAMAGE = 18

    def __init__(self):
        super().__init__(
            card_id = "howl_from_beyond",
            name = "Howl from Beyond",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        effects = [
            InstantDamage(
                source=context.source, target=enemy, amount=self.DAMAGE)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
        # The echo arms itself even on a whiff: the card only replays from the
        # exhaust pile, and something else has to put it there first.
        effects.append(HowlEcho(
            source=context.source, target=context.source, amount=1))
        return effects
