"""The colorless, event, status and curse cards, matched to the game's code.

tests/game_diff.py compares their printed numbers with the installed game
(v0.107.1); this file covers what each one does that the numbers do not show,
read from the decompiled card and power classes. Run via tests/run_all.py.
"""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import (create_card, known_card_ids,
                                               generatable_card_ids, transform_card_ids)
from GameEngine.Cards._card_enums import CardClass, CardRarity, CardType
from GameEngine.Cards._card_ref import CardRef, is_upgraded, replay_of
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.weak import Weak
from GameEngine.Effects.StatusEffects.tag_team import TagTeam as TagTeamMark
from GameEngine.Events.game_event import GameEvent

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
        # A 1-damage swing every turn and no Block, so the numbers stay readable.
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()
        e.block = 0
    for a in allies:
        a.current_hp = a.max_hp = 500
        a.energy = 9
    return c, allies, enemies

def hand(*card_ids):
    return [CardRef(cid) for cid in card_ids]

def play(c, ally, card_id, target=None):
    ally.hand = [card_id] if isinstance(card_id, CardRef) else hand(card_id)
    return c.play_card(ally, 0, target=target)

def next_turn(c, allies):
    c.end_player_turn()
    for a in allies:
        a.energy = 9

def hp(enemies):
    return [e.current_hp for e in enemies]


# --- what "a random card" may be (CardFactory.FilterForCombat) ---------------
events = [cid for cid in known_card_ids() if create_card(cid).rarity is CardRarity.EVENT]
check("the 18 Event cards carry the Event rarity", len(events) == 18, len(events))
anything = set(generatable_card_ids()) | set(generatable_card_ids(solo=True))
check("no Event card is ever made at random", not anything & set(events),
      sorted(anything & set(events)))
check("nor Feed, Hand of Greed or Hidden Gem (CanBeGeneratedInCombat)",
      not anything & {"feed", "hand_of_greed", "hidden_gem"})
check("the colorless pool to draw from is the game's 64, less Alchemize, Hand of "
      "Greed and Hidden Gem", len(generatable_card_ids(card_class=CardClass.COLORLESS)) == 61,
      len(generatable_card_ids(card_class=CardClass.COLORLESS)))
co_op = {"demonic_shield", "tank", "coordinate", "rally", "intercept"}
check("co-op cards are made in a co-op fight",
      co_op <= set(generatable_card_ids()))
check("but never in a solo fight (FilterForPlayerCount)",
      not co_op & set(generatable_card_ids(solo=True)))

seen = set()
for seed in range(30):
    c, a, es = fight(seed=seed)
    play(c, a[0], CardRef("jack_of_all_trades", upgraded=True))
    seen |= set(a[0].hand)
    if len(a[0].hand) != 2 or len(set(a[0].hand)) != 2 or "jack_of_all_trades" in a[0].hand:
        break
check("Jack of All Trades+ adds 2 different colorless cards, never itself",
      len(a[0].hand) == 2 and len(set(a[0].hand)) == 2 and "jack_of_all_trades" not in a[0].hand,
      a[0].hand)
check("and only colorless ones from the colorless pool",
      all(create_card(cid).card_class is CardClass.COLORLESS
          and create_card(cid).rarity is not CardRarity.EVENT for cid in seen), sorted(seen))

# --- Transform (CardFactory.GetDefaultTransformationOptions) -------------------
wound = transform_card_ids("wound")
check("a Wound turns into another Status, never itself",
      wound and all(create_card(cid).card_type is CardType.STATUS for cid in wound)
      and "wound" not in wound, wound)
check("and not one the game never makes in a fight (Frantic Escape, Soot)",
      not {"frantic_escape", "soot"} & set(wound), wound)
check("a Curse into another Curse",
      all(create_card(cid).card_type is CardType.CURSE for cid in transform_card_ids("regret")))
strike = transform_card_ids("strike")
check("a Strike into an Ironclad Common, Uncommon or Rare, not a starter",
      all(create_card(cid).card_class is CardClass.IRONCLAD
          and create_card(cid).rarity in (CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE)
          for cid in strike) and "strike" not in strike, len(strike))
check("an Event card into a colorless one",
      all(create_card(cid).card_class is CardClass.COLORLESS for cid in transform_card_ids("peck")))

