"""Protected contract for check_model.py, the source guard of the mangsang model in mangsang/.

Every scenario runs on a fresh disposable copy of this checkout (outside it) with the *released* mangsang
engine — never this checkout's plugin/. Run as `python3 test_model_guard.py` or
`python3 -m unittest test_model_guard.py`. Stdlib only.

Helpers never raise: they return None (or a result whose code is None), so a missing guard or engine fails
on an assertion in the test body, not as an error. A missing engine FAILS every test (never a skip).
"""
import ast
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
GUARD = "check_model.py"
EXCLUDED_TOP = (".chongdae/", ".dwitbuk/", "reviews/", ".jokbo/", ".hypothesis/")
TIMEOUT = 900

CONCEPTS = ["evidence-gate", "staleness-against-seen", "same-file-reads", "living-answer", "owed-reread"]
QUESTIONS = ["cq-relation-stored", "cq-stale-or-broken", "cq-edit-reach", "cq-question-answered",
             "cq-retired-projection"]
INVARIANTS = ["inv-registered-scope", "inv-projection", "inv-resolved", "inv-verified-confirm",
              "inv-verified-impact", "inv-verified-parts", "inv-verified-answer-health", "inv-verified-owe-for"]
REQUIRED = "inv-required"   # the required invariant over the three lists above (mangsang 2.2.0 or later)

NO_ENGINE = ("no released mangsang engine found: set MANGSANG_ENGINE to the installed released "
             "mangsang.py (e.g. ~/.claude/plugins/cache/mangsang/mangsang/<version>/mangsang.py)")


# ---------------------------------------------------------------- helpers (never raise)

def inside(path, root):
    try:
        p, r = os.path.realpath(path), os.path.realpath(root)
        return os.path.commonpath([p, r]) == r
    except Exception:
        return False


def pinned_version(root=HERE):
    try:
        with open(os.path.join(root, "hunsu.json"), encoding="utf-8") as f:
            return json.load(f)["plugins"]["mangsang"]["version"]
    except Exception:
        return None


def resolve_engine():
    """MANGSANG_ENGINE, else the hunsu.json pin in the Claude then Codex plugin cache. None if nothing exists."""
    try:
        env = os.environ.get("MANGSANG_ENGINE")
        if env:
            return os.path.abspath(env) if os.path.isfile(env) else None
        version = pinned_version()
        if not version:
            return None
        claude = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        codex = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
        for base in (claude, codex):
            cand = os.path.join(base, "plugins", "cache", "mangsang", "mangsang", version, "mangsang.py")
            if os.path.isfile(cand):
                return cand
        return None
    except Exception:
        return None


def engine_version(engine):
    """The version the engine's own plugin manifest declares, else the pin."""
    try:
        root = os.path.dirname(os.path.realpath(engine))
        for mf in (os.path.join(".claude-plugin", "plugin.json"), "plugin.json"):
            p = os.path.join(root, mf)
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    v = json.load(f).get("version")
                if v:
                    return v
    except Exception:
        pass
    return pinned_version()


def base_env(engine=None, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME") + tuple(drop)}
    if engine:
        env["MANGSANG_ENGINE"] = engine
    return env


class Result:
    def __init__(self, code=None, out=""):
        self.code, self.out = code, out


def run(argv, cwd, env):
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=TIMEOUT)
        return Result(p.returncode, p.stdout)
    except Exception as e:  # never raise
        return Result(None, "could not run %r: %s" % (argv, e))


def listed_files():
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=HERE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    except Exception:
        return None
    keep = []
    for rel in out.decode("utf-8", "surrogateescape").split("\0"):
        if not rel or rel.startswith(EXCLUDED_TOP) or "__pycache__" in rel.split("/"):
            continue
        keep.append(rel)
    return sorted(set(keep))


