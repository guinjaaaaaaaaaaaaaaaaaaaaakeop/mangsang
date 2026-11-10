"""Package isolation: the installed payload of mangsang lives in plugin/.

These tests encode the installation/development separation. They never
import the engine into this process and never put the checkout or the
payload on this process's sys.path: everything the payload does is observed
through subprocesses run with sys.executable.

Run as `python3 test_package.py` or `python3 -m unittest test_package.py`.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PAYLOAD = os.path.join(HERE, "plugin")

TOP_LEVEL = {
    ".claude-plugin", ".codex-plugin", "LICENSE", "README.md", "anchors.py",
    "commands", "hostcall.py", "judge_worker.py", "mangsang.py",
    "plugin.json", "skills", "vendor",
}
COMMANDS = {
    "check", "concept", "confirm", "cq", "impact", "judge", "lookup",
    "observe", "reconfirm", "register", "report", "retire", "source",
}
SUBCOMMANDS = [
    "register", "confirm", "observe", "impact", "cq", "check", "retire",
    "reconfirm", "judge", "lookup", "move", "concept", "source", "report",
    "vocabulary",
]
FORBIDDEN_PARTS = {
    "AGENTS.md", "CLAUDE.md", "hunsu.json", "hunsu.lock.json",
    "hunsu.local.json", "hunsu-judgments.json", "hunsu-conflicts.md",
    "selfhost-public-records.json", "marketplace.json", ".git", ".gitignore",
    ".claude", ".codex", ".agents", ".chongdae", ".dwitbuk", ".mangsang",
    ".jokbo", ".hypothesis", "reviews", "plan", "tests",
}
SHA = {
    "hostcall.py":
        "5d0249983354b2ef8a12eb89483d29fe6bbcaf2c7f435bf2dad7c4789626344c",
    "vendor/mermaid/mermaid.min.js":
        "581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8",
    "vendor/mermaid/LICENSE":
        "ec9fb67dcb25eccc416ed56e1aab819222c805a2a4bfe4cb19e7556bf2ffde80",
    "LICENSE":
        "5d5e22555ed88e3e5e38cc09ab04ae61903f35f0c9e9ac606d2a44214cca3bd0",
}
MANIFESTS = ["plugin.json", ".claude-plugin/plugin.json",
             ".codex-plugin/plugin.json"]

PLAN_MD = "# memo\n\n## Add\n\n`add` appends a line and prints its id.\n"
PLAN_MD_CHANGED = ("# memo\n\n## Add\n\n"
                   "`add` appends a line and prints its id. Twice.\n")
MEMO_PY = "def add(store, text):\n    store.append(text)\n    return len(store)\n"
PROPOSALS = {"relations": [
    {"src": "PLAN.md#Add", "predicate": "realizes", "dst": "concept:memo-add",
     "evidence": "appends a line and prints its id"},
    {"src": "memo.py:add", "predicate": "realizes", "dst": "concept:memo-add",
     "evidence": "store.append(text)"},
]}


# ---------------------------------------------------------------- helpers
# Helpers never raise on a missing payload: they return None / empty values
# so that every test fails on its own assertion, not with an error.

def clean_env():
    env = {}
    for k, v in os.environ.items():
        if k in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
            continue
        if k.startswith(("CLAUDE", "CODEX", "AGENT_")):
            continue
        env[k] = v
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run(argv, cwd, timeout=300):
    try:
        return subprocess.run(argv, cwd=cwd, env=clean_env(),
                              capture_output=True, text=True,
                              timeout=timeout)
    except Exception as exc:  # recorded, asserted on by the caller
        return subprocess.CompletedProcess(argv, -999, "", repr(exc))


def git(args, cwd):
    return run(["git"] + list(args), cwd)


def sha256(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def real(p):
    return os.path.realpath(p)


def inside(path, root):
    path, root = real(path), real(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def payload_version():
    data = load_json(os.path.join(PAYLOAD, "plugin.json"))
    if isinstance(data, dict):
        return data.get("version")
    return None


def listing(d):
    try:
        return {n for n in os.listdir(d) if n != "__pycache__"}
    except OSError:
        return None


def strings_in(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v)


def written_by_values(project):
    """Every written_by in any JSON record under project/mangsang."""
    out = []
    for root, dirs, files in os.walk(os.path.join(project, "mangsang")):
        for n in files:
            if n.endswith(".json"):
                data = load_json(os.path.join(root, n))
                if isinstance(data, dict) and "written_by" in data:
                    out.append(data["written_by"])
    return out


def strip_code(md):
    md = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", md)
    md = re.sub(r"`[^`\n]*`", "", md)
    return md


def md_links(md):
    md = strip_code(md)
    targets = []
    for m in re.finditer(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)", md):
        targets.append(m.group(1))
    for m in re.finditer(r"(?m)^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)", md):
        targets.append(m.group(1))
    out = []
    for t in targets:
        if t.startswith("<") and t.endswith(">"):
            t = t[1:-1]
        low = t.lower()
        if low.startswith(("http:", "https:", "mailto:")) or t.startswith("#"):
            continue
        t = t.split("#", 1)[0]
        if not t:
            continue
        out.append(urllib.parse.unquote(t))
    return out


def resolve_link(doc_path, root, target):
    if target.startswith("/"):
        return os.path.normpath(os.path.join(root, target.lstrip("/")))
    return os.path.normpath(os.path.join(os.path.dirname(doc_path), target))


def copy_payload(dst):
    shutil.copytree(PAYLOAD, dst,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class _TempMixin:
    _tmp = []

    @classmethod
    def mkdtemp(cls):
        d = tempfile.mkdtemp(prefix="mangsang-pkg-")
        cls._tmp.append(d)
        return d

    @classmethod
    def tearDownClass(cls):
        for d in cls._tmp:
            shutil.rmtree(d, ignore_errors=True)
        cls._tmp = []


# ---------------------------------------------------------- (1) boundary

class TestPayloadBoundary(unittest.TestCase):

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    def test_payload_top_level_is_exact(self):
        self.pre()
        self.assertEqual(listing(PAYLOAD), TOP_LEVEL)

    def test_payload_manifest_dirs_hold_only_plugin_json(self):
        self.pre()
        for d in (".claude-plugin", ".codex-plugin"):
            with self.subTest(d=d):
                self.assertEqual(listing(os.path.join(PAYLOAD, d)),
                                 {"plugin.json"})
                self.assertTrue(os.path.isfile(
                    os.path.join(PAYLOAD, d, "plugin.json")))

    def test_payload_commands_are_exact(self):
        self.pre()
        d = os.path.join(PAYLOAD, "commands")
        self.assertEqual(listing(d), {c + ".md" for c in COMMANDS})
        for c in COMMANDS:
            with self.subTest(c=c):
                self.assertTrue(os.path.isfile(os.path.join(d, c + ".md")))

    def test_payload_skill_operate_frontmatter(self):
        self.pre()
        text = read_text(os.path.join(PAYLOAD, "skills", "operate",
                                      "SKILL.md"))
        self.assertIsNotNone(text, "plugin/skills/operate/SKILL.md missing")
        self.assertTrue(text.startswith("---\n"), "no frontmatter")
        end = text.find("\n---", 4)
        self.assertGreater(end, 0, "frontmatter not closed")
        lines = [l.strip() for l in text[4:end].splitlines()]
        self.assertIn("name: operate", lines)

    def test_payload_vendor_mermaid_exact(self):
        self.pre()
        self.assertEqual(listing(os.path.join(PAYLOAD, "vendor")),
                         {"mermaid"})
        self.assertEqual(listing(os.path.join(PAYLOAD, "vendor", "mermaid")),
                         {"LICENSE", "SOURCE.md", "mermaid.min.js"})

    def test_payload_byte_pins(self):
        self.pre()
        for rel, want in SHA.items():
            with self.subTest(rel=rel):
                self.assertEqual(sha256(os.path.join(PAYLOAD, rel)), want)
        src = read_text(os.path.join(PAYLOAD, "vendor", "mermaid",
                                     "SOURCE.md"))
        self.assertIsNotNone(src)
        self.assertIn(SHA["vendor/mermaid/mermaid.min.js"], src)

    def test_root_license_identical_to_payload_license(self):
        self.pre()
        payload_license = os.path.join(PAYLOAD, "LICENSE")
        self.assertTrue(os.path.isfile(payload_license))
        root_license = os.path.join(HERE, "LICENSE")
        if os.path.exists(root_license):
            with open(root_license, "rb") as a, \
                    open(payload_license, "rb") as b:
                self.assertEqual(a.read(), b.read())

    def test_payload_has_no_symlink(self):
        self.pre()
        self.assertFalse(os.path.islink(PAYLOAD))
        found = []
        for root, dirs, files in os.walk(PAYLOAD, followlinks=False):
            for n in dirs + files:
                p = os.path.join(root, n)
                if os.path.islink(p):
                    found.append(os.path.relpath(p, PAYLOAD))
        self.assertEqual(found, [])

    def test_payload_has_no_development_material(self):
        self.pre()
        bad = []
        for root, dirs, files in os.walk(PAYLOAD):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in dirs:
                rel = os.path.relpath(os.path.join(root, n), PAYLOAD)
                if n in FORBIDDEN_PARTS or n == "mangsang":
                    bad.append(rel)
            for n in files:
                if n.endswith(".pyc"):
                    continue
                rel = os.path.relpath(os.path.join(root, n), PAYLOAD)
                if n in FORBIDDEN_PARTS:
                    bad.append(rel)
                if re.fullmatch(r"test_.*\.py", n):
                    bad.append(rel)
        self.assertEqual(bad, [])

    def test_checkout_is_git_toplevel(self):
        self.pre()
        p = git(["rev-parse", "--show-toplevel"], HERE)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(real(p.stdout.strip()), real(HERE))

    def test_payload_bytecode_not_tracked(self):
        self.pre()
        top = git(["rev-parse", "--show-toplevel"], HERE)
        self.assertEqual(top.returncode, 0, top.stderr)
        self.assertEqual(real(top.stdout.strip()), real(HERE))
        p = git(["ls-files", "--", "plugin"], HERE)
        self.assertEqual(p.returncode, 0, p.stderr)
        tracked = [l for l in p.stdout.splitlines() if l.strip()]
        self.assertEqual([l for l in tracked
                          if "__pycache__" in l or l.endswith(".pyc")], [])

    def test_payload_bytecode_is_ignored(self):
        self.pre()
        top = git(["rev-parse", "--show-toplevel"], HERE)
        self.assertEqual(real(top.stdout.strip()), real(HERE))
        p = git(["check-ignore", "-q", "--no-index",
                 "plugin/__pycache__/mangsang.cpython-311.pyc"], HERE)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_payload_nothing_needed_is_ignored(self):
        self.pre()
        top = git(["rev-parse", "--show-toplevel"], HERE)
        self.assertEqual(real(top.stdout.strip()), real(HERE))
        p = git(["ls-files", "--others", "--ignored", "--exclude-standard",
                 "--", "plugin"], HERE)
        self.assertEqual(p.returncode, 0, p.stderr)
        ignored = [l for l in p.stdout.splitlines() if l.strip()]
        self.assertEqual([l for l in ignored
                          if "__pycache__/" not in l
                          and not l.endswith(".pyc")], [])


# ---------------------------------------------- (2) manifests and catalogs

class TestManifestsAndCatalogs(unittest.TestCase):

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    def manifests(self):
        return {m: load_json(os.path.join(PAYLOAD, m)) for m in MANIFESTS}

    def test_manifests_parse_name_version_engines(self):
        self.pre()
        versions = set()
        for m, data in self.manifests().items():
            with self.subTest(manifest=m):
                self.assertIsInstance(data, dict, m + " does not parse")
                self.assertEqual(data.get("name"), "mangsang")
                v = data.get("version")
                self.assertIsInstance(v, str)
                self.assertRegex(v, r"^\d+\.\d+\.\d+$")
                versions.add(v)
                self.assertEqual((data.get("engines") or {}).get("python"),
                                 ">=3.11")
        self.assertEqual(len(versions), 1, versions)

    def test_manifests_keep_records(self):
        self.pre()
        for m in ("plugin.json", ".claude-plugin/plugin.json"):
            with self.subTest(manifest=m):
                data = load_json(os.path.join(PAYLOAD, m))
                self.assertIsInstance(data, dict)
                self.assertEqual(data.get("records"),
                                 ["mangsang/", ".mangsang/"])

    def test_manifest_plugin_paths_exist_in_payload(self):
        self.pre()
        seen = 0
        for m, data in self.manifests().items():
            self.assertIsInstance(data, dict, m)
            for s in strings_in(data):
                for x in re.findall(r"\{plugin:mangsang\}/([^\s\"']+)", s):
                    seen += 1
                    with self.subTest(manifest=m, path=x):
                        p = os.path.join(PAYLOAD, x)
                        self.assertTrue(inside(p, PAYLOAD), x)
                        self.assertTrue(os.path.exists(p), x)
        self.assertGreater(seen, 0, "no {plugin:mangsang}/ argv in manifests")

    def test_codex_manifest_skills_resolve_inside_payload(self):
        self.pre()
        data = load_json(os.path.join(PAYLOAD, ".codex-plugin",
                                      "plugin.json"))
        self.assertIsInstance(data, dict)
        skills = data.get("skills")
        self.assertIsInstance(skills, str)
        p = os.path.normpath(os.path.join(PAYLOAD, skills))
        self.assertTrue(inside(p, PAYLOAD), skills)
        self.assertTrue(os.path.isdir(p), skills)
        self.assertTrue(os.path.isfile(os.path.join(p, "operate",
                                                    "SKILL.md")))

    def test_manifest_component_paths_resolve_inside_payload(self):
        self.pre()
        for m, data in self.manifests().items():
            self.assertIsInstance(data, dict, m)
            for key in ("hooks", "commands", "mcpServers"):
                val = data.get(key)
                paths = []
                if isinstance(val, str):
                    paths = [val]
                elif isinstance(val, list):
                    paths = [v for v in val if isinstance(v, str)]
                for x in paths:
                    with self.subTest(manifest=m, key=key, path=x):
                        x2 = x.replace("${CLAUDE_PLUGIN_ROOT}/", "")
                        p = os.path.normpath(os.path.join(PAYLOAD, x2))
                        self.assertTrue(inside(p, PAYLOAD), x)
                        self.assertTrue(os.path.exists(p), x)

    def test_plugin_root_references_in_docs_exist(self):
        self.pre()
        files = []
        for sub in ("commands", "skills"):
            for root, dirs, fs in os.walk(os.path.join(PAYLOAD, sub)):
                files += [os.path.join(root, f) for f in fs
                          if f.endswith(".md")]
        self.assertTrue(files, "no command or skill docs in payload")
        seen = 0
        for f in files:
            text = read_text(f) or ""
            for x in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)",
                                text):
                x = x.rstrip(".")
                seen += 1
                with self.subTest(doc=os.path.relpath(f, PAYLOAD), path=x):
                    p = os.path.join(PAYLOAD, x)
                    self.assertTrue(inside(p, PAYLOAD), x)
                    self.assertTrue(os.path.exists(p), x)
        self.assertGreater(seen, 0)

    def test_root_has_no_second_copy_of_payload(self):
        self.pre()
        for rel in ("plugin.json", ".claude-plugin/plugin.json",
                    ".codex-plugin", "anchors.py",
                    "hostcall.py", "commands", "skills", "vendor"):
            with self.subTest(path=rel):
                self.assertFalse(os.path.lexists(os.path.join(HERE, rel)),
                                 rel + " still at the checkout root")

    def test_root_claude_marketplace_points_to_plugin(self):
        self.pre()
        v = payload_version()
        self.assertIsNotNone(v)
        data = load_json(os.path.join(HERE, ".claude-plugin",
                                      "marketplace.json"))
        self.assertIsInstance(data, dict)
        self.assertEqual((data.get("metadata") or {}).get("version"), v)
        entries = [p for p in data.get("plugins", [])
                   if p.get("name") == "mangsang"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("source"), "./plugin")
        self.assertEqual(entries[0].get("version"), v)

    def test_root_agents_marketplace_points_to_plugin(self):
        self.pre()
        data = load_json(os.path.join(HERE, ".agents", "plugins",
                                      "marketplace.json"))
        self.assertIsInstance(data, dict)
        entries = [p for p in data.get("plugins", [])
                   if p.get("name") == "mangsang"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("source"),
                         {"source": "local", "path": "./plugin"})
        self.assertNotIn("version", entries[0])


# ------------------------------------------------------------- (3) docs

class TestDocs(unittest.TestCase):

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    def test_payload_readme_links_stay_inside_payload(self):
        self.pre()
        doc = os.path.join(PAYLOAD, "README.md")
        text = read_text(doc)
        self.assertIsNotNone(text, "plugin/README.md missing")
        for t in md_links(text):
            with self.subTest(link=t):
                p = resolve_link(doc, PAYLOAD, t)
                self.assertTrue(inside(p, PAYLOAD),
                                t + " leaves the installed payload")
                self.assertTrue(os.path.exists(p), t + " does not exist")

    def test_root_docs_links_resolve(self):
        self.pre()
        for name in ("README.md", "AGENTS.md"):
            doc = os.path.join(HERE, name)
            text = read_text(doc)
            self.assertIsNotNone(text, name + " missing")
            for t in md_links(text):
                with self.subTest(doc=name, link=t):
                    p = resolve_link(doc, HERE, t)
                    self.assertTrue(inside(p, HERE), t)
                    self.assertTrue(os.path.exists(p), t + " does not exist")

    def test_root_readme_links_payload_readme(self):
        self.pre()
        doc = os.path.join(HERE, "README.md")
        text = read_text(doc)
        self.assertIsNotNone(text)
        want = real(os.path.join(PAYLOAD, "README.md"))
        hits = [t for t in md_links(text)
                if real(resolve_link(doc, HERE, t)) == want]
        self.assertTrue(hits, "README.md does not link to plugin/README.md")


# -------------------------------------------- (4) installed copy, isolated

class TestInstalledCopyIsolated(_TempMixin, unittest.TestCase):
    _tmp = []
    _state = None

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    @classmethod
    def state(cls):
        if cls._state is not None:
            return cls._state
        s = {}
        cls._state = s
        base = cls.mkdtemp()
        copy = os.path.join(base, "installed plugin")
        copy_payload(copy)
        s["copy"] = copy
        s["version"] = payload_version()
        s["toplevel"] = git(["rev-parse", "--show-toplevel"], copy)
        P = cls.mkdtemp()
        s["project"] = P

        def py(*a):
            return [sys.executable, "-B", "-E", "-s"] + list(a)

        def ms(*a):
            return run(py(os.path.join(copy, "mangsang.py"), *a), P)

        probe = (
            "import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import mangsang, anchors, hostcall, judge_worker\n"
            "print(json.dumps({'files': {m.__name__: m.__file__ for m in "
            "(mangsang, anchors, hostcall, judge_worker)}, "
            "'path': sys.path}))\n" % copy)
        s["probe"] = run(py("-c", probe), P)
        s["help"] = ms("--help")
        s["worker_help"] = run(py(os.path.join(copy, "judge_worker.py"),
                                  "--help"), P)

        write(os.path.join(P, "PLAN.md"), PLAN_MD)
        write(os.path.join(P, "memo.py"), MEMO_PY)
        steps = []
        steps.append(("concept add", ms(
            "concept", "add", "memo-add", "--means",
            "add appends a line and prints its id", "--by", "kim",
            "--target", P)))
        steps.append(("register", ms("register", "PLAN.md", "memo.py",
                                     "--target", P)))
        write(os.path.join(P, "proposals.json"), json.dumps(PROPOSALS))
        steps.append(("confirm", ms("confirm", "proposals.json", "--by",
                                    "kim", "--target", P)))
        s["proposals_left"] = os.path.exists(os.path.join(P,
                                                          "proposals.json"))
        rel_dir = os.path.join(P, "mangsang", "relations")
        rels = {}
        if os.path.isdir(rel_dir):
            for n in sorted(os.listdir(rel_dir)):
                rels[n] = load_json(os.path.join(rel_dir, n))
        s["relations"] = rels
        steps.append(("impact fresh", ms("impact", "--target", P)))
        s["lookup"] = ms("lookup", "memo.py", "--target", P)
        steps.append(("lookup", s["lookup"]))
        s["concept_list"] = ms("concept", "list", "--brief", "--target", P)
        steps.append(("concept list", s["concept_list"]))
        s["steps"] = steps
        write(os.path.join(P, "PLAN.md"), PLAN_MD_CHANGED)
        s["impact_stale"] = ms("impact", "--target", P)
        s["report_html"] = ms("report", "--html", "NET.html", "--target", P)
        s["html"] = read_text(os.path.join(P, "NET.html"))
        s["report_md"] = ms("report", "--target", P)
        s["mermaid"] = read_text(os.path.join(copy, "vendor", "mermaid",
                                              "mermaid.min.js"))
        return s

    def test_copy_is_outside_checkout_and_not_git(self):
        self.pre()
        s = self.state()
        self.assertIn(" ", os.path.basename(s["copy"]))
        self.assertFalse(inside(s["copy"], HERE))
        self.assertFalse(inside(s["project"], HERE))
        self.assertNotEqual(s["toplevel"].returncode, 0,
                            "the installed copy is inside a git work tree")

    def test_import_probe_resolves_to_copy(self):
        self.pre()
        s = self.state()
        p = s["probe"]
        self.assertEqual(p.returncode, 0, p.stderr)
        data = json.loads(p.stdout.strip().splitlines()[-1])
        for mod in ("mangsang", "anchors", "hostcall", "judge_worker"):
            with self.subTest(module=mod):
                self.assertIn(mod, data["files"])
                self.assertTrue(inside(data["files"][mod], s["copy"]),
                                data["files"][mod])
        for entry in data["path"]:
            with self.subTest(entry=entry):
                self.assertFalse(inside(entry or s["project"], HERE), entry)

    def test_help_names_every_subcommand(self):
        self.pre()
        s = self.state()
        h = s["help"]
        self.assertEqual(h.returncode, 0, h.stderr)
        for sub in SUBCOMMANDS:
            with self.subTest(sub=sub):
                self.assertRegex(h.stdout, r"\b%s\b" % re.escape(sub))
        w = s["worker_help"]
        self.assertEqual(w.returncode, 0, w.stderr)

    def test_help_choices_are_exactly_the_subcommands(self):
        """The usage line's {a,b,...} group is the parser's own list: a word in the help's prose is not a subcommand."""
        self.pre()
        h = self.state()["help"]
        self.assertEqual(h.returncode, 0, h.stderr)
        m = re.search(r"\{([a-z,-]+)\}", h.stdout)
        self.assertIsNotNone(m, h.stdout[:400])
        self.assertEqual(set(m.group(1).split(",")), set(SUBCOMMANDS))

    def test_fixture_workflow_steps_succeed(self):
        self.pre()
        s = self.state()
        for name, p in s["steps"]:
            with self.subTest(step=name):
                self.assertEqual(p.returncode, 0,
                                 "%s\n%s\n%s" % (name, p.stdout, p.stderr))
        self.assertFalse(s["proposals_left"], "confirm left proposals.json")

    def test_fixture_relations_signed_and_versioned(self):
        self.pre()
        s = self.state()
        v = s["version"]
        self.assertIsNotNone(v)
        rels = s["relations"]
        self.assertEqual(len(rels), 2, sorted(rels))
        for n, r in rels.items():
            with self.subTest(relation=n):
                self.assertIsInstance(r, dict)
                self.assertEqual((r.get("confirmed") or {}).get("by"), "kim")
                self.assertEqual(r.get("written_by"), "mangsang " + v)

    def test_fixture_lookup_and_concept_list_name_concept(self):
        self.pre()
        s = self.state()
        self.assertEqual(s["lookup"].returncode, 0, s["lookup"].stderr)
        self.assertIn("memo-add", s["lookup"].stdout)
        self.assertEqual(s["concept_list"].returncode, 0,
                         s["concept_list"].stderr)
        self.assertIn("memo-add", s["concept_list"].stdout)

    def test_fixture_impact_names_stale_plan_relation(self):
        self.pre()
        s = self.state()
        p = s["impact_stale"]
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        out = p.stdout + p.stderr
        plan_ids = [r.get("id") for r in s["relations"].values()
                    if isinstance(r, dict) and r.get("src") == "PLAN.md#Add"]
        memo_ids = [r.get("id") for r in s["relations"].values()
                    if isinstance(r, dict) and r.get("src") == "memo.py:add"]
        self.assertEqual(len(plan_ids), 1)
        stale_lines = [l for l in out.splitlines() if "stale" in l]
        self.assertTrue(any(plan_ids[0] in l and "PLAN.md#Add" in l
                            for l in stale_lines), out)
        for mid in memo_ids:
            self.assertFalse(any(mid in l for l in stale_lines), out)

    def test_fixture_report_html_inlines_copy_mermaid(self):
        self.pre()
        s = self.state()
        p = s["report_html"]
        self.assertEqual(p.returncode, 0, p.stderr)
        html, js = s["html"], s["mermaid"]
        self.assertIsNotNone(html, "NET.html not written")
        self.assertIsNotNone(js)
        self.assertNotIn("<script src", html)
        self.assertIn("mermaid.initialize", html)
        self.assertIn("memo-add", html)
        self.assertIn(js[:300], html)
        self.assertIn(js[-300:], html)

    def test_fixture_report_markdown_has_mermaid_block(self):
        self.pre()
        s = self.state()
        p = s["report_md"]
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("```mermaid", p.stdout)

    def test_zz_copy_holds_no_bytecode_after_runs(self):
        self.pre()
        s = self.state()
        bad = []
        for root, dirs, files in os.walk(s["copy"]):
            bad += [os.path.join(root, d) for d in dirs if d == "__pycache__"]
            bad += [os.path.join(root, f) for f in files
                    if f.endswith(".pyc")]
        self.assertEqual(bad, [])


