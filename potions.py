"""
Potion model + a real Ironclad-relevant potion pool, sourced from the wiki
the same way cards/enemies/relics were: `slaythespire.wiki.gg`'s
Potions_List page. Players start with 3 potion slots (wiki-confirmed);
Ascension-scaled slot counts aren't modeled (this replica has no
Ascension system at all).

Unlike relics (persistent, standing effects), potions are single-use
consumables: `Player.potions` is the inventory (capped at
`Player.potion_slots`), and using one in play.py removes it and calls its
`effect(engine, player, target=None)` immediately -- no on_pickup/
on_turn_start/etc. hooks needed. A potion's effect function CAN still
call `player.register_hook(...)` directly if it needs a delayed or
multi-turn effect (Clarity Extract, Radiant Tincture) -- register_hook
isn't relic-specific, any code holding a `player` reference can use it.

Deliberately NOT ported, same discipline as relics.py -- see README's
known gaps for the full list: potions needing other classes' unbuilt
resource systems (Focus/Orbs, Star, Doom, Forge/Summon), a temporary/
combat-scoped card upgrade distinct from the permanent `Card.upgraded`
flag (Blessing of the Forge -- upgrading a HAND card mutates the same
Card object that lives in deck_template, since start_combat() only
shallow-copies the deck list, not the Card objects themselves, so a
"real" .upgrade() there would incorrectly persist forever), a temporary
cost override on an EXISTING deck card for the same shallow-copy reason
(Touch of Insanity -- Attack/Skill/Power Potion avoid this by creating a
disposable one-off Card instance that never enters deck_template, same
trick as the Vexing Puzzlebox relic), per-card "Replay" (Soldier's Stew),
a "retain hand" mechanic (Stable Serum), hand-cost randomization that
would need the same disposable-vs-persistent-instance care as above
(Snecko Oil), an unbuilt "Buffer" status (Lucky Tonic), and "take an
extra turn" (Ambergris -- would need real turn-loop reentrancy in
play.py, not just a Potion effect function).
"""

from dataclasses import dataclass
from typing import Callable

from statuses import StatusType
from cards import CardType, FACTORIES_BY_TYPE


@dataclass
class Potion:
    name: str
    rarity: str
    description: str
    target: str  # "self" | "enemy" | "all_enemies" | "none"
    effect: Callable  # (engine, player, target=None) -> None


def _make_disposable_card_from_pool(card_type, rng):
    """Same trick as the Vexing Puzzlebox relic: a fresh Card instance,
    cost forced to 0, that's added directly to hand and never touches
    deck_template -- safe to mutate freely since nothing else references it.

    `rng` is the drinking player's own rng (see the module note on seeding).
    It is a required parameter rather than defaulting to the global `random`
    module, so a future caller cannot silently reintroduce an unseeded draw."""
    candidates = FACTORIES_BY_TYPE.get(card_type)
    if not candidates:
        return None
    factory = rng.choice(candidates)
    card = factory()
    card.cost = 0
    return card


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

def _add_disposable_card(engine, player, card_type, potion_name):
    card = _make_disposable_card_from_pool(card_type, player.rng)
    if card is None:   # no card of that type in the pool -- fizzle, don't crash
        engine.log.append(f"{potion_name} finds no card to add, fizzles")
        return
    player.add_to_hand(card)
    engine.log.append(f"{player.name} adds {card.name} (free this turn) to their Hand ({potion_name})")


def _attack_potion(engine, player, target=None):
    _add_disposable_card(engine, player, CardType.ATTACK, "Attack Potion")


def _skill_potion(engine, player, target=None):
    _add_disposable_card(engine, player, CardType.SKILL, "Skill Potion")


def _power_potion(engine, player, target=None):
    _add_disposable_card(engine, player, CardType.POWER, "Power Potion")


def _block_potion(engine, player, target=None):
    gained = player.gain_block_noncard(12)
    engine.log.append(f"{player.name} gains {gained} block (Block Potion)")


