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
| `Combat(allies, enemies, rng=rng)` | Constructor. `allies` and `enemies` arrive already built. `rng` is a seeded `random.Random` — use it for every shuffle and random choice so runs stay reproducible. |
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
system, which was never in scope. Nothing is unaccounted for.

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

## Cards that enemies hand out

Every status card an enemy or boss in the reference gives the player is
ported. Two need the enemy to pass per-copy state, which `CardRef` carries:

- **The Insatiable** — Liquify Ground applies `Sandpit(4)` and puts 6
  `frantic_escape` into the deck: 3 on top of the draw pile, 3 in the discard.
  Sandpit counts down at each of the owner's `TURN_START`s and kills at 0;
  playing Frantic Escape adds 1 and raises that copy's cost by 1 for the
  combat. `test_fork.py`'s `liquify()` is the exact shape to produce.
- **Aeonglass** — Intensity hands out Wither+X, where X is how many times it
  has intensified. That is `CardRef("wither", bonus_damage=X)`: the card reads
  `AMOUNT + bonus_damage`, so nothing else is needed.

Self-inflicted status damage (Burn, Toxic, Wither, Infection, Decay,
Disintegration) is `is_attack=False`, as in the reference: it meets Block but
takes no Strength and triggers nothing that reacts to being attacked.

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
