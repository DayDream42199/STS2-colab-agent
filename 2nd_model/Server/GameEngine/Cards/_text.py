"""What each card says, for a player to read.

Written from what each card's code does here, not copied from anywhere, so
the text cannot promise what the engine does not do.

No number is typed into a template when the card holds it:
- `{NAME}` is filled from the card's own constant of that name, after its
  upgrade, so "Deal {DAMAGE} damage." reads 6 on a Strike and 9 on a Strike+.
  DAMAGE includes this copy's bonus (Rampage, Maul, Thrash).
- `{NAME:word}` writes the number and the word, plural when it is not 1:
  "{CARDS:card}" is "1 card" or "3 cards", "{COPIES:copy}" "2 copies".
Keywords (Unplayable, Innate, Retain, Ethereal, Exhaust) come from the copy's
own properties, so an upgrade that drops Exhaust drops it from the text too.
A pair is (unupgraded, upgraded), for the few cards whose upgrade changes
what they do rather than a number.

Given the player holding it, an Attack's damage is shown as the game shows a
card in hand: after that player's Strength, Weak and Vigor. `{NOW}` is where
a card whose damage is worked out from the fight (Body Slam, Mind Blast...)
says what it comes to right now; with no holder it is left out. Block works
the same way from Combat.hand_blocks: `{BLOCK}` becomes the Block the card
gives its holder (after Dexterity, Frail, Fasten), and `{NOW_BLOCK}` says
what a worked-out Block card (Entrench, Stack...) comes to now.
"""
import re

