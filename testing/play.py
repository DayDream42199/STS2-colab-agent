"""
play.py -- Interactive terminal client for the combat replica.

Drives combat.py directly (not the RL env.py action-id interface) so a
human can actually play a fight: see hand/HP/enemy intents as text, pick a
card by number, pick a target if needed, end turn, repeat. Supports 1-4
human-controlled players (coop) against a scripted Act 1 encounter. The
player phase shows a "Whose turn?" menu each cycle so whoever's at the
keyboard freely picks who acts next, one card at a time -- see
choose_active_character()'s docstring for why this, not a fixed order or
true real-time concurrency, is the closest fit for one local terminal.

Run from the repo root: python testing/play.py [config.json]
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import random
import sys

from game_engine.entities import Player
from game_engine.cards import (make_starter_deck, make_coop_support_deck, CARD_POOL_IRONCLAD,
                    FACTORIES_BY_RARITY, TargetMode)
from game_engine.enemies import (make_nibbit, make_shrinker_beetle, make_fuzzy_wurm_crawler,
                      make_inklet_trio, make_byrdonis, make_vantom,
                      make_assassin_raider, make_axe_raider, make_brute_raider,
                      make_crossbow_raider, make_tracker_raider, make_cubex_construct,
                      make_fogmog, make_mawler, make_vine_shambler, make_flyconid,
                      make_slithering_strangler, make_snapping_jaxfruit,
                      make_leaf_slime_small, make_leaf_slime_medium,
                      make_twig_slime_small, make_twig_slime_medium, make_wriggler,
                      make_calcified_cultist, make_damp_cultist, make_seapunk,
                      make_sludge_spinner, make_sewer_clam, make_punch_construct,
                      make_haunted_ship, make_phantasmal_gardener_group,
                      make_toadpole, make_toadpole_pair,
                      make_bygone_effigy, make_phrog_parasite,
                      make_ceremonial_beast, make_the_kin,
                      make_corpse_slug, make_fossil_stalker, make_gremlin_merc,
                      make_living_fog, make_two_tailed_rat,
                      make_skulking_colony, make_terror_eel,
                      make_lagavulin_matriarch, make_soul_fysh,
                      make_waterfall_giant,
                      # --- Act 2: Hive ---
                      make_bowlbug_rock, make_bowlbug_egg, make_bowlbug_silk,
                      make_bowlbug_nectar, make_chomper, make_exoskeleton,
                      make_hunter_killer, make_louse_progenitor,
                      make_mysterious_knight, make_myte, make_ovicopter,
                      make_slumbering_beetle, make_spiny_toad, make_the_obscura,
                      make_thieving_hopper, make_tunneler,
                      make_decimillipede_group, make_entomancer,
                      make_infested_prism, make_the_insatiable,
                      make_knowledge_demon, make_kaiser_crab,
                      # --- Act 3: Glory ---
                      make_devoted_sculptor, make_scroll_of_biting, make_axebot,
                      make_fabricator, make_frog_knight, make_globe_head,
                      make_owl_magistrate, make_slimed_berserker,
                      make_living_shield, make_turret_operator,
                      make_the_lost, make_the_forgotten,
                      make_mecha_knight, make_soul_nexus, make_knight_gang,
                      make_queen, make_test_subject, make_aeonglass,
                      make_doormaker,
                      # --- Event-only enemies ---
                      make_the_merchant, make_battle_friend_v1,
                      make_battle_friend_v2, make_battle_friend_v3)
from game_engine.combat import CombatEngine
from game_engine.relics import BURNING_BLOOD, RELIC_POOL_IRONCLAD
from game_engine.entities import seed_content
from testing import config

# The active setup. main() replaces this with the loaded config.json;
# the default keeps the module importable (bench.py, tools/ and the
# tests all import play without ever calling main()).
CONFIG = dict(config.DEFAULTS)
from game_engine.potions import POTION_POOL_IRONCLAD

ENCOUNTERS = {
    "1": ("Nibbit", lambda: [make_nibbit()]),
    "2": ("Shrinker Beetle", lambda: [make_shrinker_beetle()]),
    "3": ("Fuzzy Wurm Crawler", lambda: [make_fuzzy_wurm_crawler()]),
    "4": ("Nibbit + Shrinker Beetle", lambda: [make_nibbit(), make_shrinker_beetle()]),
    "5": ("Inklet Trio", make_inklet_trio),
    "6": ("Byrdonis (Elite)", lambda: [make_byrdonis()]),
    "7": ("Vantom (Boss)", lambda: [make_vantom()]),
    "8": ("Assassin Raider", lambda: [make_assassin_raider()]),
    "9": ("Axe Raider", lambda: [make_axe_raider()]),
    "10": ("Brute Raider", lambda: [make_brute_raider()]),
    "11": ("Crossbow Raider", lambda: [make_crossbow_raider()]),
    "12": ("Tracker Raider", lambda: [make_tracker_raider()]),
    "13": ("Ruby Raiders (3-mix)", lambda: [make_axe_raider(), make_brute_raider(), make_crossbow_raider()]),
    "14": ("Cubex Construct", lambda: [make_cubex_construct()]),
    "15": ("Fogmog", lambda: [make_fogmog()]),
    "16": ("Mawler", lambda: [make_mawler()]),
    "17": ("Vine Shambler", lambda: [make_vine_shambler()]),
    "18": ("Flyconid", lambda: [make_flyconid()]),
    "19": ("Slithering Strangler", lambda: [make_slithering_strangler()]),
    "20": ("Snapping Jaxfruit", lambda: [make_snapping_jaxfruit()]),
    "21": ("Leaf Slime (S)", lambda: [make_leaf_slime_small()]),
    "22": ("Leaf Slime (M)", lambda: [make_leaf_slime_medium()]),
    "23": ("Twig Slime (S)", lambda: [make_twig_slime_small()]),
    "24": ("Twig Slime (M)", lambda: [make_twig_slime_medium()]),
    "25": ("Wriggler", lambda: [make_wriggler()]),
    # --- Underdocks (the other Act 1 region) ---
    "26": ("Calcified Cultist [UD]", lambda: [make_calcified_cultist()]),
    "27": ("Damp Cultist [UD]", lambda: [make_damp_cultist()]),
    "28": ("Seapunk [UD]", lambda: [make_seapunk()]),
    "29": ("Sludge Spinner [UD]", lambda: [make_sludge_spinner()]),
    "30": ("Sewer Clam [UD]", lambda: [make_sewer_clam()]),
    "31": ("Punch Construct [UD]", lambda: [make_punch_construct()]),
    "32": ("Haunted Ship [UD]", lambda: [make_haunted_ship()]),
    "33": ("Phantasmal Gardeners x4 [UD Elite]", make_phantasmal_gardener_group),
    "34": ("Cultist pair [UD]", lambda: [make_calcified_cultist(), make_damp_cultist()]),
    "35": ("Toadpole [UD]", lambda: [make_toadpole()]),
    "36": ("Toadpoles (Weak) x2 [UD]", make_toadpole_pair),
    # --- the rest of Act 1: remaining normals, elites and bosses ---
    "37": ("Corpse Slug [UD]", lambda: [make_corpse_slug()]),
    "38": ("Fossil Stalker [UD]", lambda: [make_fossil_stalker()]),
    "39": ("Gremlin Merc [UD]", lambda: [make_gremlin_merc()]),
    "40": ("Living Fog [UD]", lambda: [make_living_fog()]),
    "41": ("Two-Tailed Rat [UD]", lambda: [make_two_tailed_rat()]),
    "42": ("Bygone Effigy (Elite)", lambda: [make_bygone_effigy()]),
    "43": ("Phrog Parasite (Elite)", lambda: [make_phrog_parasite()]),
    "44": ("Skulking Colony [UD Elite]", lambda: [make_skulking_colony()]),
    "45": ("Terror Eel [UD Elite]", lambda: [make_terror_eel()]),
    "46": ("Ceremonial Beast (Boss)", lambda: [make_ceremonial_beast()]),
    "47": ("The Kin (Boss)", make_the_kin),
    "48": ("Lagavulin Matriarch [UD Boss]", lambda: [make_lagavulin_matriarch()]),
    "49": ("Soul Fysh [UD Boss]", lambda: [make_soul_fysh()]),
    "50": ("Waterfall Giant [UD Boss]", lambda: [make_waterfall_giant()]),
    # --- Act 2: Hive ---
    "51": ("Bowlbug Rock [Hive]", lambda: [make_bowlbug_rock()]),
    "52": ("Bowlbug Egg [Hive]", lambda: [make_bowlbug_egg()]),
    "53": ("Bowlbug Silk [Hive]", lambda: [make_bowlbug_silk()]),
    "54": ("Bowlbug Nectar [Hive]", lambda: [make_bowlbug_nectar()]),
    "55": ("Chomper [Hive]", lambda: [make_chomper()]),
    "56": ("Exoskeleton [Hive]", lambda: [make_exoskeleton()]),
    "57": ("Hunter Killer [Hive]", lambda: [make_hunter_killer()]),
    "58": ("Louse Progenitor [Hive]", lambda: [make_louse_progenitor()]),
    "59": ("Mysterious Knight [Hive]", lambda: [make_mysterious_knight()]),
    "60": ("Myte [Hive]", lambda: [make_myte()]),
    "61": ("Ovicopter [Hive]", lambda: [make_ovicopter()]),
    "62": ("Slumbering Beetle [Hive]", lambda: [make_slumbering_beetle()]),
    "63": ("Spiny Toad [Hive]", lambda: [make_spiny_toad()]),
    "64": ("The Obscura [Hive]", lambda: [make_the_obscura()]),
    "65": ("Thieving Hopper [Hive]", lambda: [make_thieving_hopper()]),
    "66": ("Tunneler [Hive]", lambda: [make_tunneler()]),
    "67": ("Decimillipede x3 [Hive Elite]", make_decimillipede_group),
    "68": ("Entomancer [Hive Elite]", lambda: [make_entomancer()]),
    "69": ("Infested Prism [Hive Elite]", lambda: [make_infested_prism()]),
    "70": ("The Insatiable [Hive Boss]", lambda: [make_the_insatiable()]),
    "71": ("Knowledge Demon [Hive Boss]", lambda: [make_knowledge_demon()]),
    "72": ("Kaiser Crab [Hive Boss]", make_kaiser_crab),
    # --- Act 3: Glory ---
    "73": ("Devoted Sculptor [Glory]", lambda: [make_devoted_sculptor()]),
    "74": ("Scroll of Biting [Glory]", lambda: [make_scroll_of_biting()]),
    "75": ("Axebot [Glory]", lambda: [make_axebot()]),
    "76": ("Fabricator [Glory]", lambda: [make_fabricator()]),
    "77": ("Frog Knight [Glory]", lambda: [make_frog_knight()]),
    "78": ("Globe Head [Glory]", lambda: [make_globe_head()]),
    "79": ("Owl Magistrate [Glory]", lambda: [make_owl_magistrate()]),
    "80": ("Slimed Berserker [Glory]", lambda: [make_slimed_berserker()]),
    "81": ("Living Shield + Turret Operator [Glory]", lambda: [make_living_shield(), make_turret_operator()]),
    "82": ("The Lost + The Forgotten [Glory]", lambda: [make_the_lost(), make_the_forgotten()]),
    "83": ("Mecha Knight [Glory Elite]", lambda: [make_mecha_knight()]),
    "84": ("Soul Nexus [Glory Elite]", lambda: [make_soul_nexus()]),
    "85": ("Knight Gang x3 [Glory Elite]", make_knight_gang),
    "86": ("Queen + Amalgam [Glory Boss]", make_queen),
    "87": ("Test Subject [Glory Boss]", lambda: [make_test_subject()]),
    "88": ("Aeonglass [Glory Boss]", lambda: [make_aeonglass()]),
    "89": ("Doormaker [Glory Boss]", lambda: [make_doormaker()]),
    # --- Event-only encounters ---
    "90": ("The Merchant??? [Event]", lambda: [make_the_merchant()]),
    "91": ("Battle Friend V1.0 [Event]", lambda: [make_battle_friend_v1()]),
    "92": ("Battle Friend V2.0 [Event]", lambda: [make_battle_friend_v2()]),
    "93": ("Battle Friend V3.0 [Event]", lambda: [make_battle_friend_v3()]),
}

# A small fixed run. Real STS gauntlets are randomized/branching; this is
# just enough sequencing to make card rewards mean something.
# Each entry's factory returns either a single Enemy or a list of Enemies
# (Inklet Trio always fights as a group of 3) -- _play_combat_loop's caller
# below normalizes either shape.
GAUNTLET = [
    ("Nibbit", make_nibbit),
    ("Shrinker Beetle", make_shrinker_beetle),
    ("Fuzzy Wurm Crawler", make_fuzzy_wurm_crawler),
    ("Inklet Trio", make_inklet_trio),
    ("Byrdonis (Elite)", make_byrdonis),
    ("Vantom (Boss)", make_vantom),
]


def hp_bar(current, maximum, width=20):
    frac = max(0, current) / max(1, maximum)
    filled = int(width * frac)
    return f"[{'#' * filled}{'-' * (width - filled)}] {current}/{maximum}"


def status_str(entity):
    parts = [f"{s.name} {v}" for s, v in entity.statuses.items() if v]
    return "  [" + ", ".join(parts) + "]" if parts else ""


def print_enemies(engine):
    print("\n-- Enemies --")
    for i, e in enumerate(engine.enemies):
        if not e.alive:
            print(f"  {i}: {e.name} -- defeated")
            continue
        intent = "?"
        if e.current_move is not None:
            intent = e.current_move.name
            if e.current_move.damage:
                # show effective damage (with the enemy's own Strength applied),
                # matching how real STS telegraphs intent damage
                eff = e.deal_attack_damage(e.current_move.damage)
                intent += f" ({eff} dmg)"
        block_note = f"  Block {e.block}" if e.block else ""
        print(f"  {i}: {e.name}  HP {hp_bar(e.hp, e.max_hp)}{block_note}  "
              f"Intent: {intent}{status_str(e)}")


def print_player(player):
    print(f"\n-- {player.name} --  HP {hp_bar(player.hp, player.max_hp)}  "
          f"Block {player.block}  Energy {player.energy}/{player.max_energy}"
          f"{status_str(player)}")
    print("Hand:")
    for i, c in enumerate(player.hand):
        cost = c.current_cost(player)
        name = c.name + ("+" if c.upgraded else "")
        print(f"  {i}: [{cost}] {name} -- {c.current_description()}")


def print_pile(pile, title):
    print(f"\n-- {title} ({len(pile)} cards) --")
    if not pile:
        print("  (empty)")
        return
    for i, c in enumerate(pile):
        cost = c.current_cost()
        name = c.name + ("+" if c.upgraded else "")
        print(f"  {i}: [{cost}] {name} -- {c.current_description()}")


def print_relics(player):
    print(f"\n-- {player.name}'s Relics ({len(player.relics)}) --")
    if not player.relics:
        print("  (none)")
        return
    for r in player.relics:
        print(f"  [{r.rarity}] {r.name} -- {r.description}")


def print_potions(player):
    print(f"\n-- {player.name}'s Potions ({len(player.potions)}/{player.potion_slots} slots) --")
    if not player.potions:
        print("  (none)")
        return
    for i, p in enumerate(player.potions):
        print(f"  {i}: [{p.rarity}] {p.name} -- {p.description}")


def print_new_log(engine, since):
    for line in engine.log[since:]:
        print(f"  > {line}")
    return len(engine.log)


def choose_enemy_target(engine):
    alive = engine.enemies_alive()
    if len(alive) == 1:
        return alive[0]
    print("Choose target:")
    for i, e in enumerate(engine.enemies):
        if e.alive:
            print(f"  {i}: {e.name} ({e.hp}/{e.max_hp} HP)")
    while True:
        raw = ask("> target #: ")
        if raw.isdigit() and int(raw) < len(engine.enemies) and engine.enemies[int(raw)].alive:
            return engine.enemies[int(raw)]
        print("Invalid target.")


COMMANDS = (
    ("<#>", "play that card"), ("e", "end turn"), ("d", "draw pile"),
    ("p", "discard pile"), ("r", "relics"), ("u", "use potion"),
    ("?", "help"), ("q", "quit"),
)


def print_commands():
    """The command legend, shown once at the start of a combat and on '?'.

    It used to be reprinted in full before EVERY action -- ~110 characters
    ahead of each card play, several times a turn -- which buried the board
    state it was supposed to sit under."""
    print()
    print("  " + "   ".join(f"{k}={v}" for k, v in COMMANDS))


class QuitGame(Exception):
    """The player asked to stop -- 'q', Ctrl+C, or end of input."""


def ask(prompt: str = "> ") -> str:
    """Every prompt in this module goes through here.

    There are 14 input() sites and only two of them used to guard anything,
    so Ctrl+D or Ctrl+C escaped as EOFError/KeyboardInterrupt from whichever
    prompt happened to be live and printed a traceback at the player:

        File "play.py", line 440, in player_take_action
        EOFError: EOF when reading a line

    Both now raise QuitGame, which main() turns into the same clean exit as
    typing 'q'. Already strips, so callers need not."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise QuitGame()


