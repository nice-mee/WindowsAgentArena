
This repository contains a modified version of [**Windows Agent Arena (WAA) 🪟**](https://github.com/microsoft/WindowsAgentArena) , a scalable Windows AI agent platform for testing and benchmarking multi-modal, desktop AI agents. This modified version focuses on integration with [UFO](https://github.com/microsoft/UFO), a UI-Focused Agent for Windows OS Interaction.

## 💻 Deployment Guide (WSL)

We highly recommend you have a look at the deployment guide from the original [WindowsAgentArena](https://github.com/microsoft/WindowsAgentArena) repository. Our guide here assumes you are familiar with the deployment process of the original repository. The following steps will help you set up the environment for running the UFO agent in the Windows Agent Arena.

### 1. Setup the repository

Clone the repository
```bash
git clone https://github.com/nice-mee/WindowsAgentArena.git
```

> Note: If you want to run OSWorld cases, checkout the `osworld` branch.
> ```bash
> git checkout osworld
> ```

Create a `config.json` file in the root of WAA repo, the API key here doesn't matter, since UFO will only use the key from its own config file.

```json
{
    "OPENAI_API_KEY": "placeholder"
}
```

### 2. Prepare the Windows Arena Docker Image

Next, build the WinArena image locally:

```bash
cd scripts
chmod +x build-container-image.sh # (if required)
chmod +x prepare-agents.sh # (if required)
./build-container-image.sh --build-base-image true
```

This will create the `windowsarena/winarena:latest` image with the latest code from the `src` directory.

### 3. Configure UFO

You should first configure UFO with `ufo/config/config.json` (refer to UFO repo for details). Then copy the entire `ufo` folder to `WindowsAgentArena/src/win-arena-container/client/`.

```bash
cp -r src/win-arena-container/vm/setup/mm_agents/UFO/ufo src/win-arena-container/client/
```

Remember to swap the order of `@staticmethod` and `@functools.lru_cache()` in `src/win-arena-container/client/ufo/llm/openai.py`, this is actually due to a bug in Python 3.9 and unfortunately WAA uses Python 3.9 instead of higher versions (UFO uses Python 3.10).

### 4. Prepare the Windows 11 VM
#### 4.1 Download Windows 11 Evaluation .iso file:
1. Visit [Microsoft Evaluation Center](https://info.microsoft.com/ww-landing-windows-11-enterprise.html), accept the Terms of Service, and download a **Windows 11 Enterprise Evaluation (90-day trial, English, United States)** ISO file [~6GB]
2. After downloading, rename the file to `setup.iso` and copy it to the directory `WindowsAgentArena/src/win-arena-container/vm/image`

#### 4.2 Automatic Setup of the Windows 11 golden image:
Before running the arena, you need to prepare a new WAA snapshot (also referred as WAA golden image). This 30GB snapshot represents a fully functional Windows 11 VM with all the programs needed to run the benchmark. This VM additionally hosts a Python server which receives and executes agent commands. To learn more about the components at play, see our [local](/img/architecture-local.png) and [cloud](/img/architecture-azure.png) components diagrams.

To prepare the gold snapshot, run **once**:
```bash
cd ./scripts
./run-local.sh --mode dev --prepare-image true
```
**Please do not interfere with the VM while it is being prepared. It will automatically shut down when the provisioning process is complete.**

You will find the 30GB WAA golden image in `WindowsAgentArena/src/win-arena-container/vm/storage`.

### 5. Start Initial Run

Start the initial run with this command:
```bash
./run-local.sh --mode dev --json-name "evaluation_examples_windows/test_custom.json" --agent UFO --agent-settings '{"llm_type": "azure", "llm_endpoint": "https://cloudgpt-openai.azure-api.net/openai/deployments/gpt-4o-20240513/chat/completions?api-version=2024-04-01-preview", "llm_auth": {"type": "api-key", "token": ""}}'
```

After booting up, wait until the device code prompt shows up, then do not enter the device code. This will block the WAA server forever as long as you don't enter the device code.


Instead, visit `localhost:8006` and control the WAA Windows, do the following things:

1. Disable Windows Firewall.
2. Open Google Chrome and complete the initial setup.
3. Open VLC and complete the initial setup.
4. Activate Office 365 (Word, Excel, PPT)


After completing these steps, kill the WAA client, then copy the "golden" image under `storage` folder to somewhere else.

### Config OSWorld setting
Config OSWorld setting under `evaluation_examples_windows/settings`
[How to setup the setting in OSWorld](https://github.com/xlang-ai/OSWorld/blob/main/ACCOUNT_GUIDELINE.md)

### How to Perform an Experiment Run

Before an experiment run, do the following things:

1. Replace image with previously obtained golden image
2. Delete the UFO logs

Then run this command:
```bash
./run-local.sh --mode dev --json-name "evaluation_examples_windows/test_osworld.json" --agent UFO --agent-settings '{"llm_type": "azure", "llm_endpoint": "https://cloudgpt-openai.azure-api.net/openai/deployments/gpt-4o-20240513/chat/completions?api-version=2024-04-01-preview", "llm_auth": {"type": "api-key", "token": ""}}
```

You probably will use a different LLM type or endpoint, so make sure to change the `--agent-settings` parameter accordingly.

