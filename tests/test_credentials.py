import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_config import credentials


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "app_config").mkdir()
        self.settings = root / "app_config" / "api_keys.json"
        self.env_file = root / ".env"
        self.addCleanup(patch.stopall)
        patch.object(credentials, "SETTINGS_FILE", self.settings).start()
        patch.object(credentials, "ENV_FILE", self.env_file).start()
        patch.dict(os.environ, {"GEMINI_API_KEY": ""}).start()

    def test_legacy_key_moves_to_env_without_losing_settings(self):
        self.settings.write_text(json.dumps({"gemini_api_key": "sample-key", "voice_name": "Kore"}))
        self.assertEqual(credentials.get_gemini_key(), "sample-key")
        self.assertIn("GEMINI_API_KEY", self.env_file.read_text())
        self.assertEqual(json.loads(self.settings.read_text()), {"voice_name": "Kore"})

    def test_env_value_overrides_saved_key(self):
        self.env_file.write_text('GEMINI_API_KEY="local-key"\n')
        self.settings.write_text(json.dumps({"gemini_api_key": "old-key"}))
        self.assertEqual(credentials.get_gemini_key(), "local-key")
        self.assertNotIn("gemini_api_key", json.loads(self.settings.read_text()))

    def test_save_replaces_key_and_preserves_other_env_values(self):
        self.env_file.write_text("OTHER_SETTING=kept\nGEMINI_API_KEY=old\n")
        credentials.save_gemini_key("new-key")
        self.assertEqual(credentials.get_gemini_key(), "new-key")
        self.assertIn("OTHER_SETTING=kept", self.env_file.read_text())
        self.assertEqual(self.env_file.read_text().count("GEMINI_API_KEY="), 1)

    def test_failed_migration_keeps_the_working_legacy_key(self):
        self.settings.write_text(json.dumps({"gemini_api_key": "sample-key"}))
        with patch.object(credentials, "_write_env_key", side_effect=OSError("read only")):
            self.assertEqual(credentials.get_gemini_key(), "sample-key")
        self.assertIn("gemini_api_key", json.loads(self.settings.read_text()))


if __name__ == "__main__":
    unittest.main()
