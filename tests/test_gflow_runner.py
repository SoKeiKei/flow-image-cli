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


if __name__ == "__main__":
    unittest.main()
