# Slay the Spire 2 (co-op) — Combat Replica

A headless, deterministic combat simulator for 1–4 co-op Ironclads. No
graphics: the point is speed and correctness so you can train against it or
play it in a terminal, not look at it.

Numbers and mechanics are cross-checked against `slaythespire.wiki.gg`, with
the raw data modules (`Module:Cards/StS2_data/Ironclad`, `Module:Powers`) as
the trusted source over the human-written summary pages. Where something is
approximated or unverified, it is flagged in code comments and in
[Scope](#scope--what-is-deliberately-not-here).

**Status:** all three acts ported, <!--test_suites-->22<!--/--> test suites, reproducible from a
seed, ~7.5k env steps/sec single-threaded.

---

## Quick start

```bash
pip install numpy
python testing/play.py         # play it yourself
python testing/demo.py         # scripted showcase
python testing/bench.py        # difficulty measurement
python game_engine/tests/run_all.py   # the test suite (~9s)
```

Run everything from the repo root — the entry points put the root on
`sys.path` themselves, so `python testing/play.py` works without installing
anything.

## Layout

```
game_engine/   the rules and content, plus the RL environment
  tests/       the 22 suites, beside the code they verify
testing/       ways to drive it: play, benchmark, demo, sandbox, trainer
  tools/       diagnostics kept because each produced a figure quoted here
config.json    what play.py loads: restrictions, party, encounter
```

### `game_engine/` — the engine modules import only each other

| file | what it holds |
|---|---|
| `statuses.py` | Status effects with real stack-type × turn-behaviour metadata, plus the shared status arithmetic (`net_strength`, damage/block multipliers) |
| `entities.py` | `Entity` → `Player`/`Enemy`: HP, block, damage resolution, the event-hook registry, and the content RNG |
| `cards/` | `Card` model with upgrade/X-cost/dynamic-cost support, and the complete <!--ironclad_cards-->91<!--/-->-card Ironclad list — split into `model` / `effects` / `tokens` / `pools` |
| `enemies/` | Movesets with telegraphed intents, and real multiplayer HP/block scaling — one module per region |
| `relics.py` | `Relic` model + <!--relics-->83<!--/--> wiki-sourced relics |
| `potions.py` | `Potion` model + all <!--potions-->52<!--/--> Ironclad-relevant potions |
| `combat.py` | `CombatEngine`: runs 1–4 players vs N enemies; owns the play-legality rules |
| `env.py` | `CombatEnv` / `GymnasiumEnv`: the machine-player interface |

`cards/` is a package, imported exactly as the old flat module was —
`import game_engine.cards as C` and `from game_engine.cards import Card` both
still work, and no name it used to export was lost.

| module | holds |
|---|---|
| `model.py` | `CardType`, `TargetMode`, the rarity tables, the `Card` dataclass |
| `effects/` | every `fx_*` — what a card actually does, split by source |
| `tokens.py` | Status, curse and token card factories (Wound, Burn, Slimed…) |
| `pools.py` | the card tables and the decks built from them |

`effects/` splits again by where the card comes from, because one file of 195
functions is not a file anyone reads:

| module | effects |
|---|---|
| `ironclad.py` | 93 |
| `colorless.py` | 100 |
| `status.py` | 4 — Status and Curse cards |
| `common.py` | 10 — helpers the others share |

The grouping is not by hand: each effect went to the module for the pool that
actually references it, computed from the tables.

`enemies/` splits the same way, by region:

| module | enemies |
|---|---|
| `overgrowth.py` | 27 — Act 1 |
| `hive.py` | 22 — Act 2 |
| `underdocks.py` | 20 — Act 1 |
| `glory.py` | 19 — Act 3 |
| `summons.py` | 11 — only ever spawned mid-fight |
| `events.py` | 4 |
| `model.py` / `shared.py` | the `Enemy` model, scaling, shared move builders |

Also computed, not chosen: each factory was placed by the region of the
encounters referencing it, and **all 92 encounter-referenced enemies mapped
to exactly one region** — no enemy straddles two. The 11 no encounter names
are summons, and every summoner points into that module, never sideways.

The import order is the dependency order: `pools` builds `Card`s out of the
effects, so those must exist first. Twelve effects need a pool table back
(Discovery draws from `CARD_POOL_IRONCLAD`), and those use a **deferred
import inside the function** — the cycle is real, and hiding it behind a
module-level trick would make `effects.py` unreadable to exactly the person
this split is for.

### `testing/` — everything that drives the engine

| file | what it holds |
|---|---|
| `play.py` | Terminal client: single fights or a 6-fight gauntlet with rewards. Reads `config.json` |
| `bench.py` | Difficulty measurement and balance-regression detection. Imports `play` to drive the real gauntlet |
| `demo.py` | Scripted showcase: card-pool smoke test, co-op battle, random RL episode |
| `simple.py` | The cut-down game — Strike and Defend only, 1–4 heroes — plus a 3-action `SimpleEnv` |
| `train_torch.py` | A PyTorch REINFORCE agent for `simple.py`, solo by default, saved to `simple_agent.pt` |
| `net/` | Networked co-op: one server terminal, one client terminal per player |

**Why `bench.py` is here rather than in `game_engine/`:** it calls
`play.run_gauntlet()` to measure the curve players actually get. Putting it in
the engine package would make `game_engine` depend on `testing`, which is
backwards.

For *why* things are the way they are — the porting history, the ambiguous
wiki readings, the bugs each pass turned up — see
**[ENGINEERING_LOG.md](ENGINEERING_LOG.md)**.

---

## Playing it

`play.py` gives you HP bars, telegraphed enemy intents with their damage,
inline statuses, your hand with full card text, and `d`/`p`/`r`/`u` to
inspect draw pile, discard, relics and potions. Two modes: a single fight
from any of the <!--encounters-->93<!--/--> encounters (grouped by region and normal/elite/boss), or
the 6-fight gauntlet with card/relic/potion rewards between fights.

```
-- Enemies --
  0: Nibbit  HP [#-------------------] 4/42  Intent: Butt (14 dmg)  [STRENGTH 2]

-- Ironclad --  HP [################----] 67/80  Block 0  Energy 2/3
Hand:
  0: [1] Strike -- Deal 6 damage.
  3: [2] Bash -- Deal 8 damage. Apply 2 Vulnerable.

Ironclad>
```

Co-op uses a free-choice "Whose turn?" menu each cycle rather than a fixed
P1-then-P2 order — one terminal has one input stream, so true simultaneous
input isn't possible, but you are not locked into a sequence.

### Networked co-op — one terminal per player

`testing/net/` replaces the shared terminal with real separate seats.

```bash
python testing/net/server.py --players 2            # the full game
python testing/net/server.py --simple --players 2   # simple.py instead
python testing/net/client.py --name Alice           # one per player
```

`--host` / `--port` / `--seed` on the server, `--host` / `--port` / `--name`
on the client. Party and encounter come from `config.json`; `--simple` reads
its `simple` section instead.

**Both games are served over the same protocol, by the same client.** They
sit behind one adapter (`net/games.py`) so the loop, the refusals and the
networking exist once: `FullGame` is 221 action ids and the real card pool,
`SimpleGame` is 3 ids and Strike/Defend. The client cannot tell them apart
and does not need to.

**The server owns the engine, and the action space is the wire protocol.** A
client sends an id from the <!--action_space-->161<!--/-->-id space and nothing else — never a card
name, never what should happen. Every id is checked against whose turn it is,
then against `legal_action_mask()`, before it reaches the engine. That mask
is already asserted correct by `test_env.py`, so it is the anti-cheat rather
than new code to trust.

**Anyone can act at any time.** There is no turn order — every player may
play cards whenever they like during the round. Sending `end turn` takes
*that player* out for the round; the enemy phase runs only once everyone has
ended, and then everyone is live again. That is closer to how co-op actually
plays than making P2 wait on P1.

**Moves are one per card, not one per card × target.** With two enemies on
the board, Strike is a single entry that then asks *which*; a card with only
one possible target sends immediately and asks nothing. Six moves shown where
the action space has nine ids.

Each client sees an egocentric view — itself first, its own hand only, and
its own legal moves, never anyone else's. `test_net.py` runs a real server
over real sockets and checks the refusals (illegal, out-of-range, non-integer,
acting after ending) and that the round advances only when *all* players have
ended.

The client holds **no rules**. It renders what it is sent and posts back an
id from the list it was handed, so swapping it for a GUI or an agent means
replacing one function.

### Configuring a run — `config.json`

`play.py` reads `config.json` for its setup, so changing the restrictions
doesn't mean editing Python. Anything left `null` or `"ask"` is still
prompted for, so the shipped config behaves exactly like the old startup.

```bash
python testing/play.py                    # uses ./config.json
python testing/play.py my_setup.json      # or any other file
```

Four presets, each a starting point you can override field by field:

| preset | what it gives you |
|---|---|
| `full` | the whole game — every card, relics, potions, all rewards |
| `basic` | Strike and Defend only, 30 HP, no relics/potions/rewards, straight into one fight |
| `coop` | three heroes — Ironclad plus two support decks — on the full game |
| `no_items` | full card pool, but no relics and no potions |

```json
{
  "preset": "basic",
  "party": [{"name": "Ironclad", "hp": 30, "energy": 3,
             "deck": "strike_defend", "starting_relic": null}],
  "content": {"relics": false, "potions": false, "card_rewards": false,
              "relic_rewards": false, "potion_rewards": false},
  "cards": {"allow": ["Strike", "Defend"], "deny": []},
  "mode": "single",
  "encounter": "1",
  "seed": null
}
```

`deck` is `"starter"`, `"coop_support"`, `"strike_defend"`, or an explicit
list like `["Strike", "Strike", "Bash"]`. Add up to four party members for
co-op. A `seed` pins the shuffles and enemy HP, so a UI can hand the same
fight to a human and to an agent.

**`cards.allow` / `cards.deny` apply to reward screens too**, not just the
starting deck — otherwise a "Strike and Defend only" run would be offered a
Perfected Strike after the first win.

**Statuses are deliberately not a toggle.** Vulnerable, Weak and the rest
come from enemy moves and card effects, so switching them off would mean
rewriting the content rather than flipping a flag. Restrict `encounter`
instead — a simple enemy applies none. Claiming a `statuses: false` switch
that didn't really work would be worse than not having one.

A bad config fails with a message naming the key (`party[0].hp must be a
positive integer, got -3`) rather than a traceback from inside the engine —
`game_engine/tests/test_config.py` checks eleven failure modes, because a UI writing this
file will get it wrong sometimes.

The suite checks that `config.json` **parses**, not what it says. It is a
settings file you are meant to edit, so asserting its contents would report a
legitimate switch to co-op as a broken build. The "full game by default"
promise is asserted against an empty config instead.

### `simple.py` — the cut-down game, solo or co-op

Same `config.json`, its own section. Nothing here is prompted for:

```json
"simple": {"players": 3, "player_hp": 30, "energy": 3,
           "enemy_hp": 75, "enemy_damage": 11,
           "max_turns": 50, "scale_enemy": null}
```

```bash
python testing/simple.py               # uses ./config.json
python testing/simple.py coop.json     # or any other file
```

`players` is 1–4. Every entry point takes these as keyword arguments —
`battle(greedy, players=3)`, `SimpleEnv(players=3)`,
`play_interactive(players=3)` — and `config.simple_kwargs(cfg)` hands you
exactly that dict.

At the keyboard, `->` marks whose sub-turn it is. The party keys:

| key | effect |
|---|---|
| `n` | next hero in seat order; past the last one the round ends |
| `s2` | jump straight to Hero 2 — any living hero, forwards or back |
| `s` | list the heroes and ask which |
| `a` | every hero's hand at once, `x` marking what they cannot afford |
| `e` | end the round for **everyone** — the enemy attacks |

Seat order is only the default; `s` is there so you can open with whichever
hand `a` showed you is worth opening with. All four keys are hidden in solo.

**`scale_enemy: null` means "on when `players > 1`."** The Dummy hits one
target, so without scaling damage-per-hero falls as 1/n while party HP grows
as n, and co-op becomes a walkover. Note that co-op is *not* tuned the way
solo is — see `battle()`'s docstring for the measured table, including the
policy ordering inverting at 3–4 heroes.

---

## Training against it

`CombatEnv` gives you `reset(seed=None)`, `step(action)`,
`legal_action_mask()`, `action_space_size()` (<!--action_space-->161<!--/-->),
`observation_space_size()` (<!--obs_size-->588<!--/-->), `OBS_OFFSETS` for slicing the
observation, and `hand_card_ids()` if you want your own card embedding.

### Which class to use

`CombatEnv` keeps the **old gym API** — `reset() -> obs`, `step() -> (obs,
reward, done, info)` — because `play.py`, `demo.py`, `bench.py`,
`testing/tools/` and the test suite all drive it directly and none of them
want a 5-tuple.

For Gymnasium / Stable-Baselines3, use the adapter:

```python
from game_engine.env import GymnasiumEnv

env = GymnasiumEnv(make_players, make_enemies, seed=0)
obs, info = env.reset()
obs, reward, terminated, truncated, info = env.step(action)
mask = env.action_masks()          # the name sb3-contrib MaskablePPO expects
```

`gymnasium` is an **optional** dependency — the project itself needs only
numpy. When it is installed the adapter subclasses `gymnasium.Env` and
publishes real `Box`/`Discrete` spaces (which SB3's `isinstance` checks
want); when it is not, the same class still works standalone.

**Terminated is not truncated.** A fight won or lost is `terminated`, and its
value bootstraps from the terminal reward. A fight cut off by the turn cap is
`truncated`, and the learner must bootstrap from the value function instead.
Collapsing them teaches the agent that hitting the cap is worth whatever the
terminal bonus was.

### Episode boundaries

Two guarantees a rollout loop depends on:

- **A finished episode is absorbing.** Stepping past `done` returns zero
  reward and changes nothing. It used to re-award the ±10 terminal bonus on
  *every* extra step, so a loop that ignored `done` could farm unbounded
  reward from a won fight — silent, because nothing crashed.
- **Episodes are bounded.** `max_turns=200` (pass `None` to disable)
  truncates rather than letting a pathological fight hang the rollout
  collecting it. No non-terminating fight could actually be constructed —
  enemies gain Strength and eventually out-scale any fixed block, and real
  fights run ~14 turns — but "probably terminates" is not a bound. At 200 it
  cannot fire by accident; it exists for the case nobody predicted.

### Seeding and reproducibility

**Same seed → same episode, exactly.** Both sources of randomness are pinned
by one number:

```python
env = CombatEnv(make_players, make_enemies, seed=7)
env.reset()            # replays seed 7 every time
env.reset(seed=21)     # or seed per episode, gym-style
```

This was not true until recently, and the failure was invisible: enemy HP is
rolled inside `make_nibbit()` **before any engine exists**, off the global
`random` module that nothing seeded. `CombatEnv(seed=7).reset()` fought a
different Nibbit every time — no episode replay, no fixed-seed A/B between
policies, no reproducing a specific fight to debug it.

Construction-time randomness now draws from `entities.CONTENT_RNG`, seeded by
`seed_content()`. Seeding is the *driver's* job, because only the driver
knows when an episode begins and it must happen before the factories run —
`env.reset()`, `bench.run_encounter()` and `testing/tools/` all do it.

Two things worth knowing:

- **An unseeded env still varies.** `CONTENT_RNG` self-seeds from system
  entropy exactly as the global module did, so `play.py` and `demo.py` are
  unaffected. `seed_content(None)` opts back out deliberately.
- **One stream per process.** Two envs whose `reset()` calls interleave would
  share it. That cannot happen in single-threaded Python or across
  subprocesses, but it *would* with threaded vectorised envs.

### Action space

`cards at enemies | cards at players | end turn` —
<!--action_space-->161<!--/--> ids.

| range | meaning |
|---|---|
| `[0, 120)` | play hand slot *s* at **enemy** *t* (10 slots × 12 enemies) |
| `[120, 160)` | play hand slot *s* at **player** *t* (10 slots × 4 players) |
| `160` | end turn |

**Potions are out of both the action space and the observation.** Cutting one
without the other would leave an agent able to drink what it cannot see.

**Enemies and players are separate axes.** They used to share one 12-wide
target axis, so `slot×12 + 2` meant "enemy 2" when that slot held a Strike
and "ally 2" when it held a heal — one id with two meanings, told apart only
by a card that changes every turn. 40 ids buys that away.

**Player-target index *t* is observation player row *t*** — self at 0,
teammates at 1–3, the same egocentric order the observation uses. `ALLY`
("another player") never offers row 0; `SELF_OR_ALLY` does.

Cards with no target to choose — `SELF`, `ALL_ENEMIES` — stay on the enemy
axis at index 0 as a placeholder, because an axis whose purpose is expressing
a choice is the wrong home for a card that has none. What the agent needs
there is *which* mode the card is, and that arrives as a hand feature.

**`legal_action_mask()` is trustworthy: masked-legal means the engine will
accept it.** That is asserted, not assumed — `test_env.py` sweeps all pool
cards across five gate states and drives 650+ masked random steps checking
the illegal-action penalty never fires.

### Observation layout

<!--obs_size-->588<!--/--> float32s. Slice with `env.OBS_OFFSETS` rather than recomputing the
arithmetic — when this section last grew, every hand-rolled offset in the
test suite broke at once.

| section | span | contents |
|---|---|---|
| players | 0–80 | (HP, block, energy + 17 status channels) × 4 |
| enemies | 80–320 | (HP, intent, block + 17 status channels) × 12 |
| piles | 320–352 | 4 piles × 8: count, 5 card-type counts, total damage, total block |
| hand | 352–552 | 20 features × <!--hand_limit-->10<!--/--> slots |
| ally_summary | 552–588 | 3 teammates × 12 capability counts (`observe.py`) |

**Teammates are capability counts, not raw hands.** The action space indexes
your *own* hand slots and never a teammate's, so slot structure there was
pure cost — 600 floats became 36. Per teammate: how many playable cards give
damage, block, draw, Strength, Energy, Vulnerable, Weak, or target an ally,
plus `other`, `dead` (held Status/Curse clutter) and the playable damage and
block totals. `other` and `dead` exist so no card is invisible — every one of
the 212 pool cards maps to at least one capability, and a test asserts it.

Counts are of what a teammate can **play**, not hold: the hand discards
wholesale at end of turn, so a card they cannot afford is gone rather than
waiting. `dead` is the exception, because a clogged hand is exactly where
holding matters.

**Piles carry composition, not just size.** A bare count cannot answer "how
many Defends are left" or "is there enough damage in the deck to finish
this"; type counts and damage/block totals can. Relics and potions were
removed outright — 343 floats that are always zero under a `no_items` config.

Design choices behind that shape:

- **The hand is semantic features, not a card-identity one-hot.** 10 slots ×
  <!--card_ids-->226<!--/--> printings would be 2260 floats teaching nothing transferable between
  Strike and Ultimate Strike. Per slot: `occupied`, `playable`, `cost`,
  `is_x_cost`, five card-type bits, `damage`, `block`, `exhausts`, `retain`,
  `ethereal`, `upgraded`, and five targeting bits. Anything wanting true
  identity calls `hand_card_ids()` and owns an embedding table — ids are
  nominal, so they are deliberately *not* folded in as scaled floats.

- **The targeting bits are load-bearing, not decoration.** The action space
  asks for a target index per slot, and card *type* does not say what that
  index means — an Attack takes an enemy, a Skill might take an enemy, an
  ally, or nobody. Without `targets_enemy` / `targets_all_enemies` /
  `targets_self` / `targets_ally` / `targets_self_or_ally` the network had to
  infer targeting from `damage` and `block`, and its only other signal was
  the mask zeroing its illegal choices *after* the fact — correction rather
  than information.
- **Potions are the opposite choice, on purpose.** A potion is an opaque
  effect callable with no comparable structure, so identity is all there is
  to encode. Per-slot, because the action space indexes slots.
- **Statuses are 17 curated channels, not 44 sparse ones.** Several *fold*
  the way the engine reads them: `strength` is the same net value
  `deal_attack_damage` uses (shared code, not a reimplementation),
  `plating` = METALLICIZE + PLATED_ARMOR, `evasion` groups
  SLIPPERY/SOAR/FLUTTER, `restricted` groups
  RINGING/SMOGGY/HEX/TANGLED/DOWNGRADED. `other_debuffs` is a catch-all so
  anything outside the list is visible as *something*. Negative Strength
  keeps its sign — clamping would hide the point of Shrink.
- **The returned array is a fresh copy.** `_observe` fills a reused buffer
  and copies out, so storing observations in a replay buffer is safe.

### Reward

Shaped for damage dealt, +10 victory, −10 defeat, −1 illegal action. A
starting point, not gospel.

### The co-op view is egocentric

**Player slot 0 is always the acting player**, with teammates following in
wrapped seat order. A single shared policy — the normal way to train co-op —
therefore reads its own HP at a fixed place.

The player block used to be ordered by seat, so slot 0 held P0 whether or not
P0 was acting. That is unlearnable for a shared policy, and it also made the
vector internally inconsistent: the relic, potion, pile and hand sections have
always described the *acting* player, so the observation showed one player's
hand beside another player's HP.

Ally target indices count over the same order, so **ally action `k` names
player slot `k+1`**. That correspondence is the point — rotating the
observation while leaving targeting in seat order would have moved the bug
rather than fixed it. A downed ally keeps its slot so the mapping does not
shift underneath the agent; the mask simply stops offering it.

Remaining limit: `env.py` models co-op as sequential per-agent sub-turns,
which is the simplest interleaving rather than the only sensible one.

---

## Content coverage

Every count here is checked against the live code by `tests/content_audit.py`
on every test run.

| | ported | notes |
|---|---|---|
| Ironclad cards | <!--ironclad_cards-->91<!--/--> | <!--ironclad_pool-->86<!--/--> in the reward pool, 3 Basic, 2 Ancient held out |
| Colorless | <!--colorless_ported-->135<!--/--> of <!--colorless_module-->151<!--/--> | <!--colorless_pool-->91<!--/--> in-pool + <!--ancient_colorless-->9<!--/--> Ancient; the rest are other-class or quest cards |
| Curses | <!--curses-->18<!--/--> | |
| Enemies | <!--enemies-->106<!--/--> | all three acts, every normal/minion/elite/boss |
| Encounters | <!--encounters-->93<!--/--> | across Overgrowth, Underdocks, Hive, Glory, events |
| Relics | <!--relics-->83<!--/--> | every one implementable from combat-visible triggers |
| Potions | <!--potions-->52<!--/--> | 48 reward-pool + 4 Special tier |
| Distinct card ids | <!--card_ids-->226<!--/--> | `cards.CARD_IDS`, name-sorted so they're stable across processes |

---

## How the engine fits together

### One rule set, every reader

"May this card be played?" lives in exactly one place:
`CombatEngine.why_not_playable(player, card)`, which returns `None` or a
reason string. `play_card` enforces it, `playable_cards` filters on it, and
`env.legal_action_mask` calls `playable_cards` and decides only *targeting*.

That matters because the rules used to exist in three copies and drifted in
both directions — Ringing/Smoggy/Bound were checked only in `play_card`, and
the env mask knew about neither those nor anything added later. A gate added
now is automatically known to all three.

A sweep over the hand shares one `_HandContext` snapshot so the hand-wide
rules (the Sloth/Normality play cap, Enthralled's must-play-first) are
answered once instead of once per card. It is a per-sweep snapshot, not a
cache: it is built, used within a single pass over a hand that cannot change
mid-pass, and dropped.

### Shared status arithmetic

Effective Strength is four statuses — permanent, this-turn, and two
positive-counter LOSS variants — folded into one number by
`statuses.net_strength()`. `deal_attack_damage`, `gain_block` (via
`net_dexterity`) and the observation all call it.

That last one is the point: an observation computing Strength even slightly
differently from the rules teaches the agent a number the engine does not
use.

### Entity defaults

`Player` and `Enemy` each carry state the other doesn't, but the damage and
block code is shared. Those one-sided fields are declared as **immutable
class attributes on `Entity`**, so shared code reads `self.field` plainly.

The block doubles as the inventory of what shared code may touch. Every
default must stay immutable — a mutable one would be a single object shared
by every instance, and `attacked_by_this_turn = []` would mean appending a
Gang Up attacker to one enemy appended it to all twelve.

### Event hooks

Several real Powers only make sense as a standing rule ("whenever a card is
Exhausted, draw"). `Player.register_hook(event, callback,
expires_this_turn=False)` installs a listener; `combat.py` fires
`card_played`/`attack_played`/`skill_played`/`power_played`/
`card_exhausted`/`enemy_died`/`enemy_turn_end`/`use_potion`/`reshuffle`, and
`entities.py` adds `block_gained`/`hp_lost`/`status_gained`/`status_applied`.
`expires_this_turn=True` (used by Rage) is stripped in `Player.end_turn()`.

### Multiplayer enemy scaling

Verified formulas, not guesses:

```
MultiplayerMonsterHP = MonsterHP * PlayerCount * ActScaling
MultiplayerBlock     = Block * PlayerCount * ActScaling
  EXCEPT 2-player Block is a flat x2 (patch-nerfed July 2026), not act-scaled
ActScaling: Act1=1.1, Act2=1.2, Act3 hallway=1.2, Act3 boss=1.3
```

`CombatEngine(players, enemies, act=..., scale_enemies=True)` applies this at
construction. Special-buff scaling is implemented too, and all four have a
real StatusType *and* a real enemy granting them:

| buff | formula | granted by | 1p → 4p |
|------|---------|-----------|---------|
| Plating | `n * ((p-1)*2 + 1)` | Sewer Clam (Underdocks) | 8 → 56 |
| Slippery | `n * p` | Inklet, Vantom (Overgrowth) | 1 → 4 |
| Artifact | `n + (p-1)` | Punch Construct (Underdocks) | 1 → 4 |
| Skittish | `int(n * ((p-1)*0.5+1))` | Phantasmal Gardener (Underdocks) | 6 → 15 |

**Thorns is deliberately absent**: no enemy *starts* with it, so
`scale_enemy_for_players()` would never see it, and inventing a formula for a
case that cannot occur would be guessing.

---

## Tests

```
$ python game_engine/tests/run_all.py
test_thorns      PASS    0.1s
...
test_state_drift PASS    0.1s
...
smoke_all        PASS    0.6s
----------------------------------------
21/21 passed in 9.0s
```

<!--test_suites-->22<!--/--> suites, several hundred assertions, ~5 seconds. `python game_engine/tests/run_all.py
env choice` filters by name; `-v` streams each suite's output; it exits
non-zero with the failing `[FAIL]` lines, so it works as a commit gate.

They are plain scripts, not a framework: each prints its own `[ok]`/`[FAIL]`
lines in game terms (`Retain keeps its own card in hand: got ['Purity'], want
['Purity']`). The runner just executes them and collects exit codes, so any
suite stays individually runnable.

Worth stating what that net catches, since "the tests pass" is cheap to say.
In one session it caught: a `None`-target crash in Havoc/Cascade, a hole
where 999 energy made unplayable Status cards castable, Mind Rot and Waste
Away silently expiring after one turn, Rebound bouncing itself, Doubt and
Shame decayed to nothing the instant they applied, an infinite recursion in
`add_to_hand`, and the hand cap quietly disabling Havoc.

### State drift is guarded

`Player.__init__` declares ~55 fields and `start_combat()` re-initialises
almost all of them — two hand-maintained lists of the same thing. Forgetting
one has **no symptom in a unit test**: the field just keeps its value from
the previous fight, so Corruption is still active in gauntlet fight 4.

`test_state_drift.py` poisons all 65 resettable fields, checks the combat and
turn boundaries restore them, checks no field is born late (only after
`start_combat`), checks the allowlists for stale entries, and plays a real
fight to confirm nothing survives into the next. It is derived from
`vars(player)`, not a hand-written field list — that would be a third copy of
the same inventory, drifting exactly like the two it polices.

It is mutation-tested: six reintroduced drift bugs, all caught, clean
baseline passes.

### The numbers in this file are checked

`content_audit.py` checked the *code* against the wiki; nothing checked this
*prose*, so counts went stale silently — "102 enemies" when the audit had
been printing 106 for a while, with two places in this same file disagreeing.

Load-bearing numbers are now wrapped in markers:

```
ALL THREE ACTS are complete -- <!--enemies-->106<!--/--> enemies across ...
```

which render as plain `106`. `content_audit.py` extracts them and compares
against live values, failing on any mismatch. **Every occurrence is checked,
not one per fact**, because the bug this exists to catch was two places
disagreeing with each other. A fact with no marker is reported as unchecked
rather than failing — an unmarked number is just prose, not a claim.

Markers rather than regexing the prose, deliberately: the numbers are not
distinguishable by value. "18" appears here as the curse count, an
observation size, a benchmark percentage and a table cell.

### `testing/tools/` — the diagnostics behind the numbers

Experiments, deliberately not in the runner — they measure rather than
assert, so there is nothing for a runner to pass or fail. Each produced a
figure this file states:

- `diag36_matrix.py` — the deck ablation showing the "flat difficulty curve"
  was a median artifact
- `diag36_godcheck.py` — the god-deck probe proving nothing is ported
  unwinnable
- `check_env_drift.py` / `check_env_obs.py` — the proofs that the action mask
  disagreed with the engine, and that the hand was invisible
- `choice_ab.py` / `choice_variants.py` — the A/B showing greedy-everywhere
  loses to random

Run them from the repo root — `python testing/tools/diag36_matrix.py`. All
six together take about 26s. They sit under `testing/` rather than beside the
engine because four of them import `bench.py` and `play.py`, and
`game_engine/` is not allowed to depend on anything outside itself.

---

## Performance

Measured with alternating in-process A/Bs on identical seeds, best-of-3 per
arm. This machine's noise floor is several percent, so single-run
microbenchmarks are not quoted.

| change | effect |
|---|---|
| Reused observation buffer | **+21% to +38%** on `env.step` |
| `StatusType` identity hash | **~+6%** (8 measurements, all positive) |
| `Entity` class-attribute defaults | `getattr` 57,425 → 4,878 calls; `deal_attack_damage` 1.14–1.17× |
| Shared `net_strength`/`net_dexterity` | engine call sites 1.6–1.8× |
| `playable_cards` O(n²) → O(n) | **no measurable change** — see below |

Two honest notes:

**The `playable_cards` rework bought nothing.** It was projected at ~17%;
that figure was the *share of runtime* legality checking occupied, not the
achievable saving. Hands are 1–6 cards in practice, and O(n²) at n≤6 with a
small constant is already fast. It was kept for the DRY win — the play-cap
rule no longer has a second copy — not for speed.

**`_status_features` gave back ~7%** in the heavy-status case by calling the
shared strength helper instead of inlining the sum. Taken deliberately: that
vector is what the agent learns from, and correctness beats 7% of one
function.

---

## Scope — what is deliberately not here

These are **permanent boundaries**, not a backlog.

- **Ironclad only.** Silent, Regent, Necrobinder and Defect will not be
  ported, so their resource systems (Shivs/Poison/Discard, Star/Forge,
  Souls/Summon/Doom, Focus/Orbs/Channel) do not exist. Their potions, the
  relics keyed to them, and the Colorless module's other-class tokens are
  therefore excluded too. Co-op is unaffected: it is 1–4 Ironclads, and every
  ally-targeting card works with an Ironclad on the other end.
- **Map, shops, rest sites, gold, events.** This is a combat replica. What
  stays in scope is anything between "combat starts" and "combat ends", plus
  the pools that feed it. Where a card or relic has a self-contained combat
  half, that half is ported and the economy clause ignored.

Genuinely unfinished, as opposed to out of scope:

- **Waterfall Giant's move order** is invented; the wiki lists its moves but
  not their sequence.
- **Disintegration's "6/7/8"** cannot be resolved from available sources.
- **A damage-modifying-by-card-name pipeline** would let in `Razor Tooth` and
  `Unsettling Lamp`, but requires touching every card effect function — high
  regression risk against verified behaviour, low value.
- **Relic drop cadence** (one offered after every gauntlet win) is invented
  pacing, not a wiki-verified rate. `Enemy.category` exists now, so
  differentiated elite/boss rates are a small job.
- **Board cap of 12** is this replica's invention. Two summoners are unbounded
  by their own text — Two-Tailed Rat's "Call for Backup" summons another
  Two-Tailed Rat — so without a cap it is an infinite spawn loop.

---

## A source-reliability note

One SEO/blog site (slaythespire-2.com) claims co-op has "no revive mechanic —
if either player is defeated, the run ends," directly contradicting the
structured wiki.gg page (which has edit history, patch notes, and cites
specific formulas). Treat wiki.gg as authoritative where sources conflict;
the revive-at-1-HP mechanic is very likely real.

The same lesson applied to cards: the wiki's human-written "Cards List" page
cross-contaminated STS1 and STS2 data for the Rare tier, listing real STS1
cards (Metalicize, Heavy Blade, Reaper, Searing Blow) that don't exist in
STS2's Ironclad pool. The raw data module is the trusted source.

---

## Design decisions worth knowing about

- **`Card` is `@dataclass(eq=False)`.** The generated `__eq__` compared all
  fields, so two freshly-made Slimed cards were `==`. Every `card in hand` /
  `list.remove(card)` in this codebase means *this exact instance*, and one
  real bug came from that: playing Slimed drew a new Slimed, and the exhaust
  removed the wrong one.
- **A card in hand IS the deck object.** `start_combat` copies the *list*, not
  the Cards, so `card.upgrade()` on a hand card would persist for the whole
  run. Combat-scoped mutations go through `upgrade_for_combat()`,
  `set_temp_cost(scope=)` and `grant_replay()`, all reverted at combat end.
- **Unplayable is a keyword, not a big number.** Status/Curse cards carry
  `UNPLAYABLE = 999` as cost, but legality gates on `is_unplayable()` — 999
  energy previously made Wound castable.
- **`Cleave` was removed.** It doesn't appear in the Ironclad data module at
  all; it was an STS1 holdover. `Bloodletting`, briefly suspected of the
  same, turned out to be a genuine STS2 card.

---

## Engineering log

The porting history, the ambiguous wiki readings, the measurement
investigations and the bugs each pass turned up live in
**[ENGINEERING_LOG.md](ENGINEERING_LOG.md)** (~1,200 lines). Numbers there are
historical and not re-checked by the audit; the counts in *this* file are the
live ones.
