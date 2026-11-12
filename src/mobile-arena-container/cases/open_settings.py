"""Open system Settings from the home screen."""
from .common import prepare_app, verify_app, cleanup

ID, VERSION = "open_settings", "1"


def setup(serial, state):
    prepare_app(serial, state, "android.settings.SETTINGS")


def make_request():
    return "帮我打开手机设置。"


def verify(serial, state, after):
    return verify_app(state, after)
