from enum import Enum

class ClientMessage(Enum):
    PLAY_CARD = "play_card"
    END_TURN = "end_turn"
    REQUEST_STATE = "request_state"
    CHOOSE = "choose"

class ServerMessage(Enum):
    WELCOME = "welcome"
    LOBBY = "lobby"
    STATE = "state"
    EFFECTS = "effects"
    READY_CHANGED = "ready_changed"
    CHOICE_REQUIRED = "choice_required"
    COMBAT_ENDED = "combat_ended"
    ERROR = "error"
