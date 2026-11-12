"""Change the display inactivity timeout to two minutes."""
from .common import prepare_setting, verify_setting, cleanup

ID, VERSION = "screen_timeout", "1"


def setup(serial, state):
    prepare_setting(serial, state, "screen_off_timeout", "600000")


def make_request():
    return "把手机自动熄屏时间改成十分钟。"


def verify(serial, state, after):
    return verify_setting(serial, state, "120000")
