from enum import Enum, auto


class GameEvent(Enum):
    # In an event context `source` is the status's owner and `target` is who
    # it happened to: a power that only cares about itself checks
    # `context.target is context.source`.
    TURN_START = auto()      # payload: -
    TURN_END = auto()        # payload: -
    CARD_PLAYED = auto()     # payload: card
    CARD_DRAWN = auto()      # payload: amount, card_ids
    CARD_EXHAUSTED = auto()  # payload: card
    HP_LOST = auto()         # payload: amount
    BLOCK_GAINED = auto()    # payload: amount
    ATTACKED = auto()        # payload: amount, attacker
    STATUS_APPLIED = auto()  # payload: effect_id
    DECK_SHUFFLED = auto()   # payload: -   the discard pile became the draw pile
