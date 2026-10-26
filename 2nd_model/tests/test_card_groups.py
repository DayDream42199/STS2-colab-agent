"""Card groups and descriptors (Server/Plugins/card_groups.py) and the agent's
plugin that sends them (Server/Plugins/aura.py).

    now     every card that is not a Power        scale   every Power
    team    damages or debuffs an enemy, buffs every player, or touches a
            teammate - or gives you a status that does one of those
    self    gives you Block, buffs you, draws you cards, gives you energy,
            heals you, changes your own cards or plays other cards
"""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session
from plugin_host import PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_enums import CardType
from GameEngine.Cards._card_ref import CardRef
from Plugins.card_groups import GROUPS, STATUS_ROLES, card_info, describe_hand
from Plugins.aura import create_plugin

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def groups(card_id, upgraded=False):
    return card_info(card_id, upgraded)["groups"]


print("== every status has a role, every card a reading ==")
import re
folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server", "GameEngine",
                      "Effects", "StatusEffects")
# The ids, as each status names itself rather than by file name.
ids = set()
for f in os.listdir(folder):
    if f.endswith(".py") and not f.startswith("_"):
        text = open(os.path.join(folder, f), encoding="utf-8").read()
        ids.update(re.findall(r'super\(\).__init__\("(\w+)"', text))
check("every status has an entry in STATUS_ROLES", ids <= set(STATUS_ROLES), sorted(ids - set(STATUS_ROLES)))
check("and STATUS_ROLES names no status that does not exist", set(STATUS_ROLES) <= ids,
      sorted(set(STATUS_ROLES) - ids))

unplayed = []
for card_id in known_card_ids():
    for upgraded in (False, True):
        info = card_info(card_id, upgraded)
        card = create_card(CardRef(card_id, upgraded=upgraded))
        if card.properties.playable and not info["measured"]:
            unplayed.append(card_id)
check("every playable card is really played in the sandbox, plain and upgraded", not unplayed, unplayed)
wrong_type = [c for c in known_card_ids()
              if ("scale" in groups(c)) != (create_card(c).card_type is CardType.POWER)
              or ("now" in groups(c)) == (create_card(c).card_type is CardType.POWER)]
check("now is every non-Power, scale every Power, and never both", not wrong_type, wrong_type)
check("only the four groups", all(set(groups(c)) <= set(GROUPS) for c in known_card_ids()))
lone = [c for c in known_card_ids() if create_card(c).card_type in (CardType.ATTACK, CardType.SKILL, CardType.POWER)
        and not {"team", "self"} & set(groups(c))]
check("every Attack, Skill and Power is team or self (only Statuses and Curses can be neither)",
      not lone, lone)

print("\n== the rules, card by card ==")
cases = [
    ("strike", ["now", "team"], "damage is team"),
    ("defend", ["now", "self"], "Block is self"),
    ("bash", ["now", "team"], "damage and Vulnerable on the enemy"),
    ("shockwave", ["now", "team"], "debuffs every enemy, no damage"),
    ("iron_wave", ["now", "team", "self"], "damage and Block: both"),
    ("lift", ["now", "team"], "Block for a teammate"),
    ("rally", ["now", "team", "self"], "Block for everyone"),
    ("tank", ["scale", "team"], "you take the hits for the others"),
    ("inflame", ["scale", "self"], "Strength for you"),
    ("demon_form", ["scale", "self"], "Strength every turn, when it fires"),
    ("juggernaut", ["scale", "team"], "damage to an enemy, when it fires"),
    ("beacon_of_hope", ["scale", "team"], "the others gain Block, when it fires"),
    ("the_bomb", ["now", "team"], "goes off on every enemy later"),
    ("panic_button", ["now", "self"], "Block; its lockout is a debuff, not a buff"),
    ("battle_trance", ["now", "self"], "draws you cards; its No Draw is a debuff, not a buff"),
    ("bloodletting", ["now", "self"], "gives you energy"),
    ("pommel_strike", ["now", "team", "self"], "damage, and draws you a card"),
    ("huddle_up", ["now", "team", "self"], "everyone draws: you, and a teammate"),
    ("impatience", ["now", "self"], "draws, with no Attack in hand"),
    ("restlessness", ["now", "self"], "draws and gives energy, with an empty hand"),
    ("forgotten_ritual", ["now", "self"], "energy, once a card was exhausted this turn"),
    ("discovery", ["now", "self"], "makes you a card"),
    ("havoc", ["now", "self"], "plays another card, whatever it is"),
    ("not_yet", ["now", "self"], "heals you"),
    ("anointed", ["now", "self"], "fetches your Rare cards"),
    ("purity", ["now", "self"], "exhausts your own cards"),
    ("beat_down", ["now", "team", "self"], "plays your Attacks: damage, and playing cards"),
    ("hellraiser", ["scale", "team", "self"], "plays your Strikes at the enemies"),
    ("slimed", ["now", "self"], "a Status, but it draws a card"),
    ("bolas", ["now", "team"], "damage; coming back to hand is no buff"),
    ("pacts_end", ["now", "team"], "damage, with three cards exhausted"),
    ("wound", ["now"], "an unplayable Status: not a Power, so now"),
]
for card_id, want, why in cases:
    check("%s: %s (%s)" % (card_id, ", ".join(want), why), groups(card_id) == want, groups(card_id))