# ------------------------------------- (5) engine identity outside checkout

class TestVendoredInsideForeignRepo(_TempMixin, unittest.TestCase):
    _tmp = []

    def test_vendored_payload_is_release_not_working_source(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")
        v = payload_version()
        self.assertIsNotNone(v)
        repo = self.mkdtemp()
        dest = os.path.join(repo, "vendored", "mangsang")
        os.makedirs(os.path.dirname(dest))
        copy_payload(dest)
        g = git(["init", "-q"], repo)
        self.assertEqual(g.returncode, 0, g.stderr)
        g = git(["add", "-A"], repo)
        self.assertEqual(g.returncode, 0, g.stderr)
        g = git(["-c", "user.name=t", "-c", "user.email=t@t",
                 "-c", "commit.gpgsign=false", "commit", "-q", "-m",
                 "vendor"], repo)
        self.assertEqual(g.returncode, 0, g.stderr)
        P = self.mkdtemp()
        p = run([sys.executable, "-B", "-E", "-s",
                 os.path.join(dest, "mangsang.py"), "concept", "add", "x",
                 "--means", "x is a fixture", "--by", "kim"], P)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        wb = written_by_values(P)
        self.assertTrue(wb, "no record with written_by")
        for w in wb:
            self.assertEqual(w, "mangsang " + v)


# ------------------------------------------------- (6) the source checkout

class TestSourceCheckout(_TempMixin, unittest.TestCase):
    _tmp = []

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    def concept_add(self, script, name):
        P = self.mkdtemp()
        p = run([sys.executable, "-B", script, "concept", "add", name,
                 "--means", "%s is a fixture" % name, "--by", "kim",
                 "--target", P], HERE)
        return P, p

    def test_checkout_payload_signs_as_working_source(self):
        self.pre()
        v = payload_version()
        self.assertIsNotNone(v)
        P, p = self.concept_add(os.path.join("plugin", "mangsang.py"), "z")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        wb = written_by_values(P)
        self.assertTrue(wb, "no record with written_by")
        for w in wb:
            self.assertRegex(
                w, r"^mangsang %s\+g[0-9a-f]+(-dirty)?$" % re.escape(v))

    def test_root_wrapper_is_thin(self):
        self.pre()
        root = os.path.join(HERE, "mangsang.py")
        self.assertTrue(os.path.isfile(root))
        self.assertLess(os.path.getsize(root), 4096)
        self.assertNotIn("def main(", read_text(root) or "def main(")

    def test_root_wrapper_help_matches_payload(self):
        self.pre()
        a = run([sys.executable, "-B", os.path.join(HERE, "mangsang.py"),
                 "--help"], HERE)
        b = run([sys.executable, "-B", os.path.join(PAYLOAD, "mangsang.py"),
                 "--help"], HERE)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertEqual(a.stdout, b.stdout)

    def test_root_wrapper_signs_like_payload_and_inlines_mermaid(self):
        self.pre()
        _, ref = self.concept_add(os.path.join(PAYLOAD, "mangsang.py"), "y")
        self.assertEqual(ref.returncode, 0, ref.stdout + ref.stderr)
        ref_wb = written_by_values(_)
        self.assertEqual(len(set(ref_wb)), 1, ref_wb)

        P = self.mkdtemp()
        wrapper = os.path.join(HERE, "mangsang.py")
        p = run([sys.executable, "-B", wrapper, "concept", "add", "y",
                 "--means", "y is a fixture", "--by", "kim", "--target", P], P)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        wb = written_by_values(P)
        self.assertTrue(wb)
        self.assertEqual(set(wb), set(ref_wb))

        p = run([sys.executable, "-B", wrapper, "report", "--html", "W.html",
                 "--target", P], P)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        html = read_text(os.path.join(P, "W.html"))
        js = read_text(os.path.join(PAYLOAD, "vendor", "mermaid",
                                    "mermaid.min.js"))
        self.assertIsNotNone(html, "W.html not written")
        self.assertIsNotNone(js)
        self.assertIn(js[:300], html)

    def test_root_judge_worker_is_thin(self):
        self.pre()
        root = os.path.join(HERE, "judge_worker.py")
        self.assertTrue(os.path.isfile(root),
                        "no root judge_worker.py (source alias)")
        self.assertLess(os.path.getsize(root) if os.path.isfile(root)
                        else 4096, 4096)
        self.assertNotIn("def main(", read_text(root) or "def main(")
        a = sha256(root)
        b = sha256(os.path.join(PAYLOAD, "judge_worker.py"))
        self.assertIsNotNone(b)
        self.assertNotEqual(a, b, "root judge_worker.py is a second copy")

    def test_root_judge_worker_help_matches_payload(self):
        self.pre()
        a = run([sys.executable, "-B", os.path.join(HERE, "judge_worker.py"),
                 "--help"], HERE)
        b = run([sys.executable, "-B",
                 os.path.join(PAYLOAD, "judge_worker.py"), "--help"], HERE)
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, b.stdout)


