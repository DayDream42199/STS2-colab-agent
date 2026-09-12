"""The real server against a boss. Only config is patched.

    python tests/live/boss_server.py              The Insatiable, act 2
    python tests/live/boss_server.py aeonglass    Aeonglass, act 1
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Server"))

import config
boss = sys.argv[1] if len(sys.argv) > 1 else "theinsatiable"
config.ENEMY_TYPE_IDS = (boss,)
config.ACT = "act2" if boss == "theinsatiable" else "act1"

import main  # noqa: E402

main.main()
