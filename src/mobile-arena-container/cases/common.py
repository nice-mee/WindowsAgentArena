"""Small initialization and outcome helpers shared by the fixed phone tasks."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import phone


def task_context(now=None):
    now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    return {"date": today.isoformat(), "timezone": "Asia/Shanghai",
            "friday": friday.isoformat(), "contact": "Flint",
            "weather_location": "北京市海淀区"}


def verdict(passed, **details):
    return {"status": "passed" if passed else "failed", **details}


def prepare_app(serial, state, action, category=None):
    component = phone.resolve_activity(serial, action, category)
    state["expected_package"] = component.split("/", 1)[0]
    phone.go_home(serial)


def verify_app(state, after):
    actual = after.get("foreground_package")
    return verdict(after.get("locked") is False and actual == state["expected_package"],
                   expected_package=state["expected_package"], actual_package=actual)


def prepare_setting(serial, state, key, initial):
    # Mutate the caller's state before changing the phone, so partial setup can restore it.
    original = phone.read_setting(serial, key)
    if original is None:
        raise RuntimeError(f"Phone does not expose system setting: {key}")
    state.update(setting=key, original=original, initial=str(initial))
    phone.write_setting(serial, key, str(initial))
    if phone.read_setting(serial, key) != str(initial):
        raise RuntimeError(f"Could not initialize system setting: {key}")
    phone.go_home(serial)


def verify_setting(serial, state, expected):
    actual = phone.read_setting(serial, state["setting"])
    return verdict(actual == str(expected), setting=state["setting"],
                   actual=actual, expected=str(expected))


def cleanup(serial, state):
    if "original" in state:
        phone.write_setting(serial, state["setting"], state["original"])
        if phone.read_setting(serial, state["setting"]) != state["original"]:
            raise RuntimeError(f"Could not restore system setting: {state['setting']}")
    phone.go_home(serial)