for seed in range(10):
    c, a, es = fight(seed=seed)
    play(c, a[0], "entropy")
    # The start of a turn with a Wound in hand; headless, the question is
    # answered at random, and there is only the Wound to pick.
    a[0].hand = hand("wound")
    c._emit(GameEvent.TURN_START, a[0])
    c._drain_asks()
    if not (len(a[0].hand) == 1 and create_card(a[0].hand[0]).card_type is CardType.STATUS
            and a[0].hand[0] != "wound"):
        break
check("Entropy turns a Wound into another Status",
      len(a[0].hand) == 1 and create_card(a[0].hand[0]).card_type is CardType.STATUS
      and a[0].hand[0] != "wound", a[0].hand)

# --- Anointed: as many Rares as the hand has room for -------------------------
c, a, es = fight(seed=4)
rares = hand("bolas", "calamity", "anointed", "rally")
a[0].draw_pile = hand("strike") + rares
a[0].hand = hand("anointed") + hand(*["defend"] * 7)
c.play_card(a[0], 0)
check("Anointed takes 3 Rares into a hand of 7: it is full at 10",
      len(a[0].hand) == 10, len(a[0].hand))
check("and the fourth Rare stays in the draw pile",
      sum(1 for r in a[0].draw_pile if create_card(r).rarity is CardRarity.RARE) == 1,
      a[0].draw_pile)

# --- Catastrophe: one at a time, a playable card over an Unplayable one -------
for seed in range(10):
    c, a, es = fight(seed=seed)
    a[0].draw_pile = hand("wound", "strike", "wound")
    before = hp(es)
    play(c, a[0], "catastrophe")
    if hp(es) == before:
        break
check("Catastrophe plays the Strike over the Wounds, every time",
      hp(es) != before, (hp(es), before))
check("and then a Wound, as nothing playable is left", len(a[0].draw_pile) == 1,
      a[0].draw_pile)

# --- Hidden Gem: a playable card that is not a Curse ---------------------------
picked = set()
for seed in range(20):
    c, a, es = fight(seed=seed)
    a[0].draw_pile = hand("wound", "regret", "strike", "slimed")
    play(c, a[0], "hidden_gem")
    picked |= {str(r) for r in a[0].draw_pile if replay_of(r)}
check("Hidden Gem picks the Strike: an Attack, Skill or Power over a Status",
      picked == {"strike"}, picked)
c, a, es = fight(seed=1)
a[0].draw_pile = hand("regret", "slimed", "wound")
play(c, a[0], "hidden_gem")
check("a playable Status if that is all there is",
      [str(r) for r in a[0].draw_pile if replay_of(r)] == ["slimed"], a[0].draw_pile)
c, a, es = fight(seed=1)
a[0].draw_pile = hand("regret", "wound")
play(c, a[0], "hidden_gem")
check("never a Curse or an Unplayable card",
      not any(replay_of(r) for r in a[0].draw_pile), a[0].draw_pile)

# --- Gang Up: every hit a teammate landed -------------------------------------
c, a, es = fight(n_allies=2, seed=2)
play(c, a[1], "twin_strike", es[0])
before = hp(es)[0]
play(c, a[0], "gang_up", es[0])
check("a teammate's Twin Strike is two hits: 5 + 2 x 5",
      es[0].current_hp == before - 15, before - es[0].current_hp)

# --- Knockdown: x2 (x3 upgraded) from the others, until its turn ends --------
c, a, es = fight(n_allies=2, seed=2)
play(c, a[0], "knockdown", es[0])
before = hp(es)[0]
play(c, a[1], "strike", es[0])
check("Knockdown: a teammate's Strike hits for 2 x 6", es[0].current_hp == before - 12,
      before - es[0].current_hp)
before = hp(es)[0]
play(c, a[0], "strike", es[0])
check("the one who applied it hits for 6", es[0].current_hp == before - 6,
      before - es[0].current_hp)
c.end_player_turn()
check("gone once the enemy's turn ends", es[0].get_status("exposed") is None)

c, a, es = fight(n_allies=2, seed=2)
before = hp(es)[0]
play(c, a[0], CardRef("knockdown", upgraded=True), es[0])
check("Knockdown+ deals 14", es[0].current_hp == before - 14, before - es[0].current_hp)
before = hp(es)[0]
play(c, a[1], "strike", es[0])
check("and makes it 3 x 6 for the teammate", es[0].current_hp == before - 18,
      before - es[0].current_hp)