def _dexterity_potion(engine, player, target=None):
    player.add_status(StatusType.DEXTERITY, 2)
    engine.log.append(f"{player.name} gains 2 Dexterity (Dexterity Potion)")


def _energy_potion(engine, player, target=None):
    player.energy += 2
    engine.log.append(f"{player.name} gains 2 Energy (Energy Potion)")


def _explosive_ampoule(engine, player, target=None):
    for e in engine.enemies:
        if e.alive:
            e.take_damage(10, source_is_attack=False, log=engine.log, label="Explosive Ampoule")


def _fire_potion(engine, player, target=None):
    if target is not None and target.alive:
        target.take_damage(20, source_is_attack=False, log=engine.log, label="Fire Potion")


def _flex_potion(engine, player, target=None):
    player.add_status(StatusType.STRENGTH_THIS_TURN, 5)
    engine.log.append(f"{player.name} gains 5 Strength this turn (Flex Potion)")


def _speed_potion(engine, player, target=None):
    player.add_status(StatusType.DEXTERITY_THIS_TURN, 5)
    engine.log.append(f"{player.name} gains 5 Dexterity this turn (Speed Potion)")


def _strength_potion(engine, player, target=None):
    player.add_status(StatusType.STRENGTH, 2)
    engine.log.append(f"{player.name} gains 2 Strength (Strength Potion)")


def _swift_potion(engine, player, target=None):
    engine.draw_extra(player, 3)
    engine.log.append(f"{player.name} draws 3 cards (Swift Potion)")


def _vulnerable_potion(engine, player, target=None):
    if target is not None and target.alive:
        target.add_status(StatusType.VULNERABLE, 3, applier=player)
        engine.log.append(f"{target.name} gains 3 Vulnerable (Vulnerable Potion)")


def _weak_potion(engine, player, target=None):
    if target is not None and target.alive:
        target.add_status(StatusType.WEAK, 3)
        engine.log.append(f"{target.name} gains 3 Weak (Weak Potion)")


def _blood_potion(engine, player, target=None):
    before = player.hp
    player.heal(round(player.max_hp * 0.2))
    engine.log.append(f"{player.name} heals {player.hp - before} HP (Blood Potion)")


# ---------------------------------------------------------------------------
# Special (Potion-Shaped Rock is needed for the Petrified Toad relic)
# ---------------------------------------------------------------------------

def _potion_shaped_rock(engine, player, target=None):
    if target is not None and target.alive:
        target.take_damage(15, source_is_attack=False, log=engine.log, label="Potion-Shaped Rock")


# "Special" rarity, like Ambergris/Foul Potion/Glowwater Potion -- not part
# of the normal reward pool below, only obtainable via a specific source
# (here, the Petrified Toad relic). Exported standalone, mirroring how
# relics.py exports BURNING_BLOOD outside RELIC_POOL_IRONCLAD.
POTION_SHAPED_ROCK = Potion("Potion-Shaped Rock", "Special", "Deal 15 damage.", "enemy", _potion_shaped_rock)


# ---------------------------------------------------------------------------
# Uncommon
# ---------------------------------------------------------------------------

def _fysh_oil(engine, player, target=None):
    player.add_status(StatusType.STRENGTH, 1)
    player.add_status(StatusType.DEXTERITY, 1)
    engine.log.append(f"{player.name} gains 1 Strength and 1 Dexterity (Fysh Oil)")


def _regen_potion(engine, player, target=None):
    player.add_status(StatusType.REGEN, 5)
    engine.log.append(f"{player.name} gains 5 Regen (Regen Potion)")


def _fortifier(engine, player, target=None):
    gained = player.gain_block_noncard(player.block * 2)  # triples total: existing + 2x more
    engine.log.append(f"{player.name} triples their Block (now {player.block}) (Fortifier)")


def _heart_of_iron(engine, player, target=None):
    player.add_status(StatusType.PLATED_ARMOR, 7)
    engine.log.append(f"{player.name} gains 7 Plating (Heart of Iron)")


