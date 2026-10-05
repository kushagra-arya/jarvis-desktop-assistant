import asyncio
import importlib.util
import threading
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("PyQt6"), "PyQt6 is not installed")
class StartupBriefingTests(unittest.IsolatedAsyncioTestCase):
    async def test_news_waits_for_greeting_completion_then_reaches_live_session(self):
        import main

        class Session:
            def __init__(self):
                self.requests = []
                self.news_sent = asyncio.Event()

            async def send_client_content(self, *, turns, turn_complete):
                self.requests.append(turns["parts"][0]["text"])
                if len(self.requests) == 2:
                    self.news_sent.set()

        class UI:
            def __init__(self):
                self.contents = []
                self.logs = []

            def show_content(self, label, text):
                self.contents.append((label, text))

            def write_log(self, text):
                self.logs.append(text)

        live = object.__new__(main.JarvisLive)
        live.session = Session()
        live.ui = UI()
        live._turn_complete_count = 0
        live._briefing_turn_event = asyncio.Event()
        live._speaking_lock = threading.Lock()
        live._is_speaking = False
        live.audio_in_queue = asyncio.Queue()

        with (patch.object(main, "load_memory", return_value={}),
              patch.object(main, "pop_last_session", return_value=None),
              patch.object(main, "_fetch_news_sync", return_value="Latest news: India\n1. Sample headline\n   Source: Example — https://example.com/story")):
            await live._send_startup_briefing()
            await asyncio.sleep(0.05)
            self.assertEqual(len(live.session.requests), 1)

            live._turn_complete_count += 1
            live._briefing_turn_event.set()
            await asyncio.wait_for(live.session.news_sent.wait(), timeout=2)

        self.assertIn("Sample headline", live.session.requests[1])
        self.assertIn("(Example)", live.session.requests[1])
        self.assertNotIn("https://example.com/story", live.session.requests[1])
        self.assertEqual(len(live.ui.contents), 1)
