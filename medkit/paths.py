from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "medkit"
APP_NAME = "MedKit"

# Where the 21:30 daily summary is appended. Overridable, in order:
#   1. MEDKIT_VAULT_FILE environment variable
#   2. {"vault_file": "..."} in ~/.config/medkit/config.json
#   3. the generic default below (never a personal path in the repo)
DEFAULT_VAULT_FILE = Path.home() / "Vaults" / "00-صحتي-والعناية" / "لوحة-الصحة.md"
USER_CONFIG = Path.home() / ".config" / "medkit" / "config.json"


def _vault_file_from_config() -> Path | None:
    try:
        raw = json.loads(USER_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = raw.get("vault_file")
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser()
    return None


VAULT_FILE = (
    Path(os.environ["MEDKIT_VAULT_FILE"]).expanduser()
    if os.environ.get("MEDKIT_VAULT_FILE")
    else (_vault_file_from_config() or DEFAULT_VAULT_FILE)
)


def data_dir() -> Path:
    override = os.environ.get("MEDKIT_DATA_DIR")
    return Path(override).expanduser() if override else DEFAULT_DATA_DIR


def medicines_file() -> Path:
    return data_dir() / "medicines.json"


def history_file() -> Path:
    return data_dir() / "history.jsonl"


def state_file() -> Path:
    return data_dir() / "state.json"


def emergency_log() -> Path:
    return data_dir() / "emergency.log"


def dashboard_command_file() -> Path:
    # One-shot command channel from the CLI into a running dashboard process.
    return data_dir() / "dashboard.cmd"


def icon_dir() -> Path:
    return data_dir() / "icons"


def medkit_bin() -> Path:
    return PROJECT_DIR / "bin" / "medkit"


def ensure_data_dir() -> Path:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory
