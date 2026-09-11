from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.tag_team import TagTeam as TagTeamStatus


class TagTeam(Card):
    DAMAGE = 11

    def __init__(self):
        super().__init__(
            card_id = "tag_team",
            name = "Tag Team",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            TagTeamStatus(
                source=context.source, target=context.target, amount=1),
        ]
