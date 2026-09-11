"""Enemies: the model, and one module per region of the Spire.

Split out of a single 2,400-line module. Which enemy went where was not a
judgement call -- each factory was placed by the region of the encounters
that actually reference it, and every one of the 92 encounter-referenced
enemies mapped to exactly one region. The 11 that no encounter names are
summons: they only ever arrive mid-fight, spawned by something else.

Everything the flat `enemies.py` exported is re-exported here, so
`import game_engine.enemies as E` keeps working unchanged.
"""

from .model import *          # noqa: F401,F403
from .shared import *         # noqa: F401,F403
from .summons import *        # noqa: F401,F403
from .overgrowth import *     # noqa: F401,F403
from .underdocks import *     # noqa: F401,F403
from .hive import *           # noqa: F401,F403
from .glory import *          # noqa: F401,F403
from .events import *         # noqa: F401,F403

# Underscore names `import *` skips.
from .shared import (_bowlbug, _dmg_move, _make_battle_friend, _make_cultist,
                     _multi_hit, _nothing, _shuffle_status_cards)
