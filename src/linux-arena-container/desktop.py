"""Open the fixed applications in profiles owned by this run."""
import json
import os
import subprocess


def open_application(application, filename, run_dir):
    profile = run_dir / "application-profile" / application
    profile.mkdir(parents=True)
    if application == "code":
        (profile / "User").mkdir()
        (profile / "User/settings.json").write_text(json.dumps({
            "workbench.startupEditor": "none", "window.restoreWindows": "none",
            "files.hotExit": "off", "files.autoSave": "off",
            "security.workspace.trust.enabled": False,
            "telemetry.telemetryLevel": "off", "update.mode": "none",
        }))
        command = ["code", "--new-window", "--wait", "--disable-extensions",
                   "--user-data-dir", str(profile), "--skip-welcome",
                   "--skip-release-notes", str(filename)]
    elif application in {"calc", "writer", "impress"}:
        command = [os.environ.get("ARENA_LIBREOFFICE", "libreoffice"),
                   f"-env:UserInstallation={profile.as_uri()}",
                   f"--{application}", "--norestore", "--nofirststartwizard", str(filename)]
    elif application == "chrome":
        command = ["google-chrome", f"--user-data-dir={profile}", "--no-first-run",
                   "--no-default-browser-check", "--disable-background-mode",
                   "--new-window", filename.resolve().as_uri()]
    else:
        raise ValueError(f"Unknown application: {application}")
    with (run_dir / f"application-{application}.log").open("w") as stream:
        return subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True)
