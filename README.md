# Aider Vision Core

Headless [Aider](https://aider.chat/) engine fork for [**Aider Vision**](https://aider-vision.digitaldefiance.org/) — a native desktop app (Tauri + React), not a VS Code clone. This repo is the **core** Python package: CLI, HTTP API, git/submodule workspaces, and docs for integrators.

**We support [Aider Vision](https://aider-vision.digitaldefiance.org/), not this fork as a standalone product.** Engine behavior and community live at [aider.chat](https://aider.chat/) and [Aider-AI/aider](https://github.com/Aider-AI/aider).

## Vision Core additions

- **HTTP API** — `aider-vision-core-serve` (FastAPI + SSE) for the Vision app and other clients
- **Headless runtime** — non-interactive flows for GUI-driven confirm/cancel
- **Git submodule workspaces** — superproject roots with nested submodules
- **Upstream alignment** — regular merges from Aider-AI/aider; small Vision-only delta

## Install

```bash
python -m pip install -U aider-vision-core

# HTTP server (default http://127.0.0.1:8741)
aider-vision-core-serve --workspace /path/to/git/repo

# CLI (same engine as upstream `aider`, renamed binary)
cd /path/to/your/project
aider-vision-core --model sonnet --api-key anthropic=<key>
```

## Documentation

- [Website / docs](aider_vision_core/website/) — fork-specific install, API, git
- [Upstream Aider docs](https://aider.chat/docs/) — most usage, models, and tutorials
- [GitHub (this fork)](https://github.com/Digital-Defiance/aider-vision-core)

## Links

| | |
|---|---|
| **Aider Vision** (app) | https://aider-vision.digitaldefiance.org/ |
| **Aider** (upstream) | https://aider.chat/ · https://github.com/Aider-AI/aider |
| **Issues (engine)** | https://github.com/Digital-Defiance/aider-vision-core/issues |
