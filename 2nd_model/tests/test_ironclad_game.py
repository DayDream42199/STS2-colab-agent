"""The Ironclad pass: every behaviour changed to match the installed game's code.

Values (costs, damage, upgrades, rarity, type) are checked against the game by
tests/game_diff.py, which needs the decompiled source and so is not run here.
This file checks what those values cannot show - what the cards DO.
"""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_ref import CardRef, is_upgraded
from GameEngine.Cards._card_enums import CardType
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.StatusEffects.cruelty import Cruelty

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=200, ally_hp=200):
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i + 1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed), scale_enemies=False)
    c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
        e.get_effects = lambda context: []          # the enemies stand still
    for a in allies:
        a.current_hp = a.max_hp = ally_hp
        a.energy = 9
        a.block = 0
    return c, allies, enemies


def cards(*ids):
    return [CardRef(i) for i in ids]


def play(c, ally, ref, target=None):
    ref = ref if isinstance(ref, CardRef) else CardRef(ref)
    ally.hand = [ref] + [r for r in ally.hand if r is not ref]
    return c.play_card(ally, 0, target=target)


def charges(unit, effect_id):
    status = unit.get_status(effect_id)
    return status.amount if status is not None else 0


def hit(c, attacker, target, amount, is_attack=True):
    c._resolve(InstantDamage(source=attacker, target=target, amount=amount, is_attack=is_attack))


# --- removed from the game ----------------------------------------------------
for gone in ("blaze", "midnight", "outrage", "abundance"):
    check("%s is gone from the registry, as from the game" % gone, gone not in known_card_ids())

# --- upgrade costs the old table missed --------------------------------------
for cid, base, up in (("infernal_blade", 1, 0), ("unmovable", 2, 1), ("expect_a_fight", 2, 1),
                      ("bloodletting", 0, 0), ("inferno", 1, 1)):
    got = (create_card(cid).cost, create_card(CardRef(cid, upgraded=True)).cost)
    check("%s costs %d, upgraded %d" % (cid, base, up), got == (base, up), got)
check("Stone Armor is a Power in the game, not a Skill",
      create_card("stone_armor").card_type is CardType.POWER)

# --- Havoc: an empty draw pile is refilled from the discard -------------------
c, (p,), (e,) = fight()
p.draw_pile, p.discard_pile = [], cards("strike")
play(c, p, "havoc")
check("Havoc on an empty draw pile shuffles the discard in and plays its top card",
      e.current_hp == 194, e.current_hp)
check("...which it exhausts, as always", "strike" in p.exhaust_pile, p.exhaust_pile)

c, (p,), (e,) = fight()
p.draw_pile, p.discard_pile = [], []
play(c, p, "havoc")
check("with nothing in either pile, Havoc does nothing and nothing breaks",
      e.current_hp == 200 and p.exhaust_pile == [], (e.current_hp, p.exhaust_pile))

# --- auto-played cards hit a random enemy, not the weakest -------------------
hits = set()
for seed in range(30):
    c, (p,), es = fight(n_enemies=2, seed=seed)
    es[1].current_hp = 100                 # the old rule always picked this one
    p.draw_pile = cards("strike")
    play(c, p, "havoc")
    hits.update(i for i, x in enumerate(es) if x.current_hp < (200, 100)[i])
check("a Strike played by Havoc lands on either enemy, at random", hits == {0, 1}, hits)

# --- Cascade: X cards, X+1 upgraded, reshuffling when it runs out -----------
c, (p,), (e,) = fight()
p.energy = 2
p.draw_pile, p.discard_pile = cards("strike", "strike"), cards("strike")
play(c, p, "cascade")
check("Cascade with 2 energy plays 2 Strikes", e.current_hp == 188, e.current_hp)

c, (p,), (e,) = fight()
p.energy = 2
p.draw_pile, p.discard_pile = cards("strike", "strike"), cards("strike")
play(c, p, CardRef("cascade", upgraded=True))
check("Cascade+ with 2 energy plays 3 - the third after shuffling the discard in",
      e.current_hp == 182, e.current_hp)
