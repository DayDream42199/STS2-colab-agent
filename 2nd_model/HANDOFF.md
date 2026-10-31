# Handoff — what changed

Your combat module landed and works. This round is **content and hooks**: the
card pool went from 3 cards to 219, and `combat.py` grew an event system to
support them.

A real 2-player co-op fight now runs end to end over the wire — join, play,
readiness-gated turn advance, private errors. Verified against a live server,
not just in unit tests.

## Start here

```bash
cd Server && python main.py
```

`REQUIRED_PLAYERS` lives in `Server/config.py` (currently 2). See
**COMBAT_INTERFACE.md** for the seam between your module and `session.py`, and
for how to add a card.

## Your `Combat` — what was added, and why

`GameEngine/Combat/combat.py` is still yours; the shape is unchanged. Roughly
120 lines were added on top:

| Added | Why |
|---|---|
| `_emit` / `_emit_for` / `GameEvent` dispatch | Powers are just statuses with an `on_event` hook. Without this, ~40 cards have nowhere to live. `_emit_for` derives events from the resolver's own result dicts, so `Resolver` stayed static and knows nothing about events. |
| `MAX_EVENT_DEPTH = 3` | A reaction may cause a reaction. Bounded so two powers cannot ping-pong forever. |
| `COUNTED_EVENTS` → `unit.turn_counters` | Cards that ask "how much HP did I lose this turn" read a counter instead of doing their own bookkeeping. |
| `_resolve_target` covering all 7 `TargetType`s | `ALL_ALLIES`, `RANDOM_ALLY`, `RANDOM_ENEMY` were unreachable. Also validates: a dead or non-existent target now raises instead of resolving. |
| `_build_draw_pile` innate handling | Innate cards go last after the shuffle, since the pile is drawn from the end. No special case in the draw loop. |
| Exhaust-pile routing, `retain`, `ethereal`, `retain_hand` | `CardProperties` flags that nothing enforced. |
| `act`, `scale_enemies` on the constructor; scaling in `start()` | Real STS2 co-op: enemy HP × players × act factor, and enemy Block × 2 for two players. Off with one player. |
| Enemy turns aim at nobody | Every enemy move lands on every living player, as in the game (`_enemy_target` and `_first_alive_ally` are gone). |
| `_enemy_dict` in `to_dict()` | An attack intent carries `damage`: per player, after the enemy's Strength and Weak and their Vulnerable, worked out as the state is sent. Uses `Resolver.damage_amount`, the side-effect-free damage maths (Vigor is now spent in `after_attack_dealt`, not while being read). |
| `_enemy_enters`, `ENEMY_TURN_START` | An enemy's `on_combat_start` runs as it arrives (Cubex's Block and Artifact). `ENEMY_TURN_START` is emitted as the enemy phase begins; Sandpit counts down there. |
| `_tick_statuses(..., after_enemy_turn)` | Players' Vulnerable, Weak and Frail count down at the end of the enemy turn, and skip their first count-down - the game's rule. They used to tick at the end of the player's turn, so a player's last turn of Vulnerable was gone before the enemies swung. |
| `Dummy1`'s block intent shows the scaled Block | Your file. With two players it announced 2 Block and gained 4, because co-op scaling doubles enemy Block in the resolver. Its intent now says 4. Attack and debuff intents still drive what it does (tests pin it to "attack for 5"); Block alone uses the printed `BLOCK = 2`, since the resolver does the scaling. |
| Auto-played cards aim at a random enemy | Havoc, Cascade, Mayhem and the rest used to take the weakest enemy, the reference engine's choice. The game's `CardCmd.AutoPlay` picks at random. |
| `_play_from_top` | Havoc and Cascade play "the top card(s)": picked when they resolve, with the discard shuffled in when the draw pile runs dry, all lifted before any is played - the game's `AutoPlayFromDrawPile`. Havoc on an empty draw pile used to do nothing. |
| `_play_from_exhaust`, at end of turn | A card with `PLAYS_FROM_EXHAUST_AT_TURN_END` (Howl from Beyond) plays itself out of the exhaust pile, then goes to the discard pile. It used to need a status armed by playing it first, and stayed in the exhaust pile replaying every turn. `end_player_turn` returns early if that ends the fight. |
| `_spend_on_play`, `_spend_status` | Unrelenting and One-Two Punch now apply statuses (`free_attack`, `one_two_punch`) the client can see, as in the game; `Ally.free_next_attack` and `extra_attack_plays` are gone. A free Attack is spent by any Attack played, auto-played ones included, which is the game's rule. |
| `card_cost` walks statuses in `COST_ORDER` | So a free Attack is priced last and Tangled's +1 cannot survive it. |
| `answer_choice` accepts `PendingChoice.STOP` (-1) | Purity and Neow's Fury are "up to N" in the game (its selector allows zero picks) but forced every pick here. A question asked with `can_stop=True` may now be stopped; `Context.ask` and `PendingChoice` (in `Context/context.py`) carry the flag, and it goes out on the wire as `can_stop`. Any other question refuses -1. The terminal client takes `choose stop`. |
| `_ally_dict`, `hand_costs`, `hand_damages` in `to_dict()` | Each ally carries `hand_cost`: what every card in hand costs to play now (Stomp's discount, Tangled, Corruption, free grants), `"X"`, or `None` if unplayable - the same number `play_card` charges (a free card is now a free copy: `free_copy`, see the last row on the other cards). And `hand_damage`: one hit of each Attack after the holder's Strength, Weak and Vigor, before the target (`None` for non-Attacks), from the new `Card.base_damage(ally)`. The terminal client prints both, e.g. `[1] strike  dmg 8`, and marks upgrades with `+`. They are the third and fourth parallel arrays beside `hand_upgraded` / `hand_replay`: COMBAT_INTERFACE.md said a third is the point to collapse them into one `hand_cards` array, which is your call since it changes the wire. |
| `pile_view` in `to_dict()` | Each ally carries `piles`: draw, discard and exhaust as lists of `{"id", "upgraded"}` - objects, not more parallel arrays. The draw pile is sorted by rarity then id, as the game's `NCardPileScreen` sorts it, so the order is never leaked. The terminal client shows pile counts on each player's line and the contents with `piles [player_id]`. |
| Card text: `Cards/_text.py`, `hand_text`, pile `text`, `option_text` | Every one of the 219 cards has text, written from what its code does here, with its numbers filled from its own constants after upgrade - so the text cannot disagree with the card. Sent with the hand, on each pile entry, and on each option of a question (`PendingChoice.to_dict`); the terminal client prints it after each card. In hand an Attack's damage is shown after the holder's Strength and Weak, as the game shows it, so the client no longer prints `hand_damage` beside it. A new card needs an entry or `tests/test_card_text.py` fails. |
| `Combat.hand_blocks(ally)`, `Card.base_block` / `block_gains`, `Resolver.block_amount` | The Block each card in hand gives its player, after Dexterity, Frail, Unmovable and Fasten - the same arithmetic `_resolve_instant_block` now uses, changing nothing while it is worked out. Not sent on the wire (a plugin reads it in-process); the hand text shows it. `tests/test_cost.py` plays every card in seven situations and checks the Block gained against it. |
| Optional plugin: `plugin_host.py` (new), `session.py`, `main.py`, `config.PLUGIN`, `ClientMessage.IDENTIFY` | Your `Session` now takes an optional plugin (named in `config.py`, loaded from your empty `Server/Plugins/` folder). Without one nothing changes. With one, it is called at combat start, turn start, each play/answer (with the card's cost, damage and Block before the play), each turn end (before the turn moves on), round end, a player leaving and combat end, and every outgoing message passes through its `format_message` per recipient - broadcasts are split per player only then. `add_player`, `remove_player` and `handle` are wrapped by `_delivered` for that. Clients may send `identify` (`{"role": "agent"}`). A plugin that fails is reported and skipped. Contract in COMBAT_INTERFACE.md, tests in `tests/test_plugin.py`. |
| Combat log: `combat_log.py` (new), `session.py`, `main.py`, `config.LOG_DIR` | Every fight goes to `2nd_model/logs/` as JSON lines: joins, setup, each turn's state, every play / answer / end turn, refusals, leaving, the outcome; plugins add lines with `session.log_event` and clients may attach a `decision` to an action. `Session` now always has a `seed` (new `seed=` argument; passing your own `rng` still works and logs no seed), and reads `ACT` / `SCALE_ENEMIES` from class attributes like `ENEMY_TYPE_IDS` so a replay can set them. `handle` is split: `_dispatch` does what it did, `handle` also logs refusals. `python combat_log.py <file>` replays a fight and checks every turn against the log. Tests in `tests/test_combat_log.py`. |
| Effects and state say a bit more | Effects now carry `action` (`play` / `choose` / `left`), and for a play `card_id`, `upgraded`, `target_id` (an answer: `option`); each player in the state carries `ended_turn`. All additive. The terminal client prints "p2 played bash+ on e1" and "(ended)". |
| Three Block rules now as in the game | **Fasten** used to grant a second Block after a Defend, so Dexterity counted twice and Unmovable doubled only half; it is now part of the card's own Block (`FastenPower.ModifyBlockAdditive`), and Ultimate Defend counts as a Defend too (`CardTag.Defend`) - `test_free21.py`'s "Fasten ignores Ultimate Defend" check changed to match. **Entrench**'s doubling is unpowered (`ValueProp.Unpowered`): Dexterity and Frail no longer touch it (`InstantBlock(powered=False)`, `StatusEffect.BLOCK_POWERED_ONLY`). **Second Wind** exhausts and gains Block one card at a time, so Dexterity counts per card, as `SecondWind.OnPlay` does. |
| Toric Toughness's later turns | `DelayedBlock` gave a fixed 5 on the next two turns, so Toric Toughness+ gave 7, 5, 5. As the game's `ToricToughnessPower` it now gives again what the play really gained (7, 7, 7; with Dexterity or Frail as they were when played), each play its own grant. That later Block is not from a card: `InstantBlock(card=False)`, so Unmovable skips it as Dexterity and Frail do. |
| Block from powers is not card Block | Feel No Pain, Plating, Rage, Crimson Mantle, Beacon of Hope and Prolong's next-turn Block are `ValueProp.Unpowered` in the game, so Dexterity, Frail and Unmovable never touched them; here they did. Their `InstantBlock`s are now `powered=False, card=False`. |
| `Card.base_damage(ally)`; seven cards read it | Body Slam, Fiend Fire, Gold Axe, Mind Blast, Ashen Strike, Perfected Strike and Pact's End worked their damage out inside `get_effects`. That sum moved into `base_damage`, which `get_effects` now reads, so the preview and the hit share one line. What they deal is unchanged (the card matrix and every suite agree). |
| The Ironclad: `Units/Allies/ironclad.py` (new), `config.ALLY_TYPE_ID = "ironclad"` | The game's `Models.Characters.Ironclad`: 80 HP with no roll, 3 energy, 5 Strike / 4 Defend / 1 Bash (Burning Blood heals after a fight, so it is left out). The server now plays it; `testally1` stays for the tests, which name it. `tests/live/choice_server.py` sets `config.ALLY_TYPE_ID` back to the test unit, since it patches that unit's deck. `tests/test_combat_log.py` fights a Leaf Slime (M) instead of a Twig Slime (S), which the Ironclad killed in one round, before any round end could be logged. |
| `Combat.legal_actions(ally)`, `legal_actions` in each ally's state | Everything a player may send right now, shaped like the message that does it: `{"type": "play_card", "hand_index", "target_id"}` per card × valid target, `{"type": "end_turn"}`, or - with a question waiting - `{"type": "choose", "option_index"}` per option and -1 to stop. It makes `play_card`'s checks in `play_card`'s order and rolls nothing (a random-target card is one action, target `None`). `tests/test_legal_actions.py` plays 40 random fights through `Session` and, at every decision, tries every listed action and every other one on a copy: all listed are accepted, all others refused (about 35,000 tried). The log's play / choose / end turn lines carry the set that was open, for the analyzer's "what they could have done". `Session` now also refuses `end_turn` from a defeated player, as `play_card` already did. |
| Waiting: `Combat.end_turn` / `wait` / `may_wait`, `ClientMessage.WAIT`; your `session.py` and `combat_log.py` | Anyone may act whenever, so an agent needs a way to let its teammates move first. **Who has ended now lives in `Combat.ended_turn`**, not `Session.ready` (that is now a read-only property over it), so `legal_actions` alone says what a player may send. `wait` is listed only while someone else can still move the turn on (a question to answer, or not ended and not waiting); any play, answer, end turn or departure clears it. So a round can never stall on waits. A wait changes nothing in the fight: it is answered with `ready_changed` (which gains `waiting`), logged as `wait`, and replayed. `ready_changed` also goes out when a player leaves mid-fight. Each ally's state carries `ended_turn` (from `Combat` now) and `waiting`. The end-turn refusals moved into `Combat.end_turn`, with the same messages. `tests/test_wait.py`; `test_legal_actions.py` now tries `wait` too. |
| One random stream per purpose: `Context/rng_streams.py` (new) | One shared `rng` meant a reshuffle changed which move an enemy rolled next turn. Now, as the game's `RunRngSet`: `shuffle`, `card_generation`, `card_selection`, `targets`, `monster_ai`, `niche` (monster HP), plus `answers` (a question answered at random, headless or after a player left), each seeded from the seed and its name, the same in every process. `Combat(rng=...)` takes the streams, or one `random.Random` to seed them (all the tests), or nothing, in which case it draws a seed and keeps it in `combat.seed`. `combat.rng` and `context.rng` still exist, as the `niche` stream; `context.rngs` is the set. 48 card, status and enemy files now draw from the stream the game uses for that card (checked one by one against the decompiled code); every draw and every card put into the draw pile at random uses `shuffle`. Enemies get `monster_ai` for their moves from the session and from summons. No unseeded fallback is left: a unit with no rng takes its base HP, or the top of `HP_RANGE` (the game's HP before its roll). Two tests had passed by seed luck and were fixed: `test_intercept.py`'s "auto-played attack takes the weakest enemy" (it is random, as the row above says) and `test_combat_log.py`'s tampered replay. Tests: `tests/test_rng_streams.py`. |
| Headbutt cannot pick itself | Found by the new streams. In the game the played card sits in the play pile while it resolves, so Headbutt's "put a card from your discard on top" never offers that Headbutt. Here it was already in the discard when the question was read. `Context.played` is the copy being played; Headbutt leaves it out. The card matrix has 67 fewer rows, all Headbutt's. |
| Unexpected errors: `session._guarded`, `Session._crashed`, `main.py` | An exception that is not a refusal (a bug in a card) used to propagate out of `handle` and stop the server. Now the traceback goes to the console and to the log (an `error` line), the sender gets an error message, everyone gets the state as it now stands (part of the action may have happened), and the fight goes on. `main.py`'s loop has a last net around each event too. Refusals are unchanged. |
| Unmovable as the game's `UnmovablePower` | It doubled "the first Block of the turn". The game doubles Block from a card or a move while this turn's gains from *other* card plays are fewer than its amount: every gain of one play is doubled (Second Wind 5 + 5 = 20 - `test_cost.py`'s 15 is now 20), it stacks, a power's own Block is neither doubled nor counted, and it belongs to the card's owner - your card's Block to a teammate is doubled, a teammate's card giving you Block is not. So each card play now has a number (`Context.play_id`, stamped on its `InstantBlock`s and on its questions' answers - each Replay play its own, as each is its own `CardPlay`), each unit keeps `card_blocks` (this turn's card Block gains by play, only those above 0), and Unmovable uses a new hook, `StatusEffect.modify_card_block`, asked of the card owner's statuses. `BLOCK_CARD_ONLY` is gone, and `hand_blocks` no longer raises and restores the turn counter between gains. Checks in `tests/test_ironclad_game.py`. |
| The plugin exists: `Server/Plugins/aura.py`, `card_groups.py` (new, in your empty `Plugins/` folder) | `config.PLUGIN = "Plugins.aura"` now finds a plugin, so the server runs with it. It changes nothing for players. A client that identifies as the agent gets, per player, a descriptor for each card in hand (`hand_cards`), in each pile (added to the pile entries) and in the deck (`deck_cards`), and for each option of a question (`option_cards`): type, cost, target, keywords, damage, hits, Block, the statuses it applies by scope (self / target / all allies / all enemies), and its groups. The groups: **now** every non-Power, **scale** every Power, **team** if it damages or debuffs an enemy, buffs every player, or touches a teammate, **self** if it gives you Block, buffs you, draws you cards, gives you energy, heals you, changes your own cards (makes, moves, exhausts, upgrades) or plays other cards. Every Attack, Skill and Power is team or self; only Statuses and Curses can be neither. They are read by playing each card once in a sandbox fight and looking at what changed; a status counts by `STATUS_ROLES` (what it does to whoever holds it, so Juggernaut is team and Demon Form self). `python -m Plugins.card_groups` from `Server/` prints every card's groups. Tests: `tests/test_card_groups.py`. |
| The agent's action menu: `Server/Plugins/action_space.py` (new), in `aura.py` | The agent picks from one fixed menu of 113 actions: 10 hand slots × 10 targets (none, 6 enemies, 3 teammates), end turn, wait, 10 option slots, and stop. The agent's state and every `ready_changed` it gets carry `action_mask` (1 where open) and `action_targets` (the unit in each target slot). The mask is `legal_actions` laid onto the menu. Players get nothing new. |
| Scripted teammates: `Server/Plugins/teammates.py` (new) | Five bots that pick from `legal_actions`: aggressive, defensive, scaling, team, random. They play through the real session with the aura plugin, to check the analyzer against players whose style is known. Each styled bot stands out on its own trait over all its turns (`tests/test_teammates.py`, 100 fights). Registers one ally type, `teammateironclad` (the Ironclad on a mixed deck), when imported. |
| The Characteristic Analyzer: `Server/Plugins/analyzer.py` (new), in `aura.py` | The spec's section 3.1.1. `aura.py`'s hooks gather each player's turn - the energy they had (what the turn began with plus every gain since), every card that was in their hand with the cost, damage and Block it showed, what they played, the damage aimed at them and their Block when they ended (a play after ending takes the end back). Once everyone has ended, each player who is not the agent is scored: `analyzer.py` works out the context, the 0-100 scores, the evidence and its weight for Aggression, Scaling and Teamwork, and updates the profile (value, deviation, confidence; memory size 8, which the spec leaves open). Each scored turn's input goes to the combat log first, as `analyzer_input` - the spec's History: `energy`, `hand`, `used`, `opp`, `incoming`, `block`, every card with its id, cost, dmg, block and groups - and the result as `profile_update` (evidence, weight, context numbers, profile). `python -m Plugins.history_export <log>` (from `Server/`, new `Plugins/history_export.py`) writes the input out per teammate as JSON in the MockUpRB prototype's list format, `[E_total, Used, Opp, D, B]`; on 332 turns of real fights the prototype's own pipeline gives the same evidence as the engine. The agent's state carries `profiles`: `{unit_id: {A, S, T, cA, cS, cT}}`. A card's damage is per hit times hits. The spec clips only Aggression's scores to 0-100; Scaling's and Teamwork's are clipped too, since a cost that changed mid-turn could push them past 100. Profiles last one fight. Memory size β = 20, as in the teammate's `CharacteristicAnalyzer` package (was 8; the package now sits at `2nd_model/CharacteristicAnalyzer`, moved out of `CharacteristicAnalyzer_v1`, whose `REALTEST.py` was deleted). `python -m Plugins.ca_feed <log>` (from `Server/`) feeds a log's turns to that package and prints its profiles beside ours; at the same β they match to the last digit. `python -m Plugins.ca_plot <log>` (new) draws CA's profile as charts in `<log>_ca.html` (traits and confidence per player by turn; plain HTML and SVG, nothing to install). Tests: `tests/test_analyzer.py` (hand-worked turns, then fights through the session, then 15 random fights, then the same turns through the package when it is present). |
| A log as turns: `Plugins/turn_export.py` (new), `Plugins/history_export.py` (`load`, `rebuild`), your `combat_log.py` (`replay(..., plugin=, log=)`, new `MemoryLog`) | The log keeps every move as its own line. `python -m Plugins.turn_export <log>` (from `Server/`) groups them into turns - per turn the state it began with and each player's moves in order, nothing dropped - prints the fight a turn at a time and writes `<log>_turns.json`. Each player's turn carries the aura plugin's `analyzer_input` and `profile_update`. A log written without the plugin gets them rebuilt: `replay` now optionally runs with a plugin and writes to a `MemoryLog`, so the fight is played again with aura on; the rebuilt lines are marked `rebuilt` and stop at the first move that does not replay the same way. `history_export`, `ca_feed` and `ca_plot` load logs the same way (`ca_feed` shows nothing "as logged" for rebuilt turns). Rebuilding today's log gives the logged `analyzer_input` lines exactly; its profiles differ only in confidence, since it was logged at β 8. Tests: `tests/test_turn_export.py`. |
| Enemy engine, for the new enemies | Found while porting the rest of Overgrowth, each as the game's code has it. **The enemy phase walks a snapshot** of the lineup (`Enemies.ToList()`): a summoned enemy used to act in the phase it arrived in, against `summon`'s own docstring. **A stunned enemy shows a Stunned intent**, and the move it had lined up is put off to the next turn instead of lost (`CreatureCmd.Stun` hands back to it; `ScriptedEnemy.skipped_move`) - Whistle included. **Minions all go once no enemy of its own right is left** (`CreatureCmd.Kill`), not only when their leader dies. **An Illusion** (Eye With Teeth) shows a Revive intent while down and loses its debuffs at death, keeping its buffs (`IllusionPower`). New hooks: `StatusEffect.modify_hp_lost` (HP lost after Block, `Unit.take_damage` / `lose_hp`: Slippery), `StatusEffect.PLAY_CAP` (Ringing; `Combat._play_cap` reads it), and `GameEvent.ENEMY_TURN_END` (Territorial). |
| A dead dealer deals nothing, a dead target takes nothing: `Resolver._resolve_instant_damage`, `Combat._Hits`, `sword_boomerang.py`, `rip_and_tear.py`, `volley.py` | As the game's `CreatureCmd.Damage` and `AttackCommand`. A multi-hit attack used to keep landing after Thorns or Flame Barrier killed its attacker, and its later hits were spent on an enemy already dead. Now the attacker is checked once per hit (`_Hits` groups one hit's damage: the `hit` number enemy attacks carry, or else a run until a target repeats). A hit still lands on every player after the first one's Thorns kills the attacker; the next hit does not come; the rest of the move (Double Smash's Weak) still happens. Sword Boomerang, Rip and Tear and Volley now pick each hit's target from the enemies alive at that hit, as the game does (`get_effects` yields them one at a time). Card matrix and determinism digest unchanged. Tests: the last section of `tests/test_underdocks.py`. |
| The other cards matched to the game: `Combat` (`_extra_plays` Tag Team, `_intercept`, `card_cost` cost caps, `_emit` per-hit `attacked_by` and `team_cards_played`), `Resolver` (`InstantCapCost`, Statuses/Curses not upgraded), `Context.solo`, `Card.GENERATED_IN_COMBAT` / `MULTIPLAYER_ONLY` / `cost_cap`, `CardRef.cost_cap` / `turn_cost_cap`, `CardRarity.EVENT`, `card_registry` (`generatable_card_ids(solo=)`, `transform_card_ids`, `can_upgrade`), `InstantCapCost` (new), `Effects/StatusEffects/enlightenment.py` (deleted), ~45 card and status files | `tests/game_diff.py` now reads every pool (206 exact, 5 different on purpose, 0 wrong), and each colorless, event, status and curse card's play code was read beside ours. Values: 22 colorless rarities, Beacon of Hope 1, Whistle 3, Rend 2 / 15 + 5, Knockdown+ 14 and x3, Maul +1, Relax 15 / 2 cards / 2 Energy, Panache and The Bomb carry their damage, Giant Rock 16, Toxic playable. Behaviour: random cards follow the game's FilterForCombat (no Event cards, no Feed / Hand of Greed / Hidden Gem, no co-op card solo); Transform uses the game's pool; stacked powers do more (Calamity, Mayhem, Hello World, Entropy, Stratagem, Automation) and instanced ones count per copy (Panache, The Bomb, Rolling Boulder, Knockdown); next-turn Energy/draw are amounts; Panic Button stops card Block only; Gang Up per hit; Gold Axe counts the team; Intercept covers the chosen player; Tag Team on AoE, not random; Enlightenment caps the copies in hand; Anointed, Catastrophe, Hidden Gem, Jackpot, Jack of All Trades, Discovery/Splash, Nostalgia, Apotheosis, Bolas as the game. Old tests that expected the reference's rules were changed: `test_cost.py` (Enlightenment), `test_fork.py` (Intercept, Maul, Bolas, Apotheosis), `test_random.py` (Jackpot), `test_oneoffs.py` (Rend), `test_counters2.py` (Gold Axe, Gang Up), `test_enemies.py` (Intercept). Card matrix and digest unchanged. Details: COMBAT_INTERFACE.md, "The other cards". Tests: `tests/test_colorless_game.py`. |
| The last card differences: `Combat` (`_capped`, `cards_started`, auto-play capped, `BEFORE_HAND_DRAW` emitted, Block's `beacons`, `TagTeam.spend`; `_free_bucket` gone), `Resolver._resolve_status` (skip_next_tick only on a new debuff), `Ally` (`free_this_turn` / `free_this_combat` removed), `GameEvent.BEFORE_HAND_DRAW` (new), `_card_ref.free_copy` (new), `tag_team.py`, `beacon_of_hope.py`, `hello_world.py`, `return_to_hand.py`, `discovery.py`, `distraction.py`, `infernal_blade.py`, `mad_science.py`, `metamorphosis.py` | Each from the game's code. A free card is that copy at cost 0 (this turn or until played; Metamorphosis for the combat, every play), not a free name - so Tangled still adds 1 and a free X card still spends all, as in the game. Normality, Sloth and Ringing count plays started and stop auto-played cards too. Two players' Tag Teams are two marks; two Beacons of Hope answer each other once. Hello World and a returning Bolas arrive before the hand is drawn. Only a new Vulnerable/Weak/Frail on a player skips its first count-down. Tests that read the old free lists were changed: `test_random.py` (and a free X card now spends all), `test_cost.py`, `test_fork.py`, `test_legal_actions.py` (also sets `cards_started`). Card matrix and digest unchanged. Tests: `tests/test_colorless_game.py`. |
| Enemy engine, for Underdocks | Found while porting Underdocks, each as the game's code has it. **Deaths were never resolved in play.** `Combat._resolve_deaths` (on_death, Minions leaving with their leader, an Illusion scheduling its return) existed but nothing called it - only the tests did - so in a real fight Phrog Parasite's Wrigglers never came and a Minion outlived its leader. `_check_combat_end` now runs it first, and the end of the players' turn and of the enemies' turn now go through `_check_combat_end` too. **An enemy summoned on the enemies' turn** picks its move once, with everyone, after that turn (`AfterCreatureAdded` rolls only on the players' side); it used to pick twice. New: `GameEvent.ENEMY_DIED` (Ravenous), a `hit` index on ATTACKED (Suck), `ScriptedEnemy.escape()` (Fat Gremlin flees: gone, not killed, nothing reacts), an enemy that is still alive after its on_death keeps its death to come (Waterfall Giant), and `StatusEffect.forbids_play` with a `skills_played` counter (Smoggy: one Skill a turn, auto-plays included). Fixed: **Vigor** adds to every hit of the attack, every target, and is spent when the attack is over - it was spent by the first hit, so Twin Strike got it once; **Thorns and Flame Barrier** hit back unpowered, not as attacks; **an enemy's unpowered Block** (Plating, Skittish) is not scaled for the party, only a card's or a move's; **Plating** works on enemies (scaled x (2 per extra player + 1), one less per player each turn, Block at the end of the enemies' turn) and **Ritual** waits a turn; **Strength and Dexterity below zero** are debuffs, which Artifact stops, and the tick no longer culls them; **Intangible on an enemy** counts down at the end of the enemies' turn - it never did; **Beckon** can be played for 1, as the game's has no Unplayable. In your tests: `test_scaling.py` stops a fight once it is over (Fat Gremlin flees) and compares the Matriarch's Plating only while she sleeps. |
| A moved card goes to the end of its pile | `_resolve_instant_move_card` put a card moved into the hand, the discard or the exhaust pile at index 0 - the left of the hand, the oldest of a pile. The game's `CardPileCmd.Add` puts it at the bottom (index -1) unless told otherwise: the right end of the hand, the newest of the pile, where a played card already went here. Wish, Secret Weapon, Headbutt's and Neow's Fury's picks and the rest now land there. The draw pile was already right (index 0 is its bottom here). |
| Summons resolve | `InstantSummon` and `Combat._resolve_summon` existed, but `Combat._resolve` never sent the effect there, so a summon would have raised `NotImplementedError` in the resolver - which is what `tests/audit_structure.py` was reporting. `_resolve` now routes it, the audit looks for a branch in Combat as well as Resolver, and `tests/test_enemies.py` summons for real. No summoning enemy is ported yet. |
| Enemy HP rolled as it enters, unlike the others | The game rolls a monster's HP when the fight creates it, among the values no other enemy on its side has (`SetUniqueMonsterHpValue`, Niche stream), then scales it for co-op. The session and summons now build enemies with no rng (`Unit.hp_range`, `hp_unrolled`), and `Combat._roll_hp` rolls them one by one in `start()` and in `summon()`. Alone, three Nibbits are always three different numbers; in co-op the others already carry their scaled HP, so - as in the game - two can match. Enemies built with their own rng, as the tests build them, keep what they rolled. |
| Secret Technique, Secret Weapon | The player picks the Skill or Attack from the draw pile, as the game's `CardSelectCmd.FromCombatPile` - they picked at random. Both are Rare in the game (Uncommon here), and their upgrade removes Exhaust (they had no upgrade). Text changed to match. |
| Neow's Fury | Took up to 2 cards whatever the hand held, the second overflowing to the discard. The game takes up to min(2, room in the hand); each question now offers nothing once the hand is full. It also never offers itself, like Headbutt. |
| `tests/test_review.py` pins one Dummy | It killed `e1` and expected a victory, so it failed whenever `config.ENEMY_TYPE_IDS` held two enemies (it does locally: two Nibbits). It now sets the lineup it was written for. |
| `MAX_ALLIES = 4`, checked in the constructor | Co-op is one to four players. Nothing enforced it, and the scaling multiplies happily past it. `session.py` reads the cap off the factory and refuses a bad `REQUIRED_PLAYERS` at startup rather than when the last player joins. No enemy cap: the real game bounds summoning per encounter (a Two-Tailed Rat group gets three Call for Backups in total), so that belongs to the summoner when one is ported. |

