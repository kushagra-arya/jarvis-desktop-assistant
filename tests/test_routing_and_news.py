import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from capabilities import open_app, quick_settings, store_search, video_player, web_search, youtube_video
from engine import window_control
from engine.action_loader import discover_actions


class RoutingTests(unittest.TestCase):
    def test_any_product_search_uses_store_uri_without_claiming_availability(self):
        with patch.object(store_search.platform, "system", return_value="Windows"), \
             patch.object(store_search.os, "startfile", create=True) as launch, \
             patch.object(store_search, "_store_visible", return_value=True):
            result = store_search.store_search({"query": "Sample Editor for Windows"})
        launch.assert_called_once_with(
            "ms-windows-store://search/?query=Sample%20Editor%20for%20Windows")
        self.assertIn("availability have not been checked", result)

    def test_open_app_store_phrase_routes_product_generically(self):
        with patch.object(open_app, "_SYSTEM", "Windows"), \
             patch.object(store_search, "store_search", return_value="Store search requested") as search:
            result = open_app.open_app({"app_name": "Sample Editor on Microsoft Store"})
        self.assertEqual(result, "Store search requested")
        search.assert_called_once_with({"query": "Sample Editor"})

    def test_youtube_play_navigates_existing_chrome(self):
        with patch.object(youtube_video, "_scrape_first_video_url",
                          return_value="https://www.youtube.com/watch?v=abcdefghijk"), \
             patch.object(youtube_video, "_open_url", return_value="Sent navigation to existing Chrome") as open_url:
            result = youtube_video.youtube_video({"action": "play", "query": "a song"})
        self.assertIn("existing Chrome", result)
        self.assertIn("Playback was not verified", result)
        open_url.assert_called_once()

    def test_video_player_explicit_youtube_request_uses_browser_route(self):
        with patch.object(youtube_video, "youtube_video", return_value="Chrome navigation") as route:
            result = video_player.video_player(
                {"action": "play", "source": "a song on YouTube"}, player=Mock())
        self.assertEqual(result, "Chrome navigation")
        route.assert_called_once_with({"action": "play", "query": "a song"}, player=route.call_args.kwargs["player"])

    def test_generic_online_video_search_defaults_to_chrome(self):
        with patch.object(youtube_video, "youtube_video", return_value="Chrome navigation") as route:
            result = video_player.video_player({"action": "play", "source": "a new trailer"},
                                               player=Mock())
        self.assertEqual(result, "Chrome navigation")
        self.assertEqual(route.call_args.args[0]["query"], "a new trailer")

    def test_named_quick_setting_checks_final_state(self):
        control = Mock()
        control.window_text.return_value = "Airplane mode"
        control.get_toggle_state.side_effect = [0, 0, 1]
        root = Mock()
        root.descendants.return_value = [control]
        with patch.object(quick_settings, "_open_panel", return_value="Quick Settings panel opened and verified."), \
             patch.object(quick_settings, "_panel", return_value=root), \
             patch.object(quick_settings.time, "sleep"):
            result = quick_settings._toggle("flight mode", True)
        self.assertIn("turned on (verified)", result)
        control.toggle.assert_called_once()

    def test_unlisted_visible_switch_can_be_read(self):
        control = Mock()
        control.window_text.return_value = "Custom switch"
        control.get_toggle_state.side_effect = [1, 1]
        root = Mock()
        root.descendants.return_value = [control]
        with patch.object(quick_settings, "_open_panel", return_value="Quick Settings panel opened and verified."), \
             patch.object(quick_settings, "_panel", return_value=root):
            result = quick_settings._toggle("Custom switch", None)
        self.assertIn("Custom switch is on", result)

    def test_airplane_and_energy_saver_open_documented_settings_pages(self):
        with patch.object(quick_settings.os, "startfile", create=True) as launch, \
             patch.object(window_control, "_windows", return_value=(Mock(), [(1, "Settings", 2)])), \
             patch.object(window_control, "_settings_windows", return_value=[(1, "Settings", 2)]):
            airplane = quick_settings._open_settings("flight mode")
            energy = quick_settings._open_settings("energy saver")
        self.assertIn("window verified", airplane)
        self.assertIn("window verified", energy)
        self.assertEqual(launch.call_args_list[0].args[0], "ms-settings:network-airplanemode")
        self.assertEqual(launch.call_args_list[1].args[0], "ms-settings:batterysaver")

    def test_new_tools_are_discovered(self):
        registry = discover_actions(Path(__file__).resolve().parents[1] / "capabilities",
                                    logger=lambda _: None)
        self.assertTrue({"clipboard_control", "quick_settings", "store_search"}
                        <= registry.names())


class NewsTests(unittest.TestCase):
    def test_yesterday_article_is_excluded(self):
        now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        rows = [
            {"title": "Old headline", "url": "https://old.example/story",
             "source": "Old", "date": (now - timedelta(days=1)).isoformat()},
            {"title": "Current headline", "url": "https://current.example/story",
             "source": "Current", "date": now.isoformat()},
        ]
        with patch.object(web_search, "_ddg_news", return_value=rows):
            result = web_search._news("")
        self.assertIn("Current headline", result)
        self.assertNotIn("Old headline", result)

    def test_india_news_has_five_current_sourced_items(self):
        now = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        rows = [{"title": f"India headline {i}", "snippet": "Summary",
                 "url": f"https://publisher{i}.example/story", "source": f"Publisher {i}",
                 "date": now} for i in range(7)]
        with patch.object(web_search, "_ddg_news", return_value=rows) as fetch:
            result = web_search._news("tech")
        self.assertIn("India", fetch.call_args.args[0])
        self.assertEqual(fetch.call_args.kwargs["region"], "in-en")
        self.assertEqual(fetch.call_args.kwargs["timelimit"], "d")
        self.assertEqual(result.count("Source:"), 5)
        self.assertIn("Publisher 0", result)
        self.assertNotIn("India headline 5", result)

    def test_grounded_fallback_keeps_only_five_linked_headlines(self):
        raw = "\n".join(f"{i}. [Headline {i}](https://news{i}.example/story)"
                        for i in range(1, 8))
        result = web_search._format_grounded_news(raw, "2026-09-28")
        self.assertEqual(result.count("Source:"), 5)
        self.assertNotIn("Headline 6", result)


if __name__ == "__main__":
    unittest.main()
