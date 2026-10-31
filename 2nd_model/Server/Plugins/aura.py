"""The agent's plugin (config.PLUGIN = "Plugins.aura"): the agent's format,
and the Characteristic Analyzer.

**Cards.** A client that identified as the agent ({"role": "agent"}) gets,
per player in a state's `allies`:
    hand_cards      one descriptor per card in hand, in hand order: cost,
                    damage per hit and Block as the hand shows them now
    piles           each entry gains the descriptor fields (printed cost,
                    the card's own damage and Block); the draw pile keeps its
                    sorted order, so nothing about the draw order leaks
    deck_cards      one descriptor per card in the deck
and to a question (`choice_required`):
    option_cards    one descriptor per option
A descriptor: id, upgraded, type, cost, target, keywords, damage, hits, block,
statuses (what it applies, by scope: self / target / all_allies /
all_enemies), groups (now / scale / team / self) - see card_groups.py.

**Actions.** With every state, and every `ready_changed` (a teammate ending
or waiting changes what is open without a new state), the agent gets its own
`action_mask` - 113 numbers, 1 where that action is open now - and
`action_targets`, the unit in each of the 10 target slots. The menu:
action_space.py.

**Profiles.** Every player who is not the agent is profiled on Aggression,
Scaling and Teamwork (analyzer.py has the arithmetic). Each turn's history is
gathered here: the energy they had, every card that was in their hand and the
values it showed, what they played, the damage aimed at them and their Block
when they ended. Once everyone has ended, each teammate's turn goes to the
combat log as "analyzer_input" - the analyzer's input, the spec's History:
energy, hand, used, opp, incoming, block, each card with its id, cost, dmg,
block and groups - and is scored, and their profile updated and logged as
"profile_update". `python -m Plugins.history_export <log>` writes the input
out per teammate in the MockUpRB prototype's list format.
The agent's state carries them as `profiles`: {unit_id: {A, S, T, cA, cS, cT}}.
A turn is not scored for a player who never ended it (they left, the fight
ended), who was dead when it began, or whose questions were being answered
for them. Profiles last the fight: the server plays one per session.

Every other client gets the player format, untouched. Game units only: the
agent normalizes.
"""
from . import action_space, analyzer
from .card_groups import card_info, describe_card, describe_hand

AGENT = "agent"


class _Turn:
    """One player's turn so far: step 1 of the analyzer, Behavioral History."""

    def __init__(self, ally):
        self.alive_at_start = ally.is_alive()
        self.energy = ally.energy            # E: what the turn began with ...
        self.last_energy = ally.energy       # ... plus every gain since
        self.opp = {}                        # id(card) -> (card, values): Opp
        self.hand = []                       # the hand as last seen, in order
        self.used = []                       # values of each card they played
        self.ended = None                    # the turn as they ended it


def _values(card_id, upgraded, cost, damage, hits, block, groups, energy):
    """A card as the analyzer reads it: cost, all its damage, its Block for
    the player, its groups - and which card it is, for whoever reads the log."""
    if cost == "X":
        cost = energy
    return {"id": card_id, "upgraded": bool(upgraded), "cost": cost or 0,
            "dmg": (damage or 0) * hits, "block": block or 0, "groups": list(groups)}


