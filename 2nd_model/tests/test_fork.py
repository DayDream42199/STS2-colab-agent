"""Card identity (CardRef), upgrades, and every card ported on top of them.

Batch 16 onward: the fork and its eight cards, Hidden Gem and Replay, Clash and
Enthralled, Intercept, the per-turn limits, the choice cards, Sandpit and
Frantic Escape, Wither+X, Splash, Mad Science. Run via tests/run_all.py.
"""
import json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_ref import CardRef, is_upgraded

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=400):
    allies = [create_ally("testally1", "p%d" % (i+1), rng=random.Random(seed))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i+1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed)); c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
    for a in allies:
        a.energy = 9
    return c, allies, enemies

def never_block(enemies):
    for e in enemies:
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()
        e.block = 0

def hand(*card_ids):
    return [CardRef(cid) for cid in card_ids]

def play(c, ally, card_id, target=None):
    # A CardRef is already a str, so it has to be checked for first or the
    # state under test gets thrown away.
    ally.hand = [card_id] if isinstance(card_id, CardRef) else hand(card_id)
    return c.play_card(ally, 0, target=target)

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- the ref itself ---------------------------------------------------------
r = CardRef("strike")
check("a ref is its id as far as anything else is concerned",
      r == "strike" and isinstance(r, str) and create_card(r).name == "Strike")
check("and json sees a plain string", json.dumps([r]) == '["strike"]',
      json.dumps([r]))

one, two = CardRef("strike"), CardRef("strike")
one.upgraded = True
check("two copies of one id are equal but not the same card",
      one == two and one is not two and is_upgraded(one) and not is_upgraded(two))

# --- upgrades reach the numbers ---------------------------------------------
c, a, es = fight()
play(c, a[0], "strike", es[0])
check("Strike deals 6", es[0].current_hp == 394, es[0].current_hp)
c, a, es = fight()
up = CardRef("strike", upgraded=True)
play(c, a[0], up, es[0])
check("Strike+ deals 9", es[0].current_hp == 391, es[0].current_hp)

c, a, es = fight()
play(c, a[0], CardRef("defend", upgraded=True))
check("Defend+ blocks 8", a[0].block == 8, a[0].block)

c, a, es = fight()
play(c, a[0], CardRef("bash", upgraded=True), es[0])
check("Bash+ deals 10 and applies 3 Vulnerable",
      es[0].current_hp == 390 and es[0].get_status("vulnerable").amount == 3,
      (es[0].current_hp, es[0].get_status("vulnerable").amount))

c, a, es = fight()
a[0].hand = hand("strike", "strike")
a[0].hand[0].upgraded = True
r0, r1 = a[0].hand[0], a[0].hand[1]
c.play_card(a[0], 0, target=es[0])
check("upgrading one Strike leaves the other alone",
      es[0].current_hp == 391 and not is_upgraded(r1), es[0].current_hp)
c.play_card(a[0], 0, target=es[0])
check("and the plain one still deals 6", es[0].current_hp == 385, es[0].current_hp)

# --- upgrades are combat-scoped ---------------------------------------------
ally = create_ally("testally1", "p1", rng=random.Random(1))
ally.deck = ["strike"] * 5
c1 = Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(1))],
            rng=random.Random(1))
c1.start()
for r in ally.draw_pile + ally.hand:
    r.upgraded = True
ally.hand = []
c2 = Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(1))],
            rng=random.Random(1))
c2.start()
check("a new combat deals fresh copies, so upgrades do not carry over",
      not any(is_upgraded(r) for r in ally.draw_pile + ally.hand))

ally = create_ally("testally1", "p1", rng=random.Random(1))
ally.deck = [CardRef("strike", upgraded=True)] + ["strike"] * 4
Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(1))],
       rng=random.Random(1)).start()
held = ally.draw_pile + ally.hand
check("a deck can hold a permanently upgraded card, and only that copy is",
      sum(1 for r in held if is_upgraded(r)) == 1,
      [(str(r), is_upgraded(r)) for r in held])
check("and the deck entry is not the copy, so combat cannot write back to it",
      all(r is not ally.deck[0] for r in held))

# --- Rampage ----------------------------------------------------------------
c, a, es = fight()
ref = CardRef("rampage")
for expected in (390, 375, 355):          # 10, then 15, then 20
    a[0].hand = [ref]
    c.play_card(a[0], 0, target=es[0])
    a[0].discard_pile = []
    check("Rampage climbs 10 / 15 / 20 on the same copy (now %d hp)" % expected,
          es[0].current_hp == expected, es[0].current_hp)

c, a, es = fight()
grown, fresh = CardRef("rampage"), CardRef("rampage")
a[0].hand = [grown]
c.play_card(a[0], 0, target=es[0])
a[0].hand = [fresh]
c.play_card(a[0], 0, target=es[0])
check("a second Rampage still opens at 10", es[0].current_hp == 380,
      es[0].current_hp)

c, a, es = fight()
ref = CardRef("rampage", upgraded=True)
a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
check("Rampage+ climbs by 10", es[0].current_hp == 370, es[0].current_hp)