# ------------------------------- (7) engine identity is catalog ownership

def claude_catalog(name, source):
    return {"name": "fixture", "owner": {"name": "t"},
            "plugins": [{"name": name, "source": source}]}


def codex_catalog(name, source):
    return {"name": "fixture", "plugins": [{"name": name, "source": source}]}


class TestEngineIdentityOwnership(_TempMixin, unittest.TestCase):
    """The +g<sha> stamp for a nested payload needs the toplevel's own
    catalog to map `mangsang` to the payload directory."""
    _tmp = []

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    @classmethod
    def fixture(cls, d, claude=None, codex=None):
        """Build REPO with PAYLOAD at REPO/<d>, run concept add from P.
        Never raises: setup problems are reported in out['error']."""
        out = {"error": None, "proc": None, "wb": [], "sha": None,
               "repo": None, "project": None}
        try:
            repo = cls.mkdtemp()
            out["repo"] = repo
            dest = repo if d == "." else os.path.join(repo, d)
            shutil.copytree(PAYLOAD, dest, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__",
                                                          "*.pyc"))
            if claude is not None:
                os.makedirs(os.path.join(repo, ".claude-plugin"),
                            exist_ok=True)
                write(os.path.join(repo, ".claude-plugin",
                                   "marketplace.json"), json.dumps(claude))
            if codex is not None:
                os.makedirs(os.path.join(repo, ".agents", "plugins"),
                            exist_ok=True)
                write(os.path.join(repo, ".agents", "plugins",
                                   "marketplace.json"), json.dumps(codex))
            for args in (["init", "-q"], ["add", "-A"],
                         ["-c", "user.name=t", "-c", "user.email=t@t",
                          "-c", "commit.gpgsign=false", "commit", "-q",
                          "-m", "fixture"]):
                g = git(args, repo)
                if g.returncode != 0:
                    out["error"] = "git %s: %s" % (args, g.stderr)
                    return out
            h = git(["rev-parse", "--short", "HEAD"], repo)
            if h.returncode != 0:
                out["error"] = "rev-parse: " + h.stderr
                return out
            out["sha"] = h.stdout.strip()
            P = cls.mkdtemp()
            out["project"] = P
            out["proc"] = run([sys.executable, "-B", "-E", "-s",
                               os.path.join(dest, "mangsang.py"), "concept",
                               "add", "x", "--means", "x is a fixture",
                               "--by", "kim", "--target", P], P)
            out["wb"] = written_by_values(P)
        except Exception as exc:
            out["error"] = repr(exc)
        return out

    def check(self, f, want):
        self.assertIsNone(f["error"], f["error"])
        self.assertFalse(inside(f["project"], f["repo"]))
        self.assertFalse(inside(f["project"], HERE))
        self.assertFalse(inside(f["repo"], HERE))
        p = f["proc"]
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(f["wb"], "no record with written_by")
        for w in f["wb"]:
            self.assertEqual(w, want)

    def release(self):
        v = payload_version()
        self.assertIsNotNone(v)
        return "mangsang " + v

    def test_neg_no_catalog_plugin_dir_is_release(self):
        self.pre()
        want = self.release()
        self.check(self.fixture("plugin"), want)

    def test_neg_other_name_is_release(self):
        self.pre()
        want = self.release()
        f = self.fixture(
            "plugin",
            claude=claude_catalog("other", "./plugin"),
            codex=codex_catalog("other", {"source": "local",
                                          "path": "./plugin"}))
        self.check(f, want)

    def test_neg_other_dir_is_release(self):
        self.pre()
        want = self.release()
        f = self.fixture(
            "plugin",
            claude=claude_catalog("mangsang", "./elsewhere"),
            codex=codex_catalog("mangsang", {"source": "local",
                                             "path": "./elsewhere"}))
        self.check(f, want)

    def test_neg_remote_source_is_release(self):
        self.pre()
        want = self.release()
        f = self.fixture(
            "plugin",
            claude=claude_catalog("mangsang", {"source": "github",
                                               "repo": "someone/mangsang"}))
        self.check(f, want)

    def test_pos_claude_catalog_stamps_working_source(self):
        self.pre()
        rel = self.release()
        f = self.fixture("plugin",
                         claude=claude_catalog("mangsang", "./plugin"))
        self.assertTrue(f["sha"], f["error"])
        self.check(f, "%s+g%s" % (rel, f["sha"]))

    def test_pos_codex_catalog_stamps_working_source(self):
        self.pre()
        rel = self.release()
        f = self.fixture("plugin",
                         codex=codex_catalog("mangsang", {"source": "local",
                                                          "path": "./plugin"}))
        self.assertTrue(f["sha"], f["error"])
        self.check(f, "%s+g%s" % (rel, f["sha"]))

    def test_pos_not_named_plugin_catalog_decides(self):
        self.pre()
        rel = self.release()
        f = self.fixture("payload",
                         claude=claude_catalog("mangsang", "./payload/"))
        self.assertTrue(f["sha"], f["error"])
        self.check(f, "%s+g%s" % (rel, f["sha"]))

    def test_pos_toplevel_payload_stamps_working_source(self):
        self.pre()
        rel = self.release()
        f = self.fixture(".")
        self.assertTrue(f["sha"], f["error"])
        self.check(f, "%s+g%s" % (rel, f["sha"]))


