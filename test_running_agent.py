"""An explicit AGENT_HOST names the running agent: it wins over the opposite host's inherited markers.

  python3 test_running_agent.py
  python3 -m unittest test_running_agent.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mangsang  # noqa: E402

PLAN = "# plan\n\n## Q1 add\n\n`add` appends and prints `#<id>`.\n\n### detail\n\nmore\n\n## Q2 list\n\nlists.\n"
CODE = "X = 1\n\n\ndef add(store, text):\n    return 1\n\n\ndef list_(store):\n    return []\n"
MODEL = "claude-opus-5-5"
SESSION = "sess-1"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False))


class Env(unittest.TestCase):
    """Every test runs in a temp dir with a synthetic Claude home; the env is built from nothing, never inherited."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mangsang-agent-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.claude = os.path.join(self.dir, "claude-home")   # CLAUDE_CONFIG_DIR: the only place a model can come from
        self.home = os.path.join(self.dir, "home")            # HOME: never the real ~/.claude
        os.makedirs(self.home)
        write(os.path.join(self.claude, "projects", "-some-project", SESSION + ".jsonl"), "".join(json.dumps(x) + "\n" for x in (
            {"type": "assistant", "message": {"model": MODEL, "content": []}},
            {"type": "user", "message": {"content": "ok"}})))

    def env(self, **markers):
        e = {"HOME": self.home, "CLAUDE_CONFIG_DIR": self.claude, "PATH": os.environ.get("PATH", "")}
        e.update(markers)
        return e

    def agent(self, **markers):
        with mock.patch.dict(os.environ, self.env(**markers), clear=True):
            return mangsang.running_agent()

    def main(self, markers, *argv):
        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env(**markers), clear=True):
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                    try:
                        code = mangsang.main(list(argv))
                    except SystemExit as err:
                        code = err.code if isinstance(err.code, int) else 1
                        out.write(str(err) + "\n")
            finally:
                if hasattr(mangsang, "APPROVED_IN"):
                    mangsang.APPROVED_IN = None
        return code, out.getvalue()

    def assertNamesNoHost(self, who):
        self.assertIsInstance(who, str)
        self.assertNotIn("Claude", who)
        self.assertNotIn("Codex", who)


class TestReproduction(Env):
    def test_R2_mixed_reproduction_1_codex_child_with_inherited_claude_markers_is_codex(self):
        who = self.agent(AGENT_HOST="codex", AGENT_WORKER="1", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION)
        self.assertEqual(who, "Codex")
        self.assertNotIn(MODEL, who or "")

    def test_R2_explicit_codex_ignores_claude_session_id_without_claudecode(self):
        self.assertEqual(self.agent(AGENT_HOST="codex", CLAUDE_CODE_SESSION_ID=SESSION), "Codex")

    def test_R2_explicit_codex_with_empty_thread_is_generic_codex(self):
        self.assertEqual(self.agent(AGENT_HOST="codex", CODEX_THREAD_ID="", CLAUDECODE="1"), "Codex")

    def test_R3_mixed_reproduction_2_claude_child_with_stale_codex_thread_and_record(self):
        who = self.agent(AGENT_HOST="claude-code", CODEX_THREAD_ID="stale-parent", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION)
        self.assertEqual(who, "Claude (%s)" % MODEL)
        self.assertNotIn("stale-parent", who or "")

    def test_R3_mixed_reproduction_2_claude_child_with_stale_codex_thread_no_record(self):
        who = self.agent(AGENT_HOST="claude-code", CODEX_THREAD_ID="stale-parent", CLAUDECODE="1")
        self.assertEqual(who, "Claude Code")
        who = self.agent(AGENT_HOST="claude-code", CODEX_THREAD_ID="stale-parent", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID="sess-unknown")
        self.assertEqual(who, "Claude Code")
        self.assertNotIn("stale-parent", who or "")