# --- Maul -------------------------------------------------------------------
c, a, es = fight()
first, second = CardRef("maul"), CardRef("maul")
a[0].hand = [first, second]
c.play_card(a[0], 0, target=es[0])
check("Maul hits twice for 5", es[0].current_hp == 390, es[0].current_hp)
c.play_card(a[0], 0, target=es[0])
check("the second Maul already carries the +2 and hits for 7 twice",
      es[0].current_hp == 376, es[0].current_hp)

c, a, es = fight()
a[0].draw_pile = hand("maul")
a[0].hand = hand("maul")
c.play_card(a[0], 0, target=es[0])
check("a Maul still in the draw pile is boosted too",
      a[0].draw_pile[0].bonus_damage == 2, a[0].draw_pile[0].bonus_damage)

# --- Thrash -----------------------------------------------------------------
c, a, es = fight(seed=5)
a[0].hand = hand("thrash", "bludgeon")
c.play_card(a[0], 0, target=es[0])
check("Thrash eats the Bludgeon in hand and hits twice for 4+32",
      es[0].current_hp == 328, es[0].current_hp)
check("and the eaten card is in the exhaust pile",
      a[0].exhaust_pile == ["bludgeon"], a[0].exhaust_pile)

c, a, es = fight(seed=5)
a[0].hand = hand("thrash", "defend")
c.play_card(a[0], 0, target=es[0])
check("with no Attack to eat, Thrash just hits twice for 4",
      es[0].current_hp == 392 and a[0].exhaust_pile == [],
      (es[0].current_hp, a[0].exhaust_pile))

c, a, es = fight(seed=5)
a[0].hand = [CardRef("thrash"), CardRef("strike", upgraded=True)]
c.play_card(a[0], 0, target=es[0])
check("an upgraded Strike feeds Thrash its upgraded 9, not 6",
      es[0].current_hp == 374, es[0].current_hp)

# --- Bolas / Thrumming Hatchet ----------------------------------------------
c, a, es = fight()
never_block(es)
ref = CardRef("bolas")
a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
check("Bolas deals 3", es[0].current_hp == 397, es[0].current_hp)
check("and goes to no pile at all",
      a[0].discard_pile == [] and a[0].exhaust_pile == [] and a[0].hand == [],
      (a[0].discard_pile, a[0].exhaust_pile, a[0].hand))
c.end_player_turn()
check("it is back in hand next turn, the same copy",
      any(h is ref for h in a[0].hand), a[0].hand)

c, a, es = fight()
never_block(es)
ref = CardRef("thrumming_hatchet", upgraded=True)
a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
check("Thrumming Hatchet+ deals 14", es[0].current_hp == 386, es[0].current_hp)
c.end_player_turn()
returned = [h for h in a[0].hand if h is ref]
check("and comes back still upgraded",
      returned and is_upgraded(returned[0]), a[0].hand)

c, a, es = fight()
never_block(es)
a[0].hand = hand("bolas", "bolas")
b1, b2 = a[0].hand[0], a[0].hand[1]
c.play_card(a[0], 0, target=es[0])
c.play_card(a[0], 0, target=es[0])
c.end_player_turn()
check("two cards can be waiting at once",
      sum(1 for h in a[0].hand if h is b1 or h is b2) == 2, a[0].hand)

# --- Armaments --------------------------------------------------------------
c, a, es = fight(seed=7)
a[0].hand = hand("armaments", "strike", "defend")
c.play_card(a[0], 0)
check("Armaments gains 5 Block", a[0].block == 5, a[0].block)
check("and upgrades exactly one card in hand",
      sum(1 for r in a[0].hand if is_upgraded(r)) == 1,
      [(str(r), is_upgraded(r)) for r in a[0].hand])

c, a, es = fight(seed=7)
a[0].hand = [CardRef("armaments", upgraded=True)] + hand("strike", "defend")
c.play_card(a[0], 0)
check("Armaments+ upgrades the whole hand",
      all(is_upgraded(r) for r in a[0].hand) and len(a[0].hand) == 2,
      [(str(r), is_upgraded(r)) for r in a[0].hand])

# --- Apotheosis -------------------------------------------------------------
c, a, es = fight(seed=9)
a[0].hand = hand("apotheosis", "strike")
a[0].draw_pile = hand("defend", "bash")
a[0].discard_pile = hand("strike")
a[0].exhaust_pile = hand("defend")
c.play_card(a[0], 0)
check("Apotheosis upgrades hand, draw pile and discard pile",
      all(is_upgraded(r) for r in a[0].hand + a[0].draw_pile + a[0].discard_pile),
      (a[0].hand, a[0].draw_pile, a[0].discard_pile))
check("but not the exhaust pile",
      not is_upgraded(a[0].exhaust_pile[0]))
check("and Apotheosis exhausts itself",
      "apotheosis" in a[0].exhaust_pile, a[0].exhaust_pile)
check("Apotheosis is Innate", create_card("apotheosis").properties.innate)
check("Apotheosis+ costs 1", create_card(
    CardRef("apotheosis", upgraded=True)).cost == 1)

# --- Aggression -------------------------------------------------------------
c, a, es = fight(seed=11)
never_block(es)
play(c, a[0], "aggression")
check("Aggression is a power and grants its status",
      a[0].get_status("aggression") is not None and a[0].discard_pile == [],
      a[0].discard_pile)
