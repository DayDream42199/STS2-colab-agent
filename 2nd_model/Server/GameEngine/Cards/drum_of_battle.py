from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Events.game_event import GameEvent


class DrumOfBattle(Card):
    CARDS = 2
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "drum_of_battle",
            name = "Drum of Battle",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.CARDS, rng=context.rng)]

    def on_event(self, event, context):
        # Pays out when THIS card is exhausted, not when it is played.
        if event is not GameEvent.CARD_EXHAUSTED:
            return None
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
