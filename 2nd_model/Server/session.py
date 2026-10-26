import functools
import random
import sys
import traceback

import config
from GameEngine.Cards._card_ref import is_upgraded
from GameEngine.Context.rng_streams import RngStreams
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage
from plugin_host import NullPlugin
from combat_log import NullLog

BROADCAST = None
PLAYER_TURN = "PLAYER_TURN"
# What a client is taken to be until it identifies itself.
DEFAULT_ROLE = "player"


def _delivered(method):
    """What an entry point sends goes through the plugin's formatter on its
    way out. With no plugin it comes back untouched."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        return self._deliver(method(self, *args, **kwargs))
    return wrapper


def _guarded(method):
    """An entry point an unexpected error cannot take the server down from:
    a bug in a card, say, is reported (Session._crashed) and the fight goes
    on from wherever it got to. Refusals - a play the rules forbid - are not
    errors and never get here."""
    @functools.wraps(method)
    def wrapper(self, sid, *args, **kwargs):
        try:
            return method(self, sid, *args, **kwargs)
        except Exception as error:
            return self._crashed(method.__name__, sid, args, error)
    return wrapper


class Session:
    DEFAULT_REQUIRED_PLAYERS = config.REQUIRED_PLAYERS
    ALLY_TYPE_ID = config.ALLY_TYPE_ID
    ENEMY_TYPE_IDS = config.ENEMY_TYPE_IDS
    ACT = config.ACT
    SCALE_ENEMIES = config.SCALE_ENEMIES

    def __init__(self, combat_factory, required_players=None, rng=None, plugin=None,
                 seed=None, combat_log=None):
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
        # A seed the log can record, so the fight can be replayed, and from it
        # one random stream per purpose (rng_streams.py). A caller that hands
        # over its own rng seeds the streams from it, and the log says there
        # is no seed.
        if rng is not None:
            self.seed = seed
            self.rngs = rng if isinstance(rng, RngStreams) else RngStreams.from_rng(rng)
        else:
            self.seed = seed if seed is not None else random.SystemRandom().randrange(2 ** 32)
            self.rngs = RngStreams(self.seed)
        self.rng = self.rngs.niche

        self.combat = None
        self.players = {}
        self.ready = set()
        self._joined_count = 0
        # The optional plugin (plugin_host.py) and what each client said it is.
        self.plugin = plugin if plugin is not None else NullPlugin()
        self.roles = {}
        self._end_announced = False
        # The combat log (combat_log.py): nothing is written without one.
        self.log = combat_log if combat_log is not None else NullLog()
        self.log.tag = self.seed

    def log_event(self, event, **data):
        """Add a line to the combat log - for a plugin's agent decisions and
        profile updates. Values should be plain JSON (numbers, strings, lists,
        dicts). Does nothing without a log."""
        self.log.write(event, **data)

    def _role(self, sid):
        return self.roles.get(sid, DEFAULT_ROLE)

    def _snapshot(self):
        """The state as players see it, for the log."""
        return self._state_message()["payload"].get("combat")

    # --- queries -------------------------------------------------------

    def is_running(self):
        return self.combat is not None and not self.combat.is_over()

    def ally_for(self, sid):
        return self.players.get(sid)

    # --- connection handling -------------------------------------------

    @_delivered
    @_guarded
    def add_player(self, sid):
        if sid in self.players:
            return [(sid, self._error("Already joined."))]
        if self.combat is not None:
            return [(sid, self._error("A combat is already in progress."))]
        if len(self.players) >= self.required_players:
            return [(sid, self._error("Session is full."))]

        self._joined_count += 1
        ally = create_ally(self.ALLY_TYPE_ID, f"p{self._joined_count}", rng=self.rngs.niche)
        self.players[sid] = ally
        self.log.write("join", unit_id=ally.unit_id, sid=sid)

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

    @_delivered
    @_guarded
    def remove_player(self, sid):
        ally = self.players.pop(sid, None)
        self.ready.discard(sid)
        self.roles.pop(sid, None)
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
        self.log.write("left", unit_id=ally.unit_id, results=results)
        if self.is_running():
            self.plugin.call("on_player_left", self, ally.unit_id)
        if results:
            outbound.append((BROADCAST, encode(
                ServerMessage.EFFECTS, source=ally.unit_id, action="left",
                results=results)))
            outbound.append((BROADCAST, self._state_message()))
        outbound.extend(self._advance_if_all_ready())
        return outbound

    def _start_combat(self):
        allies = list(self.players.values())
        # Built with no rng: each rolls its HP as the fight starts, from the
        # Niche stream and unlike the others (Combat._roll_hp). Moves come
        # from MonsterAi - as the game rolls both.
        enemies = [
            create_enemy(type_id, f"e{index + 1}")
            for index, type_id in enumerate(self.ENEMY_TYPE_IDS)
        ]
        for enemy in enemies:
            enemy.rng = self.rngs.monster_ai

        self.combat = self.combat_factory(
            allies, enemies, rng=self.rngs,
            act=self.ACT, scale_enemies=self.SCALE_ENEMIES)
        # There are people here to ask, so cards that offer a choice wait for
        # an answer instead of picking for themselves.
        self.combat.ask_players = True
        self.combat.start()
        # Everything a replay needs to set the same fight up again.
        self.log.write(
            "combat_start", seed=self.seed, act=self.ACT, scale_enemies=self.SCALE_ENEMIES,
            required_players=self.required_players, ally_type=self.ALLY_TYPE_ID,
            enemy_types=list(self.ENEMY_TYPE_IDS),
            players=[{"unit_id": ally.unit_id, "sid": sid, "role": self._role(sid),
                      "deck": [str(card) for card in ally.deck]}
                     for sid, ally in self.players.items()],
            plugin=getattr(self.plugin, "name", None), state=self._snapshot())
        self.log.write("turn_start", turn=self.combat.turn_number, state=self._snapshot())
        self.plugin.call("on_combat_start", self)
        self.plugin.call("on_turn_start", self)

        outbound = [(BROADCAST, self._state_message())]
        outbound.extend(self._choice_messages())
        return outbound

    # --- message handling ----------------------------------------------

    @_delivered
    @_guarded
    def handle(self, sid, data):
        outbound = self._dispatch(sid, data)
        self._log_refusal(sid, data, outbound)
        return outbound

    def _crashed(self, entry, sid, args, error):
        """What an unexpected error leaves behind: the traceback on the
        console and in the log, an error message to whoever sent the message,
        and - since part of the action may already have happened - the state
        as it now stands, to everyone."""
        trace = traceback.format_exc()
        what = f"{type(error).__name__}: {error}"
        print(f"Unexpected error in {entry} for {sid}:", file=sys.stderr)
        print(trace, file=sys.stderr)
        ally = self.players.get(sid)
        try:
            self.log.write("error", entry=entry, sid=sid,
                           unit_id=ally.unit_id if ally is not None else None,
                           message=args[0] if args else None, error=what, traceback=trace)
        except Exception:
            pass                             # a log that cannot take it changes nothing here
        outbound = [(sid, self._error(
            f"The server hit an unexpected error ({what}); the action may be partly done."))]
        if self.combat is not None:
            try:
                outbound.append((BROADCAST, self._state_message()))
            except Exception:
                pass
        return outbound

    def _log_refusal(self, sid, data, outbound):
        """A message the server turned down goes in the log too - an agent
        trying moves the game does not allow is worth being able to see."""
        for to, message in outbound:
            if to == sid and message.get("type") == ServerMessage.ERROR.value:
                ally = self.players.get(sid)
                self.log.write("refused", unit_id=ally.unit_id if ally else None,
                               role=self._role(sid), message=data,
                               error=message["payload"].get("message"))
                return

    def _dispatch(self, sid, data):
        try:
            message_type, payload = decode(data, ClientMessage)
        except ValueError as error:
            return [(sid, self._error(str(error)))]

        if sid not in self.players:
            return [(sid, self._error("You are not part of this session."))]
        if message_type is ClientMessage.REQUEST_STATE:
            return [(sid, self._state_message())]
        if message_type is ClientMessage.IDENTIFY:
            return self._handle_identify(sid, payload)
        if not self.is_running():
            return [(sid, self._error("No combat is in progress."))]

        try:
            if message_type is ClientMessage.PLAY_CARD:
                return self._handle_play_card(sid, payload)
            if message_type is ClientMessage.END_TURN:
                return self._handle_end_turn(sid, payload)
            if message_type is ClientMessage.CHOOSE:
                return self._handle_choose(sid, payload)
        except (ValueError, IndexError, KeyError, RuntimeError) as error:
            return [(sid, self._error(str(error)))]

        return [(sid, self._error(f"Unhandled message: {message_type.value}"))]

    def _handle_identify(self, sid, payload):
        """A client says what it is ({"role": "agent"}). Stored for the
        plugin to format by; without a plugin it changes nothing. Answered
        with the current state, so a client that identifies after the fight
        began gets it in its own format."""
        role = payload.get("role")
        if not isinstance(role, str) or not role or len(role) > 32:
            return [(sid, self._error("role must be a short string, e.g. \"agent\"."))]
        self.roles[sid] = role
        self.log.write("identify", unit_id=self.players[sid].unit_id, role=role)
        self.plugin.call("on_identify", self, self.players[sid].unit_id, role)
        return [(sid, self._state_message())]

    def _with_decision(self, data, payload):
        """A client may send a `decision` with any action - an agent's action
        probabilities, say. The game ignores it; the log keeps it."""
        if isinstance(payload, dict) and "decision" in payload:
            data["decision"] = payload["decision"]
        return data

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
        played = self._card_before_play(ally, hand_index, target_id)
        results = self.combat.play_card(ally, hand_index, target=target)

        self.ready.discard(sid)
        self.log.write("play", **self._with_decision(
            dict(played, role=self._role(sid), results=results), payload))
        if self.plugin.active:
            self.plugin.call("on_action", self, dict(played, action="play", results=results))

        outbound = [
            # Which card, so a teammate's screen can say "p2 played Bash on e1".
            (BROADCAST, encode(ServerMessage.EFFECTS, source=ally.unit_id, action="play",
                               card_id=played["card_id"], upgraded=played["upgraded"],
                               target_id=target_id, results=results)),
            (BROADCAST, self._state_message()),
        ]
        outbound.extend(self._choice_messages())
        outbound.extend(self._combat_ended_messages())
        return outbound

    def _card_before_play(self, ally, hand_index, target_id):
        """The card about to be played, as it stood in hand: which copy, and
        - for a plugin or the log - its cost, damage and Block then, and every
        action that was open instead. Worked out only when one of them will
        read it."""
        played = {"unit_id": ally.unit_id, "hand_index": hand_index, "target_id": target_id,
                  "card_id": None, "upgraded": False}
        if not (0 <= hand_index < len(ally.hand)):
            return played
        ref = ally.hand[hand_index]
        played["card_id"], played["upgraded"] = str(ref), is_upgraded(ref)
        if self.plugin.active or self.log.active:
            played["cost"] = self.combat.hand_costs(ally)[hand_index]
            played["damage"] = self.combat.hand_damages(ally)[hand_index]
            played["block"] = self.combat.hand_blocks(ally)[hand_index]
            played["energy"] = ally.energy
            played["legal_actions"] = self.combat.legal_actions(ally)
        return played

    def _handle_choose(self, sid, payload):
        option_index = payload.get("option_index")
        if not isinstance(option_index, int) or isinstance(option_index, bool):
            return [(sid, self._error("option_index must be an integer."))]

        ally = self.players[sid]
        ask = self.combat.choice_for(ally)
        option = None
        if ask is not None and 0 <= option_index < len(ask.options):
            option = str(ask.options[option_index])
        # What was on offer, read before the answer clears the question.
        legal = self.combat.legal_actions(ally) if self.log.active else None
        options = [str(o) for o in ask.options] if ask is not None else None
        results = self.combat.answer_choice(ally, option_index)
        self.log.write("choose", **self._with_decision({
            "unit_id": ally.unit_id, "role": self._role(sid), "prompt": ask.prompt,
            "option_index": option_index, "option": option, "options": options,
            "legal_actions": legal, "results": results}, payload))
        if self.plugin.active:
            self.plugin.call("on_action", self, {
                "action": "choose", "unit_id": ally.unit_id, "prompt": ask.prompt,
                "option_index": option_index, "option": option, "results": results})

        outbound = [
            # option None: they stopped an "up to N" question.
            (BROADCAST, encode(ServerMessage.EFFECTS, source=ally.unit_id, action="choose",
                               option=option, results=results)),
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

    def _handle_end_turn(self, sid, payload=None):
        if self.combat.phase.name != PLAYER_TURN:
            return [(sid, self._error("It is not the player turn."))]
        if self.combat.choice_for(self.players[sid]) is not None:
            return [(sid, self._error("Answer the choice in front of you first."))]
        if not self.players[sid].is_alive():
            # As play_card refuses them: legal_actions lists nothing for them.
            return [(sid, self._error(f"{self.players[sid].unit_id} has been defeated and cannot act."))]

        legal = self.combat.legal_actions(self.players[sid]) if self.log.active else None
        self.ready.add(sid)
        self.log.write("end_turn", **self._with_decision({
            "unit_id": self.players[sid].unit_id, "role": self._role(sid),
            "turn": self.combat.turn_number, "legal_actions": legal}, payload))
        # Before the turn can move on: the plugin sees this player's hand,
        # HP and incoming damage as they were when they ended - the last
        # player to end included.
        self.plugin.call("on_turn_ended", self, self.players[sid].unit_id)

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

        # Everyone is done and the enemies are next: the plugin's round_end.
        self.log.write("round_end", turn=self.combat.turn_number)
        self.plugin.call("on_round_end", self)
        self.ready.clear()
        self.combat.end_player_turn()
        if self.is_running():
            self.log.write("turn_start", turn=self.combat.turn_number, state=self._snapshot())
            self.plugin.call("on_turn_start", self)

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
        combat = self.combat.to_dict()
        # Who has ended their turn lives here, not in Combat; each player
        # carries it so a screen can show "(ended)".
        ended = {self.players[s].unit_id for s in self.ready if s in self.players}
        for ally in combat.get("allies", []):
            ally["ended_turn"] = ally.get("unit_id") in ended
        return encode(ServerMessage.STATE, combat=combat)

    def _combat_ended_messages(self):
        if self.combat is None or not self.combat.is_over():
            return []
        if not self._end_announced:
            self._end_announced = True
            self.log.write("combat_end", result=self.combat.result.name,
                           turn=self.combat.turn_number, state=self._snapshot())
            self.plugin.call("on_combat_end", self, self.combat.result.name)
            self.log.close()
        return [(BROADCAST, encode(ServerMessage.COMBAT_ENDED, result=self.combat.result.name))]

    def _deliver(self, outbound):
        """Each outgoing message, as each recipient is to get it. No plugin:
        unchanged, broadcasts and all. With one, a broadcast is split per
        player and every copy goes through format_message, which may reshape
        it for that recipient's role or hold it back (None)."""
        if not self.plugin.active:
            return outbound
        delivered = []
        for recipient, message in outbound:
            recipients = list(self.players) if recipient is BROADCAST else [recipient]
            for sid in recipients:
                role = self.roles.get(sid, DEFAULT_ROLE)
                shaped = self.plugin.format(self, sid, role, message)
                if shaped is not None:
                    delivered.append((sid, shaped))
        return delivered

    @staticmethod
    def _error(message):
        return encode(ServerMessage.ERROR, message=message)
