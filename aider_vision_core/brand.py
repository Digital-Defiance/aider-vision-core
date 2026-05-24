"""
Product identity for the aider-vision stack.

Two audiences
-------------
* **End user** (bubbled through the Aider Vision app): prefer **Aider Vision**.
* **Developer / support** (logs, crash reports, GitHub): **Aider Vision Core**.

When the desktop app spawns Core it sets ``AIDER_VISION_LAUNCHER=1``. In that mode,
user-visible messages use the Vision product name; technical attribution stays on Core.
"""

from __future__ import annotations

import os

# Technical ids (pip, import path, CLI)
PRODUCT_CORE = "aider-vision-core"
PRODUCT_VISION = "aider-vision"

# Human-readable product names
DISPLAY_VISION = "Aider Vision"
DISPLAY_CORE = "Aider Vision Core"

# Set by the Aider Vision desktop app when it spawns the Core process
LAUNCHER_ENV = "AIDER_VISION_LAUNCHER"
LAUNCHER_VERSION_ENV = "AIDER_VISION_APP_VERSION"


def is_launched_by_vision() -> bool:
    return os.environ.get(LAUNCHER_ENV, "").strip() in ("1", "true", "yes")


def user_facing_name() -> str:
    """Name shown to people using the Aider Vision app."""
    if is_launched_by_vision():
        return DISPLAY_VISION
    return DISPLAY_CORE


def support_name() -> str:
    """Name for engineers, pip, and issue trackers."""
    return DISPLAY_CORE


def version_banner() -> str:
    """Startup banner in the terminal."""
    from aider_vision_core import __version__

    if is_launched_by_vision():
        return f"{DISPLAY_VISION} · agent {DISPLAY_CORE} v{__version__}"
    return f"{DISPLAY_CORE} ({PRODUCT_CORE}) v{__version__}"


def launcher_context_lines() -> list[str]:
    """Extra lines for crash reports when Core was started by the desktop app."""
    if not is_launched_by_vision():
        return []
    app_ver = os.environ.get(LAUNCHER_VERSION_ENV, "unknown")
    return [
        f"User-facing product: {DISPLAY_VISION}",
        f"Launched by: {DISPLAY_VISION} ({PRODUCT_VISION}) {app_ver}",
        f"Technical component: {DISPLAY_CORE} ({PRODUCT_CORE})",
        "",
    ]


def user_facing_prefix() -> str:
    return f"[{user_facing_name()}]"


def support_prefix() -> str:
    return f"[{support_name()}]"


def format_user_error(message: str) -> str:
    """
    Format an error that will be shown to the user (e.g. via the Vision app).

    When running inside Vision, do not tell users "Aider Vision Core failed" for
  generic failures — they are using Aider Vision.
    """
    message = message.strip()
    if not message or not is_launched_by_vision():
        return message
    prefix = user_facing_prefix()
    if message.startswith("["):
        return message
    return f"{prefix} {message}"
