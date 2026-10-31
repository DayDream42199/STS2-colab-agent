"""Card groups and card descriptors, for the agent and the analyzer. Part of
the plugin: the game itself never imports this.

The four groups:
    now     every card that is not a Power
    scale   every Power
    team    damages an enemy, debuffs an enemy, buffs every player at once,
            or does anything to a teammate - or gives you a status that does
            one of those when it fires (Juggernaut, Beacon of Hope, The Bomb)
    self    gives you Block, buffs you, draws you cards, gives you energy,
            heals you, changes your own cards (makes, moves, exhausts,
            upgrades them) or plays other cards

A card can be in team and self both (Iron Wave), or in neither (a Wound: it is
just "now").

How a card is judged: it is played in a sandbox fight - two players, two
enemies - and what changed is read off: damage dealt, Block gained, and every
status that came or went on every unit. A status is judged by STATUS_ROLES: a
buff or a debuff to whoever holds it, and for a buff on a player, whether it
helps that player or the team. So a Power counts by what its status does when
it fires, which the sandbox does not wait for. The sandbox is played on its
own seed and touches nothing of the real fight.

Everything is in game units. Normalizing for the network is the agent's job.

    python -m Plugins.card_groups      every card's groups (from Server/)
"""
import random
from functools import lru_cache

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card import Card
from GameEngine.Cards._card_enums import CardType, TargetType
from GameEngine.Cards._card_ref import CardRef, is_upgraded

GROUPS = ("now", "scale", "team", "self")
SCOPES = ("self", "target", "all_allies", "all_enemies")

# What a status is to whoever holds it. SELF and TEAM are buffs: on a player,
# SELF helps that player, TEAM acts on the enemies or the other players - both,
# for one that plays your cards at the enemies.
# DEBUFF is bad for its holder. NONE is bookkeeping, or an enemy's own
# mechanic, and is ignored. Where the engine's IS_DEBUFF and the game's
# PowerType disagree (No Draw, No Block, The Gambit are debuffs in the game),
# this follows the game. Every status needs an entry; tests/test_card_groups.py
# fails until a new one has it.
SELF, TEAM, DEBUFF, NONE = "self", "team", "debuff", "none"
STATUS_ROLES = {
    "aggression": SELF,             # Attacks back from your discard
    "artifact": SELF,
    "asleep": SELF,                 # Lagavulin Matriarch: asleep until hit or three turns
    "automation": SELF,             # energy every 10 draws
    "barricade": SELF,              # your Block stays
    "beacon_of_hope": TEAM,         # the other players gain half your Block
    "block_lockout": DEBUFF,        # Panic Button: no Block (the game's NoBlock)
    "bomb": TEAM,                   # goes off on every enemy
    "calamity": SELF,               # Attacks into your hand
    "caltrops": TEAM,               # damage back at attackers (Thorns)
    "choking": DEBUFF,              # on an enemy: loses HP as cards are played (Strangle)
    "colossus_guard": SELF,         # half damage from Vulnerable attackers
    "constrict": DEBUFF,
    "corruption": SELF,
    "crimson_mantle": SELF,         # Block each turn
    "cruelty": SELF,                # your attacks hit Vulnerable enemies harder
    "curious": SELF,                # Powers cost less
    "dark_embrace": SELF,           # draw on exhaust
    "delayed_block": SELF,          # Toric Toughness's later Block
    "delayed_draw": SELF,
    "delayed_energy": SELF,
    "demon_form": SELF,             # Strength each turn
    "dexterity": SELF,
    "entropy": SELF,
    "exposed": DEBUFF,
    "fasten": SELF,
    "feel_no_pain": SELF,           # Block on exhaust
    "flame_barrier": TEAM,          # damage back at attackers
    "frail": DEBUFF,
    "free_attack": SELF,
    "gambit": DEBUFF,               # die to unblocked damage (the game's TheGambit, a debuff)
    "hardened_shell": SELF,         # Skulking Colony: loses at most so much HP a turn
    "hello_world": SELF,
    "hellraiser": (TEAM, SELF),     # plays your Strikes at enemies as they are drawn
    "illusion": NONE,               # an enemy's comeback
    "inferno": TEAM,                # damage to every enemy
    "infested": NONE,               # an enemy's death burst
    "intangible": SELF,
    "intercepting": TEAM,           # attacks on your teammates hit you instead
    "juggernaut": TEAM,             # damage to an enemy on Block
    "juggling": SELF,
    "mayhem": SELF,                 # plays your own top card
    "minion": NONE,
    "no_energy_gain": DEBUFF,
    "no_more_draw": DEBUFF,         # Battle Trance (the game's NoDraw, a debuff)
    "nostalgia": SELF,
    "one_two_punch": SELF,
    "panache": TEAM,                # damage to every enemy
    "plating": SELF,
    "plow": DEBUFF,                 # Ceremonial Beast's charge, broken by damage
    "prep_time": SELF,              # Vigor each turn
    "protected": SELF,              # half damage (Tank gives it to the others)
    "pyre": SELF,
    "rage": SELF,                   # Block per Attack
    "ravenous": SELF,               # Corpse Slug: Strength when another enemy dies
    "rebound": SELF,
    "return_to_hand": NONE,         # Bolas / Thrumming Hatchet held until next turn
    "ringing": DEBUFF,              # Beast Cry: one card this turn
    "ritual": SELF,                 # Strength at the end of every enemy turn
    "rolling_boulder": TEAM,        # damage to every enemy
    "rupture": SELF,
    "sandpit": DEBUFF,
    "shriek": DEBUFF,               # Terror Eel: stunned once it is down to it
    "shrink": DEBUFF,
    "skittish": SELF,               # Phantasmal Gardener: Block when an attack gets through
    "slippery": SELF,               # each hit through Block takes only 1 HP
    "slow": DEBUFF,                 # Bygone Effigy: takes more from each card played
    "smoggy": DEBUFF,               # Living Fog: one Skill a turn
    "stampede": (TEAM, SELF),       # plays one of your Attacks at an enemy
    "steam_eruption": SELF,         # Waterfall Giant: what it blows for when brought down
    "stored_block": SELF,
    "stratagem": SELF,
    "strength": SELF,
    "strength_loss_this_turn": DEBUFF,
    "strength_this_turn": SELF,
    "stun": DEBUFF,
    "suck": SELF,                   # Fossil Stalker: Strength per hit that gets through
    "surprise": NONE,               # Gremlin Merc: two gremlins when it dies
    "tag_team": DEBUFF,             # marks an enemy for your teammates
    "tangled": DEBUFF,
    "tank": TEAM,                   # you take the hits so the others take less
    "territorial": SELF,            # Byrdonis: Strength at each enemy turn end
    "unmovable": SELF,
    "vicious": SELF,
    "vigor": SELF,
    "vulnerable": DEBUFF,
    "weak": DEBUFF,
    "withering_presence": DEBUFF,
}

