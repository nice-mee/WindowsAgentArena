"""One real GalaxyClient request, isolated in a process group by run.py."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def health(device):
    url = urlsplit(device.server_url)
    if url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Stage 1 requires a local Linux device and local trace files")
    token = parse_qs(url.query).get("token", [""])[0]
    request = Request(
        f"{'https' if url.scheme == 'wss' else 'http'}://{url.netloc}/api/health",
        headers={"X-API-Key": token},
    )
    with urlopen(request, timeout=2) as response:
        return json.load(response)


def start_local(device_id, run_dir):
    """Start only owned services; reuse the existing Linux MCP endpoint settings."""
    import yaml
    from galaxy.client.config_loader import DeviceConfig

    config = yaml.safe_load(Path("config/ufo/mcp.yaml").read_text())
    entries = config["LinuxAgent"]["default"]["action"]
    mcp = next(item for item in entries if item["namespace"] == "BashExecutor")
    if mcp["type"] != "http" or mcp["host"] not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("--local-services requires a local HTTP BashExecutor")
    port = int(mcp["port"])
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))  # Refuse to interfere with an existing MCP.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        server_port = probe.getsockname()[1]
    key_env = mcp.get("api_key_env", "UFO_MCP_API_KEY")
    mcp_key = os.environ.get(key_env) or secrets.token_urlsafe(32)
    os.environ[key_env] = mcp_key
    os.environ["UFO_MCP_API_KEY"] = mcp_key
    server_key = secrets.token_urlsafe(32)
    url = f"ws://127.0.0.1:{server_port}/ws?token={server_key}"
    commands = [
        ("mcp", ["-m", "ufo.client.mcp.http_servers.linux_mcp_server",
                 "--host", "127.0.0.1", "--port", str(port)]),
        ("server", ["-m", "ufo.server.app", "--host", "127.0.0.1",
                    "--port", str(server_port), "--platform", "linux", "--api-key", server_key]),
    ]
    processes = []

    def launch(name, command):
        with (run_dir / f"{name}.log").open("w") as stream:
            processes.append(subprocess.Popen([sys.executable, "-u", *command],
                                              stdout=stream, stderr=subprocess.STDOUT))

    for name, command in commands:
        launch(name, command)
    device = DeviceConfig(device_id=device_id, server_url=url, os="linux", max_retries=1)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("Local service exited during startup; see service logs")
        try:
            health(device)
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError("Local server startup timed out")
    launch("device", ["-m", "ufo.client.client", "--ws", "--ws-server", url,
                      "--client-id", device_id, "--platform", "linux", "--max-retries", "1"])
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("Local service exited; see service logs")
        if device_id in health(device).get("online_clients", []):
            return device
        time.sleep(0.5)
    raise RuntimeError("Linux device registration timed out")


async def execute(settings, run_dir):
    from galaxy.galaxy_client import GalaxyClient

    client = GalaxyClient(session_name=settings["run_id"], task_name=settings["run_id"])
    phase = "initialization"
    try:
        if settings["local_services"]:
            device = start_local(settings["device"], run_dir)
        else:
            matches = [d for d in client._device_config.devices
                       if d.device_id == settings["device"] and d.os.lower() == "linux"]
            if len(matches) != 1:
                raise RuntimeError("No matching Linux device in Galaxy devices.yaml; use --local-services")
            device = matches[0]
        if device.device_id not in health(device).get("online_clients", []):
            raise RuntimeError("Target Linux device is not registered on the server")
        # GalaxyClient has no device-config argument. Limit this instance, not the YAML.
        client._device_config.devices = [device]
        await client.initialize()
        manager = client._client.device_manager
        profile = manager.device_registry.get_device(device.device_id)
        if profile is None or profile.status.value not in {"connected", "idle"}:
            raise RuntimeError("Galaxy did not establish an idle Linux connection")
        save(run_dir / "initialization.json", {"status": "passed", "device": device.device_id})
        phase = "execution"
        result = await client.process_request(settings["request"])
        constellation = client._session.current_constellation if client._session else None
        tasks = constellation.to_dict()["tasks"] if constellation else {}
        queue = manager.get_task_queue_status(device.device_id)
        # Only successful TaskEnd-backed results establish completion here. A timeout
        # or disconnected device can also be marked failed locally without an ack.
        stopped = bool(tasks) and all(
            t["status"] == "completed" and t.get("result", {}).get("status") == "completed"
            for t in tasks.values()
        ) and not (queue["is_busy"] or queue["pending_task_ids"] or queue["queued_task_ids"])
        save(run_dir / "execution.json", {
            "status": "completed" if stopped and result.get("session_results", {}).get("status") == "FINISH" else "failed",
            "galaxy": result, "tasks": tasks, "device_queue": queue,
            "device_stopped_confirmed": stopped,
        })
    except Exception as exc:
        save(run_dir / f"{phase}.json", {"status": "failed", "error": str(exc)})
        raise
    finally:
        await client.shutdown()


if __name__ == "__main__":
    run_dir = Path(sys.argv[1]).resolve()
    settings = json.loads((run_dir / "request.json").read_text())
    os.chdir(settings["ufo_root"])
    sys.path.insert(0, settings["ufo_root"])
    asyncio.run(execute(settings, run_dir))
