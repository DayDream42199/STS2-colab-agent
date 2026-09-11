from .enums import ClientMessage, ServerMessage

def encode(message_type, **payload):
    return {"type": message_type.value, "payload": payload}

def decode(data, message_enum):
    if not isinstance(data, dict):
        raise ValueError("Message must be an object.")

    raw_type = data.get("type")
    try:
        message_type = message_enum(raw_type)
    except ValueError:
        raise ValueError(f"Unknown message type: {raw_type!r}")

    payload = data.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Message payload must be an object.")

    return message_type, payload
