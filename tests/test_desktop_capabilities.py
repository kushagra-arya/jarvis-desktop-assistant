import ctypes
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from PIL import Image

from capabilities import bluetooth_control, browser_control, clipboard_control, computer_control, computer_settings, quick_settings, screen_processor
from engine import chrome_window, clipboard, window_control


class ScreenshotTests(unittest.TestCase):
    def test_default_screenshot_uses_jarvis_folder(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(screen_processor.Path, "home", return_value=Path(tmp)), \
             patch.object(screen_processor, "capture_full_desktop_png", return_value=b"png"):
            saved = screen_processor.save_full_desktop_screenshot()
            self.assertEqual(saved.parent, Path(tmp) / "Pictures" / "Screenshots" / "JARVIS")
            self.assertEqual(saved.read_bytes(), b"png")

    def test_capture_uses_combined_monitor_without_resizing(self):
        image = Image.new("RGB", (2048, 1200), "#286a9a")
        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        png = png_buffer.getvalue()
        monitor = {"left": -1000, "top": 0, "width": 2048, "height": 1200}
        capture = MagicMock()
        capture.__enter__.return_value = capture
        capture.monitors = [monitor, {"left": 0, "top": 0, "width": 1048,
                                      "height": 1200}]
        capture.grab.return_value = SimpleNamespace(rgb=b"pixels", size=(2048, 1200))
        mss_stub = SimpleNamespace(mss=lambda: capture,
                                   tools=SimpleNamespace(to_png=lambda *_: png))

        with patch.object(screen_processor, "_MSS", True), \
             patch.object(screen_processor, "mss", mss_stub, create=True):
            image_bytes, mime = screen_processor._capture_screen()
            with tempfile.TemporaryDirectory() as tmp:
                saved = screen_processor.save_full_desktop_screenshot(
                    Path(tmp) / "whole.png")
                self.assertEqual(saved.read_bytes(), png)

        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(Image.open(io.BytesIO(image_bytes)).size, (2048, 1200))
        capture.grab.assert_called_with(monitor)


class ClipboardTests(unittest.TestCase):
    def test_empty_win32_formats_try_independent_reader(self):
        user32 = Mock()
        user32.OpenClipboard.return_value = 1
        user32.IsClipboardFormatAvailable.return_value = 0
        user32.CountClipboardFormats.return_value = 0
        with patch.object(clipboard.platform, "system", return_value="Windows"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=user32, kernel32=Mock()), create=True), \
             patch.object(clipboard, "_windows_powershell_text", return_value="Copied content") as fallback:
            result = clipboard.read_clipboard()
        self.assertIn("Copied content", result)
        fallback.assert_called_once()

    def test_dedicated_clipboard_tool_routes_read(self):
        with patch.object(clipboard_control, "read_clipboard", return_value="Clipboard text:\nA note"):
            result = clipboard_control.clipboard_control({"action": "read"})
        self.assertIn("A note", result)

    def test_history_clear_uses_windows_api_result(self):
        winrt_clipboard = SimpleNamespace(is_history_enabled=lambda: True,
                                          clear_history=lambda: True)
        with patch.dict(sys.modules, {
            "winrt.windows.applicationmodel.datatransfer":
                SimpleNamespace(Clipboard=winrt_clipboard),
        }), patch.object(clipboard.subprocess, "run") as powershell:
            result = clipboard._clear_windows_history()
        self.assertEqual(result, "cleared")
        powershell.assert_not_called()

    def test_windows_clipboard_reads_text_without_modifying_it(self):
        user32 = Mock()
        user32.OpenClipboard.return_value = 1
        user32.IsClipboardFormatAvailable.return_value = 1
        user32.GetClipboardData.return_value = 123
        kernel32 = Mock()
        kernel32.GlobalLock.return_value = 456
        with patch.object(clipboard.platform, "system", return_value="Windows"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=user32, kernel32=kernel32), create=True), \
             patch.object(ctypes, "wstring_at", return_value="Meeting at 3"):
            result = clipboard.read_clipboard()
        self.assertIn("Meeting at 3", result)
        user32.EmptyClipboard.assert_not_called()
        user32.CloseClipboard.assert_called_once()

    def test_windows_clipboard_describes_copied_image(self):
        user32 = Mock()
        user32.OpenClipboard.return_value = 1
        user32.IsClipboardFormatAvailable.return_value = 0
        user32.CountClipboardFormats.return_value = 1
        with patch.object(clipboard.platform, "system", return_value="Windows"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=user32, kernel32=Mock()), create=True), \
             patch("PIL.ImageGrab.grabclipboard", return_value=Image.new("RGB", (640, 480))):
            result = clipboard.read_clipboard()
        self.assertIn("640 x 480", result)
        user32.CloseClipboard.assert_called_once()

    def test_clipboard_text_is_returned_for_summary_without_copy_shortcut(self):
        with patch.object(clipboard, "read_clipboard", return_value="Clipboard text:\nMeeting at 3"), \
             patch.object(computer_control, "_hotkey") as hotkey:
            result = computer_control.computer_control({"action": "summarize_clipboard"})
        self.assertIn("Meeting at 3", result)
        hotkey.assert_not_called()

    def test_settings_can_read_clipboard_without_pyautogui(self):
        with patch.object(computer_settings, "_PYAUTOGUI", False), \
             patch.object(clipboard, "read_clipboard", return_value="Clipboard text:\nHello"):
            result = computer_settings.computer_settings({"action": "read_clipboard"})
        self.assertIn("Hello", result)

    def test_copy_reports_current_clipboard_and_paste_is_not_claimed_verified(self):
        gui = Mock()
        with patch.object(computer_settings, "_PYAUTOGUI", True), \
             patch.object(computer_settings, "pyautogui", gui, create=True), \
             patch.object(computer_settings, "read_clipboard", return_value="Clipboard text:\nHello"), \
             patch.object(computer_settings.time, "sleep"):
            copied = computer_settings.computer_settings({"action": "copy"})
            pasted = computer_settings.computer_settings({"action": "paste"})
        self.assertIn("Hello", copied)
        self.assertIn("not verified", pasted)

    def test_settings_action_reports_real_clipboard_result(self):
        with patch.object(computer_settings, "_PYAUTOGUI", True), \
             patch.object(clipboard, "clear_clipboard",
                          return_value="Clipboard cleared and verified."):
            result = computer_settings.computer_settings(
                {"action": "clear_clipboard"})
        self.assertEqual(result, "Clipboard cleared and verified.")

    def test_settings_action_reports_clipboard_failure(self):
        with patch.object(computer_settings, "_PYAUTOGUI", True), \
             patch.object(clipboard, "clear_clipboard",
                          side_effect=RuntimeError("Clipboard is busy")):
            result = computer_settings.computer_settings(
                {"action": "clear_clipboard"})
        self.assertIn("Clipboard is busy", result)
        self.assertNotIn("Done: clear_clipboard", result)

    def test_windows_clipboard_is_emptied_and_verified(self):
        user32 = Mock()
        user32.OpenClipboard.return_value = 1
        user32.EmptyClipboard.return_value = 1
        user32.CountClipboardFormats.return_value = 0
        with patch.object(clipboard.platform, "system", return_value="Windows"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=user32),
                          create=True), \
             patch.object(clipboard, "_clear_windows_history", return_value="cleared"), \
             patch.object(clipboard.time, "sleep"):
            result = clipboard.clear_clipboard()
        self.assertIn("Current clipboard cleared and verified", result)
        self.assertIn("Win+V history cleared", result)
        user32.EmptyClipboard.assert_called_once()
        user32.CloseClipboard.assert_called_once()
        user32.CountClipboardFormats.assert_called_once()

    def test_windows_clipboard_does_not_claim_success_if_data_remains(self):
        user32 = Mock()
        user32.OpenClipboard.return_value = 1
        user32.EmptyClipboard.return_value = 1
        user32.CountClipboardFormats.return_value = 2
        with patch.object(clipboard.platform, "system", return_value="Windows"), \
             patch.object(ctypes, "windll", SimpleNamespace(user32=user32),
                          create=True):
            with self.assertRaisesRegex(RuntimeError, "still contains data"):
                clipboard.clear_clipboard()


