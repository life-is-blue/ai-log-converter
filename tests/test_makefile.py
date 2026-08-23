import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgyHarvestTests(unittest.TestCase):
    @staticmethod
    def _transcript(home: Path, root: str, session: str) -> Path:
        path = home / ".gemini" / root / "brain" / session / ".system_generated" / "logs" / "transcript.jsonl"
        path.parent.mkdir(parents=True)
        return path

    @staticmethod
    def _agy_line(content: str, cwd: str = None) -> str:
        entry = {
            "type": "PLANNER_RESPONSE",
            "content": content,
            "created_at": "2026-08-22T07:20:04Z",
            "source": "MODEL",
            "status": "DONE",
            "step_index": 1,
        }
        if cwd is not None:
            entry["tool_calls"] = [{
                "name": "run_command",
                "args": {"Cwd": f'"{cwd}"'},
            }]
        return json.dumps(entry) + "\n"

    def test_harvests_both_roots_idempotently_and_prefers_current_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            logs = tmp_path / "logs"
            # Absolute run_command Cwd partitions the session into its project dir.
            current = self._transcript(home, "antigravity-cli", "shared-session")
            duplicate = self._transcript(home, "antigravity", "shared-session")
            legacy = self._transcript(home, "antigravity", "legacy-session")
            plain = self._transcript(home, "antigravity-cli", "plain-session")
            current.write_text(self._agy_line("current source", cwd="/tmp/proj/git-library"))
            duplicate.write_text(self._agy_line("legacy duplicate"))
            legacy.write_text(self._agy_line("legacy source"))
            plain.write_text(self._agy_line("no cwd hint"))
            for source in (current, duplicate, legacy, plain):
                os.utime(source, (1, 1))

            env = os.environ.copy()
            env["HOME"] = str(home)
            command = ["make", "harvest", f"LOGS={logs}"]
            subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)

            shared_output = logs / "agy" / "git-library" / "shared-session.jsonl"
            legacy_output = logs / "agy" / "default" / "legacy-session.jsonl"
            plain_output = logs / "agy" / "default" / "plain-session.jsonl"
            self.assertIn("current source", shared_output.read_text())
            self.assertNotIn("legacy duplicate", shared_output.read_text())
            self.assertIn("legacy source", legacy_output.read_text())
            self.assertIn("no cwd hint", plain_output.read_text())
            self.assertTrue(shared_output.with_suffix(".md").exists())

            first_mtime = shared_output.stat().st_mtime_ns
            subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(shared_output.stat().st_mtime_ns, first_mtime)

            current.write_text(self._agy_line("updated current source", cwd="/tmp/proj/git-library"))
            newer = max(time.time_ns(), first_mtime + 2_000_000_000)
            os.utime(current, ns=(newer, newer))
            subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
            self.assertIn("updated current source", shared_output.read_text())


class CodexHarvestTests(unittest.TestCase):
    @staticmethod
    def _session(home: Path, session: str, cwd: str) -> Path:
        path = home / ".codex" / "sessions" / "2026" / "08" / "22" / f"{session}.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "timestamp": "2026-08-22T10:00:00.000Z",
            "type": "session_meta",
            "payload": {"id": session, "cwd": cwd},
        }) + "\n")
        return path

    def test_harvest_partitions_by_session_meta_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            logs = tmp_path / "logs"
            src = self._session(home, "rollout-2026-08-22T10-00-00-abc",
                                "/data/home/x/project/office-mpp")
            os.utime(src, (1, 1))

            env = os.environ.copy()
            env["HOME"] = str(home)
            command = ["make", "harvest", f"LOGS={logs}"]
            subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)

            out = logs / "codex" / "office-mpp" / "rollout-2026-08-22T10-00-00-abc.jsonl"
            self.assertTrue(out.exists())
            self.assertTrue(out.with_suffix(".md").exists())

            first_mtime = out.stat().st_mtime_ns
            subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(out.stat().st_mtime_ns, first_mtime)


