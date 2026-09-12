from .._effect import Effect


class StatusEffect(Effect):
    ADDITIVE = 0
    MULTIPLICATIVE = 10
    DAMAGE_ORDER = MULTIPLICATIVE

    # Something an opponent did to you, rather than a buff. Rend counts these.
    IS_DEBUFF = False

    # Whether modify_incoming_damage is consulted only for attacks. Vulnerable
    # is: a Burn or Constrict on a Vulnerable player deals its printed number,
    # as in the reference. Intangible is not: it caps every kind of damage.
    ATTACKS_ONLY = False

    def modify_incoming_damage(self, amount, attacker=None):
        # `attacker` is who is hitting (Colossus), None when unattributed.
        return amount

    def modify_outgoing_damage(self, amount, target=None):
        # `target` is who is being hit (Cruelty).
        return amount

    def modify_block_gained(self, amount):
        return amount

    def modify_card_cost(self, cost, card):
        return cost

    def modify_cards_drawn(self, amount):
        return amount

    def keeps_block(self):
        # Barricade: Block is not cleared at the start of the owner's turn.
        return False

    # Who gets asked first where a played card goes. A status claiming a card
    # it is holding (ReturnToHand) has to beat one claiming any card at all.
    REDIRECT_ORDER = 10

    def redirect_played_card(self, card, context):
        """Where a played card goes instead of the discard pile: an
        InstantMoveCard pile name, or None. Claiming spends the charge."""
        return None

    def absorb(self, other):
        # A second application of a status already held. Amounts add, unless
        # the status carries something else worth merging (ReturnToHand).
        self.amount += other.amount

    def on_owner_turn_end(self):
        self.amount -= 1

    def on_event(self, event, context):
        """React to a GameEvent: a list of effects for Combat to resolve, or
        None to ignore it."""
        return None

    def is_expired(self):
        return self.amount <= 0
