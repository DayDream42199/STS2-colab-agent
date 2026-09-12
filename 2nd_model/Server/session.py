import random

import config
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage

BROADCAST = None
PLAYER_TURN = "PLAYER_TURN"

class Session:
    DEFAULT_REQUIRED_PLAYERS = config.REQUIRED_PLAYERS
    ALLY_TYPE_ID = config.ALLY_TYPE_ID
    ENEMY_TYPE_IDS = config.ENEMY_TYPE_IDS

    def __init__(self, combat_factory, required_players=None, rng=None):
        self.combat_factory = combat_factory
        self.required_players = (
            required_players if required_players is not None else self.DEFAULT_REQUIRED_PLAYERS
        )
        # Combat's party cap, checked now so a bad REQUIRED_PLAYERS fails at
        # startup with a message, not when the last player joins.
        cap = getattr(combat_factory, "MAX_ALLIES", None)
        if self.required_players < 1 or (cap is not None and self.required_players > cap):
            raise ValueError(
                f"REQUIRED_PLAYERS must be 1 to {cap}, not {self.required_players}.")
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
        ally = create_ally(self.ALLY_TYPE_ID, f"p{self._joined_count}", rng=self.rng)
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

        # Nobody is left to answer for them, so their questions answer
        # themselves - otherwise the turn would never advance again.
        outbound = []
        results = self.combat.forfeit_choices(ally)
        if results:
            outbound.append((BROADCAST, encode(
                ServerMessage.EFFECTS, source=ally.unit_id, results=results)))
            outbound.append((BROADCAST, self._state_message()))
        outbound.extend(self._advance_if_all_ready())
        return outbound

    def _start_combat(self):
        allies = list(self.players.values())
        enemies = [
            create_enemy(type_id, f"e{index + 1}", rng=self.rng)
            for index, type_id in enumerate(self.ENEMY_TYPE_IDS)
        ]

        self.combat = self.combat_factory(
            allies, enemies, rng=self.rng,
            act=config.ACT, scale_enemies=config.SCALE_ENEMIES)
        # There are people here to ask, so cards that offer a choice wait for
        # an answer instead of picking for themselves.
        self.combat.ask_players = True
        self.combat.start()

        outbound = [(BROADCAST, self._state_message())]
        outbound.extend(self._choice_messages())
        return outbound

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
            if message_type is ClientMessage.CHOOSE:
                return self._handle_choose(sid, payload)
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

        self.ready.discard(sid)

        outbound = [
            (BROADCAST, encode(ServerMessage.EFFECTS, source=ally.unit_id, results=results)),
            (BROADCAST, self._state_message()),
        ]
        outbound.extend(self._choice_messages())
        outbound.extend(self._combat_ended_messages())
        return outbound

    def _handle_choose(self, sid, payload):
        option_index = payload.get("option_index")
        if not isinstance(option_index, int) or isinstance(option_index, bool):
            return [(sid, self._error("option_index must be an integer."))]

        ally = self.players[sid]
        results = self.combat.answer_choice(ally, option_index)

        outbound = [
            (BROADCAST, encode(ServerMessage.EFFECTS, source=ally.unit_id, results=results)),
            (BROADCAST, self._state_message()),
        ]
        outbound.extend(self._choice_messages())
        outbound.extend(self._combat_ended_messages())
        # An answer can be the last thing a turn was waiting on.
        outbound.extend(self._advance_if_all_ready())
        return outbound

    def _choice_messages(self):
        """Tell each player privately about a question waiting on them."""
        if self.combat is None:
            return []
        outbound = []
        for sid, ally in self.players.items():
            ask = self.combat.choice_for(ally)
            if ask is not None:
                outbound.append(
                    (sid, encode(ServerMessage.CHOICE_REQUIRED, **ask.to_dict())))
        return outbound

    def _handle_end_turn(self, sid):
        if self.combat.phase.name != PLAYER_TURN:
            return [(sid, self._error("It is not the player turn."))]
        if self.combat.choice_for(self.players[sid]) is not None:
            return [(sid, self._error("Answer the choice in front of you first."))]

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
        if self.combat.pending_choices:
            return []   # a card is still mid-resolution, waiting on an answer

        self.ready.clear()
        self.combat.end_player_turn()

        outbound = [(BROADCAST, self._state_message())]
        outbound.extend(self._choice_messages())
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