class MigrateFlatSessionsTests(unittest.TestCase):
    """One-time migration: git mv flat default/ sessions into project dirs."""

    def _init_repo(self, logs: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=str(logs), check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(logs), check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(logs), check=True)

    def test_migrates_and_drops_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            logs = tmp_path / "logs"
            logs.mkdir()
            self._init_repo(logs)

            # A local codex source for session "s1" (cwd → proj) and none for "s2".
            src = home / ".codex" / "sessions" / "2026" / "08" / "22" / "s1.jsonl"
            src.parent.mkdir(parents=True)
            src.write_text(json.dumps({
                "timestamp": "2026-08-22T10:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "s1", "cwd": "/data/home/x/project/proj"},
            }) + "\n")

            def add(rel: str, content: str) -> None:
                target = logs / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            # s1: flat default copy (pre-migration state) → should be git mv'd.
            add("codex/default/s1.jsonl", "s1-data")
            add("codex/default/s1.md", "s1-md")
            # s1 already re-harvested into project dir → duplicate default copy dropped.
            add("codex/proj/s1.md", "s1-md")
            # s2: no local source → stays in default.
            add("codex/default/s2.jsonl", "s2-data")
            subprocess.run(["git", "add", "-A"], cwd=str(logs), check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=str(logs), check=True)

            env = os.environ.copy()
            env["HOME"] = str(home)
            result = subprocess.run(
                ["make", "migrate-flat-sessions", f"LOGS={logs}"],
                cwd=ROOT, env=env, capture_output=True, text=True, check=True,
            )

            self.assertFalse((logs / "codex/default/s1.jsonl").exists())
            self.assertFalse((logs / "codex/default/s1.md").exists())
            self.assertEqual((logs / "codex/proj/s1.jsonl").read_text(), "s1-data")
            self.assertEqual((logs / "codex/proj/s1.md").read_text(), "s1-md")
            self.assertTrue((logs / "codex/default/s2.jsonl").exists())
            self.assertIn("MIGRATED codex/s1 -> proj", result.stderr)
            self.assertIn("DROPPED duplicate codex/s1 -> proj", result.stderr)

            # Idempotent: second run changes nothing.
            status_before = subprocess.run(
                ["git", "status", "--short"], cwd=str(logs),
                capture_output=True, text=True, check=True,
            ).stdout
            subprocess.run(
                ["make", "migrate-flat-sessions", f"LOGS={logs}"],
                cwd=ROOT, env=env, capture_output=True, text=True, check=True,
            )
            status_after = subprocess.run(
                ["git", "status", "--short"], cwd=str(logs),
                capture_output=True, text=True, check=True,
            ).stdout
            self.assertEqual(status_before, status_after)


class InstallCronTests(unittest.TestCase):
    def test_install_cron_captures_path_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cron_state = tmp_path / "cron-state"
            fake_crontab = tmp_path / "crontab-bin"
            fake_codex = tmp_path / "codex"

            fake_crontab.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-l\" ]; then\n"
                "  [ ! -f \"$CRON_STATE\" ] || cat \"$CRON_STATE\"\n"
                "else\n"
                "  cat > \"$CRON_STATE\"\n"
                "  [ \"$CRON_FAIL\" != 1 ]\n"
                "fi\n"
            )
            fake_codex.write_text("#!/bin/sh\nexit 0\n")
            fake_crontab.chmod(0o755)
            fake_codex.chmod(0o755)

            runtime_path = f"{tmp_path}:/usr/bin:/bin"
            env = os.environ.copy()
            env.update({
                "PATH": runtime_path,
                "CRON_STATE": str(cron_state),
            })

            # The Makefile calls `crontab`; expose the fake under that name while
            # retaining a separate state file for assertions.
            (tmp_path / "crontab").symlink_to(fake_crontab)

            for _ in range(2):
                result = subprocess.run(
                    ["make", "install-cron"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )

            installed = cron_state.read_text()
            self.assertEqual(installed.count("# ai-distillery-cron"), 1)
            expected_path = f"{tmp_path}:/usr/local/bin:/usr/bin:/bin"
            self.assertIn(f"export PATH={expected_path};", installed)
            self.assertIn(str(fake_codex), result.stdout)
            self.assertIn("47 8 * * *", installed)
            self.assertIn("make leader", installed)
            # The PATH must be resolved from the live environment, not a
            # hardcoded author-machine path. Scope this to the PATH segment:
            # the cron line always contains `cd '$(CURDIR)'`, which legitimately
            # holds an absolute repo path (and would false-positive on any host
            # whose $HOME lives under the checked prefix).
            path_segment = installed.split("export PATH=", 1)[1].split(";", 1)[0]
            self.assertEqual(path_segment, expected_path)

            subprocess.run(
                ["make", "install-cron", "CRON_ROLE=collector"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            installed = cron_state.read_text()
            self.assertEqual(installed.count("# ai-distillery-cron"), 1)
            self.assertIn("47 7 * * *", installed)
            self.assertIn("make collector", installed)

            invalid = subprocess.run(
                ["make", "install-cron", "CRON_ROLE=both"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("CRON_ROLE must be leader or collector", invalid.stderr)

            env["CRON_FAIL"] = "1"
            failed = subprocess.run(
                ["make", "install-cron"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("ERROR: failed to install cron", failed.stderr)


if __name__ == "__main__":
    unittest.main()
