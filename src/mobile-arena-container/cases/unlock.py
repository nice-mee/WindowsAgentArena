"""Existing opt-in PIN task; the PIN is supplied at runtime, never stored here."""
ID, VERSION = "unlock", "1"


def make_request(pin="<runtime PIN>"):
    return f"帮我把手机解锁，密码是 {pin}。"
