"""Cards: the model, what each card does, and the tables of which exist.

Split out of a single 3,000-line module. The import order below is the
dependency order and is not incidental -- pools builds Cards out of the
effects and token factories, so those have to exist first.

Everything the old flat `cards.py` exported is re-exported here, so
`import game_engine.cards as C` and `from game_engine.cards import X` keep
working unchanged.
"""

from .model import *          # noqa: F401,F403
from .effects import *        # noqa: F401,F403
from .tokens import *         # noqa: F401,F403
from .pools import *          # noqa: F401,F403

# Names a leading underscore keeps out of `import *`, re-exported because
# the flat module exposed them and tests reach for some of them.
from .model import (_BASIC_CARDS, _COMMON_CARDS, _RARE_CARDS,
                    _ANCIENT_CARDS, _TOKEN_CARDS, _COLORLESS_CARDS)
from .effects import (_arm_once, _arm_power, _ally_of, _auto_target_for,
                      _clash_playable, _fresh_free_card, _midnight_cost,
                      _pick, _return_next_turn, _sample_distinct,
                      _stomp_cost, _fx_slimed)
from .tokens import _curse, _status_card
from .pools import _all_card_names, _assert_rarity_coverage, _card