def _liquid_bronze(engine, player, target=None):
    player.add_status(StatusType.THORNS, 3)
    engine.log.append(f"{player.name} gains 3 Thorns (Liquid Bronze)")


def _potion_of_binding(engine, player, target=None):
    for e in engine.enemies:
        if e.alive:
            e.add_status(StatusType.WEAK, 1)
            e.add_status(StatusType.VULNERABLE, 1, applier=player)
    engine.log.append("ALL enemies gain 1 Weak and 1 Vulnerable (Potion of Binding)")


def _powdered_demise(engine, player, target=None):
    if target is None or not target.alive:
        return

    def _tick(engine, player, **kwargs):
        if kwargs.get("enemy") is target and target.alive:
            target.take_damage(9, source_is_attack=False, log=engine.log, label="Powdered Demise")

    player.register_hook("enemy_turn_end", _tick)
    engine.log.append(f"{target.name} will lose 9 HP at the end of each of its turns (Powdered Demise)")


def _gamblers_brew(engine, player, target=None):
    discard_count = len(player.hand)
    player.discard_pile.extend(player.hand)
    player.hand = []
    engine.draw_extra(player, discard_count)
    engine.log.append(f"{player.name} discards and redraws {discard_count} cards (Gambler's Brew)")


def _ashwater(engine, player, target=None):
    """Real Ashwater lets the player choose how many/which cards to
    Exhaust. This replica's potion-use UI (play.py) doesn't have a
    multi-select prompt, so it Exhausts the player's WHOLE current hand --
    a reasonable, clearly-documented simplification, not a silent one."""
    for card in list(player.hand):
        engine.exhaust_card(player, card)
    engine.log.append(f"{player.name} exhausts their whole Hand (Ashwater -- simplified: no partial-select UI)")


# ---------------------------------------------------------------------------
# Rare
# ---------------------------------------------------------------------------

def _fruit_juice(engine, player, target=None):
    player.max_hp += 5
    player.hp += 5
    engine.log.append(f"{player.name}'s Max HP rises by 5 (Fruit Juice)")


def _ship_in_a_bottle(engine, player, target=None):
    gained = player.gain_block_noncard(10)
    player.pending_relic_block += 10
    engine.log.append(f"{player.name} gains {gained} block now, and 10 more next turn (Ship in a Bottle)")


def _mazaleths_gift(engine, player, target=None):
    player.add_status(StatusType.RITUAL, 1)
    engine.log.append(f"{player.name} gains 1 Ritual (Mazaleth's Gift)")


def _bottled_potential(engine, player, target=None):
    player.draw_pile.extend(player.hand)
    player.draw_pile.extend(player.discard_pile)
    player.hand = []
    player.discard_pile = []
    player.rng.shuffle(player.draw_pile)
    engine.draw_extra(player, 5)
    engine.log.append(f"{player.name} shuffles their cards together and draws 5 (Bottled Potential)")


def _fairy_in_a_bottle(engine, player, target=None):
    """Same pattern as the Lizard Tail relic (revive once), but this is a
    single-use consumable discarded on use rather than a standing relic --
    installed via a plain hp_lost hook, no relic_counters flag needed
    since the potion itself is removed from inventory once used, and this
    hook naturally only exists for the rest of THIS combat (start_combat()
    wipes player.hooks every fight)."""
    fired = {"done": False}

    def _on_hp_lost(engine, player, **kwargs):
        if not fired["done"] and player.hp <= 0:
            fired["done"] = True
            player.hp = round(player.max_hp * 0.3)
            player.alive = True
            engine.log.append(f"{player.name} would have died, but Fairy in a Bottle heals to {player.hp} HP!")

    player.register_hook("hp_lost", _on_hp_lost)
    engine.log.append(f"{player.name} feels a fairy watching over them (Fairy in a Bottle)")


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# The "port everything" batch: the 22 potions previously deferred. Each was
# blocked on a named engine feature; those now exist (see README).
# ---------------------------------------------------------------------------

