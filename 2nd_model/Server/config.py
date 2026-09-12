from GameEngine.Registry.unit_registry import known_ally_type_ids, known_enemy_type_ids

# --- network -------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5000
POLL_INTERVAL = 0.01  # seconds between event-queue polls in main.py's loop

# --- session / matchmaking ------------------------------------------
REQUIRED_PLAYERS = 2  # raise for co-op; 1 is solo testing

# --- combat setup ----------------------------------------------------
ALLY_TYPE_ID = "testally1"
ENEMY_TYPE_IDS = ("dummy1",)          # e.g. ("aeonglass",) or ("leafslimemedium", "twigslimesmall")
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
