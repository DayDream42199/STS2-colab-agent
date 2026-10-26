"""Every card's text: present, filled from the card's own numbers, following
its upgrade and its keywords, and sent to the players with the state."""
import random, re, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Cards._text import TEXT, card_text

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def text(card_id, **ref):
    return card_text(create_card(CardRef(card_id, **ref)))

ids = sorted(known_card_ids())

# --- coverage -----------------------------------------------------------------
check("every registered card has text", not [c for c in ids if c not in TEXT],
      [c for c in ids if c not in TEXT])
check("no text for a card that does not exist", not [c for c in TEXT if c not in ids],
      [c for c in TEXT if c not in ids])

# --- every card renders, plain and upgraded ------------------------------------
broken = []
for cid in ids:
    for upgraded in (False, True):
        try:
            rendered = text(cid, upgraded=upgraded)
        except Exception as error:
            broken.append("%s%s: %r" % (cid, "+" if upgraded else "", error))
            continue
        if not rendered or re.search(r"[{}]|None", rendered):
            broken.append("%s%s: %r" % (cid, "+" if upgraded else "", rendered))
check("all %d cards render plain and upgraded, every field filled" % len(ids),
      not broken, broken)

# --- a number an upgrade changes must be in the text --------------------------
# Otherwise the upgrade would change the card and not what it says.
missed = []
for cid in ids:
    base, up = create_card(cid), create_card(CardRef(cid, upgraded=True))
    entry = TEXT[cid]
    templates = " ".join(entry) if isinstance(entry, tuple) else entry
    for name, value in vars(type(base)).items():
        if not (name.isupper() and isinstance(value, int)) or isinstance(value, bool):
            continue
        if getattr(base, name) != getattr(up, name) and "{" + name not in templates:
            missed.append("%s.%s" % (cid, name))
check("every number an upgrade changes appears in the text", not missed, missed)

# --- what particular cards say -------------------------------------------------
expect = {
    ("strike", False): "Deal 6 damage.",
    ("strike", True): "Deal 9 damage.",
    ("defend", True): "Gain 8 Block.",
    ("bash", True): "Deal 10 damage. Apply 3 Vulnerable.",
    ("twin_strike", False): "Deal 5 damage 2 times.",
    ("dual_wield", False): "Choose an Attack or Power in your Hand. Add 1 copy of it into your Hand.",
    ("dual_wield", True): "Choose an Attack or Power in your Hand. Add 2 copies of it into your Hand.",
    ("cascade", True): "Play the top X+1 cards of your Draw Pile.",
    ("true_grit", False): "Gain 7 Block. Exhaust a random card in your Hand.",
    ("true_grit", True): "Gain 9 Block. Exhaust a card in your Hand.",
    ("stack", False): "Gain Block equal to the number of cards in your Discard Pile.",
    ("stack", True): "Gain Block equal to the number of cards in your Discard Pile, plus 3.",
    ("wound", False): "Unplayable.",
    ("dazed", False): "Unplayable. Ethereal.",
    ("purity", False): "Retain. Exhaust up to 3 cards in your Hand. Exhaust.",
    ("slimed", False): "Draw 1 card. Exhaust.",
}
for (cid, upgraded), want in expect.items():
    got = text(cid, upgraded=upgraded)
    check("%s%s reads %r" % (cid, "+" if upgraded else "", want), got == want, got)

check("an upgrade that removes Ethereal removes it from the text",
      "Ethereal" in text("apparition") and "Ethereal" not in text("apparition", upgraded=True),
      (text("apparition"), text("apparition", upgraded=True)))
check("an upgrade that removes Exhaust removes it from the text",
      text("discovery").endswith("Exhaust.") and not text("discovery", upgraded=True).endswith("Exhaust."),
      text("discovery", upgraded=True))
check("an upgrade that adds Innate adds it", text("aggression", upgraded=True).startswith("Innate."),
      text("aggression", upgraded=True))
check("a boosted Rampage says what it will deal now",
      text("rampage", bonus_damage=5).startswith("Deal 14 damage."), text("rampage", bonus_damage=5))
check("an upgraded Wither from Aeonglass says its real damage",
      "take 6 damage" in text("wither", bonus_damage=3), text("wither", bonus_damage=3))

# --- sent with the state ---------------------------------------------------------
allies = [create_ally("testally1", "p%d" % i, rng=random.Random(i)) for i in (1, 2)]
enemies = [create_enemy("dummy1", "e1", rng=random.Random(1))]
c = Combat(allies, enemies, rng=random.Random(1))
c.start()
p = allies[0]
p.hand = [CardRef("strike"), CardRef("bash", upgraded=True), CardRef("wish")]
p.draw_pile = [CardRef("defend"), CardRef("strike")]
p.discard_pile = [CardRef("rampage", bonus_damage=5)]
mine = next(d for d in c.to_dict()["allies"] if d["unit_id"] == "p1")
check("hand_text: one per card in hand, the copy's own numbers",
      mine["hand_text"] == ["Deal 6 damage.", "Deal 10 damage. Apply 3 Vulnerable.",
                            text("wish")], mine["hand_text"])
check("every pile entry carries its text",
      all(e.get("text") for pile in mine["piles"].values() for e in pile)
      and mine["piles"]["discard"][0]["text"].startswith("Deal 14 damage."), mine["piles"])

c.ask_players = True
p.energy = 9
c.play_card(p, 2)                                   # Wish asks
ask = c.to_dict()["choices"]["p1"]
check("a question sends what each option does",
      ask["option_text"] == [text(o) for o in ask["options"]], ask)

# --- in hand, damage reads as it will land -------------------------------------
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.weak import Weak