def _colorless_potion(engine, player, target=None):
    """Choose 1 of 3 random Colorless cards to add into your Hand. It's free
    to play this turn. No UI to choose, so it takes the first of the 3 --
    same simplification the Attack/Skill/Power Potions already use."""
    from cards import COLORLESS_POOL
    picks = player.rng.sample(COLORLESS_POOL, k=min(3, len(COLORLESS_POOL)))
    card = picks[0]()
    card.cost = 0        # a fresh instance, never in deck_template: safe to mutate
    player.add_to_hand(card)
    engine.log.append(f"{player.name} adds {card.name} (free this turn) to their Hand (Colorless Potion)")


def _blessing_of_the_forge(engine, player, target=None):
    """Upgrade all cards in your Hand for the rest of combat. This was
    deferred specifically because a bare card.upgrade() on a hand card would
    persist for the whole run; upgrade_for_combat() reverts it at combat end."""
    n = sum(1 for c in player.hand if player.upgrade_for_combat(c))
    engine.log.append(f"{player.name} upgrades {n} card(s) for this combat (Blessing of the Forge)")


def _clarity_extract(engine, player, target=None):
    player.bonus_draw_turns += 3
    engine.draw_extra(player, 1)
    engine.log.append(f"{player.name} draws 1 now and 1 extra for 3 turns (Clarity Extract)")


def _cure_all(engine, player, target=None):
    player.energy += 1
    engine.draw_extra(player, 2)
    engine.log.append(f"{player.name} gains 1 energy and draws 2 (Cure All)")


def _duplicator(engine, player, target=None):
    player.extra_card_plays += 1
    engine.log.append(f"{player.name}'s next card is played an extra time (Duplicator)")


def _radiant_tincture(engine, player, target=None):
    player.energy += 1
    player.bonus_energy_turns += 3
    engine.log.append(f"{player.name} gains 1 energy now and 1 for 3 turns (Radiant Tincture)")


def _stable_serum(engine, player, target=None):
    player.retain_hand_turns += 2
    engine.log.append(f"{player.name} retains their Hand for 2 turns (Stable Serum)")


def _touch_of_insanity(engine, player, target=None):
    """Choose a card in your Hand. It is free to play this combat. Auto-picks
    the most expensive card, which is the only choice worth making."""
    playable = [c for c in player.hand if c.current_cost() != "X"]
    if not playable:
        engine.log.append("Touch of Insanity finds no card to discount, fizzles")
        return
    chosen = max(playable, key=lambda c: c.current_cost())
    player.set_temp_cost(chosen, 0, scope="combat")
    engine.log.append(f"{chosen.name} is free to play this combat (Touch of Insanity)")


def _beetle_juice(engine, player, target=None):
    """Enemy's attacks deal 30% less damage for the next 4 turns. Mechanically
    identical to the Shrink debuff this replica already models (a flat 0.7
    outgoing multiplier), so it reuses it with a 4-turn duration rather than
    adding a second status with the same numbers."""
    if target is not None and target.alive:
        target.add_status(StatusType.SHRINK, 4, applier=player)
        engine.log.append(f"{target.name}'s attacks deal 30% less for 4 turns (Beetle Juice)")


def _distilled_chaos(engine, player, target=None):
    """Play the top 3 cards of your Draw Pile."""
    for _ in range(3):
        if not player.draw_pile:
            break
        card = player.draw_pile.pop()
        engine.auto_play_card(player, card, source="Distilled Chaos")


def _droplet_of_precognition(engine, player, target=None):
    """Choose a card in your Draw Pile and add it into your Hand. No UI, so
    it takes the top card."""
    if not player.draw_pile:
        engine.log.append("Droplet of Precognition finds an empty draw pile, fizzles")
        return
    card = player.draw_pile.pop()
    player.add_to_hand(card)
    engine.log.append(f"{player.name} pulls {card.name} into hand (Droplet of Precognition)")