def interactive_choice(engine, player, options, prompt, kind):
    """Answer a CombatEngine.request_choice prompt at the terminal.

    Thirteen cards say "choose a card" and every one of them used to resolve
    with a coin flip, because there was no way to ask. Installed on the
    engine in run_combat/run_gauntlet.

    Prompts through ask(), so Ctrl+D/Ctrl+C here quits the game cleanly
    rather than silently choosing for you."""
    print()
    print(f"{prompt} ({player.name}):")
    for i, c in enumerate(options):
        cost = c.current_cost(player)
        print(f"  {i}: {c.name}{'+' if c.upgraded else ''} "
              f"[{cost}] {c.current_description()}")
    while True:
        raw = ask("> choose #: ")
        if raw.isdigit() and int(raw) < len(options):
            return options[int(raw)]
        print("Invalid choice.")


def choose_active_character(engine, pending):
    """Prompt for which not-yet-ended living player acts next. Real STS2
    co-op is simultaneous; a single local terminal can't offer true
    concurrent input, so instead of forcing a fixed turn order, the
    human(s) at the keyboard get free choice of who acts each cycle --
    play a card as A, then B, then back to A, in whatever order feels
    right, rather than being locked into alternating turns. Shows every
    pending character's hand up front, not just HP/energy, so that
    choice can actually be informed by what each of them can do."""
    if len(pending) == 1:
        return pending[0]
    print_enemies(engine)
    for p in pending:
        print_player(p)
    print("\nWhose turn?")
    for i, p in enumerate(pending):
        print(f"  {i}: {p.name}  HP {p.hp}/{p.max_hp}  Energy {p.energy}/{p.max_energy}")
    while True:
        raw = ask("> choose character: ")
        if raw.isdigit() and int(raw) < len(pending):
            return pending[int(raw)]
        print("Invalid choice.")


