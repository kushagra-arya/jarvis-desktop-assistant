from __future__ import annotations

import base64
import json
import struct
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


PAGE = Path(__file__).with_name("index.html")
FRAME_INTERVAL = 1 / 30


def main() -> int:
    desired = {"state": "idle", "level": 0.0}
    lock = threading.Lock()
    stopped = threading.Event()

    def read_commands() -> None:
        for line in sys.stdin.buffer:
            try:
                command = json.loads(line)
                state = command.get("state", "idle")
                level = max(0.0, min(1.0, float(command.get("level", 0))))
                if state not in ("idle", "listening", "thinking", "speaking", "sleeping"):
                    continue
                with lock:
                    desired.update(state=state, level=level)
            except (ValueError, TypeError):
                continue
        stopped.set()

    threading.Thread(target=read_commands, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = None
            page = None
            normal = ["--allow-file-access-from-files", "--no-sandbox"]
            software = normal + ["--disable-gpu", "--enable-unsafe-swiftshader"]
            for flags in (normal, software):
                for options in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
                    try:
                        browser = playwright.chromium.launch(
                            headless=True, args=flags, **options
                        )
                        page = browser.new_page(
                            viewport={"width": 900, "height": 760},
                            device_scale_factor=1,
                        )
                        page.goto(PAGE.as_uri(), wait_until="load", timeout=20000)
                        page.wait_for_function("Boolean(window.jarvisCore)",
                                               timeout=6000)
                        page.evaluate("window.jarvisCore.setAudioLevel(0)")
                        break
                    except Exception:
                        if browser is not None:
                            browser.close()
                        browser = None
                        page = None
                if page is not None:
                    break
            if page is None or browser is None:
                return 2
            try:
                session = page.context.new_cdp_session(page)
                next_frame = 0.0

                def on_frame(event: dict) -> None:
                    nonlocal next_frame
                    try:
                        now = time.monotonic()
                        if now >= next_frame and not stopped.is_set():
                            frame = base64.b64decode(event["data"])
                            sys.stdout.buffer.write(struct.pack("!I", len(frame)))
                            sys.stdout.buffer.write(frame)
                            sys.stdout.buffer.flush()
                            next_frame += FRAME_INTERVAL
                            if next_frame <= now:
                                next_frame = now + FRAME_INTERVAL
                    except (BrokenPipeError, OSError):
                        stopped.set()
                    finally:
                        session.send("Page.screencastFrameAck",
                                     {"sessionId": event["sessionId"]})

                session.on("Page.screencastFrame", on_frame)
                session.send("Page.startScreencast", {
                    "format": "png", "everyNthFrame": 1,
                    "maxWidth": 900, "maxHeight": 760,
                })
                previous = None
                while not stopped.is_set():
                    with lock:
                        current = desired.copy()
                    if current != previous:
                        page.evaluate("""command => {
                            window.jarvisCore.setState(command.state);
                            window.jarvisCore.setAudioLevel(command.level);
                        }""", current)
                        previous = current
                    page.wait_for_timeout(35)
                session.send("Page.stopScreencast")
            finally:
                browser.close()
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

