"""ADB initialization, independent observations, and restoration of test settings."""
import json
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
import uuid
from pathlib import Path


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def redact_secret(value, secret):
    """Redact values without corrupting JSON numeric literals."""
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "<redacted>")
    if isinstance(value, dict):
        return {str(k).replace(secret, "<redacted>"): redact_secret(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secret(v, secret) for v in value]
    if type(value) in (int, float) and str(value) == secret:
        return "<redacted>"
    return value


def adb(serial, *args, binary=False, timeout=20):
    command = ["adb", *(["-s", serial] if serial else []), *args]
    result = subprocess.run(command, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or "ADB failed")
    return result.stdout if binary else result.stdout.decode("utf-8", errors="replace").strip()


def select_device(requested=None):
    rows = [line.split() for line in adb(None, "devices").splitlines()[1:] if line.strip()]
    ready = [row[0] for row in rows if len(row) >= 2 and row[1] == "device"]
    if requested:
        if requested not in ready:
            raise RuntimeError("Requested phone is not online/authorized in adb devices")
        return requested
    if len(ready) != 1:
        raise RuntimeError(f"Expected one authorized Android device, found {len(ready)}; connect phone or use --serial")
    return ready[0]


def resolve_activity(serial, action, category=None):
    arguments = ["-a", action, *(["-c", category] if category else [])]
    output = adb(serial, "shell", "cmd", "package", "resolve-activity", "--brief",
                 "--user", "current", *arguments)
    components = re.findall(r"(?m)^([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)$", output)
    if len(components) != 1 or "ResolverActivity" in components[0]:
        raise RuntimeError(f"No default app resolves {action} {category or ''}")
    return components[0]


def start_activity(serial, component):
    output = adb(serial, "shell", "am", "start", "-W", "-n", shlex.quote(component))
    if "Error" in output or "Exception" in output:
        raise RuntimeError(output)


def go_home(serial):
    adb(serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb(serial, "shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(0.5)


def read_setting(serial, key):
    value = adb(serial, "shell", "settings", "--user", "current", "get", "system", key)
    return None if value in {"", "null"} else value


def write_setting(serial, key, value):
    output = adb(serial, "shell", "settings", "--user", "current", "put", "system", key, shlex.quote(value))
    if output:
        raise RuntimeError(f"Cannot set {key}: {output}")


def lock_state(policy):
    """Unknown OEM layouts fail closed; never infer unlocked from missing text."""
    values = re.findall(r"\b(?:mShowingLockscreen|mKeyguardShowing|isKeyguardShowing|keyguardShowing)=(true|false)\b", policy)
    delegate = re.search(r"KeyguardServiceDelegate\s*[:{]?\s*\n((?:[ \t]+[^\n]*\n?)*)", policy)
    if delegate:
        values += re.findall(r"(?m)^\s*showing=(true|false)\b", delegate.group(1))
    if not values or len(set(values)) != 1:
        return None
    return values[0] == "true"


def state(serial):
    policy = adb(serial, "shell", "dumpsys", "window", "policy")
    power = adb(serial, "shell", "dumpsys", "power")
    window = adb(serial, "shell", "dumpsys", "window", "windows")
    focus = re.search(r"(?:mCurrentFocus|mFocusedApp)=.*?\s([A-Za-z0-9_.]+)/", window)
    return {"locked": lock_state(policy),
            "awake": bool(re.search(r"\bmWakefulness=Awake\b", power)),
            "foreground_package": focus.group(1) if focus else None,
            "foreground_source": "window_focus" if focus else None,
            "policy": policy, "power": power, "window": window}


def add_ui_evidence(observed, xml):
    """A missing OEM focus field is unknown, not proof that the wrong app ran."""
    nodes = ET.fromstring(xml).iter("node")
    packages = sorted({node.get("package") for node in nodes if node.get("package")})
    observed["visible_ui_packages"] = packages
    # Do not guess the foreground from all window entries, IME targets or a
    # multi-package tree (which can include keyboard/notification overlays).
    if observed.get("foreground_package") is None and len(packages) == 1:
        observed["foreground_package"] = packages[0]
        observed["foreground_source"] = "ui_tree_single_package"
    return observed


def preflight(requested=None):
    serial = select_device(requested)
    packages = sorted(line.removeprefix("package:") for line in
                      adb(serial, "shell", "pm", "list", "packages").splitlines()
                      if line.startswith("package:"))
    info = {"serial": serial,
            "model": adb(serial, "shell", "getprop", "ro.product.model"),
            "android": adb(serial, "shell", "getprop", "ro.build.version.release"),
            "device_date": adb(serial, "shell", "date", "+%Y-%m-%d"),
            "packages": packages,
            "input_method": adb(serial, "shell", "settings", "get", "secure", "default_input_method"),
            "state": state(serial)}
    info["weather_candidates"] = [p for p in packages if "weather" in p.lower()]
    info["app_versions"] = {}
    for package in [p for p in packages if p == "com.tencent.mm" or p in info["weather_candidates"]]:
        text = adb(serial, "shell", "dumpsys", "package", package)
        match = re.search(r"versionName=([^\s]+)", text)
        info["app_versions"][package] = match.group(1) if match else None
    return info


def snapshot(serial, directory):
    directory.mkdir(parents=True, exist_ok=True)
    observed = state(serial)
    save(directory / "state.json", observed)
    errors = []
    try:
        png = adb(serial, "exec-out", "screencap", "-p", binary=True)
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Screenshot is not PNG")
        (directory / "screen.png").write_bytes(png)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        errors.append(str(exc))
    # A unique temporary dump only. Never overwrite a user's existing dump.
    remote = f"/data/local/tmp/mobile-arena-{uuid.uuid4().hex}.xml"
    try:
        adb(serial, "shell", "uiautomator", "dump", remote, timeout=30)
        xml = adb(serial, "shell", "cat", remote)
        add_ui_evidence(observed, xml)
        (directory / "ui.xml").write_text(xml, encoding="utf-8")
    except (RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        errors.append(str(exc))
    finally:
        try:
            adb(serial, "shell", "rm", "-f", remote)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            errors.append(f"Temporary UI dump cleanup failed: {exc}")
    observed["evidence_errors"] = errors
    save(directory / "state.json", observed)
    return observed