def choose_ally_target(engine, player):
    allies = engine.other_players(player)
    if not allies:
        print("No living ally -- this card will fizzle.")
        return None
    if len(allies) == 1:
        return allies[0]
    print("Choose ally:")
    for i, p in enumerate(allies):
        print(f"  {i}: {p.name} ({p.hp}/{p.max_hp} HP)")
    while True:
        raw = ask("> ally #: ")
        if raw.isdigit() and int(raw) < len(allies):
            return allies[int(raw)]
        print("Invalid choice.")


def use_potion_prompt(engine, player, log_pos):
    """Returns the new log_pos if a potion was actually used (a real
    action -- the caller hands control back to character-select), or
    None if nothing happened (empty inventory, cancelled, or no valid
    enemy target) -- matching the 'd'/'p'/'r' info-only commands, which
    re-prompt the SAME player rather than consuming their turn."""
    print_potions(player)
    if not player.potions:
        return None
    print("  c: cancel")
    while True:
        raw = ask("> use which potion? ").lower()
        if raw == "c":
            return None
        if not raw.isdigit() or int(raw) >= len(player.potions):
            print("Invalid choice.")
            continue
        potion = player.potions[int(raw)]
        target = None
        if potion.target == "enemy":
            if not engine.enemies_alive():
                print("No enemies left to target.")
                return None
            target = choose_enemy_target(engine)
        ok = engine.use_potion(player, potion, target=target)
        log_pos = print_new_log(engine, log_pos)
        if not ok:
            print("Could not use that potion.")
            return None
        return log_pos


