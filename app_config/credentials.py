import json
import os
import sys
import threading
from pathlib import Path


BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
SETTINGS_FILE = BASE_DIR / "app_config" / "api_keys.json"
_LOCK = threading.RLock()


def _env_key() -> str:
    try:
        lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        name, sep, value = line.partition("=")
        if not sep or name.strip().removeprefix("export ").strip() != "GEMINI_API_KEY":
            continue
        value = value.strip()
        if value.startswith('"'):
            try:
                return str(json.loads(value)).strip()
            except (ValueError, TypeError):
                return ""
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1].strip()
        return value.split(" #", 1)[0].strip()
    return ""


def _legacy_settings() -> dict:
    try:
        value = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_env_key(key: str) -> None:
    if not key or "\n" in key or "\r" in key:
        raise ValueError("GEMINI_API_KEY must be one line")
    try:
        lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    kept = [line for line in lines
            if line.partition("=")[0].strip().removeprefix("export ").strip()
            != "GEMINI_API_KEY"]
    kept.append("GEMINI_API_KEY=" + json.dumps(key, ensure_ascii=False))
    temporary = ENV_FILE.with_name(".env.tmp")
    temporary.write_text("\n".join(kept) + "\n", encoding="utf-8")
    if os.name != "nt":
        os.chmod(temporary, 0o600)
    temporary.replace(ENV_FILE)


def _remove_legacy_key(settings: dict) -> None:
    if "gemini_api_key" not in settings:
        return
    settings.pop("gemini_api_key")
    temporary = SETTINGS_FILE.with_name("api_keys.json.tmp")
    temporary.write_text(json.dumps(settings, indent=4) + "\n", encoding="utf-8")
    temporary.replace(SETTINGS_FILE)


def migrate_legacy_key() -> bool:
    with _LOCK:
        settings = _legacy_settings()
        old_key = str(settings.get("gemini_api_key") or "").strip()
        if not old_key:
            return False
        if not _env_key():
            try:
                _write_env_key(old_key)
            except OSError:
                return False
        if _env_key():
            try:
                _remove_legacy_key(settings)
            except OSError:
                return False
            return True
        return False


def get_gemini_key() -> str:
    migrate_legacy_key()
    return (os.environ.get("GEMINI_API_KEY", "").strip()
            or _env_key()
            or str(_legacy_settings().get("gemini_api_key") or "").strip())


def save_gemini_key(key: str) -> None:
    with _LOCK:
        _write_env_key(key.strip())
        _remove_legacy_key(_legacy_settings())
