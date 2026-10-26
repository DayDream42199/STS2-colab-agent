from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.StatusEffects.no_energy_gain import NoEnergyGain


class ExpectAFight(Card):
    """Gain 1 Energy for each Attack in your Hand. You cannot gain additional
    Energy this turn. (The beta version gave Block per Strength; the game
    replaced it.)"""

    ENERGY_PER_ATTACK = 1

    def __init__(self):
        super().__init__(
            card_id = "expect_a_fight",
            name = "Expect a Fight",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        from ..Registry.card_registry import create_card
        ally = context.source
        attacks = sum(1 for ref in ally.hand
                      if create_card(ref).card_type is CardType.ATTACK)
        # The Energy first, then the lock: the lock is on energy gained after.
        return [
            InstantEnergy(source=ally, target=ally, amount=self.ENERGY_PER_ATTACK * attacks),
            NoEnergyGain(source=ally, target=ally),
        ]