def _entropic_brew(engine, player, target=None):
    """Fill all your empty potion slots with random potions."""
    added = 0
    while len(player.potions) < player.potion_slots:
        player.potions.append(player.rng.choice(POTION_POOL_IRONCLAD))
        added += 1
    engine.log.append(f"{player.name} fills {added} potion slot(s) (Entropic Brew)")


def _gigantification_potion(engine, player, target=None):
    player.next_attack_multiplier = 3
    engine.log.append(f"{player.name}'s next Attack deals triple damage (Gigantification Potion)")


def _liquid_memories(engine, player, target=None):
    """Put a card from your Discard Pile into your Hand. It costs 0 this
    turn. Auto-picks the most expensive card in the discard pile."""
    if not player.discard_pile:
        engine.log.append("Liquid Memories finds an empty discard pile, fizzles")
        return
    costed = [c for c in player.discard_pile if c.current_cost() != "X"]
    chosen = max(costed, key=lambda c: c.current_cost()) if costed else player.discard_pile[0]
    player.discard_pile.remove(chosen)
    player.add_to_hand(chosen)
    player.set_temp_cost(chosen, 0, scope="turn")
    engine.log.append(f"{player.name} returns {chosen.name} to hand, free this turn (Liquid Memories)")


def _lucky_tonic(engine, player, target=None):
    player.add_status(StatusType.BUFFER, 1)
    engine.log.append(f"{player.name} gains 1 Buffer (Lucky Tonic)")


def _orobic_acid(engine, player, target=None):
    """Add a random Attack, Skill, and Power into your Hand. They're free to
    play this turn."""
    for ctype in (CardType.ATTACK, CardType.SKILL, CardType.POWER):
        _add_disposable_card(engine, player, ctype, "Orobic Acid")


def _shackling_potion(engine, player, target=None):
    """ALL enemies lose 7 Strength this turn."""
    for e in engine.enemies_alive():
        e.add_status(StatusType.STRENGTH_LOSS_THIS_TURN, 7, applier=player)
    engine.log.append("ALL enemies lose 7 Strength this turn (Shackling Potion)")


def _snecko_oil(engine, player, target=None):
    """Draw 7 cards. Randomize the cost of cards in your Hand this turn.
    The randomized costs go through set_temp_cost so they revert -- writing
    card.cost directly would randomize the deck permanently."""
    engine.draw_extra(player, 7)
    for c in player.hand:
        if c.current_cost() == "X":
            continue
        player.set_temp_cost(c, player.rng.randint(0, 3), scope="turn")
    engine.log.append(f"{player.name} draws 7 and randomizes hand costs (Snecko Oil)")


def _soldiers_stew(engine, player, target=None):
    """All cards containing Strike gain 1 Replay this combat."""
    n = 0
    for pile in (player.hand, player.draw_pile, player.discard_pile):
        for c in pile:
            if "Strike" in c.name:
                player.grant_replay(c, 1)
                n += 1
    engine.log.append(f"{n} Strike card(s) gain 1 Replay this combat (Soldier's Stew)")


def _ambergris(engine, player, target=None):
    """Heal for 50% of your max HP. If used in combat, take an extra turn."""
    before = player.hp
    player.heal(round(player.max_hp * 0.5))
    player.extra_turns += 1
    engine.log.append(f"{player.name} heals {player.hp - before} HP and takes an extra turn (Ambergris)")


def _foul_potion(engine, player, target=None):
    """Deal 12 damage to EVERYONE -- enemies AND players, the user included.
    The 'throw it at the Merchant for 100 Gold' half needs a shop, which
    this replica has no concept of."""
    for e in engine.enemies_alive():
        e.take_damage(12, source_is_attack=False, log=engine.log, label="Foul Potion")
    for p in engine.players_alive():
        p.take_damage(12, source_is_attack=False, log=engine.log, label="Foul Potion")


def _glowwater_potion(engine, player, target=None):
    """Exhaust your Hand. Draw 10 cards."""
    for c in list(player.hand):
        engine.exhaust_card(player, c)
    engine.draw_extra(player, 10)
    engine.log.append(f"{player.name} exhausts their hand and draws 10 (Glowwater Potion)")


