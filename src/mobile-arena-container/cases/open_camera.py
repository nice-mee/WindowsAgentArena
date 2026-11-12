"""Open the camera without taking a photo or recording video."""
from .common import prepare_app, verify_app, cleanup

ID, VERSION = "open_camera", "1"


def setup(serial, state):
    prepare_app(serial, state, "android.media.action.STILL_IMAGE_CAMERA")


def make_request():
    return "帮我打开相机，先不要拍照。"


def verify(serial, state, after):
    return verify_app(state, after)
