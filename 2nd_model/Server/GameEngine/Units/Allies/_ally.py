from abc import ABC

from .._unit import Unit
from ...Cards._card_ref import is_upgraded, replay_of

class Ally(Unit, ABC):
    DEFAULT_MAX_ENERGY = 3
    DEFAULT_DECK = []
    # The most a hand holds. Drawing stops here, and a card added or moved into
    # a full hand (Jackpot, Wish, Bolas coming back) goes to the discard pile
    # instead - the game's CardPileCmd.Add. The resolver does that part.
    HAND_LIMIT = 10

    def __init__(self, unit_id, max_hp=None, hp_variance=None, max_energy=None, deck=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)

        self.max_energy = max_energy if max_energy is not None else self.DEFAULT_MAX_ENERGY
        self.energy = self.max_energy

        self.deck = list(deck) if deck is not None else list(self.DEFAULT_DECK)
        self.draw_pile = []
        self.hand = []
        self.discard_pile = []
        # Exhausted cards leave play for the rest of the combat, but are
        # still a readable zone: several cards count or read them.
        self.exhaust_pile = []
        # Set by cards like Equilibrium; cleared every turn by Combat.
        self.retain_hand = False
        # Ids that cost 0 for their next play. A tally rather than a flag on
        # the card, because piles hold id strings: with two Strikes held and
        # one made free, either may be the free one.
        self.free_this_turn = []
        self.free_this_combat = []
        # Reshuffles this draw did. An Ally has no Combat to emit with, so it
        # counts them and Combat announces them (Stratagem).
        self.shuffles_pending = 0

    def start_turn(self):
        self.retain_hand = False
        self.free_this_turn = []
        self.clear_block()
        self.energy = self.max_energy

    def draw(self, count, rng):
        drawn = []
        for _ in range(count):
            if len(self.hand) >= self.HAND_LIMIT:
                break
            if not self.reshuffle_if_empty(rng):
                break
            card_id = self.draw_pile.pop()
            self.hand.append(card_id)
            drawn.append(card_id)
        return drawn

    def reshuffle_if_empty(self, rng):
        """An empty draw pile takes the discard pile, shuffled. False if both
        are empty. Drawing does this, and so does playing off the top (Havoc)."""
        if self.draw_pile:
            return True
        if not self.discard_pile:
            return False
        self.draw_pile, self.discard_pile = self.discard_pile, []
        rng.shuffle(self.draw_pile)
        self.shuffles_pending += 1
        return True

    def gain_energy(self, amount):
        if amount > 0:
            self.energy += amount

    def spend_energy(self, amount):
        if amount > self.energy:
            raise ValueError("Not enough energy.")
        self.energy -= amount

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "energy": self.energy,
            "max_energy": self.max_energy,
            "hand": list(self.hand),
            # Additive: an upgraded card keeps its printed id, so this is the
            # only way the client can tell one apart.
            "hand_upgraded": [is_upgraded(card_id) for card_id in self.hand],
            "hand_replay": [replay_of(card_id) for card_id in self.hand],
            "exhaust_pile_count": len(self.exhaust_pile),
        })
        return data