def player_take_action(engine, player, log_pos):
    """Handle exactly ONE meaningful action for this player (a successful
    card play, or ending their turn) and return (ended, new_log_pos).
    Invalid input and info-only commands ('d'/'p') loop back to re-prompt
    the SAME player rather than handing control away, since they aren't
    real game actions. The caller re-shows the character-select prompt
    (choose_active_character) after every action instead of letting this
    player keep going -- so whoever's at the keyboard picks who acts
    next, card by card, rather than being locked into a fixed order."""
    while True:
        print_enemies(engine)
        print_player(player)
        raw = ask(f"\n{player.name}> ").lower()
        if raw == "q":
            raise QuitGame()
        if raw in ("?", "h", "help"):
            print_commands()
            continue
        if raw == "e":
            return True, log_pos
        if raw == "d":
            print_pile(player.draw_pile, f"{player.name}'s Draw Pile")
            continue
        if raw == "p":
            print_pile(player.discard_pile, f"{player.name}'s Discard Pile")
            continue
        if raw == "r":
            print_relics(player)
            continue
        if raw == "u":
            ended = use_potion_prompt(engine, player, log_pos)
            if ended is not None:
                log_pos = ended
                return False, log_pos
            continue
        if not raw.isdigit() or int(raw) >= len(player.hand):
            print("Invalid selection.")
            continue
        card = player.hand[int(raw)]
        card_cost = card.current_cost(player)
        if card_cost != "X" and card_cost > player.energy:
            print(f"{card.name} costs {card_cost} energy, you have {player.energy}.")
            continue

        target = None
        ally_target = None
        if card.target == TargetMode.SINGLE_ENEMY:
            if not engine.enemies_alive():
                print("No enemies left to target.")
                continue
            target = choose_enemy_target(engine)
        elif card.target == TargetMode.ALLY:
            ally_target = choose_ally_target(engine, player)
        elif card.target == TargetMode.SELF_OR_ALLY:
            choice = ask("Target self or ally? (s/a): ").lower()
            if choice == "a":
                ally_target = choose_ally_target(engine, player)

        ok = engine.play_card(player, card, target=target, ally_target=ally_target)
        log_pos = print_new_log(engine, log_pos)
        if not ok:
            print("Could not play that card.")
            continue
        return False, log_pos


