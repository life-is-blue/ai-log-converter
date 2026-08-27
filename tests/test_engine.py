import subprocess
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

import ai_engine


class EngineSelectionTests(unittest.TestCase):
    def tearDown(self):
        ai_engine._codex_enabled.cache_clear()

    def test_default_engine_is_http_even_with_codex_installed(self):
        with mock.patch.dict(ai_engine.os.environ, {}, clear=False), \
             mock.patch.object(ai_engine.shutil, "which", return_value="/usr/bin/codex"):
            if "LLM_ENGINE" in ai_engine.os.environ:
                del ai_engine.os.environ["LLM_ENGINE"]
            ai_engine._codex_enabled.cache_clear()
            self.assertFalse(ai_engine._codex_enabled())

    def test_codex_engine_requires_env_and_cli(self):
        for engine_val, which_ret, expected in [
            ("codex", "/usr/bin/codex", True),
            ("codex", None, False),
            ("http", "/usr/bin/codex", False),
        ]:
            with self.subTest(engine=engine_val, which=which_ret):
                with mock.patch.dict(ai_engine.os.environ, {"LLM_ENGINE": engine_val}), \
                     mock.patch.object(ai_engine.shutil, "which", return_value=which_ret):
                    ai_engine._codex_enabled.cache_clear()
                    self.assertEqual(ai_engine._codex_enabled(), expected)

    @mock.patch.object(ai_engine, "_call_llm_auto", return_value="http answer")
    def test_call_engine_skips_codex_by_default(self, llm_auto):
        with mock.patch.object(ai_engine.shutil, "which", return_value="/usr/bin/codex"):
            ai_engine._codex_enabled.cache_clear()
            result = ai_engine.call_engine("content", "system")
        self.assertEqual(result, "http answer")
        llm_auto.assert_called_once_with("content", "system", 4000, True)

    @mock.patch.object(ai_engine, "_call_codex", return_value="codex answer")
    @mock.patch.object(ai_engine, "_call_llm_auto", return_value="http answer")
    def test_call_engine_uses_codex_when_opted_in(self, llm_auto, codex):
        with mock.patch.dict(ai_engine.os.environ, {"LLM_ENGINE": "codex"}), \
             mock.patch.object(ai_engine.shutil, "which", return_value="/usr/bin/codex"):
            ai_engine._codex_enabled.cache_clear()
            result = ai_engine.call_engine("content", "system")
        self.assertEqual(result, "codex answer")
        codex.assert_called_once()
        llm_auto.assert_not_called()


class CodexEngineTests(unittest.TestCase):
    @mock.patch.object(ai_engine.time, "sleep")
    @mock.patch.object(ai_engine.subprocess, "run")
    def test_codex_retries_once_then_succeeds(self, run, sleep):
        run.side_effect = [
            subprocess.CompletedProcess([], 1, "", "temporary failure"),
            subprocess.CompletedProcess([], 0, "final answer\n", ""),
        ]

        with redirect_stderr(StringIO()):
            result = ai_engine._call_codex("content", "system")

        self.assertEqual(result, "final answer")
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(2)

    @mock.patch.object(ai_engine.time, "sleep")
    @mock.patch.object(ai_engine.subprocess, "run")
    def test_codex_failure_logs_actionable_stderr_tail(self, run, _sleep):
        run.return_value = subprocess.CompletedProcess(
            [], 1, "", "startup banner\n" + "x" * 2200 + "ROOT CAUSE"
        )
        stderr = StringIO()

        with redirect_stderr(stderr):
            self.assertEqual(ai_engine._call_codex("content", "system"), "")

        output = stderr.getvalue()
        self.assertIn("ROOT CAUSE", output)
        self.assertNotIn("startup banner", output)
        self.assertEqual(run.call_count, 2)

    @mock.patch.object(ai_engine.time, "sleep")
    @mock.patch.object(ai_engine.subprocess, "run")
    def test_codex_timeout_retries_once(self, run, sleep):
        run.side_effect = [
            subprocess.TimeoutExpired("codex", 300),
            subprocess.CompletedProcess([], 0, "recovered", ""),
        ]

        with redirect_stderr(StringIO()):
            result = ai_engine._call_codex("content", "system")

        self.assertEqual(result, "recovered")
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
