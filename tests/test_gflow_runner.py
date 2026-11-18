import unittest

from flow_cli.gflow_runner import NO_AGENT_REASON, apply_patch, refuse_agent


class NoAgentTests(unittest.TestCase):
    def setUp(self):
        from gflow_cli.api.transports import agent_only_composer as composer

        self.composer = composer
        self.saved = (
            composer.unported_video,
            composer.unported_image,
            composer.refuse_unported,
        )

    def tearDown(self):
        (
            self.composer.unported_video,
            self.composer.unported_image,
            self.composer.refuse_unported,
        ) = self.saved

    def test_agent_composer_is_refused_for_video_and_image(self):
        self.assertTrue(apply_patch())
        self.assertEqual(self.composer.unported_video(object()), NO_AGENT_REASON)
        self.assertEqual(self.composer.unported_image(object()), NO_AGENT_REASON)

    def test_refusal_message_tells_user_to_turn_agent_off(self):
        apply_patch()
        error = self.composer.refuse_unported(NO_AGENT_REASON)
        self.assertIn("智能体", error.detail)
        self.assertIn("关闭", error.detail)

    def test_other_refusals_keep_upstream_message(self):
        apply_patch()
        error = self.composer.refuse_unported("something else")
        self.assertIn("something else", error.detail)

    def test_refuse_agent_ignores_request_shape(self):
        self.assertEqual(refuse_agent(1, key=2), NO_AGENT_REASON)


class TelemetryDisabledTests(unittest.TestCase):
    def test_telemetry_is_neutralised(self):
        import os
        from unittest.mock import patch

        from gflow_cli import telemetry, telemetry_upload

        from flow_cli.gflow_runner import disable_telemetry

        saved = {
            (telemetry, n): getattr(telemetry, n)
            for n in ("record", "record_counter", "record_crash", "maybe_show_notice", "uploads_enabled")
        }
        saved.update({(telemetry_upload, n): getattr(telemetry_upload, n) for n in ("maybe_upload", "send", "_spawn_sender")})
        try:
            with patch.dict(os.environ, {}, clear=False):
                self.assertTrue(disable_telemetry())
                self.assertEqual(os.environ["DO_NOT_TRACK"], "1")
                self.assertEqual(os.environ["GFLOW_CLI_TELEMETRY"], "0")
            self.assertIsNone(telemetry.record("cli", "x", [], "ok", 0.1))
            self.assertFalse(telemetry.uploads_enabled())
            self.assertFalse(telemetry.maybe_show_notice())
            self.assertIsNone(telemetry_upload.send("2026-W45"))
        finally:
            for (module, name), value in saved.items():
                setattr(module, name, value)


if __name__ == "__main__":
    unittest.main()