def run_combat(players, enemies):
    engine = CombatEngine(players, enemies, scale_enemies=(len(players) > 1))
    engine.choice_resolver = interactive_choice
    engine.start_player_turn()
    return _play_combat_loop(engine, players)


def offer_card_reward(player, num_players, extra_from_prayer_wheel=True,
                       rarity=None, was_elite=False):
    """Real-STS-style reward screen: pick 1 of 3 random cards from the full
    ported Ironclad pool, or skip. Picked cards go into deck_template, which
    Player.start_combat() rebuilds the draw pile from -- so it persists into
    the next fight of the run. Multiplayer-only cards (e.g. Tank) are excluded
    from solo-run rewards, matching real STS2's Is_Multiplayer restriction.
    Any relic with an on_card_added hook (Frozen/Molten/Toxic Egg, and now
    Book of Five Rings) fires here, the moment a card genuinely enters the
    deck -- not when it's drawn/played.

    rarity: restrict the offer to one tier (White Star's Rare-only drop).
    was_elite: whether the fight just won was an elite, which is what gates
    that White Star drop."""
    label = f"{rarity} card reward" if rarity else "card reward"
    print(f"\n{'*' * 60}\n{player.name}: choose a {label}\n{'*' * 60}")
    pool = FACTORIES_BY_RARITY[rarity] if rarity else CARD_POOL_IRONCLAD
    # The config's card filter applies to REWARDS too, not just the starting
    # deck -- otherwise a "Strike and Defend only" run would be handed a
    # Perfected Strike after the first win.
    _permitted = config.card_filter(CONFIG)
    pool = [factory for factory in pool if _permitted(factory().name)]
    if not pool:
        return
    if num_players == 1:
        pool = [factory for factory in pool if not factory().is_multiplayer]
    factories = random.sample(pool, k=min(3, len(pool)))
    offered = [factory() for factory in factories]
    for i, c in enumerate(offered):
        cost = c.current_cost()
        print(f"  {i}: [{cost}] {c.name} -- {c.current_description()}")
    print("  s: skip")
    while True:
        raw = ask("> pick a card, or 's' to skip: ").lower()
        if raw == "s":
            print("Skipped.")
            break
        if raw.isdigit() and int(raw) < len(offered):
            chosen = offered[int(raw)]
            player.deck_template.append(chosen)
            print(f"Added {chosen.name} to {player.name}'s deck.")
            for relic in player.relics:
                if relic.on_card_added:
                    relic.on_card_added(player, chosen)
            break
        print("Invalid choice.")

    if extra_from_prayer_wheel and any(r.name == "Prayer Wheel" for r in player.relics):
        print(f"\n(Prayer Wheel: an additional card reward)")
        offer_card_reward(player, num_players, extra_from_prayer_wheel=False,
                          was_elite=was_elite)

    # White Star: "Elites drop an additional Rare card reward." Gated on the
    # fight actually having been an elite, and on `rarity is None` so the
    # extra Rare drop can't itself trigger another one.
    if (rarity is None and was_elite
            and any(r.name == "White Star" for r in player.relics)):
        print(f"\n(White Star: an additional Rare card reward from the elite)")
        offer_card_reward(player, num_players, extra_from_prayer_wheel=False,
                          rarity="Rare")