check("...and the cards it played end up discarded, not exhausted",
      p.exhaust_pile == [] and p.discard_pile.count("strike") == 3, (p.exhaust_pile, p.discard_pile))

# --- Burning Pact: YOU choose, and the exhaust comes before the draw ---------
c, (p,), (e,) = fight(seed=2)
c.ask_players = True
p.hand = cards("strike", "defend")
p.draw_pile = cards("bash", "anger")
play(c, p, "burning_pact")
ask = c.choice_for(p)
check("Burning Pact asks which card to exhaust", ask is not None and sorted(ask.options) == ["defend", "strike"],
      ask and ask.options)
check("...before drawing anything", sorted(p.hand) == ["defend", "strike"], p.hand)
c.answer_choice(p, ask.options.index("defend"))
check("the chosen card is exhausted, then 2 are drawn",
      p.exhaust_pile == ["defend"] and sorted(p.hand) == ["anger", "bash", "strike"],
      (p.exhaust_pile, p.hand))

c, (p,), (e,) = fight(seed=2)
p.hand, p.draw_pile = [], cards("bash", "anger")
play(c, p, "burning_pact")
check("with an empty hand it just draws", sorted(p.hand) == ["anger", "bash"], p.hand)

# --- Brand: lose HP, choose, exhaust, then Strength ----------------------------
c, (p,), (e,) = fight(seed=3)
c.ask_players = True
p.hand = cards("strike")
play(c, p, "brand")
check("Brand costs its 1 HP straight away", p.current_hp == 199, p.current_hp)
check("...asks what to exhaust, and holds the Strength until it is answered",
      c.choice_for(p) is not None and p.get_status("strength") is None)
c.answer_choice(p, 0)
check("answered: Strike exhausted, 1 Strength", p.exhaust_pile == ["strike"]
      and charges(p, "strength") == 1, (p.exhaust_pile, charges(p, "strength")))

# --- True Grit: random, but upgraded you choose ------------------------------
c, (p,), (e,) = fight(seed=4)
c.ask_players = True
p.hand = cards("strike", "defend")
play(c, p, "true_grit")
check("True Grit exhausts at random - no question", c.choice_for(p) is None
      and len(p.exhaust_pile) == 1 and p.block == 7, (p.exhaust_pile, p.block))

c, (p,), (e,) = fight(seed=4)
c.ask_players = True
p.hand = cards("strike", "defend")
play(c, p, CardRef("true_grit", upgraded=True))
ask = c.choice_for(p)
check("True Grit+ asks instead", ask is not None and p.block == 9, (ask, p.block))
c.answer_choice(p, ask.options.index("strike"))
check("...and exhausts the one chosen", p.exhaust_pile == ["strike"], p.exhaust_pile)

# --- Forgotten Ritual: only if you exhausted a card this turn ----------------
c, (p,), (e,) = fight()
play(c, p, "forgotten_ritual")
check("Forgotten Ritual gives nothing if nothing was exhausted this turn",
      p.energy == 8, p.energy)

c, (p,), (e,) = fight()
p.hand = cards("strike")
play(c, p, "true_grit")                                    # exhausts the Strike
play(c, p, "forgotten_ritual")
check("...and 3 Energy once something was", p.energy == 9 - 1 - 1 + 3, p.energy)

c, (p,), (e,) = fight()
p.hand = cards("strike")
play(c, p, "true_grit")
play(c, p, CardRef("forgotten_ritual", upgraded=True))
check("Forgotten Ritual+ gives 4", p.energy == 9 - 1 - 1 + 4, p.energy)

# --- Aggression stacks: two copies pull two Attacks a turn -------------------
for copies in (1, 2):
    c, (p,), (e,) = fight(seed=5)
    for _ in range(copies):
        play(c, p, "aggression")
    p.hand = []
    p.discard_pile = cards("anger", "anger", "anger")
    p.draw_pile = cards(*["defend"] * 10)
    c.end_player_turn()
    pulled = [r for r in p.hand if r == "anger"]
    check("%d Aggression pulls %d upgraded Attack(s) out of the discard" % (copies, copies),
          len(pulled) == copies and all(is_upgraded(r) for r in pulled),
          [(str(r), is_upgraded(r)) for r in p.hand])

