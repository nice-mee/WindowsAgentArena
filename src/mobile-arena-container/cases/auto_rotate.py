"""Enable auto-rotation, then restore the original setting after grading."""
from .common import prepare_setting, verify_setting, cleanup

ID, VERSION = "auto_rotate", "1"


def setup(serial, state):
    prepare_setting(serial, state, "accelerometer_rotation", "0")


def make_request():
    return "帮我开启屏幕自动旋转。"


def verify(serial, state, after):
    return verify_setting(serial, state, "1")
