# Combat interface

`Server/session.py` drives combat entirely through the surface below. It does
not import `GameEngine.Combat` — `Server/main.py` passes the class in:

```python
from GameEngine.Combat.combat import Combat
session = Session(combat_factory=Combat, required_players=config.REQUIRED_PLAYERS)
```

So combat stays free to restructure internally as long as one class satisfies
this. The surface has not changed since it was first written.

---

## What Session calls

| Call | Expectation |
|---|---|
| `Combat(allies, enemies, rng=rng, act="act1", scale_enemies=True)` | Constructor. `allies` and `enemies` arrive already built; 1 to `Combat.MAX_ALLIES` (4) players, or it raises `ValueError`. `rng` is a seeded `random.Random` — use it for every shuffle and random choice so runs stay reproducible. `act` and `scale_enemies` drive co-op HP scaling (below); both come from `config.py`. |
| `.start()` | Set up draw piles, deal opening hands, choose first intents. |
| `.is_over()` | `bool`. |
| `.phase.name` | Enum-like. Session only tests `== "PLAYER_TURN"`. |
| `.result.name` | Broadcast verbatim when the fight ends. |
| `.find_unit(unit_id)` | The unit with that id, or `None`. |
| `.play_card(ally, hand_index, target=None)` | Play it. Return a list of JSON-safe dicts describing what happened. |
| `.end_player_turn()` | Run the enemy turn and begin the next player turn. Raises while a choice is unanswered. |
| `.choice_for(ally)` | The question waiting on this player, or `None`. |
| `.answer_choice(ally, option_index)` | Carry out the option they picked; returns result dicts like `play_card`. |
| `.forfeit_choices(ally)` | A player left: answer what they were asked, and anything they are asked later, at random. Without this a fight would wait forever on them. |
| `.ask_players` | Set True when there are players to ask; False (default) answers at random. |
| `.to_dict()` | Full JSON-safe state. Broadcast verbatim after every action. |

Session catches `ValueError`, `IndexError`, `KeyError` and `RuntimeError` from
`play_card` and `end_player_turn`, and returns the message privately to the
player who sent it. Raising with a readable message is the way to reject an
illegal play — no result code needed.

A refusal has to leave the fight exactly as it was. Every check — hand
rules, cost, target (an `ALLY`-target card aimed at yourself is refused with
"must target another player", as every such card says) — runs before the
energy is spent and the card leaves the hand. A card must not raise from
inside `get_effects`: by then it has been paid for and popped, so the player
would lose the card and the energy and see only an error. `tests/card_matrix.py`
checks this for every card.

## Three constraints that come from the wire, not from taste

**1. `to_dict()` must be JSON-serializable.** No enums, no objects, no sets. It
goes straight into a socket.io message.

**2. `ally.hand` is the client's source of truth, and `hand_index` indexes it.**
The client picks a card by position and sends that integer back, so whatever
`hand` holds must be JSON-safe and stably ordered.

It holds `CardRef`s — a `str` subclass carrying the id, so json still writes
`"strike"` and nothing on the wire changed. Per-copy state that the id cannot
express rides alongside in arrays the same length as `hand`: `hand_upgraded`
(bools) and `hand_replay` (ints). Both are additive; a client that ignores them
behaves exactly as before.

If a third such field ever appears, these should collapse into one
`hand_cards` array of objects rather than growing a fourth parallel array —
your call, and cheap while only two clients read it.

**3. Unit ids are assigned by Session**, not by combat: allies are `p1`, `p2`, …
and enemies `e1`, `e2`, …. The client targets by these strings, which is what
`find_unit` resolves.

---

## How a card works

A card is pure data plus one method. It never mutates a unit:

```python
class Anger(Card):
    DAMAGE = 6

    def __init__(self):
        super().__init__(
            card_id="anger", name="Anger",
            card_type=CardType.ATTACK, card_class=CardClass.IRONCLAD,
            rarity=CardRarity.COMMON, cost=0, target_type=TargetType.ENEMY,
            properties=CardProperties(exhaust=True),
        )

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
```