c, a, es = fight(n_allies=3, seed=2)
play(c, a[0], "knockdown", es[0])
play(c, a[1], "knockdown", es[0])
before = hp(es)[0]
play(c, a[2], "strike", es[0])
check("two players' Knockdowns are two: the third player hits for 4 x 6",
      es[0].current_hp == before - 24, before - es[0].current_hp)
before = hp(es)[0]
play(c, a[0], "strike", es[0])
check("and each applier is doubled only by the other's", es[0].current_hp == before - 12,
      before - es[0].current_hp)

# --- Panache: counts from when it is played, unpowered ----------------------
c, a, es = fight(n_enemies=2, seed=5)
a[0].apply_status(Strength(source=a[0], target=a[0], amount=5))
play(c, a[0], "defend")
play(c, a[0], "defend")
play(c, a[0], "panache")
for _ in range(4):
    play(c, a[0], "defend")
before = hp(es)
check("Panache played third: no hit at the turn's fifth card", before == [400, 400], before)
play(c, a[0], "defend")
check("but at the fifth card after it: 10 to every enemy, Strength not added",
      hp(es) == [390, 390], hp(es))
next_turn(c, a)
for _ in range(4):
    play(c, a[0], "defend")
check("the count starts again each turn", hp(es) == [390, 390], hp(es))
play(c, a[0], "defend")
check("and fires at the fifth card of the new turn", hp(es) == [380, 380], hp(es))

c, a, es = fight(seed=5)
play(c, a[0], CardRef("panache", upgraded=True))
for _ in range(5):
    play(c, a[0], "defend")
check("Panache+ deals 14", hp(es) == [386], hp(es))

# --- The Bomb: each its own countdown and damage ---------------------------
c, a, es = fight(seed=6)
play(c, a[0], "the_bomb")
next_turn(c, a)
play(c, a[0], CardRef("the_bomb", upgraded=True))
next_turn(c, a)
before = hp(es)[0]
c.end_player_turn()
check("the first Bomb goes off at the end of its third turn, for 40",
      es[0].current_hp == before - 40, before - es[0].current_hp)
for ally in a:
    ally.energy = 9
before = hp(es)[0]
c.end_player_turn()
check("the second a turn later, for 50 (The Bomb+)", es[0].current_hp == before - 50,
      before - es[0].current_hp)

# --- Rolling Boulder: each rolls and grows on its own -------------------------
c, a, es = fight(seed=7)
play(c, a[0], "rolling_boulder")
play(c, a[0], "rolling_boulder")
before = hp(es)[0]
next_turn(c, a)
check("two Boulders roll for 5 + 5", es[0].current_hp == before - 10, before - es[0].current_hp)
before = hp(es)[0]
next_turn(c, a)
check("and then 10 + 10: each grows by 5", es[0].current_hp == before - 20,
      before - es[0].current_hp)

# --- Panic Button: no Block from cards, Block from elsewhere still lands ------
c, a, es = fight(seed=8)
play(c, a[0], "panic_button")
check("Panic Button gives 30", a[0].block == 30, a[0].block)
play(c, a[0], "defend")
check("then a Defend gives nothing", a[0].block == 30, a[0].block)
play(c, a[0], "entrench")
check("but Entrench's doubling is unpowered and lands (NoBlockPower)", a[0].block == 60,
      a[0].block)

# --- next-turn Energy and draw are amounts, not turns -------------------------
c, a, es = fight(seed=9)
play(c, a[0], "relax")
check("Relax gives 15 Block", a[0].block == 15, a[0].block)
a[0].draw_pile = hand(*["defend"] * 12)
c.end_player_turn()
check("next turn, 2 more Energy and 2 more cards", (a[0].energy, len(a[0].hand)) == (5, 7),
      (a[0].energy, len(a[0].hand)))
c, a, es = fight(seed=9)
play(c, a[0], CardRef("relax", upgraded=True))
check("Relax+ gives 17 Block", a[0].block == 17, a[0].block)
a[0].draw_pile = hand(*["defend"] * 12)
c.end_player_turn()
check("and 3 Energy and 3 cards", (a[0].energy, len(a[0].hand)) == (6, 8),
      (a[0].energy, len(a[0].hand)))
c, a, es = fight(seed=9)
play(c, a[0], CardRef("outmaneuver", upgraded=True))
play(c, a[0], "outmaneuver")
c.end_player_turn()
check("Outmaneuver+ and Outmaneuver add up: 3 + 2 more Energy", a[0].energy == 8, a[0].energy)