info = card_info("bash")
check("Bash applies 2 Vulnerable to its target, Bash+ 3",
      info["statuses"]["target"] == {"vulnerable": 2} and card_info("bash", True)["statuses"]["target"] == {"vulnerable": 3},
      (info["statuses"], card_info("bash", True)["statuses"]))
info = card_info("shockwave")
check("Shockwave: Weak and Vulnerable on all enemies",
      set(info["statuses"]["all_enemies"]) == {"weak", "vulnerable"} and not info["statuses"]["target"],
      info["statuses"])
check("Inflame: 2 Strength on self", card_info("inflame")["statuses"]["self"] == {"strength": 2})
check("hits: Strike 1, Twin Strike 2, Sword Boomerang 3, Thunderclap 1 on each enemy",
      [card_info(c)["hits"] for c in ("strike", "twin_strike", "sword_boomerang", "thunderclap")] == [1, 2, 3, 1],
      [card_info(c)["hits"] for c in ("strike", "twin_strike", "sword_boomerang", "thunderclap")])

print("\n== the sandbox stays a sandbox ==")
s = Session(Combat, required_players=1, seed=5)
s.ENEMY_TYPE_IDS = ("nibbit",)
s.add_player("a")
streams = lambda: [getattr(s.rngs, name).getstate() for name in s.rngs.NAMES]
before, global_before, state_before = streams(), random.getstate(), json.dumps(s._state_message(), sort_keys=True)
card_info.cache_clear()
for card_id in ("strike", "sword_boomerang", "discovery", "havoc", "wish"):
    card_info(card_id)
check("reading cards moves none of the fight's random streams, nor the global random",
      streams() == before and random.getstate() == global_before)
check("and changes nothing in the fight", json.dumps(s._state_message(), sort_keys=True) == state_before)

print("\n== the agent's plugin ==")
def session(plugin):
    s = Session(Combat, required_players=2, seed=11, plugin=plugin)
    s.ENEMY_TYPE_IDS = ("nibbit", "leafslimemedium")
    s.add_player("bot")
    if plugin is not None:
        s.handle("bot", encode(ClientMessage.IDENTIFY, role="agent"))
    return s, s.add_player("human")

s, out = session(PluginGuard(create_plugin(), "aura"))
plain, plain_out = session(None)
mine = next(m for to, m in out if to == "bot" and m["type"] == "state")["payload"]["combat"]
theirs = next(m for to, m in out if to == "human" and m["type"] == "state")
check("the human gets exactly the player format", json.dumps(theirs, sort_keys=True)
      == json.dumps(next(m for to, m in plain_out if m["type"] == "state"), sort_keys=True))
check("the agent gets hand_cards and deck_cards for every player, the human none",
      all("hand_cards" in a and "deck_cards" in a for a in mine["allies"])
      and not any("hand_cards" in a for a in theirs["payload"]["combat"]["allies"]))
p1 = s.combat.allies[0]
hand = mine["allies"][0]["hand_cards"]
check("one descriptor per card in hand, in hand order",
      [d["id"] for d in hand] == [str(c) for c in p1.hand], [d["id"] for d in hand])
check("cost, damage and Block as the hand shows them now",
      [d["cost"] for d in hand] == s.combat.hand_costs(p1)
      and [d["damage"] for d in hand] == s.combat.hand_damages(p1)
      and [d["block"] for d in hand] == s.combat.hand_blocks(p1))
check("a teammate's hand is described too (hands are visible)",
      [d["id"] for d in mine["allies"][1]["hand_cards"]] == [str(c) for c in s.combat.allies[1].hand])
draw = mine["allies"][0]["piles"]["draw"]
check("pile entries carry the descriptor and keep the sorted, order-hiding draw pile",
      draw and all("groups" in e and "type" in e for e in draw)
      and [e["id"] for e in draw] == [e["id"] for e in s.combat.pile_view(p1)["draw"]])
check("numbers are game units: no fractions anywhere", all(
    not isinstance(v, float) for d in hand for v in (d["cost"], d["damage"], d["block"], d["hits"])))

s.combat.allies[0].hand = [CardRef("wish")] + list(s.combat.allies[0].hand)
s.combat.allies[0].energy = 3
out = s.handle("bot", encode(ClientMessage.PLAY_CARD, hand_index=0))
question = next((m for to, m in out if to == "bot" and m["type"] == "choice_required"), None)
check("a question for the agent describes each option",
      question is not None and len(question["payload"]["option_cards"]) == len(question["payload"]["options"])
      and all("groups" in d for d in question["payload"]["option_cards"]),
      question and question["payload"].get("option_cards", [])[:1])

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