`get_effects` returns effects; `Resolver` is the only code that touches a unit.
Register the class in `Registry/card_registry.py` and it exists.

**Choices belong to the card, not the resolver.** A card that exhausts a random
card picks the id itself and hands the resolver a list. That keeps `Resolver` a
flat dispatch with no game knowledge in it.

**`context`** carries `source`, `target`, `all_allies`, `all_enemies`, `rng`,
and `payload`. Use `context.rng` — never module-level `random` — or seeded runs
stop reproducing.

**Two hooks answer "may this be played", and neither is `properties.playable`,**
which is a fixed property of the printing. Both read the whole hand, and both
are checked before any cost is paid:

- `playable_now(ally)` — a condition on the hand. Clash returns False unless
  every card held is an Attack. The card asking is still in hand at that point.
- `MUST_PLAY_FIRST` — a class flag. While such a card is held, nothing else may
  be played; Enthralled is the only one. With two in hand the first copy is the
  one that has to go.
- `PLAY_CAP` — a class flag capping cards played per turn while held (Sloth,
  Normality). The tightest cap in hand wins.

Two more are charged at turn start rather than at play time, and read the whole
**deck** — hand, draw pile and discard pile — not just the hand: `DRAW_PENALTY`
(Mind Rot) and `ENERGY_PENALTY` (Waste Away). Copies stack, and the exhaust pile
is excluded, which is what makes exhausting one the way out.

Neither applies to a card played by another card — `auto_play_card` bypasses
both, matching the reference.

**Effects are all built before any of them resolve**, so `get_effects` alone
cannot make a decision that depends on what an earlier effect of the same card
did. `follow_up(result, context)` is the way round it: Combat calls it after
each effect resolves, and it returns more effects. "Draw 2, then put a card
back" (Thinking Ahead) is exactly that shape. Follow-ups are resolved but not
offered back, so they cannot chain.

## How a power works

There is no power registry. A power is a `StatusEffect` with an `on_event`
hook, and `Combat` dispatches:

```python
class DarkEmbrace(StatusEffect):
    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.CARD_EXHAUSTED:
            return None
        if context.target is not context.source:
            return None
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.amount, rng=context.rng)]
```

Return a list of effects, or `None` to ignore. Combat resolves what comes back,
one level deeper, bounded by `MAX_EVENT_DEPTH`.

**In an event context, `source` is the status's owner and `target` is who the
event happened to.** A power that only cares about itself checks
`context.target is context.source`. Getting this backwards is the easiest
mistake to make here.

Statuses may also modify numbers rather than react: `modify_incoming_damage`,
`modify_outgoing_damage`, `modify_block_gained`. `DAMAGE_ORDER` decides
sequencing — `ADDITIVE` (Strength) runs before `MULTIPLICATIVE` (Vulnerable),
because +2 then ×1.5 is not ×1.5 then +2.

The ten events: `TURN_START`, `TURN_END`, `CARD_PLAYED`, `CARD_DRAWN`,
`CARD_EXHAUSTED`, `HP_LOST`, `BLOCK_GAINED`, `ATTACKED`, `STATUS_APPLIED`,
`DECK_SHUFFLED`.

`DECK_SHUFFLED` is the odd one: an `Ally` reshuffles inside its own `draw()`
and has no Combat to emit with, so it counts reshuffles and Combat drains the
count once the draw has finished. Draining mid-loop would let a status move a
card out from under the draw.

---

## Card identity — how it was settled

Piles used to hold bare `card_id` strings, so a card could carry no per-copy
state. That blocked 8 cards and every upgrade.

Neither of the two obvious ways out was taken. Piles now hold `CardRef`, which
**subclasses `str`**: it is the id for every purpose that already existed —
`card_id == "strike"`, the registry lookup, `json.dumps` — and an object with
attributes for the one purpose that did not. So no comparison, no card file and
no wire field had to change, and `hand_index` still works exactly as before.

