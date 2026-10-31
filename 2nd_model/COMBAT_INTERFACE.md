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
| `Combat(allies, enemies, rng=rng, act="act1", scale_enemies=True)` | Constructor. `allies` and `enemies` arrive already built; 1 to `Combat.MAX_ALLIES` (4) players, or it raises `ValueError`. `rng` is the fight's random streams (`Context/rng_streams.py`, one per purpose, as the game's `RunRngSet`), or one seeded `random.Random` to seed them from; with none it draws a seed and keeps it in `.seed`. Draw from the stream that fits (below) so runs stay reproducible and one kind of randomness never moves another. `act` and `scale_enemies` drive co-op HP scaling (below); both come from `config.py`. |
| `.start()` | Set up draw piles, deal opening hands, choose first intents. |
| `.is_over()` | `bool`. |
| `.phase.name` | Enum-like. Session only tests `== "PLAYER_TURN"`. |
| `.result.name` | Broadcast verbatim when the fight ends. |
| `.find_unit(unit_id)` | The unit with that id, or `None`. |
| `.play_card(ally, hand_index, target=None)` | Play it. Return a list of JSON-safe dicts describing what happened. Takes back this player's end turn, if they had ended. |
| `.end_turn(ally)` | This player is done for the turn: their id goes in `.ended_turn`. Refused (as `play_card` is) outside the player turn, with a question to answer, or when defeated. Session ends the round once every player still connected has ended. |
| `.wait(ally)` / `.may_wait(ally)` | Let the others move first: their id goes in `.waiting`, nothing else changes. Allowed only while someone else can still move the turn on - a question to answer, or not ended and not waiting - and never for a player who has ended or is already waiting. The next play, answer, end turn or departure clears every wait. So waiting never stalls a round: `tests/test_wait.py`. |
| `.end_player_turn()` | Run the enemy turn and begin the next player turn. Raises while a choice is unanswered. Clears `.ended_turn` and `.waiting`. |
| `.choice_for(ally)` | The question waiting on this player, or `None`. |
| `.answer_choice(ally, option_index)` | Carry out the option they picked; returns result dicts like `play_card`. `PendingChoice.STOP` (-1) ends an "up to N" question with nothing picked, and is refused on any other. |
| `.forfeit_choices(ally)` | A player left: answer what they were asked, and anything they are asked later, at random. Without this a fight would wait forever on them. |
| `.ask_players` | Set True when there are players to ask; False (default) answers at random. |
| `.legal_actions(ally)` | Every message this player may send now, as `{"type": "play_card", "hand_index", "target_id"}`, `{"type": "end_turn"}`, `{"type": "wait"}` (when `may_wait`) and `{"type": "choose", "option_index"}` (-1 to stop). Listed is accepted, anything else refused - `tests/test_legal_actions.py` checks both. Also in each ally's state as `legal_actions`. |
| `.to_dict()` | Full JSON-safe state. Broadcast verbatim after every action. Each ally carries `ended_turn` and `waiting`. |

**Waiting on the wire.** A client sends `wait` (no payload; `decision` is
kept as on any action). Everyone gets a `ready_changed` - `ready`,
`waiting_on` (who the round still needs) and `waiting` (who chose to wait) -
and no state, since nothing in the fight changed. `ready_changed` also goes
out when a player leaves mid-fight, so whoever waited on them decides again.
A human never needs to send it; the terminal client does not.

Session catches `ValueError`, `IndexError`, `KeyError` and `RuntimeError` from
`play_card` and `end_player_turn`, and returns the message privately to the
player who sent it. Raising with a readable message is the way to reject an
illegal play — no result code needed. Anything else that is raised is a bug:
Session catches it too, prints and logs the traceback (an `error` line), tells
the sender, sends everyone the state as it now stands, and carries on.

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

A third, `hand_cost`, is added by `Combat.to_dict()` (the ally alone cannot
price a card): what each card costs to play right now, as the game prints it -
a number after Stomp's discount, Tangled, Corruption, a Frantic Escape bump or
a copy's own cap (a free copy, Enlightenment); `"X"` for an X-cost card; `None`
for one that cannot be played.
`Combat.hand_costs(ally)` gives the same list to in-process code.