_FOR_A_TEAMMATE = (TargetType.ALLY, TargetType.ALL_ALLIES, TargetType.RANDOM_ALLY)

# Results that change the player's own cards - self.
_CARD_CHANGES = ("instant_add_card", "instant_move_card", "instant_exhaust", "instant_upgrade_card",
                 "instant_boost_card", "instant_grant_replay", "instant_raise_cost",
                 "instant_cap_cost")


def _roles(status_id):
    role = STATUS_ROLES.get(status_id, NONE)
    return role if isinstance(role, tuple) else (role,)


# --- the sandbox -------------------------------------------------------------

def _units_state(units):
    return {unit.unit_id: {
        "hp": unit.current_hp, "max_hp": unit.max_hp, "block": unit.block,
        "statuses": {sid: status.amount for sid, status in unit.statuses.items()},
        "energy": getattr(unit, "energy", None),
        "piles": tuple(len(getattr(unit, pile, ()))
                       for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile")),
    } for unit in units}


def _flat(results):
    """Every result dict, those of cards played by this one included."""
    for result in results or ():
        if isinstance(result, dict):
            yield result
            yield from _flat(result.get("results"))


_INERT = ["debris"] * 6          # Debris does nothing when played (Slimed draws)
_FETCHABLE = ["strike", "impervious"]   # an Attack, a Skill, a Rare


def _play_in_sandbox(card_id, upgraded, filler, energy, draw=_INERT):
    """Play the card once, as p1, in a fresh fight. None if it cannot be played
    there; else (card, target, results, before, after, allies, enemies)."""
    p1, p2 = create_ally("ironclad", "p1"), create_ally("ironclad", "p2")
    e1, e2 = create_enemy("dummy1", "e1"), create_enemy("dummy1", "e2")
    combat = Combat([p1, p2], [e1, e2], rng=random.Random(7), scale_enemies=False)
    combat.start()
    for enemy in (e1, e2):
        enemy.current_hp = enemy.max_hp = 300
        enemy.block = 0
        enemy.statuses.clear()
    for ally in (p1, p2):
        ally.current_hp = ally.max_hp = 200
        ally.energy = 10
        ally.statuses.clear()
    p1.energy = energy
    p1.block = 10                                  # Body Slam, Entrench
    p1.current_hp = 150                            # room to heal
    p1.hand = [CardRef(card_id, upgraded=upgraded)] + [CardRef(c) for c in filler]
    # Inert cards to draw, so Havoc and Cascade show only what they do
    # themselves; Attacks in the discard for Beat Down, Headbutt, Neow's Fury;
    # three exhausted, which Pact's End needs before it deals anything.
    p1.draw_pile = [CardRef(c) for c in draw]
    p1.discard_pile = [CardRef(c) for c in ("strike", "defend", "anger")]
    p1.exhaust_pile = [CardRef("strike") for _ in range(3)]
    p1.turn_counters["cards_exhausted"] = 1        # and one this turn (Forgotten Ritual)
    card = create_card(p1.hand[0])
    target = {TargetType.ENEMY: e1, TargetType.ALLY: p2}.get(card.target_type)
    units = combat.allies + combat.enemies
    before = _units_state(units)
    try:
        results = combat.play_card(p1, 0, target=target)
    except Exception:
        return None
    return card, target, results, before, _units_state(units), combat.allies, combat.enemies


def _effects(play):
    """What one sandbox play did, as signals for the groups, the hits and
    the statuses it applied by scope."""
    card, target, results, before, after, allies, enemies = play
    me, mate = allies
    signals = set()
    enemy_ids = {e.unit_id for e in enemies}
    hits_on = {}
    for result in _flat(results):
        effect_id, target_id = result.get("effect_id"), result.get("target_id")
        if effect_id == "instant_damage" and target_id in enemy_ids:
            hits_on[target_id] = hits_on.get(target_id, 0) + 1
        elif target_id == me.unit_id and effect_id == "instant_play_card":
            signals.add("plays_cards")       # whatever it played (Havoc on Debris does nothing)
        elif target_id == me.unit_id and (result.get("amount") or 0) > 0:
            if effect_id in ("instant_draw", "instant_draw_until"):
                signals.add("draw")
            elif effect_id == "instant_energy":
                signals.add("energy")
            elif effect_id in ("instant_heal", "instant_max_hp_gain"):
                signals.add("heal")
            elif effect_id in _CARD_CHANGES:
                signals.add("own_cards")
    if hits_on or any(after[e]["hp"] + after[e]["block"] < before[e]["hp"] + before[e]["block"]
                      for e in enemy_ids):
        signals.add("damage")
    if after[me.unit_id]["block"] > before[me.unit_id]["block"]:
        signals.add("block")
    if after[mate.unit_id] != before[mate.unit_id] or card.target_type in _FOR_A_TEAMMATE:
        signals.add("teammate")

    deltas = {}           # status id -> {unit id: change}
    for unit_id in after:
        old, new = before[unit_id]["statuses"], after[unit_id]["statuses"]
        for sid in set(old) | set(new):
            change = new.get(sid, 0) - old.get(sid, 0)
            if change:
                deltas.setdefault(sid, {})[unit_id] = change
    statuses = {scope: {} for scope in SCOPES}
    for sid, changes in deltas.items():
        roles = _roles(sid)
        if NONE in roles:
            continue
        for unit_id, change in changes.items():
            harmful = (DEBUFF in roles) == (change > 0)      # a debuff gained, or a buff lost
            if unit_id in enemy_ids:
                if harmful:
                    signals.add("enemy_debuff")
            elif unit_id == me.unit_id and not harmful:
                if change > 0 and TEAM in roles:
                    signals.add("team_status")
                if change < 0 or SELF in roles:       # a buff for you, or a debuff taken off
                    signals.add("self_buff")
        on = set(changes)
        if enemy_ids <= on:
            statuses["all_enemies"][sid] = changes[next(iter(enemy_ids))]
            on -= enemy_ids
        if {me.unit_id, mate.unit_id} <= on:
            statuses["all_allies"][sid] = changes[me.unit_id]
            signals.add("all_allies")
            on -= {me.unit_id, mate.unit_id}
        for unit_id in on:
            scope = "self" if unit_id == me.unit_id else "target"
            statuses[scope][sid] = changes[unit_id]
    if card.target_type is TargetType.ALL_ENEMIES:
        hits = max(hits_on.values(), default=0)
    else:
        hits = sum(hits_on.values())
    return signals, hits, statuses


@lru_cache(maxsize=None)
def card_info(card_id, upgraded=False):
    """What a card is, apart from the numbers that move during a fight: type,
    target, keywords, hits (per energy, for an X-cost card), the statuses it
    applies by scope, its groups, and the signals they were read from."""
    card = create_card(CardRef(card_id, upgraded=upgraded))
    x_cost = card.cost == Card.X_COST
    plays = []
    if card.properties.playable:
        # The rest of the hand: mixed; all Attacks (Clash); no Attacks
        # (Impatience); nothing (Restlessness). What any of them shows counts.
        for filler in (["strike", "defend", "wound"], ["strike", "strike"], ["defend", "defend"], []):
            play = _play_in_sandbox(card_id, upgraded, filler, 1 if x_cost else 10)
            if play is not None:
                plays.append(play)
    signals, hits, statuses = set(), 0, {scope: {} for scope in SCOPES}
    for index, play in enumerate(plays):
        found, play_hits, play_statuses = _effects(play)
        signals |= found
        if index == 0:                              # numbers from one play, not added up
            hits, statuses = play_hits, play_statuses
    if plays and not signals:
        # Nothing happened: something to fetch from the draw pile may be what
        # it needs (Anointed, Secret Weapon). Only then, or Catastrophe - which
        # plays random cards from it - would read as whatever it played.
        play = _play_in_sandbox(card_id, upgraded, ["strike", "defend", "wound"],
                                1 if x_cost else 10, draw=_FETCHABLE)
        if play is not None:
            signals |= _effects(play)[0]
    groups = ["scale" if card.card_type is CardType.POWER else "now"]
    if signals & {"damage", "enemy_debuff", "teammate", "all_allies", "team_status"}:
        groups.append("team")
    if signals & {"block", "self_buff", "draw", "energy", "heal", "own_cards", "plays_cards"}:
        groups.append("self")
    props = card.properties
    return {
        "id": card_id,
        "upgraded": upgraded,
        "type": card.card_type.name,
        "target": card.target_type.name,
        "keywords": [k for k, on in (("exhaust", props.exhaust), ("ethereal", props.ethereal),
                                     ("retain", props.retain), ("innate", props.innate),
                                     ("unplayable", not props.playable)) if on],
        "x_cost": x_cost,
        "hits": hits,
        "statuses": statuses,
        "groups": groups,
        "measured": bool(plays),
        "signals": sorted(signals),
    }


def groups(card_ref):
    """The groups of one card (a CardRef or an id)."""
    return list(card_info(str(card_ref), is_upgraded(card_ref))["groups"])


# --- descriptors ---------------------------------------------------------------

def _descriptor(card_ref, holder, cost, damage, block):
    info = card_info(str(card_ref), is_upgraded(card_ref))
    hits = info["hits"] * (holder.energy if info["x_cost"] else 1)
    return {
        "id": info["id"], "upgraded": info["upgraded"], "type": info["type"],
        "cost": cost, "target": info["target"], "keywords": list(info["keywords"]),
        "damage": damage, "hits": hits, "block": block,
        "statuses": {scope: dict(amounts) for scope, amounts in info["statuses"].items()},
        "groups": list(info["groups"]),
    }


def describe_hand(combat, ally):
    """A descriptor per card in `ally`'s hand: cost, damage per hit and Block
    as they stand now - the numbers the hand shows (hand_costs, hand_damages,
    hand_blocks) - and the rest from card_info."""
    costs, damages, blocks = combat.hand_costs(ally), combat.hand_damages(ally), combat.hand_blocks(ally)
    return [_descriptor(card_ref, ally, costs[i], damages[i], blocks[i])
            for i, card_ref in enumerate(ally.hand)]


def describe_card(card_ref, holder):
    """A descriptor for a card out of hand - a pile, the deck, a question's
    option: printed cost, and its own damage and Block before any status."""
    card = create_card(card_ref)
    cost = None if not card.properties.playable else ("X" if card.cost == Card.X_COST else card.cost)
    return _descriptor(card_ref, holder, cost, card.base_damage(holder), card.base_block(holder))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for card_id in known_card_ids():
        plain, plus = card_info(card_id), card_info(card_id, True)
        note = "" if plus["groups"] == plain["groups"] else "   upgraded: " + ", ".join(plus["groups"])
        print("%-22s %-7s %-17s %-44s%s%s" % (
            card_id, plain["type"], ", ".join(plain["groups"]), ", ".join(plain["signals"]),
            "" if plain["measured"] or plain["keywords"].count("unplayable") else "  (could not be played)",
            note))
