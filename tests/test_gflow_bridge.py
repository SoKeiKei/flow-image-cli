import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from flow_cli.gflow_bridge import (
    check_gflow_compatibility,
    clear_fixed_project,
    get_fixed_project,
    run_gflow,
    set_fixed_project,
)


class GflowBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_patch = patch.dict(
            os.environ, {"FLOW_CLI_HOME": self.temp_dir.name}, clear=False
        )
        self.home_patch.start()
        self.version_patch = patch(
            "flow_cli.gflow_bridge.get_installed_gflow_version",
            return_value="0.67.0",
        )
        self.version_patch.start()

    def tearDown(self):
        self.version_patch.stop()
        self.home_patch.stop()
        self.temp_dir.cleanup()

    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_current_version_is_accepted(self, _find_spec):
        self.assertEqual(check_gflow_compatibility(), (True, None))

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    @patch(
        "flow_cli.gflow_bridge.get_installed_gflow_version",
        return_value="0.53.1",
    )
    def test_old_version_returns_clear_error_without_running_upstream(
        self, _version, _find_spec, run
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            result = run_gflow("video", ["t2v", "test"])

        self.assertEqual(result, 2)
        self.assertIn("0.53.1", output.getvalue())
        self.assertIn(">=0.67.0,<0.68.0", output.getvalue())
        run.assert_not_called()

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=None)
    def test_missing_dependency_returns_clear_error(self, _find_spec, run):
        output = io.StringIO()
        with redirect_stdout(output):
            result = run_gflow("video", ["t2v", "test"])

        self.assertEqual(result, 2)
        self.assertIn("未安装", output.getvalue())
        run.assert_not_called()

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_forwards_video_arguments(self, _find_spec, run):
        run.return_value.returncode = 7

        result = run_gflow("video", ["t2v", "一只猫", "--model", "omni-flash"])

        self.assertEqual(result, 7)
        command = run.call_args.args[0]
        self.assertEqual(command[1:4], ["-m", "gflow_cli", "video"])
        self.assertEqual(command[4:], ["t2v", "一只猫", "--model", "omni-flash"])
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["PYTHONUTF8"], os.environ.get("PYTHONUTF8", "1"))
        self.assertEqual(
            environment["GFLOW_CLI_OUTPUT_DIR"], str(Path.cwd() / "output")
        )

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_empty_arguments_show_upstream_help(self, _find_spec, run):
        run.return_value.returncode = 0

        result = run_gflow("video", [])

        self.assertEqual(result, 0)
        self.assertEqual(run.call_args.args[0][-2:], ["video", "--help"])

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_models_can_run_without_implicit_help(self, _find_spec, run):
        run.return_value.returncode = 0

        result = run_gflow("models", [], show_help_when_empty=False)

        self.assertEqual(result, 0)
        self.assertEqual(run.call_args.args[0][-3:], ["-m", "gflow_cli", "models"])

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_fixed_project_is_injected_for_generation(self, _find_spec, run):
        run.return_value.returncode = 0
        project_id = "123e4567-e89b-42d3-a456-426614174000"
        set_fixed_project(project_id)

        run_gflow("video", ["t2v", "竹林"])

        self.assertEqual(run.call_args.args[0][-2:], ["--project", project_id])

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_fixed_project_is_injected_for_video_extend(self, _find_spec, run):
        run.return_value.returncode = 0
        project_id = "123e4567-e89b-42d3-a456-426614174000"
        set_fixed_project(project_id)

        run_gflow("video", ["extend", "clip.mp4"])

        self.assertEqual(run.call_args.args[0][-2:], ["--project", project_id])

    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_fixed_project_is_not_injected_for_video_chain(self, _find_spec, run):
        run.return_value.returncode = 0
        set_fixed_project("123e4567-e89b-42d3-a456-426614174000")

        run_gflow("video", ["chain", "manifest.jsonl"])

        command = run.call_args.args[0]
        self.assertNotIn("--project", command)
        self.assertEqual(command[-2:], ["chain", "manifest.jsonl"])

    @patch("flow_cli.migrated_image.run_migrated_t2i", return_value=0)
    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_explicit_project_overrides_fixed_project(
        self, _find_spec, run, run_migrated_t2i
    ):
        run.return_value.returncode = 0
        set_fixed_project("123e4567-e89b-42d3-a456-426614174000")

        run_gflow("image", ["t2i", "竹林", "--project", "custom-project"])

        arguments = run_migrated_t2i.call_args.args[0]
        self.assertEqual(arguments.count("--project"), 1)
        self.assertEqual(arguments[-2:], ["--project", "custom-project"])
        run.assert_not_called()

    @patch("flow_cli.migrated_image.run_migrated_t2i", return_value=0)
    @patch("flow_cli.gflow_bridge.subprocess.run")
    @patch("flow_cli.gflow_bridge.importlib.util.find_spec", return_value=object())
    def test_fixed_project_is_injected_for_migrated_image(
        self, _find_spec, run, run_migrated_t2i
    ):
        project_id = "123e4567-e89b-42d3-a456-426614174000"
        set_fixed_project(project_id)

        result = run_gflow("image", ["t2i", "竹林", "--model", "nano2-lite"])

        self.assertEqual(result, 0)
        self.assertEqual(
            run_migrated_t2i.call_args.args[0][-2:], ["--project", project_id]
        )
        run.assert_not_called()

    def test_fixed_project_can_be_read_and_cleared(self):
        project_id = "123e4567-e89b-42d3-a456-426614174000"
        set_fixed_project(project_id)
        self.assertEqual(get_fixed_project(), project_id)
        self.assertTrue(clear_fixed_project())
        self.assertIsNone(get_fixed_project())


if __name__ == "__main__":
    unittest.main()