A fourth, `hand_damage`, is one hit of each Attack as the game shows it before
a target is chosen: after the holder's Strength, Weak and Vigor (Vigor is not
spent by being shown), not the target's Vulnerable; `None` for anything that
is not an Attack. It comes from `Card.base_damage(ally)` - the printed number,
or, for the seven cards that work theirs out (Body Slam, Fiend Fire, Gold Axe,
Mind Blast, Ashen Strike, Perfected Strike, Pact's End), the same method
their `get_effects` reads, so the number shown and the hit cannot drift.
What depends on the target (Bully, Rend, Gang Up) shows the base number.
`Combat.hand_damages(ally)` gives it in-process; `tests/test_cost.py` plays
every Attack four ways and checks the first hit against it.

A fifth, `hand_text`, is what each card does, as the player reads it:
"Deal 6 damage." on a Strike, "Deal 9 damage." on a Strike+. It comes from
`Cards/_text.py`, one template per card written from what its code does
here. The numbers are never typed in: `{DAMAGE}` is filled from the card's
own constant after its upgrade (and its Rampage-style bonus), and keywords
(Unplayable, Innate, Retain, Ethereal, Exhaust) from the copy's properties.
In hand, an Attack's damage reads as the game shows a card in hand - after
the holder's Strength, Weak and Vigor, the same number as `hand_damage` - and
Body Slam, Mind Blast, Gold Axe, Ashen Strike and Perfected Strike add what
they come to now ("Deal damage equal to your Block (now 7)."). Block works
the same way from `Combat.hand_blocks(ally)`: the Block each card gives the
player holding it, after Dexterity, Frail, Unmovable and Fasten (`None` for
Lift, whose Block goes to a teammate, and Mimic, whose depends on the
target). It is computed in-process and not sent as its own array; the hand
text shows it, and Entrench, Stack, Second Wind, Evil Eye and Fisticuffs add
"(now N)". Piles and question options show the printed numbers. The terminal client prints only
the text, since `hand_damage` would say the same number twice.
**A new card needs an entry there**; `tests/test_card_text.py` fails until it
has one, and also fails if an upgrade changes a number the text leaves out.
Question options carry the same, as `option_text` beside `options`.

The piles go out already in that shape: `piles` holds `draw`, `discard` and
`exhaust`, each a list of `{"id", "upgraded", "text"}` (`Combat.pile_view(ally)`).
The draw pile is sorted as the game's pile screen sorts it - rarity, then id,
Status and Curse last - so it never gives away which card comes next; discard
and exhaust keep their order, newest last. The terminal client shows the
counts on each player's line and the contents on `piles [player_id]`.

With five, these really should collapse into one `hand_cards` array of
objects, the shape the piles already use — your call. `hand_cost`,
`hand_damage` and `hand_text` went in as arrays so that no client broke; the
collapse would change the wire.

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

**`context`** carries `source`, `target`, `all_allies`, `all_enemies`,
`rngs`, `payload`, and for a card being played `played` (that copy) and
`play_id` (that play). Draw from the stream the game uses -
`context.rngs.card_generation` for a card made, `.card_selection` for a card
picked at random, `.targets` for a random target, `.shuffle` for a draw (pass it
as `rng=`) or a card put into the draw pile at random - never module-level
`random`, or seeded runs stop reproducing. `context.rng` is the `niche` stream.

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
                            amount=self.amount, rng=context.rngs.shuffle)]
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
in 219 card files. Cards read their numbers off their own constants, so
`apply_upgrade` sets those constants on the instance and no card has to know.
For 5 (Knockdown, Outmaneuver, Panache, Relax, The Bomb) the upgraded number
lives on a *status* rather than the card, so their upgrade is currently a
no-op. A few upgrades change what a card does rather than a number - Cascade+
plays X+1, Primal Force+ and Stoke+ make upgraded cards, True Grit+ lets you
choose - and those read `self.upgraded` in `get_effects`.

## What is left, and what unlocks it

18 of the 230 planned cards. `python Registry/coverage.py` prints the split:
13 cannot exist in an Ironclad-only co-op run, 4 are no longer in the game
(Blaze, Midnight, Outrage, Abundance), and Alchemize needs a potion system,
which was never in scope. A ninth Mad Science variant, Improvement
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

Every enemy here is ported from the installed game's own code (v0.107.1,
`MegaCrit.Sts2.Core.Models.Monsters`): HP, every number, the move pattern and
what each move does. `tests/test_enemies.py` checks each against it.

**Every move lands on every living player.** The game has no single-target
enemy move: `MonsterModel.PerformMove` hands each move all the players, and an
attack built with `FromMonster` targets all opponents. So Butt hits both
players for 12, Roar puts 3 Vulnerable on both, Goop slimes both. An intent
names nobody. Intercept is the one way to change who is hit: the interceptor
takes the covered teammate's hit as well as their own.

`Units/Enemies/_scripted.py` gives an enemy a move list and `pick_move(turn)`.
A fixed pattern is a cycle; a random one uses `choose(branches)`, the game's
RandomBranchState:

```python
class Mawler(ScriptedEnemy):
    def __init__(self, ...):
        self._claw = attack("Claw", 4, hits=2)
        self._branches = (Branch(attack("Rip and Tear", 14), Branch.NO_REPEAT),
                          Branch(debuff("Roar", Vulnerable, 3), Branch.ONCE),
                          Branch(self._claw, Branch.NO_REPEAT))

    def pick_move(self, turn):
        return self._claw if turn == 0 else self.choose(self._branches)
```

A `Branch` may be `NO_REPEAT` (never twice running), `ONCE` (once a fight), a
number N (at most N running), or `FOREVER`, plus a `cooldown` (not while among
the last c moves) and a `weight`. With every option ruled out the first branch
is taken, as the game's loop does. Enemies choose from the fight's
`monster_ai` stream (their HP rolls from `niche`), so what the players do -
how often they reshuffle, what they make - never changes an enemy's next move.

The helpers: `attack(name, damage, hits=, block=, inflict=, gain=)`,
`buff(name, Status, n)`, `guard(name, block)`, `debuff(name, Status, n)` and
`hand_out(card_id, n)` - all aimed at every player. `HP_RANGE = (32, 35)` rolls
the range once per fight; `NAME` is what the client shows. `on_combat_start`
returns what an enemy does as it arrives (Cubex's 13 Block and Artifact,
Aeonglass's Withering Presence); `same_kind_index` is its encounter slot (two
Nibbits: the front one Slices first, the back one Hisses first).

**What the players see of an intent.** `type`, `name`, `amount` (per hit, as
printed), `hits` and `block` (scaled for the party, what it will actually
gain). `Combat.to_dict()` adds `damage`: for each living player, what one hit
will do to them after the enemy's Strength and Weak and their Vulnerable - the
number the game shows - worked out when the state is sent, so it moves as the
turn goes. The terminal client shows its own player's number and neither the
move's name nor a target, as the game does not.