# --- Cruelty: added to Vulnerable, stacks, and only for its holder -----------
def strike_into_vulnerable(cruelty=None, holder_strikes=True, vulnerable=True):
    c, (p1, p2), (e,) = fight(n_allies=2)
    if vulnerable:
        e.apply_status(Vulnerable(source=p1, target=e, amount=3))
    for amount in cruelty or ():
        p1.apply_status(Cruelty(source=p1, target=p1, amount=amount))
    play(c, p1 if holder_strikes else p2, "strike", e)
    return 200 - e.current_hp

check("a Strike into Vulnerable: 6 x 1.5 = 9", strike_into_vulnerable() == 9)
check("with Cruelty: 6 x (1.5 + 0.25) = 10", strike_into_vulnerable([25]) == 10,
      strike_into_vulnerable([25]))
check("Cruelty+ (50): 6 x 2 = 12", strike_into_vulnerable([50]) == 12, strike_into_vulnerable([50]))
check("two Cruelties stack: 6 x (1.5 + 0.5) = 12", strike_into_vulnerable([25, 25]) == 12,
      strike_into_vulnerable([25, 25]))
check("no Vulnerable, no bonus", strike_into_vulnerable([25], vulnerable=False) == 6)
check("a teammate's Strike is not helped - the game reads the attacker's Cruelty",
      strike_into_vulnerable([25], holder_strikes=False) == 9,
      strike_into_vulnerable([25], holder_strikes=False))
c, (p,), (e,) = fight()
play(c, p, CardRef("cruelty", upgraded=True))
check("the card applies 25, upgraded 50", charges(p, "cruelty") == 50, charges(p, "cruelty"))

# --- Tank: double damage from attacks on the tank; half on the others --------
c, (p1, p2), (e,) = fight(n_allies=2)
play(c, p1, "tank")
hit(c, e, p1, 10)
hit(c, e, p2, 10)
check("Tank takes double from an attack: 10 -> 20", p1.current_hp == 180, p1.current_hp)
check("its teammate takes half: 10 -> 5", p2.current_hp == 195, p2.current_hp)
hit(c, e, p1, 3, is_attack=False)
check("but only attacks: 3 damage that is not an attack stays 3", p1.current_hp == 177,
      p1.current_hp)
p1.current_hp = 0
hit(c, e, p2, 10)
check("with the tank dead, the teammate's protection is gone", p2.current_hp == 185, p2.current_hp)

# --- Expect a Fight: Energy per Attack held, then no more Energy this turn ---
c, (p,), (e,) = fight()
p.hand = cards("strike", "strike", "defend")
play(c, p, "expect_a_fight")
check("2 Attacks in hand: pay 2, gain 2", p.energy == 9, p.energy)
check("...and No Energy Gain for the rest of the turn", p.get_status("no_energy_gain") is not None)
play(c, p, "bloodletting")
check("so Bloodletting's Energy is lost (its HP is not)", p.energy == 9 and p.current_hp == 197,
      (p.energy, p.current_hp))
p.hand = []
c.end_player_turn()
check("the lock is gone next turn", p.get_status("no_energy_gain") is None)

# --- One-Two Punch and Unrelenting are statuses now --------------------------
c, (p,), (e,) = fight()
play(c, p, CardRef("one_two_punch", upgraded=True))
check("One-Two Punch+ doubles the next 2 Attacks", charges(p, "one_two_punch") == 2)
play(c, p, "strike", e)
play(c, p, "strike", e)
play(c, p, "strike", e)
check("12 + 12 + 6", e.current_hp == 200 - 30, e.current_hp)

c, (p,), (e,) = fight()
play(c, p, "unrelenting", e)
p.draw_pile = cards("strike")
play(c, p, "havoc")
check("an Attack played by Havoc spends Unrelenting's free Attack, as in the game",
      p.get_status("free_attack") is None, p.statuses.keys())

