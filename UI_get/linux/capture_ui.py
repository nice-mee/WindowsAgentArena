#!/usr/bin/env python3
"""Capture Linux desktop and AT-SPI tree; draw visible control IDs.

Run from the graphical desktop session using /usr/bin/python3.
Dependencies (Ubuntu/Debian): python3-pyatspi python3-pil python3-gi gir1.2-gtk-3.0
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', help='Only traverse applications whose name contains this text')
    parser.add_argument('--all-windows', action='store_true', help='Explicitly traverse all showing windows, including occluded windows')
    parser.add_argument('--include-text', action='store_true', help='Also annotate named static text/labels')
    parser.add_argument('--delay', type=float, default=3, help='Seconds to prepare the desktop')
    parser.add_argument('--max-nodes', type=int, default=5000)
    parser.add_argument('--max-depth', type=int, default=40)
    parser.add_argument('--seconds', type=float, default=30, help='Traversal time budget')
    args = parser.parse_args()
    if args.max_nodes < 1 or args.max_depth < 1 or args.seconds <= 0 or args.delay < 0:
        parser.error('Limits must be positive and delay must be nonnegative')
    try:
        import pyatspi
        import gi
        gi.require_version('Gdk', '3.0')
        from gi.repository import Gdk, Atspi
        from PIL import Image, ImageDraw, ImageFont, ImageGrab
    except ImportError as exc:
        raise RuntimeError(f'{exc}. Use /usr/bin/python3; see README.md for dependencies.')

    Atspi.set_timeout(1000, 2000)
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError('No graphical display. Run inside the logged-in desktop session.')
    geometries = [display.get_monitor(i).get_geometry() for i in range(display.get_n_monitors())]
    if not geometries:
        raise RuntimeError('No monitors found')
    left = min(r.x for r in geometries)
    top = min(r.y for r in geometries)
    right = max(r.x + r.width for r in geometries)
    bottom = max(r.y + r.height for r in geometries)
    output = Path(__file__).resolve().parent / 'outputs' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True)
    print(f'Capture in {args.delay:g}s. Keep the desktop unchanged.\nOutput: {output}', flush=True)
    time.sleep(args.delay)
    session = os.environ.get('XDG_SESSION_TYPE', '')
    if session == 'wayland':
        # Desktop-specific fallback; may require consent or be unsupported.
        subprocess.run(['gnome-screenshot', '-f', str(output / 'screen.png')],
                       check=True, capture_output=True, timeout=30)
        with Image.open(output / 'screen.png') as image:
            screenshot = image.convert('RGB')
        backend = 'gnome-screenshot'
    else:
        screenshot = ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).convert('RGB')
        screenshot.save(output / 'screen.png')
        backend = 'Pillow ImageGrab / X11'
    sx, sy = screenshot.width / (right - left), screenshot.height / (bottom - top)
    errors, controls, tree, lines, apps = [], [], [], [], []
    selected_windows = []
    window_inventory = []
    selection_warning = None
    active_pid, active_title = None, ''
    if not args.app and not args.all_windows and session != 'wayland':
        # AT-SPI ACTIVE flags can be stale; consult the X11 window manager.
        root_prop = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
        match = re.search(r'0x[0-9a-fA-F]+', root_prop)
        if not match or int(match.group(), 16) == 0:
            raise RuntimeError('No active X11 window; select a target with --app.')
        props = subprocess.check_output(['xprop', '-id', match.group(), '_NET_WM_PID', '_NET_WM_NAME', 'WM_NAME'], text=True)
        pid_match = re.search(r'_NET_WM_PID.*?=\s*(\d+)', props)
        active_pid = int(pid_match.group(1)) if pid_match else None
        title_match = re.search(r'(?:_NET_WM_NAME|WM_NAME)\([^)]*\) = "(.*)"', props)
        active_title = title_match.group(1) if title_match else ''

    started = time.monotonic()
    count = 0
    truncated = False

    def visit(node, parent, depth, app):
        nonlocal count, truncated
        if count >= args.max_nodes or depth > args.max_depth or time.monotonic() - started > args.seconds:
            truncated = True
            return
        count += 1
        node_id = str(count)
        record = {'id': node_id, 'parent_id': parent, 'depth': depth, 'application': app}
        tree.append(record)
        try:
            record.update(name=node.name or '', role=node.getRoleName(), description=node.description or '')
            states = node.getState()
            record['states'] = [str(s) for s in states.getStates()]
            record['showing'] = states.contains(pyatspi.STATE_SHOWING)
            record['visible'] = states.contains(pyatspi.STATE_VISIBLE)
            record['attributes'] = node.getAttributes()
            interfaces = list(pyatspi.listInterfaces(node))
            record['interfaces'] = interfaces
            if 'Component' in interfaces:
                rect = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
                record['rect'] = [rect.x, rect.y, rect.x + rect.width, rect.y + rect.height]
            if 'Action' in interfaces:
                action = node.queryAction()
                record['actions'] = [action.getName(i) for i in range(action.nActions)]
            lines.append('  ' * depth + f"[{node_id}] {record['role']} {record['name']!r} {record.get('rect', '')}")
            rect = record.get('rect')
            interactive_roles = {'push button', 'toggle button', 'check box', 'radio button',
                                 'entry', 'password text', 'combo box', 'list item', 'tree item',
                                 'menu item', 'check menu item', 'radio menu item', 'page tab',
                                 'link', 'slider', 'spin button', 'scroll bar'}
            structural_roles = {'application', 'frame', 'window', 'panel', 'section',
                                'filler', 'root pane', 'scroll pane', 'viewport', 'tool bar',
                                'document web', 'page tab list', 'menu', 'menu bar', 'status bar',
                                'list', 'tree', 'landmark', 'document frame', 'embedded',
                                'internal frame', 'canvas', 'paragraph', 'heading', 'static', 'label', 'text'}
            direct_actions = [a for a in record.get('actions', [])
                              if a.lower() not in {'clickancestor', 'showcontextmenu'}]
            actionable = (record['role'] in interactive_roles
                          or states.contains(pyatspi.STATE_EDITABLE)
                          or (bool(direct_actions) and record['role'] not in structural_roles))
            text_requested = args.include_text and record['role'] in {'static', 'text', 'label', 'heading'} and record['name']
            if rect and record['visible'] and record['showing'] and (actionable or text_requested):
                x1, y1, x2, y2 = rect
                if x2 > x1 and y2 > y1 and x2 > left and y2 > top and x1 < right and y1 < bottom:
                    control = dict(record)
                    control['image_rect'] = [max(0, round((x1-left)*sx)), max(0, round((y1-top)*sy)),
                                             min(screenshot.width-1, round((x2-left)*sx)),
                                             min(screenshot.height-1, round((y2-top)*sy))]
                    controls.append(control)
            child_count = node.childCount
            record['child_count'] = child_count
            for index in range(child_count):
                if count >= args.max_nodes or time.monotonic() - started > args.seconds:
                    truncated = True
                    break
                try:
                    child = node.getChildAtIndex(index)
                    if child is not None:
                        visit(child, node_id, depth + 1, app)
                except Exception as exc:
                    errors.append({'parent_id': node_id, 'child_index': index, 'error': str(exc)})
        except Exception as exc:
            record['error'] = str(exc)
            errors.append({'id': node_id, 'error': str(exc)})

    desktop = pyatspi.Registry.getDesktop(0)
    candidates = []
    for index in range(desktop.childCount):
        try:
            app = desktop.getChildAtIndex(index)
            name = app.name or ''
            apps.append(name)
            if args.app and args.app.casefold() not in name.casefold():
                continue
            for window in app:
                states = window.getState()
                showing = states.contains(pyatspi.STATE_SHOWING)
                window_inventory.append({'application': name, 'pid': app.get_process_id(),
                                         'title': window.name, 'showing': showing,
                                         'active': states.contains(pyatspi.STATE_ACTIVE)})
                if args.app or args.all_windows:
                    if showing:
                        candidates.append((app, window, name))
                elif session == 'wayland':
                    if showing and states.contains(pyatspi.STATE_ACTIVE):
                        candidates.append((app, window, name))
                elif ((active_pid is not None and app.get_process_id() == active_pid)
                      or (active_title and window.name == active_title)):
                    # Match identity before considering visibility: Chromium may
                    # expose the real frame with SHOWING=False and unnamed popups
                    # with SHOWING=True. Child visibility remains checked for drawing.
                    candidates.append((app, window, name))
        except Exception as exc:
            errors.append({'application_index': index, 'error': str(exc)})
    if not args.app and not args.all_windows and session != 'wayland':
        exact_both = [c for c in candidates if active_title and c[1].name == active_title
                      and active_pid is not None and c[0].get_process_id() == active_pid]
        exact_title = [c for c in candidates if active_title and c[1].name == active_title]
        pid_showing = [c for c in candidates if c[0].get_process_id() == active_pid
                       and c[1].getState().contains(pyatspi.STATE_SHOWING)]
        candidates = next((group for group in (exact_both, exact_title, pid_showing)
                           if len(group) == 1), [])
    if not candidates:
        selection_warning = ('No unambiguous AT-SPI target. Screenshot retained; no controls annotated. '
                             'Inspect window_inventory in metadata.json; --app can select an exposed application.')
        print(f'Warning: {selection_warning}', flush=True)
    for app, window, name in candidates:
        selected_windows.append({'application': name, 'window': window.name})
        visit(window, None, 0, name)
    # Preserve the entire collected tree, but deduplicate drawing rectangles and
    # use separate consecutive visual IDs (large tree IDs are not control counts).
    unique, seen = [], set()
    for control in controls:
        key = tuple(control['image_rect'])
        if key in seen:
            continue
        seen.add(key)
        control['node_id'] = control['id']
        control['id'] = str(len(unique) + 1)
        unique.append(control)
    controls = unique
    for filename, data in [('ui_tree.json', tree), ('controls.json', controls)]:
        (output / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'ui_tree.txt').write_text('\n'.join(lines), encoding='utf-8')
    overlay = Image.new('RGBA', screenshot.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for control in controls:
        draw.rectangle(control['image_rect'], outline=(255, 70, 40, 220), fill=(255, 180, 0, 15), width=2)
    annotated = Image.alpha_composite(screenshot.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(annotated)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(12, screenshot.width // 130))
    except OSError:
        font = ImageFont.load_default()
    for control in controls:
        label = control['id']
        box = draw.textbbox((0, 0), label, font=font)
        w, h = box[2]-box[0]+6, box[3]-box[1]+6
        x, y = control['image_rect'][:2]
        x, y = min(x, screenshot.width-w), min(y, screenshot.height-h)
        draw.rectangle((x, y, x+w, y+h), fill='yellow', outline='black')
        draw.text((x+3-box[0], y+3-box[1]), label, font=font, fill='black')
    annotated.save(output / 'screen_annotated.png')
    comparison = Image.new('RGB', (screenshot.width*2, screenshot.height))
    comparison.paste(screenshot, (0, 0))
    comparison.paste(annotated, (screenshot.width, 0))
    comparison.save(output / 'screen_comparison.png')
    metadata = {'session': session, 'screenshot_backend': backend, 'applications': apps,
                'active_window': {'pid': active_pid, 'title': active_title},
                'window_inventory': window_inventory, 'selection_warning': selection_warning,
                'app_filter': args.app, 'selected_windows': selected_windows,
                'all_windows': args.all_windows, 'include_text': args.include_text, 'nodes': count, 'annotated_controls': len(controls),
                'truncated': truncated, 'errors': errors, 'desktop_rect': [left, top, right, bottom],
                'image_size': list(screenshot.size), 'coordinate_scale': [sx, sy],
                'notes': ['Screenshot and tree are sequential, not atomic.',
                          'AT-SPI showing/visible does not guarantee a window is not occluded.',
                          'Mixed-DPI or Wayland coordinates may need desktop-specific calibration.']}
    (output / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Nodes: {count}; annotated: {len(controls)}; truncated: {truncated}; errors: {len(errors)}')
    if not controls:
        print('No annotatable controls: inspect ui_tree.json and metadata.json; application may not expose accessibility nodes.')
    print(f'Comparison: {output / "screen_comparison.png"}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Capture failed: {exc}', file=sys.stderr)
        sys.exit(1)
