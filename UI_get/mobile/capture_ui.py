#!/usr/bin/env python3
"""Capture Android screenshot, UI XML and numbered controls via ADB.

Run: /usr/bin/python3 capture_ui.py [--serial DEVICE_SERIAL]
Requires: adb on PATH and Pillow in the selected Python environment.
"""

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", help="ADB device serial (required if multiple devices)")
    parser.add_argument("--adb", default="adb", help="ADB executable")
    args = parser.parse_args()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        parser.exit(1, "Missing Pillow. Install with: python -m pip install Pillow\n")

    def run(command, timeout=60):
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace").strip()
                               or result.stdout.decode(errors="replace").strip())
        return result.stdout

    devices = run([args.adb, "devices"]).decode().splitlines()[1:]
    online = [line.split()[0] for line in devices
              if len(line.split()) >= 2 and line.split()[1] == "device"]
    if args.serial:
        if args.serial not in online:
            raise RuntimeError("Selected device is not connected/authorized. Check adb devices.")
        serial = args.serial
    elif len(online) == 1:
        serial = online[0]
    else:
        raise RuntimeError("Connect and authorize one device, or select one with --serial. "
                           f"Available devices: {online}")
    adb = [args.adb, "-s", serial]
    output = Path(__file__).resolve().parent / "outputs" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output.mkdir(parents=True)
    remote = f"/sdcard/ufo_ui_{output.name}.xml"
    try:
        print(f"Device: {serial}\nKeep the phone unlocked and the screen unchanged.", flush=True)
        # Delete any possible previous dump so a failed dump cannot return stale XML.
        run(adb + ["shell", "rm", "-f", remote])
        run(adb + ["shell", "uiautomator", "dump", remote])
        xml = run(adb + ["exec-out", "cat", remote])
        root = ET.fromstring(xml)
        (output / "window_dump.xml").write_bytes(xml)
        # These are sequential observations, not an atomic snapshot.
        png = run(adb + ["exec-out", "screencap", "-p"])
        (output / "screen.png").write_bytes(png)
    finally:
        try:
            run(adb + ["shell", "rm", "-f", remote], timeout=10)
        except (RuntimeError, subprocess.TimeoutExpired):
            pass

    ET.indent(root, space="  ")
    ET.ElementTree(root).write(output / "window_dump_pretty.xml", encoding="utf-8", xml_declaration=True)
    controls = []
    for node in root.iter("node"):
        attrs = dict(node.attrib)
        bounds = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", attrs.get("bounds", ""))
        if not bounds:
            continue
        left, top, right, bottom = map(int, bounds.groups())
        if right <= left or bottom <= top:
            continue
        name = attrs.get("text") or attrs.get("content-desc") or ""
        kind = attrs.get("class", "").split(".")[-1]
        meaningful = any(attrs.get(key) == "true" for key in
                         ("clickable", "long-clickable", "checkable", "scrollable"))
        if not (meaningful or name or "Edit" in kind or "Button" in kind):
            continue
        controls.append({"id": str(len(controls) + 1), "name": name or kind,
                         "type": kind, "rect": [left, top, right, bottom],
                         "attributes": attrs})
    (output / "controls.json").write_text(json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8")

    with Image.open(output / "screen.png") as source:
        original = source.convert("RGBA")
    overlay = Image.new("RGBA", original.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    palette = [(230, 60, 60), (0, 130, 220), (20, 155, 80), (165, 70, 205)]
    for index, control in enumerate(controls):
        color = palette[index % len(palette)]
        draw.rectangle(control["rect"], fill=(*color, 25), outline=(*color, 230), width=3)
    annotated = Image.alpha_composite(original, overlay).convert("RGB")
    draw = ImageDraw.Draw(annotated)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(16, original.width // 55))
    except OSError:
        font = ImageFont.load_default()
    for control in controls:
        label = control["id"]
        box = draw.textbbox((0, 0), label, font=font)
        width, height = box[2] - box[0] + 8, box[3] - box[1] + 8
        x = max(0, min(control["rect"][0], annotated.width - width))
        y = max(0, min(control["rect"][1], annotated.height - height))
        draw.rectangle((x, y, x + width, y + height), fill="yellow", outline="black")
        draw.text((x + 4 - box[0], y + 4 - box[1]), label, fill="black", font=font)
    annotated.save(output / "screen_annotated.png")
    comparison = Image.new("RGB", (original.width * 2, original.height), "white")
    comparison.paste(original.convert("RGB"), (0, 0))
    comparison.paste(annotated, (original.width, 0))
    comparison.save(output / "screen_comparison.png")
    (output / "metadata.json").write_text(json.dumps({
        "device": serial, "size": list(original.size), "control_count": len(controls),
        "note": "XML and screenshot captured sequentially. IDs are temporary, not Android resource-id."
    }, indent=2), encoding="utf-8")
    print(f"Saved {len(controls)} controls to: {output}\nComparison: screen_comparison.png")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired, ET.ParseError) as error:
        print(f"Capture failed: {error}", file=sys.stderr)
        sys.exit(1)