TEXT = {
    "aggression": "At the start of your turn, put a random Attack from your Discard Pile into your Hand and Upgrade it.",
    "anger": "Deal {DAMAGE} damage. Add a copy of this card into your Discard Pile.",
    "anointed": "Put every Rare card from your Draw Pile into your Hand.",
    "apotheosis": "Upgrade ALL cards in your Hand, Draw Pile and Discard Pile.",
    "apparition": "Gain {INTANGIBLE} Intangible: until your next turn, all damage you take is reduced to 1.",
    "armaments": ("Gain {BLOCK} Block. Upgrade a card in your Hand.",
                  "Gain {BLOCK} Block. Upgrade ALL cards in your Hand."),
    "ascenders_bane": "",
    "ashen_strike": "Deal {DAMAGE} damage, plus {EXTRA_PER_EXHAUSTED} for each card in your Exhaust Pile{NOW}.",
    "automation": "Every 10 cards you draw, gain 1 Energy.",
    "bad_luck": "At the end of your turn, if this is in your Hand, lose {HP_LOSS} HP.",
    "barricade": "Block is not removed at the start of your turn.",
    "bash": "Deal {DAMAGE} damage. Apply {VULNERABLE} Vulnerable.",
    "battle_trance": "Draw {CARDS:card}. You cannot draw any more cards this turn.",
    "beacon_of_hope": "Whenever you gain Block on your turn, the other players gain half that much Block.",
    "beat_down": "Play {COUNT:random Attack} from your Discard Pile.",
    "beckon": "At the end of your turn, if this is in your Hand, lose {AMOUNT} HP.",
    "believe_in_you": "Another player gains {ENERGY} Energy.",
    "blood_wall": "Lose {HP_LOSS} HP. Gain {BLOCK} Block.",
    "bloodletting": "Lose {HP_LOSS} HP. Gain {ENERGY} Energy.",
    "bludgeon": "Deal {DAMAGE} damage.",
    "body_slam": "Deal damage equal to your Block{NOW}.",
    "bolas": "Deal {DAMAGE} damage. At the start of your next turn, return this to your Hand.",
    "brand": "Lose {HP_LOSS} HP. Exhaust a card in your Hand. Gain {STRENGTH} Strength.",
    "break": "Deal {DAMAGE} damage. Apply {VULNERABLE} Vulnerable.",
    "breakthrough": "Lose {HP_LOSS} HP. Deal {DAMAGE} damage to ALL enemies.",
    "brightest_flame": "Gain {ENERGY} Energy. Draw {CARDS:card}. Lose {MAX_HP_LOSS} Max HP.",
    "bully": "Deal {DAMAGE} damage, plus {EXTRA_PER_VULNERABLE} for each Vulnerable on the enemy.",
    "burn": "At the end of your turn, if this is in your Hand, take {AMOUNT} damage.",
    "burning_pact": "Exhaust a card in your Hand. Draw {CARDS:card}.",
    "byrd_swoop": "Deal {DAMAGE} damage.",
    "calamity": "Whenever you play an Attack, add a random Attack into your Hand.",
    "caltrops": "Whenever you are attacked, deal {THORNS} damage back.",
    "cascade": ("Play the top X cards of your Draw Pile.",
                "Play the top X+1 cards of your Draw Pile."),
    "catastrophe": "Play {COUNT:random card} from your Draw Pile.",
    "cinder": "Deal {DAMAGE} damage. Exhaust a random card in your Hand.",
    "clash": "Can only be played if every card in your Hand is an Attack. Deal {DAMAGE} damage.",
    "clumsy": "",
    "colossus": "Gain {BLOCK} Block. Until your next turn, take half damage from attacks by Vulnerable enemies.",
    "conflagration": "Deal {DAMAGE} damage to ALL enemies {ROUNDS:time}.",
    "coordinate": "Give another player {STRENGTH} Strength this turn.",
    "corruption": "Skills cost 0. Whenever you play a Skill, Exhaust it.",
    "crimson_mantle": "At the start of your turn, lose 1 HP and gain {AMOUNT} Block.",
    "cruelty": "Your attacks deal an extra {AMOUNT}% damage to Vulnerable enemies.",
    "curse_of_the_bell": "",
    "dark_embrace": "Whenever a card is Exhausted, draw {AMOUNT:card}.",
    "dark_shackles": "The enemy loses {STRENGTH_LOSS} Strength this turn.",
    "dazed": "",
    "debris": "No effect.",
    "debt": "",
    "decay": "At the end of your turn, if this is in your Hand, take {DAMAGE} damage.",
    "defend": "Gain {BLOCK} Block.",
    "demon_form": "At the start of your turn, gain {AMOUNT} Strength.",
    "demonic_shield": "Lose {HP_LOSS} HP. Give another player Block equal to your Block.",
    "discovery": "Choose 1 of {OFFER} random Ironclad cards to add into your Hand. It is free to play this turn.",
    "disintegration": "At the end of your turn, if this is in your Hand, take {AMOUNT} damage.",
    "dismantle": "Deal {DAMAGE} damage. If the enemy is Vulnerable, hit it twice.",
    "distraction": "Add a random Skill into your Hand. It is free to play this turn.",
    "dominate": "Apply {VULNERABLE} Vulnerable. Gain 1 Strength for each Vulnerable on the enemy.",
    "doubt": "At the end of your turn, if this is in your Hand, gain {WEAK} Weak.",
    "dramatic_entrance": "Deal {DAMAGE} damage to ALL enemies.",
    "drum_of_battle": "Draw {CARDS:card}. When this card is Exhausted, gain {ENERGY} Energy.",
    "dual_wield": "Choose an Attack or Power in your Hand. Add {COPIES:copy} of it into your Hand.",
    "enlightenment": "This turn, your cards cost at most 1.",
    "enthralled": "While this is in your Hand, you must play it before any other card.",
    "entrench": "Double your Block{NOW_BLOCK}.",
    "entropy": "At the start of your turn, choose a card in your Hand to Transform into a random card.",
    "equilibrium": "Gain {BLOCK} Block. Retain your Hand this turn.",
    "eternal_armor": "Gain {PLATING} Plating.",
    "evil_eye": "Gain {BLOCK} Block, or twice that if you have Exhausted a card this turn{NOW_BLOCK}.",
    "expect_a_fight": "Gain {ENERGY_PER_ATTACK} Energy for each Attack in your Hand. You cannot gain any more Energy this turn.",
    "exterminate": "Deal {DAMAGE} damage to ALL enemies {ROUNDS:time}.",
    "fasten": "Your Defend and Ultimate Defend cards give {BLOCK} additional Block.",
    "feed": "Deal {DAMAGE} damage. If this kills the enemy, gain {MAX_HP} Max HP.",
    "feeding_frenzy": "Gain {STRENGTH} Strength this turn.",
    "feel_no_pain": "Whenever a card is Exhausted, gain {AMOUNT} Block.",
    "fiend_fire": "Exhaust your Hand. Deal {DAMAGE_PER_CARD} damage for each card Exhausted.",
    "fight_me": "Deal {DAMAGE} damage {HITS:time}. Gain {STRENGTH} Strength. The enemy gains {ENEMY_STRENGTH} Strength.",
    "finesse": "Gain {BLOCK} Block. Draw {CARDS:card}.",
    "fisticuffs": "Deal {DAMAGE} damage. Gain Block equal to the damage dealt{NOW_BLOCK}.",
    "flame_barrier": "Gain {BLOCK} Block. Until your next turn, whenever you are attacked, deal {AMOUNT} damage back.",
    "flash_of_steel": "Deal {DAMAGE} damage. Draw {CARDS:card}.",
    "folly": "",
    "forgotten_ritual": "If you have Exhausted a card this turn, gain {ENERGY} Energy.",
    "frantic_escape": "Push the Sandpit back {TURNS:turn}. This card costs {COST_RISE} more for the rest of combat.",
    "gang_up": "Deal {DAMAGE} damage, plus {PER_ALLY} for each other player who attacked this enemy this turn.",
    "giant_rock": "Deal {DAMAGE} damage.",
    "gold_axe": "Deal damage equal to the number of cards you have played this combat{NOW}.",
    "greed": "",
    "guilty": "",
    "hand_of_greed": "Deal {DAMAGE} damage.",
    "havoc": "Play the top card of your Draw Pile and Exhaust it.",
    "headbutt": "Deal {DAMAGE} damage. Put a card from your Discard Pile on top of your Draw Pile.",
    "hello_world": "At the start of your turn, add a random Common card into your Hand.",
    "hellraiser": "Whenever you draw a card with \"Strike\" in its name, it is played against a random enemy.",
    "hemokinesis": "Lose {HP_LOSS} HP. Deal {DAMAGE} damage.",
    "hidden_gem": "A random card in your Draw Pile without Replay gains Replay {REPLAY}: it is played {REPLAY} extra times.",
    "howl_from_beyond": "Deal {DAMAGE} damage to ALL enemies. At the end of your turn, if this is in your Exhaust Pile, play it and put it in your Discard Pile.",
    "huddle_up": "ALL players draw {CARDS:card}.",
    "impatience": "If you have no Attacks in your Hand, draw {CARDS:card}.",
    "impervious": "Gain {BLOCK} Block.",
    "infection": "At the end of your turn, if this is in your Hand, take {AMOUNT} damage.",
    "infernal_blade": "Add a random Attack into your Hand. It is free to play this turn.",
    "inferno": "At the start of your turn, lose 1 HP. Whenever you lose HP on your turn, deal {AMOUNT} damage to ALL enemies.",
    "inflame": "Gain {STRENGTH} Strength.",
    "injury": "",
    "intercept": "Gain {BLOCK} Block. Until your next turn, attacks aimed at the other players hit you instead.",
    "iron_wave": "Gain {BLOCK} Block. Deal {DAMAGE} damage.",
    "jack_of_all_trades": "Add {COUNT:random Colorless card} into your Hand.",
    "jackpot": "Deal {DAMAGE} damage. Add {COUNT:random Ironclad card} into your Hand. They are free to play this turn.",
    "juggernaut": "Whenever you gain Block, deal {AMOUNT} damage to a random enemy.",
    "juggling": "Add a copy of the third Attack you play each turn into your Hand.",
    "knockdown": "Deal {DAMAGE} damage. Until the end of its turn, the enemy takes double damage from the other players' attacks.",
    "lift": "Give another player {BLOCK} Block.",
    "mad_science_chaos": "Gain {BLOCK} Block. Add a random Ironclad card into your Hand. It is free to play this turn.",
    "mad_science_choking": "Deal {DAMAGE} damage. Whenever you play a card this turn, the enemy loses {PER_CARD} HP.",
    "mad_science_curious": "Your Powers cost {DISCOUNT} less.",
    "mad_science_energized": "Gain {BLOCK} Block. Gain {ENERGY} Energy.",
    "mad_science_expertise": "Gain {STRENGTH} Strength. Gain {DEXTERITY} Dexterity.",
    "mad_science_sapping": "Deal {DAMAGE} damage. Apply {WEAK} Weak. Apply {VULNERABLE} Vulnerable.",
    "mad_science_violence": "Deal {DAMAGE} damage {HITS:time}.",
    "mad_science_wisdom": "Gain {BLOCK} Block. Draw {CARDS:card}.",
    "mangle": "Deal {DAMAGE} damage. The enemy loses {STRENGTH_LOSS} Strength this turn.",
    "master_of_strategy": "Draw {CARDS:card}.",
    "maul": "Deal {DAMAGE} damage {HITS:time}. ALL your Maul cards deal {BONUS} more damage for the rest of combat.",
    "mayhem": "At the start of your turn, play the top card of your Draw Pile.",
    "metamorphosis": "Add {COUNT:random Attack} into your Draw Pile. They are free to play for the rest of combat.",
    "mimic": "Gain Block equal to another player's Block.",
    "mind_blast": "Deal damage equal to the number of cards in your Draw Pile{NOW}.",
    "mind_rot": "While this is in your Hand, Draw Pile or Discard Pile, you draw {DRAW_PENALTY:card} less at the start of each turn.",
    "molten_fist": "Deal {DAMAGE} damage. Double the enemy's Vulnerable.",
    "neows_fury": "Deal {DAMAGE} damage. Put up to {COUNT:card} from your Discard Pile into your Hand.",
    "normality": "While this is in your Hand, you cannot play more than {PLAY_CAP:card} a turn.",
    "nostalgia": "The first Attack or Skill you play each turn goes on top of your Draw Pile.",
    "not_yet": "Heal {HEAL} HP.",
    "offering": "Lose {HP_LOSS} HP. Gain {ENERGY} Energy. Draw {CARDS:card}.",
    "omnislice": "Deal {DAMAGE} damage. Deal the same damage to ALL other enemies.",
    "one_two_punch": "This turn, your next {REPLAYS:Attack} will be played twice.",
    "outmaneuver": "Next turn, gain 2 Energy.",
    "pacts_end": "If you have {REQUIRED_EXHAUSTED} or more cards in your Exhaust Pile, deal {DAMAGE} damage to ALL enemies.",
    "panache": "Every time you play 5 cards in a single turn, deal 10 damage to ALL enemies.",
    "panic_button": "Gain {BLOCK} Block. You cannot gain Block for {TURNS:turn}.",
    "peck": "Deal {DAMAGE} damage {HITS:time}.",
    "perfected_strike": "Deal {DAMAGE} damage, plus {EXTRA_PER_STRIKE} for each card with \"Strike\" in its name in your deck{NOW}.",
    "pillage": "Deal {DAMAGE} damage. Draw cards until you draw a card that is not an Attack.",
    "pommel_strike": "Deal {DAMAGE} damage. Draw {CARDS:card}.",
    "poor_sleep": "",
    "prep_time": "At the start of your turn, gain {VIGOR} Vigor: your next attack deals that much more damage.",
    "primal_force": ("Transform all Attacks in your Hand into Giant Rock.",
                     "Transform all Attacks in your Hand into Giant Rock+."),
    "production": "Gain {ENERGY} Energy.",
    "prolong": "Next turn, gain Block equal to your current Block.",
    "prowess": "Gain {AMOUNT} Strength. Gain {AMOUNT} Dexterity.",
    "purity": "Exhaust up to {COUNT:card} in your Hand.",
    "pyre": "At the start of your turn, gain {AMOUNT} Energy.",
    "rage": "Whenever you play an Attack this turn, gain {AMOUNT} Block.",
    "rally": "ALL players gain {BLOCK} Block.",
    "rampage": "Deal {DAMAGE} damage. This card deals {INCREASE} more damage for the rest of combat.",
    "rebound": "Deal {DAMAGE} damage. Put the next card you play this turn on top of your Draw Pile.",
    "regret": "At the end of your turn, if this is in your Hand, lose 1 HP for each card in your Hand.",
    "relax": "Gain {BLOCK} Block. Next turn, draw 2 cards and gain 2 Energy.",
    "rend": "Deal {DAMAGE} damage, plus {PER_DEBUFF} for each different debuff on the enemy.",
    "restlessness": "If your Hand is empty, draw {CARDS:card} and gain {ENERGY} Energy.",
    "rip_and_tear": "Deal {DAMAGE} damage to a random enemy {HITS:time}.",
    "rolling_boulder": "At the start of your turn, deal {DAMAGE} damage to ALL enemies, then increase this damage by 5.",
    "rupture": "Whenever you lose HP on your turn, gain {AMOUNT} Strength.",
    "salvo": "Deal {DAMAGE} damage. Retain your Hand this turn.",
    "scrawl": "Draw cards until your Hand is full.",
    "second_wind": "Exhaust all non-Attack cards in your Hand. Gain {BLOCK_PER_CARD} Block for each card Exhausted{NOW_BLOCK}.",
    "secret_technique": "Put a Skill from your Draw Pile into your Hand.",
    "secret_weapon": "Put an Attack from your Draw Pile into your Hand.",
    "seeker_strike": "Deal {DAMAGE} damage. Choose 1 of {OFFER} random cards from your Draw Pile to put into your Hand.",
    "setup_strike": "Deal {DAMAGE} damage. Gain {STRENGTH} Strength this turn.",
    "shame": "At the end of your turn, if this is in your Hand, gain {FRAIL} Frail.",
    "shockwave": "Apply {AMOUNT} Weak and {AMOUNT} Vulnerable to ALL enemies.",
    "shrug_it_off": "Gain {BLOCK} Block. Draw {CARDS:card}.",
    "slimed": "Draw {CARDS:card}.",
    "sloth": "While this is in your Hand, you cannot play more than {PLAY_CAP:card} a turn.",
    "soot": "",
    "spite": "Deal {DAMAGE} damage. If you lost HP this turn, hit {HITS_IF_HURT:time} instead.",
    "splash": "Choose 1 of {OFFER} random Ironclad Attacks to add into your Hand. It is free to play this turn.",
    "spore_mind": "No effect.",
    "squash": "Deal {DAMAGE} damage. Apply {VULNERABLE} Vulnerable.",
    "stack": ("Gain Block equal to the number of cards in your Discard Pile{NOW_BLOCK}.",
              "Gain Block equal to the number of cards in your Discard Pile, plus {BONUS}{NOW_BLOCK}."),
    "stampede": "At the end of your turn, a random Attack in your Hand is played against a random enemy.",
    "stoke": ("Exhaust your Hand. Add a random Ironclad card into your Hand for each card Exhausted.",
              "Exhaust your Hand. Add a random upgraded Ironclad card into your Hand for each card Exhausted."),
    "stomp": "Deal {DAMAGE} damage to ALL enemies. Costs 1 less for each Attack you played this turn.",
    "stone_armor": "Gain {PLATING} Plating.",
    "stratagem": "Whenever your Draw Pile is reshuffled, choose a card from it to put into your Hand.",
    "strike": "Deal {DAMAGE} damage.",
    "sword_boomerang": "Deal {DAMAGE} damage to a random enemy {HITS:time}.",
    "tag_team": "Deal {DAMAGE} damage. The next Attack another player plays on this enemy is played twice.",
    "tank": "You take double damage from attacks. The other players take half damage from attacks.",
    "taunt": "Gain {BLOCK} Block. Apply {VULNERABLE} Vulnerable.",
    "tear_asunder": "Deal {DAMAGE} damage. Hit 1 more time for each time you lost HP this combat.",
    "the_bomb": "In {TURNS:turn}, deal 40 damage to ALL enemies.",
    "the_gambit": "Gain {BLOCK} Block. If you take unblocked attack damage this combat, you die.",
    "thinking_ahead": "Draw {CARDS:card}. Put a card from your Hand on top of your Draw Pile.",
    "thrash": "Deal {DAMAGE} damage {HITS:time}. Exhaust a random Attack in your Hand and add its damage to this card.",
    "thrumming_hatchet": "Deal {DAMAGE} damage. At the start of your next turn, return this to your Hand.",
    "thunderclap": "Deal {DAMAGE} damage and apply {VULNERABLE} Vulnerable to ALL enemies.",
    "toric_toughness": "Gain {BLOCK} Block. Gain that much Block again at the start of each of your next {TURNS:turn}.",
    "toxic": "At the end of your turn, if this is in your Hand, take {AMOUNT} damage.",
    "tremble": "Apply {VULNERABLE} Vulnerable.",
    "true_grit": ("Gain {BLOCK} Block. Exhaust a random card in your Hand.",
                  "Gain {BLOCK} Block. Exhaust a card in your Hand."),
    "twin_strike": "Deal {DAMAGE} damage {HITS:time}.",
    "ultimate_defend": "Gain {BLOCK} Block.",
    "ultimate_strike": "Deal {DAMAGE} damage.",
    "unmovable": "The first time you gain Block from a card each turn, double it.",
    "unrelenting": "Deal {DAMAGE} damage. Your next Attack costs 0.",
    "uppercut": "Deal {DAMAGE} damage. Apply {WEAK} Weak. Apply {VULNERABLE} Vulnerable.",
    "vicious": "Whenever you apply Vulnerable, draw {AMOUNT:card}.",
    "void": "Whenever you draw this card, lose 1 Energy.",
    "volley": "Deal {DAMAGE} damage to a random enemy X times.",
    "waste_away": "While this is in your Hand, Draw Pile or Discard Pile, you get {ENERGY_PENALTY} less Energy each turn.",
    "whirlwind": "Deal {DAMAGE} damage to ALL enemies X times.",
    "whistle": "Deal {DAMAGE} damage. Stun the enemy: it skips its next turn.",
    "wish": "Choose a card from your Draw Pile and put it into your Hand.",
    "wither": "At the end of your turn, if this is in your Hand, take {WITHER_DAMAGE} damage.",
    "wound": "",
    "writhe": "",
}

