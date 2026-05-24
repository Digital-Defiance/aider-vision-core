# Aider Vision product split

## Two products

| | **Aider Vision** | **Aider Vision Core** |
|---|------------------|------------------------|
| **What users see** | Desktop app window | Agent running in terminal / behind the app |
| **Repo** | `aider-vision` | `aider-vision-core` |
| **Install** | App bundle / Tauri build | `pip install aider-vision-core` |
| **Typical errors** | Won’t start, can’t connect to Core, UI bugs | LLM, git, repo-map, edits, API |

**Aider Vision** is the shell. **Aider Vision Core** is the coding agent (fork of Aider).

## Who to blame (for users)

**In the Aider Vision app**, most errors shown in chat use **`[Aider Vision]`** even when the agent (Core) failed — because that is the product people opened.

| Where | Label |
|-------|--------|
| Chat / main errors | **Aider Vision** |
| Terminal tab (technical log) | **Aider Vision Core** (full detail) |
| Crash report file / GitHub (developers) | **Aider Vision Core** + “launched by Vision” |

- **Can’t start**, window, settings → **Aider Vision**
- **Model / git / repo map** → still Core under the hood; users see **Aider Vision** in chat, engineers see Core in the technical log

## For developers

- Core reads `AIDER_VISION_LAUNCHER=1` when the desktop app spawns it (crash reports include both versions).
- Prefer separate GitHub issues: `Digital-Defiance/aider-vision` vs `Digital-Defiance/aider-vision-core`.
- Shared branding constants: `aider_vision_core/brand.py` and `aider-vision/src/brand.ts`.
