from .._effect import Effect


class StatusEffect(Effect):
    ADDITIVE = 0
    MULTIPLICATIVE = 10
    DAMAGE_ORDER = MULTIPLICATIVE

    # Something an opponent did to you, rather than a buff. Rend counts these.
    IS_DEBUFF = False

    # Counted down at the end of the ENEMY turn, whoever holds it - the game's
    # Vulnerable, Weak and Frail (AfterSideTurnEnd, enemy side). So a player's
    # Vulnerable is still there when the enemies swing.
    TICKS_AFTER_ENEMY_TURN = False
    # Set when one of those lands on a player: its first count-down is
    # skipped, as the game's SkipNextDurationTick does, so an enemy's 2
    # Vulnerable covers the next two enemy turns, not one.
    skip_next_tick = False

    # Whether modify_incoming_damage is consulted only for attacks. Vulnerable
    # is: a Burn or Constrict on a Vulnerable player deals its printed number,
    # as in the reference. Intangible is not: it caps every kind of damage.
    ATTACKS_ONLY = False
    # The most cards its holder may play in a turn while it lasts (Ringing:
    # 1), read by Combat._play_cap beside the hand's Normality and Sloth.
    PLAY_CAP = None

    def forbids_play(self, card):
        """Whether its holder may not play `card` right now (Smoggy: a second
        Skill in a turn). Asked of manual and automatic plays alike, as the
        game's ShouldPlay is."""
        return False

    def modify_incoming_damage(self, amount, attacker=None):
        # `attacker` is who is hitting (Colossus), None when unattributed.
        return amount

    def modify_outgoing_damage(self, amount, target=None):
        # `target` is who is being hit (Cruelty).
        return amount

    # Whether modify_block_gained applies only to "powered" Block from a card
    # or a move - a card's own Block value. Dexterity and Frail are: Entrench's
    # doubling and a power's own Block are unpowered in the game, so they skip
    # them (IsPoweredCardOrMonsterMoveBlock).
    BLOCK_POWERED_ONLY = False

    def modify_block_gained(self, amount):
        return amount

    def modify_hp_lost(self, amount):
        """HP the holder is about to lose, after Block (Slippery). Called only
        for a real hit or loss, so it may spend a charge."""
        return amount

    def modify_card_block(self, amount, target, play_id):
        """Block a card of this status's owner gives `target` - the owner or
        a teammate - in card play `play_id`, after the target's own Block
        modifiers. Asked of the card's owner, not the target: the game's
        Unmovable doubles what its owner's cards give, and nothing else's."""
        return amount

    def after_attack_dealt(self):
        # The owner just attacked. The modify_* hooks above must not change
        # anything (an intent previews them); a one-shot bonus spends here.
        pass

    # When card_cost asks this status. A free Attack goes last (100), so an
    # extra cost from Tangled cannot survive it.
    COST_ORDER = 0

    def modify_card_cost(self, cost, card):
        return cost

    def modify_energy_gain(self, amount):
        # Energy gained from an effect, not the turn's refill (No Energy Gain).
        return amount

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