class ChromeTests(unittest.TestCase):
    def test_browser_tool_routes_chrome_without_playwright_session(self):
        with patch.object(chrome_window, "chrome_is_running", return_value=True), \
             patch.object(chrome_window, "control_chrome",
                          return_value="Used existing Chrome") as control, \
             patch.object(browser_control._registry, "get") as create_session:
            result = browser_control.browser_control(
                {"action": "search", "browser": "chrome", "query": "weather"})
        self.assertEqual(result, "Used existing Chrome")
        control.assert_called_once()
        create_session.assert_not_called()

    def test_navigation_uses_existing_window(self):
        open_native = Mock()
        with patch.object(chrome_window, "focus_existing_chrome", return_value=True), \
             patch.object(chrome_window, "_navigate",
                          return_value="Sent navigation") as navigate:
            result = chrome_window.control_chrome(
                {"action": "go_to", "url": "https://mail.google.com/"},
                open_native,
            )
        self.assertEqual(result, "Sent navigation")
        navigate.assert_called_once_with("https://mail.google.com/", False)
        open_native.assert_not_called()

    def test_running_chrome_is_not_replaced_when_focus_fails(self):
        open_native = Mock()
        with patch.object(chrome_window, "focus_existing_chrome", return_value=False), \
             patch.object(chrome_window, "chrome_is_running", return_value=True):
            result = chrome_window.control_chrome(
                {"action": "go_to", "url": "https://mail.google.com/"},
                open_native,
            )
        self.assertIn("No separate browser was opened", result)
        open_native.assert_not_called()

    def test_full_page_capture_reports_only_a_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            downloads = home / "Downloads"
            downloads.mkdir()
            gui = Mock()

            def capture_on_enter(key):
                if key == "enter":
                    Image.new("RGB", (16, 48), "blue").save(
                        downloads / "Screenshot new.png")

            gui.press.side_effect = capture_on_enter
            with patch.object(chrome_window.Path, "home", return_value=home), \
                 patch.object(chrome_window, "_desktop", return_value=gui), \
                 patch.object(chrome_window.time, "sleep"):
                result = chrome_window._full_page_screenshot(None)

        self.assertIn("Full-page Chrome screenshot saved", result)
        self.assertIn("Screenshots", result)
        self.assertIn("JARVIS", result)
        self.assertEqual(gui.hotkey.call_count, 3)


