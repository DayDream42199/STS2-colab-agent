"""Seeded randomness, one stream per purpose (GameEngine/Context/rng_streams.py).

Same seed and same actions, same fight - in this process and in a fresh one
with a different PYTHONHASHSEED. What the players do never moves the enemies'
moves. Nothing in a fight draws from Python's global, unseeded `random`."""
import hashlib, json, os, random, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Server"))

from session import Session
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Context.rng_streams import RngStreams
from GameEngine.Registry.unit_registry import create_ally, create_enemy, register_ally
from GameEngine.Registry.card_registry import create_card
from GameEngine.Cards._card_enums import TargetType
from GameEngine.Units.Allies._ally import Ally

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


class StreamProbe(Ally):
    """Cards that draw on every stream: random targets, cards made, cards
    picked at random, reshuffles, a card put in the draw pile at random."""
    DEFAULT_MAX_HP = 70
    DEFAULT_HP_VARIANCE = 6
    DEFAULT_DECK = ["sword_boomerang", "infernal_blade", "jackpot", "true_grit", "cinder",
                    "stoke", "rip_and_tear", "strike", "defend", "pommel_strike",
                    "burning_pact", "seeker_strike", "havoc", "metamorphosis", "wish"]
register_ally(StreamProbe)


def send(s, sid, kind, **payload):
    s.handle(sid, encode(kind, **payload))


def fight(seed, skip_first_play=False, turns=8):
    """Two players play the first card they can afford, answer 0, end turn."""
    s = Session(Combat, required_players=2, seed=seed)
    s.ALLY_TYPE_ID = "streamprobe"
    s.ENEMY_TYPE_IDS = ("nibbit", "leafslimemedium", "flyconid")
    s.add_player("a")
    s.add_player("b")
    states, intents, first = [], [], True
    for _ in range(turns):
        if not s.is_running():
            break
        # A dead enemy's intent is whatever it last showed: not a move.
        intents.append([(e.unit_id, e.is_alive(),
                         (e.intent or {}).get("name") if e.is_alive() else None)
                        for e in s.combat.enemies])
        for sid in list(s.players):
            ally = s.players[sid]
            for _attempt in range(10):
                if not s.is_running() or not ally.is_alive():
                    break
                if s.combat.choice_for(ally) is not None:
                    send(s, sid, ClientMessage.CHOOSE, option_index=0)
                    continue
                if first and skip_first_play:
                    break
                plays = [a for a in s.combat.legal_actions(ally) if a["type"] == "play_card"]
                if not plays:
                    break
                send(s, sid, ClientMessage.PLAY_CARD, hand_index=plays[0]["hand_index"],
                     target_id=plays[0]["target_id"])
            first = False
            if s.is_running() and ally.is_alive():
                send(s, sid, ClientMessage.END_TURN)
        states.append(s._state_message())
    return json.dumps(states, sort_keys=True, default=str), intents


def digest(seeds):
    blob = "".join(fight(seed)[0] for seed in seeds)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


if len(sys.argv) > 1 and sys.argv[1] == "--digest":       # the fresh-process half
    print(digest(range(1, 4)))
    sys.exit(0)

print("== the streams ==")
a, b = RngStreams(42), RngStreams(42)
check("same seed, same streams", all(getattr(a, n).random() == getattr(b, n).random()
                                     for n in RngStreams.NAMES))
a = RngStreams(42)
firsts = {getattr(a, n).random() for n in RngStreams.NAMES}
check("each purpose its own sequence", len(firsts) == len(RngStreams.NAMES), len(firsts))
check("a different seed, different streams", RngStreams(42).shuffle.random() != RngStreams(43).shuffle.random())
x = random.Random(5)
check("streams from one random.Random: the same rng state gives the same streams",
      RngStreams.from_rng(random.Random(5)).targets.random() == RngStreams.from_rng(x).targets.random())

print("\n== same seed, same fight ==")
one, _ = fight(11)
two, _ = fight(11)
check("twice in this process", one == two)
check("a different seed is a different fight", fight(12)[0] != one)
here = digest(range(1, 4))
env = dict(os.environ, PYTHONHASHSEED="12345")
there = subprocess.run([sys.executable, __file__, "--digest"], capture_output=True, text=True, env=env)
check("and in a fresh process with another PYTHONHASHSEED",
      there.stdout.strip() == here, (here, there.stdout.strip(), there.stderr[-300:]))

c = Combat([create_ally("ironclad", "p1")], [create_enemy("nibbit", "e1")])
check("a Combat handed no rng still has a seed, to be played again from",
      isinstance(c.seed, int), c.seed)

print("\n== what the players do never moves the enemies' moves ==")
# Compared while the same enemies are alive in both: a dead enemy rolls no
# more moves, which moves the stream for the rest - as in the game, whose
# MonsterAi stream all the monsters share.
_, played = fight(7)
_, held = fight(7, skip_first_play=True)
alive = lambda turn: [living for _, living, _ in turn]
same_lineup = [(x, y) for x, y in zip(played, held) if alive(x) == alive(y)]
check("same seed, one player holding their first turn: every enemy intent the same",
      all(x == y for x, y in same_lineup) and len(same_lineup) >= 3,
      [(x, y) for x, y in same_lineup if x != y][:2] or len(same_lineup))

print("\n== nothing draws from the global random ==")
before = random.getstate()
fight(3)
Combat([create_ally("testally1", "p1")], [create_enemy("leafslimemedium", "e1")]).start()
check("a whole fight, and units built with no rng, leave Python's global random untouched",
      random.getstate() == before)
check("no rng: a ranged HP takes the top of the range, as the game's HP before its roll",
      create_enemy("leafslimemedium", "e1").max_hp == create_enemy("leafslimemedium", "e1").HP_RANGE[1])
check("no rng: a varied HP takes its base number",
      create_ally("testally1", "p1").max_hp == create_ally("testally1", "p1").DEFAULT_MAX_HP)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
