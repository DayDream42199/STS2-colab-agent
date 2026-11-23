# Collaborative Agent: MaskablePPO training

Trains the Collaborative Agent (seat 0) with MaskablePPO and Final_reward_norm.
Inputs (15,046), actions (106) and masks follow `agent_input` / `agent_output` exactly.

## Setup (Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python test_env.py
```

## Reward: Final_reward_norm (default), paid as the change each step
```
Score_t = 100 - General_penalty_t
r_t     = 1/100 * (Score_t - Score_(t-1))
        + 1/50  * (Collab_t - Collab_(t-1)) * (1 - min(CTime / DTime, 1) * CDecay)
```
Code: `collab_agent/final_reward.py`.
- **The score** is read every time the agent is asked to act, and once more when the fight ends; each step
  is paid the change since the last read. Over a fight that adds up to (final score - starting score) / 100,
  however many steps it took, so a fight is never paid more for being long.
- **General penalty**: A + B + C + D = 100, and E (turn count) on top, so the score can dip below 0.
  A is charged only on the read where the fight is lost. E must stay below A + C/4 (then any win beats
  any loss with up to 4 players): `PenaltyWeights.check()` refuses anything else.
  "Allies" means the whole team, the agent included. Hitting the round limit (30) counts as a loss.
  `--team-penalty B_team,C_team` puts teammates on their own weights: B and C are then the agent's own HP and
  knockout, A + B + C + D + B_team + C_team = 100, and E < A + min(C, C_team / 3). Scores made on different
  weights don't compare, so every fight also logs `fight/score_std` (the default weights), `fight/mates_alive`
  and `fight/self_alive`.
- **Collaborative scoring** is given on the step where each event happens. All are measured in every fight,
  each at its own starting weights (`DEFAULT_WEIGHTS`), whichever one trains the agent (`f_train`).
  - `baseline`: 0.1 x Vulnerable applications (offense); 0.2 / allies x sum(A_i x min(c_A_i + 0.5, 1) x Block given to ally i)
    + 0.1 x Weak applications (defense). A_i and c_A_i are the ally's profile at that moment.
  - `variant1`: bonus enemy HP teammates removed because of the agent's Vulnerable (offense), and teammate HP
    saved by its Weak and its Block (defense), in % of the enemy / ally HP pool. When several players applied
    the same debuff, the agent gets its share of the stacks. The agent's Block on a teammate is counted as used last.
  - `variant2` (cash-in counts): 0.1 x teammates' hits on an enemy with the agent's Vulnerable (offense);
    0.1 x enemy hits where its Weak still saved a teammate HP + 0.1 x enemy hits its Block soaked up (defense).
  - `variant3` (complement): each round, for each teammate, -A_i x e_A x w_A - S_i x e_S x w_S
    + max(0, -T_i) x max(0, e_T) x w_T, each times min(c + 0.5, 1); e and w are the analyzer's evidence and
    weight for the agent's own turn (others).
  - `variant4`: variant2's offense and defense with variant3's complement.
  - add more scorings to `SCORINGS` (and their starting weights to `DEFAULT_WEIGHTS`) in `final_reward.py`.
- **CTime** is the training timestep (sent to the envs at every rollout); **DTime** = 0.5 x total timesteps.
- **Advantage point** = the agent's mean score with the teammates' true profiles minus its mean score with
  each teammate's A, S, T swapped for the style furthest from theirs (`styles.py`), on the same fights
  (`evaluate.py`). Above 0, the agent plays better when it knows who its teammates really are.
  g_n = advantage(agent trained with f_n) - advantage(agent trained with the baseline).
  `assist_share` (variant1's offense) is the same ruler for every agent.

## Train
```
python train.py                                                  # defaults below, 2M steps
python train.py --penalty 45,20,20,15,10 --turn 6,10,0.35        # A,B,C,D (= 100), E on top  and  a,b,c
python train.py --scoring variant2 --cdecay 0.5                  # f_n at its starting weights, CDecay
python train.py --scoring variant1 --collab-w 0.4,0.2,0          # or your own w_offense,w_defense,w_others
python train.py --collab-w 0,0,0                                 # collaboration off
python train.py --timesteps 5000000 --n-envs 8 --subproc         # faster on a multi-core PC
python train.py --reward-mode weighted --reward-config reward_weights.json   # the earlier weighted reward
tensorboard --logdir runs
```
Defaults: penalty 45,15,25,15,5; turn 6,10,0.35; scoring baseline at 7,2,0; CDecay 0.5.
Starting weights (a fight's collaborative part about 0.03 - 0.06): baseline 7,2,0; variant1 0.2,0.2,0;
variant2 3,3,0; variant3 0,0,3; variant4 3,3,3.
TensorBoard shows `reward/general`, `reward/collab`, each penalty part (`reward/pen_A` ... `pen_E`),
`reward/f_baseline` ... `reward/f_variant4`, `reward/f_train`, and `fight/win`, `fight/ally_hp_frac`,
`fight/rounds`, `fight/score`, `fight/assist_share`.

## Experiments
```
python experiments.py all --dry-run            # list the settings first
python experiments.py bc --timesteps 1000000
python experiments.py ad
python experiments.py e
python experiments.py turn
python experiments.py collab
python experiments.py cdecay
python experiments.py all --subproc
```
| stage | what changes | others fixed at | best = |
|---|---|---|---|
| bc | B vs C: (45,15,25,15) ... (45,35,5,15), E 5 | turn 6,10,0.35; collaboration off | win rate > ally HP left > fewest turns |
| ad | A vs D: (45,15) ... (25,35) | best B, C; collaboration off | same |
| e | E = 5, 10, 20 | best A, B, C, D; collaboration off | same |
| turn | shift, width, sharpness (7 settings); skipped if the best E < 10 | best penalty; collaboration off | same |
| collab | 5 scorings x weights (15 settings, `COLLAB_SETS`) | best penalty + turn, CDecay 0.5 | gate, then advantage point > assist share |
| cdecay | 0, 0.25, 0.5, 0.75, 1.0 for the best 2 of collab | best of all above | same as collab |

- Each stage saves its best (and top 3) to `runs/experiments/best.json`; the next stage starts from it.
- The gate (collab, cdecay): a setting whose score falls more than `--score-gate` (2) points below the
  stage 1 winner's goes last, since helping must not cost the team.
- Two settings tie on a number when they differ by less than `--tie` (0.02 for win and HP) or `--adv-tie`
  (2 points of advantage), or by less than the spread between their seeds. Default seeds: 0,1,2.
  The advantage point is noisy: a fight's score spreads about +-35 points, so with 500 fights a side it
  carries about +-2 points of noise, and with 40 (a quick `evaluate.py`) about +-8. Judge it on many fights.
- Finished runs are skipped, so a stage can be stopped and continued; a setting met again in a later stage
  (a winner carried forward, CDecay 0.5) reuses its result (`runs/experiments/index.json`).
- Results per stage: `runs/experiments/<stage>_results.csv`, with g_n against the best baseline setting.

## Evaluate
```
python evaluate.py runs/collab_agent/final_model.zip --baselines
```
Prints win rate, ally HP left, fight length, score and advantage point against each teammate type,
next to a random agent and the Cheese bot playing the agent's seat. Each team is played twice on the same
fights (true and swapped profiles); a policy that never reads the profiles, like those two, gets exactly 0.
The styles' usual profiles are worked out once (about a minute) and kept in `runs/style_profiles.json`.

## Ablation: do the profiles help?
```
python train.py --out runs/with_profiles
python train.py --zero-profiles --out runs/no_profiles
python evaluate.py runs/with_profiles/final_model.zip
python evaluate.py runs/no_profiles/final_model.zip
```

## Specialists: is adapting worth anything?
```
python train.py --engine real --teammates aggressive --collab-w 0,0,0 --out runs/spec_aggressive
python train.py --engine real --teammates defensive --collab-w 0,0,0 --out runs/spec_defensive
```
Each agent trains next to one kind of teammate, on the fight score alone. Then play both next to both kinds:
if each does better next to its own kind than the other agent does there, the best play depends on the
teammate, and that gap is about the most a profile could add.

## Files
```
collab_agent/config.py       constants, input layout, RewardWeights, EnvConfig (difficulty, team settings)
collab_agent/cards.py        mock card set + Analyzer tags (scale/now, team/self)
collab_agent/engine.py       mock combat engine (stand-in for your Game Engine)
collab_agent/real_engine.py  the same interface on 2nd_model's engine (--engine real)
collab_agent/bots.py         scripted teammates: aggressive, defensive, cheese, random, change, support,
                             blend (its own random mix per bot), continuous (aggressive with probability x,
                             else defensive; x uniform per bot), and scale, now, self, team (cards with that
                             analyzer tag first, then anything): only with --teammates, or evaluate's 2x teams