POTION_POOL_IRONCLAD = [
    # Common (Any class)
    Potion("Attack Potion", "Common", "Choose 1 of 3 random Attack cards to add into your Hand. It's free to play this turn.", "none", _attack_potion),
    Potion("Skill Potion", "Common", "Choose 1 of 3 random Skill cards to add into your Hand. It's free to play this turn.", "none", _skill_potion),
    Potion("Power Potion", "Common", "Choose 1 of 3 random Power cards to add into your Hand. It's free to play this turn.", "none", _power_potion),
    Potion("Block Potion", "Common", "Gain 12 Block.", "none", _block_potion),
    Potion("Dexterity Potion", "Common", "Gain 2 Dexterity.", "none", _dexterity_potion),
    Potion("Energy Potion", "Common", "Gain 2 energy.", "none", _energy_potion),
    Potion("Explosive Ampoule", "Common", "Deal 10 damage to ALL enemies.", "all_enemies", _explosive_ampoule),
    Potion("Fire Potion", "Common", "Deal 20 damage.", "enemy", _fire_potion),
    Potion("Flex Potion", "Common", "Gain 5 Strength. At the end of your turn, lose 5 Strength.", "none", _flex_potion),
    Potion("Speed Potion", "Common", "Gain 5 Dexterity. At the end of your turn, lose 5 Dexterity.", "none", _speed_potion),
    Potion("Strength Potion", "Common", "Gain 2 Strength.", "none", _strength_potion),
    Potion("Swift Potion", "Common", "Draw 3 cards.", "none", _swift_potion),
    Potion("Vulnerable Potion", "Common", "Apply 3 Vulnerable.", "enemy", _vulnerable_potion),
    Potion("Weak Potion", "Common", "Apply 3 Weak.", "enemy", _weak_potion),
    # Common (Ironclad)
    Potion("Blood Potion", "Common (Ironclad)", "Heal for 20% of your Max HP.", "none", _blood_potion),

    # Uncommon
    Potion("Fysh Oil", "Uncommon", "Gain 1 Strength and 1 Dexterity.", "none", _fysh_oil),
    Potion("Regen Potion", "Uncommon", "Gain 5 Regen.", "none", _regen_potion),
    Potion("Fortifier", "Uncommon", "Triple your Block.", "none", _fortifier),
    Potion("Heart of Iron", "Uncommon", "Gain 7 Plating.", "none", _heart_of_iron),
    Potion("Liquid Bronze", "Uncommon", "Gain 3 Thorns.", "none", _liquid_bronze),
    Potion("Potion of Binding", "Uncommon", "Apply 1 Weak and 1 Vulnerable to ALL enemies.", "all_enemies", _potion_of_binding),
    Potion("Powdered Demise", "Uncommon", "Enemy loses 9 HP at the end of each of its turns.", "enemy", _powdered_demise),
    Potion("Gambler's Brew", "Uncommon", "Discard any number of cards, then draw that many.", "none", _gamblers_brew),
    Potion("Ashwater", "Uncommon (Ironclad)", "Exhaust any number of cards in your Hand.", "none", _ashwater),

    # Rare
    Potion("Fruit Juice", "Rare", "Gain 5 Max HP.", "none", _fruit_juice),
    Potion("Ship in a Bottle", "Rare", "Gain 10 Block. Next turn, gain 10 Block.", "none", _ship_in_a_bottle),
    Potion("Mazaleth's Gift", "Rare", "Gain 1 Ritual.", "none", _mazaleths_gift),
    Potion("Bottled Potential", "Rare", "Shuffle ALL your cards into your Draw Pile. Draw 5 cards.", "none", _bottled_potential),
    Potion("Fairy in a Bottle", "Rare", "When your HP would be reduced to 0, instead this potion is discarded and you heal to 30% of your Max HP.", "none", _fairy_in_a_bottle),
    # --- the "port everything" batch ---
    Potion("Colorless Potion", "Common", "Choose 1 of 3 random Colorless cards to add into your Hand. It's free to play this turn.", "none", _colorless_potion),
    Potion("Blessing of the Forge", "Uncommon", "Upgrade all cards in your Hand for the rest of combat.", "none", _blessing_of_the_forge),
    Potion("Clarity Extract", "Uncommon", "Draw 1 card. At the start of your next 3 turns, draw 1 additional card.", "none", _clarity_extract),
    Potion("Cure All", "Uncommon", "Gain 1 energy. Draw 2 cards.", "none", _cure_all),
    Potion("Duplicator", "Uncommon", "This turn, your next card is played an extra time.", "none", _duplicator),
    Potion("Radiant Tincture", "Uncommon", "Gain 1 energy. Gain an additional 1 energy at the start of your next 3 turns.", "none", _radiant_tincture),
    Potion("Stable Serum", "Uncommon", "Retain your Hand for 2 turns.", "none", _stable_serum),
    Potion("Touch of Insanity", "Uncommon", "Choose a card in your Hand. It is free to play this combat.", "none", _touch_of_insanity),
    Potion("Beetle Juice", "Rare", "Enemy's attacks deal 30% less damage for the next 4 turns.", "enemy", _beetle_juice),
    Potion("Distilled Chaos", "Rare", "Play the top 3 cards of your Draw Pile.", "none", _distilled_chaos),
    Potion("Droplet of Precognition", "Rare", "Choose a card in your Draw Pile and add it into your Hand.", "none", _droplet_of_precognition),
    Potion("Entropic Brew", "Rare", "Fill all your empty potion slots with random potions.", "none", _entropic_brew),
    Potion("Gigantification Potion", "Rare", "The next Attack you play deals triple damage.", "none", _gigantification_potion),
    Potion("Liquid Memories", "Rare", "Put a card from your Discard Pile into your Hand. It costs 0 this turn.", "none", _liquid_memories),
    Potion("Lucky Tonic", "Rare", "Gain 1 Buffer.", "none", _lucky_tonic),
    Potion("Orobic Acid", "Rare", "Add a random Attack, Skill, and Power into your Hand. They're free to play this turn.", "none", _orobic_acid),
    Potion("Shackling Potion", "Rare", "ALL enemies lose 7 Strength this turn.", "all_enemies", _shackling_potion),
    Potion("Snecko Oil", "Rare", "Draw 7 cards. Randomize the cost of cards in your Hand this turn.", "none", _snecko_oil),
    Potion("Soldier's Stew", "Rare (Ironclad)", "All cards containing Strike gain 1 Replay this combat.", "none", _soldiers_stew),
]