**Six ordering fixes**, each found by a test that failed:

1. **Cost paid and card popped from hand *before* resolving**, discard appended
   *after*. A card that reads its own discard pile (Stack) must not count
   itself, but a failure mid-resolution must not leave it replayable either.
2. **`TURN_END` fires after `_tick_statuses`, before `_discard_hands`.** Doubt
   and Shame apply statuses at end of turn; ticking afterwards culled them the
   instant they landed. The cards still have to be in hand, hence before the
   discard.
3. **Defensive "this turn" statuses survive the end-of-turn tick** and clear on
   the next `TURN_START` — ally statuses tick before the enemy phase runs, so
   anything decaying there would be gone before a single attack landed. Hit
   Flame Barrier, Intangible, Colossus and Toric Toughness.
4. **Dead allies are excluded** from playing cards, holding hands, and
   receiving statuses. A dead ally could previously play a card and win the
   fight.
5. **A held card reacts to its holder's `TURN_END` only.** The event is
   emitted once per player, and `_emit` walked every hand for every emission,
   so a Burn dealt 2 × the player count. Invisible in every solo test; the
   Wriggler's Infection in a two-player fight showed 6 where 3 was due.
6. **Vulnerable multiplies attacks only.** The resolver ran every incoming
   modifier on every damage, so a Burn on a Vulnerable player dealt 3. The
   reference gates its defender multiplier on `source_is_attack`; a status now
   declares `ATTACKS_ONLY` (Vulnerable, Exposed, Colossus Guard do; Intangible,
   Tank and Protected still cap or scale everything). Found by Constrict.

