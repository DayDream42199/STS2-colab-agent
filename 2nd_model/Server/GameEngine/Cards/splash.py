from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_ref import CardRef
from .discovery import Discovery


class Splash(Discovery):
    """Discovery narrowed to Attacks "from another character".

    In co-op that is your partner's character, and in an Ironclad-only run
    your partner is an Ironclad too, so the pool is the Ironclad one. When a
    second class exists this is where it would read the partner's class."""

    def __init__(self):
        Card.__init__(
            self,
            card_id = "splash",
            name = "Splash",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def offer_from(self, context):
        from ..Registry.card_registry import generatable_card_ids

        return generatable_card_ids(card_class=CardClass.IRONCLAD,
                                    card_type=CardType.ATTACK,
                                    solo=context.solo)

    def offered(self, card_id):
        # Upgraded, Splash offers the Attacks upgraded (the game's Splash has
        # no upgrade of its own: IsUpgraded upgrades what it generates).
        return CardRef(card_id, upgraded=True) if self.upgraded else card_id