class TestExplicitHost(Env):
    def test_R2_explicit_codex_with_its_own_thread(self):
        self.assertEqual(self.agent(AGENT_HOST="codex", CODEX_THREAD_ID="T"), "Codex (thread T)")

    def test_R2_explicit_codex_with_its_own_thread_and_claudecode_present(self):
        self.assertEqual(self.agent(AGENT_HOST="codex", CODEX_THREAD_ID="T", CLAUDECODE="1",
                                    CLAUDE_CODE_SESSION_ID=SESSION), "Codex (thread T)")

    def test_R3_explicit_claude_without_claudecode_reads_the_record(self):
        self.assertEqual(self.agent(AGENT_HOST="claude-code", CLAUDE_CODE_SESSION_ID=SESSION), "Claude (%s)" % MODEL)

    def test_R3_explicit_claude_without_claudecode_or_record_is_claude_code(self):
        self.assertEqual(self.agent(AGENT_HOST="claude-code"), "Claude Code")

    def test_R3_explicit_claude_beats_agent_worker(self):
        self.assertEqual(self.agent(AGENT_HOST="claude-code", AGENT_WORKER="1"), "Claude Code")

    def test_R1_whitespace_around_codex_is_stripped(self):
        self.assertEqual(self.agent(AGENT_HOST="  codex  ", CLAUDECODE="1", AGENT_WORKER="1"), "Codex")

    def test_R1_whitespace_around_claude_code_is_stripped(self):
        self.assertEqual(self.agent(AGENT_HOST="\tclaude-code\n", CODEX_THREAD_ID="stale-parent"), "Claude Code")

    def test_R1_read_at_call_time_not_import_time(self):
        self.assertEqual(self.agent(AGENT_HOST="codex", CLAUDECODE="1"), "Codex")
        self.assertEqual(self.agent(AGENT_HOST="claude-code", CODEX_THREAD_ID="x"), "Claude Code")


class TestLegacy(Env):
    def test_R4_legacy_codex_thread_only(self):
        self.assertEqual(self.agent(CODEX_THREAD_ID="X"), "Codex (thread X)")
        self.assertEqual(self.agent(AGENT_HOST="", CODEX_THREAD_ID="X"), "Codex (thread X)")

    def test_R4_legacy_claudecode_with_record(self):
        self.assertEqual(self.agent(CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION), "Claude (%s)" % MODEL)
        self.assertEqual(self.agent(AGENT_HOST="", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION), "Claude (%s)" % MODEL)

    def test_R4_legacy_claudecode_without_record(self):
        self.assertEqual(self.agent(CLAUDECODE="1"), "Claude Code")
        self.assertEqual(self.agent(AGENT_HOST="", CLAUDECODE="1"), "Claude Code")

    def test_R4_legacy_order_codex_thread_before_claudecode(self):
        self.assertEqual(self.agent(CODEX_THREAD_ID="X", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION), "Codex (thread X)")
        self.assertEqual(self.agent(AGENT_HOST="", CODEX_THREAD_ID="X", CLAUDECODE="1"), "Codex (thread X)")

    def test_R4_legacy_whitespace_only_host_is_empty(self):
        self.assertEqual(self.agent(AGENT_HOST="   ", CODEX_THREAD_ID="X", CLAUDECODE="1"), "Codex (thread X)")

    def test_R4_worker_only(self):
        self.assertEqual(self.agent(AGENT_WORKER="1"), "an agent worker")
        self.assertEqual(self.agent(AGENT_HOST="", AGENT_WORKER="1"), "an agent worker")

    def test_R4_human_terminal_is_none(self):
        self.assertIsNone(self.agent())
        self.assertIsNone(self.agent(AGENT_HOST=""))


class TestUnknownHost(Env):
    HOSTS = ("gemini", "claude", "Codex", "CODEX", "Claude-Code")

    def test_R5_unknown_host_with_both_markers_is_an_agent(self):
        for host in self.HOSTS:
            with self.subTest(host=host):
                who = self.agent(AGENT_HOST=host, CLAUDECODE="1", CODEX_THREAD_ID="x", CLAUDE_CODE_SESSION_ID=SESSION)
                self.assertEqual(who, "an agent")
                self.assertNamesNoHost(who)
                self.assertNotIn(MODEL, who)

    def test_R5_unknown_host_with_worker_is_an_agent_worker(self):
        for host in self.HOSTS:
            with self.subTest(host=host):
                who = self.agent(AGENT_HOST=host, CLAUDECODE="1", CODEX_THREAD_ID="x", AGENT_WORKER="1",
                                 CLAUDE_CODE_SESSION_ID=SESSION)
                self.assertEqual(who, "an agent worker")
                self.assertNamesNoHost(who)

    def test_R5_unknown_host_alone_is_never_none(self):
        self.assertEqual(self.agent(AGENT_HOST="gemini"), "an agent")

    def test_R5_unknown_host_does_not_consult_session_model(self):
        with mock.patch.object(mangsang, "session_model", side_effect=AssertionError("session_model consulted")):
            self.assertEqual(self.agent(AGENT_HOST="gemini", CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=SESSION), "an agent")

    def test_R2_explicit_codex_does_not_consult_session_model(self):
        with mock.patch.object(mangsang, "session_model", side_effect=AssertionError("session_model consulted")):
            self.assertEqual(self.agent(AGENT_HOST="codex", CLAUDECODE="1", AGENT_WORKER="1",
                                        CLAUDE_CODE_SESSION_ID=SESSION), "Codex")


