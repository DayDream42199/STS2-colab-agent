from enum import Enum, auto


class GameEvent(Enum):
    """Things a persistent effect can react to. Combat emits these; statuses
    answer through StatusEffect.on_event and return effects to resolve.

    In the event context, `source` is the unit holding the reacting status and
    `target` is the unit the event happened to. A power that only cares about
    its own owner therefore checks `context.target is context.source`."""

    TURN_START = auto()      # payload: -
    TURN_END = auto()        # payload: -
    CARD_PLAYED = auto()     # payload: card
    CARD_DRAWN = auto()      # payload: amount
    CARD_EXHAUSTED = auto()  # payload: card
    HP_LOST = auto()         # payload: amount
    BLOCK_GAINED = auto()    # payload: amount
    ATTACKED = auto()        # payload: amount, attacker
    STATUS_APPLIED = auto()  # payload: effect_id
