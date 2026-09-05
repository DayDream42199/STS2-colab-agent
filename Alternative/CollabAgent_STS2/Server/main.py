import time

from Network.network import Server
from Network.enums import NetworkEvent
from session import Session, BROADCAST

# The only dependency on the combat module. Session drives it purely through
# the surface documented in COMBAT_INTERFACE.md.
try:
    from GameEngine.Combat.combat import Combat
except ImportError:
    Combat = None

HOST = "0.0.0.0"
PORT = 5000
REQUIRED_PLAYERS = 1
POLL_INTERVAL = 0.01

def main():
    if Combat is None:
        raise SystemExit(
            "GameEngine/Combat/combat.py is not implemented yet. Everything else "
            "is ready; see COMBAT_INTERFACE.md for the surface it must provide."
        )

    server = Server()
    session = Session(combat_factory=Combat, required_players=REQUIRED_PLAYERS)

    server.start(HOST, PORT)

    try:
        while True:
            event = server.get_event()
            if event is None:
                time.sleep(POLL_INTERVAL)
                continue
            if not handle_event(server, session, event):
                break
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        server.shutdown()

def handle_event(server, session, event):
    network_event = event[0]

    if network_event is NetworkEvent.SERVER_STARTED:
        print(f"Listening on {HOST}:{PORT}, waiting for {REQUIRED_PLAYERS} player(s).")
        return True

    if network_event is NetworkEvent.START_FAILED:
        print(f"Failed to start server: {event[1]}")
        return False

    if network_event is NetworkEvent.CLIENT_CONNECTED:
        sid = event[1]
        print(f"Client connected: {sid}")
        dispatch(server, session.add_player(sid))
        return True

    if network_event is NetworkEvent.CLIENT_DISCONNECTED:
        sid = event[1]
        print(f"Client disconnected: {sid}")
        dispatch(server, session.remove_player(sid))
        return True

    if network_event is NetworkEvent.MESSAGE_RECEIVED:
        sid, data = event[1], event[2]
        dispatch(server, session.handle(sid, data))
        return True

    if network_event in (NetworkEvent.SEND_FAILED, NetworkEvent.CLIENT_DISCONNECT_FAILED):
        print(f"Network error: {event[1]}")
        return True

    return True

def dispatch(server, outbound):
    for recipient, message in outbound:
        if recipient is BROADCAST:
            server.broadcast(message)
        else:
            server.send(recipient, message)

if __name__ == "__main__":
    main()
