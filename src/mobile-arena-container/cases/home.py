"""Return to the home screen from Settings."""
import phone
from .common import verify_app, cleanup

ID, VERSION = "home", "1"


def setup(serial, state):
    home = phone.resolve_activity(serial, "android.intent.action.MAIN", "android.intent.category.HOME")
    state["expected_package"] = home.split("/", 1)[0]
    phone.go_home(serial)
    phone.start_activity(serial, phone.resolve_activity(serial, "android.settings.SETTINGS"))


def make_request():
    return "帮我回到手机桌面。"


def verify(serial, state, after):
    return verify_app(state, after)
