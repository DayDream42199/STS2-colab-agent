from ._instant_effect import InstantEffect


class InstantUpgradeCard(InstantEffect):
    """Upgrade specific copies, wherever they are.

    It marks the ref, so the upgrade follows the card between piles."""

    def __init__(self, source, target, card_refs):
        super().__init__("instant_upgrade_card")
        self.source = source
        self.target = target
        self.card_refs = list(card_refs)