Three consequences worth knowing:

- **`create_card(ref)` binds the copy's state onto the card**, so `self.upgraded`
  and `self.bonus_damage` are simply there in `get_effects`.
- **Removal from a pile is identity-based** (`_card_ref.take`). `list.remove`
  drops the first *equal* entry, which with two Strikes in hand is a coin flip.
- **Upgrades are combat-scoped for free.** `_build_draw_pile` copies each deck
  entry, so a fight's upgrades die with it and there is nothing to revert. A
  deck entry that is itself an upgraded `CardRef` stays upgraded — that is how
  a permanent upgrade would be expressed.

What an upgrade *changes* lives in one table, `Cards/_upgrades.py`, rather than
in 223 card files. Cards read their numbers off their own constants, so
`apply_upgrade` sets those constants on the instance and no card has to know.
161 cards have an entry. For 6 (Cruelty, Knockdown, Outmaneuver, Panache,
Relax, The Bomb) the upgraded number lives on a *status* rather than the card,
so their upgrade is currently a no-op.

## What is left, and what unlocks it

14 of the 230 planned cards. `python Registry/coverage.py` prints the split:
13 cannot exist in an Ironclad-only co-op run, and Alchemize needs a potion
system, which was never in scope. A ninth Mad Science variant, Improvement
("at the end of combat, Upgrade a random card"), is skipped as deck editing
between fights. Nothing is unaccounted for.

Two cards have no values in the reference engine and were ported from the
game itself:

- **Splash** — "1 of 3 random Attacks from another character". In co-op that
  is your partner's character; in an Ironclad-only run that is Ironclad, so it
  is Discovery narrowed to Ironclad Attacks. `Splash.offer_from` is where a
  second class would plug in. Its upgrade is unknown, so Splash+ is a no-op.
- **Mad Science** — one event card with eight printings (Sapping, Violence,
  Choking, Energized, Wisdom, Chaos, Expertise, Curious), all cost 1. Each is
  its own id, `mad_science_<variant>`, sharing the name; `TOKEN` class, so
  "a random card" never turns one up. Types were inferred from the text —
  damage is an Attack, Curious is a Power, the rest are Skills. Choking, like
  StS1's Choke, does not trigger on the card that applied it.

## How an enemy works

`Units/Enemies/_scripted.py` gives an enemy a move list and one rule:

```python
class TheInsatiable(ScriptedEnemy):
    DEFAULT_MAX_HP = 321          # single-player; Combat scales it for co-op

    def __init__(self, ...):
        thrash = Move("Thrash", Move.ATTACK, lambda e, c: e._thrash(c),
                      damage=8, hits=2)
        ...
        self._cycle = (thrash, lunge, salivate, thrash)

    def pick_move(self, turn):
        return self._opener if turn == 0 else self._cycle[(turn - 1) % 4]
```

A `Move` is a name, a kind (`attack` / `block` / `buff` / `debuff`), a function
building its effects, and the per-hit `damage` and `hits` the client shows.
`ScriptedEnemy.choose_intent` picks the move and — for an Attack — **names its
target then**, so the intent the players see says who is about to be hit. That
pick stands if the ally is still alive when the turn comes (`_enemy_target`);
otherwise the first living ally takes it. Intercept redirects after that.

**Co-op scaling** is real STS2, applied in `Combat.start()`; one player is
never scaled. HP: × player count × act factor (act1 1.1, act2 1.2, act3 1.2,
act3boss 1.3) — The Insatiable is 321 alone, 770 for two in act 2. Block an
enemy gains: flat × 2 for two players, × players × act factor beyond; the
resolver applies `enemy.block_scale` before Dexterity, as the reference does.
Aeonglass's Ebb blocks 33 alone, 66 for two, 109 for three (33 × 3.3 = 108.9,
rounded as the reference does). Nothing else scales: an enemy's damage, the
Strength it gains and the status cards it hands out are the same numbers for
one player or four, and each move names one living player. `tests/test_scaling.py`
runs every scripted enemy at 1–4 players in two acts and checks all of that
turn by turn against the solo run.

