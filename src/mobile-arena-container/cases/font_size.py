"""Increase the system font scale relative to a fixed default-size start."""
import phone
from .common import prepare_setting, verdict, cleanup

ID, VERSION = "font_size", "1"


def setup(serial, state):
    prepare_setting(serial, state, "font_scale", "1.0")


def make_request():
    return "帮我把手机的系统字体调大一点。"


def verify(serial, state, after):
    actual = phone.read_setting(serial, state["setting"])
    try:
        larger = float(actual) > float(state["initial"])
    except (TypeError, ValueError):
        larger = False
    return verdict(larger, setting=state["setting"], initial=state["initial"], actual=actual)
