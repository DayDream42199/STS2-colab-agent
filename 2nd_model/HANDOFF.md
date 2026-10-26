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
| `_ally_dict`, `hand_costs`, `hand_damages` in `to_dict()` | Each ally carries `hand_cost`: what every card in hand costs to play now (Stomp's discount, Tangled, Corruption, free grants), `"X"`, or `None` if unplayable - the same number `play_card` charges. And `hand_damage`: one hit of each Attack after the holder's Strength, Weak and Vigor, before the target (`None` for non-Attacks), from the new `Card.base_damage(ally)`. The terminal client prints both, e.g. `[1] strike  dmg 8`, and marks upgrades with `+`. They are the third and fourth parallel arrays beside `hand_upgraded` / `hand_replay`: COMBAT_INTERFACE.md said a third is the point to collapse them into one `hand_cards` array, which is your call since it changes the wire. |
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
| One random stream per purpose: `Context/rng_streams.py` (new) | One shared `rng` meant a reshuffle changed which move an enemy rolled next turn. Now, as the game's `RunRngSet`: `shuffle`, `card_generation`, `card_selection`, `targets`, `monster_ai`, `niche` (monster HP), plus `answers` (a question answered at random, headless or after a player left), each seeded from the seed and its name, the same in every process. `Combat(rng=...)` takes the streams, or one `random.Random` to seed them (all the tests), or nothing, in which case it draws a seed and keeps it in `combat.seed`. `combat.rng` and `context.rng` still exist, as the `niche` stream; `context.rngs` is the set. 48 card, status and enemy files now draw from the stream the game uses for that card (checked one by one against the decompiled code); every draw and every card put into the draw pile at random uses `shuffle`. Enemies get `monster_ai` for their moves from the session and from summons. No unseeded fallback is left: a unit with no rng takes its base HP, or the top of `HP_RANGE` (the game's HP before its roll). Two tests had passed by seed luck and were fixed: `test_intercept.py`'s "auto-played attack takes the weakest enemy" (it is random, as the row above says) and `test_combat_log.py`'s tampered replay. Tests: `tests/test_rng_streams.py`. |
| Headbutt cannot pick itself | Found by the new streams. In the game the played card sits in the play pile while it resolves, so Headbutt's "put a card from your discard on top" never offers that Headbutt. Here it was already in the discard when the question was read. `Context.played` is the copy being played; Headbutt leaves it out. The card matrix has 67 fewer rows, all Headbutt's. |
| Unexpected errors: `session._guarded`, `Session._crashed`, `main.py` | An exception that is not a refusal (a bug in a card) used to propagate out of `handle` and stop the server. Now the traceback goes to the console and to the log (an `error` line), the sender gets an error message, everyone gets the state as it now stands (part of the action may have happened), and the fight goes on. `main.py`'s loop has a last net around each event too. Refusals are unchanged. |
| Unmovable as the game's `UnmovablePower` | It doubled "the first Block of the turn". The game doubles Block from a card or a move while this turn's gains from *other* card plays are fewer than its amount: every gain of one play is doubled (Second Wind 5 + 5 = 20 - `test_cost.py`'s 15 is now 20), it stacks, a power's own Block is neither doubled nor counted, and it belongs to the card's owner - your card's Block to a teammate is doubled, a teammate's card giving you Block is not. So each card play now has a number (`Context.play_id`, stamped on its `InstantBlock`s and on its questions' answers - each Replay play its own, as each is its own `CardPlay`), each unit keeps `card_blocks` (this turn's card Block gains by play, only those above 0), and Unmovable uses a new hook, `StatusEffect.modify_card_block`, asked of the card owner's statuses. `BLOCK_CARD_ONLY` is gone, and `hand_blocks` no longer raises and restores the turn counter between gains. Checks in `tests/test_ironclad_game.py`. |
| The plugin exists: `Server/Plugins/aura.py`, `card_groups.py` (new, in your empty `Plugins/` folder) | `config.PLUGIN = "Plugins.aura"` now finds a plugin, so the server runs with it. It changes nothing for players. A client that identifies as the agent gets, per player, a descriptor for each card in hand (`hand_cards`), in each pile (added to the pile entries) and in the deck (`deck_cards`), and for each option of a question (`option_cards`): type, cost, target, keywords, damage, hits, Block, the statuses it applies by scope (self / target / all allies / all enemies), and its groups. The groups: **now** every non-Power, **scale** every Power, **team** if it damages or debuffs an enemy, buffs every player, or touches a teammate, **self** if it gives you Block, buffs you, draws you cards, gives you energy, heals you, changes your own cards (makes, moves, exhausts, upgrades) or plays other cards. Every Attack, Skill and Power is team or self; only Statuses and Curses can be neither. They are read by playing each card once in a sandbox fight and looking at what changed; a status counts by `STATUS_ROLES` (what it does to whoever holds it, so Juggernaut is team and Demon Form self). `python -m Plugins.card_groups` from `Server/` prints every card's groups. Tests: `tests/test_card_groups.py`. |
| The Characteristic Analyzer: `Server/Plugins/analyzer.py` (new), in `aura.py` | The spec's section 3.1.1. `aura.py`'s hooks gather each player's turn - the energy they had (what the turn began with plus every gain since), every card that was in their hand with the cost, damage and Block it showed, what they played, the damage aimed at them and their Block when they ended (a play after ending takes the end back). Once everyone has ended, each player who is not the agent is scored: `analyzer.py` works out the context, the 0-100 scores, the evidence and its weight for Aggression, Scaling and Teamwork, and updates the profile (value, deviation, confidence; memory size 8, which the spec leaves open). Each scored turn's input goes to the combat log first, as `analyzer_input` - the spec's History: `energy`, `hand`, `used`, `opp`, `incoming`, `block`, every card with its id, cost, dmg, block and groups - and the result as `profile_update` (evidence, weight, context numbers, profile). `python -m Plugins.history_export <log>` (from `Server/`, new `Plugins/history_export.py`) writes the input out per teammate as JSON in the MockUpRB prototype's list format, `[E_total, Used, Opp, D, B]`; on 332 turns of real fights the prototype's own pipeline gives the same evidence as the engine. The agent's state carries `profiles`: `{unit_id: {A, S, T, cA, cS, cT}}`. A card's damage is per hit times hits. The spec clips only Aggression's scores to 0-100; Scaling's and Teamwork's are clipped too, since a cost that changed mid-turn could push them past 100. Profiles last one fight. Tests: `tests/test_analyzer.py` (hand-worked turns, then fights through the session, then 15 random fights). |
| Enemy engine, for the new enemies | Found while porting the rest of Overgrowth, each as the game's code has it. **The enemy phase walks a snapshot** of the lineup (`Enemies.ToList()`): a summoned enemy used to act in the phase it arrived in, against `summon`'s own docstring. **A stunned enemy shows a Stunned intent**, and the move it had lined up is put off to the next turn instead of lost (`CreatureCmd.Stun` hands back to it; `ScriptedEnemy.skipped_move`) - Whistle included. **Minions all go once no enemy of its own right is left** (`CreatureCmd.Kill`), not only when their leader dies. **An Illusion** (Eye With Teeth) shows a Revive intent while down and loses its debuffs at death, keeping its buffs (`IllusionPower`). New hooks: `StatusEffect.modify_hp_lost` (HP lost after Block, `Unit.take_damage` / `lose_hp`: Slippery), `StatusEffect.PLAY_CAP` (Ringing; `Combat._play_cap` reads it), and `GameEvent.ENEMY_TURN_END` (Territorial). |
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
| all 32 enemies | ported from the installed game's code: patterns, numbers, targets. See COMBAT_INTERFACE.md for the table. |

**Ironclad values come from the game itself** (v0.107.1, decompiled with
ILSpy into `D:\sts2_source` - outside this repo, since it is Mega Crit's code).
`python tests/game_diff.py` compares all 87 Ironclad cards with the installed
game on cost, every number, upgrade, keyword, type, rarity and target, and
lists any difference; rerun it after a game patch. All 87 match. Everything
else still comes from the beta-era reference engine. `coverage.py` records the
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
- **Underdocks is not ported.** Overgrowth is complete (all 22 encounters);
  Underdocks, the other Act 1, has 1 of its 20. Acts 2 and 3 have only their
  two bosses. Encounters are not modelled as such: `config.ENEMY_TYPE_IDS`
  names the lineup (The Kin is `("kinfollower", "kinfollower", "kinpriest")`,
  Inklets three `inklet`s).
- **Only the Ironclad cards are checked against the game's code**
  (`tests/game_diff.py`). The colorless and other cards still carry the
  beta-era reference's values; Secret Technique, Secret Weapon and Neow's Fury
  were fixed when found, the rest are unchecked.
- **No rejoining.** A player who drops leaves the fight for good - their
  questions are answered at random and a new connection is refused while a
  combat runs. `eventlet` is deprecated upstream and should be replaced.
- **Combat runs once per Session.** `Combat.start()` rebuilds the draw pile but
  does not clear `hand` / `discard_pile` / `exhaust_pile`, so reusing an `Ally`
  for a second fight would carry them over. Harmless today — `_start_combat`
  refuses a second combat — but it is yours to decide before runs exist.
- `python-socketio`'s *client* also needs `pip install requests websocket-client`;
  the server side only needs `eventlet` and `python-socketio`.