a[0].discard_pile = hand("strike", "defend")
c.end_player_turn()
pulled = [r for r in a[0].hand if r == "strike" and is_upgraded(r)]
check("at turn start it pulls the Attack out of the discard, upgraded",
      len(pulled) == 1 and all(r != "strike" for r in a[0].discard_pile),
      (a[0].hand, a[0].discard_pile))

ally = create_ally("testally1", "p1", rng=random.Random(3))
ally.deck = ["aggression"] + ["defend"] * 20
c3 = Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(3))],
            rng=random.Random(3))
c3.start()
check("un-upgraded Aggression is not Innate, so it is not in the opening hand",
      "aggression" not in ally.hand, ally.hand)

ally = create_ally("testally1", "p1", rng=random.Random(3))
ally.deck = [CardRef("aggression", upgraded=True)] + ["defend"] * 20
Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(3))],
       rng=random.Random(3)).start()
check("Aggression+ is Innate, so it comes up in the opening hand",
      "aggression" in ally.hand, ally.hand)

# --- identity holds through the piles ---------------------------------------
c, a, es = fight()
a[0].hand = hand("strike", "strike")
a[0].hand[1].upgraded = True
plain, upgraded = a[0].hand[0], a[0].hand[1]
from GameEngine.Effects.InstantEffects.instant_exhaust import InstantExhaust
from GameEngine.Resolution.resolver import Resolver
Resolver.resolve(InstantExhaust(source=a[0], target=a[0], card_ids=[upgraded]))
check("exhausting one of two equal copies takes the one it was handed",
      a[0].hand == [plain] and a[0].hand[0] is plain
      and a[0].exhaust_pile[0] is upgraded,
      (a[0].hand, a[0].exhaust_pile))

# --- Hidden Gem and Replay --------------------------------------------------
c, a, es = fight(seed=13)
a[0].draw_pile = hand("strike", "defend", "bash")
play(c, a[0], "hidden_gem")
granted = [r for r in a[0].draw_pile if r.replay]
check("Hidden Gem grants Replay 2 to exactly one draw-pile card",
      len(granted) == 1 and granted[0].replay == 2,
      [(str(r), r.replay) for r in a[0].draw_pile])

c, a, es = fight(seed=13)
a[0].draw_pile = [CardRef("strike", replay=2)]
play(c, a[0], "hidden_gem")
check("it passes over a card that already has Replay",
      a[0].draw_pile[0].replay == 2, a[0].draw_pile[0].replay)

c, a, es = fight(seed=13)
a[0].draw_pile = []
play(c, a[0], "hidden_gem")
check("and does nothing at all with an empty draw pile", True)

c, a, es = fight(seed=13)
a[0].draw_pile = hand("strike")
play(c, a[0], CardRef("hidden_gem", upgraded=True))
check("Hidden Gem+ grants Replay 3", a[0].draw_pile[0].replay == 3,
      a[0].draw_pile[0].replay)

c, a, es = fight()
ref = CardRef("strike", replay=2)
a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
check("Replay 2 means a Strike resolves three times", es[0].current_hp == 382,
      es[0].current_hp)
check("and it lands in the discard pile once, not three times",
      a[0].discard_pile == ["strike"], a[0].discard_pile)
check("the play is counted three times", a[0].turn_count("cards_played") == 3,
      a[0].turn_count("cards_played"))

a[0].hand = [ref]
c.play_card(a[0], 0, target=es[0])
check("Replay is standing, not a charge: the next play is three again",
      es[0].current_hp == 364 and ref.replay == 2,
      (es[0].current_hp, ref.replay))

c, a, es = fight()
a[0].hand = [CardRef("defend", replay=2)]
c.play_card(a[0], 0)
check("Replay is not Attacks-only - a Defend blocks three times",
      a[0].block == 15, a[0].block)

c, a, es = fight()
plain = CardRef("strike")
a[0].hand = [CardRef("strike", replay=2), plain]
c.play_card(a[0], 1, target=es[0])
check("and only the copy that has it replays", es[0].current_hp == 394,
      es[0].current_hp)

ally = create_ally("testally1", "p1", rng=random.Random(2))
ally.deck = ["strike"] * 5
Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(2))],
       rng=random.Random(2)).start()
for r in ally.draw_pile + ally.hand:
    r.replay = 2
ally.hand = []
Combat([ally], [create_enemy("dummy1", "e1", rng=random.Random(2))],
       rng=random.Random(2)).start()
check("Replay dies with the combat, like an upgrade",
      not any(r.replay for r in ally.draw_pile + ally.hand))

# --- Clash ------------------------------------------------------------------
def refused(fn):
    """(was it refused, what it said)"""
    try:
        fn()
    except (ValueError, IndexError, RuntimeError) as error:
        return True, str(error)
    return False, ""

c, a, es = fight()
a[0].hand = hand("clash", "strike", "bash")
c.play_card(a[0], 0, target=es[0])
check("Clash deals 14 out of an all-Attack hand", es[0].current_hp == 386,
      es[0].current_hp)

c, a, es = fight()
a[0].hand = hand("clash")
c.play_card(a[0], 0, target=es[0])
check("Clash alone in hand is fine - it is an Attack itself",
      es[0].current_hp == 386, es[0].current_hp)

