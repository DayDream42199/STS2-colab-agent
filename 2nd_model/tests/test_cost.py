"""Batch 13: cost modification and X-cost."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def charges(unit, effect_id):
    """What a counter status has left - 0 once it is gone."""
    status = unit.get_status(effect_id)
    return status.amount if status is not None else 0


def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=400):
    allies = [create_ally("testally1", "p%d" % (i+1), rng=random.Random(seed))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i+1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed)); c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
    for a in allies:
        a.energy = 3
    return c, allies, enemies

def play(c, ally, card_id, target=None):
    ally.hand = [card_id]
    return c.play_card(ally, 0, target=target)

check("registry has 219 cards", len(known_card_ids()) == 219, len(known_card_ids()))

# --- Stomp: 1 less per Attack played this turn ------------------------------
c, a, es = fight(n_enemies=2, seed=2)
check("Stomp starts at 3", c.card_cost(a[0], create_card("stomp")) == 3,
      c.card_cost(a[0], create_card("stomp")))
a[0].energy = 9
play(c, a[0], "strike", es[0])
check("one Attack played -> Stomp costs 2",
      c.card_cost(a[0], create_card("stomp")) == 2,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "defend")
check("a Skill does not make Stomp cheaper",
      c.card_cost(a[0], create_card("stomp")) == 2,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "strike", es[0])
play(c, a[0], "strike", es[0])
check("three Attacks -> Stomp is free",
      c.card_cost(a[0], create_card("stomp")) == 0,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "strike", es[0])
check("Stomp never goes below 0",
      c.card_cost(a[0], create_card("stomp")) == 0,
      c.card_cost(a[0], create_card("stomp")))

c, a, es = fight(n_enemies=2, seed=2)
a[0].energy = 9
for _ in range(3):
    play(c, a[0], "strike", es[0])
before = a[0].energy
hp = [e.current_hp for e in es]
play(c, a[0], "stomp")
check("Stomp at 0 spends nothing", a[0].energy == before, a[0].energy)
check("Stomp hits all enemies for 12",
      [e.current_hp for e in es] == [h - 12 for h in hp],
      [e.current_hp for e in es])
c.end_player_turn()
check("the discount resets next turn",
      c.card_cost(a[0], create_card("stomp")) == 3,
      c.card_cost(a[0], create_card("stomp")))

# --- the combat-wide exhaust tally, by anyone --------------------------------
# Midnight read this; Midnight is gone from the game, the tally is kept.
c, a, es = fight(seed=3)
a[0].energy = 9
a[0].hand = ["cinder", "strike", "defend"]
c.play_card(a[0], 0, target=es[0])        # Cinder exhausts a card + itself
exhausted = c.combat_counters.get("cards_exhausted", 0)
check("exhausting cards is counted combat-wide", exhausted > 0, exhausted)
c.end_player_turn()
check("the tally survives the turn boundary",
      c.combat_counters.get("cards_exhausted", 0) == exhausted,
      c.combat_counters.get("cards_exhausted", 0))

c, a, es = fight(n_allies=2, seed=3)
a[1].energy = 9
a[1].hand = ["cinder", "strike", "defend"]
c.play_card(a[1], 0, target=es[0])
check("another player's exhausts count in the same tally",
      c.combat_counters.get("cards_exhausted", 0) > 0,
      c.combat_counters.get("cards_exhausted", 0))

# --- Unrelenting: the next Attack costs 0 -----------------------------------
c, a, es = fight(seed=4)
a[0].energy = 3
play(c, a[0], "unrelenting", es[0])
check("Unrelenting deals 14", es[0].current_hp == 386, es[0].current_hp)
check("Unrelenting cost its own 2", a[0].energy == 1, a[0].energy)
check("it grants one free Attack, as a status the player can see",
      charges(a[0], "free_attack") == 1, a[0].statuses.keys())
play(c, a[0], "defend")
check("a Skill does not spend the grant", charges(a[0], "free_attack") == 1)
check("and the Skill still cost its 1", a[0].energy == 0, a[0].energy)
play(c, a[0], "strike", es[0])
check("the next Attack is free", a[0].energy == 0, a[0].energy)
check("the grant is spent, and the status gone", a[0].get_status("free_attack") is None)

c, a, es = fight(seed=4)
a[0].energy = 2
play(c, a[0], "unrelenting", es[0])
c.end_player_turn()
check("the grant has no deadline - it survives the turn",
      charges(a[0], "free_attack") == 1, charges(a[0], "free_attack"))

# --- Corruption: Skills cost 0 and Exhaust ----------------------------------
c, a, es = fight(seed=5)
a[0].energy = 9
play(c, a[0], "corruption")
check("Corruption zeroes a Skill's cost",
      c.card_cost(a[0], create_card("defend")) == 0,
      c.card_cost(a[0], create_card("defend")))
check("Attacks still cost", c.card_cost(a[0], create_card("strike")) == 1,
      c.card_cost(a[0], create_card("strike")))
before = a[0].energy
play(c, a[0], "defend")
check("playing a Skill spends nothing", a[0].energy == before, a[0].energy)
check("the Skill is exhausted, not discarded",
      a[0].exhaust_pile == ["defend"] and "defend" not in a[0].discard_pile,
      (a[0].exhaust_pile, a[0].discard_pile))
play(c, a[0], "strike", es[0])
check("an Attack still goes to the discard", "strike" in a[0].discard_pile,
      a[0].discard_pile)
check("Corruption is permanent", a[0].get_status("corruption") is not None)
c.end_player_turn()
check("Corruption survives the turn", a[0].get_status("corruption") is not None)

# --- Enlightenment: everything costs at most 1 ------------------------------
c, a, es = fight(seed=6)
a[0].energy = 9
check("Bludgeon normally costs 3",
      c.card_cost(a[0], create_card("bludgeon")) == 3,
      c.card_cost(a[0], create_card("bludgeon")))
play(c, a[0], "enlightenment")
check("Enlightenment caps Bludgeon at 1",
      c.card_cost(a[0], create_card("bludgeon")) == 1,
      c.card_cost(a[0], create_card("bludgeon")))
check("it does not raise a card that already costs 0",
      c.card_cost(a[0], create_card("anger")) == 0,
      c.card_cost(a[0], create_card("anger")))
check("Enlightenment exhausts itself", a[0].exhaust_pile == ["enlightenment"],
      a[0].exhaust_pile)
c.end_player_turn()
check("the cap is gone next turn",
      c.card_cost(a[0], create_card("bludgeon")) == 3,
      c.card_cost(a[0], create_card("bludgeon")))
check("the status itself expired",
      a[0].get_status("enlightenment") is None, a[0].statuses)

c, a, es = fight(seed=6)
a[0].energy = 9
play(c, a[0], "corruption")
play(c, a[0], "enlightenment")
check("Corruption's 0 for Skills survives Enlightenment's cap",
      c.card_cost(a[0], create_card("defend")) == 0,
      c.card_cost(a[0], create_card("defend")))

# --- X-cost -----------------------------------------------------------------
c, a, es = fight(n_enemies=2, seed=7)
a[0].energy = 3
check("an X card costs everything you have",
      c.card_cost(a[0], create_card("whirlwind")) == 3,
      c.card_cost(a[0], create_card("whirlwind")))
hp = [e.current_hp for e in es]
play(c, a[0], "whirlwind")
check("Whirlwind hits all enemies X times for 5",
      [e.current_hp for e in es] == [h - 15 for h in hp],
      [e.current_hp for e in es])
check("Whirlwind drained the energy", a[0].energy == 0, a[0].energy)

c, a, es = fight(n_enemies=2, seed=7)
a[0].energy = 0
hp = [e.current_hp for e in es]
play(c, a[0], "whirlwind")
check("Whirlwind at 0 energy is a legal no-op",
      [e.current_hp for e in es] == hp, [e.current_hp for e in es])

c, a, es = fight(n_enemies=3, seed=8)
a[0].energy = 2
total_before = sum(e.current_hp for e in es)
play(c, a[0], "volley")
check("Volley fires X shots of 10",
      sum(e.current_hp for e in es) == total_before - 20,
      sum(e.current_hp for e in es))

c, a, es = fight(seed=9)
a[0].energy = 2
a[0].draw_pile = ["defend", "strike", "strike"]   # top two are strikes
hp = es[0].current_hp
play(c, a[0], "cascade")
check("Cascade plays the top X cards", es[0].current_hp == hp - 12,
      es[0].current_hp)
check("Cascade took them off the draw pile", a[0].draw_pile == ["defend"],
      a[0].draw_pile)

c, a, es = fight(seed=9)
a[0].energy = 5
a[0].draw_pile = ["strike"]
hp = es[0].current_hp
play(c, a[0], "cascade")
check("Cascade copes with a short draw pile", es[0].current_hp == hp - 6,
      es[0].current_hp)

# --- an auto-played X card has no energy behind it --------------------------
c, a, es = fight(n_enemies=2, seed=10)
a[0].energy = 9
a[0].draw_pile = ["whirlwind"]
hp = [e.current_hp for e in es]
play(c, a[0], "havoc")
check("Havoc playing Whirlwind deals nothing - nobody paid for it",
      [e.current_hp for e in es] == hp, [e.current_hp for e in es])
check("but it was still played and exhausted",
      a[0].exhaust_pile == ["whirlwind"], a[0].exhaust_pile)

# --- the free-play tally still wins over a dynamic cost ---------------------
c, a, es = fight(seed=11)
a[0].energy = 0
a[0].free_this_turn = ["bludgeon"]
a[0].hand = ["bludgeon"]
c.play_card(a[0], 0, target=es[0])
check("a free grant beats a 3-cost card at 0 energy", es[0].current_hp == 368,
      es[0].current_hp)

# --- hand_cost: what each card in hand costs, sent with the state -----------
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Effects.StatusEffects.tangled import Tangled

def wire_costs(c, ally):
    return next(d for d in c.to_dict()["allies"] if d["unit_id"] == ally.unit_id)["hand_cost"]

c, a, es = fight(n_allies=2, n_enemies=2, seed=12)
a[0].energy = 9
a[0].hand = ["strike", "bash", "whirlwind", "burn", "stomp",
             CardRef("frantic_escape", cost_bump=2)]
check("printed costs, X, unplayable as None, and a copy's own bump",
      wire_costs(c, a[0]) == [1, 2, "X", None, 3, 3], wire_costs(c, a[0]))
check("one entry per card in hand, for every ally",
      all(len(d["hand_cost"]) == len(d["hand"]) for d in c.to_dict()["allies"]),
      [(len(d["hand"]), len(d["hand_cost"])) for d in c.to_dict()["allies"]])

a[0].hand.insert(0, "strike")
c.play_card(a[0], 0, target=es[0])
check("Stomp's discount shows as soon as an Attack is played",
      wire_costs(c, a[0])[4] == 2, wire_costs(c, a[0]))

a[0].apply_status(Tangled(source=es[0], target=a[0], amount=1))
check("Tangled adds 1 to Attacks only",
      wire_costs(c, a[0])[:2] == [2, 3] and wire_costs(c, a[0])[3] is None,
      wire_costs(c, a[0]))

a[0].free_this_turn = ["bash"]
check("a free grant shows 0", wire_costs(c, a[0])[1] == 0, wire_costs(c, a[0]))

c, a, es = fight(seed=13)
a[0].energy = 9
play(c, a[0], "corruption")
a[0].hand = ["defend", "strike"]
check("Corruption: Skills show 0, Attacks keep their cost",
      wire_costs(c, a[0]) == [0, 1], wire_costs(c, a[0]))

# --- hand_damage: one hit, after your Strength and Weak, before the target ----
from GameEngine.Cards._card_enums import CardType, TargetType
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.weak import Weak
from GameEngine.Effects.StatusEffects.vigor import Vigor
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable

def wire_damage(c, ally):
    return next(d for d in c.to_dict()["allies"] if d["unit_id"] == ally.unit_id)["hand_damage"]

c, a, es = fight(seed=14)
p = a[0]
p.hand = ["strike", "defend", "twin_strike", "burn", CardRef("bash", upgraded=True)]
check("Attacks show their printed hit, everything else None",
      wire_damage(c, p) == [6, None, 5, None, 10], wire_damage(c, p))
p.apply_status(Strength(source=p, target=p, amount=2))
check("Strength adds to every hit", wire_damage(c, p) == [8, None, 7, None, 12],
      wire_damage(c, p))
p.apply_status(Weak(source=p, target=p, amount=1))
check("Weak takes a quarter off, rounded down", wire_damage(c, p) == [6, None, 5, None, 9],
      wire_damage(c, p))
es[0].apply_status(Vulnerable(source=p, target=es[0], amount=2))
check("the target's Vulnerable is not in it - no target is chosen yet",
      wire_damage(c, p) == [6, None, 5, None, 9], wire_damage(c, p))

c, a, es = fight(seed=15)
p = a[0]
p.apply_status(Vigor(source=p, target=p, amount=3))
p.hand = ["strike"]
wire_damage(c, p)
check("showing Vigor's bonus does not spend it", wire_damage(c, p) == [9]
      and p.get_status("vigor") is not None, (wire_damage(c, p), p.statuses.keys()))

c, a, es = fight(seed=16)
p = a[0]
p.hand = ["body_slam", "mind_blast", "pacts_end", "ashen_strike"]
p.block, p.draw_pile, p.exhaust_pile = 7, ["strike"] * 4, ["defend"] * 2
check("worked-out damage: Body Slam = Block, Mind Blast = draw pile, "
      "Pact's End 0 below 3 exhausted, Ashen Strike +3 per exhausted",
      wire_damage(c, p) == [7, 4, 0, 12], wire_damage(c, p))
p.exhaust_pile.append("defend")
check("Pact's End shows 17 once 3 cards are exhausted", wire_damage(c, p)[2] == 17,
      wire_damage(c, p))

# Every Attack, plain and upgraded, played for real: its first hit is the
# number the state showed, with and without Strength, Weak and Vigor.
def first_hit(card_id, upgraded, setup):
    c, a, es = fight(seed=17, enemy_hp=999)
    p, foe = a[0], es[0]
    p.energy = 20
    p.deck = ["strike"] * 5 + ["defend"] * 5
    p.exhaust_pile = [CardRef("strike") for _ in range(3)]
    p.draw_pile = [CardRef("strike") for _ in range(6)]
    play(c, p, "defend")                        # one card played, and Block
    foe.block = 0
    ref = CardRef(card_id, upgraded=upgraded)
    card = create_card(ref)
    p.hand = [ref, CardRef("strike"), CardRef("defend"), CardRef("strike")]
    if not card.playable_now(p):                # Clash wants a hand of Attacks
        p.hand = [ref, CardRef("strike"), CardRef("strike")]
    setup(p)
    shown = c.hand_damages(p)[0]
    target = foe if card.target_type is TargetType.ENEMY else None
    hits = [r for r in c.play_card(p, 0, target=target)
            if "total" in r and r.get("source_id") == p.unit_id
            and r.get("target_id") == foe.unit_id]
    return shown, hits[0]["total"] if hits else None

setups = {
    "plain": lambda p: None,
    "+2 Strength": lambda p: p.apply_status(Strength(source=p, target=p, amount=2)),
    "+2 Strength, Weak": lambda p: (p.apply_status(Strength(source=p, target=p, amount=2)),
                                    p.apply_status(Weak(source=p, target=p, amount=1))),
    "3 Vigor": lambda p: p.apply_status(Vigor(source=p, target=p, amount=3)),
}
wrong, plays = [], 0
for card_id in sorted(known_card_ids()):
    if create_card(card_id).card_type is not CardType.ATTACK:
        continue
    for upgraded in (False, True):
        for name, setup in setups.items():
            plays += 1
            shown, dealt = first_hit(card_id, upgraded, setup)
            if shown != dealt:
                wrong.append("%s%s %s: shown %s, dealt %s"
                             % (card_id, "+" if upgraded else "", name, shown, dealt))
check("every Attack's first hit is what hand_damage showed (%d plays)" % plays,
      not wrong, wrong)

# --- hand_blocks: the Block each card gives the player holding it ------------
from GameEngine.Effects.StatusEffects.dexterity import Dexterity
from GameEngine.Effects.StatusEffects.frail import Frail
from GameEngine.Effects.StatusEffects.unmovable import Unmovable
from GameEngine.Effects.StatusEffects.fasten import Fasten
from GameEngine.Effects.StatusEffects.block_lockout import BlockLockout

c, a, es = fight(n_allies=2, seed=19)
p = a[0]
p.hand = ["defend", "strike", "lift", "rally", "ultimate_defend"]
check("Block cards show their Block; an Attack, and Lift (all of it to a teammate), None",
      c.hand_blocks(p) == [5, None, None, 12, 11], c.hand_blocks(p))
p.apply_status(Dexterity(source=p, target=p, amount=2))
check("Dexterity adds to each", c.hand_blocks(p) == [7, None, None, 14, 13], c.hand_blocks(p))
p.apply_status(Frail(source=p, target=p, amount=1))
check("Frail takes a quarter off the total: (5 + 2) x 0.75 = 5",
      c.hand_blocks(p)[0] == 5, c.hand_blocks(p))

# Fasten the game's way: part of the Defend's own Block, so Dexterity once.
c, a, es = fight(seed=20)
p = a[0]
p.energy = 9
p.apply_status(Fasten(source=p, target=p, amount=4))
p.apply_status(Dexterity(source=p, target=p, amount=2))
p.hand = ["defend", "ultimate_defend", "shrug_it_off"]
check("Fasten adds to Defend and Ultimate Defend only; Dexterity counts once",
      c.hand_blocks(p) == [11, 17, 10], c.hand_blocks(p))
play(c, p, "defend")
check("and a Defend gains exactly that, in one gain (5 + 4 + 2, not + 2 again)",
      p.block == 11, p.block)

# Second Wind: one gain per card exhausted, so Dexterity counts each time.
c, a, es = fight(seed=21)
p = a[0]
p.energy = 9
p.apply_status(Dexterity(source=p, target=p, amount=1))
p.hand = ["second_wind", "defend", "defend", "strike"]
shown = c.hand_blocks(p)[0]
c.play_card(p, 0)
check("Second Wind: 2 cards x (5 + 1) = 12, shown and gained",
      shown == 12 and p.block == 12 and sorted(p.exhaust_pile) == ["defend", "defend"],
      (shown, p.block, p.exhaust_pile))

# Entrench: unpowered in the game, so Dexterity and Frail leave it alone.
c, a, es = fight(seed=22)
p = a[0]
p.energy = 9
p.block = 10
p.apply_status(Dexterity(source=p, target=p, amount=2))
p.apply_status(Frail(source=p, target=p, amount=1))
p.hand = ["entrench"]
shown = c.hand_blocks(p)[0]
c.play_card(p, 0)
check("Entrench doubles 10 to 20 with Dexterity and Frail on: neither applies",
      shown == 10 and p.block == 20, (shown, p.block))

# Unmovable doubles every gain of the turn's first Block play - for Second Wind,
# both of its gains, since the game counts gains from other plays.
c, a, es = fight(seed=23)
p = a[0]
p.energy = 9
p.apply_status(Unmovable(source=p, target=p, amount=1))
p.hand = ["second_wind", "defend", "defend"]
counters = dict(p.turn_counters)
shown = c.hand_blocks(p)[0]
check("working it out changes nothing: hand and turn counters as they were",
      [str(x) for x in p.hand] == ["second_wind", "defend", "defend"] and p.turn_counters == counters,
      (p.hand, p.turn_counters, counters))
c.play_card(p, 0)
check("Unmovable: 5 doubled and 5 doubled = 20, shown and gained", shown == 20 and p.block == 20,
      (shown, p.block))

c, a, es = fight(seed=24)
p = a[0]
p.apply_status(BlockLockout(source=p, target=p, amount=2))
p.hand = ["defend"]
check("Panic Button's lockout: a Defend shows 0", c.hand_blocks(p) == [0], c.hand_blocks(p))

# Toric Toughness, as the game's ToricToughnessPower: the next two turns each
# gain again the Block the play really gained - unpowered and not from a card,
# so Dexterity, Frail and Unmovable do not touch it a second time.
def toric_turns(upgraded=False, setup=lambda p: None, plays=1):
    c, a, es = fight(seed=26)
    p = a[0]
    p.energy = 9
    setup(p)
    gained = []
    for _ in range(plays):
        before = p.block
        play(c, p, CardRef("toric_toughness", upgraded=upgraded))
        gained.append(p.block - before)
    later = []
    for _ in range(3):
        c.end_player_turn()                          # the next turn's Block, before any card
        later.append(p.block)
    return gained, later, p

gained, later, p = toric_turns()
check("Toric Toughness: 5 now, 5 at the start of each of the next 2 turns, then nothing",
      gained == [5] and later == [5, 5, 0] and p.get_status("delayed_block") is None,
      (gained, later))
gained, later, _ = toric_turns(upgraded=True)
check("Toric Toughness+: 7, then 7 and 7 (it used to give 5 on the later turns)",
      gained == [7] and later == [7, 7, 0], (gained, later))
gained, later, _ = toric_turns(setup=lambda p: p.apply_status(Dexterity(source=p, target=p, amount=2)))
check("with 2 Dexterity: 7 when played, and 7 again - Dexterity counted once, not twice",
      gained == [7] and later == [7, 7, 0], (gained, later))
gained, later, _ = toric_turns(setup=lambda p: p.apply_status(Frail(source=p, target=p, amount=5)))
check("Frail when played: 5 x 0.75 = 3, and 3 again even while still Frail",
      gained == [3] and later == [3, 3, 0], (gained, later))
gained, later, _ = toric_turns(setup=lambda p: p.apply_status(Unmovable(source=p, target=p, amount=1)))
check("Unmovable doubles the play to 10; the later 10s are not doubled again",
      gained == [10] and later == [10, 10, 0], (gained, later))
gained, later, p = toric_turns(plays=2)
check("two plays, two grants: 5 + 5 each of the next two turns",
      gained == [5, 5] and later == [10, 10, 0], (gained, later))

c, a, es = fight(seed=27)
p = a[0]
p.hand = ["toric_toughness"]
text = next(d for d in c.to_dict()["allies"] if d["unit_id"] == p.unit_id)["hand_text"][0]
check("its text says so", text == "Gain 5 Block. Gain that much Block again at the start of "
      "each of your next 2 turns.", text)

# Every card, plain and upgraded, played for real in seven situations: the
# Block it gives its player is what hand_blocks showed. None means none.
def self_block(card_id, upgraded, setup):
    c, a, es = fight(n_allies=2, seed=25, enemy_hp=999)
    p, mate, foe = a[0], a[1], es[0]
    p.energy = 20
    p.block, mate.block = 7, 4
    ref = CardRef(card_id, upgraded=upgraded)
    card = create_card(ref)
    p.hand = [ref, CardRef("strike"), CardRef("defend"), CardRef("bash")]
    if not card.playable_now(p):                     # Clash wants a hand of Attacks
        p.hand = [ref, CardRef("strike"), CardRef("strike")]
    p.draw_pile = [CardRef("strike") for _ in range(6)]
    p.discard_pile = [CardRef("strike") for _ in range(4)]
    setup(p)
    shown = c.hand_blocks(p)[0]
    target = {TargetType.ENEMY: foe, TargetType.ALLY: mate}.get(card.target_type)
    before = p.block
    c.play_card(p, 0, target=target)
    return shown, p.block - before

block_setups = {
    "plain": lambda p: None,
    "+2 Dexterity": lambda p: p.apply_status(Dexterity(source=p, target=p, amount=2)),
    "Frail": lambda p: p.apply_status(Frail(source=p, target=p, amount=1)),
    "+2 Dexterity, Frail": lambda p: (p.apply_status(Dexterity(source=p, target=p, amount=2)),
                                      p.apply_status(Frail(source=p, target=p, amount=1))),
    "Unmovable": lambda p: p.apply_status(Unmovable(source=p, target=p, amount=1)),
    "Fasten 4": lambda p: p.apply_status(Fasten(source=p, target=p, amount=4)),
    "lockout": lambda p: p.apply_status(BlockLockout(source=p, target=p, amount=2)),
}
wrong, plays = [], 0
for card_id in sorted(known_card_ids()):
    card = create_card(card_id)
    if not card.properties.playable or card_id == "mimic":    # Mimic's Block is the target's
        continue
    for upgraded in (False, True):
        for name, setup in block_setups.items():
            plays += 1
            shown, gained = self_block(card_id, upgraded, setup)
            if (shown or 0) != gained:
                wrong.append("%s%s %s: shown %s, gained %s"
                             % (card_id, "+" if upgraded else "", name, shown, gained))
check("every card gives its player the Block hand_blocks showed (%d plays)" % plays,
      not wrong, wrong)

# --- piles on the wire -------------------------------------------------------
def wire_piles(c, ally):
    return next(d for d in c.to_dict()["allies"] if d["unit_id"] == ally.unit_id)["piles"]

c, a, es = fight(n_allies=2, seed=18)
p = a[0]
p.draw_pile = [CardRef("strike"), CardRef("slimed"), CardRef("bash", upgraded=True),
               CardRef("defend"), CardRef("offering")]
p.discard_pile = [CardRef("defend"), CardRef("strike")]
p.exhaust_pile = [CardRef("burning_pact", upgraded=True)]
piles = wire_piles(c, p)
check("the draw pile is sorted like the game's pile screen: rarity, then id, "
      "Status and Curse last - never the real order",
      [e["id"] for e in piles["draw"]] == ["bash", "defend", "strike", "offering", "slimed"],
      piles["draw"])
check("each entry says whether that copy is upgraded",
      (piles["draw"][0]["id"], piles["draw"][0]["upgraded"]) == ("bash", True)
      and [(e["id"], e["upgraded"]) for e in piles["exhaust"]] == [("burning_pact", True)],
      piles)
check("discard keeps its order", [e["id"] for e in piles["discard"]] == ["defend", "strike"],
      piles["discard"])
check("the real draw pile is untouched by being shown",
      [str(x) for x in p.draw_pile] == ["strike", "slimed", "bash", "defend", "offering"],
      p.draw_pile)
check("every ally's piles are sent",
      all(set(d["piles"]) == {"draw", "discard", "exhaust"} for d in c.to_dict()["allies"]))

print()
print("ALL BATCH 13 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