def fresh():
    allies = [create_ally("testally1", "p1", rng=random.Random(3))]
    c = Combat(allies, [create_enemy("dummy1", "e1", rng=random.Random(3))], rng=random.Random(3))
    c.start()
    return c, allies[0]

def hand_text(c, p):
    return next(d for d in c.to_dict()["allies"] if d["unit_id"] == p.unit_id)["hand_text"]

c, p = fresh()
p.apply_status(Strength(source=p, target=p, amount=2))
p.hand = [CardRef("strike"), CardRef("twin_strike"), CardRef("defend"), CardRef("decay")]
p.draw_pile = [CardRef("strike")]
check("with 2 Strength a Strike in hand says 8, Twin Strike 7 a hit",
      hand_text(c, p)[:2] == ["Deal 8 damage.", "Deal 7 damage 2 times."], hand_text(c, p))
check("Strength does not touch Block, or damage a Curse does to you",
      hand_text(c, p)[2] == "Gain 5 Block." and "take 2 damage" in hand_text(c, p)[3],
      hand_text(c, p)[2:])
pile = next(d for d in c.to_dict()["allies"] if d["unit_id"] == "p1")["piles"]["draw"]
check("a pile shows the printed number, as the game's pile screen does",
      pile[0]["text"] == "Deal 6 damage.", pile)
p.apply_status(Weak(source=p, target=p, amount=1))
check("Weak takes it down: 8 x 0.75 = 6", hand_text(c, p)[0] == "Deal 6 damage.", hand_text(c, p))

c, p = fresh()
p.block = 7
p.hand = [CardRef("body_slam"), CardRef("mind_blast")]
p.draw_pile = [CardRef("strike")] * 4
check("worked-out damage says what it comes to now",
      hand_text(c, p) == ["Deal damage equal to your Block (now 7).",
                          "Innate. Deal damage equal to the number of cards in your Draw Pile (now 4)."],
      hand_text(c, p))
check("and not outside a hand, where there is no now",
      text("body_slam") == "Deal damage equal to your Block.", text("body_slam"))

# Every Attack: the number its hand text leads with is the one hand_damage
# sends, with Strength and Weak on - one number, not two that can disagree.
c, p = fresh()
p.apply_status(Strength(source=p, target=p, amount=3))
p.apply_status(Weak(source=p, target=p, amount=1))
p.exhaust_pile = [CardRef("strike")] * 3               # arms Pact's End
disagree = []
for cid in ids:
    card = create_card(cid)
    entry = TEXT[cid]
    template = entry if isinstance(entry, str) else entry[0]
    if card.card_type.name != "ATTACK" or "{DAMAGE}" not in template or "{NOW}" in template:
        continue
    p.hand = [CardRef(cid)]
    state = next(d for d in c.to_dict()["allies"] if d["unit_id"] == "p1")
    shown = int(re.search(r"deal (\d+) damage", state["hand_text"][0], re.I).group(1))
    if shown != state["hand_damage"][0]:
        disagree.append("%s: text %d, hand_damage %s" % (cid, shown, state["hand_damage"][0]))
check("every Attack's hand text and hand_damage agree", not disagree, disagree)

# --- in hand, Block reads as it will be gained --------------------------------
from GameEngine.Effects.StatusEffects.dexterity import Dexterity
from GameEngine.Effects.StatusEffects.frail import Frail

c, p = fresh()
p.apply_status(Dexterity(source=p, target=p, amount=2))
p.block = 10
p.hand = [CardRef("defend"), CardRef("lift"), CardRef("second_wind"), CardRef("entrench"),
          CardRef("evil_eye")]
check("with 2 Dexterity: Defend says 7; Lift (a teammate's Block) keeps its printed 11",
      hand_text(c, p)[0] == "Gain 7 Block." and "Give another player 11 Block" in hand_text(c, p)[1],
      hand_text(c, p)[:2])
check("worked-out Block says its total now: Second Wind, 4 other non-Attacks x (5 + 2) = 28",
      hand_text(c, p)[2].endswith("(now 28)."), hand_text(c, p)[2])
check("Entrench's doubling ignores Dexterity: (now 10)",
      hand_text(c, p)[3] == "Double your Block (now 10).", hand_text(c, p)[3])
check("Evil Eye keeps its printed 8 and says the total: (now 10)",
      hand_text(c, p)[4] == "Gain 8 Block, or twice that if you have Exhausted a card this turn (now 10).",
      hand_text(c, p)[4])
check("outside a hand the printed Block stands", text("defend") == "Gain 5 Block.", text("defend"))

# Every card that gives its player Block: the number its hand text gives (or
# its "(now N)") is the one hand_blocks has, with Dexterity and Frail on.
c, p = fresh()
p.apply_status(Dexterity(source=p, target=p, amount=3))
p.apply_status(Frail(source=p, target=p, amount=1))
p.block, p.discard_pile = 6, [CardRef("strike")] * 5
disagree = []
for cid in ids:
    p.hand = [CardRef(cid), CardRef("defend")]
    state = next(d for d in c.to_dict()["allies"] if d["unit_id"] == "p1")
    block = c.hand_blocks(p)[0]
    if block is None or not create_card(cid).properties.playable:
        continue
    said = re.search(r"\(now (\d+)\)\.?$", state["hand_text"][0]) or \
        re.search(r"(?:Gain|gain) (\d+) Block", state["hand_text"][0])
    if said is None or int(said.group(1)) != block:
        disagree.append("%s: text %r, hand_blocks %s" % (cid, state["hand_text"][0], block))
check("every Block card's hand text and hand_blocks agree", not disagree, disagree)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
