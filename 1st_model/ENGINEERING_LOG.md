# Engineering log

The build narrative for the combat replica: what was ported when, what the
wiki actually said, which readings were ambiguous, and the bugs each pass
turned up. Roughly chronological.

This used to live in `README.md`. It was moved out because it had grown to
about 1,200 lines and buried the reference material -- not because it stopped
being useful. Nothing was deleted in the move.

`README.md` is the reference doc: what this is, how to run it, the RL
interface, coverage counts, and current scope. Come here for *why* something
is the way it is.

**Numbers in this file are historical.** They were true when written and are
not re-checked by the audit; `README.md`'s counts are the live ones, verified
by `tests/content_audit.py` on every run.

---

## What's now verified against real STS2 data
- Basics (Strike/Defend/Bash) and ~24 more Ironclad Common/Uncommon cards —
  exact costs, damage, block, and upgrade numbers from the user's sheet
  (all 27+ ported cards spot-checked row-by-row against the full 90-card sheet)
- **36 more Ironclad cards** (source: wiki, see the note at the top of this
  file), individually unit-tested against their exact wiki wording —
  bringing the total to 63. Needed two small engine additions, both
  small/scoped like every other addition this project has made: a
  `turn_start` fireable event (mirrors relics' `on_turn_start`, but for
  cards -- Demon Form/Crimson Mantle/Pyre's "at the start of your turn, X"
  register for it via the normal `register_hook` a Power already uses for
  everything else) and a `hp_loss_events_this_combat` counter (Tear
  Asunder needs a COUNT of self-inflicted HP-loss events, not the
  existing `lost_hp_this_combat`'s total AMOUNT). Also found and fixed a
  design limitation while implementing Mangle: `Entity.add_status()` pops
  a status entirely once its stack count reaches ≤0, so it structurally
  can't represent a temporary NEGATIVE stat reduction (as opposed to a
  temporary positive gain, which `STRENGTH_THIS_TURN` already handles
  fine) -- Mangle needed exactly that ("enemy loses N Strength this
  turn"), so it's deferred rather than hacked around; see known gaps.
- Ironclad starting deck (5 Strike / 4 Defend / 1 Bash) and 80 Max HP,
  confirmed against the wiki's Ironclad page
- Real multiplayer cards `Blaze`, `Demonic Shield`, `Tank`
- Vulnerable (1.5x dmg), Weak (0.75x dmg), Frail (0.75x block), Shrink
  (0.7x dmg) — all confirmed directly against the wiki's Debuffs page
- Player cap raised to 1-4 (STS2 confirmed 2-4 player coop)
- Status stack-type/turn-behavior categories, per the Buffs/Debuffs wiki pages
- Event-hook system: `Dark Embrace`, `Feel No Pain`, `Rage` all ported and tested
- **Enemy HP + Block scaling by player count and Act**, exact wiki formulas,
  including the 2-player Block-scaling patch nerf
- **Enemy roster**: Nibbit, Shrinker Beetle, Fuzzy Wurm Crawler are real
  STS2 Act 1 ("Overgrowth") mobs with wiki-sourced HP/movesets (previously
  this replica used STS1-only enemies that don't exist in STS2 at all)
- **Ally target choice for 3-4 players**: both `play.py` (already correct)
  and `env.py`'s RL action space (previously always picked the first ally)
  now let the actor choose which living teammate an `ALLY`-targeted card hits
- **Cost-changes-on-upgrade**: `Body Slam`, `Havoc`, `Tank` (1→0) and
  `Dark Embrace` (2→1) now actually cost less energy once upgraded,
  via `Card.upgrade_cost` / `Card.current_cost()`
- **Death/revive-at-1-HP co-op mechanic**: in `run_gauntlet()`, a player
  who hits 0 HP mid-fight but whose team still wins revives at 1 HP for
  the next encounter, per the wiki (see source note below); they weren't
  excluded from the fight they died in either — teammates can already
  finish a fight solo, since `combat.py` only calls defeat once every
  player is down
- **Relics**: Ironclad's real starting relic `Burning Blood`, plus 67 more
  real, wiki-sourced relics spanning Common/Uncommon/Rare (including
  Ironclad's 3 Rare class relics) — every one that's implementable purely
  from combat-visible triggers, without Gold/Shop/Rest-Site/map systems
  this replica doesn't have (see known gaps for the excluded list).
  Offered as a reward alongside cards after each gauntlet win.
  Getting relic effects to actually stick took care: `Player.start_turn()`
  unconditionally resets Block to 0 and rebuilds the hand from scratch
  every turn (including turn 1), so a relic firing during
  `CombatEngine.__init__` (before turn 1 even starts) would have its
  Block/extra-draw wiped out the instant `start_player_turn()` ran. Relic
  `on_turn_start` effects fire from inside `start_player_turn()` itself
  instead — every turn, not just turn 1, with each relic's own callback
  checking `turn_number` for "start of combat"/"2nd turn"/"every N turns"
  semantics — so they land on top instead of getting clobbered. Getting
  the *reactive* relics (Demon Tongue, Ruined Helmet) right took a second
  pass too: a naive "fires once per combat" wrapper marks itself fired on
  the FIRST matching event regardless of whether that specific event
  passes the relic's own filter (source == "self", status == Strength),
  which would permanently swallow the real trigger if an irrelevant event
  of the same event-name happened to fire first — fixed by having those
  two track their own "actually fired" flag instead of using the generic
  helper.
- **Potions**: 28 real, wiki-sourced potions (players start with 3 slots,
  wiki-confirmed), used via a `u` command in `play.py` and offered as a
  reward alongside cards/relics after each gauntlet win (gated on having
  a free slot, matching real STS2 behavior). Building this surfaced a
  genuine pre-existing bug: `Dexterity` was tracked as a status since
  early in the project (comment: "+N block on block-granting cards") but
  `gain_block()` never actually consulted it — several already-shipped
  relics (Oddly Smooth Stone, Kunai, Sparkling Rouge...) were granting a
  status with zero mechanical effect. Fixed in `entities.py`, applied as
  a flat add mirroring how Strength adds flat damage before Weak's
  multiplier. Also added a new `DEXTERITY_THIS_TURN` status (mirroring
  `STRENGTH_THIS_TURN`) for Speed Potion, and a new `enemy_turn_end`
  broadcast event in `combat.py` for Powdered Demise's per-enemy delayed
  damage. Also went back and ported the 4 relics originally skipped for
  needing a potion system: `Potion Belt`, `Petrified Toad`, `Reptile
  Trinket`, `White Beast Statue` (the last one's effect is already this
  replica's default behavior — see the comment in `relics.py`).
- **Special enemy buff scaling, exercised**: added a real `SLIPPERY`
  status ("the next N times this creature loses HP, it only loses 1 HP
  instead," per the wiki -- a fully-blocked hit spends no stack) and
  `Inklet` (real Act 1 mob, always fights as a trio of 3, each starting
  with 1 Slippery), specifically because no enemy in this replica used
  any of the four special-scaling buffs before this, leaving
  `scale_special_buff()` untested against a real fight. Wired generically
  via a new `SPECIAL_BUFF_STATUSES` map in `enemies.py` -- any enemy
  factory can set a starting `PLATED_ARMOR`/`SLIPPERY` stack count at its
  base/solo value, and `scale_enemy_for_players()` now scales it
  automatically, the same way it already scaled HP. `play.py`'s gauntlet
  loop needed a small generalization too: encounter factories used to
  always return a single `Enemy`, wrapped in a list by the caller;
  `make_inklet_trio()` returns a list of 3 directly, so the loop now
  accepts either shape. `Inklet Trio` is GAUNTLET's new 4th fight (and a
  5th `ENCOUNTERS` single-fight option), verified in both solo and a real
  2-player run where the multiplayer formula (`Amount * PlayerCount`)
  visibly changes the starting stack count.
- **Elite and boss**: real Act 1 encounters `Byrdonis` (elite -- HP
  81-84, gains 1 Strength every one of its own turns via "Territorial 1",
  alternates Swoop/Peck) and `Vantom` (boss -- HP 173, starts with 9
  Slippery, cycles Ink Blot/Inky Lance/Dismember/Prepare). GAUNTLET is
  now 6 fights, closing on the boss. The OTHER Overgrowth elite, Phrog
  Parasite, was passed over -- its Infect move needs its own status-card
  type distinct from Wound, and its death effect summons 4 new enemies
  mid-combat, which this engine's enemy list (fixed once at
  `CombatEngine` construction) has no mechanism for. Vantom's Dismember
  needed a real Wound status card (`CardType.STATUS`, `make_wound()`),
  the first "unplayable" card this replica has had to model -- verified
  that Wounds never leak into `deck_template` (they only ever enter
  `discard_pile`, which `start_combat()` doesn't carry between fights, so
  they're naturally combat-scoped, matching real STS).
- **Feed, Pillage, Rampage**: the three cards flagged as lowest-risk from
  the second batch's deferred list, now done. Feed needed nothing new --
  `take_damage()` already returns a `killed` flag on its `DamageResult`.
  Pillage needed a draw-until-condition loop, written to terminate safely
  even against an all-Attack deck (verified directly: draws every card
  and stops, doesn't hang). Rampage needed a new `Card.combat_bonus_damage`
  field -- deliberately NOT reusing `values`/`upgraded` (which are
  permanent, run-long) since deck_template's Card objects are the same
  objects replayed every fight in a gauntlet; `Player.start_combat()`
  resets it to 0 for every card in `deck_template` at the start of each
  fight, verified the bonus does NOT persist into a second combat.
- **17 more real Overgrowth normal monsters**: the 5 "Ruby Raiders"
  (Assassin/Axe/Brute/Crossbow/Tracker), Cubex Construct, Fogmog (missing
  its Illusory Spores summon move, same blocker as Phrog Parasite),
  Mawler, Vine Shambler, Flyconid, Slithering Strangler, Snapping
  Jaxfruit, both Leaf Slime sizes, both Twig Slime sizes, and Wriggler --
  all 21 real normal monsters now (Nibbit/Shrinker Beetle/Fuzzy Wurm
  Crawler/Inklet were already done). Needed two new mechanics: a
  `CONSTRICT` status (Slithering Strangler -- "while the applying enemy
  is alive, take N damage at the end of your turn", resolved as a fixed
  engine rule each turn rather than a registered hook, same reasoning as
  Poison/Regen already being direct logic) and Infection's real active
  effect (a genuinely different case from Wound: Infection deals damage
  if still in hand at end of turn, so its effect had to live in
  `CombatEngine._resolve_infection()` since an Unplayable card's own
  `effect()` never runs). Also surfaced and fixed a real, structural bug
  along the way while implementing Slimed (a *playable* status card,
  unlike Wound/Infection): `Card` was a plain `@dataclass`, which
  auto-generates `__eq__` comparing every field -- so two freshly-made
  Slimed cards (identical fields) were `==` to each other. Playing Slimed
  drew a NEW Slimed into hand, and the subsequent `exhaust_card()` call
  (holding a reference to the ORIGINAL, already-played instance, no
  longer in hand) matched and incorrectly exhausted the newly-drawn one
  instead, since list membership/removal (`in`, `.remove()`) both use
  `==`. Fixed with `@dataclass(eq=False)`, falling back to identity
  comparison -- checked first that nothing in the codebase relied on
  value-equality between distinct Card instances (nothing did; existing
  code already used `is` for this exact reason in a few places, like
  Burning Pact's `c is not card`). This was a latent risk anywhere two
  cards with identical field values could coexist (e.g. two unplayed
  starting Strikes), not something introduced by this batch -- just
  surfaced by it. Full validation: all 25 `ENCOUNTERS` as of that pass
  (Nibbit through Wriggler — Underdocks added 11 more later) run cleanly
  against the complete card pool + full relic pool.

## Underdocks — the other half of Act 1 (partial port)
Act 1 in STS2 randomly picks between **two** regions per run: Overgrowth
and Underdocks. Only Overgrowth was ported, and nothing in this file said
so -- it was an undocumented blind spot, not a tracked deferral. Found
while researching which enemies actually grant Artifact/Skittish.

Ported (all 22), all wiki-sourced: **Calcified Cultist**, **Damp
Cultist** (both use Ritual, which only started working at all after the
enemy per-turn tick fix), **Seapunk**, **Sludge Spinner**, **Sewer Clam**
(Plating 8), **Punch Construct** (Artifact 1), **Haunted Ship** (shuffles
5 Dazed), **Toadpole** (Thorns 2), and the **Phantasmal Gardener** elite,
which fights as four with Skittish 6 each and staggered move cycles so no
two ever act alike on the same turn.

Three statuses landed with them:
- **Artifact** ("Negates X debuffs") intercepts inside `Entity.add_status`
  before the debuff lands. Needed a `DEBUFF_STATUSES` set, since buffs and
  debuffs had only ever been separated by *comment*. Only positive
  applications are negated -- negative amounts are decay/removal steps
  (`decay_statuses_end_of_turn` calls `add_status(s, -1)`), and eating
  those would mean debuffs could never wear off.
- **Skittish** ("The first time this creature is hit each turn, it gains X
  Block") fires once per CARD, not per hit -- the wiki is explicit that
  Twin Strike lands both hits before the Block appears. So it resolves
  after the whole card does, via a `hit_by_current_card` flag rather than
  inside `take_damage`. Its stacks are the block AMOUNT and are never
  spent; the once-per-turn limit is a separate flag.
- **Thorns** ("When hit by an attack, deal X damage back") is the exact
  opposite of Skittish and fires once per HIT — see its own section below.

Deliberately NOT ported and why:
**Living Fog** (undocumented "Smoggy" + summons Gas Bomb), **Corpse Slug**
("Ravenous"), **Fossil Stalker** ("Suck"), **Gremlin Merc** ("Surprise"/
"Thievery" -- Thievery needs gold), **Fat/Sneaky Gremlin** and **Gas
Bomb** (minions needing mid-combat summoning), **Two-Tailed Rat** ("Call
for Backup", summoning). Ravenous/Suck/Surprise/Thievery/Minion are all
absent from the wiki's Buffs page -- the same wall Slippery and Skittish
hit, where a third-party site was the only source. Underdocks' other two
elites (Skulking Colony, Terror Eel) and all three bosses (Waterfall
Giant, Soul Fysh, Lagavulin Matriarch) are unported.

Difficulty note: Underdocks content measured much harder than Overgrowth's.
The **Cultist pair sits at 58%** (23/40) with a starter deck -- the first
non-boss encounter in the whole replica that isn't a walkover -- and the
**Phantasmal Gardener elite is 0%**, i.e. boss-tier, against Overgrowth's
Byrdonis at 95%. Four bodies each blocking 6 per turn is simply a
different kind of fight.

(That Cultist figure was recorded here as 52% when Underdocks first
landed and no longer reproduces; it is a stable 23/40 across fresh
processes now. Checked before assuming: disabling the new Thorns
retaliation entirely gives the identical 23/40, and Thorns is applied
zero times in that fight, so this session's change is not the cause. The
earlier number most likely predates a later fix that was never
re-measured.)

## Thorns
"When hit by an attack, deal X damage back." Intensity/Permanent per the
wiki.gg Buffs page. Added for Toadpole, and it also unblocked the
**Liquid Bronze** potion (Uncommon, gain 3 Thorns) and the **Bronze
Scales** relic (Common, start each combat with 3 Thorns), both of which
had been sitting in the excluded lists for exactly this reason.

It fires **once per hit**, which makes it the mirror image of Skittish
(once per card) — the two statuses landed one session apart and read
almost identically in plain English, so the distinction is worth stating
outright. Toadpole is its own proof: its 3-hit **Spike Spit** exists to
punish multi-hit attacks, which only means anything if each hit
retaliates separately. Verified: Twin Strike into 2 Thorns costs 4, and
Twin Strike + Strike costs 6.

One source conflict, resolved the same way as the co-op-revive one below.
A third-party site (spire-codex) calls Thorns a **Counter**, which would
mean stacks are spent per trigger; wiki.gg says **Intensity/Permanent**.
Toadpole settles it independently — its Spike Spit move explicitly
"removes 2 Thorns from self", which is only a meaningful cost if
triggering doesn't already spend them.

Three readings of "when hit" that were judgement calls, all deliberate:
- A **fully blocked** hit still retaliates. The wording is "when hit",
  not "when you lose HP" — contrast Slippery, which the wiki patched
  specifically so a fully-blocked hit spends no stack.
- A **killing** hit still retaliates; the attack landed before the
  defender died.
- Retaliation is **not itself an attack**, so it ignores
  Strength/Weak/Vulnerable and cannot bounce back off the attacker's own
  Thorns. That's what makes two Thorns creatures terminate instead of
  recursing.

Unverified, flagged rather than hidden: whether the attacker's **Block**
absorbs the retaliation. The STS2 wiki doesn't say. This replica says yes,
matching every other `source_is_attack=False` damage source it already has
(poison, Constrict, Kusarigama, Parrying Shield).

Mechanically this needed one real engine change: `Entity.take_damage()`
now takes an optional `attacker`, since it previously had no idea who was
swinging. It defaults to `None` = no retaliation, which is correct for
every non-creature damage source, so the ~70 existing call sites that
don't pass it stay right by construction. Card effects pass their caster,
enemy moves pass the enemy.

**A finding from wiring it up:** against `bench.py`'s policy a solo
Toadpole triggers Thorns **0.00 times per fight** — it dies in ~2 turns,
before its turn-2 Spiken ever resolves. The "Toadpoles (Weak)" pair
triggers it 2.35 times per fight for 4.7 damage, purely because the wiki
specifies the *front* Toadpole opens on Spiken instead of Whirl. That one
sourced detail is the only reason the mechanic does anything at all in
Act 1 against a fast deck — a good argument for porting encounter
specifics rather than just enemy stat blocks.

## Act 1 is complete: every elite and boss, both regions
All of Act 1's enemies are now ported — 50 encounters, up from 36.

**The region layout in this file was wrong and is now corrected.** Reading
the wiki's Elites and Bosses data modules (rather than the region module,
which only lists Normals and Minions) shows:

| | Overgrowth | Underdocks |
|---|---|---|
| **Elites** | Byrdonis, **Bygone Effigy**, **Phrog Parasite** | Phantasmal Gardener, **Skulking Colony**, **Terror Eel** |
| **Bosses** | Vantom, **Ceremonial Beast**, **The Kin** | **Lagavulin Matriarch**, **Soul Fysh**, **Waterfall Giant** |

Earlier notes had Ceremonial Beast filed as an elite and Phrog Parasite as
an ordinary monster. Both were wrong. Each region has **three** elites and
**three** bosses drawn from a pool, which `ACT1_ELITE_POOL` /
`ACT1_BOSS_POOL` in `play.py` now expose.

**Three enemies were deferred for statuses that don't exist.** Corpse Slug,
Fossil Stalker and Gremlin Merc were held back for "Ravenous", "Suck" and
"Surprise/Thievery". The raw Underdocks data module shows **none of those
appear in their movesets** — they are plain attackers, and the Merc's only
special behavior is summoning on death. That deferral came from a weaker
source, not from the data. A good argument for always going to the module.

### Mid-combat summoning
Six enemies needed it, and it was the single biggest blocker left in Act 1:
Gremlin Merc and Phrog Parasite (on death), Living Fog (Gas Bomb),
Two-Tailed Rat (itself), and Fogmog — whose **Illusory Spores move had been
silently cut** from its original port, so that enemy had been incomplete
without it being obvious.

Deaths now resolve *before* the victory check, or killing the last enemy
would end the fight and skip the reinforcements entirely.

**An invented rule, flagged as such:** Two-Tailed Rat's "Call for Backup"
summons another Two-Tailed Rat, which can call for backup itself. Nothing
in its text bounds that, so `CombatEngine.MAX_ENEMIES = 12` caps the board.
The real game must have some limit; 12 is this replica's guess.

**A bug this created, caught by testing:** minions abandon combat when
their leader dies (The Kin's Followers). Because `summon_enemy()` records
the summoner as the spawn's leader, running that cleanup *after* the death
effect meant Gremlin Merc's two gremlins were born already orphaned and
immediately swept up — the encounter ended the moment the Merc died.
Cleanup now runs before the death effect.

### New mechanics
| Mechanic | Source | Used by |
|---|---|---|
| **Vigor** | wiki Buffs page | Terror Eel |
| **Intangible** | wiki Buffs page | Soul Fysh |
| **Ringing** — "only 1 card this turn" | Ceremonial Beast's page | Ceremonial Beast |
| **Smoggy** — "only 1 Skill per turn" | Living Fog's page | Living Fog |
| **Steam Eruption** — charge counter | boss's own move text | Waterfall Giant |
| **Plow** — HP-threshold phase change | Ceremonial Beast's page | Ceremonial Beast |
| **STRENGTH_LOSS / DEXTERITY_LOSS** | — | Lagavulin's Soul Siphon |
| **Beckon** status card | Soul Fysh's page | Soul Fysh |
| Sleep/Stun, minion-flee, invulnerability | move text | several |

Ringing and Smoggy are enforced at `play_card`, so **auto-plays bypass
them** — Stampede and Hellraiser aren't the player choosing to play a card,
and both debuffs read as restrictions on the player's own actions.

Soul Siphon is why `STRENGTH_LOSS`/`DEXTERITY_LOSS` are permanent *positive*
counters that subtract: `add_status()` pops anything at ≤0, so a player
sitting at 0 Strength could never be pushed negative by `add_status(STRENGTH, -2)`.
Same trick Mangle already needed, now with a permanent variant.

Soul Fysh's Intangible quirk falls out for free. The wiki notes its first
Fade stack "fades instantly"; since it gains 2 during its own turn and
Intangible is Duration/Decremented, one expires at that turn's end and
exactly one protects it during the player's turn. No special case needed.

### Measured, with one big caveat
30 seeds, starter deck: **Bygone Effigy 0%, Phrog Parasite 0%, Ceremonial
Beast 0%, The Kin 0%, Lagavulin Matriarch 0%, Soul Fysh 0%**, Terror Eel
97%, Skulking Colony 100%. Underdocks' new normals are all 100%.

**Waterfall Giant measured 37%, and that number is an artifact of my own
guess.** The wiki lists its moves but not their order, and the cycle I
invented ends in About To Blow → Explode, which *kills the boss*. So a
player who simply survives 8 turns wins. The real boss almost certainly
gates that finale on something (low HP, a Steam threshold) rather than a
fixed turn count. Tracked as #38 — do not read 37% as a balance result.

## Content audits — cards, relics, potions
`content_audit.py` joins `enemy_audit.py`: hardcoded wiki name lists diffed
against what the modules actually build, exiting nonzero on a gap. Result:

| | Covered |
|---|---|
| Ironclad cards | **<!--ironclad_cards-->91<!--/-->/91** |
| Potions (in scope) | **<!--potions-->52<!--/-->/52** |
| Relics (in scope) | **81/81** |

**The card and potion counts were confirmed, not corrected.** Cards had
been assembled from a *union of two lossy extractions*; a third independent
read of the same module dropped three more entries, which is the strongest
argument yet that any single read of that page is a lower bound. Potions
matched the `Module:Potions/StS2_data` list exactly.

**Relics were not fine.** The audit found **13 missing**, and every one of
them was on this file's "deliberately excluded" list — written when the
engine genuinely couldn't express them, and never revisited as the engine
grew. Eleven were ported in an afternoon using machinery built for other
things:

| Relic | Was excluded for | Now uses |
|---|---|---|
| Mummified Hand | "turn-scoped cost override on an existing deck card" | `set_temp_cost` (built for Snecko Oil) |
| Razor Tooth | "depends on knowing what a card did" | `upgrade_for_combat` (built for Aggression) |
| Paper Phrog | "damage-by-card-name pipeline" | `vulnerable_damage_bonus` (built for Cruelty) |
| Unsettling Lamp | same | the `status_applied` hook (built for Vicious) |
| Shuriken | — | `_register_every_n_per_turn`, which already existed |
| Strike Dummy, Miniature Cannon | "by-card-name pipeline" | a new per-card damage bonus |
| Red Skull, Sturdy Clamp, Ice Cream, Gambling Chip | four different reasons | one small Player field each |

Only **Lucky Fysh** and **The Courier** stayed out, both pure gold/shop.

**A real bug fell out of Paper Phrog.** Its text — "enemies with Vulnerable
take 75% more damage rather than 50%" — is unambiguous that the bonus is
**additive** with Vulnerable's own 50%. The Cruelty card had been
implemented as a second multiplier on top (1.5 × 1.25 = 1.875 instead of
1.75), which nothing else would have caught, because Cruelty's own wording
("an additional 25% damage") is ambiguous on its own. Both now feed a
single `vulnerable_bonus` parameter on `damage_multiplier_for_defender`.

**The scope filter needed correcting too.** My first pass excluded 18
relics as "navigation"; checking each one's actual Description rather than
guessing from the name showed that Mango, Pear, Strawberry, Meat on the
Bone and Potion Belt are all combat effects (Max HP, end-of-combat heal,
potion slots) and were already ported. The real navigation set is 15.

The standing lesson, now demonstrated three times: **an exclusion note
records the engine at the moment it was written, and stops being true
without anyone editing it.** Cruelty and Colossus, then Thorns unblocking
Bronze Scales, now eleven relics at once.

## Statuses verified against the powers modules
`Module:Powers/StS2_data` is the aggregator for status definitions, and it
has **eight** submodules — `Common` (shared buffs, plus buffs from relics,
potions and colorless cards), one per class, `Enemy` (enemy starting powers
and intents), and `Debuff` (all debuffs). Reading the two that apply here
settled every status this replica models, and corrected three.

**Regen and Ritual were firing at the wrong end of the turn.** Both are
defined as END of turn — Regen "at the end of your turn, heal X HP, then
reduce Regen by 1", Ritual "at the end of its turn, gains X Strength" — and
both were implemented as start-of-turn ticks from an earlier reading of the
summary Buffs page. Poison genuinely *is* start-of-turn ("at the start of
its turn, loses X HP"), which is probably how all three ended up together.
Fixed: `tick_start_of_turn()` now holds Poison alone, and
`apply_end_of_turn_gains()` covers Metallicize/Plating block, then Regen,
then Ritual.

**Shrink lasted the wrong number of turns.** This file previously noted a
"minor duration conflict" between sources and guessed ~2 turns; Shrinker
Beetle applied 1 stack. The module settles it: "Attacks deal 30% less
damage. Removed when the applier dies / after **3** turns." Now applied as
3, and its stack type changed from Nonstacking to Duration so the count can
mean turns remaining. The removed-when-the-applier-dies half is *not*
modeled — nothing tracks which entity applied a given status — and is
flagged in the code rather than silently skipped.

**Tangled is finally wired.** "Attacks cost an additional energy for 2
turns" had a StatusType and no effect since early in the project, waiting
on exactly the dynamic-cost system that #35 built. Applied before the
zero-cost overrides, so a genuinely free Attack stays free.

Everything else checked out unchanged: Vulnerable, Weak, Frail, Poison,
Constrict, Ringing, Smoggy, Hex, Tender, Chains of Binding, Thorns, Vigor,
Intangible, Buffer, Artifact, Plating, Strength and Dexterity all match
their module text exactly.

**Still undocumented after all that:** `Downgraded` appears in no powers
module, so "cards resolve as their un-upgraded printing" remains the least
invented reading, marked as a guess in `make_knight_gang`. `Sandpit`,
`Slippery`, `Skittish`, `Soar`, `Flutter`, `Burrowed` and `Plow` are also
absent from these modules — they were sourced from individual enemy pages,
which for `Slippery`/`Skittish` was already noted as third-party-grade
sourcing.

**Balance impact of the timing fixes** (30 seeds): Cultist pair 58% → 53%,
Calcified Cultist and Shrinker Beetle unchanged at 100%, and Act 3's
Devoted Sculptor — 9 Ritual, the biggest Ritual user in the game — at 0%.
Small and in the expected direction: Ritual paying out at end of turn means
an enemy's first buffed attack lands a turn earlier than it used to.

## Every enemy in the game is ported
All three acts, all four regions, **<!--enemies-->106<!--/--> of <!--enemies-->106<!--/--> enemies** — <!--encounters-->93<!--/--> encounters.

| Region | Normals + minions | Elites | Bosses |
|---|---|---|---|
| Act 1 Overgrowth | 22 | 3 | 4 units |
| Act 1 Underdocks | 16 | 3 | 3 |
| Act 2 Hive | 18 | 3 | 4 units |
| Act 3 Glory | 16 | 5 units | 5 units |
| Event-only | 4 | — | — |

**Act 1 is the only act with two regions.** The Acts page settles it, and
the wording matters: alternate regions are "currently only implemented for
Act 1", so this is a shipping state, not a design rule — a later patch
could add a second Hive or Glory.

`enemy_audit.py` is the proof: it lists every name from the data modules
and diffs against what `enemies.py` builds. Re-run it after adding anything.
The only "built but not on a module list" entry is **Hatchling**, which the
wiki describes inside Tough Egg's Hatch text.

### Two things a completeness check caught that a region-by-region sweep missed
**There is a seventh enemy module.** `Module:Enemies/StS2_data/Events`
holds event-only enemies (The Merchant???, Battle Friend V1/V2/V3). It is
referenced by the main aggregator module but by no region page, so walking
the four regions never reaches it. Found by reading the aggregator's own
list of submodules — the lesson being that the index page is a better
starting point than the pages it indexes.

**`Module:Powers/StS2_data/Enemy` is where enemy PASSIVE powers live**,
separate from movesets. Not finding it caused four real errors:

| Power | What this file said | What the module says |
|---|---|---|
| **Steam Eruption** | a charge the Waterfall Giant spends on its own Explode | "When killed, deals X damage at the end of your next turn" |
| **Ravenous / Suck** | "don't appear in Corpse Slug's or Fossil Stalker's movesets — the deferral came from a worse source" | real passive powers, just not moves |
| **Reattach** | Decimillipede revives instantly | "revives in **2 turns**" |
| **Flutter** | wears off after X hits | "Deal attack damage X times to **Stun** it" |
| **Personal Hive** | undocumented, left unimplemented | "Whenever this enemy is hit by an Attack, add X Dazed into your Draw Pile" |

The Steam Eruption one was the expensive mistake. Reading it as a
self-destruct timer made me invent an About To Blow → Explode finale that
killed the boss on turn 8, so **Waterfall Giant benchmarked at 37% while
every other Act 1 boss sat at 0%** — a number this file already flagged as
"an artifact of my own guess". With the real power it is a posthumous bomb,
the invented finale is gone, and the boss now measures **0%**, in line with
its peers. The earlier flag was right; the fix was in a module I hadn't
found.

The Ravenous/Suck correction is the one worth remembering: I had been
confident enough to *write down* that those statuses didn't exist in those
enemies' data. They did — in a different module, as passives rather than
moves. "Not in the moveset" was true and also the wrong question.

## Act 3 — Glory
One region, like the Hive. Its distinguishing feature is **standing rules
that last only while a specific enemy lives**, which nothing earlier had.

| Status | Effect | From |
|---|---|---|
| **Soar** | 50% less attack damage until it lands | Owl Magistrate |
| **Hex** | All your cards are Ethereal — the hand *exhausts* at end of turn | Spectral Knight |
| **Downgraded** | Cards resolve as their un-upgraded printing | Magi Knight |
| **Bound** | Only 1 Bound card playable per turn | Queen |

**Soar is the mirror of Act 2's Flutter and reads better for it.** Flutter
spends a stack per hit, so you punch through it; Soar spends nothing and
ends only when the Magistrate itself lands — its Verdict, which is also its
biggest attack. One rewards hitting, the other rewards waiting.

**Hex turns out to *be* Ethereal.** The wiki's Debuffs page defines Hex as
"while Spectral Knight is alive, ALL your cards are Ethereal", so it is
implemented as the hand exhausting instead of discarding — routed through
`exhaust_card()` so exhaust counters and Dark Embrace-style listeners stay
correct. Both Hex and Downgraded clear when their knight dies.

**Bound is a per-card affliction, not a player status**, because "only one
Bound card can be played each turn" has to hold no matter how many you are
holding — so the flag lives on the `Card` and is cleared at end of turn.

**Test Subject is the first multi-phase boss:** three separate HP pools
(100 → 200 → 300) with "Adaptable" reviving it into the next phase instead
of dying. Phase 2 adds Painful Stabs (a Wound to your discard on unblocked
damage) and a Multi-Claw that gains a hit every use; only phase 3 can be
killed for good. **Aeonglass** escalates from both directions at once — its
Nth Increasing Intensity shuffles a `Wither+N` into your deck *and* grants
2+N Strength.

**Guardbot** is the first enemy that buffs another enemy by name, giving
its Block to the Fabricator (falling back to its leader, then any living
ally, so it still does something if the Fabricator is already dead).

**One uncertainty flagged rather than guessed:** the wiki names Glory's
bosses as Queen, Test Subject and Aeonglass, but the Bosses module also
carries **Doormaker** (489 HP, a rotating Hunger/Scrutiny/Grasp buff). It
is ported standalone; whether it is a fourth boss or a transformation of
another one is unresolved. **Downgraded**'s exact effect is also
undocumented anywhere — "resolves as the un-upgraded printing" is the least
invented reading of the word, and it is marked as such in the code.

## Act 2 — The Hive
Act 2 is a **single** region (Act 1's two-region split is not repeated), and
it is fully ported: **22 new encounters**, taking the total to 72. All 16
normals, both minions, the 3 elites and all 3 bosses. Construct the engine
with `act="act2"` so multiplayer scaling picks up the 1.2 act multiplier.

New mechanics, all sourced from individual enemy pages because **none of
them are on the wiki's Buffs page**:

| Status | Effect | From |
|---|---|---|
| **Tender** | "Whenever you play a card, lose X Strength and X Dexterity this turn" | Hunter Killer |
| **Burrowed** | Block is *not* cleared at the start of the holder's turn | Tunneler |
| **Flutter** | Takes 50% less Attack damage; each hit spends a stack | Thieving Hopper |
| **Sandpit** | "In X turns you will be eaten and die" — a countdown, not damage | The Insatiable |

Tender is the most interesting addition because it punishes a shape of play
nothing in Act 1 touched: the penalty compounds *per card*, so a wide turn
is actively worse than a narrow one. Sandpit is the first effect in the
replica that kills outright regardless of HP — the `Frantic Escape` status
card it comes with is the way out, and it gets more expensive every time
you play it.

Two enemies needed structures that didn't exist: **Tough Egg** hatches into
a Hatchling (modeled as the egg dying and summoning its replacement, which
means AOE that kills the egg first denies the hatch), and **Decimillipede**
fights as three segments that *revive at 25 HP* unless they all die close
together. **The Obscura**'s Wail is the first move that buffs the enemy's
own whole side.

**A real bug this batch surfaced, unrelated to Act 2.** Myte's "adds 2 Toxic
to your Hand" did nothing, because `start_turn()` discarded the hand at the
*start* of the player's turn — throwing away anything an enemy had put
there during its own turn. The discard now happens in `end_turn()`, matching
the real sequence (discard → enemies act → draw), and the
"if this is in your Hand at end of turn" cards resolve before it. Every
future effect of that shape would have silently done nothing too.

**Two documented holes, left open rather than guessed:** Entomancer's
"Personal Hive" (#40) and Knowledge Demon's "each player chooses one of two
debuffs", which has no UI hook — the same wall the Gambling Chip relic hit
— and auto-picks Weak.

Act 3 (Glory) is the remaining half of this work, with its research already
gathered — see task #29.

## Finishing the potions
All **<!--potions-->52<!--/-->** Ironclad-relevant potions are ported — 48 in the reward pool and
4 Special-tier ones held outside it (`Potion-Shaped Rock`, `Ambergris`,
`Foul Potion`, `Glowwater Potion`), matching how the real game gates them.

**Most of the 22 that were left had been blocked on the same hazard**, and
the fix for it already existed by the time this batch ran. `start_combat()`
copies the deck *list*, not the `Card` objects, so a card in hand IS the
object in `deck_template` — writing `card.cost = 0` or `card.upgrade()` on
it silently persists for the entire run. That one trap had deferred
`Blessing of the Forge`, `Touch of Insanity` and `Snecko Oil`.
`Player.upgrade_for_combat()` (built while porting Aggression, which also
fixed a live Armaments bug) plus new `set_temp_cost()` / `grant_replay()`
helpers make all of them reversible, each reverting at the right boundary:

| Helper | Scope | Used by |
|---|---|---|
| `upgrade_for_combat` | combat | Blessing of the Forge, Armaments, Aggression |
| `set_temp_cost(scope="combat")` | combat | Touch of Insanity |
| `set_temp_cost(scope="turn")` | turn | Snecko Oil, Liquid Memories |
| `grant_replay` | combat | Soldier's Stew |

**Ambergris ("take an extra turn") needed no driver changes.** Every driver
— `play.py`, `env.py`, `bench.py` — already loops start → end → enemy turn,
so `run_enemy_turn()` consuming the charge and returning early gives a real
extra turn without any of them knowing the mechanic exists.

Also new: **Buffer** (Lucky Tonic), **retain hand** (Stable Serum),
`next_attack_multiplier` for Gigantification's triple (the existing
`next_attack_double` relic field couldn't express it), and Duplicator's
any-card replay, which shares One-Two Punch's re-entrancy guard so the
three replay sources can't chain into each other.

**Beetle Juice reuses Shrink.** "Enemy's attacks deal 30% less damage for
4 turns" is mechanically identical to the Shrink debuff already modeled as
a flat 0.7 outgoing multiplier, so it applies Shrink with a 4-turn duration
rather than adding a second status with identical numbers. Two names, one
mechanic — recorded because the conflation is deliberate.

### A partial Colorless pool came with it
*(Superseded — the module is complete now; see the next section. Kept for
the history.)* `Colorless Potion` ("choose 1 of 3 random Colorless cards")
needed something real to draw from, so **22 Colorless cards** went into
`cards.COLORLESS_POOL` — the slice needing zero new engine features
(Ultimate Strike/Defend, Finesse, Dark Shackles, Shockwave, Mind Blast,
Rend, Caltrops, Entrench, Beat Down, Catastrophe and more). `Caltrops` is a
one-liner now that Thorns exists, and `Rend` reads the `DEBUFF_STATUSES`
set Artifact introduced, so it stays correct as new debuffs land instead of
carrying a hardcoded list.

That was a deliberate slice, not the whole thing. It is now finished — see
below.

## The Colorless module is complete (#39)
The module has **<!--colorless_module-->151<!--/--> entries**, not the "200+" this README used to claim.
That number was a guess printed next to an unverifiable coverage line;
`content_audit.py` now carries the full <!--colorless_module-->151<!--/-->-name ledger and fails if
anything drifts:

```
module entries : <!--colorless_module-->151<!--/-->
ported         : <!--colorless_ported-->135<!--/-->
excluded       :  16  (quest / other-class / placeholder)
```

**103 new cards** went in: 69 more into `COLORLESS_POOL` (now <!--colorless_pool-->91<!--/-->), plus
`ANCIENT_COLORLESS` (<!--ancient_colorless-->9<!--/-->), `CURSE_POOL` (<!--curses-->18<!--/-->) and 7 new Status cards.

### What is excluded, and why
Recorded rather than silently dropped, because an exclusion list is the
thing most likely to go stale (it has three times already in this project):

- **Quest cards** (Byrdonis Egg, Lantern Key, Spoils Map, Dowsing) — map
  items with no combat text whatsoever.
- **Other characters' tokens** (Shiv, Soul, Fuel, Luminesce, Sovereign
  Blade, the three Minion cards) and **Splash** ("an Attack from another
  character"). Ironclad-only is a permanent scope decision. **Sweeping
  Gaze** belongs with them and was *wrongly listed as in-scope in #39's own
  description*: its text is "Osty deals X damage", and Osty is another
  character's companion.
- **Mad Science** itself, whose only text points at the Tinker Time event.
  Its **nine customised printings** all have real, self-contained combat
  text, so those *are* ported.
- **Wither (Upgraded)**, a NoList duplicate of the already-ported Wither.

Gold clauses are dropped and the combat half kept, noted on the cards
themselves: Hand of Greed loses "if Fatal, gain 20 Gold", Debt loses "lose
10 Gold".

### Two new card keywords
**Retain** ("not discarded at the end of your turn") and **Ethereal** ("if
this is in your Hand at end of turn, Exhaust it") are now per-card, joining
the hand-wide versions that already existed (Stable Serum/Equilibrium for
Retain, Hex for Ethereal). All four now meet at a single loop in
`Player.end_turn`, with one rule worth stating: **Ethereal outranks
Retain.** A retained hand still loses its Ethereal cards — that is exactly
what stops Apparition and Void from jamming the hand forever.

Both keywords needed a second flag, in opposite directions. Four cards
(Anointed, Gold Axe, Scrawl, Wish) print Retain *only when upgraded*, like
the existing `innate_on_upgrade`. Apparition is the mirror: it prints
Ethereal on the **base** side and **loses** it on upgrade, so it needed
`loses_ethereal_on_upgrade` instead.

**Eternal** is recorded from the data and deliberately inert. It means
"cannot be removed from your Deck", and deck editing happens at shops and
rest sites — map features, out of scope. Same for Guilty's "removed after 5
combats". The flags are kept so the card data stays true and is already
right if deck editing ever lands.

### Four bugs the new test suite caught
`test_colorless.py` (100+ assertions) found these, all real:

1. **`UNPLAYABLE` was a big cost, not a keyword.** The sentinel is `999`, so
   a player with 999 energy could cast Wound. Reachable in this codebase —
   the test harnesses routinely hand out 99+ energy, and Brightest Flame,
   Production and Restlessness all add more. Now gated on `is_unplayable()`.
2. **Mind Rot and Waste Away stopped working after one turn.** Both say
   "each turn", but they only scanned the *hand* — and a Status card is
   discarded at end of turn like anything else, so the penalty fired once
   and quietly died. Now scans the whole deck; Exhausting the card, the
   real way out, still ends it.
3. **Rebound bounced itself.** "Put the next card you play this turn on top
   of your Draw Pile" armed a flag that `play_card` then consumed at
   Rebound's *own* disposal step. It now stores the card that armed it.
   Worse, the flag was initialised to `False` while the check tested
   `is not None`, so *the first card played in every combat* went to the
   draw pile — a bug that reached far outside Colorless and was caught by
   the pre-existing `audit.py`, not by the new tests.
4. **Doubt and Shame did nothing.** Both apply a 1-stack debuff at end of
   turn, but the hand-penalty pass runs *before*
   `decay_statuses_end_of_turn`, which decremented it straight back to zero.
   Status-applying penalties are now queued and applied after decay.

### Deliberate modelling choices
- **"Choose 1 of 3"** *was* a random pick. It is now a real choice —
  see "The card-choice interface" below.
- **Transform** (Entropy) is combat-scoped, like Primal Force: the
  replacement lives in hand only and `deck_template` is never touched, so
  the original returns next fight.
- **Apotheosis** upgrades through `upgrade_for_combat`, not `card.upgrade()`
   — the latter would permanently upgrade the entire deck for the rest of
  the run, which is the exact bug Armaments once had.
- **Outmaneuver's `@SE`** and **Disintegration's "6/7/8"** were both flagged
  as unverified readings. Both have since been chased down — see below.

## Porting the last 21 cards
The Ironclad is now **complete: all <!--ironclad_cards-->91<!--/--> cards** in the wiki's
`Module:Cards/StS2_data/Ironclad`. <!--ironclad_pool-->86<!--/--> sit in the reward pool, 3 are the
Basic starters, and the 2 Ancient cards (`Break`, `Corruption`) are held in
a separate `ANCIENT_CARDS_IRONCLAD` list — Ancient isn't a normal reward
tier in the real game, and folding them into the pool would dilute every
ordinary card drop.

**Pinning down the denominator was its own problem.** Two independent
extractions of the same wiki data module disagreed: one silently dropped
`Bloodletting`, the other dropped `Midnight`. Neither was wrong about what
it *did* list, so the real card list is the **union** of the two, and the
"90-card sheet" figure quoted elsewhere in this file was one card short.
Any future count that disagrees is more likely a lossy extraction than new
game data.

These 21 cards had all been deferred for named missing features, so this
was mostly engine work:

| Feature built | Cards it unblocked |
|---|---|
| `Card.dynamic_cost` + `current_cost(player)` | Stomp, Midnight, Unrelenting, Corruption |
| `Innate` keyword (draw-pile reorder) | Aggression+, Juggling+ |
| `engine.auto_play_card()` + `turn_end` event | Stampede, Howl from Beyond, Hellraiser |
| Per-card `card_drawn` event | Hellraiser |
| Applier-side `status_applied` event | Vicious |
| `attacker` in the damage pipeline | Cruelty, Colossus |
| `STRENGTH_LOSS_THIS_TURN` | Mangle |
| `THORNS_THIS_TURN` | Flame Barrier |
| Hand-scoped card transformation | Primal Force (+ the `Giant Rock` token) |
| Replay-next-card counter | One-Two Punch |

Two of those deserve specific mention because the README had previously
written them off as too risky:

- **Cruelty and Colossus** were both filed as "core-pipeline change, high
  regression risk" — they need to know the *other* party's Vulnerable
  status mid-attack. The `attacker` parameter added for Thorns made them
  two guarded multipliers in `take_damage()` that no-op whenever nobody has
  the Power. The feared rewrite never materialised; the earlier assessment
  was correct *at the time* and simply stopped being true.
- **Mangle** was blocked because `add_status()` pops any status at ≤0, so a
  temporary *negative* Strength couldn't sit on an existing positive one.
  Solved by storing the loss as a positive counter that subtracts, rather
  than fighting the pop rule.

**A real bug this surfaced, unrelated to the new cards.** Aggression
upgrades a card it pulls from the discard pile, which is how it came out
that **Armaments had been permanently upgrading cards for the entire run**.
`start_combat()` copies the deck *list*, not the `Card` objects, so a card
in hand is the same object that lives in `deck_template` — `card.upgrade()`
on it never wore off. Both now go through `Player.upgrade_for_combat()`,
which records the change and reverts it at combat end. The shallow-copy
trap was already documented as the reason several *potions* were deferred;
nobody had noticed the cards already in the game were falling into it.

**Two readings worth flagging as judgement calls**, both documented at
their implementation:
- **Howl from Beyond** ("at the end of your turn, if this is in your
  Exhaust Pile, play it") has no printed Exhaust, so it only reaches the
  exhaust pile via another card. It is implemented as recurring — playing
  it from the exhaust pile doesn't remove it, so it fires every turn
  thereafter. That's the only reading under which the second sentence does
  anything.
- **Unrelenting**'s free Attack is deliberately *not* turn-scoped; the card
  sets no turn limit, so the flag survives until an Attack consumes it.

Auto-plays are depth-capped at 5. Hellraiser can genuinely chain — a drawn
Pommel Strike draws more cards, which may be more Strikes — and while that
terminates on its own once the deck runs dry, the cap turns a pathological
deck into a bounded no-op instead of a stack overflow.

Gauntlet clear rate with the 19 new pool cards: **8/40 (20%)**, which is
squarely inside the 15–22% band that #37 documents as pool-reshuffle noise.
Read it as "no detectable change", not as a balance result.

## Measured difficulty (bench.py)
`bench.py` now measures **combat**, and the gauntlet is opt-in.

**Part A is the headline.** Every one of the <!--encounters-->93<!--/--> encounters runs
independently from a seeded deck with no reward stream, grouped by
region and by normal/elite/boss, with the raw win count shown next to the
percentage so the sample size is never hidden.

**Part B (the gauntlet) is behind `--gauntlet` and prints a warning.** It
bundles reward luck into the result: adding two items to the reward pools
once moved its clear rate from 6/40 to 9/40 by reshuffling later draws
alone, and three values recorded across sessions — 18%, 15%, 22% — were one
result inside the noise. Reward pacing is also this replica's own invention
rather than the game's, so its number is not a balance finding.

### The "flat curve" was the summary statistic, not the content (#36)
For a while this README reported a difficulty curve of **100 / 100 / 100 /
50** and called Acts 1–2 walkovers. That number was median win rate, and the
median was the wrong statistic. Normals inside a region are **bimodal** — a
cluster of trivial fights and a cluster of real ones — so the median just
reports whichever cluster holds more than half the encounters. Act 2's Hive
has 8 of 16 normals at 100%; the median duly says 100% while the mean says
62.8%.

Holding the deck fixed at the 10-card starter deck for *every* fight, the
mean descends cleanly and always did:

```
region                 n   fixed-deck win   HP lost   ladder win
Act 1  Overgrowth     23         100.0%      10.1       100.0%
Act 1  Underdocks     15          96.7%      14.0        96.7%
Act 2  Hive           16          62.8%      22.9        82.8%
Act 3  Glory          10          21.5%      38.4        54.8%
```

Three lessons are now baked into `bench.py`:

**Report the mean, and show both.** Group blocks print mean *and* median
side by side. Where they disagree the distribution is bimodal, and that is
itself worth seeing.

**Win rate saturates; HP lost does not.** Every Act 1 Overgrowth normal is
40/40 — 920 runs, zero losses. Win rate cannot distinguish a Twig Slime from
a Mawler because both are 100%. Average HP lost separates them instantly (0
vs 29) and yields a monotone curve across all four regions. It is measured
over wins only: counting losses would score every death as "80 lost" and
collapse the metric back into the win rate it exists to complement.

**Measure each fight twice.** `fixed` uses the starter deck for everything —
one yardstick, so it measures how the *content* scales. `ladder` sizes the
deck to where the fight sits in a run — so it measures what a player
plausibly *experiences*. Both are printed because they answer different
questions and previously only one existed.

### The Act 1 elite/boss "0%" was a measurement bug
`DECK_TIERS` was keyed on the **act alone**, which meant an Act 1 *boss* was
fought with the Act 1 *starter deck*. That is a fight no player ever has —
anyone reaching Vantom has ~8 fights of rewards behind them — and it
reported all three Act 1 bosses plus two Act 1 elites as flat 0%,
indistinguishable from Act 3 bosses. That was the "oddity" #36 was opened to
explain, and it was entirely manufactured.

`DECK_TIERS` is now a six-rung **run-progress ladder** and `DECK_TIER_FOR`
keys on `(region, normal/elite/boss)`, since within an act you clear normals
first, then an elite, then the boss. The affected fights, before → after:

| encounter | act-keyed | ladder |
|---|---|---|
| Bygone Effigy (Elite) | 0% | 50% |
| Phrog Parasite (Elite) | 0% | 65% |
| Vantom (Boss) | 0% | 25% |
| Ceremonial Beast (Boss) | 0% | 22% |
| The Kin (Boss) | 0% | 18% |

None were mis-ported. **Both tables are still invented** — the real game has
no such thing — but a monotone run-progress ladder is far more defensible
than one step per act, and the rungs are printed in the output so the
assumption travels with the numbers.

Byrdonis, incidentally, was never the anomaly. It is simply the softest Act
1 elite — 95% on a bare starter deck. The other two were being measured
wrong.

### Nothing is unwinnable; the remaining 0%s are the policy
The fights that stayed near 0% even on the top rung were re-run with a
deliberately absurd loadout (250 HP, 6 energy, 40 cards all upgraded, 11
relics). All 13 became winnable — 12 at 100%, The Insatiable at 55% — with
zero timeouts. So no encounter is ported into unwinnability, and every
remaining 0% is `greedy_policy` failing to plan, not broken data.

This is the shape to expect, and it should stop reading as a bug: a scripted
heuristic that plays the largest single attack each turn, never builds a
synergy and never sequences a setup, loses to Act 2/3 bosses. Beating those
is what an actual trained agent is *for* — a benchmark policy that already
cleared them would leave no headroom to measure.

Two caveats that still hold. `greedy_policy` evaluates cards by
string-matching their description, so these are RELATIVE signals. And an
earlier version of this harness collected potions but never drank them,
reporting 0% clears — a measurement gap that looked exactly like a
difficulty result.

### A crash the investigation turned up
Probing with a 40-card all-upgraded deck made `Cascade` draw and play far
more cards than any normal run, which exposed a latent bug in `fx_havoc` and
`fx_cascade`: both built an auto-target of `None` when the drawn card needed
a living enemy and the board was already empty, then resolved it anyway.
`fx_spite` dereferences `target.alive` on its first line, so this was a hard
`AttributeError`, not a fizzle. `CombatEngine.auto_play_card` had guarded
this case correctly all along — these two were the outliers. Both now share
a `_auto_target_for` helper that refuses to resolve, and Cascade stops
drawing rather than milling the rest of its X for nothing.

## Two flagged readings, chased down (#47)
The Colorless port left two numbers marked "assumed, not verified". Both are
now resolved — one confirmed, one proven unresolvable.

### `@SE` is Energy — confirmed
`Module:Keywords/StS2_data/Icons` defines every `@XX` code. `@SE` is
**"Energy (Silent) — the Silent's Energy orb. Energy is a resource used to
play cards."** So Outmaneuver grants plain Energy, exactly as implemented.

The oddity is *which icon*: every other Colorless card writes energy as
`@CE` ("the generic Energy icon found on all Colorless cards"). Outmaneuver
is a Silent card in STS1, so this looks like a transcription slip in the
wiki data rather than a real distinction — there is no separate
Silent-energy resource, both codes resolve to Energy.

### Disintegration's "6/7/8" cannot be resolved, and now I know why
Not for lack of looking. Three findings, each independently sufficient:

1. **It is not Ascension notation.** STS2 ascension scaling is written
   `{{Asc|9|21|2}}` — see the Fabricator in
   `Module:Enemies/StS2_data/Glory`. And `6/7/8` appears **nowhere else in
   any card, power, keyword or enemy module**. It is a one-off with no
   convention behind it, which kills the "probably act-scaled" guess that
   was recorded as the likely reading.
2. **Nothing creates the card.** "Disintegration" occurs in exactly one
   place in the entire wiki: its own entry in the Colorless module. No
   card, relic, potion, event or enemy power grants it. (The Fabricator has
   a move called *Disintegrate*, but that is a plain 11-damage attack and is
   unrelated.) So there is no in-game context to read the number against.
3. **It has no page of its own**, so there is no prose to check either.

It stays at 6, the lowest value — which is inert in practice, because no
enemy here generates it either. That mirrors the data exactly, and it stays
in `STATUS_CARDS` so the <!--colorless_module-->151<!--/-->-entry Colorless ledger remains complete.

**The useful part is the negative result:** the guess in the code (act
scaling) was wrong to state as likely, and the reason is now on the card
rather than in a task nobody will re-open.

## The <!--hand_limit-->10<!--/-->-card hand limit (#46)
Nothing enforced a hand cap anywhere. Retain could hold an arbitrarily large
hand across turns, and all 29 "add a card to your Hand" effects appended
directly — Calamity, Hello World, Jackpot, Dual Wield, Metamorphosis, and
every enemy that shuffles a Status in.

**Sourced, not assumed.** The wiki's Mechanics page: *"The maximum number of
cards allowed in hand is 10. There is no way to exceed this limit."* Two
caveats recorded on `entities.HAND_LIMIT`:

- That Mechanics page is the **STS1** one — the wiki has no STS2 equivalent
  — so this is an STS1 rule applied to an STS2 replica.
- The page contradicts itself on where overflow goes: drawn excess to the
  **discard** pile, created excess to the **draw** pile. That second half is
  contradicted by eight individual card pages (Blade Dance, Cloak and
  Dagger, Deus Ex Machina, Dual Wield, Nightmare, Power Through, Hello
  World, Magnetism), each saying *"it gets added to the discard pile"*.
  Eight specific pages beat one general clause, so everything overflows to
  the discard pile here.

All 29 sites now go through `Player.add_to_hand()`; `test_handcap.py`
greps the source to assert no direct `hand.append` survives outside
`entities.py`. `env.MAX_HAND` and Scrawl's local `HAND_SIZE = 10` both now
read the shared constant instead of restating it.

### It broke Havoc, and that was the interesting part
Havoc and Cascade were implemented as "draw 1, then play the card off the
top of your hand" — reusing `draw_cards` for its reshuffle logic. With a cap
in place, a **full hand turned both into no-ops**: the draw overflowed to
the discard pile, hand size didn't change, and their "did I draw anything?"
check read that as an empty deck.

The real rule is that those cards play the top of your draw pile *without it
ever entering your hand*, so the limit should never have applied. They now
use a new `Player.take_top_of_draw()`, which also means they no longer fire
`card_drawn` or count toward "cards drawn" — correct, since they are not
draws. Mayhem uses it too, and picked up reshuffle handling it never had.

### The balance effect is ~nil, and that is itself the finding
On a deck built specifically around Retain and card generators (120 seeds ×
8 encounters), enforcing the cap costs **−0.2pp** — noise. The cap is
genuinely binding: with it disabled the same runs reach **16-card hands**.
It just doesn't matter, because `greedy_policy` is limited by **energy**,
not by cards. Three energy a turn means the 11th through 16th cards were
dead weight either way.

It still matters for correctness, and for the handful of effects that
actually *read* hand size (Regret's "lose 1 HP for each card in your Hand"
gets weaker; the relic that grants Block equal to hand size gets capped) —
and it would matter a great deal to a policy that could exploit a big hand.

## The card-choice interface (#45)
Thirteen cards say **choose**, not *random* — Armaments, Headbutt, True
Grit+, Purity, Dual Wield, Thinking Ahead, Neow's Fury, Wish, Seeker Strike,
Stratagem, Discovery, Abundance, Entropy — and every one of them was
resolving with `rng.choice` or "just take the first", because this replica
had no way to ask.

All thirteen now go through `CombatEngine.request_choice(player, options,
prompt, kind)`. Drivers install `engine.choice_resolver`:

- **`play.py`** prompts at the terminal, listing each option with its cost
  and text. A human was previously getting coin flips.
- **`bench.py`** scores the options (see below).
- **`env.py`** installs nothing, so it keeps the random default. Its action
  space cannot express a mid-effect decision — that would need resumable
  card effects *and* the options encoded in the observation, which is a far
  bigger change than a resolver.

Cards whose text says **random** were deliberately left alone: Cinder,
Thrash, Stampede, Aggression, Beat Down, Catastrophe, Stoke, Infernal Blade,
Hidden Gem, Jack of All Trades, Alchemize, Jackpot, Metamorphosis,
Distraction, Mayhem and every "random enemy". That randomness *is* the card.
`test_choice.py` asserts both directions — each choose-card asks, each
random-card doesn't.

### Being greedy everywhere was worse than random
The obvious resolver — always take the best card, always throw away the
worst — **lost 4pp of win rate**. Measured over 1920 runs per arm (160 seeds
× 12 non-saturated encounters, decks built around the choice cards):

```
random, i.e. no resolver          50.21%
greedy on GAIN prompts only       52.45%   (+2.24)
greedy on EVERY prompt            49.48%   (-0.73)
```

So `bench.greedy_choice` is greedy **only** on prompts that add a card to
your side (tutors, Dual Wield's copy, Headbutt's recovery) and defers to
random on the rest. That is an empirical result, not a preference.

Two things worth keeping straight. First, this is tuned to *the benchmark's
own policy*, not to correct play: a human would obviously upgrade their
biggest card, but greedy `upgrade` measured slightly negative because
`greedy_policy` cannot exploit it — which is why `play.py` asks the human
instead. Second, chasing the 4pp down found a **real bug**, not just a bad
weight: Headbutt and Thinking Ahead had both been filed under the kind
`to_draw_top`, but Headbutt *recovers* a card from the discard pile (you
want the best) while Thinking Ahead *sheds* one from your hand (you want the
worst). One label, two opposite preferences — a resolver had to be wrong for
one of them. Thinking Ahead is now `stash`.

### It barely moves the headline benchmark, and that means nothing
The main curve shifted by ≤0.5pp. That is expected and uninformative: the
fixed-deck column is Strike/Defend/Bash, which contains no choice cards at
all, and the ladder column draws 13 choice cards from a 186-card pool, so
most runs never see one. Measuring the effect required decks built *around*
those cards — which is the general lesson, since an aggregate that cannot
contain the thing you changed cannot measure it.

## Elite/boss-triggered relics + card rarity
Three relics that had been sitting in the known-gaps list are now in:

- **Book of Five Rings** ("Every 5 cards you add to your Deck, heal 20 HP")
  — this one was a debt, not a blocker: it was scoped into the original
  relics batch, dropped during write-up, and never implemented. The whole-
  run `relic_counters` it needed already existed.
- **Pantograph** ("At the start of each Boss combat, heal 25 HP")
- **White Star** ("Elites drop an additional Rare card reward")

The latter two needed real additions, because the engine genuinely could
not tell an elite from a normal monster -- that distinction existed only
as display text in `play.py`'s encounter menus ("Byrdonis (Elite)"), so
nothing could branch on it. Added `Enemy.category` ("normal"/"elite"/
"boss") plus `CombatEngine.has_enemy_category()`. That marker is also a
prerequisite for real boss-pool selection and real per-encounter reward
rates, so it pays for itself beyond these two relics.

White Star needed something else missing: **`Card` had no rarity at all**.
Relics and potions carried a `rarity` field; cards never did -- the tiers
existed only as section comments in the pool. Added `Card.rarity`, filled
by `__post_init__` from a name table (`_COMMON_CARDS`/`_RARE_CARDS`, with
Uncommon as the default) so every card gets one however it's built, and a
`FACTORIES_BY_RARITY` index alongside the existing type index. The
"unlisted means Uncommon" default is guarded by `_assert_rarity_coverage()`
at import: a newly-ported card missing from the tables would otherwise
silently become Uncommon and quietly skew any rarity-weighted reward.
Current split across the 67 pooled cards: 20 Common / 29 Uncommon / 18 Rare.

Balance impact: none detectable. `bench.py` at 40 seeds gives 6/40 clears
against 7/40 before -- a one-run difference, i.e. noise at this sample
size. Three healing-ish relics added to a 70-relic pool rarely get drawn.

## Audit pass — 8 bugs found by full-codebase read-through, all fixed
Every one was reproduced with a failing test first, then re-run after the
fix. Listed worst-first.

1. **Enemies ran NO per-turn status logic at all** (`Enemy.take_turn`).
   The `Entity` methods existed and worked; only `Player.start_turn`/
   `end_turn` ever called them, so on the enemy side every status rule
   silently did nothing. Four separate symptoms from one root cause:
   Vulnerable/Weak/Frail on enemies **never expired** (permanent
   debuffs); Poison on enemies **never ticked**, which made the
   `Twisted Funnel` relic a completely dead effect (measured: 4 Poison
   applied, 0 damage ever dealt); enemy **Block accumulated forever**
   (Axe Raider sat on 30 Block after 12 turns instead of 0); and
   Metallicize/Plating/Regen/Ritual never fired on enemies, which
   quietly nullified the enemy-Plating scaling that `scale_special_buff`
   goes to the trouble of computing. Fixed by mirroring the player's
   ordering: Block clears and Poison/Regen/Ritual tick at the START of
   the enemy's own turn (so Block it gained still protects it through
   the player's turn, and Poison lands on 0 Block and hits HP directly,
   both matching how players already work), then Metallicize/Plating
   grant Block and debuffs decay at the END. Poison killing an enemy
   before it acts is handled explicitly. Verified Slippery (CONSUMED)
   and Byrdonis's Strength (PERMANENT) are correctly left alone by the
   new decay step. **This shifts balance**, in both directions: enemies
   no longer snowball Block, but player-applied debuffs now wear off --
   in an A/B on the identical Vantom fight the player ended 8 HP worse
   off, because Bash's Vulnerable stopped lasting the whole fight.
2. **Infernal Blade exhausted itself twice** -- its effect called
   `exhaust_card` while the pool entry also set `exhausts=True`, so
   `play_card` exhausted it again. The card landed in `exhaust_pile`
   twice, `total_exhausted_this_combat` jumped by 2, and every "whenever
   a card is Exhausted" trigger double-fired off one play (Feel No Pain
   paid 6 Block instead of 3). It was the only card in the file with
   this shape.
3. **`end_player_turn()` had no `_combat_over` guard**, unlike
   `play_card`/`use_potion`/`run_enemy_turn`. Calling it after a win
   re-ran `_check_victory_defeat()` and **re-fired every `on_combat_end`
   relic** (Burning Blood healed twice, "VICTORY" logged twice).
   `play.py`'s loop happens to break first, but `env.py`'s
   `_advance_sub_turn()` calls it unconditionally, so the RL path was
   exposed.
4. **Spite+ ignored its own upgrade** -- the effect hardcoded `hits = 2`
   while the upgraded text says "hits 3 times". Moved the count into
   `values`/`upgrade_values` so `card.val()` drives it. Audited every
   other multi-hit card: Twin Strike, Fight Me!, and Thrash all keep 2
   hits and only change damage on upgrade, so Spite was the only one
   where the *count* was the upgrade.
5. **Drum of Battle stacked duplicate hooks** -- it registered a
   combat-long `card_exhausted` listener on every play, but the card
   returns to the discard pile and can legitimately be replayed in one
   fight. Two plays then one Exhaust paid +4 energy instead of +2. Fixed
   with a per-combat `Player.armed_card_hooks` set so the listener arms
   once per instance.
6. **Havoc and Cascade bypassed the hook system** -- they called
   `played.effect(...)` raw, skipping `card_played`/`attack_played`/
   `skill_played`/`power_played` and the `enemy_died` broadcast. Measured:
   Rage granted 3 Block for a directly-played Attack and 0 for the
   identical Attack played via Havoc. Fixed by extracting
   `CombatEngine.resolve_card_effect()` and routing `play_card`, Havoc,
   and Cascade all through it, so the two paths can't drift apart again.
7. **Cleanups, no behaviour change**: a prebuilt `FACTORIES_BY_TYPE`
   index replaces `[f for f in CARD_POOL_IRONCLAD if f().card_type == X]`,
   which was instantiating all 60+ cards on every Infernal Blade / card-
   adding-potion play just to read one field; `Card.clone()` now copies
   the `values`/`upgrade_values` dicts instead of letting `copy.copy`
   leave Anger/Outrage copies sharing them (same aliasing shape as the
   dataclass-equality bug above, caught before it could bite);
   and `scale_enemy_for_players` is now idempotent, since it mutates
   `max_hp` in place and would silently double-scale an Enemy object
   reused across two engines.

## The RL interface: four passes that made it usable (#43, #44, #48, #49)

These sections lived in `README.md` until it was reorganised. They are the
history behind the observation and action space that file now documents.

### One rule set, three readers (#43)
The play rules used to exist in three copies: `play_card` (enforces),
`playable_cards` (advertises, read by `play.py`'s menu and `bench.py`'s
policy) and `env.legal_action_mask` (what the agent may pick). They drifted,
in both directions:

- Ringing, Smoggy and Bound were checked **only** in `play_card`, so
  `playable_cards` offered cards the engine then refused — the UI listed
  them and the benchmark policy wasted turns on them.
- The env mask knew about **neither** those nor anything added later, so
  Clash's play condition and the Sloth/Normality play caps were masked
  legal and then rejected. A masked agent would pick one, eat the −1 and
  burn the step on nothing.

All three now go through `CombatEngine.why_not_playable(player, card)`,
which returns `None` or a reason string.

Aligning them surfaced a real gameplay bug: **an ALLY-targeting card with no
ally was playable, and Demonic Shield loses 1 HP before discovering it has
no target.** `play.py` filters `is_multiplayer` cards out of solo reward
pools, so this looked unreachable — but `Jack of All Trades` and `Discovery`
both pull a *random* card into hand from a Colorless pool full of ally
cards. Now refused outright.

The benchmark barely moved (fixed-deck curve identical; Ceremonial Beast,
the Ringing boss, went 9/40 → 10/40), which is the expected shape for a
correctness fix rather than a balance change.

### The board cap and the observation layout (#44)
`env.py` had `MAX_ENEMIES = 4`. That was correct when written — enemy
lineups were fixed and the largest was 4 — and then **#23 added mid-combat
summoning and nothing here was revisited.** The engine caps the board at 12
precisely because two summoners are unbounded by their own text. So on any
summoning fight, enemies past index 3 were **invisible in the observation
and unreachable through the action space**: kill Phrog Parasite, it spawns
4 Wrigglers, and the agent cannot target the last one.

It now imports the cap (`MAX_ENEMIES = CombatEngine.MAX_ENEMIES`) rather
than restating it. Action space 41 → 121, observation 18 → 48.

Checking the padding maths turned up a second, quieter bug. `_observe`
padded players to **2** and then ran one trailing pad-to-total loop, so the
total length came out 18 for *every* party size and nothing ever looked
wrong — but at 3-4 players the extra players' features occupied the slots a
decoder reads as enemies, with the enemies shifted along behind them. **A
correct total length is not a correct layout.** Each section now pads to its
own fixed width.

### The hand is now in the observation (#48)
Checking the cap fix turned up something worse than the cap. The action
space indexes hand **slots**, but `_observe` emitted only player and enemy
features — so replacing a hand of Strikes with five Wounds left the
observation **bit-identical**. An agent was choosing "slot 3" with no way to
know what was in it, and the contents change every turn, which makes the
mapping from action to consequence close to random no matter how long you
train.

The hand became 150 floats — 15 features × `MAX_HAND` slots — in a fixed
section of its own.

### Statuses, relics and potions (#49)
The last three blind spots, all verified absent before being fixed rather
than assumed.

**Statuses were invisible** — 5 Strength on the player and 3 Vulnerable on
the enemy moved the observation not at all. That one had a sharp
consequence: `bench.py`'s `greedy_policy` explicitly sequences around
Vulnerable, so the scripted baseline had *strictly more information* than
the agent it was a baseline for.

**Potions had no action id at all.** All 52 are modelled, `use_potion`
works, `play.py` exposes it — but the action space was `(hand slot × target)
+ END_TURN`, so an agent could not drink one. That is precisely why
`bench.py` needed its own `maybe_use_potion`, and why an early benchmark bot
collected potions and died holding them.