# --- powers that stack do more, not longer -------------------------------------
c, a, es = fight(seed=10)
play(c, a[0], "calamity")
play(c, a[0], "calamity")
play(c, a[0], "strike", es[0])
check("two Calamities: an Attack played adds 2 Attacks", len(a[0].hand) == 2, a[0].hand)

c, a, es = fight(seed=10)
play(c, a[0], "hello_world")
play(c, a[0], "hello_world")
c.end_player_turn()
check("two Hello Worlds: 2 Commons, different ones, on top of the hand of 5",
      len(a[0].hand) == 7 and len(set(a[0].hand[5:])) == 2, a[0].hand)

c, a, es = fight(seed=10)
play(c, a[0], "mayhem")
play(c, a[0], "mayhem")
a[0].draw_pile = hand(*["defend"] * 5) + hand("strike", "strike") + hand(*["defend"] * 5)
before = hp(es)[0]
c.end_player_turn()
# The hand is drawn first (the five on top), then Mayhem plays the next two.
check("two Mayhems play the top two cards after the draw", es[0].current_hp == before - 12,
      before - es[0].current_hp)

c, a, es = fight(seed=10)
play(c, a[0], "stratagem")
play(c, a[0], "stratagem")
a[0].draw_pile = []
a[0].discard_pile = hand("strike", "defend", "bash", "anger")
a[0].hand = hand("flash_of_steel")
c.play_card(a[0], 0, target=es[0])
# Four reshuffled: one drawn by Flash of Steel, two taken, one left.
check("two Stratagems take 2 cards out of the reshuffled pile",
      len(a[0].hand) == 3 and len(a[0].draw_pile) == 1, (a[0].hand, a[0].draw_pile))

c, a, es = fight(seed=10)
play(c, a[0], "nostalgia")
a[0].draw_pile = []
play(c, a[0], "master_of_strategy")
play(c, a[0], "strike", es[0])
check("Nostalgia counts the Skill that Exhausted: the Strike goes to the discard",
      "strike" in a[0].discard_pile and "strike" not in a[0].draw_pile,
      (a[0].discard_pile, a[0].draw_pile))

# --- Tag Team: an attack on the marked enemy, or one at every enemy ----------
c, a, es = fight(n_allies=2, n_enemies=2, seed=11)
play(c, a[0], "tag_team", es[0])
before = hp(es)
play(c, a[1], "thunderclap")
# 4, then 6 on enemies the first play made Vulnerable.
check("a teammate's Thunderclap hits everyone, so it is played twice",
      [b - h for b, h in zip(before, hp(es))] == [10, 10], [b - h for b, h in zip(before, hp(es))])
c, a, es = fight(n_allies=2, n_enemies=1, seed=11)
play(c, a[0], "tag_team", es[0])
before = hp(es)[0]
play(c, a[1], "sword_boomerang")
check("a random-target Sword Boomerang is not (the game's TagTeamPower)",
      es[0].current_hp == before - 9 and es[0].get_status("tag_team") is not None,
      (before - es[0].current_hp, list(es[0].statuses)))

# --- Discovery and Splash: may be skipped; Splash+ offers upgraded Attacks ----
c, a, es = fight(seed=12)
c.ask_players = True
play(c, a[0], CardRef("splash", upgraded=True))
ask = c.pending_choices[a[0].unit_id]
check("Splash's question may be skipped (canSkip)", ask.can_stop)
check("and Splash+ offers its Attacks upgraded",
      all(is_upgraded(o) for o in ask.options), [(str(o), is_upgraded(o)) for o in ask.options])

# --- Normality stops a card that plays itself too (ShouldPlay) ---------------
def normality_havoc(held):
    c, a, es = fight(seed=13)
    a[0].hand = hand(*held, "strike", "strike", "havoc")
    a[0].draw_pile = hand("strike")
    first = len(held)
    c.play_card(a[0], first, target=es[0])
    c.play_card(a[0], first, target=es[0])
    before = hp(es)[0]
    c.play_card(a[0], first)          # Havoc, the third play
    return before - es[0].current_hp, a[0]
dealt, ally = normality_havoc([])
check("Havoc as a third card plays the Strike it turns up", dealt == 6, dealt)
dealt, ally = normality_havoc(["normality"])
check("holding Normality, that Strike is the fourth play started: not played", dealt == 0, dealt)
check("it is still taken off the pile and Exhausted, as Havoc's card",
      "strike" in ally.exhaust_pile and ally.draw_pile == [], (ally.exhaust_pile, ally.draw_pile))

