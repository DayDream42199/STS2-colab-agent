from abc import ABC, abstractmethod
from ._card_properties import CardProperties
from ._card_ref import bonus_of, cost_bump_of, is_upgraded, replay_of
from ._upgrades import upgrade_for

class Card(ABC):
    # A card printed with this cost spends everything the player has, and the
    # amount spent arrives back in get_effects as context.x_amount.
    X_COST = "X"

    # What this card hits for per hit, where that is a printed number. Read by
    # cards that read other cards (Thrash); 0 where the damage is worked out.
    DAMAGE = 0

    # A card that would rather declare its own upgrade than sit in the shared
    # table in _upgrades.py.
    UPGRADE = None

    # While this sits in hand, nothing else may be played (Enthralled).
    MUST_PLAY_FIRST = False

    # While this sits in hand, no more than this many cards may be played in a
    # turn (Sloth, Normality). The tightest cap held wins.
    PLAY_CAP = None

    # Charged every turn for every copy in the deck - hand, draw pile or
    # discard pile alike (Mind Rot, Waste Away). Copies stack.
    DRAW_PENALTY = 0
    ENERGY_PENALTY = 0

    def __init__(
        self,
        card_id,
        name,
        card_type,
        card_class,
        rarity,
        cost,
        target_type,
        properties=None
    ):
        self.card_id = card_id
        self.name = name
        self.card_type = card_type
        self.card_class = card_class
        self.rarity = rarity
        self.cost = cost
        self.target_type = target_type

        self.properties = properties if properties is not None else CardProperties()

        # A Card is minted fresh for every lookup, so state belonging to the
        # copy rather than the printing lives on the ref and arrives in bind().
        self.ref = card_id
        self.upgraded = False
        # Rampage and Maul grow one copy's damage for the rest of the combat.
        self.bonus_damage = 0
        # Extra times this copy resolves per play. Standing, not spent.
        self.replay = 0
        # Added to this copy's cost for the combat (Frantic Escape).
        self.cost_bump = 0

    def bind(self, card_ref):
        """Take on the state of the copy being played."""
        self.ref = card_ref
        self.bonus_damage = bonus_of(card_ref)
        self.replay = replay_of(card_ref)
        self.cost_bump = cost_bump_of(card_ref)
        if is_upgraded(card_ref):
            self.apply_upgrade()

    def apply_upgrade(self):
        """Swap in the upgraded numbers.

        Cards read their numbers off their own constants, so setting those on
        the instance is the whole of it - no card needs to know."""
        self.upgraded = True
        table = self.UPGRADE if self.UPGRADE is not None else upgrade_for(self.card_id)
        for name, value in table.items():
            if name == "properties":
                for flag, on in value.items():
                    setattr(self.properties, flag, on)
            else:
                setattr(self, name, value)

    def on_event(self, event, context):
        # Only matters while the card sits in hand (Burn, Void). Default: ignore.
        return None

    def follow_up(self, result, context):
        """More effects, chosen from what one of this card's effects just did.

        Effects are all built before any of them run, so this is the only way
        a card can read its own damage - Fisticuffs blocking for what it dealt.
        Combat calls it after each effect resolves. Default: nothing.
        """
        return None

    def playable_now(self, ally):
        """Whether this may be played out of `ally`'s hand right now.

        A condition on the hand rather than on the card, so `properties.playable`
        cannot answer it. This card is still in hand when it is asked."""
        return True

    def dynamic_cost(self, context):
        """What this card costs right now, before statuses and free plays.

        Stomp and Midnight count things up and get cheaper. Everything else
        costs what is printed on it, plus whatever this copy has had added."""
        if self.cost == self.X_COST:
            return self.cost
        return self.cost + self.cost_bump

    @abstractmethod
    def get_effects(self, context):
        pass