class WindowAndBluetoothTests(unittest.TestCase):
    def test_native_radio_requests_access_and_verifies_readback(self):
        radio = SimpleNamespace(kind=3, state=0)

        async def get_radios():
            return [radio]

        async def request_access():
            return 1

        async def set_state(target):
            radio.state = target
            return 1

        radio.set_state_async = set_state
        module = SimpleNamespace(
            Radio=SimpleNamespace(get_radios_async=get_radios,
                                  request_access_async=request_access),
            RadioState=SimpleNamespace(ON=1, OFF=0),
        )
        with patch.dict(sys.modules, {"winrt.windows.devices.radios": module}):
            result = __import__("asyncio").run(bluetooth_control._set_radio_native(True))
        self.assertIn("turned on", result)
        self.assertIn("radio state verified", result)

    def test_focus_does_not_claim_success_without_foreground_match(self):
        user32 = Mock()
        user32.GetForegroundWindow.return_value = 99
        with patch.object(window_control.platform, "system", return_value="Windows"), \
             patch.object(window_control, "_windows", return_value=(user32, [(42, "Video Studio", 123)])), \
             patch.object(window_control.time, "sleep"):
            result = window_control.focus_window("Video")
        self.assertIn("did not bring it to the foreground", result)
        self.assertNotIn("Verified foreground", result)

    def test_open_bluetooth_settings_checks_window(self):
        with patch.object(bluetooth_control.platform, "system", return_value="Windows"), \
             patch.object(bluetooth_control.os, "startfile", create=True) as start, \
             patch.object(bluetooth_control, "_settings_open", return_value=True):
            result = bluetooth_control.bluetooth_control({"action": "open_settings"})
        start.assert_called_once_with("ms-settings:bluetooth")
        self.assertIn("verified", result)

    def test_radio_success_uses_native_state_without_opening_settings(self):
        with patch.object(bluetooth_control.platform, "system", return_value="Windows"), \
             patch.object(bluetooth_control, "_set_radio_native", new_callable=AsyncMock,
                          return_value="Bluetooth turned on (radio state verified)"), \
             patch.object(bluetooth_control, "_open_settings") as open_settings:
            result = bluetooth_control.bluetooth_control({"action": "turn_on"})
        self.assertIn("turned on", result)
        open_settings.assert_not_called()

    def test_radio_falls_back_to_quick_settings_without_claiming_settings_open_as_success(self):
        with patch.object(bluetooth_control.platform, "system", return_value="Windows"), \
             patch.object(bluetooth_control, "_set_radio_native", new_callable=AsyncMock,
                          return_value="Windows denied permission"), \
             patch.object(quick_settings, "quick_settings",
                          return_value="Bluetooth turned on (verified)") as quick, \
             patch.object(bluetooth_control, "_open_settings") as open_settings:
            result = bluetooth_control.bluetooth_control({"action": "turn_on"})
        self.assertIn("turned on", result)
        quick.assert_called_once()
        open_settings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