# --- Tag Team: one mark per player who played it -------------------------------
c, a, es = fight(n_allies=2, seed=14)
play(c, a[0], "tag_team", es[0])
before = hp(es)[0]
play(c, a[1], "tag_team", es[0])
check("Tag Team is an Attack: p2's on p1's mark is played twice, 11 + 11",
      es[0].current_hp == before - 22, before - es[0].current_hp)
check("and leaves two marks of p2's", [m[0] for m in es[0].get_status("tag_team").marks] == [a[1], a[1]],
      [m[0].unit_id for m in es[0].get_status("tag_team").marks])

def marked_by(c, a, es, *appliers):
    for applier in appliers:
        es[0].apply_status(TagTeamMark(source=applier, target=es[0], amount=1))
c, a, es = fight(n_allies=3, seed=14)
marked_by(c, a, es, a[0], a[1])
before = hp(es)[0]
play(c, a[2], "strike", es[0])
check("p1's and p2's marks are two: a third player's Strike is played 3 times",
      es[0].current_hp == before - 18, before - es[0].current_hp)
c, a, es = fight(n_allies=3, seed=14)
marked_by(c, a, es, a[0], a[1])
before = hp(es)[0]
play(c, a[0], "strike", es[0])
check("p1's Strike sets off only p2's mark", es[0].current_hp == before - 12,
      before - es[0].current_hp)
check("and p1's own mark is still there for somebody else",
      [m[0] for m in es[0].get_status("tag_team").marks] == [a[0]],
      [m[0].unit_id for m in es[0].get_status("tag_team").marks])

# --- Beacon of Hope: two Beacons answer each other once ------------------------
c, a, es = fight(n_allies=2, seed=15)
play(c, a[0], "beacon_of_hope")
play(c, a[1], "beacon_of_hope")
play(c, a[0], "the_gambit")
check("p1's 50 gives p2 25, p2's Beacon gives back 12, and it stops there",
      (a[0].block, a[1].block) == (62, 25), (a[0].block, a[1].block))

# --- before the hand is drawn (BeforeHandDraw) ---------------------------------
ok = True
for seed in range(12):
    c, a, es = fight(seed=seed)
    ref = CardRef("bolas")
    play(c, a[0], ref, es[0])
    a[0].draw_pile = []
    a[0].discard_pile = [ref] + hand(*["strike"] * 5)
    c.end_player_turn()
    if not (len(a[0].hand) == 6 and any(h is ref for h in a[0].hand)):
        ok = False
        break
check("Bolas comes back before the draw: it is never drawn, the hand is it plus 5", ok,
      a[0].hand)
c, a, es = fight(seed=16)
play(c, a[0], "hello_world")
a[0].draw_pile = hand(*["wound"] * 5)
c.end_player_turn()
check("Hello World's card is in hand before the 5 drawn",
      len(a[0].hand) == 6 and create_card(a[0].hand[0]).rarity is CardRarity.COMMON
      and all(h == "wound" for h in a[0].hand[1:]), a[0].hand)

# --- Doubt and Shame: only a new Weak or Frail skips its count-down -----------
def charges(unit, effect_id):
    status = unit.get_status(effect_id)
    return status.amount if status is not None else 0
c, a, es = fight(seed=17)
a[0].hand = hand("doubt")
c.end_player_turn()
check("Doubt on a player with no Weak: 1 Weak, still there for their turn",
      charges(a[0], "weak") == 1, charges(a[0], "weak"))
c, a, es = fight(seed=17)
a[0].apply_status(Weak(source=es[0], target=a[0], amount=2))
a[0].hand = hand("doubt")
c.end_player_turn()
check("on one who had 2 already: 3, then down to 2 like the rest (PowerCmd.Apply)",
      charges(a[0], "weak") == 2, charges(a[0], "weak"))

# --- printed values that drive play -----------------------------------------
check("Toxic can be played, for 1, and Exhausts",
      create_card("toxic").properties.playable and create_card("toxic").cost == 1
      and create_card("toxic").properties.exhaust)
check("Giant Rock deals 16, 20 upgraded (Primal Force+ makes them upgraded)",
      (create_card("giant_rock").DAMAGE, create_card(CardRef("giant_rock", upgraded=True)).DAMAGE)
      == (16, 20))

print()
print("%d checks failed" % len(bad))
for line in bad:
    print("   ", line)
sys.exit(1 if bad else 0)