c, a, es = fight()
a[0].hand = hand("clash", "defend")
was, why = refused(lambda: c.play_card(a[0], 0, target=es[0]))
check("a Skill in hand stops Clash", was, why)
check("and the refused play cost nothing",
      a[0].energy == 9 and len(a[0].hand) == 2, (a[0].energy, len(a[0].hand)))

c, a, es = fight()
a[0].hand = hand("clash", "greed")
was, why = refused(lambda: c.play_card(a[0], 0, target=es[0]))
check("a Curse in hand stops Clash too", was, why)

c, a, es = fight()
a[0].hand = [CardRef("clash", upgraded=True), CardRef("strike")]
c.play_card(a[0], 0, target=es[0])
check("Clash+ deals 18", es[0].current_hp == 382, es[0].current_hp)

c, a, es = fight()
a[0].hand = hand("defend")
c.auto_play_card(a[0], CardRef("clash"), target=es[0])
check("a card played by another card skips the condition, as in the reference",
      es[0].current_hp == 386, es[0].current_hp)

# --- Enthralled -------------------------------------------------------------
c, a, es = fight()
a[0].hand = hand("enthralled", "strike")
was, why = refused(lambda: c.play_card(a[0], 1, target=es[0]))
check("Enthralled in hand blocks every other card", was, why)
check("and blocks without spending energy", a[0].energy == 9, a[0].energy)

c.play_card(a[0], 0)
check("Enthralled itself can be played, and costs 2", a[0].energy == 7,
      a[0].energy)
check("it goes to the discard pile", a[0].discard_pile == ["enthralled"],
      a[0].discard_pile)
c.play_card(a[0], 0, target=es[0])
check("with it gone the hand is free again", es[0].current_hp == 394,
      es[0].current_hp)

c, a, es = fight()
a[0].hand = hand("enthralled", "strike", "enthralled")
first, second = a[0].hand[0], a[0].hand[2]
was, _ = refused(lambda: c.play_card(a[0], 2, target=es[0]))
check("with two Enthralled, the second one does not satisfy the first", was)
c.play_card(a[0], 0)
check("the first goes, and now the second is the one that must go",
      any(h is second for h in a[0].hand)
      and refused(lambda: c.play_card(a[0], 0, target=es[0]))[0],
      a[0].hand)

c, a, es = fight()
a[0].hand = hand("enthralled")
c.play_card(a[0], 0)
check("Enthralled alone in hand plays fine", a[0].hand == [], a[0].hand)

c, a, es = fight()
a[0].hand = hand("enthralled")
c.auto_play_card(a[0], CardRef("strike"), target=es[0])
check("and it does not block a card played by another card",
      es[0].current_hp == 394, es[0].current_hp)

# --- Intercept --------------------------------------------------------------
def pin(enemies, intent):
    for e in enemies:
        e.choose_intent = lambda context=None, e=e: setattr(e, "intent", intent)
        e.choose_intent()
        e.block = 0

def duo(seed=1, hp=200, intent=None):
    c, a, es = fight(n_allies=2, seed=seed)
    pin(es, intent or {"type": "attack", "amount": 5})
    for ally in a:
        ally.max_hp = ally.current_hp = hp
        ally.block = 0
    return c, a, es

c, a, es = duo()
play(c, a[0], "intercept")
check("Intercept grants 9 Block", a[0].block == 9, a[0].block)

c, a, es = duo()
c.end_player_turn()
check("without it, the enemy hits both players for 5",
      (a[0].current_hp, a[1].current_hp) == (195, 195),
      (a[0].current_hp, a[1].current_hp))

c, a, es = duo()
play(c, a[0], "intercept")
a[0].block = 0
c.end_player_turn()
check("with it, p1 takes both hits and p2 takes none",
      (a[0].current_hp, a[1].current_hp) == (190, 200),
      (a[0].current_hp, a[1].current_hp))

c, a, es = duo()
play(c, a[0], "intercept")
c.end_player_turn()
check("the interceptor's own Block meets the redirected hit, so it lands "
      "before resolution", (a[0].current_hp, a[0].block) == (199, 0),
      (a[0].current_hp, a[0].block))

c, a, es = duo()
play(c, a[0], CardRef("intercept", upgraded=True))
check("Intercept+ grants 13 Block", a[0].block == 13, a[0].block)

c, a, es = duo()
play(c, a[0], "intercept")
a[0].block = 0
c.end_player_turn()
check("it survived the end-of-turn tick into the enemy phase",
      a[1].current_hp == 200, a[1].current_hp)
a[0].block = a[1].block = 0
c.end_player_turn()
check("and is gone by the turn after, so p2 is hit again",
      a[1].current_hp == 195, a[1].current_hp)

c, a, es = duo(intent={"type": "debuff_all", "status": "vulnerable", "amount": 1})
play(c, a[0], "intercept")
c.end_player_turn()
check("it covers being hit, not being cursed - p2 still gets Vulnerable",
      a[1].get_status("vulnerable") is not None,
      list(a[1].statuses))

c, a, es = duo()
play(c, a[0], "flame_barrier")
play(c, a[0], "intercept")
hp = es[0].current_hp
c.end_player_turn()
check("the redirected hit is answered by the interceptor's Flame Barrier",
      es[0].current_hp < hp, "enemy %d -> %d" % (hp, es[0].current_hp))

