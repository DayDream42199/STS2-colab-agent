from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage


def handle_server_message(data):
    try:
        message_type, payload = decode(data, ServerMessage)
    except ValueError as error:
        print(f"[bad message from server] {error}")
        return

    if message_type is ServerMessage.WELCOME:
        print(f"[welcome] you are {payload.get('unit_id')}")
    elif message_type is ServerMessage.LOBBY:
        print(f"[lobby] {payload.get('players')}/{payload.get('required')} players connected")
    elif message_type is ServerMessage.STATE:
        _print_state(payload.get("combat", {}))
    elif message_type is ServerMessage.EFFECTS:
        print(f"[effects] {payload.get('source')} -> {payload.get('results')}")
    elif message_type is ServerMessage.READY_CHANGED:
        print(f"[ready] ready={payload.get('ready')} waiting_on={payload.get('waiting_on')}")
    elif message_type is ServerMessage.CHOICE_REQUIRED:
        print(f"[choose] {payload.get('prompt')}")
        for i, option in enumerate(payload.get("options", [])):
            print(f"      choose {i} -> {option}")
    elif message_type is ServerMessage.COMBAT_ENDED:
        print(f"[combat ended] result={payload.get('result')}")
    elif message_type is ServerMessage.ERROR:
        print(f"[error] {payload.get('message')}")
    else:
        print(f"[unhandled message] {message_type} {payload}")


def _print_state(combat):
    print(f"--- phase: {combat.get('phase')}  result: {combat.get('result')} ---")
    for ally in combat.get("allies", []):
        statuses = ally.get("statuses", {})
        status_str = ", ".join(f"{k}:{v}" for k, v in statuses.items()) or "-"
        print(
            f"  [ALLY {ally['unit_id']}] hp={ally['current_hp']}/{ally['max_hp']} "
            f"block={ally['block']} energy={ally['energy']}/{ally['max_energy']} "
            f"statuses=({status_str})"
        )
        for i, card_id in enumerate(ally.get("hand", [])):
            print(f"      hand[{i}] = {card_id}")
    for unit_id, choice in (combat.get("choices") or {}).items():
        print(f"  [CHOICE for {unit_id}] {choice.get('prompt')}")
        for i, option in enumerate(choice.get("options", [])):
            print(f"      choose {i} -> {option}")
    for enemy in combat.get("enemies", []):
        statuses = enemy.get("statuses", {})
        status_str = ", ".join(f"{k}:{v}" for k, v in statuses.items()) or "-"
        print(
            f"  [ENEMY {enemy['unit_id']}] hp={enemy['current_hp']}/{enemy['max_hp']} "
            f"block={enemy['block']} intent={enemy.get('intent')} statuses=({status_str})"
        )


def parse_command(line):
    parts = line.split()
    if not parts:
        return None

    cmd = parts[0].lower()

    if cmd == "help":
        print("commands: play <hand_index> [target_id]  |  choose <option_index>"
              "  |  end_turn  |  state  |  quit")
        return None

    if cmd == "choose":
        if len(parts) < 2 or not parts[1].isdigit():
            print("usage: choose <option_index>")
            return None
        return encode(ClientMessage.CHOOSE, option_index=int(parts[1]))

    if cmd == "quit":
        return "quit"

    if cmd == "state":
        return encode(ClientMessage.REQUEST_STATE)

    if cmd == "end_turn":
        return encode(ClientMessage.END_TURN)

    if cmd == "play":
        if len(parts) < 2 or not parts[1].isdigit():
            print("usage: play <hand_index> [target_id]")
            return None
        hand_index = int(parts[1])
        target_id = parts[2] if len(parts) > 2 else None
        return encode(ClientMessage.PLAY_CARD, hand_index=hand_index, target_id=target_id)

    print(f"unknown command: {cmd!r}. type 'help'.")
    return None