class Aura:
    name = "aura"

    def __init__(self):
        self.turns = {}          # unit_id -> _Turn
        self.profiles = {}       # unit_id -> analyzer profile

    # --- the agent's format ----------------------------------------------

    def format_message(self, session, recipient, role, message):
        if role != AGENT or session.combat is None:
            return message
        kind = message.get("type")
        payload = message.get("payload") or {}
        if kind == "state" and payload.get("combat"):
            self._add_cards(session.combat, payload["combat"])
            payload["profiles"] = {unit_id: analyzer.values(profile)
                                   for unit_id, profile in self.profiles.items()
                                   if unit_id != _unit_of(session, recipient)}
            self._add_menu(session, recipient, payload)
        elif kind == "ready_changed":
            self._add_menu(session, recipient, payload)
        elif kind == "choice_required":
            self._add_options(session.combat, payload)
        return message

    @staticmethod
    def _add_menu(session, recipient, payload):
        ally = session.players.get(recipient)
        if ally is None:
            return
        slots = action_space.targets(session.combat, ally)
        payload["action_targets"] = slots
        payload["action_mask"] = action_space.mask(session.combat, ally, slots)

    @staticmethod
    def _add_cards(combat, state):
        for ally_state in state.get("allies", ()):
            ally = combat.find_unit(ally_state["unit_id"])
            if ally is None:
                continue
            ally_state["hand_cards"] = describe_hand(combat, ally)
            for entries in ally_state.get("piles", {}).values():
                for entry in entries:
                    entry.update(describe_card(_ref(entry), ally))
            ally_state["deck_cards"] = [describe_card(card, ally) for card in ally.deck]

    @staticmethod
    def _add_options(combat, payload):
        ally = combat.find_unit(payload.get("unit_id"))
        ask = combat.choice_for(ally) if ally is not None else None
        if ask is None:
            return
        payload["option_cards"] = [describe_card(option, ally) for option in ask.options]

    # --- the analyzer: gathering each turn -------------------------------

    def on_combat_start(self, session):
        self.turns = {}
        self.profiles = {ally.unit_id: analyzer.new_profile()
                         for sid, ally in session.players.items() if session.roles.get(sid) != AGENT}

    def on_identify(self, session, unit_id, role):
        # Identifying as the agent can come after the fight began.
        if role == AGENT:
            self.profiles.pop(unit_id, None)
        elif session.combat is not None:
            self.profiles.setdefault(unit_id, analyzer.new_profile())

    def on_turn_start(self, session):
        combat = session.combat
        self.turns = {ally.unit_id: _Turn(ally) for ally in combat.allies}
        for ally in combat.allies:
            self._see_hand(combat, ally)

    def on_action(self, session, action):
        combat = session.combat
        actor = action.get("unit_id")
        spent = 0
        if action.get("action") == "play":
            spent = self._played(action)
        for ally in combat.allies:
            turn = self.turns.get(ally.unit_id)
            if turn is None:
                continue
            # Energy gained since last seen, past what a play spent: Bloodletting,
            # a teammate's Believe In You, Automation on a draw.
            paid = spent if ally.unit_id == actor else 0
            turn.energy += max(0, ally.energy - (turn.last_energy - paid))
            turn.last_energy = ally.energy
            if turn.ended is None:
                self._see_hand(combat, ally)

    def _played(self, action):
        """Record the card they played, as it stood in hand; returns what it
        cost them."""
        turn = self.turns.get(action["unit_id"])
        if turn is None:
            return 0
        info = card_info(action["card_id"], bool(action.get("upgraded")))
        cost = action.get("cost")
        spent = action.get("energy", 0) if cost == "X" else (cost or 0)
        hits = info["hits"] * (spent if info["x_cost"] else 1)
        values = _values(action["card_id"], action.get("upgraded"), spent, action.get("damage"),
                         hits, action.get("block"), info["groups"], spent)
        turn.used.append(values)
        index = action.get("hand_index")
        if index is not None and 0 <= index < len(turn.hand) and str(turn.hand[index]) == action["card_id"]:
            card = turn.hand[index]
            turn.opp[id(card)] = (card, values)
        turn.ended = None          # playing after ending takes the end back
        return spent

    def _see_hand(self, combat, ally):
        """Add whatever is in the hand to Opp, with the values it shows now."""
        turn = self.turns[ally.unit_id]
        for card, d in zip(ally.hand, describe_hand(combat, ally)):
            turn.opp[id(card)] = (card, _values(d["id"], d["upgraded"], d["cost"], d["damage"],
                                                d["hits"], d["block"], d["groups"], ally.energy))
        turn.hand = list(ally.hand)

    def on_turn_ended(self, session, unit_id):
        turn = self.turns.get(unit_id)
        if turn is None or turn.ended is not None:
            return                                  # a repeat changes nothing
        combat = session.combat
        ally = combat.find_unit(unit_id)
        self._see_hand(combat, ally)
        turn.ended = {
            "energy": turn.energy,
            "hand": [turn.opp[id(card)][1] for card in ally.hand],   # what was left
            "used": list(turn.used),
            "opp": [values for _, values in turn.opp.values()],
            "incoming": _incoming(combat, ally),
            "block": ally.block,
            "turn": combat.turn_number,
        }

    # --- the analyzer: scoring, once everyone has ended -------------------

    def on_round_end(self, session):
        combat = session.combat
        for unit_id, profile in self.profiles.items():
            turn = self.turns.get(unit_id)
            if (turn is None or turn.ended is None or not turn.alive_at_start
                    or unit_id in combat.unattended):
                continue
            history = turn.ended
            session.log_event("analyzer_input", unit_id=unit_id, **history)
            found, context, mapped = analyzer.evidence(history)
            analyzer.update(profile, found)
            session.log_event("profile_update", unit_id=unit_id, turn=history["turn"],
                              evidence=found, context=context, mapped=mapped,
                              profile=analyzer.values(profile))


def _incoming(combat, ally):
    """D: the damage every enemy's attack intent will do to `ally`, all hits."""
    total = 0
    for enemy in combat.enemies:
        if not enemy.is_alive():
            continue
        intent = combat._enemy_dict(enemy).get("intent") or {}
        if intent.get("type") == "attack":
            total += intent.get("damage", {}).get(ally.unit_id, 0) * intent.get("hits", 1)
    return total


def _unit_of(session, sid):
    ally = session.players.get(sid)
    return ally.unit_id if ally is not None else None


def _ref(entry):
    from GameEngine.Cards._card_ref import CardRef
    return CardRef(entry["id"], upgraded=entry["upgraded"])


def create_plugin():
    return Aura()