# Special tier: obtainable only from specific sources, never the normal
# reward pool -- same treatment as POTION_SHAPED_ROCK above.
AMBERGRIS = Potion("Ambergris", "Special", "Heal for 50% of your max HP. If used in combat, take an extra turn.", "none", _ambergris)
FOUL_POTION = Potion("Foul Potion", "Special", "Deal 12 damage to EVERYONE.", "none", _foul_potion)
GLOWWATER_POTION = Potion("Glowwater Potion", "Special", "Exhaust your Hand. Draw 10 cards.", "none", _glowwater_potion)
SPECIAL_POTIONS = [POTION_SHAPED_ROCK, AMBERGRIS, FOUL_POTION, GLOWWATER_POTION]


# ---------------------------------------------------------------------------
# Stable potion ids, for env.py's observation. Same contract as
# cards.CARD_IDS / relics.RELIC_IDS.
# ---------------------------------------------------------------------------
ALL_POTIONS = sorted({p.name for p in POTION_POOL_IRONCLAD}
                     | {p.name for p in SPECIAL_POTIONS})
POTION_IDS = {name: i for i, name in enumerate(ALL_POTIONS)}
TOTAL_POTION_IDS = len(POTION_IDS)


def potion_id(potion) -> int:
    return POTION_IDS.get(potion.name, -1)