def make_copy():
    """A fresh git-initialized copy of the checkout in a temp dir outside HERE, or None."""
    files = listed_files()
    if not files:
        return None
    try:
        tmp = tempfile.mkdtemp(prefix="mangsang-guard-")
        if inside(tmp, HERE):
            shutil.rmtree(tmp, ignore_errors=True)
            return None
        dst = os.path.join(tmp, "repo")
        os.makedirs(dst)
        for rel in files:
            src = os.path.join(HERE, rel)
            if not os.path.lexists(src) or os.path.isdir(src):
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target, follow_symlinks=False)
        env = base_env()
        for argv in (["git", "init", "-q"], ["git", "add", "-A"],
                     ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "-m", "copy"]):
            if subprocess.run(argv, cwd=dst, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode != 0:
                shutil.rmtree(tmp, ignore_errors=True)
                return None
        return tmp, dst
    except Exception:
        return None


def snapshot_model(repo):
    """{relative path: sha256} of every file under repo/mangsang/ (empty dict if absent)."""
    snap = {}
    root = os.path.join(repo, "mangsang")
    try:
        for d, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(d, f)
                with open(p, "rb") as fh:
                    snap[os.path.relpath(p, repo)] = hashlib.sha256(fh.read()).hexdigest()
    except Exception:
        return None
    return snap


def relation_files(repo, src=None, dst=None, predicate=None):
    """Paths of live relation records in repo/mangsang/relations matching the given fields."""
    hits = []
    for p in sorted(glob.glob(os.path.join(repo, "mangsang", "relations", "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                r = json.load(f)
        except Exception:
            continue
        if src is not None and r.get("src") != src:
            continue
        if dst is not None and r.get("dst") != dst:
            continue
        if predicate is not None and r.get("predicate") != predicate:
            continue
        hits.append((p, r))
    return hits


def remove(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except Exception:
        return False


def edit_json(path, fn):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d = fn(d)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return True
    except Exception:
        return False


def function_source(path, name):
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        for node in ast.parse(src).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.get_source_segment(src, node)
    except Exception:
        pass
    return None


def replace_once(path, old, new):
    """Replace exactly one occurrence of old; False when old is not there exactly once."""
    try:
        with open(path, encoding="utf-8") as f:
            s = f.read()
        if s.count(old) != 1:
            return False
        with open(path, "w", encoding="utf-8") as f:
            f.write(s.replace(old, new, 1))
        return True
    except Exception:
        return False


def replace_in_function(path, name, old, new):
    """Replace old (once) only inside function `name`; False if the function or the text is not found."""
    body = function_source(path, name)
    if body is None or body.count(old) != 1:
        return False
    return replace_once(path, body, body.replace(old, new, 1))


# ---------------------------------------------------------------- tests

class ModelGuard(unittest.TestCase):

    def setUp(self):
        self.engine = None
        self.repo = None

    # Every step inside a test body; assertions decide, helpers only return.
    def prepare(self):
        engine = resolve_engine()
        self.assertIsNotNone(engine, NO_ENGINE)
        self.assertTrue(os.path.isfile(engine), NO_ENGINE)
        self.assertFalse(inside(engine, HERE),
                         "the engine must be the installed released one, not this checkout's: %s" % engine)
        made = make_copy()
        self.assertIsNotNone(made, "could not make a disposable git copy of %s" % HERE)
        tmp, repo = made
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertFalse(inside(repo, HERE), "the copy must live outside the checkout")
        self.engine, self.repo = engine, repo
        return engine, repo

    def guard_path(self):
        return os.path.join(self.repo, GUARD)

    def assert_guard_present(self):
        self.assertTrue(os.path.isfile(self.guard_path()),
                        "%s is missing from the repository root (copied from %s)" % (GUARD, HERE))

    def guard(self, *args, env=None, cwd=None):
        env = base_env(self.engine) if env is None else env
        return run([sys.executable, self.guard_path(), "--target", self.repo] + list(args),
                   cwd=cwd or self.repo, env=env)

    def engine_cmd(self, *args):
        return run([sys.executable, self.engine] + list(args) + ["--target", self.repo], cwd=self.repo,
                   env=base_env(self.engine))

    def assert_guard_fails_naming(self, *names, before=None):
        """Runs the guard on the mutated copy: exit 1 (a guard failure, not a crash or refusal), each name
        printed, and nothing under mangsang/ written."""
        self.assert_guard_present()
        before = snapshot_model(self.repo) if before is None else before
        r = self.guard()
        self.assertIsNotNone(r.code, r.out)
        self.assertEqual(r.code, 1, "guard should exit 1 on a model that lost something; got %r:\n%s"
                         % (r.code, r.out))
        for n in names:
            self.assertIn(n, r.out, "guard output should name %r:\n%s" % (n, r.out))
        self.assertEqual(snapshot_model(self.repo), before, "the guard wrote under mangsang/ on a failing run")
        return r

    # (0) the copy machinery itself and the engine on a pristine tree
    def test_00_pristine_engine_holds_on_the_copy(self):
        engine, repo = self.prepare()
        for cmd in ("check", "cq", "impact"):
            r = self.engine_cmd(cmd)
            self.assertEqual(r.code, 0, "released engine %s fails on the pristine copy:\n%s" % (cmd, r.out))

    # (1) pristine
    def test_01_pristine_copy_passes_names_engine_and_writes_nothing(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        before = snapshot_model(repo)
        self.assertTrue(before, "the copy has no mangsang/ model")
        r = self.guard()
        self.assertEqual(r.code, 0, "guard should pass on the pristine copy:\n%s" % r.out)
        self.assertTrue(engine in r.out or os.path.realpath(engine) in r.out,
                        "guard output should name the engine path %s:\n%s" % (engine, r.out))
        version = engine_version(engine)
        self.assertTrue(version, "cannot tell the engine's version")
        self.assertIn(version, r.out, "guard output should name the engine version %s:\n%s" % (version, r.out))
        self.assertEqual(snapshot_model(repo), before, "the guard changed bytes under mangsang/")

    def test_01_target_defaults_to_the_guard_directory(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        elsewhere = tempfile.mkdtemp(prefix="mangsang-guard-cwd-")
        self.addCleanup(shutil.rmtree, elsewhere, True)
        before = snapshot_model(repo)
        r = run([sys.executable, self.guard_path()], cwd=elsewhere, env=base_env(engine))
        self.assertEqual(r.code, 0, "without --target the guard should check its own directory:\n%s" % r.out)
        self.assertEqual(snapshot_model(repo), before)
        self.assertEqual(os.listdir(elsewhere), [], "the guard wrote into its working directory")

    def test_01_engine_flag_is_used_without_the_environment(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        r = self.guard("--engine", engine, env=base_env(None, drop=("MANGSANG_ENGINE",)))
        self.assertEqual(r.code, 0, "guard with --engine should pass on the pristine copy:\n%s" % r.out)
        self.assertTrue(engine in r.out or os.path.realpath(engine) in r.out, r.out)

    def test_01_hunsu_pin_is_found_in_the_claude_cache(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        version = pinned_version(repo)
        self.assertTrue(version, "the copy's hunsu.json pins no mangsang version")
        fake = tempfile.mkdtemp(prefix="mangsang-guard-home-")
        self.addCleanup(shutil.rmtree, fake, True)
        plugdir = os.path.join(fake, "claude", "plugins", "cache", "mangsang", "mangsang", version)
        shutil.copytree(os.path.dirname(os.path.realpath(engine)), plugdir, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        env = base_env(None, drop=("MANGSANG_ENGINE",))
        env["CLAUDE_CONFIG_DIR"] = os.path.join(fake, "claude")
        env["CODEX_HOME"] = os.path.join(fake, "codex")
        r = self.guard(env=env)
        self.assertEqual(r.code, 0, "guard should resolve the pinned engine from CLAUDE_CONFIG_DIR:\n%s" % r.out)
        self.assertIn(os.path.join(plugdir, "mangsang.py"), r.out.replace(os.path.realpath(fake), fake),
                      "guard output should name the pinned engine it resolved:\n%s" % r.out)

    # (2) absent model
    def test_02_absent_model_fails(self):
        engine, repo = self.prepare()
        self.assertTrue(remove(os.path.join(repo, "mangsang")))
        self.assert_guard_present()
        r = self.guard()
        self.assertEqual(r.code, 1, "guard should exit 1 when mangsang/ is absent:\n%s" % r.out)
        self.assertIn("mangsang", r.out)
        self.assertFalse(os.path.exists(os.path.join(repo, "mangsang")), "the guard recreated mangsang/")

    def test_02_absent_registry_fails(self):
        engine, repo = self.prepare()
        self.assertTrue(remove(os.path.join(repo, "mangsang", "registry.json")))
        before = snapshot_model(repo)
        self.assert_guard_fails_naming("registry", before=before)
        self.assertFalse(os.path.exists(os.path.join(repo, "mangsang", "registry.json")))

    # (3) empty model
    def test_03_empty_model_fails(self):
        engine, repo = self.prepare()
        n = 0
        for sub in ("concepts", "cq", "relations"):
            for p in glob.glob(os.path.join(repo, "mangsang", sub, "*")):
                self.assertTrue(remove(p))
                n += 1
        self.assertGreater(n, 0)
        r = self.assert_guard_fails_naming()
        self.assertTrue(any(c in r.out for c in CONCEPTS), "an empty model should be reported by name:\n%s" % r.out)

    # (4) missing concept
    def test_04_missing_concept_fails_naming_it(self):
        engine, repo = self.prepare()
        self.assertTrue(remove(os.path.join(repo, "mangsang", "concepts", "same-file-reads.json")))
        self.assert_guard_fails_naming("same-file-reads")

    def test_04_concept_with_empty_means_fails_naming_it(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "mangsang", "concepts", "living-answer.json")
        self.assertTrue(edit_json(p, lambda d: dict(d, means="   ")))
        self.assert_guard_fails_naming("living-answer")

    # (5) missing question
    def test_05_missing_question_fails_naming_it(self):
        engine, repo = self.prepare()
        self.assertTrue(remove(os.path.join(repo, "mangsang", "cq", "cq-edit-reach.json")))
        self.assert_guard_fails_naming("cq-edit-reach")

    def test_05_retired_question_fails_naming_it(self):
        engine, repo = self.prepare()
        r = self.engine_cmd("cq", "retire", "cq-edit-reach", "--why", "disposable test copy")
        if r.code != 0:  # the released engine refused (e.g. wants a signature): retire the record by hand
            p = os.path.join(repo, "mangsang", "cq", "cq-edit-reach.json")
            self.assertTrue(edit_json(p, lambda d: dict(d, retired={"why": "disposable test copy"})), r.out)
        self.assert_guard_fails_naming("cq-edit-reach")

    def test_05_question_answered_by_another_concept_fails_naming_it(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "mangsang", "cq", "cq-edit-reach.json")

        def swap(d):
            d["verify"]["concepts"] = ["evidence-gate"]
            return d
        self.assertTrue(edit_json(p, swap))
        self.assert_guard_fails_naming("cq-edit-reach")

    # (6) missing invariant
    def test_06_missing_invariant_fails_naming_it(self):
        engine, repo = self.prepare()
        self.assertTrue(remove(os.path.join(repo, "mangsang", "cq", "inv-projection.json")))
        self.assert_guard_fails_naming("inv-projection")

    def test_06_retired_invariant_fails_naming_it(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "mangsang", "cq", "inv-verified-parts.json")
        self.assertTrue(edit_json(p, lambda d: dict(d, retired={"why": "disposable test copy"})))
        self.assert_guard_fails_naming("inv-verified-parts")

    def test_06_unregistered_scope_file_fails_naming_it(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "mangsang", "registry.json")
        self.assertTrue(edit_json(p, lambda d: [e for e in d if e.get("path") != "MODEL.md"]))
        self.assert_guard_fails_naming("MODEL.md")

    # (7) missing projection
    SFR_TEST = "test_mangsang.py:test_a_python_anchor_covers_its_attachments_and_what_it_reads_in_its_file"

    def test_07_missing_projection_fails_naming_the_concept(self):
        engine, repo = self.prepare()
        hits = relation_files(repo, src=self.SFR_TEST, predicate="realizes")
        self.assertEqual(len(hits), 1, "expected one realizes relation from %s" % self.SFR_TEST)
        self.assertEqual(hits[0][1].get("dst"), "concept:same-file-reads")
        self.assertTrue(remove(hits[0][0]))
        self.assert_guard_fails_naming("same-file-reads")

    def test_07_retired_projection_is_not_live(self):
        engine, repo = self.prepare()
        hits = relation_files(repo, src=self.SFR_TEST, predicate="realizes")
        self.assertEqual(len(hits), 1)
        rid = hits[0][1]["id"]
        r = self.engine_cmd("retire", rid, "--why", "disposable test copy")
        self.assertEqual(r.code, 0, "released engine could not retire %s:\n%s" % (rid, r.out))
        self.assert_guard_fails_naming("same-file-reads")

    # (8) missing verifies
    def test_08_missing_verifies_fails_naming_the_symbol(self):
        engine, repo = self.prepare()
        hits = relation_files(repo, dst="plugin/mangsang.py:owe_for", predicate="verifies")
        self.assertEqual(len(hits), 1, "expected one verifies relation onto plugin/mangsang.py:owe_for")
        self.assertTrue(hits[0][1].get("src", "").startswith("test_mangsang.py:"))
        self.assertTrue(remove(hits[0][0]))
        self.assert_guard_fails_naming("owe_for")

    # (9) code mutation, engine itself
    def mutate_quoted(self):
        p = os.path.join(self.repo, "plugin", "mangsang.py")
        ok = replace_in_function(p, "quoted", "norm(evidence) in norm(texts[key])",
                                 "norm(evidence) == norm(texts[key])")
        self.assertTrue(ok, "could not find quoted's `norm(evidence) in norm(texts[key])` in the copy")

    def quoted_relation_ids(self):
        hits = relation_files(self.repo, src="plugin/mangsang.py:quoted")
        self.assertTrue(hits, "the model has no relation whose src is plugin/mangsang.py:quoted")
        return [r["id"] for _, r in hits]

    def assert_stale(self, out, rids):
        for rid in rids:
            lines = [l for l in out.splitlines() if rid in l]
            self.assertTrue(any("stale" in l and "plugin/mangsang.py:quoted" in l for l in lines),
                            "impact should name %s (src plugin/mangsang.py:quoted) as stale:\n%s" % (rid, out))

    def test_09_code_mutation_makes_impact_stale(self):
        engine, repo = self.prepare()
        rids = self.quoted_relation_ids()
        self.mutate_quoted()
        before = snapshot_model(repo)
        r = self.engine_cmd("impact")
        self.assertEqual(r.code, 1, "impact should exit 1 after quoted changed:\n%s" % r.out)
        self.assert_stale(r.out, rids)
        self.assertEqual(snapshot_model(repo), before)

    def test_09_code_mutation_fails_the_guard(self):
        engine, repo = self.prepare()
        self.mutate_quoted()
        self.assert_guard_present()
        before = snapshot_model(repo)
        r = self.guard()
        self.assertIsNotNone(r.code, r.out)
        self.assertNotEqual(r.code, 0, "guard should fail when the engine's impact finds stale relations:\n%s"
                            % r.out)
        self.assertNotEqual(r.code, 2, "a stale model is a failure (1), not a refusal:\n%s" % r.out)
        self.assertIn("quoted", r.out, "the engine's findings should reach the guard's output:\n%s" % r.out)
        self.assertEqual(snapshot_model(repo), before, "the guard reconfirmed or rewrote a record")

    # (10) same-file read
    def test_10_same_file_read_makes_quoted_stale(self):
        engine, repo = self.prepare()
        rids = self.quoted_relation_ids()
        p = os.path.join(repo, "plugin", "mangsang.py")
        quoted_before = function_source(p, "quoted")
        self.assertIsNotNone(quoted_before)
        self.assertIn("split_anchor(", quoted_before, "quoted no longer reads split_anchor")
        ok = replace_in_function(p, "split_anchor", "if i > 0]", "if i >= 0]")
        self.assertTrue(ok, "could not change split_anchor's body in the copy")
        self.assertEqual(function_source(p, "quoted"), quoted_before, "quoted's own lines must not change")
        r = self.engine_cmd("impact")
        self.assertEqual(r.code, 1, "impact should exit 1 after a helper quoted reads changed:\n%s" % r.out)
        self.assert_stale(r.out, rids)

    # (11) formatting is not content
    def test_11_comment_inside_quoted_is_not_a_change(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "plugin", "mangsang.py")
        anchor = '    norm = lambda t: " ".join(str(t).split())\n'
        ok = replace_in_function(p, "quoted", anchor, anchor + "    # a comment is not content\n")
        self.assertTrue(ok, "could not add a comment inside quoted in the copy")
        self.assertIn("# a comment is not content", function_source(p, "quoted") or "")
        r = self.engine_cmd("impact")
        self.assertEqual(r.code, 0, "a comment inside quoted must not stale anything:\n%s" % r.out)

    def test_11_comment_inside_quoted_keeps_the_guard_passing(self):
        engine, repo = self.prepare()
        p = os.path.join(repo, "plugin", "mangsang.py")
        anchor = '    norm = lambda t: " ".join(str(t).split())\n'
        self.assertTrue(replace_in_function(p, "quoted", anchor, anchor + "    # a comment is not content\n"))
        self.assert_guard_present()
        r = self.guard()
        self.assertEqual(r.code, 0, "guard should still pass after a comment-only edit:\n%s" % r.out)

    # (12) refusal
    def test_12_engine_inside_the_target_is_refused(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        before = snapshot_model(repo)
        r = self.guard("--engine", os.path.join(repo, "plugin", "mangsang.py"))
        self.assertEqual(r.code, 2, "an engine inside the target must be refused with exit 2:\n%s" % r.out)
        self.assertTrue(r.out.strip(), "the refusal must say why")
        self.assertEqual(snapshot_model(repo), before)

    def test_12_engine_inside_the_target_from_the_environment_is_refused(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        r = self.guard(env=base_env(os.path.join(repo, "plugin", "mangsang.py")))
        self.assertEqual(r.code, 2, "MANGSANG_ENGINE inside the target must be refused with exit 2:\n%s" % r.out)
        self.assertTrue(r.out.strip(), "the refusal must say why")

    def test_12_symlinked_engine_resolving_inside_the_target_is_refused(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        outside = tempfile.mkdtemp(prefix="mangsang-guard-link-")
        self.addCleanup(shutil.rmtree, outside, True)
        link = os.path.join(outside, "mangsang.py")
        os.symlink(os.path.join(repo, "plugin", "mangsang.py"), link)
        r = self.guard("--engine", link)
        self.assertEqual(r.code, 2, "an engine whose realpath is inside the target must be refused:\n%s" % r.out)

    def test_12_no_engine_is_refused(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        empty = tempfile.mkdtemp(prefix="mangsang-guard-noengine-")
        self.addCleanup(shutil.rmtree, empty, True)
        env = base_env(None, drop=("MANGSANG_ENGINE",))
        env["CLAUDE_CONFIG_DIR"] = os.path.join(empty, "claude")
        env["CODEX_HOME"] = os.path.join(empty, "codex")
        env["HOME"] = empty
        r = self.guard(env=env)
        self.assertEqual(r.code, 2, "with no engine anywhere the guard must refuse with exit 2:\n%s" % r.out)
        self.assertTrue(r.out.strip(), "the refusal must say why")

    # (13) the registered scope: a file committed under plugin/ or as a root suite is asked about
    def commit_new_file(self, rel, body="x = 1\n"):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        for argv in (["git", "add", "--", rel],
                     ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "-m", "add " + rel]):
            done = run(argv, self.repo, base_env())
            self.assertEqual(done.code, 0, "could not commit %s in the copy:\n%s" % (rel, done.out))

    def scope_line(self, out):
        return [l for l in out.splitlines() if "inv-registered-scope" in l]

    def assert_new_file_fails(self, rel, body="x = 1\n"):
        """A committed file the scope does not classify: the engine's check FAILED on inv-registered-scope naming it,
        and the guard exits 1 naming both."""
        self.commit_new_file(rel, body)
        r = self.engine_cmd("check")
        self.assertEqual(r.code, 1, "the released engine's check should fail on a new unclassified %s:\n%s" % (rel, r.out))
        self.assertTrue(any("FAILED" in l and rel in l for l in self.scope_line(r.out)),
                        "check should say inv-registered-scope FAILED naming %s:\n%s" % (rel, r.out))
        self.assert_guard_fails_naming("inv-registered-scope", rel)

    def test_13_a_new_payload_module_fails_check_and_the_guard(self):
        self.prepare()
        self.assert_new_file_fails("plugin/resolver.py", "def resolve(x):\n    return x\n")

    def test_13_a_new_root_suite_fails_check_and_the_guard(self):
        self.prepare()
        self.assert_new_file_fails("test_resolver.py", "import unittest\n")

    def test_13_a_new_payload_directory_fails_check_and_the_guard(self):
        self.prepare()
        self.assert_new_file_fails("plugin/lib/util.py")

    def test_13_code_beside_the_command_adapters_fails(self):
        self.prepare()
        self.assert_new_file_fails("plugin/commands/helper.py", "print(1)\n")

    def test_13_another_vendored_library_fails(self):
        self.prepare()
        self.assert_new_file_fails("plugin/vendor/other/lib.js", "var x = 1;\n")

    def test_13_a_second_skill_fails(self):
        self.prepare()
        self.assert_new_file_fails("plugin/skills/second/SKILL.md", "# second\n")

    def test_13_a_new_command_adapter_is_classified_by_its_glob(self):
        self.prepare()
        self.commit_new_file("plugin/commands/newcmd.md", "Run `mangsang newcmd`.\n")
        r = self.engine_cmd("check")
        self.assertEqual(r.code, 0, "a new plugin/commands/*.md adapter is excepted by its glob:\n%s" % r.out)
        self.assert_guard_present()
        r = self.guard()
        self.assertEqual(r.code, 0, "the guard should still pass with a new command adapter:\n%s" % r.out)

    def test_13_registering_the_new_module_answers_the_scope(self):
        self.prepare()
        self.commit_new_file("plugin/resolver.py", "def resolve(x):\n    return x\n")
        self.assertEqual(self.engine_cmd("check").code, 1)
        r = self.engine_cmd("register", "plugin/resolver.py")
        self.assertEqual(r.code, 0, "the released engine could not register the new module:\n%s" % r.out)
        r = self.engine_cmd("check")
        self.assertEqual(r.code, 0, "a registered module answers the scope:\n%s" % r.out)
        self.assertTrue(any("holds" in l for l in self.scope_line(r.out)), r.out)

    # (14) the guard keeps the scope itself: what the engine's check cannot see about its own invariant
    SCOPE_INV = os.path.join("mangsang", "cq", "inv-registered-scope.json")

    def edit_scope(self, fn):
        def apply(d):
            fn(d["verify"])
            return d
        self.assertTrue(edit_json(os.path.join(self.repo, self.SCOPE_INV), apply))
        r = self.engine_cmd("check")
        self.assertEqual(r.code, 0, "the engine's own check still holds on this edit; only the guard can tell:\n%s" % r.out)

    def test_14_dropping_the_payload_prefix_fails_the_guard(self):
        self.prepare()
        self.edit_scope(lambda v: v.__setitem__("paths", [p for p in v["paths"] if p != "plugin/"]))
        self.assert_guard_fails_naming("inv-registered-scope", "plugin/")

    def test_14_dropping_the_suite_prefix_fails_the_guard(self):
        self.prepare()
        self.edit_scope(lambda v: v.__setitem__("paths", [p for p in v["paths"] if p != "test_"]))
        self.assert_guard_fails_naming("inv-registered-scope", "test_")

    def test_14_an_unclassified_except_fails_the_guard(self):
        self.prepare()
        self.edit_scope(lambda v: v["except"].append("plugin/*"))
        self.assert_guard_fails_naming("inv-registered-scope", "plugin/*")

    def test_14_an_except_model_md_does_not_name_fails_the_guard(self):
        self.prepare()
        p = os.path.join(self.repo, "MODEL.md")
        self.assertTrue(replace_once(p, "  - `plugin/hostcall.py` — vendored, kept in step with the other copies.\n", ""),
                        "could not find plugin/hostcall.py's bullet under Not claimed in the copy's MODEL.md")
        self.assert_guard_fails_naming("inv-registered-scope", "plugin/hostcall.py", "MODEL.md")

    # (15) a verifies goes stale when the symbol it proves changes
    def test_15_editing_a_verified_symbol_stales_its_verifies(self):
        engine, repo = self.prepare()
        hits = relation_files(repo, dst="plugin/mangsang.py:owe_for", predicate="verifies")
        self.assertEqual(len(hits), 1, "expected one verifies relation onto plugin/mangsang.py:owe_for")
        rid = hits[0][1]["id"]
        p = os.path.join(repo, "plugin", "mangsang.py")
        self.assertTrue(replace_in_function(p, "owe_for", 'r["dst"].startswith("concept:")', 'r["dst"].startswith("concept:x")'),
                        "could not change owe_for's body in the copy")
        r = self.engine_cmd("impact")
        self.assertEqual(r.code, 1, "impact should exit 1 after owe_for changed:\n%s" % r.out)
        self.assertTrue(any(rid in l and "stale" in l and "plugin/mangsang.py:owe_for" in l for l in r.out.splitlines()),
                        "impact should name the verifies %s on owe_for stale:\n%s" % (rid, r.out))


    # (16) the model's content is kept by the engine — inv-required and `check --require-model`; the guard keeps inv-required
    def required_path(self):
        return os.path.join(self.repo, "mangsang", "cq", REQUIRED + ".json")

    def test_16_the_guard_asks_check_with_require_model(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        r = self.guard()
        self.assertEqual(r.code, 0, "guard should pass on the pristine copy:\n%s" % r.out)
        self.assertIn("--- mangsang check --require-model", r.out)
        self.assertTrue(any("holds" in l and REQUIRED in l for l in r.out.splitlines()), "inv-required should hold:\n%s" % r.out)

    def test_16_a_retired_required_invariant_fails_the_guard_while_the_engine_holds(self):
        engine, repo = self.prepare()
        self.assertTrue(edit_json(self.required_path(), lambda d: dict(d, retired={"why": "disposable test copy"})))
        r = self.engine_cmd("check", "--require-model")
        self.assertEqual(r.code, 0, "a retired invariant is asked by nobody, so the engine cannot say it:\n%s" % r.out)
        self.assert_guard_fails_naming(REQUIRED)

    def test_16_a_narrowed_required_invariant_fails_the_guard_naming_what_it_dropped(self):
        engine, repo = self.prepare()

        def drop(d):
            d["verify"]["concepts"] = [c for c in d["verify"]["concepts"] if c != "owed-reread"]
            d["verify"]["invariants"] = [i for i in d["verify"]["invariants"] if i != "inv-verified-parts"]
            return d
        self.assertTrue(edit_json(self.required_path(), drop))
        r = self.engine_cmd("check", "--require-model")
        self.assertEqual(r.code, 0, "what it no longer names, the engine no longer asks:\n%s" % r.out)
        self.assert_guard_fails_naming(REQUIRED, "owed-reread", "inv-verified-parts")

    def test_16_a_drifted_concept_fails_through_the_engine(self):
        engine, repo = self.prepare()
        r = self.engine_cmd("concept", "drift", "living-answer", "--why", "disposable test copy", "--delegated", "disposable test copy")
        self.assertEqual(r.code, 0, "the released engine could not mark the concept drifted:\n%s" % r.out)
        r = self.engine_cmd("check", "--require-model")
        self.assertEqual(r.code, 1, "inv-required should fail on a drifted concept:\n%s" % r.out)
        self.assertTrue(any("FAILED" in l and REQUIRED in l and "concept:living-answer is marked drifted" in l for l in r.out.splitlines()), r.out)
        self.assert_guard_fails_naming("living-answer")

    def test_16_an_owed_reread_fails_through_the_engine(self):
        engine, repo = self.prepare()
        hits = relation_files(repo, src="plugin/mangsang.py:owe_for", predicate="realizes")
        self.assertEqual(len(hits), 1, "expected one realizes relation from plugin/mangsang.py:owe_for")
        r = self.engine_cmd("retire", hits[0][1]["id"], "--why", "disposable test copy")
        self.assertEqual(r.code, 0, r.out)
        r = self.engine_cmd("check", "--require-model")
        self.assertTrue(r.code == 1 and any(REQUIRED in l and "concept:owed-reread owes a re-read" in l for l in r.out.splitlines()), r.out)
        self.assert_guard_fails_naming("owed-reread")

    def test_16_an_engine_before_2_2_0_is_refused(self):
        engine, repo = self.prepare()
        self.assert_guard_present()
        old = tempfile.mkdtemp(prefix="mangsang-guard-oldengine-")
        self.addCleanup(shutil.rmtree, old, True)
        copy = os.path.join(old, "mangsang")
        shutil.copytree(os.path.dirname(os.path.realpath(engine)), copy, ignore=shutil.ignore_patterns("__pycache__"))
        for mf in ("plugin.json", os.path.join(".claude-plugin", "plugin.json"), os.path.join(".codex-plugin", "plugin.json")):
            if os.path.isfile(os.path.join(copy, mf)):
                self.assertTrue(edit_json(os.path.join(copy, mf), lambda d: dict(d, version="2.1.0")))
        before = snapshot_model(repo)
        r = self.guard("--engine", os.path.join(copy, "mangsang.py"), env=base_env(None, drop=("MANGSANG_ENGINE",)))
        self.assertEqual(r.code, 2, "an engine without the required kind must be refused with exit 2:\n%s" % r.out)
        self.assertIn("2.2.0", r.out)
        self.assertEqual(snapshot_model(repo), before)


if __name__ == "__main__":
    unittest.main()