def offer_relic_reward(player):
    """Relic reward screen, parallel to offer_card_reward: pick 1 of 2
    random relics not already owned, or skip. This replica only has
    regular (non-elite/non-boss) fights so far -- real STS2 doesn't hand
    out a relic after every regular fight, but with no elites/chests/shops
    yet (see README known gaps) there's no other relic-drop opportunity to
    hook this into, so it rides along after each gauntlet win for now."""
    owned = {r.name for r in player.relics}
    pool = [r for r in RELIC_POOL_IRONCLAD if r.name not in owned]
    if not pool:
        return
    print(f"\n{'*' * 60}\n{player.name}: choose a relic reward\n{'*' * 60}")
    offered = random.sample(pool, k=min(2, len(pool)))
    for i, r in enumerate(offered):
        print(f"  {i}: [{r.rarity}] {r.name} -- {r.description}")
    print("  s: skip")
    while True:
        raw = ask("> pick a relic, or 's' to skip: ").lower()
        if raw == "s":
            print("Skipped.")
            return
        if raw.isdigit() and int(raw) < len(offered):
            chosen = offered[int(raw)]
            player.add_relic(chosen)
            print(f"{player.name} obtains {chosen.name}!")
            return
        print("Invalid choice.")


def offer_potion_reward(player):
    """Potion reward screen, parallel to offer_card_reward/offer_relic_reward.
    Real STS2 gates potion pickup on having a free slot -- if the player's
    inventory is already full, the reward is skipped entirely rather than
    forcing a discard choice (matching how a full potion belt behaves at
    a real combat-reward screen)."""
    if len(player.potions) >= player.potion_slots:
        print(f"\n{player.name}'s potion belt is full -- no potion reward offered.")
        return
    print(f"\n{'*' * 60}\n{player.name}: choose a potion reward\n{'*' * 60}")
    offered = random.sample(POTION_POOL_IRONCLAD, k=min(2, len(POTION_POOL_IRONCLAD)))
    for i, p in enumerate(offered):
        print(f"  {i}: [{p.rarity}] {p.name} -- {p.description}")
    print("  s: skip")
    while True:
        raw = ask("> pick a potion, or 's' to skip: ").lower()
        if raw == "s":
            print("Skipped.")
            return
        if raw.isdigit() and int(raw) < len(offered):
            chosen = offered[int(raw)]
            player.potions.append(chosen)
            print(f"{player.name} obtains {chosen.name}!")
            return
        print("Invalid choice.")


