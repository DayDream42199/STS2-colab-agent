from enum import Enum

class ClientMessage(Enum):
    PLAY_CARD = "play_card"
    END_TURN = "end_turn"
    REQUEST_STATE = "request_state"
    CHOOSE = "choose"
    # Let the others move first: allowed while someone else is still to act
    # (Combat.may_wait), listed in legal_actions when it is. Changes nothing.
    WAIT = "wait"
    # {"role": "agent"}: what this client is, for the plugin to format by.
    # A human client never needs to send it; without a plugin it changes nothing.
    IDENTIFY = "identify"

class ServerMessage(Enum):
    WELCOME = "welcome"
    LOBBY = "lobby"
    STATE = "state"
    EFFECTS = "effects"
    READY_CHANGED = "ready_changed"
    CHOICE_REQUIRED = "choice_required"
    COMBAT_ENDED = "combat_ended"
    ERROR = "error"
