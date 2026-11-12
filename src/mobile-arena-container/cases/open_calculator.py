"""Open the installed calculator application."""
from .common import prepare_app, verify_app, cleanup

ID, VERSION = "open_calculator", "1"


def setup(serial, state):
    prepare_app(serial, state, "android.intent.action.MAIN", "android.intent.category.APP_CALCULATOR")


def make_request():
    return "帮我打开计算器。"


def verify(serial, state, after):
    return verify_app(state, after)