A `Move` can be `targeted=True` without being an Attack — Aeonglass's
Intensity is a debuff that still names one player.

Most Act 1 enemies are two moves long, so five helpers cover them:
`attack("Tackle", 3)` is a Move hitting the announced target (`hits=2` for a
double, `block=5` for one that guards as it swings, `inflict=(Frail, 2)` for a
rider on the victim, `gain=(Strength, 2)` for one on the attacker),
`buff("Hiss", Strength, 2)` and `guard("Reload", 3)` are the Strength and
Block moves, `debuff("Roar", Vulnerable, 3)` puts a status on one named player,
and `hand_out("slimed", 2)` builds the effects that put status cards into the
target's discard pile. `HP_RANGE = (32, 35)` rolls the wiki's range once per
fight from the seeded rng (replacing `DEFAULT_MAX_HP`), and `NAME = "Leaf
Slime (M)"` is what the client shows instead of the class name. A whole
slime is twelve lines:

```python
class LeafSlimeMedium(ScriptedEnemy):
    NAME = "Leaf Slime (M)"
    HP_RANGE = (32, 35)

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        sticky = Move("Sticky Shot", Move.DEBUFF, hand_out("slimed", 2), targeted=True)
        self._cycle = (sticky, attack("Clump Shot", 8))

    def pick_move(self, turn):
        return self._cycle[turn % 2]
```

The plain Act 1 pool — Nibbit, Snapping Jaxfruit, Fuzzy Wurm Crawler, and the
Assassin / Axe / Brute / Crossbow Raiders (`raiders.py`) — is built from those
four helpers alone; `test_enemies.py` holds each one's script as a table of
(move, damage taken, Block after, Strength after) per turn. Two things to know
when reading them: an enemy's Block clears at the start of **its own** turn,
so Crossbow Raider's Reload never protects it from the player (as in the
reference), and Snapping Jaxfruit gains its Strength *after* the orb lands, so
the orbs go 3, 5, 7.

The Act 1 debuffers — Flyconid, Slithering Strangler, Vine Shambler, Shrinker
Beetle, Mawler, Tracker Raider, Cubex Construct — brought three statuses:

- **Shrink** (Shrinker Beetle, 3 turns): the player's Attacks deal 30% less;
  stacks with Weak (6 → 4 → 3). The wiki's "removed when the applier dies" is
  modelled here, which the reference notes it does not do: a status knows its
  `source`, so a dead Beetle's Shrink does nothing and is culled at the next tick.
- **Constrict** (Slithering Strangler, 3): at the end of each of the player's
  turns, 3 damage while the Strangler lives. Never decays; Block stops it;
  Vulnerable does not touch it (see below); gone once the Strangler is dead.
- **Tangled** (Vine Shambler): Attacks cost 1 more, one turn per stack. Applied
  before the free-play grants are consulted, so an Attack Unrelenting made free
  stays free. The reference applies **1** where its own note quotes the wiki as
  "for 2 turns"; the reference's number is used (`VineShambler.TANGLED`).

Fogmog is the one Act 1 normal left out: Illusory Spores *summons* an Eye With
Teeth, and `Combat` has no way to add an enemy after `start()` yet — the
newcomer would need an intent chosen and the co-op scaling applied. That is
the next engine feature, shared with Phrog Parasite and Two-Tailed Rat.

**A status can be attack-only.** `StatusEffect.ATTACKS_ONLY = True` means its
`modify_incoming_damage` is consulted for attacks alone — Vulnerable, Exposed
and Colossus Guard — so a Burn, a Constrict or a Wither on a Vulnerable player
deals its printed number, as in the reference. Intangible, Tank and Protected
leave it False and cap or scale every kind of damage. Before this a Burn on a
Vulnerable player dealt 3.

