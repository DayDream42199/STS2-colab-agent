"""The real server, with a deck full of cards that ask a question.

Only the deck is patched, and only here - the tree itself is untouched.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Server"))

from GameEngine.Units.Allies.test_ally_1 import TestAlly1
TestAlly1.DEFAULT_DECK = ["wish"] * 5 + ["strike"] * 5

import main  # noqa: E402

main.main()   # main.py only runs under __main__, so call it
