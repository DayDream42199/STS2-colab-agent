# Handoff — what changed

Your combat module landed and works. This round is **content and hooks**: the
card pool went from 3 cards to 223, and `combat.py` grew an event system to
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
| `_enemy_target` | A scripted enemy names its victim when it chooses its intent; this honours that if they are still alive. |

**Four ordering fixes**, each found by a test that failed:

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

## Resolution

`Resolution/resolver.py` handles 17 instant effects plus statuses. Two fixes
worth knowing about:

- `int(amount)`, not `int(round(amount))`. StS floors: 5 damage × 1.5 Vulnerable
  is 7, not 8.
- `target.apply_status(copy.copy(effect))`, not the effect itself. Applying one
  status object to three enemies otherwise aliased it — ticking one enemy's
  Vulnerable ticked all three.

## Content

| | |
|---|---|
| `Cards/` | 223 registered cards |
| `Cards/_card_ref.py` | `CardRef` — the per-copy identity piles hold |
| `Cards/_upgrades.py` | what an upgrade changes, per card, in one table |
| `Effects/StatusEffects/` | 64 statuses |
| `Effects/InstantEffects/` | 17 instant effects |
| `Registry/card_registry.py` | `create_card(card_id)`, `known_card_ids()` |
| `Registry/coverage.py` | run it directly: which of the 230 planned cards are done, and what is blocking the rest |
| `Units/Enemies/_scripted.py` | `Move` + `ScriptedEnemy`: the shape every real enemy uses |
| `Units/Enemies/the_insatiable.py`, `aeonglass.py` | the first two real enemies, both bosses; 2 of 98 in the reference |

Values come from a reference engine, not from memory. `coverage.py` records the
13 cards that **cannot** exist here (other characters' tokens, quest items) and
the 1 blocked on a system that does not exist yet, each with the reason named.
Nothing is unaccounted for: every card on the list is ported, excluded, or
carries a stated blocker.

## Player choice

Twelve cards stop and ask the player: `choice_required` goes privately to
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

Eighteen scripts, about twenty seconds, one verdict: twelve suites (the card
slice against reference values, one per ported batch, a regression pass, a
bug hunt, the choice round trip through Session), a structural audit of every
card, status, effect and upgrade entry, every card played plain, upgraded and
with Replay, the card matrix (below) over the whole registry, a determinism
check (same seed, byte-identical fight), and a fuzzer that plays 300 whole
fights with random decks from the entire registry. Every script exits non-zero
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
  which needs potions. Every other card on the list is in.
- **True Grit+ still picks at random.** Its base printing genuinely says "at
  random", so only the upgraded half should ask, and the card does not yet
  split the two. The other twelve choice cards now ask the player.
- **Combat runs once per Session.** `Combat.start()` rebuilds the draw pile but
  does not clear `hand` / `discard_pile` / `exhaust_pile`, so reusing an `Ally`
  for a second fight would carry them over. Harmless today — `_start_combat`
  refuses a second combat — but it is yours to decide before runs exist.
- `python-socketio`'s *client* also needs `pip install requests websocket-client`;
  the server side only needs `eventlet` and `python-socketio`.