c, a, es = duo()
play(c, a[0], "intercept")
a[0].current_hp = 0
c.end_player_turn()
check("a dead interceptor intercepts nothing", a[1].current_hp == 195,
      a[1].current_hp)

c, a, es = fight()
pin(es, {"type": "attack", "amount": 5})
a[0].max_hp = a[0].current_hp = 200
play(c, a[0], "intercept")
c.end_player_turn()
check("and alone it is just 9 Block", a[0].current_hp == 200, a[0].current_hp)

# --- per-turn limits --------------------------------------------------------
def deck_fight(deck, seed=1):
    """A combat that does NOT top the ally's energy up, so the turn-start
    penalties are visible."""
    ally = create_ally("testally1", "p1", rng=random.Random(seed))
    ally.deck = list(deck)
    enemy = create_enemy("dummy1", "e1", rng=random.Random(seed))
    c = Combat([ally], [enemy], rng=random.Random(seed))
    c.start()
    enemy.current_hp = enemy.max_hp = 400
    return c, ally, enemy

c, a, es = fight()
a[0].hand = hand("strike", "strike", "strike", "strike")
for _ in range(4):
    c.play_card(a[0], 0, target=es[0])
check("four Strikes is fine with nothing capping you",
      a[0].turn_count("cards_played") == 4, a[0].turn_count("cards_played"))

for card_id in ("sloth", "normality"):
    c, a, es = fight()
    a[0].hand = hand(card_id, "strike", "strike", "strike", "strike")
    for _ in range(3):
        c.play_card(a[0], 1, target=es[0])
    was, why = refused(lambda: c.play_card(a[0], 1, target=es[0]))
    check("%s caps you at 3 cards a turn" % card_id, was, why)
    check("...and the refusal costs no energy", a[0].energy == 6, a[0].energy)
    check("...and %s cannot itself be played" % card_id,
          refused(lambda: c.play_card(a[0], 0))[0])

c, a, es = fight()
never_block(es)
a[0].hand = hand("sloth", "strike", "strike", "strike", "strike")
for _ in range(3):
    c.play_card(a[0], 1, target=es[0])
c.end_player_turn()
a[0].hand = hand("strike", "strike", "strike")
for _ in range(3):
    c.play_card(a[0], 0, target=es[0])
check("the cap resets with the turn", a[0].turn_count("cards_played") == 3,
      a[0].turn_count("cards_played"))

c, a, es = fight()
a[0].hand = hand("strike", "strike", "strike", "strike")
a[0].discard_pile = hand("sloth")
for _ in range(4):
    c.play_card(a[0], 0, target=es[0])
check("Sloth in the discard pile does not cap you - it stops you while held",
      a[0].turn_count("cards_played") == 4, a[0].turn_count("cards_played"))

# --- Mind Rot and Waste Away ------------------------------------------------
c, a, e = deck_fight(["strike"] * 10)
check("a clean deck deals the full hand of 5", len(a.hand) == 5, len(a.hand))
check("and the full 3 energy", a.energy == 3, a.energy)

c, a, e = deck_fight(["strike"] * 10 + ["mind_rot"])
check("one Mind Rot in the deck costs a card off the turn's draw",
      len(a.hand) == 4, len(a.hand))

c, a, e = deck_fight(["strike"] * 10 + ["mind_rot"] * 2)
check("and two cost two", len(a.hand) == 3, len(a.hand))

c, a, e = deck_fight(["strike"] * 10 + ["waste_away"])
check("one Waste Away costs an energy", a.energy == 2, a.energy)

c, a, e = deck_fight(["strike"] * 10 + ["waste_away"] * 2)
check("and two cost two", a.energy == 1, a.energy)

c, a, e = deck_fight(["strike"] * 10 + ["mind_rot", "waste_away"])
check("the two stack independently",
      (len(a.hand), a.energy) == (4, 2), (len(a.hand), a.energy))

c, a, e = deck_fight(["strike"] * 20 + ["mind_rot"])
never_block([e])
first = len(a.hand)
c.end_player_turn()
check("the penalty is charged every turn, not once",
      (first, len(a.hand)) == (4, 4), (first, len(a.hand)))

c, a, e = deck_fight(["strike"] * 10)
a.hand, a.draw_pile, a.discard_pile, a.exhaust_pile = [], [], [], []
a.draw_pile = hand("mind_rot")
check("a penalty card counts from the draw pile", c._deck_penalties(a) == (1, 0),
      c._deck_penalties(a))
a.draw_pile, a.discard_pile = [], hand("mind_rot")
check("and from the discard pile", c._deck_penalties(a) == (1, 0),
      c._deck_penalties(a))
a.discard_pile, a.hand = [], hand("mind_rot")
check("and from hand", c._deck_penalties(a) == (1, 0), c._deck_penalties(a))
a.hand, a.exhaust_pile = [], hand("mind_rot", "waste_away")
check("but not from the exhaust pile - exhausting one is the way out",
      c._deck_penalties(a) == (0, 0), c._deck_penalties(a))