## Resolution

`Resolution/resolver.py` handles 17 instant effects plus statuses. Three fixes
worth knowing about:

- `int(amount)`, not `int(round(amount))`. StS floors: 5 damage × 1.5 Vulnerable
  is 7, not 8.
- `target.apply_status(copy.copy(effect))`, not the effect itself. Applying one
  status object to three enemies otherwise aliased it — ticking one enemy's
  Vulnerable ticked all three.
- **A full hand sends cards to the discard pile.** `_resolve_instant_add_card`
  and `_resolve_instant_move_card` used to put any number of cards into a hand;
  only drawing stopped at `Ally.HAND_LIMIT` (10). The game checks each card as
  it arrives (`CardPileCmd.Add`, `isFullHandAdd`) and sends it to the discard
  pile once the hand holds 10 - Jackpot, Discovery, Wish, Anointed, a Bolas
  coming back. Both now do that, card by card, and their result lists the
  overflow as `to_discard`. `tests/fuzz.py` and the card matrix now fail if
  any hand goes over 10.

## Content

| | |
|---|---|
| `Cards/` | 219 registered cards |
| `Cards/_card_ref.py` | `CardRef` — the per-copy identity piles hold |
| `Cards/_upgrades.py` | what an upgrade changes, per card, in one table |
| `Effects/StatusEffects/` | 74 statuses |
| `Effects/InstantEffects/` | 18 instant effects |
| `Registry/card_registry.py` | `create_card(card_id)`, `known_card_ids()` |
| `Registry/coverage.py` | run it directly: which of the 230 planned cards are done, and what is blocking the rest |
| `Units/Enemies/_scripted.py` | `Move` + `ScriptedEnemy` + `Branch`: fixed cycles and the game's random move choice; `attack()` / `buff()` / `guard()` / `debuff()` / `hand_out()`, all aimed at every player; `HP_RANGE`, `NAME`, `on_combat_start` |
| `Units/Enemies/the_insatiable.py`, `aeonglass.py` | two bosses |
| `Units/Enemies/leaf_slime.py`, `twig_slime.py`, `wriggler.py` | five Act 1 enemies that hand out Slimed and Infection |
| `Units/Enemies/nibbit.py`, `snapping_jaxfruit.py`, `fuzzy_wurm_crawler.py`, `raiders.py` | eight more Act 1 enemies, damage / Strength / Block / debuff cycles |
| `Units/Enemies/flyconid.py`, `slithering_strangler.py`, `vine_shambler.py`, `shrinker_beetle.py`, `mawler.py`, `cubex_construct.py` | the Act 1 debuffers (Shrink, Constrict, Tangled, Artifact) |
| `Units/Enemies/inklet.py`, `fogmog.py`, `phrog_parasite.py`, `bygone_effigy.py`, `byrdonis.py`, `the_kin.py`, `vantom.py`, `ceremonial_beast.py` | the rest of Overgrowth (new): Inklet, Fogmog and its Eye With Teeth, the elites Phrog Parasite, Bygone Effigy and Byrdonis, the bosses The Kin (Priest and Followers), Vantom and Ceremonial Beast - with the statuses they need, `Slippery`, `Slow`, `Territorial`, `Plow`, `Ringing` (new). All 22 Overgrowth encounters can be built. Tests: `tests/test_overgrowth.py`. |
| `Units/Enemies/seapunk.py`, `sewer_clam.py`, `haunted_ship.py`, `sludge_spinner.py`, `punch_construct.py`, `cultists.py`, `toadpole.py`, `corpse_slug.py`, `fossil_stalker.py`, `gremlins.py`, `living_fog.py`, `two_tailed_rat.py`, `terror_eel.py`, `skulking_colony.py`, `phantasmal_gardener.py`, `lagavulin_matriarch.py`, `soul_fysh.py`, `waterfall_giant.py` | Underdocks, the other Act 1 (new): Seapunk, Sewer Clam, Haunted Ship, Sludge Spinner, Punch Construct, the Calcified and Damp Cultists, Toadpole, Corpse Slug, Fossil Stalker, Gremlin Merc with its Sneaky and Fat Gremlins, Living Fog with its Gas Bombs, Two-Tailed Rat; the elites Terror Eel, Skulking Colony and Phantasmal Gardener; the bosses Lagavulin Matriarch, Soul Fysh and Waterfall Giant - with the statuses they need, `Ravenous`, `Suck`, `Shriek`, `HardenedShell`, `Skittish`, `Surprise`, `Smoggy`, `Asleep`, `SteamEruption` (new). All 20 Underdocks encounters can be built. Tests: `tests/test_underdocks.py`. |
| all 53 enemies | ported from the installed game's code: patterns, numbers, targets. See COMBAT_INTERFACE.md for the table. |

