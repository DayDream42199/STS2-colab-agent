from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage

# Who this client is, from the welcome message: an enemy's intent shows the
# damage it will do to this player.
_me = {"unit_id": None}
# The last combat state received, so `piles` can print without asking again.
_last = {"combat": None}


def handle_server_message(data):
    try:
        message_type, payload = decode(data, ServerMessage)
    except ValueError as error:
        print(f"[bad message from server] {error}")
        return

    if message_type is ServerMessage.WELCOME:
        _me["unit_id"] = payload.get("unit_id")
        print(f"[welcome] you are {payload.get('unit_id')}")
    elif message_type is ServerMessage.LOBBY:
        print(f"[lobby] {payload.get('players')}/{payload.get('required')} players connected")
    elif message_type is ServerMessage.STATE:
        _last["combat"] = payload.get("combat", {})
        _print_state(_last["combat"])
    elif message_type is ServerMessage.EFFECTS:
        print(f"[effects] {_describe_action(payload)} -> {payload.get('results')}")
    elif message_type is ServerMessage.READY_CHANGED:
        print(f"[ready] ready={payload.get('ready')} waiting_on={payload.get('waiting_on')}")
    elif message_type is ServerMessage.CHOICE_REQUIRED:
        print(f"[choose] {payload.get('prompt')}")
        _print_options(payload)
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
        piles = ally.get("piles") or {}
        pile_str = ""
        if piles:
            pile_str = " piles=draw %d/discard %d/exhaust %d" % tuple(
                len(piles.get(name, [])) for name in ("draw", "discard", "exhaust"))
        ended = " (ended)" if ally.get("ended_turn") else ""
        print(
            f"  [ALLY {ally['unit_id']}]{ended} hp={ally['current_hp']}/{ally['max_hp']} "
            f"block={ally['block']} energy={ally['energy']}/{ally['max_energy']} "
            f"statuses=({status_str}){pile_str}"
        )
        # Cost first, as the game prints it in the card's corner: [1], [X],
        # or [-] for a card that cannot be played. "+" marks an upgrade. Then
        # what the card does, its damage already after your Strength and
        # Weak. (hand_damage carries that number alone, for an agent.)
        costs = ally.get("hand_cost") or []
        upgraded = ally.get("hand_upgraded") or []
        texts = ally.get("hand_text") or []
        for i, card_id in enumerate(ally.get("hand", [])):
            cost = ""
            if i < len(costs):
                cost = "[%s] " % ("-" if costs[i] is None else costs[i])
            plus = "+" if i < len(upgraded) and upgraded[i] else ""
            text = f"  | {texts[i]}" if i < len(texts) and texts[i] else ""
            print(f"      hand[{i}] = {cost}{card_id}{plus}{text}")
    for unit_id, choice in (combat.get("choices") or {}).items():
        print(f"  [CHOICE for {unit_id}] {choice.get('prompt')}")
        _print_options(choice)
    for enemy in combat.get("enemies", []):
        statuses = enemy.get("statuses", {})
        status_str = ", ".join(f"{k}:{v}" for k, v in statuses.items()) or "-"
        print(
            f"  [ENEMY {enemy['unit_id']}] {enemy.get('name', '?')} "
            f"hp={enemy['current_hp']}/{enemy['max_hp']} block={enemy['block']} "
            f"intent={_describe_intent(enemy.get('intent'))} statuses=({status_str})"
        )


def _describe_action(payload):
    """Who did what, from an effects message: "p2 played bash+ on e1",
    "p1 chose defend", "p1 stopped", "p2 left". Just the source from a server
    that does not say."""
    who = payload.get("source", "?")
    action = payload.get("action")
    if action == "play":
        card = (payload.get("card_id") or "?") + ("+" if payload.get("upgraded") else "")
        target = payload.get("target_id")
        return f"{who} played {card}" + (f" on {target}" if target else "")
    if action == "choose":
        option = payload.get("option")
        return f"{who} chose {option}" if option else f"{who} stopped"
    if action == "left":
        return f"{who} left; their open choices were answered at random"
    return str(who)


