class Context:
    """Passed into Card.get_effects() and Enemy.get_effects(). Holds only
    references — no behavior. Combat assembles a fresh one for every card
    play and every enemy move."""

    def __init__(self, source, target=None, all_allies=None, all_enemies=None,
                 rng=None, payload=None):
        self.source = source
        self.target = target
        self.all_allies = all_allies if all_allies is not None else []
        self.all_enemies = all_enemies if all_enemies is not None else []
        # Cards that draw need to reshuffle; the Resolver has no combat
        # reference, so the effect carries the rng it was built with.
        self.rng = rng
        # Extra detail for event dispatch (amount lost, card played, ...).
        self.payload = payload if payload is not None else {}
