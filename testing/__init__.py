"""Ways to drive the engine: the terminal client, the benchmark, the
demo, and the simplified sandbox used for a first RL agent.

`tools/` sits here too. Those are diagnostics rather than drivers, but four
of the six import `bench` and `play`, so they belong on this side of the
line -- `game_engine/` must not depend on anything outside itself.
"""