`Dummy1` predates this and still hits every ally at once; it is a test target,
not a model.

## Cards that enemies hand out

Every status card an enemy or boss in the reference gives the player is
ported. Two need the enemy to pass per-copy state, which `CardRef` carries:

- **The Insatiable** (ported: `Units/Enemies/the_insatiable.py`) — Liquify
  Ground applies `Sandpit(4)` and puts 6 `frantic_escape` into the deck: 3 at
  the **bottom** of the draw pile, 3 in the discard. Sandpit counts down at each
  of the owner's `TURN_START`s and kills at 0 - the fight is lethal on turn 5
  unless escapes are found and played; each adds 1 and raises that copy's cost
  by 1 for the combat.
- **Aeonglass** (ported: `Units/Enemies/aeonglass.py`) — Increasing Intensity
  hands one player Wither+X and takes 2+X Strength, where X is how many times
  it has intensified. The card is `CardRef("wither", bonus_damage=X)` and
  reads `AMOUNT + bonus_damage`, so it deals 3, 4, 5... The client sees only
  `"wither"` in hand; the bonus is not on the wire yet (see the `hand_cards`
  note above).
- **Leaf Slime (S/M), Twig Slime (M)** (`leaf_slime.py`, `twig_slime.py`) —
  Goop / Sticky Shot put 1 or 2 `slimed` into one named player's discard pile,
  then the slime hits, alternating from the shot. Twig Slime (S) only Tackles.
- **Wriggler** (`wriggler.py`) — Wriggle gives one player an `infection` and
  the Wriggler 2 Strength; Nasty Bite follows.

Self-inflicted status damage (Burn, Toxic, Wither, Infection, Decay,
Disintegration) is `is_attack=False`, as in the reference: it meets Block but
takes no Strength and triggers nothing that reacts to being attacked. A card
held at end of turn reacts to **its holder's** `TURN_END` only — `TURN_END` is
emitted once per player, and the hand walk used to run for every emission, so
a Burn dealt 2 per player in the fight. Found by the Wriggler's Infection.

## Player choice

Twelve cards stop mid-resolution and ask the player a question. The machinery
is one method:

```python
context.ask(ally, "Put a card on top of your Draw Pile",
            lambda: list(ally.hand), stash)
```

Nothing happens at that moment. `stash(chosen)` returns the effects that carry
the answer out, and Combat runs them once there is an answer.

**With nobody to ask, the answer is picked at random** (`Combat.ask_players`
is False by default). A headless or training run therefore plays straight
through, exactly as it did before choices existed. `Session` sets the flag when
players connect, and only then does anything wait.

Three things worth knowing before adding a thirteenth:

- **Options are worked out when the question is put, not when it is queued.**
  Pass a callable when they come from a pile. Purity queues three questions at
  once; without this the second would offer the card the first just exhausted.
- **A question raised mid-action is answered after the action finishes.** A
  card can ask from `get_effects`, from `follow_up` (Thinking Ahead, whose
  question only exists after the draw), or from a status's `on_event`
  (Stratagem, on a reshuffle).
- **Each player holds one question at a time**; the rest of theirs wait in
  order behind it, so a card's questions arrive in the order it asked. The
  other player is not blocked and may be holding a question of their own. The
  turn will not advance until every question is answered - and a player who
  disconnects has theirs answered for them (`forfeit_choices`), or it never
  would.

On the wire: `choice_required` goes privately to whoever must answer, `choose`
carries `option_index` back, and `to_dict()["choices"]` carries the same thing
for any client that missed the message.

True Grit is the thirteenth call site and stays random on purpose: its base
printing reads "Exhaust 1 card **at random**". Only True Grit+ should ask, and
our port does not yet split the two.
