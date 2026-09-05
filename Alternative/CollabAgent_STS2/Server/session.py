import random

from GameEngine.Units.Allies.test_ally_1 import TestAlly1
from GameEngine.Units.Enemies.dummy_1 import Dummy1
from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage

BROADCAST = None

# The one phase name Session needs to recognise. See COMBAT_INTERFACE.md.
PLAYER_TURN = "PLAYER_TURN"

class Session:
    DEFAULT_REQUIRED_PLAYERS = 1
    ALLY_CLASS = TestAlly1
    ENEMY_CLASSES = (Dummy1,)

    def __init__(self, combat_factory, required_players=None, rng=None):
        self.combat_factory = combat_factory
        self.required_players = (
            required_players if required_players is not None else self.DEFAULT_REQUIRED_PLAYERS
        )
        self.rng = rng if rng is not None else random.Random()

        self.combat = None
        self.players = {}
        self.ready = set()
        self._joined_count = 0

    # --- queries -------------------------------------------------------

    def is_running(self):
        return self.combat is not None and not self.combat.is_over()

    def ally_for(self, sid):
        return self.players.get(sid)

    # --- connection handling -------------------------------------------

    def add_player(self, sid):
        if sid in self.players:
            return [(sid, self._error("Already joined."))]
        if self.combat is not None:
            return [(sid, self._error("A combat is already in progress."))]
        if len(self.players) >= self.required_players:
            return [(sid, self._error("Session is full."))]

        self._joined_count += 1
        ally = self.ALLY_CLASS(f"p{self._joined_count}", rng=self.rng)
        self.players[sid] = ally

        outbound = [(sid, encode(ServerMessage.WELCOME, unit_id=ally.unit_id))]

        if len(self.players) < self.required_players:
            outbound.append((BROADCAST, encode(
                ServerMessage.LOBBY,
                players=len(self.players),
                required=self.required_players,
            )))
            return outbound

        outbound.extend(self._start_combat())
        return outbound

    def remove_player(self, sid):
        ally = self.players.pop(sid, None)
        self.ready.discard(sid)
        if ally is None:
            return []

        if self.combat is None:
            return [(BROADCAST, encode(
                ServerMessage.LOBBY,
                players=len(self.players),
                required=self.required_players,
            ))]

        # The ally stays in the combat so turn order and enemy targeting hold up;
        # it simply stops receiving commands.
        return self._advance_if_all_ready()

    def _start_combat(self):
        allies = list(self.players.values())
        enemies = [
            cls(f"e{index + 1}", rng=self.rng)
            for index, cls in enumerate(self.ENEMY_CLASSES)
        ]

        self.combat = self.combat_factory(allies, enemies, rng=self.rng)
        self.combat.start()

        return [(BROADCAST, self._state_message())]

    # --- message handling ----------------------------------------------

    def handle(self, sid, data):
        try:
            message_type, payload = decode(data, ClientMessage)
        except ValueError as error:
            return [(sid, self._error(str(error)))]

        if sid not in self.players:
            return [(sid, self._error("You are not part of this session."))]
        if message_type is ClientMessage.REQUEST_STATE:
            return [(sid, self._state_message())]
        if not self.is_running():
            return [(sid, self._error("No combat is in progress."))]

        try:
            if message_type is ClientMessage.PLAY_CARD:
                return self._handle_play_card(sid, payload)
            if message_type is ClientMessage.END_TURN:
                return self._handle_end_turn(sid)
        except (ValueError, IndexError, KeyError, RuntimeError) as error:
            return [(sid, self._error(str(error)))]

        return [(sid, self._error(f"Unhandled message: {message_type.value}"))]

    def _handle_play_card(self, sid, payload):
        if self.combat.phase.name != PLAYER_TURN:
            return [(sid, self._error("It is not the player turn."))]

        hand_index = payload.get("hand_index")
        if not isinstance(hand_index, int) or isinstance(hand_index, bool):
            return [(sid, self._error("hand_index must be an integer."))]

        target = None
        target_id = payload.get("target_id")
        if target_id is not None:
            target = self.combat.find_unit(target_id)
            if target is None:
                return [(sid, self._error(f"Unknown target: {target_id!r}"))]

        ally = self.players[sid]
        results = self.combat.play_card(ally, hand_index, target=target)

        # Playing a card invalidates any readiness already declared this turn.
        self.ready.discard(sid)

        outbound = [
            (BROADCAST, encode(ServerMessage.EFFECTS, source=ally.unit_id, results=results)),
            (BROADCAST, self._state_message()),
        ]
        outbound.extend(self._combat_ended_messages())
        return outbound

    def _handle_end_turn(self, sid):
        if self.combat.phase.name != PLAYER_TURN:
            return [(sid, self._error("It is not the player turn."))]

        self.ready.add(sid)

        outbound = [(BROADCAST, encode(
            ServerMessage.READY_CHANGED,
            ready=sorted(self.players[s].unit_id for s in self.ready),
            waiting_on=sorted(a.unit_id for a in self._pending_allies()),
        ))]
        outbound.extend(self._advance_if_all_ready())
        return outbound

    def _advance_if_all_ready(self):
        if not self.is_running():
            return []
        if self.combat.phase.name != PLAYER_TURN:
            return []
        if self._pending_allies():
            return []

        self.ready.clear()
        self.combat.end_player_turn()

        outbound = [(BROADCAST, self._state_message())]
        outbound.extend(self._combat_ended_messages())
        return outbound

    def _pending_allies(self):
        return [
            ally
            for sid, ally in self.players.items()
            if ally.is_alive() and sid not in self.ready
        ]

    # --- outbound helpers ----------------------------------------------

    def _state_message(self):
        if self.combat is None:
            return encode(
                ServerMessage.LOBBY,
                players=len(self.players),
                required=self.required_players,
            )
        return encode(ServerMessage.STATE, combat=self.combat.to_dict())

    def _combat_ended_messages(self):
        if self.combat is None or not self.combat.is_over():
            return []
        return [(BROADCAST, encode(ServerMessage.COMBAT_ENDED, result=self.combat.result.name))]

    @staticmethod
    def _error(message):
        return encode(ServerMessage.ERROR, message=message)