def run_gauntlet(players):
    """Runs the fixed GAUNTLET sequence, carrying HP and deck (including
    reward picks) forward between fights. Player.start_combat() (called by
    CombatEngine's constructor) always resets hp to max_hp -- we override
    that with the carried-over value right after construction, before any
    turn starts, so HP genuinely persists across fights like a real run.

    Real STS2 co-op: a player downed mid-fight revives at 1 HP on the next
    floor if a teammate survived to win the fight (confirmed on wiki.gg --
    see README's source-reliability note). A downed player doesn't end the
    fight early either -- combat.py's _check_victory_defeat only calls
    defeat once EVERY player is down, so teammates can still finish a fight
    solo and trigger the revive below."""
    for name, make_enemy in GAUNTLET:
        if not any(p.hp > 0 for p in players):
            print("\nYour whole party has fallen. Run over.")
            return
        print(f"\n{'#' * 60}\nEncounter: {name}\n{'#' * 60}")

        carried_hp = {p: p.hp for p in players}
        spawned = make_enemy()
        enemies = spawned if isinstance(spawned, list) else [spawned]
        engine = CombatEngine(list(players), enemies, scale_enemies=(len(players) > 1))
        engine.choice_resolver = interactive_choice
        for p in players:
            p.hp = carried_hp[p]
            p.alive = p.hp > 0
        engine.start_player_turn()
        engine = _play_combat_loop(engine, players)

        if not engine.victory:
            print("\nRun over.")
            return
        for p in players:
            if p.hp <= 0:
                p.hp = 1
                p.alive = True
                print(f"{p.name} revives at 1 HP!")
        was_elite = any(e.category == "elite" for e in enemies)
        for p in players:
            if p.alive:
                # Each reward screen is gated by config.json, so a restricted
                # run does not silently reintroduce what it switched off.
                if CONFIG["content"]["card_rewards"]:
                    offer_card_reward(p, len(players), was_elite=was_elite)
                if CONFIG["content"]["relic_rewards"]:
                    offer_relic_reward(p)
                if CONFIG["content"]["potion_rewards"]:
                    offer_potion_reward(p)

    print(f"\n{'=' * 60}\nGauntlet clear -- you survived all {len(GAUNTLET)} encounters!\n{'=' * 60}")


def _play_combat_loop(engine, players):
    """Shared player-phase/enemy-phase loop, factored out so run_combat()
    (one fight) and run_gauntlet() (fight, already-started engine) both
    drive the same turn structure.

    The player phase lets whoever's at the keyboard freely choose WHICH
    living player acts next, each cycle, instead of either locking player
    1 into fully resolving their turn before player 2 even starts, or
    forcing a fixed alternating order -- neither matches real STS2's
    simultaneous co-op turns, and free choice of actor is the closest a
    single local terminal (one input stream) can get to that."""
    print_commands()
    turn_log_pos = len(engine.log)
    while not engine.is_over:
        print(f"\n{'=' * 60}\nTurn {engine.turn_number} -- Player phase\n{'=' * 60}")
        active = [p for p in players if p.alive]
        done = set()
        while len(done) < len(active) and not engine.is_over:
            pending = [p for p in active if p not in done]
            p = choose_active_character(engine, pending)
            ended, turn_log_pos = player_take_action(engine, p, turn_log_pos)
            if ended:
                done.add(p)
        if engine.is_over:
            break

        engine.end_player_turn()
        if engine.is_over:
            break

        print(f"\n{'-' * 60}\nEnemy phase\n{'-' * 60}")
        turn_log_pos = print_new_log(engine, turn_log_pos)
        engine.run_enemy_turn()
        turn_log_pos = print_new_log(engine, turn_log_pos)

        if not engine.is_over:
            engine.start_player_turn()

    print("\n" + "=" * 60)
    print("VICTORY!" if engine.victory else "DEFEAT...")
    print("=" * 60)
    return engine