def _print_options(choice):
    """A question's options, each with what the card does."""
    texts = choice.get("option_text") or []
    for i, option in enumerate(choice.get("options", [])):
        text = f"  | {texts[i]}" if i < len(texts) and texts[i] else ""
        print(f"      choose {i} -> {option}{text}")
    if choice.get("can_stop"):
        print("      choose stop -> pick nothing more")


def _describe_intent(intent):
    """What a player sees of an enemy's next move: the kind, and its numbers.

    Not the move's name - the game does not show it - and not a target: every
    enemy move lands on every player. Attack damage is what it will do to YOU,
    after its Strength and Weak and your Vulnerable, as the game shows it."""
    if not isinstance(intent, dict):
        return "-"
    kind = intent.get("type", "?")
    block = intent.get("block", 0)
    if kind == "attack":
        per_player = intent.get("damage") or {}
        text = f"Attack {per_player.get(_me['unit_id'], intent.get('amount', 0))}"
        if intent.get("hits", 1) > 1:
            text += f"x{intent['hits']}"
        if block:
            text += f" +{block} Block"
        return text
    if kind == "block":
        # Dummy1 carries its Block in "amount"; scripted enemies in "block".
        return f"Block {block or intent.get('amount', 0)}"
    if kind in ("debuff", "debuff_all"):
        return "Debuff"
    if kind == "buff":
        return "Buff"
    return kind.capitalize()


def _print_piles(unit_id):
    """One player's draw, discard and exhaust piles, from the last state.

    Copies are counted ("strike x3"), listed where the first one appears,
    each with what it does.
    The draw pile arrives sorted by rarity, as the game shows it, so it says
    nothing about what comes next; discard and exhaust come in the order the
    cards went in."""
    combat = _last["combat"]
    if not combat:
        print("no state yet - try 'state'.")
        return
    ally = next((a for a in combat.get("allies", []) if a.get("unit_id") == unit_id), None)
    if ally is None:
        print(f"no player {unit_id!r}. players: "
              + ", ".join(a.get("unit_id", "?") for a in combat.get("allies", [])))
        return
    piles = ally.get("piles")
    if piles is None:
        print("this server does not send piles.")
        return
    print(f"  [PILES {unit_id}]")
    for name in ("draw", "discard", "exhaust"):
        cards = piles.get(name, [])
        # Grouped by name AND text: a boosted Rampage is not a plain one.
        counts = {}
        for card in cards:
            key = (card.get("id", "?") + ("+" if card.get("upgraded") else ""),
                   card.get("text") or "")
            counts[key] = counts.get(key, 0) + 1
        print(f"      {name} ({len(cards)}):" + ("" if cards else " -"))
        for (label, text), n in counts.items():
            shown = label if n == 1 else f"{label} x{n}"
            print(f"          {shown}" + (f"  | {text}" if text else ""))


def parse_command(line):
    parts = line.split()
    if not parts:
        return None

    cmd = parts[0].lower()

    if cmd == "help":
        print("commands: play <hand_index> [target_id]  |  choose <option_index|stop>"
              "  |  end_turn  |  state  |  piles [player_id]  |  quit")
        return None

    if cmd == "piles":
        # Local: printed from the last state, nothing is sent.
        _print_piles(parts[1] if len(parts) > 1 else _me["unit_id"])
        return None

    if cmd == "choose":
        # "stop" ends an "up to N" question (Purity); the server refuses it
        # on a question that needs an answer.
        if len(parts) >= 2 and parts[1].lower() == "stop":
            return encode(ClientMessage.CHOOSE, option_index=-1)
        if len(parts) < 2 or not parts[1].isdigit():
            print("usage: choose <option_index|stop>")
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