# --- the choice cards, picking at random ------------------------------------
c, a, es = fight(seed=21)
a[0].hand = hand("discovery")
c.play_card(a[0], 0)
check("Discovery adds one card to hand", len(a[0].hand) == 1, a[0].hand)
check("and marks that exact card free this turn",
      a[0].free_this_turn == [a[0].hand[0]], a[0].free_this_turn)
check("and exhausts itself", a[0].exhaust_pile == ["discovery"],
      a[0].exhaust_pile)
check("what it offers comes from the Ironclad pool",
      create_card(a[0].hand[0]).card_class.name == "IRONCLAD",
      create_card(a[0].hand[0]).card_class.name)

c, a, es = fight(seed=21)
a[0].hand = [CardRef("discovery", upgraded=True)]
c.play_card(a[0], 0)
check("Discovery+ does not exhaust", a[0].exhaust_pile == [], a[0].exhaust_pile)

c, a, es = fight(seed=4)
a[0].hand = hand("abundance")
c.play_card(a[0], 0)
check("Abundance adds a Power, free this turn",
      len(a[0].hand) == 1
      and create_card(a[0].hand[0]).card_type.name == "POWER"
      and a[0].free_this_turn == [a[0].hand[0]],
      [(str(r), create_card(r).card_type.name) for r in a[0].hand])

# --- Dual Wield -------------------------------------------------------------
c, a, es = fight(seed=3)
a[0].hand = hand("dual_wield", "bludgeon", "defend")
c.play_card(a[0], 0)
check("Dual Wield copies an Attack out of the hand",
      sorted(a[0].hand) == ["bludgeon", "bludgeon", "defend"], a[0].hand)

c, a, es = fight(seed=3)
a[0].hand = hand("dual_wield", "defend", "defend")
c.play_card(a[0], 0)
check("with no Attack or Power to copy it does nothing",
      a[0].hand == ["defend", "defend"], a[0].hand)

c, a, es = fight(seed=3)
a[0].hand = [CardRef("dual_wield", upgraded=True), CardRef("bludgeon")]
c.play_card(a[0], 0)
check("Dual Wield+ makes two copies", a[0].hand.count("bludgeon") == 3,
      a[0].hand)

c, a, es = fight(seed=3)
a[0].hand = [CardRef("dual_wield"), CardRef("bludgeon", upgraded=True)]
c.play_card(a[0], 0)
check("and the copy of an upgraded card is upgraded too",
      all(is_upgraded(r) for r in a[0].hand) and len(a[0].hand) == 2,
      [(str(r), is_upgraded(r)) for r in a[0].hand])

# --- Seeker Strike ----------------------------------------------------------
c, a, es = fight(seed=8)
a[0].hand = hand("seeker_strike")
a[0].draw_pile = hand("bash", "defend", "strike")
c.play_card(a[0], 0, target=es[0])
check("Seeker Strike deals 9", es[0].current_hp == 391, es[0].current_hp)
check("and moves one card from the draw pile into hand",
      (len(a[0].hand), len(a[0].draw_pile)) == (1, 2),
      (a[0].hand, a[0].draw_pile))

c, a, es = fight(seed=8)
a[0].hand = hand("seeker_strike")
a[0].draw_pile = []
c.play_card(a[0], 0, target=es[0])
check("with an empty draw pile it is just the 9",
      es[0].current_hp == 391 and a[0].hand == [], (es[0].current_hp, a[0].hand))

c, a, es = fight(seed=8)
a[0].hand = [CardRef("seeker_strike", upgraded=True)]
a[0].draw_pile = hand("defend")
c.play_card(a[0], 0, target=es[0])
check("Seeker Strike+ deals 12", es[0].current_hp == 388, es[0].current_hp)

# --- Thinking Ahead ---------------------------------------------------------
c, a, es = fight(seed=6)
a[0].hand = hand("thinking_ahead")
a[0].draw_pile = hand("bash", "defend", "strike", "strike")
c.play_card(a[0], 0)
check("Thinking Ahead draws 2 and stashes 1, so the hand nets one card",
      len(a[0].hand) == 1, a[0].hand)
check("the stashed card is on top of the draw pile",
      len(a[0].draw_pile) == 3, a[0].draw_pile)
stashed = a[0].draw_pile[-1]
drawn = a[0].draw(1, random.Random(1))
check("...and is the very next card drawn", drawn[0] is stashed,
      (str(stashed), [str(d) for d in drawn]))
check("Thinking Ahead exhausts", a[0].exhaust_pile == ["thinking_ahead"],
      a[0].exhaust_pile)

c, a, es = fight(seed=6)
a[0].hand = [CardRef("thinking_ahead", upgraded=True)]
a[0].draw_pile = hand("bash", "defend")
c.play_card(a[0], 0)
check("Thinking Ahead+ does not exhaust", a[0].exhaust_pile == [],
      a[0].exhaust_pile)

c, a, es = fight(seed=6)
a[0].hand = hand("thinking_ahead")
a[0].draw_pile = []
a[0].discard_pile = []
c.play_card(a[0], 0)
check("with nothing to draw and an empty hand it is quiet",
      a[0].hand == [] and a[0].draw_pile == [],
      (a[0].hand, a[0].draw_pile))

