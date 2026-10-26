"""The real server, with a deck full of cards that ask a question.

Only the test unit's deck and the ally type are patched, and only here - the
tree itself is untouched. The server's own player is the Ironclad.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Server"))

from GameEngine.Units.Allies.test_ally_1 import TestAlly1
TestAlly1.DEFAULT_DECK = ["wish"] * 5 + ["strike"] * 5
import config  # noqa: E402
config.ALLY_TYPE_ID = TestAlly1.type_id()

import main  # noqa: E402

main.main()   # main.py only runs under __main__, so call it
