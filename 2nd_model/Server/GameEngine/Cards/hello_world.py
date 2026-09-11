from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.hello_world import HelloWorld as HelloWorldStatus


class HelloWorld(Card):
    def __init__(self):
        super().__init__(
            card_id = "hello_world",
            name = "Hello World",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [HelloWorldStatus(
            source=context.source, target=context.source, amount=1)]