CharacteristicAnalyzer/      your Characteristic Analyzer package (the 2nd_model copy: takes Block at turn end)
collab_agent/analyzer.py     bridge to the package: history format, one profile file per env and seat
collab_agent/observation.py  Normalization: state -> 15,046 numbers
collab_agent/env.py          Gymnasium env: mask, Divide and Conquer, wait, reward
collab_agent/final_reward.py Final_reward_norm: general penalty, collaborative scorings, CDecay, advantage point
collab_agent/styles.py       each teammate style's usual profile, for the swapped-profile test
collab_agent/model.py        shared card reader + trunk (--network flat, the default)
collab_agent/pair_policy.py  one scorer for every card-and-target pair (--network pair)
train.py / evaluate.py / experiments.py / test_env.py / test_real_engine.py
```

## Characteristic Analyzer
Teammate profiles come from the `CharacteristicAnalyzer` package (import the folder, use the `_api` functions):
- new team -> `CA.newProfile(name, name, overwrite=True)` for each teammate
- end of every round -> `CA.updateProfile(name, [E_total, Used, Opp, incomingDamage, blockAtTurnEnd])`,
  and the returned A, S, T, c_A, c_S, c_T go into that teammate's player slot
- every card in Used and Opp carries the values it showed in hand (not the HP it actually took off)
- `incomingDamage` and `blockAtTurnEnd` are read when the player ends the turn; the package takes off the
  Block that did not come from their own cards (start of turn, teammates' Block):
  `I = incomingDamage - (blockAtTurnEnd - Block of the used cards)`
- a player knocked out is not scored again: their last turn is handed over once
- the agent's own turn is scored without a profile (`analyzer.turn_evidence`) for `variant3`
- beta is set inside the package (`Internals/CharacteristicUpdate.py`)

To use a newer version of the package, replace the `CharacteristicAnalyzer` folder.

## Settings worth knowing (`EnvConfig`)
- `engine = "mock"`: or `"real"` for 2nd_model's engine; then `real_ally`, `real_extra_cards = 4` and
  `real_pool_weights = (0.7, 0.2, 0.1)` (hallway, elite, boss) set up its fights. `real_deck` (`--deck teamwork`)
  gives every seat one whole deck instead of random extra cards; `--pool-weights` sets the fight mix.
- `real_deck_presets = None` (`--deck teamwork --deck-presets Whole,Default,Small,Bloated,Helper`, real engine): each new
  team is dealt one of these kinds of deck, drawn at random. `Whole`: every seat the whole deck. A preset
  (`real_engine.DECK_PRESETS`, the same as the playtest's): each seat its own deck, that many cards of each kind, drawn
  from the whole deck's cards. Repeat a name to make it more common. Off: every seat the whole deck. `Pool`
  (`real_pool_cards = 8`, `--pool-cards`): each seat the starter and that many cards from every Ironclad and co-op card.
- `history_fights = 0` (`--history-fights`): fights a new team plays before the agent meets it (the Cheese bot in
  its seat), so its profiles start built. 0: they start fresh.
- `no_wait = False` (`--no-wait`): a test of what a profile is worth when the agent has to move before seeing its
  teammates' plays: no Wait, and teammates never act first. Their hands stay visible, so hand and profile together
  are its clue to what they will play.
- `blind_teammates = False` (`--blind-teammates`): the same, and their hands and piles are hidden too. Their health,
  Block, energy and statuses stay visible. Neither is the game's real rules.
- `network = "flat"` (`--network pair`): `flat` is the shared card reader and trunk with one output per action. `pair`
  (`collab_agent/pair_policy.py`) scores every card-and-target pair with one small network, on the card's summary, the
  target's summary and the whole situation, so an example of a card teaches every hand slot and every teammate, and two
  teammates swapped in the input swap their scores. The input, the actions, the masks and the trainer are the same, and a
  saved run loads whichever it was trained with.
- `card_effects = False` (`--card-effects`, real engine, `--network pair`): each card in the input also shows what its
  damage, Block and statuses don't (`config.EFFECT_NAMES`): HP it costs, healing, energy and cards drawn, the same for a
  teammate, and whether it exhausts, adds, moves, improves or plays cards. Read once per card from the same sandbox play
  `card_groups.card_info` uses (`real_engine.card_effects`), in a block after the piles, so the rest of the input is
  unchanged and runs trained without it load and play as before. Without it, 16 pool cards look exactly like another one.
- `enemy_statuses = False` (`--enemy-statuses`, real engine, `--network pair`): the input also shows the Act 1 enemies'
  own statuses that `config.STATUS_LIST` lacks and so drops (`config.ENEMY_EXTRA_STATUSES`: the Waterfall Giant's Steam
  Eruption, the size of its blast to come; Lagavulin's and the Bygone Effigy's Asleep; Slow, Hardened Shell, Territorial,
  Shriek, Skittish, Plow, Ringing, Slippery), 10 numbers per enemy in a block at the very end, after any card effects,
  read with that enemy. The rest of the input is unchanged and runs trained without it load and play as before.
- Scripted teammates never play a card whose HP cost would knock them out (`bots._kills_itself`: Bloodletting, Offering,
  Hemokinesis, Blood Wall, Brand, Breakthrough at low HP); before, with pool cards, they did about once in 20 fights. Only
  the random bot and the blend bot's mistakes still can. The trained deck has no such card, so its fights are unchanged.
- `sort_teammates = False` (`--sort-teammates`): the agent's input and its target numbers list teammates by danger,
  worked out again at every decision. Slot 1 is the teammate with the least HP left after the hits coming at them,
  knocked-out teammates come last. Their numbers, hand and piles move with them, and `env.target_seat` turns a slot back
  into a seat. Off: by seat, where agents tend to pick a favourite seat whoever is in danger.
- `start_hp = None` (`--start-hp 100,75,50,25,10`, real engine): at each fight start, each player's HP is drawn
  separately from these percentages of max HP, so the agent plays hurt and has to choose who to protect. Repeat a
  percentage to make it more common. A fight is still one episode, and the reward pays only for what changes after
  the fight starts. Scores include HP already missing at the start, so compare them only at the same starting HP.
  Off: everyone starts full.
- `team_fights = 10`: a team stays together for 10 fights and profiles carry over between them.
- `max_rounds = 30`: a fight that reaches this many rounds counts as a loss.
- `profile_dir = "runs/profiles"`: where the package saves profile JSON files (one per env and teammate seat).
- `teammate_lead_prob = 0.3`: chance each teammate acts before the agent at turn start.
- `swap_profiles`, `style_profiles`: the advantage-point test (evaluation only): the agent is shown each
  teammate's A, S, T as the style furthest from theirs; confidence and the reward stay true.
- `enemy_hp_per_player = 125`, `enemy_atk_per_player = 15`: difficulty. At these values a random agent
  wins about half its fights and the Cheese bot about three quarters.

## The real engine (2nd_model)
`collab_agent/real_engine.py` runs the same env on 2nd_model's engine instead of the mock:
```
python test_real_engine.py                          # checks, about a minute; nothing is trained
python train.py --engine real
python experiments.py all --engine real --subproc   # results in runs/experiments_real/
python evaluate.py runs/collab_agent/final_model.zip --engine real --baselines
```
It looks for `2nd_model/Server` next to this folder; set `STS2_SERVER` if it is elsewhere.
- **Fights**: Ironclads (the starter deck plus `real_extra_cards` cards from every Ironclad card and the
  co-op cards), against the Act 1 lineups in `real_engine.py` (`HALLWAY`, `ELITES`, `BOSSES`, picked by
  `real_pool_weights`), with co-op enemy scaling. Every card works, questions included (one pick at a
  time, "up to" ones with Stop, through Divide and Conquer); every enemy attack hits every player.
- **Turns** are simultaneous, as in the game: the round ends once every player still standing has
  ended. The env's wait, teammate lead and bots work as with the mock. Bots answer questions with the
  first option (the random bot at random).
- **Analyzer input** comes from 2nd_model's aura plugin hooks: the same turn records a real game logs.
- **Cards**: `real_engine.BLOCK_TO` says where Block goes when a card's target doesn't: Lift's is all the teammate's
  (`Combat.hand_blocks` has no number for it, as it shows what the holder gains), Intercept's is the holder's and the
  teammate is only covered. Agents trained before this saw Lift as a blank card and Intercept as Block on the teammate,
  and the bots saw Lift as no Block, so their results don't compare with later runs. Energy and card draw have no slot in
  a card's input (Believe in You still reads as blank), and Demonic Shield and Mimic show no Block number.
- **Rewards**: the general penalty reads the real state. For the collaborative scorings the adapter
  keeps who applied each enemy's Vulnerable and Weak (stacks per player, from each action's results),
  the agent's Block given, teammates' hits on its Vulnerable (the bonus HP is the hit with the
  Vulnerable multiplier undone, rounded up), and - from the intents, just before each enemy turn - the
  HP its Weak and its Block will save each teammate. These last two are worked out ahead of the
  enemy turn, so a hit the turn changes (Intercept, Thorns) is not counted differently.
- About 90 steps a second per env with a random agent (the mock is faster); use `--subproc`.
- Statuses the input list does not have (some enemy-only ones added since) are left out of the input.

## Plugging in another engine
`env.py` and `observation.py` only use these parts of `engine.Combat` (`real_engine.RealCombat` has them all):
- state: `players[4]`, `enemies[6]` (None if empty), `turn`, `result`, `stats`, `finished_histories`,
  `total_enemy_max_hp`, `version`
- player: `hp, max_hp, block, energy, max_energy, statuses, hand, draw, discard, exhaust, ended, alive, seat, bot`
- enemy: `hp, max_hp, block, statuses, alive, slot, intent(kinds, damage, hits, target)`
- methods: `legal_plays`, `play`, `answer_question` (returns the next question, or None),
  `pending_question`, `end_turn`, `bot_step`, `bot_finish_turn`, `incoming`, `enemy_hit`, `card_hit`,
  `card_block`, `shown_damage`, `living_players`, `living_enemies`, `ally_hp_scale`, `enemy_hp_scale`
- module: `make_team(rng, bots, cfg)`, `new_fight(rng, players, cfg)`

Write an adapter with the same names around your engine and the rest of the code stays as it is.

## Simplifications in the mock engine
- one fight per episode; HP resets to full each fight
- small card set, 5 statuses in use (strength, dexterity, vulnerable, weak, frail)
- enemy attacks pick one target player; durations tick down at end of round (as in the spec)
- no potions, relics, map or rewards