# --- Thrash grows after it hits (covered in depth in test_fork) --------------
c, (p,), (e,) = fight()
ref = CardRef("thrash")
p.hand = [ref, CardRef("strike")]
c.play_card(p, 0, target=e)
check("Thrash's first hit is its own 4 x 2; the eaten Strike counts next time",
      e.current_hp == 192 and ref.bonus_damage == 6, (e.current_hp, ref.bonus_damage))

# --- upgrades that change what a card does -----------------------------------
c, (p,), (e,) = fight()
p.hand = cards("strike")
play(c, p, CardRef("primal_force", upgraded=True))
check("Primal Force+ makes upgraded Giant Rocks",
      [str(r) for r in p.hand] == ["giant_rock"] and all(is_upgraded(r) for r in p.hand),
      [(str(r), is_upgraded(r)) for r in p.hand])

c, (p,), (e,) = fight()
p.hand = cards("defend", "defend")
play(c, p, CardRef("stoke", upgraded=True))
check("Stoke+ replaces the hand with upgraded cards",
      len(p.hand) == 2 and all(is_upgraded(r) for r in p.hand),
      [(str(r), is_upgraded(r)) for r in p.hand])

c, (p,), (e,) = fight()
play(c, p, "stone_armor")
check("Stone Armor, as a Power, leaves play and leaves Plating behind",
      "stone_armor" not in p.discard_pile and charges(p, "plating") == 4,
      (p.discard_pile, charges(p, "plating")))

# --- a full hand: a card added or moved into it goes to the discard pile -----
# The game's CardPileCmd.Add checks each card as it arrives: at 10 cards
# (CardPile.MaxCardsInHand) it lands in the discard pile instead.
from GameEngine.Effects.InstantEffects.instant_move_card import InstantMoveCard

def overflow(results):
    return [str(x) for r in results for x in r.get("to_discard", [])]

c, (p,), (e,) = fight()
p.hand, p.discard_pile = cards("infernal_blade", *["defend"] * 10), []
results = c.play_card(p, 0)
check("Infernal Blade into a full hand: the Attack goes to the discard pile",
      len(p.hand) == 10 and len(p.discard_pile) == 1
      and create_card(p.discard_pile[0]).card_type is CardType.ATTACK
      and overflow(results) == [str(p.discard_pile[0])],
      (len(p.hand), p.discard_pile, overflow(results)))

c, (p,), (e,) = fight()
p.hand, p.discard_pile = cards("jackpot", *["defend"] * 8), []
results = c.play_card(p, 0, target=e)
check("Jackpot with room for 2: two reach the hand, the third is discarded",
      len(p.hand) == 10 and len(overflow(results)) == 1
      and sorted(map(str, p.discard_pile)) == sorted([overflow(results)[0], "jackpot"]),
      (len(p.hand), p.discard_pile, overflow(results)))

c, (p,), (e,) = fight()
p.hand, p.discard_pile = [CardRef("dual_wield", upgraded=True)] + cards("strike", *["defend"] * 8), []
results = c.play_card(p, 0)                          # nobody to ask: the Strike is the only Attack
check("Dual Wield+ with room for 1: one copy in hand, the other discarded",
      [str(r) for r in p.hand].count("strike") == 2 and len(p.hand) == 10
      and overflow(results) == ["strike"] and "strike" in p.discard_pile,
      ([str(r) for r in p.hand], p.discard_pile, overflow(results)))

c, (p,), (e,) = fight()
p.hand, p.draw_pile, p.discard_pile = cards("wish", *["defend"] * 10), cards("bash"), []
results = c.play_card(p, 0)
check("Wish into a full hand: the card leaves the draw pile for the discard pile",
      p.draw_pile == [] and "bash" not in p.hand and p.discard_pile == ["bash"]
      and overflow(results) == ["bash"],
      (p.draw_pile, p.discard_pile, overflow(results)))

c, (p,), (e,) = fight()
p.hand, p.discard_pile = cards(*["defend"] * 10), []
c._resolve(InstantMoveCard(source=p, target=p, card_ids=cards("bolas"),
                           from_pile=InstantMoveCard.GONE, to_pile=InstantMoveCard.HAND))
