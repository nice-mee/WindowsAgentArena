"""Explicit case registry; no discovery or inheritance."""
from . import (wechat, unlock, weather, home, open_settings, open_camera,
               open_clock, open_calculator, auto_rotate, auto_brightness,
               screen_timeout, font_size)
from .common import task_context

CASES = {case.ID: case for case in (
    home, open_settings, open_camera, open_clock, open_calculator,
    auto_rotate, auto_brightness, screen_timeout, font_size,
    wechat, unlock, weather,
)}


def make_request(case, pin="<runtime PIN>"):
    module = CASES[case]
    return module.make_request(pin) if case == "unlock" else module.make_request()