class TestAgentEnv(Env):
    def test_R6_agent_env_contains_agent_host(self):
        self.assertIn("AGENT_HOST", mangsang.AGENT_ENV)

    def test_R6_agent_env_keeps_the_legacy_keys(self):
        for k in ("CLAUDECODE", "CODEX_THREAD_ID", "AGENT_WORKER", "CLAUDE_CODE_SESSION_ID"):
            self.assertIn(k, mangsang.AGENT_ENV)

    def project(self):
        pj = os.path.join(self.dir, "proj")
        write(os.path.join(pj, "plan", "PLAN.md"), PLAN)
        write(os.path.join(pj, "memo.py"), CODE)
        write(os.path.join(pj, "mangsang", "people.json"), {"people": ["lee"]})
        return pj

    def test_R6_explicit_host_alone_is_an_agent_for_signing(self):
        pj = self.project()
        code, out = self.main({"AGENT_HOST": "codex"}, "concept", "add", "alpha", "--means", "a thing", "--by", "lee", "--target", pj)
        self.assertNotEqual(code, 0, out)
        self.assertIn("--approved-in", out)
        self.assertFalse(os.path.exists(os.path.join(pj, "mangsang", "concepts", "alpha.json")))

    def test_R6_unknown_explicit_host_alone_is_an_agent_for_signing(self):
        pj = self.project()
        code, out = self.main({"AGENT_HOST": "gemini"}, "concept", "add", "alpha", "--means", "a thing", "--by", "lee", "--target", pj)
        self.assertNotEqual(code, 0, out)
        self.assertIn("--approved-in", out)

    def test_R6_no_markers_is_a_person_for_signing(self):
        pj = self.project()
        code, out = self.main({}, "concept", "add", "alpha", "--means", "a thing", "--by", "lee", "--target", pj)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(pj, "mangsang", "concepts", "alpha.json")))


class TestProvenance(Env):
    def setUp(self):
        super().setUp()
        self.pj = os.path.join(self.dir, "proj")
        write(os.path.join(self.pj, "plan", "PLAN.md"), PLAN)
        write(os.path.join(self.pj, "memo.py"), CODE)
        self.assertEqual(self.main({}, "register", "plan/PLAN.md", "memo.py", "--target", self.pj)[0], 0)
        write(os.path.join(self.pj, "proposals.json"), {"relations": [
            {"src": "plan/PLAN.md#Q1 add", "predicate": "documents", "dst": "memo.py:add", "evidence": "appends and prints"},
            {"src": "plan/PLAN.md#Q2 list", "predicate": "documents", "dst": "memo.py:list_", "evidence": "lists."}]})
        code, out = self.main({}, "confirm", os.path.join(self.pj, "proposals.json"), "--by", "tester", "--target", self.pj)
        self.assertEqual(code, 0, out)
        rels = {r["dst"]: r for r in mangsang.decl(self.pj)["relations"]}
        self.assertEqual(rels["memo.py:add"]["confirmed"], {"by": "tester"})
        self.rid = rels["memo.py:add"]["id"]
        self.other = os.path.join(self.pj, "mangsang", "relations", rels["memo.py:list_"]["id"] + ".json")
        with open(self.other, "rb") as fh:
            self.other_bytes = fh.read()
        write(os.path.join(self.pj, "memo.py"), CODE.replace("return 1", "return 2"))   # only `add` moves: one stale relation

    def reconfirmed(self, markers):
        code, out = self.main(markers, "reconfirm", self.rid, "--target", self.pj)
        self.assertEqual(code, 0, out)
        r = next(x for x in mangsang.decl(self.pj)["relations"] if x["id"] == self.rid)
        with open(self.other, "rb") as fh:
            self.assertEqual(fh.read(), self.other_bytes, "an old signature is never relabeled")
        return r["confirmed"]

    def test_R7_reconfirm_under_explicit_codex_thread_signs_that_thread(self):
        self.assertEqual(self.reconfirmed({"AGENT_HOST": "codex", "CODEX_THREAD_ID": "T"}), {"agent": "Codex (thread T)"})

    def test_R7_reconfirm_under_mixed_reproduction_1_signs_generic_codex(self):
        self.assertEqual(self.reconfirmed({"AGENT_HOST": "codex", "AGENT_WORKER": "1", "CLAUDECODE": "1",
                                           "CLAUDE_CODE_SESSION_ID": SESSION}), {"agent": "Codex"})

    def test_R7_reconfirm_under_explicit_claude_with_stale_thread_signs_claude(self):
        self.assertEqual(self.reconfirmed({"AGENT_HOST": "claude-code", "CODEX_THREAD_ID": "stale-parent",
                                           "CLAUDE_CODE_SESSION_ID": SESSION}), {"agent": "Claude (%s)" % MODEL})


if __name__ == "__main__":
    unittest.main()
