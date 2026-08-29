import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_pipeline  # noqa: E402


class ExecuteStepTests(unittest.TestCase):
    @mock.patch.object(run_pipeline.subprocess, "run")
    def test_deferred_exit_is_recorded_without_raising(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(["classifier"], 75)
        marks = []

        returncode = run_pipeline.execute_step(
            ["classifier"],
            step="classify",
            mark_step=lambda *args, **kwargs: marks.append((args, kwargs)),
            deferred_exit_codes=frozenset({75}),
        )

        self.assertEqual(returncode, 75)
        self.assertEqual([args[1] for args, _ in marks], ["running", "deferred"])

    @mock.patch.object(run_pipeline.subprocess, "run")
    def test_other_failures_still_stop_the_pipeline(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(["classifier"], 1)

        with self.assertRaises(subprocess.CalledProcessError):
            run_pipeline.execute_step(
                ["classifier"],
                step="classify",
                mark_step=lambda *args, **kwargs: None,
                deferred_exit_codes=frozenset({75}),
            )

    @mock.patch.object(run_pipeline, "write_json_atomic")
    @mock.patch.object(run_pipeline, "execute_step")
    def test_pipeline_keeps_current_snapshot_when_ai_is_deferred(
        self, execute_step_mock, write_json_mock
    ):
        def result(command, **kwargs):
            if command[-1] == "scripts/classify_context.py":
                return run_pipeline.AI_DEFERRED_EXIT_CODE
            return 0

        execute_step_mock.side_effect = result
        argv = [
            "run_pipeline.py",
            "--skip-watch",
            "--skip-data-restore",
            "--no-lock",
        ]

        with mock.patch.object(sys, "argv", argv):
            self.assertEqual(run_pipeline.main(), 0)

        commands = [call.args[0] for call in execute_step_mock.call_args_list]
        self.assertNotIn(
            [run_pipeline.PYTHON, "scripts/build_public_data.py"], commands
        )
        final_payload = write_json_mock.call_args.args[1]
        self.assertEqual(final_payload["status"], "deferred")
        self.assertEqual(
            final_payload["returnCode"], run_pipeline.AI_DEFERRED_EXIT_CODE
        )


if __name__ == "__main__":
    unittest.main()
