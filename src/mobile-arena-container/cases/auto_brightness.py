"""Disable automatic brightness, restoring the original mode afterwards."""
import phone
from .common import prepare_setting, verify_setting, cleanup as restore_setting

ID, VERSION = "auto_brightness", "1"


def setup(serial, state):
    state["original_brightness"] = phone.read_setting(serial, "screen_brightness")
    prepare_setting(serial, state, "screen_brightness_mode", "1")


def make_request():
    return "帮我关闭自动亮度。"


def verify(serial, state, after):
    return verify_setting(serial, state, "0")


def cleanup(serial, state):
    restore_setting(serial, state)
    if state.get("original_brightness") is not None:
        phone.write_setting(serial, "screen_brightness", state["original_brightness"])
