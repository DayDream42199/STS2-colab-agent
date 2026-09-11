import sys
import threading
import time

import config
from Network.client import Client
from Network.enums import NetworkEvent
from UI import terminal_ui

sys.stdout.reconfigure(line_buffering=True)


def main():
    client = Client()
    stop = threading.Event()

    listener = threading.Thread(target=_listen, args=(client, stop), daemon=True)
    listener.start()

    print(f"Connecting to {config.HOST}:{config.PORT} ...")
    client.connect(config.HOST, config.PORT)

    waited = 0.0
    while not client.connected and waited < config.CONNECT_TIMEOUT:
        time.sleep(0.02)
        waited += 0.02

    if not client.connected:
        print("[error] could not connect within timeout.")
        stop.set()
        return

    print("type 'help' for commands.")

    try:
        while not stop.is_set():
            try:
                line = input("> ").strip()
            except EOFError:
                break

            result = terminal_ui.parse_command(line)
            if result is None:
                continue
            if result == "quit":
                break
            client.send(result)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if client.connected:
            client.disconnect()


def _listen(client, stop):
    while not stop.is_set():
        event = client.get_event()
        if event is None:
            time.sleep(config.POLL_INTERVAL)
            continue
        _handle_network_event(event)


def _handle_network_event(event):
    network_event = event[0]

    if network_event is NetworkEvent.CONNECTED:
        print("[connected]")
    elif network_event is NetworkEvent.CONNECTION_FAILED:
        print(f"[connection failed] {event[1]}")
    elif network_event is NetworkEvent.DISCONNECTED:
        print("[disconnected]")
    elif network_event is NetworkEvent.SEND_FAILED:
        print(f"[send failed] {event[1]}")
    elif network_event is NetworkEvent.MESSAGE_RECEIVED:
        terminal_ui.handle_server_message(event[1])


if __name__ == "__main__":
    main()
