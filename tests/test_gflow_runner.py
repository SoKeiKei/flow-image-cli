import unittest

from flow_cli.gflow_runner import apply_patch, make_gate_quotes_more, make_unported_video


class GateQuotesMoreTests(unittest.TestCase):
    def setUp(self):
        from gflow_cli.api.transports import agent_only_composer

        self.original = agent_only_composer.gate_quotes_more
        self.gate = make_gate_quotes_more(self.original)

    def test_chinese_credits_first_is_not_mistaken_for_count(self):
        title = "要消耗 7 个点数，开始生成这 1 个视频吗？"
        self.assertTrue(self.original(title, 1))  # 上游误判
        self.assertFalse(self.gate(title, 1))

    def test_chinese_gate_still_rejects_larger_count(self):
        self.assertTrue(self.gate("要消耗 28 个点数，开始生成这 4 个视频吗？", 1))
        self.assertFalse(self.gate("要消耗 28 个点数，开始生成这 4 个视频吗？", 4))

    def test_chinese_title_half_rendered_is_unreadable(self):
        self.assertIsNone(self.gate("要消耗 7 个点数，开始生成这", 1))

    def test_english_titles_use_original_logic(self):
        title = "Use 10 credits to kick off these 3 videos?"
        self.assertEqual(self.gate(title, 1), self.original(title, 1))

    def test_apply_patch_replaces_function(self):
        from gflow_cli.api.transports import agent_only_composer

        try:
            self.assertTrue(apply_patch())
            self.assertFalse(
                agent_only_composer.gate_quotes_more("要消耗 7 个点数，开始生成这 1 个视频吗？", 1)
            )
        finally:
            agent_only_composer.gate_quotes_more = self.original

    def test_omni_1_2_text_to_video_is_allowed_other_limits_remain(self):
        from types import SimpleNamespace

        from gflow_cli.api.transports import agent_only_composer as composer

        original = composer.unported_video
        unported = make_unported_video(original)
        base = dict(
            mode=composer.Mode.T2V,
            reference_entities=None,
            reference_entity_names=None,
            count=1,
            aspect=composer.Aspect.LANDSCAPE,
            resolution=None,
        )
        omni = SimpleNamespace(model=composer.VideoModel.OMNI_1_2_FLASH, **base)
        self.assertIsNone(unported(omni))
        self.assertIs(omni.model, composer.VideoModel.OMNI_1_2_FLASH)
        many = SimpleNamespace(
            model=composer.VideoModel.OMNI_1_2_FLASH, **{**base, "count": 2}
        )
        self.assertEqual(unported(many), "more than one video per request")


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
