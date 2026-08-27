# testing/tools/

Diagnostics, not tests. Each one produced a number that the main README now
states, and they live here so those claims stay reproducible. They are
deliberately NOT in `game_engine/tests/run_all.py` -- they measure, they do
not assert, so there is nothing for a runner to pass or fail.

- `diag36_matrix.py` -- #36 deck ablation: every encounter x 3 deck tiers,
  showed the 'flat curve' was a median artifact
- `diag36_godcheck.py` -- #36 god-deck probe: all 13 near-0% fights are
  winnable, so nothing is ported unwinnable
- `check_env_drift.py` -- #43 proof the action mask disagreed with the engine
- `check_env_obs.py` -- #44/#48 proof of the 4-enemy cap and the invisible hand
- `choice_ab.py` -- #45 A/B harness for the choice resolver
- `choice_variants.py` -- #45 resolver sweep: greedy-everywhere loses to random

Run any of them directly, from the repo root:

    python testing/tools/diag36_matrix.py

Runtimes on the dev machine, slowest first: `choice_variants` 15s,
`diag36_matrix` 5s, `choice_ab` 3s, the rest ~1s each. About 26s for all six.

Four of the six import `testing.bench` / `testing.play`, which is why this
folder sits under `testing/` and not beside the engine. `choice_variants.py`
imports `choice_ab.py` as a sibling, so those two move together.
