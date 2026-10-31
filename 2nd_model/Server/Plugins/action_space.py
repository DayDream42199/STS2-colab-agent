"""The agent's actions as one fixed menu, the layout agreed for the agent:

    0-99     play a card: 10 x hand slot (0-9) + target slot (0-9)
    100      end turn
    101      wait
    102-111  answer the question: option slot 0-9
    112      stop an "up to N" question (option_index -1)

Target slots: 0 is none - a card that picks its own target (Self, All,
Random, Whirlwind); 1-6 the enemies, the living ones in fight order (a dead
enemy gives up its slot, and those after it move up); 7-9 the other players
in seat order (a defeated one keeps its slot, closed). No Act 1 fight has
more than 6 enemies alive at once; a 7th would have no slot. `targets` names the unit in
each slot; the agent's input should list enemies and teammates the same way.

`mask` is Combat.legal_actions laid onto the menu: an index is open exactly
when the action it decodes to would be accepted. `decode` turns an open index
back into the message to send.

A question with more than 10 options: the slots are its first 10. The
agent's divide-and-conquer card choice runs its own rounds and sends the
winner's real option_index - `decode(..., options=...)` maps a slot to
whichever options that round fed in.
"""
from GameEngine.Context.context import PendingChoice

HAND_SLOTS = 10
ENEMY_SLOTS = 6
TEAMMATE_SLOTS = 3
TARGET_SLOTS = 1 + ENEMY_SLOTS + TEAMMATE_SLOTS
OPTION_SLOTS = 10

END_TURN = HAND_SLOTS * TARGET_SLOTS       # 100
WAIT = END_TURN + 1                        # 101
CHOOSE = WAIT + 1                          # 102, option slot 0
STOP = CHOOSE + OPTION_SLOTS               # 112
SIZE = STOP + 1                            # 113


def targets(combat, ally):
    """The unit id in each of the 10 target slots, None where it is empty."""
    enemies = [enemy.unit_id for enemy in combat.enemies if enemy.is_alive()][:ENEMY_SLOTS]
    mates = [other.unit_id for other in combat.allies if other is not ally][:TEAMMATE_SLOTS]
    return ([None] + enemies + [None] * (ENEMY_SLOTS - len(enemies))
            + mates + [None] * (TEAMMATE_SLOTS - len(mates)))


def encode(action, slots):
    """The menu index of a legal_actions entry, or None if it has no slot: a
    seventh living enemy, an option past the tenth."""
    kind = action["type"]
    if kind == "end_turn":
        return END_TURN
    if kind == "wait":
        return WAIT
    if kind == "choose":
        option = action["option_index"]
        if option == PendingChoice.STOP:
            return STOP
        return CHOOSE + option if 0 <= option < OPTION_SLOTS else None
    if kind == "play_card":
        hand = action["hand_index"]
        if not 0 <= hand < HAND_SLOTS:
            return None
        target = action["target_id"]
        if target is None:
            return hand * TARGET_SLOTS
        for slot in range(1, TARGET_SLOTS):
            if slots[slot] == target:
                return hand * TARGET_SLOTS + slot
        return None
    raise ValueError(f"Not an action: {action!r}")


def decode(index, slots, options=None):
    """The action at an open menu index, shaped as legal_actions shapes it:
    its "type" is the message to send, the rest the payload. `options`, if
    given: the real option_index behind each option slot."""
    if not 0 <= index < SIZE:
        raise IndexError(f"Menu index {index} out of range.")
    if index < END_TURN:
        hand, slot = divmod(index, TARGET_SLOTS)
        return {"type": "play_card", "hand_index": hand, "target_id": slots[slot]}
    if index == END_TURN:
        return {"type": "end_turn"}
    if index == WAIT:
        return {"type": "wait"}
    if index == STOP:
        return {"type": "choose", "option_index": PendingChoice.STOP}
    slot = index - CHOOSE
    return {"type": "choose", "option_index": options[slot] if options is not None else slot}


def mask(combat, ally, slots=None):
    """SIZE numbers, 1 where that action is open to `ally` now, else 0."""
    slots = slots if slots is not None else targets(combat, ally)
    out = [0] * SIZE
    for action in combat.legal_actions(ally):
        index = encode(action, slots)
        if index is not None:
            out[index] = 1
    return out