# Numbers that are not a single constant.
_COMPUTED = {
    "DAMAGE": lambda card: card.DAMAGE + card.bonus_damage,
    "WITHER_DAMAGE": lambda card: card.AMOUNT + card.bonus_damage,
}
# An Attack's per-hit damage: what the holder's Strength, Weak and Vigor change.
_HIT_FIELDS = ("DAMAGE", "DAMAGE_PER_CARD")

_FIELD = re.compile(r"\{([A-Z_]+)(?::([^}]+))?\}")


def _plural(phrase, n):
    if n == 1:
        return phrase
    head, _, word = phrase.rpartition(" ")
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        word = word[:-1] + "ies"
    else:
        word += "s"
    return (head + " " if head else "") + word


def template_for(card):
    """The raw template for this copy - the upgraded one if it has one."""
    entry = TEXT[card.card_id]
    if isinstance(entry, tuple):
        return entry[1] if card.upgraded else entry[0]
    return entry


def card_text(card, holder=None, block=None):
    """This copy's text, numbers filled in and keywords added.

    `card` is a Card from create_card, so it already carries its upgrade and
    its per-copy bonus. `holder`, the player whose hand it is in, turns an
    Attack's damage into what it deals from that hand, as the game shows it;
    `block` is the Block it gives them (Combat.hand_blocks, None if none).
    Without them the printed numbers stand (piles, questions). Raises KeyError
    for a card with no entry."""
    from ..Resolution.resolver import Resolver       # imported late: it sits above the cards
    from ._card_enums import CardType
    live = holder is not None and card.card_type is CardType.ATTACK
    template = template_for(card)
    # A worked-out Block card says its total in {NOW_BLOCK}; its {BLOCK} is the
    # printed part of a sum, so it stays printed.
    live_block = holder is not None and block is not None and "{NOW_BLOCK}" not in template

    def fill(match):
        key, word = match.group(1), match.group(2)
        if key == "NOW":
            if not live:
                return ""
            return " (now %d)" % Resolver.damage_amount(holder, None, card.base_damage(holder))
        if key == "NOW_BLOCK":
            return " (now %d)" % block if holder is not None and block is not None else ""
        value = _COMPUTED[key](card) if key in _COMPUTED else getattr(card, key)
        if live and key in _HIT_FIELDS:
            value = Resolver.damage_amount(holder, None, value)
        if live_block and key == "BLOCK":
            value = block
        return "%s %s" % (value, _plural(word, value)) if word else str(value)

    body = _FIELD.sub(fill, template)
    props = card.properties
    front = [name for name, on in (("Unplayable", not props.playable),
                                   ("Innate", props.innate),
                                   ("Retain", props.retain),
                                   ("Ethereal", props.ethereal)) if on]
    parts = [word + "." for word in front]
    if body:
        parts.append(body)
    if props.exhaust:
        parts.append("Exhaust.")
    return " ".join(parts)