**Co-op scaling** is real STS2, applied in `Combat.start()`; one player is
never scaled. HP: × player count × act factor (act1 1.1, act2 1.2, act3 1.2,
act3boss 1.3). Block an enemy gains: flat × 2 for two players, × players × act
factor beyond, rounded. Artifact: +1 per extra player. Nothing else scales -
damage, Strength gained, status cards - so each player takes what a solo
player would. `tests/test_scaling.py` checks every registered enemy at 1-4
players. Slippery is also multiplied by the player count, and Plow takes the
same factor as HP, as the game scales them.

**Debuffs on players count down at the end of the enemy turn.** Vulnerable,
Weak and Frail tick at the end of the enemy's turn whoever holds them
(`TICKS_AFTER_ENEMY_TURN`), and one landing on a player skips its first
count-down (`skip_next_tick`, the game's SkipNextDurationTick). So Roar's 3
Vulnerable is there for the next three enemy turns. Tangled and Shrink count
down at the end of their owner's turn, as in the game.

**Artifact** cancels the next debuff aimed at its holder, one charge each; the
resolver does it and nothing is applied, so nothing reacting to a debuff fires.

| Enemy | HP | Pattern (every move hits every player) |
|---|---|---|
| Nibbit | 42-46 | Butt 12 / Hesitant Slice 6 +5 Block / Hiss +2 Str; alone it opens with Butt |
| Snapping Jaxfruit | 31-33 | Energy Orb 3, then +2 Str, every turn |
| Fuzzy Wurm Crawler | 55-57 | Acid Goop 4 / Inhale +7 Str / Acid Goop |
| Assassin Raider | 18-23 | Killshot 10 |
| Axe Raider | 20-22 | Swing 5 +5 Block, Swing, Big Swing 12 |
| Brute Raider | 30-33 | Beat 7 / Roar +3 Str |
| Crossbow Raider | 18-21 | Reload 3 Block / Fire! 14 |
| Tracker Raider | 21-25 | Track (2 Frail) once, then Unleash the Hounds 1 x 8 every turn |
| Leaf Slime (S) | 11-15 | Tackle 3 or Goop (1 Slimed), random, never twice running |
| Leaf Slime (M) | 32-35 | Sticky Shot (2 Slimed) / Clump Shot 8 |
| Twig Slime (S) | 7-11 | Tackle 4 |
| Twig Slime (M) | 26-28 | Sticky Shot (1 Slimed), then random: Pokey Pounce 11 (at most twice running) or Sticky Shot |
| Wriggler | 17-21 | Nasty Bite 6 / Wriggle (1 Infection, +2 Str); slots 1 and 3 bite first |
| Flyconid | 47-49 | random: Vulnerable Spores (2 Vuln, cooldown 3), Frail Spores 8 +2 Frail (cooldown 2), Smash 11; never twice running, never opens with Vulnerable |
| Slithering Strangler | 53-55 | Constrict 3 every other turn (it stacks), Thwack 7 +5 Block or Lash 12 between |
| Vine Shambler | 61 | Swipe 6 x 2 / Grasping Vines 8 + Tangled / Chomp 16 |
| Shrinker Beetle | 38-40 | Shrinker (permanent Shrink while it lives) / Chomp 7 / Stomp 13 |
| Mawler | 72 | Claw 4 x 2, then random: Rip and Tear 14, Claw (neither twice running), Roar 3 Vuln (once) |
| Cubex Construct | 65 | arrives with 13 Block + 1 Artifact; Charge Up +2 Str, then Repeater Blast 7 (+2 Str) twice, Expel Blast 5 x 2 |
| The Insatiable | 321 | Liquify Ground, then Thrash 8 x 2, Lunging Bite 28, Salivate +2 Str, Thrash, repeating from Thrash |
| Aeonglass | 512 | Ebb 26 +33 Block / Eye Lasers 11 x 2 / Increasing Intensity; arrives with 3 Artifact |
| Inklet | 11-17 | three of them; arrives with 1 Slippery; Jab 3, then at random Piercing Gaze 10 or Whirlwind 2 x 3, then Jab again; the middle one opens with Whirlwind |
| Fogmog | 74 | Illusion (calls in an Eye With Teeth), Swipe 8 +1 Str, then Headbutt 14 (60%) or Swipe then Headbutt; then Swipe again |
| Eye With Teeth | 6 | Distract: 3 Dazed into every discard pile, every turn; an Illusion (back at full HP the turn after it dies) and a Minion |
| Phrog Parasite (elite) | 61-64 | Infect (3 Infection into every discard pile) / Lash 4 x 4; dies into four Wrigglers, stunned their first turn |
| Bygone Effigy (elite) | 127 | Sleep, Wake (+10 Str), then Slashes 13 every turn; Slow: attacks on it +10% per card played that turn |
| Byrdonis (elite) | 81-84 | Swoop 17 / Peck 3 x 3; Territorial: +1 Str at the end of every enemy turn |
| Kin Priest (boss) | 190 | Orb of Frailty 8 +1 Frail, Orb of Weakness 8 +1 Weak, Beam 3 x 3, Ritual +2 Str |
| Kin Follower | 58-59 | two, Minions of the Priest; Quick Slash 5, Boomerang 2 x 2, Power Dance +2 Str; the first opens with the Dance |
| Vantom (boss) | 173 | arrives with 8 Slippery; Ink Blot 7, Inky Lance 6 x 2, Dismember 26 + 3 Wounds, Prepare +2 Str |
| Ceremonial Beast (boss) | 252 | Stamp (Plow 150), then Plow 18 +2 Str every turn; at 150 HP the charge breaks - Strength gone, stunned a turn - then Beast Cry (Ringing: one card next turn), Stomp 15, Crush 17 +3 Str |
| Seapunk | 44-46 | Sea Kick 11, Spinning Kick 2 x 4, Bubble Burp 7 Block +1 Str |
| Sewer Clam | 56 | arrives with 8 Plating and 8 Block; Jet 10 / Pressurize +4 Str |
| Haunted Ship | 63 | Haunt (3 Weak, 5 Dazed into every discard) once, then Swipe 13 / Stomp 4 x 3 |
| Sludge Spinner | 37-39 | Oil Spray 8 +1 Weak, then at random, never twice running: Oil Spray, Slam 11, Rage 6 +3 Str |
| Punch Construct | 55 | arrives with 1 Artifact; Ready 10 Block, Fast Punch 5 x 2 +1 Frail, Strong Punch 14 |
| Calcified Cultist / Damp Cultist | 38-41 / 51-53 | Incantation (Ritual 2 / 5: that much Str at each enemy turn's end, from the next), then Dark Strike 9 / 1 |
| Toadpole | 21-25 | Whirl 7, Spiken (+2 Thorns), Spike Spit (Thorns -2, then 3 x 3); the front one opens with Spiken |
| Corpse Slug | 25-27 | two or three; Whip Slap 3 x 2, Glomp 8, Goop 2 Frail, each starting at a different one; Ravenous 4: another enemy dies, it is stunned and +4 Str |
| Fossil Stalker | 51-53 | Latch 12, then at random, at most twice running: Latch, Tackle 9 +1 Frail, Lash 3 x 2; Suck 3: +3 Str per hit that gets through |
| Gremlin Merc | 47-49 | Gimme 7 x 2, Double Smash 6 x 2 +2 Weak, Hehe 8 +2 Str; Surprise: dies into a Sneaky Gremlin (10-14, Tackle 9) and a Fat Gremlin (13-17, flees), both Spawned their first turn |
| Living Fog | 80 | Advanced Gas 8 + Smoggy (one Skill a turn, for good), then Bloat 5 (sets down a Gas Bomb) / Super Gas Blast 8; Gas Bomb 7 HP, a Minion: Explode 8 and it is gone |
| Two-Tailed Rat | 17-21 | three; Scratch 8, Disease Bite 6, Screech 1 Frail - one each to open, then at random; Call for Backup (one more rat) once per rat, three in all, after two moves, while fewer than five |
| Terror Eel (elite) | 140 | Crash 16 / Thrash 3 x 3 +6 Vigor; Shriek 70: down to 70 HP it is stunned, then Terror (99 Vulnerable), then Crash |
| Skulking Colony (elite) | 75 | Hardened Shell 20 (at most 20 HP lost a turn); Zoom 14, Zoom 14, Inertia 9 +2 Str, Piercing Stabs 7 x 2 |
| Phantasmal Gardener (elite) | 26-31 | four; Bite 5, Lash 7, Flail 1 x 3, Enlarge +2 Str, opening on Flail / Bite / Lash / Enlarge; Skittish 6: Block after the first card attack each turn that gets through |
| Lagavulin Matriarch (boss) | 222 | asleep 3 turns behind 12 Plating and Block; a hit through its Block wakes it (stunned a turn); then Slash 19, Disembowel 9 x 2, Slash 12 +12 Block, Soul Siphon (-2 Str -2 Dex on every player, +2 Str) |
| Soul Fysh (boss) | 211 | Beckon (a Beckon into every draw and discard pile), De-Gas 16, Gaze 7 + a Beckon, Fade (2 Intangible), Scream 13 +3 Vulnerable; a Beckon held at the end of a turn costs 6 HP |
| Waterfall Giant (boss) | 240 | Pressurize 15 Steam Eruption, then Stomp 15 +1 Weak, Ram 10, Siphon (heals 10 a player), Pressure Gun 20 (+5 each time), Pressure Up 13, each +3 Steam Eruption; brought down holding it, About to Blow, then Explode for it and dies |

All 22 Overgrowth encounters can now be built (`tests/test_overgrowth.py`
covers the eleven added since the first twenty-one), and all 20 of Underdocks
(`tests/test_underdocks.py`). Summoning: an `InstantSummon` effect goes to
`Combat._resolve` (like `InstantPlayCard`, it needs Combat's ids, scaling and
rng) and brings enemies in scaled, led by the summoner, optionally Stunned or
a Minion. One summoned on the players' turn picks its move at once; one
summoned on the enemies' turn picks it with everyone once that turn is over,
as the game's `AfterCreatureAdded`. A summoned enemy waits for the next enemy
phase to act, as the game walks a snapshot of the lineup.

**Deaths.** `Combat._check_combat_end` resolves them first
(`_resolve_deaths`): the dead enemy's `on_death` (Phrog Parasite's Wrigglers,
the Gremlin Merc's gremlins, an Illusion's return), Minions leaving, and
`GameEvent.ENEMY_DIED` for the others (Corpse Slug's Ravenous) - so the last
enemy dying into others does not win the fight. An enemy still alive after
its `on_death` did not die (Waterfall Giant). `ScriptedEnemy.escape()` takes
one out without a death (Fat Gremlin).

**Dying mid-attack.** A dead dealer deals nothing and a dead target takes
nothing (`Resolver._resolve_instant_damage`, as the game's
`CreatureCmd.Damage`). The dealer is checked once per hit, as `AttackCommand`
does (`Combat._Hits`): a hit lands on everyone it was aimed at, then the
attack stops if Thorns or Flame Barrier killed the attacker. The rest of the
move still happens. A move's hits should carry `effect.hit` (the `attack()`
helper numbers them); unnumbered damage counts as one hit until a target
repeats. A card that picks a random target per hit yields its hits one at a
time, so each picks from the living.

**Minions.** One leaves when its leader dies, and once no enemy of its own
right is left standing (or about to revive), every Minion goes - the game's
CreatureCmd.Kill - so the Kin's followers fall with the Priest.

**Stun.** A stunned enemy shows a Stunned intent and skips its turn; the move
it had lined up is put off to the next turn, not lost, as the game's stun hands
back to it. A stunned arrival (Phrog's Wrigglers) then opens its pattern.

**HP is rolled as an enemy enters**, not when it is built: the session and
summons build enemies with no rng, and `Combat._roll_hp` rolls each from the
Niche stream among the values its range allows that no living enemy already
has - the game's `SetUniqueMonsterHpValue`, so three Nibbits alone are 42-46
all different. As in the game each rolls against the ones before it, which in
co-op already carry their scaled HP, so there two can match. An enemy built
with its own rng (the tests) keeps what it rolled.

**A status can be attack-only.** `StatusEffect.ATTACKS_ONLY = True` means its
`modify_incoming_damage` is consulted for attacks alone — Vulnerable, Exposed
and Colossus Guard — so a Burn, a Constrict or a Wither on a Vulnerable player
deals its printed number, as in the reference. Intangible, Tank and Protected
leave it False and cap or scale every kind of damage. Before this a Burn on a
Vulnerable player dealt 3.

`Dummy1` predates this and still hits every ally at once; it is a test target,
not a model.

## Cards that enemies hand out

- **The Insatiable** - Liquify Ground gives every player 4 `sandpit` and six
  `frantic_escape`: three shuffled into the draw pile at random depths, three
  in the discard. Sandpit counts down at the start of each enemy turn, as the
  game's does, and kills at 0 - so with 1 left the players still get that
  whole turn. A Frantic Escape adds 1 and costs 1 more for the combat.
- **Aeonglass** - Increasing Intensity upgrades every Wither already in play,
  then hands every player a Wither at that level, then gains 3 Strength (4 the
  next time, 5 after). A Wither deals 3 +3 per upgrade (`CardRef("wither",
  bonus_damage=3 * level)`). Withering Presence, on every player from the
  start, puts a Wither in their hand every 6 cards they play. The client sees
  only `"wither"`; the level is not on the wire yet.
- **Leaf / Twig Slimes** - `slimed` into every player's discard.
- **Wriggler** - an `infection` to every player.

Self-inflicted status damage (Burn, Toxic, Wither, Infection, Decay,
Disintegration) is `is_attack=False`, as in the reference: it meets Block but
takes no Strength and triggers nothing that reacts to being attacked. A card
held at end of turn reacts to **its holder's** `TURN_END` only — `TURN_END` is
emitted once per player, and the hand walk used to run for every emission, so
a Burn dealt 2 per player in the fight. Found by the Wriggler's Infection.

## The Ironclad pass: matching the installed game

`tests/game_diff.py` reads the game's own card classes (decompiled from
`sts2.dll`, v0.107.1) and compares every Ironclad card with ours. All 87 match
on cost, values, upgrade, keywords, type, rarity and target. The behaviour
changes that came with it, each copied from the game's code:

- **Cruelty is added to Vulnerable, not multiplied after it**, and only for
  the holder's attacks: 6 into Vulnerable is 6 x (1.5 + 0.25) = 10. The card
  applies 25 (50 upgraded) and copies stack. `Vulnerable.modify_incoming_damage`
  reads the attacker's `cruelty`.
- **Tank doubles attack damage on the tank** (was 1.5x) and gives teammates
  half damage from attacks (`protected`, the game's Guarded), which ends when
  the tank dies. Neither touches damage that is not an attack.
- **Aggression stacks**: `amount` Attacks pulled a turn.
- **Thrash hits first, then eats** a random Attack and keeps its damage (with
  your Strength) on that copy for the combat, like Rampage.
- **Expect a Fight** is the game's card: 1 Energy per Attack in hand, then
  `no_energy_gain` for the turn (energy gains from effects become 0).
- **Forgotten Ritual** only pays if you exhausted a card earlier this turn.
- **Burning Pact, Brand and True Grit+ ask** which card to exhaust.
- **Havoc / Cascade** play from the top with a reshuffle (see HANDOFF.md);
  Cascade+ plays X+1. **Howl from Beyond** replays itself from the exhaust
  pile at end of turn. **Unrelenting / One-Two Punch** are visible statuses.
- **Stone Armor is a Power**, and three rarities moved (Bloodletting common,
  Dominate and Taunt uncommon).

## The other cards: colorless, event, status, curse

`tests/game_diff.py` now reads every pool a card here can come from (Ironclad,
Colorless, Event, Status, Curse, Token; `python tests/game_diff.py Colorless`
for one). 206 cards match exactly; 5 differ on purpose (Void stores its Energy
loss as -1; the four Act 2 Knowledge Demon choices are deck cards here); 11
are left out with a reason (Alchemize, Mad Science by hand, other characters'
tokens). Each card's play code was then read beside ours; what changed:

- **Values.** 22 colorless cards are Rare, not Uncommon, and Splash Uncommon;
  the 18 Event cards are Event.
  Beacon of Hope costs 1, Whistle 3, Rend 2 (15 + 5 per debuff, 18 + 8
  upgraded), Mind Blast+ 0, Entrench+ 1. Knockdown+ deals 14 and multiplies by
  3. Maul grows by 1 (2 upgraded). Relax: 15 Block (17), then 2 cards and 2
  Energy next turn (3 and 3); Outmaneuver 2 Energy (3). Panache 10 (14), The
  Bomb 40 (50), Giant Rock 16 (20). Toxic is playable for 1 and Exhausts.
- **A random card** (`generatable_card_ids`) is never an Event card (new
  `CardRarity.EVENT`), never one the game will not make in a fight (Feed, Hand
  of Greed, Hidden Gem: `Card.GENERATED_IN_COMBAT`), and in a solo fight never
  a co-op card (`Card.MULTIPLAYER_ONLY`; `Context.solo`). **Transform** has its
  own pool (`transform_card_ids`): a Status into another Status, a Curse into
  a Curse, anything else into a Common/Uncommon/Rare of its own pool.
- **Stacked powers do more, not longer**: two Calamities add 2 Attacks, two
  Mayhems play 2 cards, Hello World adds `amount` different Commons, Entropy
  and Stratagem take `amount` cards, Automation gives `amount` Energy. The
  game's instanced powers keep one count per copy played: Panache (counts from
  when it is played, resets each turn, unpowered damage), The Bomb (own fuse
  and damage), Rolling Boulder (each grows by 5), Automation, Knockdown (two
  players' multiply; neither doubles its own attacks).
- **Next-turn Energy and draw** (`delayed_energy`, `delayed_draw`) are an
  amount paid once, as EnergyNextTurnPower / DrawCardsNextTurnPower.
- **Panic Button** stops only a card's own Block: Entrench's doubling, a
  power's Block and a teammate's Beacon of Hope still land (NoBlockPower).
- **Gang Up** pays per hit a teammate landed this turn (a Twin Strike is two);
  **Gold Axe** counts every card the team played this combat.
- **Intercept targets one player** and covers only them (CoveredPower). Every
  enemy attack hits every player, so redirecting the covered player's hit
  gives the game's numbers (covered 0, interceptor x2).
- **Tag Team** goes off for an attack on the marked enemy or one at every
  enemy, not a random-target one (TagTeamPower).
- **Enlightenment** caps the copies in hand at 1, this turn or until each is
  played; upgraded, for the combat (`InstantCapCost`, `CardRef.turn_cost_cap`
  / `cost_cap`). A card drawn afterwards costs what it costs.
- **Upgrades skip Statuses and Curses** (`can_upgrade`): Armaments, Apotheosis
  and the rest. Apotheosis reaches the exhaust pile too.
- **Anointed** takes random Rares up to the hand's room; **Catastrophe** plays
  one card at a time, a playable one over an Unplayable; **Hidden Gem** picks a
  playable non-Curse, an Attack/Skill/Power over a Status; **Jackpot** adds
  cards printed at 0 (upgraded if it is), not cards made free; **Jack of All
  Trades** adds different cards, never itself; **Discovery and Splash** may be
  skipped, and Splash+ offers upgraded Attacks; **Nostalgia** counts every
  Attack or Skill played, Exhausted or not.
- **Bolas and Thrumming Hatchet** go to the discard pile like any card and are
  taken back next turn from whatever pile they are in.

Then the last differences, each from the game's code:

- **Free means that copy.** Discovery, Splash, Distraction, Infernal Blade and
  Mad Science make the card they add cost 0 this turn or until it is played;
  Metamorphosis for the whole combat, every time it is played (`free_copy`,
  the same per-copy cap as Enlightenment; `Ally.free_this_turn` and
  `free_this_combat` are gone). As in the game, Tangled still adds its 1 on
  top, and a free X card still spends all your Energy.
- **Normality, Sloth and Ringing count plays started** (`cards_started`, the
  game's CardPlaysStarted) and stop a card that plays itself too: past the
  cap it goes to its pile unplayed (Havoc as your third card turns up nothing).
- **Tag Team keeps one mark per player** (`marks`): two players' marks are two
  extra plays for a third player, and each is set off only by somebody else.
- **Two Beacons of Hope answer each other once**: Block carries the Beacons it
  came through (`beacons`), as the game's HasAlreadyBeenGivenBlock.
- **Before the hand is drawn** (new `GameEvent.BEFORE_HAND_DRAW`, the game's
  BeforeHandDraw): Hello World's cards and a returning Bolas or Thrumming
  Hatchet arrive first, so they take hand room and are never drawn.
- **Only a new Vulnerable, Weak or Frail skips its first count-down** on a
  player (PowerCmd.Apply): added to one already held, it ticks with it. So
  Doubt on a Weak player is 3 down to 2, not a held 3.

Tests: `tests/test_colorless_game.py` (32 of its checks fail on the old code).

## Player choice

Fifteen cards and two powers (Entropy, Stratagem) stop mid-resolution and
ask the player a question. The machinery is one method:

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

Four things worth knowing before adding another:

- **Options are worked out when the question is put, not when it is queued.**
  Pass a callable when they come from a pile. Purity queues three questions at
  once; without this the second would offer the card the first just exhausted.
- **A question raised mid-action is answered after the action finishes.** A
  card can ask from `get_effects`, from `follow_up` (Thinking Ahead, whose
  question only exists after the draw), or from a status's `on_event`
  (Stratagem, on a reshuffle).
- **What comes after the choice goes inside the answer.** Burning Pact
  exhausts and then draws; if the draw were returned from `get_effects` it
  would resolve first, and the player could exhaust a card they just drew.
  So `exhaust(chosen)` returns the exhaust and then the draw. Brand does the
  same with its Strength.
- **Each player holds one question at a time**; the rest of theirs wait in
  order behind it, so a card's questions arrive in the order it asked. The
  other player is not blocked and may be holding a question of their own. The
  turn will not advance until every question is answered - and a player who
  disconnects has theirs answered for them (`forfeit_choices`), or it never
  would.
- **"Up to N" questions can be stopped.** Purity (0 to 3) and Neow's Fury (0
  to 2) ask with `can_stop=True`, as the game's selector allows zero picks
  there. Answering `PendingChoice.STOP` (-1) picks nothing; the answer is
  never resolved, so the card asks nothing further. Every other question
  refuses -1. A headless run still picks at random and never stops.

On the wire: `choice_required` goes privately to whoever must answer, `choose`
carries `option_index` back (-1 to stop), and `to_dict()["choices"]` carries
the same thing for any client that missed the message. Each question carries
`can_stop`.

True Grit asks only when upgraded: the base printing really is "at random",
and the game's code chooses for you there. Armaments asks unupgraded and takes
the whole hand upgraded, again as the game does.

## The optional plugin

The server can take one plugin, which tells players from the agent, shapes
what each client receives, and watches the fight as it happens - the hook
for the Characteristic Analyzer and the agent's format. **The game never
needs it**: with no plugin file everyone gets the player format and nothing
else changes.

**Where it lives.** `config.PLUGIN` names a module under `Server/Plugins/`
(`"Plugins.aura"` by default; `None` turns it off). The module provides
`create_plugin()`, returning an object; `plugin_host.load_plugin` loads it at
startup and `Session(plugin=...)` takes it. No file, an import error, no
`create_plugin`, or one that raises: the server says so on its console and
runs without a plugin.

**Who is who.** A client may send `identify` with `{"role": "agent"}`. The
session keeps it in `session.roles` (a client that never identifies is
`"player"`) and answers with the current state, in that client's format. A
human client never needs to send it, and without a plugin it changes nothing.

**What the plugin may define** - all optional, each given the session first,
so it can read `session.combat`, `session.players` and `session.roles`:

| Method | When | Given |
|---|---|---|
| `format_message(session, recipient, role, message)` | every message, per recipient | a copy of the player-format message. Return the message to send, or `None` to send that client nothing |
| `on_identify(session, unit_id, role)` | a client identified | |
| `on_combat_start(session)` | the fight has begun | |
| `on_turn_start(session)` | the players' turn has begun (turn 1 included) | `session.combat.turn_number` |
| `on_action(session, action)` | a play or an answer went through | see below |
| `on_turn_ended(session, unit_id)` | a player ended their turn, **before** the turn can move on | the state they ended in - the last player's too |
| `on_round_end(session)` | everyone has ended; the enemies are next | |
| `on_player_left(session, unit_id)` | a player left mid-fight | `session.combat.unattended` |
| `on_combat_end(session, result)` | once, at the end | `"VICTORY"` / `"DEFEAT"` |

`action` for a play: `action: "play"`, `unit_id`, `card_id`, `upgraded`,
`hand_index`, `target_id`, and the card as it stood in hand just before -
`cost` (`"X"` for X-cost), `damage` (`hand_damage`), `block`
(`hand_blocks`), `energy` - then `results`. For an answer: `action:
"choose"`, `unit_id`, `prompt`, `option_index`, `option` (`None` when they
stopped an "up to N" question), `results`. One call per action a player
chose: cards played by other cards (Havoc, Mayhem) come inside `results`.

**What the server promises.**
- No plugin: every message goes out exactly as the player format has it,
  broadcasts and all.
- With one, a broadcast is split per player so each copy can be shaped for
  its recipient; `format_message` gets a copy, so reshaping one cannot
  change another.
- A plugin that raises is reported on the console and the game carries on:
  a failing hook is skipped, a failing `format_message` sends that message
  in the player format.
- Everything handed to the plugin is in game units - HP, Block, damage,
  costs, status amounts. **Normalizing for a network (tanh, soft scales,
  one-hots) belongs to the AI's side**, not to the plugin or the server.

**`Plugins/aura.py`** is the plugin `config.py` names. For now it does one
thing: a client that identified as the agent gets a descriptor for every card
- `hand_cards` and `deck_cards` on each player, the descriptor fields on each
pile entry, `option_cards` on a question - built by `Plugins/card_groups.py`.
A descriptor is `id`, `upgraded`, `type`, `cost`, `target`, `keywords`,
`damage` (per hit), `hits`, `block`, `statuses` (what it applies, by scope:
`self` / `target` / `all_allies` / `all_enemies`) and `groups` (`now`, `scale`,
`team`, `self`). In hand, cost, damage and Block are what the hand shows now;
out of hand, the printed cost and the card's own damage and Block. Every other
client gets the player format untouched. A new status needs a role in
`card_groups.STATUS_ROLES`, or `tests/test_card_groups.py` fails.

The agent also gets its actions as one fixed menu (`Plugins/action_space.py`),
with every state and every `ready_changed`: `action_mask`, 113 numbers, 1
where that action is open now, and `action_targets`, the unit in each target
slot. Menu: 0-99 play, `10 x hand slot + target slot`; 100 end turn; 101
wait; 102-111 answer option 0-9; 112 stop. Target slots: 0 none (the card
picks its own), 1-6 the living enemies in fight order, 7-9 the other players
in seat order. The mask is `legal_actions` laid onto the menu, and
`action_space.decode` turns an index back into the message. A question with
more than 10 options shows its first 10; the agent's divide-and-conquer card
choice runs its own rounds and sends the winner's real `option_index`.

It is also the Characteristic Analyzer (`Plugins/analyzer.py` has the
arithmetic): every player who is not the agent is profiled on Aggression,
Scaling and Teamwork, scored at each round end from that turn's history, and
the agent's state carries `profiles`, `{unit_id: {A, S, T, cA, cS, cT}}`.
Each scored turn writes two lines to the combat log: `analyzer_input`, the
analyzer's input - the spec's History: `energy`, `hand`, `used`, `opp`,
`incoming`, `block`, each card with its `id`, `upgraded`, `cost`, `dmg`,
`block` and `groups` - and `profile_update`: the evidence, its weight, the
context numbers and the profile. `python -m Plugins.history_export <log>`
(from `Server/`) writes the input per teammate in the MockUpRB prototype's
format, `[E_total, Used, Opp, D, B]` with each card `[cost, dmg, block,
groups]`. That is also what the teammate's `CharacteristicAnalyzer` package
(`2nd_model/CharacteristicAnalyzer`) takes: `python -m Plugins.ca_feed <log>` feeds each turn to it and
prints its profile beside ours (the same, at the same β; ours is 20 too).
`python -m Plugins.ca_plot <log>` draws CA's profile: `<log>_ca.html` next to
the log, per player the traits A, S, T by turn and, in a chart of its own,
CA's confidence in each - one page, no libraries, opens in any browser.
A log written without this plugin has no such lines; these three then make
them by replaying the fight with the plugin on (see Turns, under the combat
log).

**Scripted teammates** (`Plugins/teammates.py`): five bots that play from
`legal_actions` - aggressive (damage first), defensive (Block first), scaling
(Powers first), team (cards for the team first) and random. A styled bot plays
its own cards first and then the rest it can afford. `python -m
Plugins.teammates [fights]` (from `Server/`) plays every pairing on one deck
against Act 1 enemies, through the session with this plugin, and prints what
the analyzer made of each style; `tests/test_teammates.py` checks that each
stands out on its own trait.

**For human players** the effects message now says what happened (`action`,
`card_id`, `upgraded`, `target_id`; `option` for an answer), so the terminal
client prints "p2 played bash+ on e1", and each player in the state carries
`ended_turn`, shown as "(ended)". `tests/test_plugin.py` covers loading, the
no-plugin path, identify, every hook in order through a fight, per-recipient
formats and a plugin that crashes.

## The combat log

Every fight is written to `config.LOG_DIR` (`2nd_model/logs/`, which git
ignores; `None` turns it off), one file per combat named
`combat_<date>_<time>_<seed>.jsonl`: one JSON object per line, flushed as it
goes, so a crash keeps everything up to it. Each line has `seq`, `time` and
`event`. The events, and what each carries, are listed at the top of
`Server/combat_log.py`: joins, identify, `combat_start` (seed, act, enemies,
each player's deck, full state), `turn_start` (state), every `play` (the
card's cost, damage and Block before, and its results) and `choose`,
`end_turn`, `wait`, `round_end`, `refused` (the message and why), `error` (an
unexpected exception, with its traceback), `left`, and `combat_end` (result
and final state). Each play, answer, end turn and wait also carries
`legal_actions`, what was open instead; an answer carries the `options` too.

**Agent decisions and profile updates.** Any action a client sends may carry
a `decision` field - an agent's action probabilities, say. The game ignores
it and the log keeps it on that action's line. A plugin adds its own lines
with `session.log_event(event, **data)` (`"profile_update"`, for instance).

**Replay.** The session now always has a seed (`Session(seed=...)`, or one it
picks itself; a caller that passes its own `rng` keeps it and logs no seed).
`combat_log.replay(lines, Combat)` sets the same fight up from
`combat_start`, sends the recorded actions again, and compares every turn's
state and the outcome with the log; `python combat_log.py <file>` does it
from `Server/`. A replay needs the same cards, enemies and decks as the
recording, and says so first when a deck differs. `tests/test_combat_log.py`
logs whole fights (one with a player leaving), replays them exactly, and
checks that changing one recorded action is caught. A log that cannot be
written is reported once and the fight goes on without it.

**Turns.** `python -m Plugins.turn_export <log> [out.json]` (from `Server/`)
groups the raw lines into turns: per turn, the state it began with and each
player's moves (play, choose, end turn, wait, refused, left) in the order
they made them, each its log line less `time`, `unit_id` and `role`, with its
`seq` showing how the players' moves fell together. It prints the fight a
turn at a time ("Bash -> e1  8 to e1 (79 HP left), vulnerable 2 on e1") and
writes the whole of it to `<log>_turns.json`. Each player's turn also holds
the aura plugin's `analyzer_input` and `profile_update` for it. A log written
without the plugin gets them rebuilt (`history_export.load` / `rebuild`):
`combat_log.replay` now takes a `plugin` and a `log` (`MemoryLog`, lines kept
in a list), so the fight is played again from its seed with the plugin on.
The rebuilt lines are marked `rebuilt`, the profiles are at today's beta, and
they stop at the first move the replay could not make the same way (another
card, or one refused), since past it the replay is another fight; a note says
which. Tests: `tests/test_turn_export.py`.
