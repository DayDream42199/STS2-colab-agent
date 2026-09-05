from enum import Enum

class ClientMessage(Enum):
    PLAY_CARD = "play_card"
    END_TURN = "end_turn"
    REQUEST_STATE = "request_state"

class ServerMessage(Enum):
    WELCOME = "welcome"
    LOBBY = "lobby"
    STATE = "state"
    EFFECTS = "effects"
    READY_CHANGED = "ready_changed"
    COMBAT_ENDED = "combat_ended"
    ERROR = "error"
