"""The combat engine: rules, content and the RL environment.

The MODULES here are self-contained -- statuses, entities, cards, enemies,
relics, potions, combat and env import only each other, so the package can be
used without anything else in the repo being importable.

`tests/` is the exception, and deliberately so. Test code is allowed to
depend on everything it verifies, and six of the suites reach into
`testing.*` because that is what they are testing (config.py, the benchmark,
the encounter table). So the self-contained claim covers the engine modules,
not the test folder sitting beside them.
"""
