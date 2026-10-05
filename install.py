import platform
import subprocess
import sys
from pathlib import Path


OS = platform.system()
MIN_PY = (3, 11)
MAX_PY = (3, 13)


def _run(label: str, args: list[str]) -> None:
    print(f"\n[Setup] {label}")
    subprocess.run(args, check=True)


def _check_python() -> None:
    version = sys.version_info[:2]
    if version > MAX_PY:
        print(f"[Setup] Python {version[0]}.{version[1]} is newer than the tested "
              f"{MAX_PY[0]}.{MAX_PY[1]}; continuing.")
    if version < MIN_PY:
        print(f"[Setup] Python {version[0]}.{version[1]} is unsupported. "
              f"Use Python {MIN_PY[0]}.{MIN_PY[1]} or newer.")
        sys.exit(1)


def main() -> None:
    print(f"[Setup] Jarvis multimodal project on {OS or 'unknown'}, "
          f"Python {sys.version_info[0]}.{sys.version_info[1]}")
    _check_python()
    _run("Installing Python dependencies",
         [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    try:
        _run("Installing Playwright Chromium and Firefox",
             [sys.executable, "-m", "playwright", "install", "chromium", "firefox"])
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"[Setup] Browser installation skipped: {error}")
        print(f"[Setup] Retry: {sys.executable} -m playwright install chromium firefox")

    if OS == "Windows":
        try:
            import win32com.client
        except ImportError:
            postinstall = Path(sys.executable).parent / "Scripts" / "pywin32_postinstall.py"
            print("[Setup] pywin32 registration is unavailable; desktop shortcuts "
                  "will use a fallback.")
            print(f"[Setup] Repair: {sys.executable} {postinstall} -install")
    elif OS == "Linux":
        print("[Setup] Linux desktop actions may need pactl, brightnessctl, "
              "systemd-run or at, and xdg-open.")
    elif OS == "Darwin":
        print("[Setup] Safari automation needs the optional Playwright WebKit browser.")

    print("[Setup] Complete. Set GEMINI_API_KEY in .env, then run python main.py.")


if __name__ == "__main__":
    main()