check("a Bolas coming back to a full hand lands in the discard pile",
      len(p.hand) == 10 and p.discard_pile == ["bolas"], (len(p.hand), p.discard_pile))

c, (p,), (e,) = fight()
p.hand, p.discard_pile = cards(*["defend"] * 9), cards("strike", "bash")
c._resolve(InstantMoveCard(source=p, target=p, card_ids=list(p.discard_pile),
                           from_pile=InstantMoveCard.DISCARD, to_pile=InstantMoveCard.HAND))
check("one at a time: the first fills the hand, the next goes back to the discard",
      "strike" in p.hand and len(p.hand) == 10 and p.discard_pile == ["bash"],
      ([str(r) for r in p.hand], p.discard_pile))

c, (p,), (e,) = fight()
p.hand, p.discard_pile = cards("infernal_blade", "defend", "defend"), []
results = c.play_card(p, 0)
check("with room, nothing changes: the Attack is added to the hand",
      len(p.hand) == 3 and p.discard_pile == [] and overflow(results) == [],
      (len(p.hand), p.discard_pile))

print("\n== Unmovable: Models.Powers.UnmovablePower ==")
from GameEngine.Effects.StatusEffects.unmovable import Unmovable
from GameEngine.Effects.InstantEffects.instant_block import InstantBlock


def unmovable(stacks=1, n_allies=1):
    c, allies, enemies = fight(n_allies=n_allies)
    allies[0].apply_status(Unmovable(source=allies[0], target=allies[0], amount=stacks))
    return c, allies, enemies


def gained(c, ally, ref, target=None):
    """Block the play gave, and what hand_blocks showed for it first."""
    ref = ref if isinstance(ref, CardRef) else CardRef(ref)
    ally.hand = [ref] + [r for r in ally.hand if r is not ref]
    shown = c.hand_blocks(ally)[0]
    who = target if target is not None else ally
    before = who.block
    c.play_card(ally, 0, target=target)
    return who.block - before, shown


c, (p,), _ = unmovable()
first, shown = gained(c, p, "defend")
second, _ = gained(c, p, "defend")
check("Unmovable 1: the first Defend 5 -> 10, the next is 5", (first, second) == (10, 5), (first, second))
check("hand_blocks showed the 10", shown == 10, shown)

c, (p,), _ = unmovable(stacks=2)
got = [gained(c, p, "defend")[0] for _ in range(3)]
check("it stacks: Unmovable 2 doubles two Defends, not the third", got == [10, 10, 5], got)

c, (p,), _ = unmovable()
p.hand = cards("second_wind", "defend", "defend")
block, shown = gained(c, p, p.hand[0])
check("every gain of one play is doubled: Second Wind's 5 + 5 -> 20, as shown",
      (block, shown) == (20, 20), (block, shown))
check("and those two gains used it up: a Defend after is 5", gained(c, p, "defend")[0] == 5)

c, (p,), _ = unmovable()
p.block = 0
check("a play that gains nothing (Entrench on 0 Block) is no gain on record",
      gained(c, p, "entrench")[0] == 0 and p.card_blocks == [], p.card_blocks)
check("so the Defend after it is still doubled", gained(c, p, "defend")[0] == 10)

c, (p,), _ = unmovable()
c._resolve(InstantBlock(source=p, target=p, amount=4, powered=False, card=False))
check("a power's own Block (Plating's kind) is not doubled and not counted",
      p.block == 4 and p.card_blocks == [], (p.block, p.card_blocks))
check("so the first Defend still is", gained(c, p, "defend")[0] == 10)

c, (p, q), _ = unmovable(n_allies=2)
block, _ = gained(c, p, "lift", target=q)
check("your card's Block to a teammate is doubled too: Lift 11 -> 22", block == 22, block)
c, (p, q), _ = unmovable(n_allies=2)
block, _ = gained(c, q, "lift", target=p)
check("a teammate's card giving you Block is not: their Lift on you stays 11", block == 11, block)
check("and it does count against yours: your Defend after it is 5", gained(c, p, "defend")[0] == 5)

