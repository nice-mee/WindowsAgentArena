"""One real Galaxy request using owned, serial-pinned Mobile services."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from phone import redact_secret, save


def health(url, key):
    with urlopen(Request(url, headers={"X-API-Key": key}), timeout=2) as response:
        return json.load(response)


def _read_json(path):
    """Read a JSON file, returning None instead of raising."""
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def _condense_task_latency(summary):
    """Keep the evaluation record small: shares, totals and the worst steps."""
    if not isinstance(summary, dict):
        return {"available": False}

    def _field(block, key):
        return (block or {}).get(key)

    phases = summary.get("phases") or {}
    return {
        "available": True,
        "step_count": summary.get("step_count"),
        "total_s": summary.get("total_s"),
        "phase_sum_s": {name: _field(stats, "sum_s") for name, stats in phases.items()},
        "phase_share": {name: _field(stats, "share") for name, stats in phases.items()},
        "llm": {
            key: _field(summary.get("llm"), key)
            for key in ("calls", "retries", "models", "prompt_chars",
                        "completion_chars", "images", "image_bytes")
        },
        "gaps": summary.get("gaps"),
        "slow_steps": summary.get("slow_steps"),
        "outliers": summary.get("outliers"),
    }


def collect_task_latency(logs_root):
    """Map every task log directory to its condensed latency summary."""
    latency = {}
    if not logs_root.exists():
        return latency
    for entry in sorted(logs_root.iterdir()):
        if not entry.is_dir() or entry.name == "galaxy":
            continue
        summary = _read_json(entry / "latency.json")
        if summary:
            latency[entry.name] = _condense_task_latency(summary)
    return latency


def attach_task_latency(tasks, logs_root):
    """Attach latency summaries to the matching task entries in-place."""
    by_dir = collect_task_latency(logs_root)
    for task_id, task in tasks.items():
        match = next(
            (summary for name, summary in by_dir.items() if task_id in name), None
        )
        task["latency"] = match or {"available": False, "reason": "no latency.json"}
    return tasks


def attach_session_latency(result, logs_root, run_id):
    """Attach the Galaxy session rollup (planning/editing overhead) to the result."""
    summary = _read_json(logs_root / "galaxy" / run_id / "latency.json")
    if not summary:
        result.setdefault("latency", {"available": False, "reason": "no latency.json"})
        return result
    constellation = summary.get("constellation") or {}
    result["latency"] = {
        "available": True,
        "session_total_s": summary.get("session_total_s"),
        "tasks_total_s": summary.get("tasks_total_s"),
        "constellation_total_s": constellation.get("total_s"),
        "constellation_rounds": constellation.get("step_count"),
        "untracked_s": summary.get("untracked_s"),
    }
    return result


def validate_mobile_profile(profile):
    """Reject host-PC metadata before it can reach Galaxy's planner."""
    if profile is None or profile.status.value not in {"connected", "idle"}:
        raise RuntimeError("Galaxy did not establish an idle Mobile connection")
    system = profile.metadata.get("system_info", {})
    capabilities = set(profile.capabilities)
    if (profile.os != "mobile" or system.get("platform") != "mobile"
            or system.get("platform_type") != "mobile"
            or not {"mobile_touch", "mobile_apps"} <= capabilities
            or capabilities & {"cli", "office", "linux_apps", "windows_apps", "macos_apps"}):
        raise RuntimeError(
            "Mobile device profile is missing or conflicts with host metadata: "
            f"os={profile.os}, platform={system.get('platform')}, "
            f"platform_type={system.get('platform_type')}, capabilities={sorted(capabilities)}"
        )


