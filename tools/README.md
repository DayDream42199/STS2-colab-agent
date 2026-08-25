# tools/

Diagnostics, not tests. Each one produced a number that the main README now
states, and they live here so those claims stay reproducible. They are slow
and some take minutes, so they are deliberately NOT in `tests/run_all.py`.

- `diag36_matrix.py` -- #36 deck ablation: every encounter x 3 deck tiers, showed the 'flat curve' was a median artifact\n- `diag36_godcheck.py` -- #36 god-deck probe: all 13 near-0% fights are winnable, so nothing is ported unwinnable\n- `check_env_drift.py` -- #43 proof the action mask disagreed with the engine\n- `check_env_obs.py` -- #44/#48 proof of the 4-enemy cap and the invisible hand\n- `choice_ab.py` -- #45 A/B harness for the choice resolver\n- `choice_variants.py` -- #45 resolver sweep: greedy-everywhere loses to random\n
Run any of them directly:

    python tools/diag36_matrix.py

`choice_variants.py` imports `choice_ab.py`, so they move together.
