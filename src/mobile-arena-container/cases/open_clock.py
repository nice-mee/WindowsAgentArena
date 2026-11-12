"""Open the clock application; do not create or change alarms."""
from .common import prepare_app, verify_app, cleanup

ID, VERSION = "open_clock", "1"


def setup(serial, state):
    prepare_app(serial, state, "android.intent.action.SHOW_ALARMS")


def make_request():
    return "帮我打开手机时钟。"


def verify(serial, state, after):
    return verify_app(state, after)