# Region is read off the encounter label, which is the only place it is
# recorded -- ENCOUNTERS is a flat dict. Tier comes from the real
# Enemy.category, so it cannot drift from the data. bench.py imports both
# from here; the dependency can only run this way round, since bench
# already imports play.
REGION_TAGS = (
    ("[UD", "Act 1  Underdocks"),
    ("[Hive", "Act 2  Hive"),
    ("[Glory", "Act 3  Glory"),
    ("[Event", "Event-only"),
)

REGION_ORDER = ["Act 1  Overgrowth", "Act 1  Underdocks", "Act 2  Hive",
                "Act 3  Glory", "Event-only"]

TIER_LABEL = {"normal": "normals", "elite": "elites", "boss": "bosses"}


def region_of(name: str) -> str:
    for tag, region in REGION_TAGS:
        if tag in name:
            return region
    return "Act 1  Overgrowth"


def tier_of(make_enemies) -> str:
    """normal / elite / boss, from the enemies themselves."""
    built = make_enemies()
    built = built if isinstance(built, list) else [built]
    cats = {e.category for e in built}
    for tier in ("boss", "elite"):
        if tier in cats:
            return tier
    return "normal"


def print_encounter_menu():
    """All 93 encounters, grouped by region and by normal/elite/boss.

    This used to be one flat 93-line list, so picking a fight meant
    scrolling past every fight in the game and reading the "[Hive]" /
    "[Glory]" tags off the names to work out where anything was."""
    groups = {}
    for key, (name, make_enemies) in ENCOUNTERS.items():
        groups.setdefault((region_of(name), tier_of(make_enemies)),
                          []).append((key, name))
    for region in REGION_ORDER:
        for tier in ("normal", "elite", "boss"):
            block = groups.get((region, tier))
            if not block:
                continue
            print()
            print("  -- {}  |  {} --".format(region, TIER_LABEL[tier]))
            # Two columns: 93 entries one-per-line is what made this a wall.
            cells = ["{:>3}: {}".format(k, n) for k, n in block]
            for i in range(0, len(cells), 2):
                row = "".join(c.ljust(40) for c in cells[i:i + 2])
                print("   " + row.rstrip())


def main(config_path=None):
    """Set the game up from config.json, then hand over to the player.

    Anything the config leaves as null/"ask" still gets prompted for, so the
    default config behaves exactly like the old hardcoded startup. A config
    that specifies everything starts the fight immediately -- which is what
    a UI launching this wants."""
    global CONFIG
    try:
        CONFIG = config.load(config_path)
    except config.ConfigError as exc:
        print("Config error: {}".format(exc))
        print("Fix config.json, or delete it to play the full game.")
        sys.exit(2)

    print("Slay the Spire 2 (coop) -- Combat Replica")
    print("=" * 60)
    print(config.describe(CONFIG))

    if CONFIG.get("seed") is not None:
        # Pins the deck shuffles and the HP a factory rolls, so a UI can
        # hand the same fight to a human and an agent.
        random.seed(CONFIG["seed"])
        seed_content(CONFIG["seed"])

    players = config.build_party(CONFIG)

    mode = CONFIG["mode"]
    if mode == "ask":
        print("\nGame mode:")
        print(f"  1: Gauntlet run ({len(GAUNTLET)} fights, card reward after each win)")
        print("  2: Single fight (pick an encounter)")
        mode = "single" if ask("> mode [1]: ") == "2" else "gauntlet"

    if mode == "single":
        choice = CONFIG.get("encounter")
        if choice is None:
            print("\nChoose an encounter:")
            print_encounter_menu()
            choice = ask("\n> encounter [1]: ")
        if choice not in ENCOUNTERS:
            print("  no encounter {!r} -- falling back to 1".format(choice))
            choice = "1"
        name, make_enemies = ENCOUNTERS[choice]
        print("\nEncounter: {}".format(name))
        run_combat(players, make_enemies())
    else:
        run_gauntlet(players)


if __name__ == "__main__":
    # `python testing/play.py my_config.json` to use a different setup, which
    # is how a UI would launch several configurations side by side.
    _path = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        main(_path)
    except QuitGame:
        print("Quitting.")
        sys.exit(0)
