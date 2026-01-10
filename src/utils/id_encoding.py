def encode_id(id: str) -> str:
    return id.encode("utf-8").hex()

def decode_id(id: str) -> str:
    return bytes.fromhex(id).decode("utf-8")