# ------------------------------------ (8) source import compatibility

PROBE = r"""
import importlib, json, os, sys
%(prelude)s
out = {"errors": {}}
def rp(p):
    return os.path.realpath(p) if isinstance(p, str) else None
mods = {}
for name in ("mangsang", "judge_worker", "anchors", "hostcall"):
    try:
        mods[name] = importlib.import_module(name)
    except BaseException as exc:
        out["errors"][name] = repr(exc)
m = mods.get("mangsang"); jw = mods.get("judge_worker")
an = mods.get("anchors"); hc = mods.get("hostcall")
out["files"] = {k: rp(getattr(v, "__file__", None)) for k, v in mods.items()}
out["m_callable"] = {k: callable(getattr(m, k, None))
                     for k in ("main", "decl", "engine")}
out["m_import_module_is"] = (m is not None
                             and importlib.import_module("mangsang") is m)
out["m_sys_modules_is"] = m is not None and sys.modules.get("mangsang") is m
out["m_anchors_is"] = (m is not None and "anchors" in sys.modules
                       and getattr(m, "anchors", None)
                       is sys.modules["anchors"])
out["jw_main_callable"] = callable(getattr(jw, "main", None))
out["jw_import_module_is"] = (jw is not None and
                              importlib.import_module("judge_worker") is jw)
out["jw_run_claude_is_hostcall"] = (
    jw is not None and hc is not None
    and getattr(jw, "run_claude", None) is not None
    and getattr(jw, "run_claude", None) is getattr(hc, "run_claude", None))
mf = getattr(m, "__file__", None)
out["engine_worker"] = (rp(os.path.join(os.path.dirname(mf),
                                        "judge_worker.py"))
                        if isinstance(mf, str) else None)
out["module_files"] = [rp(getattr(v, "__file__", None))
                       for v in list(sys.modules.values())
                       if isinstance(getattr(v, "__file__", None), str)]
try:
    out["engine"] = m.engine() if callable(getattr(m, "engine", None)) \
        else None
except BaseException as exc:
    out["engine"] = None
    out["errors"]["engine"] = repr(exc)
sys.stdout.write(json.dumps(out) + "\n")
"""