c, (p,), _ = unmovable()
p.draw_pile = cards("defend")
block, _ = gained(c, p, "havoc")
check("a Defend that Havoc plays is a play of its own: doubled, 10", block == 10, block)
check("and the next play is a different one: 5", gained(c, p, "defend")[0] == 5)

c, (p,), (e,) = unmovable()
c.end_player_turn()
p.energy = 9
check("a new turn: doubled again", gained(c, p, "defend")[0] == 10)

c, (p,), (e,) = fight()
e.apply_status(Unmovable(source=e, target=e, amount=1))
c._resolve(InstantBlock(source=e, target=e, amount=6))
check("never for an enemy, even holding it", e.block == 6, e.block)

print("\n== the Ironclad unit: Models.Characters.Ironclad ==")
import config
from GameEngine.Units.Allies.ironclad import Ironclad

rolls = {create_ally("ironclad", "p1", rng=random.Random(seed)).max_hp for seed in range(50)}
check("80 HP, never rolled", rolls == {80}, rolls)
irc = create_ally("ironclad", "p1", rng=random.Random(1))
check("3 energy", irc.max_energy == 3, irc.max_energy)
check("starting deck: 5 Strike, 4 Defend, 1 Bash",
      sorted(irc.deck) == sorted(["strike"] * 5 + ["defend"] * 4 + ["bash"]), irc.deck)
check("the server plays the Ironclad", config.ALLY_TYPE_ID == Ironclad.type_id(), config.ALLY_TYPE_ID)

print("\n== beyond the Ironclad cards, matched to the game's code ==")
from GameEngine.Cards._card_enums import CardRarity
from GameEngine.Context.context import PendingChoice


def asking(n_allies=1):
    """A fight whose questions wait for an answer, as with players connected."""
    c, allies, enemies = fight(n_allies=n_allies)
    c.ask_players = True
    return c, allies, enemies


for card_id, kind, word in (("secret_technique", CardType.SKILL, "Skill"),
                            ("secret_weapon", CardType.ATTACK, "Attack")):
    card = create_card(card_id)
    c, (p,), _ = asking()
    p.hand = cards(card_id, "defend")
    p.draw_pile = cards("strike", "defend", "bash", "shrug_it_off")
    c.play_card(p, 0)
    ask = c.choice_for(p)
    offered = [str(o) for o in ask.options] if ask else None
    check("%s asks which %s - the player picks, it is not random" % (card.name, word),
          offered == [str(x) for x in p.draw_pile if create_card(x).card_type is kind], offered)
    chosen = ask.options[-1]
    c.answer_choice(p, len(ask.options) - 1)
    check("%s: the picked card comes to the end of the hand" % card.name,
          p.hand[-1] is chosen and chosen not in p.draw_pile, [str(x) for x in p.hand])
    c, (p,), _ = asking()
    p.hand = cards(card_id)
    p.draw_pile = cards("burn")
    c.play_card(p, 0)
    check("%s: no %s to take, no question" % (card.name, word), c.choice_for(p) is None)
    check("%s is Rare, exhausts, and its upgrade does not" % card.name,
          card.rarity is CardRarity.RARE and card.properties.exhaust
          and not create_card(CardRef(card_id, upgraded=True)).properties.exhaust)

for held, offers in ((7, 2), (8, 2), (9, 1), (10, 0)):
    c, (p,), (e,) = asking()
    p.hand = cards("neows_fury", *["defend"] * held)
    p.discard_pile = cards("strike", "bash", "anger")
    c.play_card(p, 0, target=e)
    taken = 0
    while c.choice_for(p) is not None:
        c.answer_choice(p, 0)
        taken += 1
    check("Neow's Fury with %d other cards held: offers %d, never more than the hand holds"
          % (held, offers), taken == offers and len(p.hand) == min(10, held + 2), (taken, len(p.hand)))

c, (p,), _ = asking()
p.hand = cards("wish", "strike", "defend")
p.draw_pile = cards("bash")
c.play_card(p, 0)
c.answer_choice(p, 0)
check("a card moved into the hand goes to its end, as CardPileCmd.Add's Bottom",
      [str(x) for x in p.hand] == ["strike", "defend", "bash"], [str(x) for x in p.hand])

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
