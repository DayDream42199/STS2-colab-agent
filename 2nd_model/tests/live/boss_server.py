"""The real server against any registered enemies. Only config is patched.

    python tests/live/boss_server.py                        The Insatiable, act 2
    python tests/live/boss_server.py aeonglass              Aeonglass, act 1
    python tests/live/boss_server.py leafslimemedium twigslimesmall
                                                            an Act 1 lineup
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Server"))

import config
kinds = tuple(sys.argv[1:]) or ("theinsatiable",)
config.ENEMY_TYPE_IDS = kinds
config.ACT = "act2" if kinds == ("theinsatiable",) else "act1"

import main  # noqa: E402

main.main()