class TestSourceImport(_TempMixin, unittest.TestCase):
    """`import mangsang` / `import judge_worker` from a checkout are the
    runtime modules of plugin/ — one instance each."""
    _tmp = []
    _state = None

    def pre(self):
        self.assertTrue(os.path.isdir(PAYLOAD),
                        "plugin/ (the installed payload) does not exist")

    @classmethod
    def state(cls):
        if cls._state is not None:
            return cls._state
        s = {}
        cls._state = s
        py = [sys.executable, "-B", "-E", "-s", "-c"]
        s["cwd HERE"] = run(py + [PROBE % {"prelude": ""}], HERE)
        tmp = cls.mkdtemp()
        s["sys.path HERE"] = run(
            py + [PROBE % {"prelude": "sys.path.insert(0, %r)" % HERE}], tmp)
        return s

    def probes(self):
        """(label, process, parsed JSON or None) for both modes."""
        out = []
        for label, p in self.state().items():
            data = None
            lines = p.stdout.splitlines()
            if lines:
                try:
                    data = json.loads(lines[-1])
                except ValueError:
                    data = None
            out.append((label, p, data))
        return out

    def test_probe_exits_zero_and_prints_only_json(self):
        self.pre()
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(len(p.stdout.splitlines()), 1, p.stdout)
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertEqual(data.get("errors") if data else None, {},
                                 p.stderr)

    def test_import_mangsang_is_payload_runtime(self):
        self.pre()
        want = real(os.path.join(PAYLOAD, "mangsang.py"))
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertEqual(data["files"].get("mangsang"), want)
                self.assertEqual(data["m_callable"],
                                 {"main": True, "decl": True,
                                  "engine": True})
                self.assertTrue(data["m_import_module_is"])
                self.assertTrue(data["m_sys_modules_is"])

    def test_import_anchors_is_payload_and_shared(self):
        self.pre()
        want = real(os.path.join(PAYLOAD, "anchors.py"))
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertEqual(data["files"].get("anchors"), want)
                self.assertTrue(data["m_anchors_is"],
                                "mangsang.anchors is not sys.modules['anchors']")

    def test_import_judge_worker_is_payload_worker(self):
        self.pre()
        want = real(os.path.join(PAYLOAD, "judge_worker.py"))
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertEqual(data["files"].get("judge_worker"), want)
                self.assertTrue(data["jw_main_callable"])
                self.assertTrue(data["jw_import_module_is"])

    def test_import_hostcall_is_payload_and_shared(self):
        self.pre()
        want = real(os.path.join(PAYLOAD, "hostcall.py"))
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertEqual(data["files"].get("hostcall"), want)
                self.assertTrue(data["jw_run_claude_is_hostcall"])

    def test_engine_names_the_imported_worker(self):
        self.pre()
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertIsNotNone(data["engine_worker"])
                self.assertEqual(data["engine_worker"],
                                 data["files"].get("judge_worker"))

    def test_one_instance_per_file(self):
        self.pre()
        pm = real(os.path.join(PAYLOAD, "mangsang.py"))
        pj = real(os.path.join(PAYLOAD, "judge_worker.py"))
        hm = real(os.path.join(HERE, "mangsang.py"))
        hj = real(os.path.join(HERE, "judge_worker.py"))
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                files = data["module_files"]
                self.assertEqual(files.count(pm), 1, files)
                self.assertEqual(files.count(pj), 1, files)
                self.assertEqual(files.count(hm), 0,
                                 "root mangsang.py is a module")
                self.assertEqual(files.count(hj), 0,
                                 "root judge_worker.py is a module")

    def test_imported_engine_is_working_source(self):
        self.pre()
        v = payload_version()
        self.assertIsNotNone(v)
        for label, p, data in self.probes():
            with self.subTest(mode=label):
                self.assertIsInstance(data, dict, p.stdout + p.stderr)
                self.assertIsInstance(data["engine"], str,
                                      data.get("errors"))
                self.assertRegex(
                    data["engine"],
                    r"^mangsang %s\+g[0-9a-f]+(-dirty)?$" % re.escape(v))


if __name__ == "__main__":
    unittest.main()