**Card values come from the game itself** (v0.107.1, decompiled with
ILSpy into `D:\sts2_source` - outside this repo, since it is Mega Crit's code).
`python tests/game_diff.py` compares every card with the installed game, pool
by pool (Ironclad, Colorless, Event, Status, Curse, Token), on cost, every
number, upgrade, keyword, type, rarity and target, and lists any difference;
rerun it after a game patch. 206 match, 5 differ on purpose (listed by the
script), none differ otherwise. `coverage.py` records the
13 cards that **cannot** exist here (other characters' tokens, quest items),
the 4 **removed** from the game (Blaze, Midnight, Outrage, Abundance), and the 2
deliberately left out (Alchemize needs potions; Mad Science (Improvement)
edits the deck after the fight), each with the reason named.
Nothing is unaccounted for: every card on the list is ported, excluded, or
carries a stated blocker.

## Player choice

Fifteen cards and two powers stop and ask the player: `choice_required` goes privately to
whoever must answer, `choose` carries `option_index` back. `Combat.ask_players`
gates it — **False by default, which answers at random**, so headless and
training runs are unaffected. `Session` sets it True when players connect. The
details, and the traps, are in COMBAT_INTERFACE.md.

## Questions — all three closed

1. ~~`playable` default~~ — you kept `True`. Closed.
2. ~~Does the registry belong in `Registry/`?~~ — it lives there now. Closed.
3. ~~Card identity~~ — closed without touching the wire. Piles hold `CardRef`,
   a `str` subclass, so it is still the id everywhere it was, and an object
   where per-copy state was needed. That unblocked the last 8 cards and all
   upgrades. **Two additive wire fields**, `hand_upgraded` and `hand_replay`,
   alongside `hand`; a client ignoring both behaves as before.
   See COMBAT_INTERFACE.md.

## Verified

```bash
python tests/run_all.py
```

Twenty-five scripts, about two and a half minutes, one verdict: thirteen suites (the card
slice against reference values, one per ported batch, a regression pass, a
bug hunt, the choice round trip through Session, every enemy at 1–4 players),
a structural audit of every card, status, effect and upgrade entry, every card
played plain, upgraded and with Replay, the card matrix (below) over the whole
registry, a determinism check (same seed, byte-identical fight), and a fuzzer
that plays 300 whole fights with random decks and mixed enemy lineups from the
entire registry. Every script exits non-zero
on failure, so the runner needs nothing from their output; `run_all.py fork
cost` runs only the suites matching those words.

`tests/card_matrix.py <card>` plays one card through every situation and
prints a diff per row: 1 or 2 allies × 1 or 2 enemies × plain or upgraded,
aimed at each legal target; then Strength, Weak, Dexterity, Frail, enemy
Vulnerable, Block on either side, a lethal enemy, a dying player, an
all-Attack hand, a second copy, a full hand, empty piles and Replay; then the
illegal moves (no target, dead target, wrong pool, self as "another player",
0 energy, bad index, dead player, finished fight, and for a card that asks a
question: playing or ending the turn before answering, and a bad option),
each of which must be refused and change nothing. Choice cards get one row
per option. Each row shows the play, a Strike played after it, and the end
of turn. `--save` approves the table into `tests/golden/<card>.json`; from
then on any change to that card's behaviour fails the run. `all` runs every
card and prints only failures. The first run found six co-op cards
(Believe In You, Blaze, Coordinate, Demonic Shield, Lift, Mimic) refusing a
self target from inside `get_effects` — after the energy was spent and the
card had left the hand. The check now lives in `Combat._resolve_target`,
before either.

`tests/live/` holds the socket tests. They need a server up:
`python Server/main.py` then `tests/live/live2p.py`; or
`tests/live/choice_server.py` (the real server with an all-Wish deck) then
`tests/live/live_choice.py`. `tests/live/boss_server.py [aeonglass]` is the
real server configured for a boss.

## Not done

- **14 of the 230 planned cards**: 13 that cannot exist here, and Alchemize,
  which needs potions. Every other card on the list is in. The sheet's Effect
  tab also names a ninth Mad Science variant, *Improvement* ("at the end of
  combat, Upgrade a random card") - skipped on purpose, recorded in
  `coverage.py`. The Effect tab's other 53 unported entries are all enemy
  mechanics waiting on their enemies; the Thorns it lists is our `caltrops`.
- **Acts 2 and 3 are not ported.** Both Act 1s are complete (Overgrowth's 22
  encounters, Underdocks' 20); Acts 2 and 3 have only their two bosses and
  Glory's Construct Menagerie. Encounters are not modelled as such:
  `config.ENEMY_TYPE_IDS` names the lineup (The Kin is `("kinfollower",
  "kinfollower", "kinpriest")`, Inklets three `inklet`s, Living Fog alone).
- **No gold.** The Gremlin Merc steals gold in the game; here it only attacks.
- **Enemy move Block in co-op** is flat x2 for two players, on purpose; the
  game's is players x the act factor (2.2 in Act 1). HP already uses the
  game's.
- **Every card is checked against the game's code** (`tests/game_diff.py`
  for the numbers, `tests/test_ironclad_game.py` and
  `tests/test_colorless_game.py` for behaviour). No known difference is left
  in an Act 1 card. The Act 2 cards (Knowledge Demon's, Frantic Escape,
  Toxic's source) were not gone through.
- **No rejoining.** A player who drops leaves the fight for good - their
  questions are answered at random and a new connection is refused while a
  combat runs. `eventlet` is deprecated upstream and should be replaced.
- **Combat runs once per Session.** `Combat.start()` rebuilds the draw pile but
  does not clear `hand` / `discard_pile` / `exhaust_pile`, so reusing an `Ally`
  for a second fight would carry them over. Harmless today — `_start_combat`
  refuses a second combat — but it is yours to decide before runs exist.
- `python-socketio`'s *client* also needs `pip install requests websocket-client`;
  the server side only needs `eventlet` and `python-socketio`.
