"""What each card DOES, grouped by where the card comes from.

One function per behaviour, split by source so a file is small enough to
read: `ironclad` and `colorless` are the two card pools, `status` is the
clutter other things add to your deck, and `common` is what they share.

Everything is re-exported, so `from game_engine.cards import fx_plain_attack`
and `from .effects import *` behave exactly as they did when this was one
1,800-line module.
"""

from .common import *        # noqa: F401,F403
from .ironclad import *      # noqa: F401,F403
from .colorless import *     # noqa: F401,F403
from .status import *        # noqa: F401,F403

# Underscore names `import *` skips, but callers reach for.
from .common import (_ally_of, _random_ally_of, _arm_once, _arm_power,
                     _auto_target_for,
                     _fresh_free_card, _pick, _return_next_turn,
                     _sample_distinct)
from .ironclad import _midnight_cost, _stomp_cost
from .colorless import _clash_playable
from .status import _fx_slimed
