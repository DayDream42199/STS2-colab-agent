# Handoff — what changed

Split: **combat is yours**, everything else was built out. Nothing was
restructured, no cards were added — still Strike, Defend and Bash.

`Context/`, `Registry/`, `Resolution/` and `Plugins/` are untouched.

## Start here

```bash
cd Server && python main.py
```

It will tell you combat is missing and exit. That is expected and is the only
thing standing between this and a playable co-op fight. See
**COMBAT_INTERFACE.md** for the surface `session.py` expects.

## Your files that were changed

| File | Change | Why |
|---|---|---|
| `Cards/_card.py` | `from _card_properties` → `from ._card_properties` | Absolute import inside a package. Nothing in the project imported at all before this. |
| `Cards/_card_properties.py` | `playable=False` → `True` | **Needs your decision** — see questions below. |
| `Units/_unit.py` | optional `rng=None` param | Seeded, reproducible max-HP rolls. |
| `Units/Allies/_ally.py` | forwards `rng` | Same. |
| `Units/Enemies/_enemy.py` | forwards `rng` | Same. |
| `Units/Enemies/dummy_1.py` | forwards `rng` | Same. |
| `Server/main.py` | was empty, now the server loop | Entry point. |

Eleven lines total across the six code files. Every RNG change is
backward-compatible: omit `rng` and behaviour is bit-for-bit what it was.

**Touched and then reverted to your originals** (byte-identical, verified):
`Effects/StatusEffects/_status_effect.py` and `vulnerable.py`. Hooks were added
there to serve a damage resolver, then removed once combat became yours — that
shape is your call. The suggestion is recorded in COMBAT_INTERFACE.md.

## New files

| File | What |
|---|---|
| `Server/session.py` | Lobby, `sid`→ally mapping, turn readiness, message handling. Imports no combat module. |
| `Server/Protocol/enums.py`, `protocol.py` | Wire message types and `encode`/`decode`. |
| `Client/Protocol/…` | Byte-identical mirror, matching how `Network/` is already duplicated. |
| `Cards/_card_registry.py` | `create_card(card_id)` — turns deck strings into `Card` objects. |
| `.gitignore` | Standard Python ignores. `__pycache__` came across in both directions; this stops it. |

## Protocol

Messages are `{"type": ..., "payload": {...}}`.

- **Client → server:** `play_card` (`hand_index`, optional `target_id`), `end_turn`, `request_state`
- **Server → client:** `welcome`, `lobby`, `state`, `effects`, `ready_changed`, `combat_ended`, `error`

Two behaviours worth knowing: ending your turn is **readiness-based** — the turn
advances only when every living, connected player has sent `end_turn`, and
playing a card revokes your readiness. And a disconnect releases the turn rather
than deadlocking it; the ally stays in the fight so targeting stays coherent.

`REQUIRED_PLAYERS` at the top of `main.py` is 1 for solo testing. Raise it for co-op.

## Questions

1. **`playable` default.** It was `False`, which made every card unplayable, while
   every other flag in `CardProperties` is off-by-default. Flipped to `True` on the
   assumption it was a slip. Revert if it was deliberate.
2. **Does `_card_registry.py` belong in `Registry/`?** It went into `Cards/`. Your
   empty `Registry/` may well be its intended home — or `Registry/` may mean
   something else entirely, in which case say so and it moves.
3. **The two design questions in COMBAT_INTERFACE.md** — card identity (id strings
   vs `Card` instances, which decides whether upgrades are possible) and the status
   hook shape.

## Not done

- **No tests ship with this.** The session layer is untested in-tree; its suite
  needs writing against a stub combat.
- **No client application.** `Client/` is still the network shell plus the protocol
  mirror — no game code, nothing to connect with yet.
- `python-socketio`'s *client* also needs `pip install requests websocket-client`;
  the server side only needs `eventlet` and `python-socketio`.