async def start_local(settings, run_dir):
    import yaml
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    from galaxy.client.config_loader import DeviceConfig

    config = yaml.safe_load(Path("config/ufo/mcp.yaml").read_text())["MobileAgent"]["default"]
    endpoints = []
    for kind, namespace in (("data_collection", "MobileDataCollector"), ("action", "MobileActionExecutor")):
        entry = next(e for e in config[kind] if e["namespace"] == namespace)
        if entry["type"] != "http" or entry["host"] not in {"localhost", "127.0.0.1"}:
            raise RuntimeError("Mobile arena requires local HTTP Mobile MCP endpoints")
        if entry.get("auth") != "${UFO_MCP_API_KEY}":
            raise RuntimeError("Mobile MCP auth must reference ${UFO_MCP_API_KEY} in existing config")
        endpoints.append(entry)
    for entry in endpoints:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", int(entry["port"])))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        server_port = probe.getsockname()[1]
    key = secrets.token_urlsafe(32)
    url = f"ws://127.0.0.1:{server_port}/ws?token={key}"
    processes = []

    def launch(name, args):
        path = os.devnull if settings["case"] == "unlock" else str(run_dir / f"{name}.log")
        with open(path, "w") as stream:
            processes.append(subprocess.Popen([sys.executable, "-u", *args],
                                              stdout=stream, stderr=subprocess.STDOUT))

    # One process with both MCP endpoints: they must share the control cache.
    launch("mcp", ["-m", "ufo.client.mcp.http_servers.mobile_mcp_server", "--server", "both",
                   "--host", "127.0.0.1", "--data-port", str(endpoints[0]["port"]),
                   "--action-port", str(endpoints[1]["port"])])
    launch("server", ["-m", "ufo.server.app", "--host", "127.0.0.1", "--port", str(server_port),
                      "--platform", "mobile", "--api-key", key])
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("Owned Mobile service exited during startup")
        try:
            health(f"http://127.0.0.1:{server_port}/api/health", key)
            for entry in endpoints:
                transport = StreamableHttpTransport(
                    url=f"http://127.0.0.1:{entry['port']}{entry.get('path', '/mcp')}",
                    auth=os.environ["UFO_MCP_API_KEY"])
                async with Client(transport, timeout=3) as client:
                    await asyncio.wait_for(client.list_tools(), timeout=5)
            break
        except Exception:
            await asyncio.sleep(0.5)
    else:
        raise RuntimeError("Mobile server/MCP startup timed out")
    launch("device", ["-m", "ufo.client.client", "--ws", "--ws-server", url,
                      "--client-id", settings["device"], "--platform", "mobile", "--max-retries", "1"])
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("Owned Mobile service exited")
        if settings["device"] in health(f"http://127.0.0.1:{server_port}/api/health", key).get("online_clients", []):
            return DeviceConfig(device_id=settings["device"], server_url=url, os="mobile", max_retries=1)
        await asyncio.sleep(0.5)
    raise RuntimeError("Mobile device registration timed out")


async def execute(settings, run_dir, pin):
    # Set before UFO's configuration loader expands environment references.
    os.environ["UFO_MCP_API_KEY"] = secrets.token_urlsafe(32)
    os.environ["ANDROID_SERIAL"] = settings["serial"]
    from galaxy.galaxy_client import GalaxyClient
    from cases import make_request

    def persist(name, data):
        # PIN must not appear in the retained execution/error records.
        save(run_dir / name, redact_secret(data, pin))

    client = GalaxyClient(session_name=settings["run_id"], task_name=settings["run_id"])
    phase = "initialization"
    try:
        device = await start_local(settings, run_dir)
        client._device_config.devices = [device]
        await client.initialize()
        manager = client._client.device_manager
        profile = manager.device_registry.get_device(device.device_id)
        validate_mobile_profile(profile)
        persist("initialization.json", {"status": "passed", "device": device.device_id,
                                       "os": profile.os, "capabilities": profile.capabilities,
                                       "system_info": profile.metadata["system_info"]})
        phase = "execution"
        # Forward the stored user request verbatim. Only the runtime PIN is
        # substituted for unlock; run IDs, device routing and grading stay internal.
        request = make_request("unlock", pin) if settings["case"] == "unlock" else settings["request"]
        persist("submission.json", {"status": "submitting", "device": device.device_id})
        result = await client.process_request(request)
        constellation = client._session.current_constellation if client._session else None
        tasks = constellation.to_dict()["tasks"] if constellation else {}
        queue = manager.get_task_queue_status(device.device_id)
        acknowledged = all(
            t["status"] == "completed" and (t.get("result") or {}).get("status") == "completed"
            for t in tasks.values()) and not (queue["is_busy"] or queue["pending_task_ids"] or queue["queued_task_ids"])
        complete = bool(tasks) and acknowledged and result.get("session_results", {}).get("status") == "FINISH"
        # Latency rollups are produced by UFO; attach them without ever failing the run.
        try:
            attach_task_latency(tasks, Path("logs"))
            attach_session_latency(result, Path("logs"), settings["run_id"])
        except Exception as exc:
            result.setdefault("latency", {"available": False, "reason": str(exc)})
        persist("execution.json", {"status": "completed" if complete else "failed", "tasks": tasks,
                                  "galaxy": result, "device_queue": queue,
                                  "device_stopped_confirmed": acknowledged})
    except Exception as exc:
        persist(f"{phase}.json", {"status": "failed", "error": str(exc)})
        raise
    finally:
        await client.shutdown()


if __name__ == "__main__":
    run_dir = Path(sys.argv[1]).resolve()
    settings = json.loads((run_dir / "request.json").read_text())
    pin = sys.stdin.readline().strip() if settings["case"] == "unlock" else ""
    sys.path.insert(0, settings["ufo_root"])
    asyncio.run(execute(settings, run_dir, pin))
