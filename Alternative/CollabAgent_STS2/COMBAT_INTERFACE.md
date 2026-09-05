# Combat interface

`Server/session.py` drives combat entirely through the surface below. It does not
import `GameEngine.Combat` — `Server/main.py` passes the class in:

```python
from GameEngine.Combat.combat import Combat
session = Session(combat_factory=Combat, required_players=REQUIRED_PLAYERS)
```

So the combat module is free to be structured however you like (`Context/`,
`Resolution/`, wherever) as long as one class satisfies this. Until it exists,
`main.py` exits with a message saying so; everything else already runs.

---

## What Session calls

| Call | Expectation |
|---|---|
| `Combat(allies, enemies, rng=rng)` | Constructor. `allies` and `enemies` arrive already built. `rng` is a seeded `random.Random` — use it for every shuffle and random choice so runs stay reproducible. |
| `.start()` | Set up draw piles, deal opening hands, choose first intents. |
| `.is_over()` | `bool`. |
| `.phase.name` | Enum-like. Session only tests `== "PLAYER_TURN"`. |
| `.result.name` | Broadcast verbatim when the fight ends. `"VICTORY"` / `"DEFEAT"` suggested. |
| `.find_unit(unit_id)` | The unit with that id, or `None`. |
| `.play_card(ally, hand_index, target=None)` | Play it. Return a list of JSON-safe dicts describing what happened. |
| `.end_player_turn()` | Run the enemy turn and begin the next player turn. |
| `.to_dict()` | Full JSON-safe state. Broadcast verbatim after every action. |

Session catches `ValueError`, `IndexError`, `KeyError` and `RuntimeError` from
`play_card` and `end_player_turn`, and returns the message privately to the
player who sent it. So raising with a readable message is the way to reject an
illegal play — no need for a result code.

## Three constraints that come from the wire, not from taste

**1. `to_dict()` must be JSON-serializable.** No enums, no objects, no sets. It
goes straight into a socket.io message.

**2. `ally.hand` is the client's source of truth, and `hand_index` indexes it.**
`Ally.to_dict()` already ships `hand` to the client; the client picks a card by
position and sends that integer back. Whatever `hand` holds must therefore be
JSON-safe and stably ordered. It currently holds `card_id` strings.

**3. Unit ids are assigned by Session**, not by combat: allies are `p1`, `p2`, …
and enemies `e1`, `e2`, … The client targets by these strings, which is what
`find_unit` resolves.

## Helpers already in place

- `GameEngine/Cards/_card_registry.py` — `create_card(card_id)` turns the strings
  in `Ally.deck` into `Card` objects, `known_card_ids()` lists them. Register new
  cards there. **This may belong in your empty `Registry/` — say the word and it moves.**
- `Unit`, `Ally` and `Enemy` now take an optional `rng=` which threads through to
  the max-HP roll, so seeded runs are reproducible. Omit it and behaviour is
  unchanged from before.

## Two design questions that are yours to answer

**Card identity.** Piles hold `card_id` strings and `create_card()` mints a fresh
instance per play. Clean, and ideal for the wire — but it means a card cannot
carry per-copy state. No upgrades, no "this copy costs 0 this turn". Either piles
hold `Card` instances and serialize to ids at the network boundary, or upgrades
get tracked alongside. Cheap now, expensive after a hundred cards exist.

**Status hooks.** Resolution needs somewhere to express "Vulnerable multiplies
incoming damage by 1.5". `StatusEffect` is currently a bare `pass`, left exactly
as you wrote it. One shape that works, if useful:

```python
class StatusEffect(Effect):
    def modify_incoming_damage(self, amount): return amount
    def modify_outgoing_damage(self, amount): return amount
    def on_owner_turn_end(self): self.amount -= 1
```

...with the resolver folding every status on source and target over the amount.
Entirely your call — this is only a suggestion, deliberately not implemented.
