import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import ai_report
from ai_report import cmd_sync_memory


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


class SyncMemoryConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote = root / "remote.git"
        seed = root / "seed"
        self.local_a = root / "machine-a"
        self.local_b = root / "machine-b"

        git(root, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(root, "init", "--initial-branch=main", str(seed))
        self._configure(seed)
        (seed / "shared.md").write_text("base\n")
        git(seed, "add", "shared.md")
        git(seed, "commit", "-m", "initial")
        git(seed, "remote", "add", "origin", str(self.remote))
        git(seed, "push", "-u", "origin", "main")

        git(root, "clone", str(self.remote), str(self.local_a))
        git(root, "clone", str(self.remote), str(self.local_b))
        self._configure(self.local_a)
        self._configure(self.local_b)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _configure(repo):
        git(repo, "config", "user.name", "AI Distillery Test")
        git(repo, "config", "user.email", "test@example.invalid")

    def _sync_a(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            cmd_sync_memory(SimpleNamespace(logs=str(self.local_a)))
        return stderr.getvalue()

    def test_non_conflicting_remote_advance_rebases_and_retries(self):
        (self.local_b / "remote.md").write_text("from machine b\n")
        git(self.local_b, "add", "remote.md")
        git(self.local_b, "commit", "-m", "machine b")
        git(self.local_b, "push")

        (self.local_a / "local.md").write_text("from machine a\n")
        output = self._sync_a()

        self.assertIn("remote advanced, rebasing", output)
        self.assertTrue((self.local_a / "remote.md").is_file())
        self.assertTrue((self.local_a / "local.md").is_file())
        self.assertEqual(git(self.local_a, "status", "--porcelain").stdout, "")
        self.assertEqual(
            git(self.local_a, "rev-parse", "HEAD").stdout,
            git(self.remote, "rev-parse", "main").stdout,
        )

    def test_conflict_aborts_rebase_and_preserves_local_commit(self):
        (self.local_b / "shared.md").write_text("machine b\n")
        git(self.local_b, "commit", "-am", "machine b conflict")
        git(self.local_b, "push")

        (self.local_a / "shared.md").write_text("machine a\n")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            cmd_sync_memory(SimpleNamespace(logs=str(self.local_a)))

        self.assertFalse((self.local_a / ".git" / "rebase-merge").exists())
        self.assertEqual((self.local_a / "shared.md").read_text(), "machine a\n")
        self.assertEqual(git(self.local_a, "status", "--porcelain").stdout, "")

    def test_clean_retry_pushes_commit_left_by_previous_failure(self):
        (self.local_a / "pending.md").write_text("already committed\n")
        git(self.local_a, "add", "pending.md")
        git(self.local_a, "commit", "-m", "pending local commit")

        output = self._sync_a()

        self.assertIn("no new changes", output)
        self.assertEqual(
            git(self.local_a, "rev-parse", "HEAD").stdout,
            git(self.remote, "rev-parse", "main").stdout,
        )


class SyncMemoryTimeoutTests(SyncMemoryConcurrencyTests):
    """Regression (2026-09-03): a push TimeoutExpired escaped the retry loop —
    which only caught CalledProcessError — and killed the whole leader chain,
    even though the ref had already been updated server-side."""

    def _patch_push(self, mode, max_timeouts=1):
        """Intercept `git push` only; every other git call runs for real.

        mode="false_negative": push runs to completion, THEN raises
        TimeoutExpired — server updated the ref, client never heard back.
        mode="real_timeout": push raises without running (network dead).
        """
        real_run = subprocess.run
        state = {"timeouts": 0}

        def fake_run(*args, **kwargs):
            if args and args[0][:2] == ["git", "push"]:
                if state["timeouts"] < max_timeouts:
                    state["timeouts"] += 1
                    if mode == "false_negative":
                        real_run(*args, **kwargs)  # server-side: ref updated
                    raise subprocess.TimeoutExpired(cmd=list(args[0]), timeout=120)
            return real_run(*args, **kwargs)

        return mock.patch.object(ai_report.subprocess, "run", side_effect=fake_run)

    def test_false_negative_timeout_confirms_on_remote(self):
        (self.local_a / "f.md").write_text("x\n")
        stderr = StringIO()
        with self._patch_push("false_negative"), redirect_stderr(stderr):
            cmd_sync_memory(SimpleNamespace(logs=str(self.local_a)))

        self.assertIn("push confirmed on remote after timeout", stderr.getvalue())
        self.assertEqual(
            git(self.local_a, "rev-parse", "HEAD").stdout,
            git(self.remote, "rev-parse", "main").stdout,
        )

    def test_real_timeout_retries_and_succeeds(self):
        (self.local_a / "f.md").write_text("x\n")
        stderr = StringIO()
        with self._patch_push("real_timeout", max_timeouts=1) as run, \
             mock.patch.object(ai_report.time, "sleep"), redirect_stderr(stderr):
            cmd_sync_memory(SimpleNamespace(logs=str(self.local_a)))

        self.assertIn("retry 1/2", stderr.getvalue())
        self.assertEqual(
            git(self.local_a, "rev-parse", "HEAD").stdout,
            git(self.remote, "rev-parse", "main").stdout,
        )

    def test_persistent_timeout_exits_nonzero(self):
        (self.local_a / "f.md").write_text("x\n")
        stderr = StringIO()
        with self._patch_push("real_timeout", max_timeouts=99), \
             mock.patch.object(ai_report.time, "sleep"), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                cmd_sync_memory(SimpleNamespace(logs=str(self.local_a)))

        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("git operation timed out", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