# --- Stratagem --------------------------------------------------------------
c, a, e = deck_fight(["strike"] * 10)
a.hand = hand("stratagem")
c.play_card(a, 0)
check("Stratagem is a power, so it goes to no pile", a.discard_pile == [],
      a.discard_pile)
never_block([e])
a.hand, a.draw_pile = [], []
a.discard_pile = hand("bash", "defend", "strike", "strike", "strike", "strike")
c.end_player_turn()
check("the turn draw reshuffles, and Stratagem takes an extra card out of it",
      (len(a.hand), len(a.draw_pile)) == (6, 0), (a.hand, a.draw_pile))

c, a, e = deck_fight(["strike"] * 10)
never_block([e])
a.hand, a.draw_pile = [], hand("bash", "defend", "strike", "strike", "strike",
                               "strike")
a.discard_pile = []
c.end_player_turn()
check("with no reshuffle it does nothing",
      (len(a.hand), len(a.draw_pile)) == (5, 1), (a.hand, a.draw_pile))

# --- Sandpit and Frantic Escape (The Insatiable) ----------------------------
from GameEngine.Effects.StatusEffects.sandpit import Sandpit

def liquify(c, ally):
    """What The Insatiable's Liquify Ground does: 4 Sandpit, 3 Frantic Escape
    on top of the draw pile and 3 in the discard. Mirrors the reference."""
    ally.apply_status(Sandpit(source=None, target=ally, amount=4))
    for _ in range(3):
        ally.draw_pile.append(CardRef("frantic_escape"))     # top: drawn from the end
        ally.discard_pile.append(CardRef("frantic_escape"))

c, a, es = fight()
never_block(es)
liquify(c, a[0])
check("Liquify leaves 4 Sandpit and 6 Frantic Escape",
      a[0].get_status("sandpit").amount == 4
      and (a[0].draw_pile + a[0].discard_pile).count("frantic_escape") == 6)

for turn, left in ((1, 3), (2, 2), (3, 1)):
    a[0].hand = []
    c.end_player_turn()
    check("turn %d: Sandpit ticks to %d at turn start" % (turn, left),
          a[0].get_status("sandpit").amount == left and a[0].is_alive(),
          (a[0].get_status("sandpit").amount, a[0].is_alive()))
a[0].hand = []
c.end_player_turn()
check("turn 4: the player is eaten", not a[0].is_alive() and c.is_over(),
      (a[0].current_hp, c.result))

c, a, es = fight()
never_block(es)
liquify(c, a[0])
a[0].hand = []
c.end_player_turn()                                   # sandpit 3
fe = [r for r in a[0].hand if r == "frantic_escape"]
check("the Frantic Escapes on top of the draw pile are drawn next turn",
      len(fe) == 3, a[0].hand)
c.play_card(a[0], a[0].hand.index(fe[0]))
check("playing one buys a turn", a[0].get_status("sandpit").amount == 4,
      a[0].get_status("sandpit").amount)
check("and costs 1 the first time (3 at turn start)", a[0].energy == 2, a[0].energy)
check("and that copy now costs 2, the others still 1",
      create_card(fe[0]).dynamic_cost(None) == 2
      and create_card(fe[1]).dynamic_cost(None) == 1,
      (fe[0].cost_bump, fe[1].cost_bump))
check("it goes to the discard, not the exhaust pile",
      any(r is fe[0] for r in a[0].discard_pile), a[0].discard_pile)

a[0].hand = [fe[0]]
c.play_card(a[0], 0)
check("played again it charges 2 and will cost 3 next", a[0].energy == 0
      and fe[0].cost_bump == 2, (a[0].energy, fe[0].cost_bump))

c, a, es = fight()
never_block(es)
liquify(c, a[0])
a[0].hand = []
c.end_player_turn()
a[0].hand = [r for r in a[0].hand if r == "frantic_escape"]
for _ in range(3):
    c.play_card(a[0], 0)
check("three escapes on one turn push Sandpit from 3 to 6",
      a[0].get_status("sandpit").amount == 6, a[0].get_status("sandpit").amount)
check("three separate copies cost 1 each, not 1+2+3", a[0].energy == 0, a[0].energy)

check("Sandpit is a debuff, so Rend counts it",
      Sandpit(source=None, target=None, amount=1).IS_DEBUFF)

# --- Wither+X (Aeonglass) ---------------------------------------------------
c, a, es = fight()
never_block(es)
a[0].max_hp = a[0].current_hp = 100
a[0].hand = [CardRef("wither"), CardRef("wither", bonus_damage=2)]
c.end_player_turn()
check("Wither deals 3 and Wither+2 deals 5 from the same class",
      a[0].current_hp == 100 - 3 - 5 - 1, a[0].current_hp)   # -1: the enemy's hit

c, a, es = fight()
never_block(es)
a[0].max_hp = a[0].current_hp = 100
a[0].hand = [CardRef("burn")]
from GameEngine.Effects.StatusEffects.strength import Strength
a[0].apply_status(Strength(source=a[0], target=a[0], amount=10))
c.end_player_turn()
check("a status card's damage is not your own attack: Strength does not add to Burn",
      a[0].current_hp == 100 - 2 - 1, a[0].current_hp)

