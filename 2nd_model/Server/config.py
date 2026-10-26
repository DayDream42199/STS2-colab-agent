import os

from GameEngine.Registry.unit_registry import known_ally_type_ids, known_enemy_type_ids

# --- network -------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5000
POLL_INTERVAL = 0.01  # seconds between event-queue polls in main.py's loop

# --- session / matchmaking ------------------------------------------
REQUIRED_PLAYERS = 2  # raise for co-op; 1 is solo testing

# --- plugin ----------------------------------------------------------
# Module under Server/Plugins/ that may reshape what each client receives and
# watch the fight (see plugin_host.py). If the file is not there, the server
# runs as usual and sends everyone the player format. None turns it off.
PLUGIN = "Plugins.aura"

# --- combat log ------------------------------------------------------
# Every action, decision and outcome, one file per fight (combat_log.py), so
# fights can be replayed, debugged and evaluated. None turns it off. The
# folder is 2nd_model/logs/, which git ignores.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")

# --- combat setup ----------------------------------------------------
ALLY_TYPE_ID = "ironclad"            # the game's Ironclad; "testally1" is the test unit
ENEMY_TYPE_IDS = ("nibbit","nibbit")          # e.g. ("aeonglass",) or ("leafslimemedium", "twigslimesmall")
# Co-op scaling: enemy HP x player count x this act's factor (1.1 / 1.2 / 1.2 /
# 1.3 for act1 / act2 / act3 / act3boss). Single player is never scaled.
ACT = "act1"
SCALE_ENEMIES = True

assert ALLY_TYPE_ID in known_ally_type_ids(), (
    f"config.ALLY_TYPE_ID={ALLY_TYPE_ID!r} is not registered in unit_registry.py"
)
assert all(t in known_enemy_type_ids() for t in ENEMY_TYPE_IDS), (
    f"config.ENEMY_TYPE_IDS={ENEMY_TYPE_IDS!r} contains an id not registered in unit_registry.py"
)