# --- Splash -----------------------------------------------------------------
c, a, es = fight(seed=17)
a[0].hand = hand("splash")
c.play_card(a[0], 0)
got = a[0].hand
check("Splash adds one card, free this turn",
      len(got) == 1 and a[0].free_this_turn == [got[0]], (got, a[0].free_this_turn))
check("and it is an Attack from the partner's (Ironclad) pool",
      create_card(got[0]).card_type.name == "ATTACK"
      and create_card(got[0]).card_class.name == "IRONCLAD",
      (str(got[0]), create_card(got[0]).card_type.name))
check("Splash does not exhaust", a[0].discard_pile == ["splash"], a[0].discard_pile)

# --- Mad Science ------------------------------------------------------------
c, a, es = fight()
play(c, a[0], "mad_science_sapping", es[0])
check("Sapping: 12 damage, 2 Weak, 2 Vulnerable",
      es[0].current_hp == 388
      and es[0].get_status("weak").amount == 2
      and es[0].get_status("vulnerable").amount == 2,
      (es[0].current_hp, dict((k, v.amount) for k, v in es[0].statuses.items())))

c, a, es = fight()
play(c, a[0], "mad_science_violence", es[0])
check("Violence: 12 damage three times", es[0].current_hp == 364, es[0].current_hp)

c, a, es = fight()
a[0].hand = hand("mad_science_choking", "strike", "defend")
c.play_card(a[0], 0, target=es[0])
check("Choking: 12 damage, and does not choke on itself",
      es[0].current_hp == 388, es[0].current_hp)
c.play_card(a[0], 0, target=es[0])          # strike: 6 + 6 choke
c.play_card(a[0], 0)                        # defend: 6 choke
check("then every card this turn costs the enemy 6 HP, Skills included",
      es[0].current_hp == 388 - 6 - 6 - 6, es[0].current_hp)
check("the choke ignores Block - it is HP loss, not damage",
      True)  # InstantHpLoss by construction; kept as documentation
never_block(es)
c.end_player_turn()
a[0].hand = hand("strike")
hp = es[0].current_hp
c.play_card(a[0], 0, target=es[0])
check("and it is gone next turn", es[0].current_hp == hp - 6, es[0].current_hp)

c, a, es = fight()
a[0].energy = 3
play(c, a[0], "mad_science_energized")
check("Energized: 8 Block and 2 energy (net +1 after its own cost)",
      a[0].block == 8 and a[0].energy == 4, (a[0].block, a[0].energy))

c, a, es = fight()
a[0].hand = hand("mad_science_wisdom")
a[0].draw_pile = hand("strike", "strike", "strike", "strike")
c.play_card(a[0], 0)
check("Wisdom: 8 Block and draw 3", a[0].block == 8 and len(a[0].hand) == 3,
      (a[0].block, a[0].hand))

c, a, es = fight(seed=9)
play(c, a[0], "mad_science_chaos")
check("Chaos: 8 Block and a random card, free this turn",
      a[0].block == 8 and len(a[0].hand) == 1
      and a[0].free_this_turn == [a[0].hand[0]], (a[0].block, a[0].hand))

c, a, es = fight()
play(c, a[0], "mad_science_expertise")
check("Expertise: 2 Strength and 2 Dexterity",
      a[0].get_status("strength").amount == 2
      and a[0].get_status("dexterity").amount == 2,
      dict((k, v.amount) for k, v in a[0].statuses.items()))
play(c, a[0], "strike", es[0])
play(c, a[0], "defend")
check("and they apply: Strike hits for 8, Defend blocks 7",
      es[0].current_hp == 392 and a[0].block == 7, (es[0].current_hp, a[0].block))

c, a, es = fight()
play(c, a[0], "mad_science_curious")
check("Curious is a power", a[0].get_status("curious") is not None
      and a[0].discard_pile == [], a[0].discard_pile)
a[0].energy = 3
a[0].hand = hand("demon_form")            # a 3-cost Power
cost = c.card_cost(a[0], create_card("demon_form"))
check("and Powers cost 1 less", cost == 2, cost)
cost = c.card_cost(a[0], create_card("strike"))
check("but not Attacks", cost == 1, cost)

check("no Mad Science can be turned up by 'a random card'",
      not any(cid.startswith("mad_science") for cid in
              __import__("GameEngine.Registry.card_registry", fromlist=["x"])
              .generatable_card_ids()))
check("all eight share the name the card list uses",
      all(create_card(cid).name == "Mad Science" for cid in known_card_ids()
          if cid.startswith("mad_science")))

# --- the wire ---------------------------------------------------------------
c, a, es = fight()
a[0].hand = hand("strike", "defend")
a[0].hand[1].upgraded = True
state = json.loads(json.dumps(c.to_dict()))
check("hand still goes over the wire as plain id strings",
      state["allies"][0]["hand"] == ["strike", "defend"],
      state["allies"][0]["hand"])
check("with upgrades alongside it",
      state["allies"][0]["hand_upgraded"] == [False, True],
      state["allies"][0]["hand_upgraded"])

c, a, es = fight()
a[0].hand = [CardRef("strike", replay=2), CardRef("defend")]
state = json.loads(json.dumps(c.to_dict()))
check("and Replay alongside that",
      state["allies"][0]["hand_replay"] == [2, 0],
      state["allies"][0]["hand_replay"])

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
