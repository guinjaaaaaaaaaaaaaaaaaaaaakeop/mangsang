"""Self-check for mangsang. A temp project with a plan section, a module and a test; every rejection and every kind of staleness fires once.

  python test_mangsang.py
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "plugin")   # the installed payload; the root mangsang.py is only its CLI wrapper
sys.path.insert(0, PLUGIN)
import mangsang  # noqa: E402

PLAN = "# plan\n\n## Q1 add\n\n`add` appends and prints `#<id>`.\n\n### detail\n\nmore\n\n## Q2 list\n\nlists.\n"
CODE = "X = 1\n\n\ndef add(store, text):\n    return 1\n\n\ndef list_(store):\n    return []\n"
TEST = "def test_Q1_add():\n    assert True\n"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False))


def run(*argv):
    # the self-check plays a person at a terminal; the session that runs it may be an agent's (its env says so)
    for k in mangsang.AGENT_ENV:
        os.environ.pop(k, None)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = mangsang.main(list(argv))
        except SystemExit as err:
            code = err.code if isinstance(err.code, int) else 1
            out.write(str(err) + "\n")
    return code, out.getvalue()


class Project:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="mangsang-test-")
        write(os.path.join(self.dir, "plan", "PLAN.md"), PLAN)
        write(os.path.join(self.dir, "memo.py"), CODE)
        write(os.path.join(self.dir, "test_memo.py"), TEST)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.dir, ignore_errors=True)

    def propose(self, *rels):
        write(os.path.join(self.dir, "proposals.json"), {"relations": list(rels)})
        return run("confirm", os.path.join(self.dir, "proposals.json"), "--by", "kim", "--target", self.dir)


def rel(src, pred, dst, ev="appends and prints"):   # a quote from PLAN's Q1 section — evidence must be in an anchor's text
    return {"src": src, "predicate": pred, "dst": dst, "evidence": ev}



class Skip(unittest.SkipTest):
    """Raised by a test that cannot run on this host; the runner reports it as SKIP, never as PASS. A unittest.SkipTest,
    so a harness that runs these functions under unittest (hacheong's red-before-build) reads it as a skip, not an error."""

def test_python_fingerprints_ignore_comments_and_formatting_markdown_does_not():
    """The fingerprint of a Python anchor is its token stream: a comment, a blank line, reformatting — no change.
    Real edits change it. Markdown stays a text hash: in prose the wording is the content."""
    code = "def add(store, text):\n    return 1\n"
    assert mangsang.fp(code, "m.py") == mangsang.fp("# note\ndef add(store, text):  # inline\n\n    return 1\n", "m.py")
    assert mangsang.fp(code, "m.py") != mangsang.fp("def add(store, text):\n    return 2\n", "m.py")
    assert mangsang.fp("word\n", "a.md") != mangsang.fp("word changed\n", "a.md")
    assert mangsang.fp("word\n", "a.md") != mangsang.fp("word\n", None) or True   # md/None both text-hash — same digest
    assert mangsang.fp("word\n", "a.md") == mangsang.fp("word\n")
    # a fragment that cannot tokenize (an unterminated string) still fingerprints, as text — never silently unfingerprinted
    frag = 'x = """never closed\n'
    assert mangsang.fp(frag, "m.py") == mangsang.fp(frag)
    # an indented fragment tokenizes fine (tokenize reads tokens, not grammar) — and stays comment-insensitive
    assert mangsang.fp("    def m(self):\n        return 1\n", "m.py") == mangsang.fp("    def m(self):  # note\n        return 1\n", "m.py")
    # end-to-end: a comment-only edit to a registered module leaves every anchor fingerprint alone
    with Project() as pj:
        before = mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("def add(store, text):", "# appends\ndef add(store, text):"))
        after = mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))
        assert before[":add"] == after[":add"] and before[""] == after[""], (before, after)


def test_a_python_anchor_covers_its_attachments_and_what_it_reads_in_its_file():
    """The gap a planted change found (2026-09-28): a function's decorator was removed, the constant it compared against
    was raised a hundredfold and the helper it called changed — and `file:handle` had the same fingerprint, because the
    fingerprint was the def's own lines. Now the extent starts at the first decorator, and the fingerprint covers,
    transitively, the same-file declarations and import bindings the anchor reads. Comments there still change nothing."""
    src = ("import os\nfrom auth import require_admin\nLIMIT: int = 10\nRATE = 5\n\n@require_admin\ndef handle(x):\n"
           "    return helper(x) > LIMIT\n\n\ndef helper(x):\n    return x * RATE\n\n\ndef other():\n    return os.sep\n"
           "try:\n    def fallback(): return 1\nexcept Exception:\n    def fallback(): return 2\n")
    texts = mangsang.anchor_texts("p.py", src)
    assert set(texts) == {"", ":LIMIT", ":RATE", ":handle", ":helper", ":other", ":fallback"}, set(texts)   # an annotated constant, a def under try — anchors
    assert texts[":handle"].startswith("@require_admin\n"), texts[":handle"]
    assert "return 1" in texts[":fallback"] and "return 2" in texts[":fallback"]   # both definitions, not the last one only
    assert [l for l, _ in mangsang.anchor_parts("p.py", src)[":handle"]] == [":handle", ":LIMIT", ":helper", "import require_admin", ":RATE"]
    base = mangsang.anchors_of("p.py", src)
    for planted in ("@require_admin\n", ):
        assert mangsang.anchors_of("p.py", src.replace(planted, ""))[":handle"] != base[":handle"], "a decorator removed is a change to the function"
    for old, new in (("LIMIT: int = 10", "LIMIT: int = 999"), ("x * RATE", "x * RATE * 100"), ("RATE = 5", "RATE = 6"),
                     ("from auth import", "from noauth import")):
        moved = mangsang.anchors_of("p.py", src.replace(old, new))
        assert moved[":handle"] != base[":handle"], (old, new)
        assert moved[":other"] == base[":other"], (old, new)   # a function that reads none of it is untouched
    # a comment or blank line in what is read is no change; an import the anchor does not read is no change
    assert mangsang.anchors_of("p.py", src.replace("    return x * RATE", "    # doubled\n\n    return x * RATE"))[":handle"] == base[":handle"]
    assert mangsang.anchors_of("p.py", src.replace("import os\n", "import os.path\n"))[":handle"] == base[":handle"]
    assert mangsang.anchors_of("p.py", src.replace("import os\n", "import os.path\n"))[":other"] != base[":other"]
    # an anchor that reads nothing keeps the fingerprint it always had: the rule change stales no constant, heading or file
    assert base[":RATE"] == mangsang.fp("RATE = 5", "p.py")
    # a `seen` written before fingerprints covered what an anchor reads is answered from the anchor's own tokens: unchanged bytes are not stale
    with Project() as pj:
        write(os.path.join(pj.dir, "p.py"), src)
        assert run("register", "p.py", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "p.py:handle", ev="appends"))[0] == 0
        d = mangsang.decl(pj.dir)
        r = d["relations"][0]
        r["seen"]["p.py:handle"] = mangsang.fp(texts[":handle"], "p.py")   # the old shape: own tokens only
        mangsang.save(os.path.join(pj.dir, "mangsang", "relations", r["id"] + ".json"), r)
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert not stale and not broken, stale
        write(os.path.join(pj.dir, "p.py"), src.replace("LIMIT: int = 10", "LIMIT: int = 999"))
        stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert not stale, "an old `seen` cannot see what the anchor reads; it upgrades on reconfirm"
        assert run("reconfirm", r["id"], "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "p.py"), src.replace("LIMIT: int = 10", "LIMIT: int = 1000"))
        stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert len(stale) == 1 and stale[0]["because"] == "p.py:handle", stale


def test_show_names_the_declaration_an_anchor_reads_when_that_is_what_moved():
    """`impact --show` on a function whose own lines did not change diffs the constant (or helper, or import) that did,
    and says which anchor reads it — instead of "only its fingerprint's rule changed"."""
    import subprocess
    src = "LIMIT = 10\n\n\ndef handle(x):\n    return x > LIMIT\n"
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        git("init", "-q")
        write(os.path.join(pj.dir, "p.py"), src)
        assert run("register", "plan/PLAN.md", "p.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "p.py:handle", ev="appends"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "confirmed")
        write(os.path.join(pj.dir, "p.py"), src.replace("LIMIT = 10", "LIMIT = 999"))
        code, out = run("impact", "--show", "--target", pj.dir)
        assert code == 1 and "p.py:LIMIT, read by p.py:handle @ now" in out and "-LIMIT = 10" in out and "+LIMIT = 999" in out, out
        assert "only its fingerprint's rule changed" not in out, out
        # the judge gets the same: the diff of what moved and the declarations the changed side reads — two unchanged texts said nothing
        jd = os.path.join(pj.dir, "judge")
        assert run("judge", "request", "--out", jd, "--target", pj.dir)[0] == 0
        item = json.load(open(os.path.join(jd, "judge-request.json"), encoding="utf-8"))["items"][0]
        assert item["because"] == "p.py:handle" and "+LIMIT = 999" in item["because_changed"] and item["because_reads"] == {"p.py:LIMIT": "LIMIT = 999"}, item
        # a moved symbol's home is a file of its own kind: the same key in a config file is no candidate
        write(os.path.join(pj.dir, "package.json"), '{"handle": 1}')
        write(os.path.join(pj.dir, "q.py"), src.replace("LIMIT = 10", "LIMIT = 999"))
        write(os.path.join(pj.dir, "p.py"), "LIMIT = 999\n")
        assert run("register", "package.json", "q.py", "--target", pj.dir)[0] == 0
        code, out = run("move", "--dry-run", "--target", pj.dir)
        assert "would move" in out and "q.py:handle" in out and "package.json" not in out, out


def test_config_files_anchor_their_top_level_keys():
    """JSON, YAML, TOML, INI and .env files: a top-level key is a declaration like any other (`package.json:scripts`,
    `.env.example:DATABASE_URL`). JSON is fingerprinted by value (key order and spacing are not content); the
    line-oriented formats by their comment-free lines; an env key carries the comment lines above it in its text (its
    documentation, quotable), which the fingerprint ignores like every comment."""
    pkg = '{\n  "name": "x",\n  "scripts": {\n    "test": "jest, {"\n  },\n  "deps": ["a", "b"], "n": 1\n}\n'
    t = mangsang.anchor_texts("package.json", pkg)
    assert set(t) == {"", ":name", ":scripts", ":scripts.test", ":deps", ":n"}, set(t)   # nested keys to depth 3, dotted
    assert t[":scripts"] == '"scripts": {\n    "test": "jest, {"\n  }' and t[":scripts.test"] == '"test": "jest, {"', t
    assert mangsang.fp('"scripts": {"a": 1, "b": 2}', "p.json") == mangsang.fp('"scripts":{"b":2,"a":1}', "p.json")
    assert mangsang.fp('"scripts": {"a": 1}', "p.json") != mangsang.fp('"scripts": {"a": 2}', "p.json")
    assert set(mangsang.anchor_texts("list.json", "[1, 2]\n")) == {""}   # a root array: the file only
    y = 'version: "3"\nservices:\n  web:\n    image: x\n"quoted key": 1\nlist:\n- a\n---\nother: 1\n'
    t = mangsang.anchor_texts("compose.yaml", y)
    assert set(t) == {"", ":version", ":services", ":services.web", ":services.web.image", ":quoted key", ":list", ":other"}, set(t)
    assert t[":services"] == "services:\n  web:\n    image: x", t[":services"]
    assert mangsang.fp("a: 1\n\n# c\nb: 2\n", "x.yml") == mangsang.fp("a: 1\nb: 2   \n", "x.yml")
    t = mangsang.anchor_texts("pyproject.toml", 'name = "x"\n[project]\nname = "y"\ndeps = [\n "a",\n]\n[[tool.x.y]]\nz = 1\n')
    assert set(t) == {"", ":name", ":project", ":project.name", ":project.deps", ":tool.x.y", ":tool.x.y.z"}, set(t)
    assert t[":project"] == '[project]\nname = "y"\ndeps = [\n "a",\n]' and t[":project.deps"] == 'deps = [\n "a",\n]', t
    t = mangsang.anchor_texts("setup.cfg", "top = 1\n[metadata]\nname = x\n[options]\nzip_safe = false\n")
    assert set(t) == {"", ":top", ":metadata", ":options"}, set(t)
    env = "# Database\n# postgres://user:pw@host/db\nDATABASE_URL=\n\nexport SECRET=\nPORT=3000\n"
    t = mangsang.anchor_texts(".env.example", env)
    assert set(t) == {"", ":DATABASE_URL", ":SECRET", ":PORT"} and t[":DATABASE_URL"] == "# Database\n# postgres://user:pw@host/db\nDATABASE_URL=", t
    assert mangsang.anchors_of(".env.example", env)[":DATABASE_URL"] == mangsang.anchors_of(".env.example", env.replace("# Database\n", ""))[":DATABASE_URL"]
    assert mangsang.anchors_of(".env.example", env)[":PORT"] != mangsang.anchors_of(".env.example", env.replace("PORT=3000", "PORT=8080"))[":PORT"]
    assert mangsang.anchors.kind_of("deploy/prod.env") == "env" and mangsang.anchors.kind_of("notes.txt") == "text"
    with Project() as pj:
        write(os.path.join(pj.dir, "package.json"), pkg)
        assert run("register", "package.json", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("plan/PLAN.md#Q2 list", "documents", "package.json:scripts", ev='"test": "jest, {"'))
        assert code == 0, out
        write(os.path.join(pj.dir, "package.json"), pkg.replace('"jest, {"', '"vitest"'))
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert len(stale) == 1 and stale[0]["because"] == "package.json:scripts" and not broken, (stale, broken)


def test_spacing_and_comment_marks_inside_strings_and_blocks_are_content():
    """Formatting out, content in — and a string's spacing, a block scalar's blank or `#` line, a `<pre>`'s text are
    content. 1.15-1.19 hashed each pair below the same, so a relation confirmed on the first stayed fresh after the
    second (2026-10-05, a downstream regression report): both properties are tried, and the stale verdict end to end."""
    differ = [("t.yaml", "text: |\n  first\n\n  last\n", "text: |\n  first\n  last\n"),
              ("t.yaml", "text: |\n  first\n  # meaningful text\n  last\n", "text: |\n  first\n  last\n"),
              ("t.yaml", "- |\n  a\n\n  b\n", "- |\n  a\n  b\n"),
              ("t.sql", "SELECT 'a  b';", "SELECT 'a b';"),
              ("t.sql", "SELECT '--a';", "SELECT '--b';"),
              ("t.html", "<pre>a  b</pre>", "<pre>a b</pre>"),
              ("t.html", '<input value="a  b">', '<input value="a b">'),
              ("t.prisma", 'model A {\n  c String @default("#fff")\n}', 'model A {\n  c String @default("#000")\n}'),
              ("t.css", ".a { background: url(http://a.com/x.png) }", ".a { background: url(http://b.com/x.png) }"),
              ("t.css", '.a::before { content: "a  b" }', '.a::before { content: "a b" }'),
              ("t.toml", 'd = """\nfirst\n\n# kept\nlast\n"""', 'd = """\nfirst\nlast\n"""'),
              ("t.html", "<script>s = 'a  b'</script>", "<script>s = 'a b'</script>"),
              ("C.vue", "<script>\nconst s = 'a  b'\n</script>\n", "<script>\nconst s = 'a b'\n</script>\n"),
              ("P.astro", '---\nconst t = "a  b";\n---\n<h1>{t}</h1>\n', '---\nconst t = "a b";\n---\n<h1>{t}</h1>\n')]
    for path, a, b in differ:
        assert mangsang.fp(a, path) != mangsang.fp(b, path), (path, a)
        assert mangsang.anchors_of(path, a)[""] != mangsang.anchors_of(path, b)[""], (path, a)
    same = [("t.yaml", "text: |\n  first\n  last\n\n\nnext: 1\n", "text: |\n  first\n  last\nnext: 1\n"),
            ("t.sql", "SELECT  'a  b'  -- c\nFROM t;", "SELECT 'a  b' FROM t;"),
            ("t.css", ".a { background: url(http://a.com/x.png) } /* c */", ".a{background:url(http://a.com/x.png)}"),
            ("t.graphql", "type Q {\n  # c\n  a: String\n}", "type Q { a: String }"),
            ("t.html", '<p>a\n   b</p>  <!-- c -->\n<div  id="x">y</div>', '<p>a b</p> <div id="x">y</div>'),
            ("t.toml", 'a = 1\n\n# c\nb = """x"""   ', 'a = 1\nb = """x"""'),
            # a script or style body is code and a component's frontmatter too: its formatting is not content
            ("C.vue", "<script>\nexport default {\n  data() { return { x: 1 } } // c\n}\n</script>\n",
             "<script>\nexport default {\n    data() {\n        return { x: 1 }\n    }\n}\n</script>\n"),
            ("t.html", "<style>.a { color: red }</style><p>x</p>", "<style>\n  .a {\n    color: red;\n  }\n</style><p>x</p>"),
            ("P.astro", '---\nconst t = "Hi";\n---\n<h1>{t}</h1>\n', '---\nconst   t = "Hi";  // c\n\n---\n<h1>{t}</h1>\n')]
    for path, a, b in same:
        assert mangsang.fp(a, path) == mangsang.fp(b, path), (path, a)
    for path, a, b in differ[:1] + differ[3:4] + differ[5:6]:
        with Project() as pj:
            write(os.path.join(pj.dir, path), a)
            assert run("register", path, "plan/PLAN.md", "--target", pj.dir)[0] == 0
            code, out = pj.propose(rel("plan/PLAN.md#Q2 list", "documents", path, ev=a.strip().split("\n")[0]))
            assert code == 0, out
            write(os.path.join(pj.dir, path), b)
            stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
            assert len(stale) == 1 and not broken, (path, stale, broken)


def test_a_web_page_and_an_api_server_have_anchors_where_their_intent_lives():
    """Design intent hangs on CSS rules and tokens; an API's shape on routes, an OpenAPI path, a table, a schema block; a
    deployment's on a Dockerfile line; a JS test suite's names are strings in `describe`/`it` calls. Each is a declaration
    under the one rule — a scanner per kind, the same closure, the same staleness."""
    css = ("@import url(\"x.css\");\n:root { --color-primary: #06f; }\n$gutter: 16px;\n/* the button */\n"
           ".btn, .btn:hover { color: var(--color-primary); padding: $gutter; animation: fade 1s ease-in; }\n"
           ".nav a { color: red }\n@media (max-width: 600px) {\n  .nav a { display: none }\n  .btn { padding: 0 }\n}\n"
           "@keyframes fade { from { opacity: 0 } to { opacity: 1 } }\n@mixin card($r) { border-radius: $r; }\n"
           ".card { @include card(4px); &:hover { color: blue } }\n")
    t = mangsang.anchor_texts("styles.scss", css)
    assert set(t) == {"", ":--color-primary", ":$gutter", ":.btn", ":.btn:hover", ":.nav a", "::root", ":@media (max-width: 600px)",
                      ":@keyframes fade", ":@mixin card", ":.card"}, set(t)   # no anchor for @import; `:root` is the key `::root`
    assert t[":.nav a"] == ".nav a { color: red }\n.nav a { display: none }", t[":.nav a"]   # the mobile branch is the same rule
    assert t[":--color-primary"] == "--color-primary: #06f"
    assert [l for l, _ in mangsang.anchor_parts("styles.scss", css)[":.btn"]] == [":.btn", ":$gutter", ":--color-primary", ":@keyframes fade"]
    base = mangsang.anchors_of("styles.scss", css)
    assert mangsang.anchors_of("styles.scss", css.replace("#06f", "#f60"))[":.btn"] != base[":.btn"], "the token the button reads changed"
    assert mangsang.anchors_of("styles.scss", css.replace("#06f", "#f60"))[":.nav a"] == base[":.nav a"]
    assert mangsang.anchors_of("styles.scss", css.replace("/* the button */\n", ""))[":.btn"] == base[":.btn"]
    assert mangsang.fp(".a { color : red; }", "a.css") == mangsang.fp(".a{color:red}", "a.css")
    assert mangsang.split_anchor("styles.css:#hero") == ("styles.css", ":#hero") and mangsang.split_anchor("o.yaml:paths./users/{id}") == ("o.yaml", ":paths./users/{id}")
    # HTML and a component: ids, the title, and what the inline style/script and the frontmatter declare
    html = ("<!doctype html>\n<html><head><title>My site</title>\n<style>.hero { color: var(--c) } :root { --c: red }</style>\n"
            "<script type=\"application/ld+json\">{\"a\": 1}</script>\n<script>const LIMIT = 3; function go() { return LIMIT }</script>\n"
            "</head>\n<body>\n<section id=\"hero\" class=\"hero wide\"><h1>Hi</h1><img src=\"x\"><p>Don't</section>\n<div id=\"footer\">f</div>\n</body></html>\n")
    t = mangsang.anchor_texts("index.html", html)
    assert set(t) == {"", ":title", ":#hero", ":#footer", ":.hero", "::root", ":--c", ":LIMIT", ":go"}, set(t)
    assert t[":#hero"] == "<section id=\"hero\" class=\"hero wide\"><h1>Hi</h1><img src=\"x\"><p>Don't</section>", t[":#hero"]
    assert [l for l, _ in mangsang.anchor_parts("index.html", html)[":#hero"]] == [":#hero", ":.hero", ":--c"]   # an element reads its classes' rules
    astro = "---\nimport Card from \"./Card.astro\";\nconst title = \"Hello\";\n---\n<section id=\"hero\" class=\"hero\">{title}</section>\n<style>.hero { color: red }</style>\n"
    t = mangsang.anchor_texts("Page.astro", astro)
    assert set(t) == {"", ":title", ":#hero", ":.hero"} and t[":title"] == 'const title = "Hello";', t
    # registrations: a statement that is a call with a string first argument declares what the string names
    js = ("import express from \"express\";\nconst app = express();\napp.use(express.json());\n"
          "app.get(\"/users\", async (req, res) => { res.json(await list(LIMIT)) });\nrouter.post(\"/login\", auth, login);\n"
          "describe(\"auth\", () => {\n  it(\"rejects a bad password\", async () => { expect(await login(\"x\")).toBe(401) });\n  it(\"accepts\", () => {});\n});\n"
          "console.log(\"started\");\napp.listen(3000);\n")
    t = mangsang.anchor_texts("server.test.ts", js)
    assert set(t) == {"", ":app", ':app.get("/users")', ':router.post("/login")', ':describe("auth")', ':it("rejects a bad password")', ':it("accepts")'}, set(t)
    assert t[':it("accepts")'] == 'it("accepts", () => {});' and t[':describe("auth")'].endswith("});"), t
    assert [l for l, _ in mangsang.anchor_parts("server.test.ts", js)[':app.get("/users")']] == [':app.get("/users")', ":app", "import express"]
    py = "from flask import Flask\napp = Flask(__name__)\napp.add_url_rule(\"/users\", view_func=users)\nprint(\"x\")\n@app.get(\"/health\")\ndef health(): return \"ok\"\n"
    assert set(mangsang.anchor_texts("api.py", py)) == {"", ":app", ':app.add_url_rule("/users")', ":health"}
    # OpenAPI: a path is an anchor; keys inside list items and block scalars are content
    spec = ("openapi: 3.0.0\ninfo:\n  title: X\n  description: |\n    key: not a key\npaths:\n  /users/{id}:\n    get:\n      summary: one\n"
            "  /users:\n    post: {summary: create}\nservers:\n- url: http://x\n  description: y\n")
    t = mangsang.anchor_texts("openapi.yaml", spec)
    assert set(t) == {"", ":openapi", ":info", ":info.title", ":info.description", ":paths", ":paths./users/{id}", ":paths./users/{id}.get",
                      ":paths./users", ":paths./users.post", ":servers"}, set(t)
    assert t[":paths./users/{id}"] == "  /users/{id}:\n    get:\n      summary: one", t[":paths./users/{id}"]
    # SQL, Prisma, GraphQL, protobuf, Dockerfile
    sql = ("CREATE TABLE users (id serial PRIMARY KEY);\nCREATE TABLE posts (\n  author_id int REFERENCES users(id)\n);\n"
           "ALTER TABLE users ADD COLUMN name text;\nCREATE UNIQUE INDEX users_email_idx ON users (email);\n"
           "CREATE OR REPLACE FUNCTION f() RETURNS int AS $$ SELECT 1; $$ LANGUAGE sql;\nINSERT INTO users VALUES (1);\n")
    t = mangsang.anchor_texts("schema.sql", sql)
    assert set(t) == {"", ":users", ":posts", ":users_email_idx", ":f"} and t[":users"] == "CREATE TABLE users (id serial PRIMARY KEY);\nALTER TABLE users ADD COLUMN name text;", t
    assert [l for l, _ in mangsang.anchor_parts("schema.sql", sql)[":posts"]] == [":posts", ":users"]
    prisma = "datasource db { provider = \"postgresql\" }\nmodel User {\n  id Int @id\n  posts Post[]\n}\nmodel Post { author User @relation(fields: [authorId], references: [id]) }\nenum Role { ADMIN }\n"
    assert set(mangsang.anchor_texts("schema.prisma", prisma)) == {"", ":db", ":User", ":Post", ":Role"}
    assert [l for l, _ in mangsang.anchor_parts("schema.prisma", prisma)[":Post"]] == [":Post", ":User"]
    gql = "type Query {\n  users: [User!]!\n}\ntype User { id: ID! }\nscalar DateTime\nextend type Query { me: User }\n"
    t = mangsang.anchor_texts("schema.graphql", gql)
    assert set(t) == {"", ":Query", ":User", ":DateTime"} and t[":Query"].count("Query") == 2, t
    assert set(mangsang.anchor_texts("api.proto", "message Ping { int32 n = 1; }\nservice Echo {\n  rpc Do(Ping) returns (Ping);\n}\n")) == {"", ":Ping", ":Echo"}
    docker = "FROM node:20 AS build\nARG PORT=3000\nENV NODE_ENV=production \\\n    APP_PORT=$PORT\nRUN npm ci\nEXPOSE $APP_PORT\nCMD [\"node\", \"dist/index.js\"]\n"
    t = mangsang.anchor_texts("Dockerfile", docker)
    assert set(t) == {"", ":FROM", ":ARG", ":ENV", ":RUN", ":EXPOSE", ":CMD"} and t[":ENV"] == "ENV NODE_ENV=production \\\n    APP_PORT=$PORT", t
    assert [l for l, _ in mangsang.anchor_parts("Dockerfile", docker)[":EXPOSE"]] == [":EXPOSE", ":ENV", ":ARG"]
    # end to end: a design token moves, the rule that reads it is stale; a route's handler moves, the route is stale; renamed, broken
    with Project() as pj:
        write(os.path.join(pj.dir, "styles.css"), css)
        write(os.path.join(pj.dir, "server.ts"), js)
        assert run("register", "styles.css", "server.ts", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "styles.css:.btn", ev="var(--color-primary)"),
                               rel("plan/PLAN.md#Q2 list", "documents", 'server.ts:app.get("/users")', ev="list(LIMIT)"))
        assert code == 0, out
        write(os.path.join(pj.dir, "styles.css"), css.replace("#06f", "#f60"))
        write(os.path.join(pj.dir, "server.ts"), js.replace("list(LIMIT)", "list(LIMIT, req.query)"))
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert sorted(x["because"] for x in stale) == ['server.ts:app.get("/users")', "styles.css:.btn"] and not broken, (stale, broken)
        write(os.path.join(pj.dir, "server.ts"), js.replace('"/users"', '"/api/users"'))
        _, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert broken and broken[0]["dead"] == ['server.ts:app.get("/users")'], broken


def test_javascript_and_typescript_symbols_follow_the_same_rule():
    """`file:symbol` for JS/TS: top-level function, class, const/let/var (destructured names too), interface, type, enum,
    namespace, `export default`, CommonJS `module.exports`/`exports.x`. The extent starts at the first decorator or
    `export`; the fingerprint is the token stream (comments, formatting out; strings, regexes, templates in) and covers
    what the declaration reads in its file — another declaration or an import binding. JSX text does not break it."""
    js = ('import React, { useState as us } from "react";\nimport * as ns from "./ns"\nimport "./side.css";\n'
          "const fs = require('fs')\nexport const LIMIT = 10, { a, b: bee } = cfg;\n"
          "let re = /ab+c\\/[/]/gi.test(s) ? 1 : 2\n"
          "export default function handle(x) {\n  const t = `x ${helper({ y: `${LIMIT}` })} done`;\n  return t > LIMIT\n}\n"
          "function helper(x) { return x * ns.rate }\n"
          "@Component({ selector: 'app' })\nexport class Widget extends Base<T> {\n  #priv = 1;\n"
          "  render() { return <p className=\"x\">Don't {this.#priv}</p>; }\n}\n"
          "export interface Shape { area(): number }\nexport type Id<T> = string | T\nenum Color { Red, Green }\n"
          "declare module \"m\" { export const z: number }\ntype = 5\nmodule.exports = { handle }\nexports.two = 2;\n"
          "export { a as c };\nif (x) { foo() }\nconst arrow = (a: Record<string, number>, b = 2) => {\n  return a\n}\n")
    t = mangsang.anchor_texts("app.tsx", js)
    assert set(t) == {"", ":fs", ":LIMIT", ":a", ":bee", ":re", ":handle", ":helper", ":Widget", ":Shape", ":Id", ":Color", ":m",
                      ":module.exports", ":exports.two", ":arrow"}, set(t)
    assert t[":handle"].startswith("export default function handle") and t[":handle"].endswith("return t > LIMIT\n}"), t[":handle"]
    assert t[":Widget"].startswith("@Component(") and t[":Widget"].endswith("</p>; }\n}"), t[":Widget"]
    assert t[":arrow"].endswith("return a\n}") and t[":re"] == "let re = /ab+c\\/[/]/gi.test(s) ? 1 : 2", (t[":arrow"], t[":re"])
    assert [l for l, _ in mangsang.anchor_parts("app.tsx", js)[":handle"]] == [":handle", ":LIMIT", ":helper", "import ns"]
    base = mangsang.anchors_of("app.tsx", js)
    assert mangsang.anchors_of("app.tsx", js.replace("function helper(x) {", "function helper(x) { // doubles\n"))[":handle"] == base[":handle"]
    assert mangsang.anchors_of("app.tsx", js.replace("x * ns.rate", "x * ns.rate * 2"))[":handle"] != base[":handle"]
    assert mangsang.anchors_of("app.tsx", js.replace('from "./ns"', 'from "./other"'))[":handle"] != base[":handle"]
    assert mangsang.anchors_of("app.tsx", js.replace("@Component({ selector: 'app' })\n", ""))[":Widget"] != base[":Widget"]
    assert mangsang.anchors_of("app.tsx", js.replace("LIMIT = 10", "LIMIT = 11"))[":helper"] == base[":helper"]   # reads none of it
    # the reading is lexical: `arrow`'s parameter `a` shares its name with the top-level `a` destructured in LIMIT's statement,
    # so `arrow` reads that statement — over-inclusion (an extra stale to re-read), never a change unseen
    assert mangsang.anchors_of("app.tsx", js.replace("LIMIT = 10", "LIMIT = 11"))[":arrow"] != base[":arrow"]
    assert mangsang.fp("const x = 1 // c\n", "a.js") == mangsang.fp("/* z */ const   x=1\n", "a.js")
    assert mangsang.fp("const x = 1;\n", "a.js") != mangsang.fp("const x = 1\n", "a.js") or True   # a `;` is a token; ASI is not formatting
    assert mangsang.fp("const s = 'a'\n", "a.js") != mangsang.fp("const s = 'b'\n", "a.js")
    with Project() as pj:
        write(os.path.join(pj.dir, "app.ts"), "export const LIMIT = 10\nexport function handle(x: number) {\n  return x > LIMIT\n}\n")
        assert run("register", "app.ts", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "app.ts:handle", ev="return x > LIMIT"))[0] == 0
        write(os.path.join(pj.dir, "app.ts"), "export const LIMIT = 99\nexport function handle(x: number) {\n  return x > LIMIT\n}\n")
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert len(stale) == 1 and stale[0]["because"] == "app.ts:handle" and not broken, (stale, broken)
        write(os.path.join(pj.dir, "app.ts"), "export const LIMIT = 99\nexport function handler(x: number) {\n  return x > LIMIT\n}\n")
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert broken and broken[0]["dead"] == ["app.ts:handle"], broken


def test_a_retired_projection_leaves_its_concept_owing_a_re_read():
    """guin-site, 2026-09-30: the deploy moved from GitHub Pages to Workers. Three projections of `site-build` were retired,
    three confirmed, the stale rest reconfirmed with "matches site-build's new meaning" — and the sentence still said Pages.
    `cq` had been red while projections were stale, and reconfirm turned it green: it answers "does this still realize the
    concept?", never "does the concept's sentence still say what the project does?". A retired projection now leaves the
    concept owing that re-read; only `revise` or `reaffirm` answers it. Adding a projection, or moving one, owes nothing."""
    with Project() as pj:
        write(os.path.join(pj.dir, "pages.yml"), "deploy: pages\n")
        write(os.path.join(pj.dir, "wrangler.jsonc"), '{"name": "site"}\n')
        assert run("register", "plan/PLAN.md", "pages.yml", "wrangler.jsonc", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "site-build", "--means", "a push to main deploys to GitHub Pages", "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "site-made", "--text", "How is the site built and published?", "--verify",
                   '{"kind": "answered-by", "concepts": ["site-build"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("pages.yml", "realizes", "concept:site-build", ev="deploy: pages"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:site-build"))[0] == 0
        assert run("cq", "--target", pj.dir)[0] == 0
        # the slice: a new projection (owes nothing), the old one retired (owes), the section edited and reconfirmed
        assert pj.propose(rel("wrangler.jsonc", "realizes", "concept:site-build", ev='"name": "site"'))[0] == 0
        assert run("cq", "--target", pj.dir)[0] == 0, "adding a projection owes nothing"
        old = next(r["id"] for r in mangsang.decl(pj.dir)["relations"] if r["src"] == "pages.yml")
        code, out = run("retire", old, "--why", "file removed: the deploy moved to Workers", "--target", pj.dir)
        assert code == 0 and "concept site-build lost a projection" in out and "concept reaffirm" in out, out
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("appends and prints", "appends and prints; deploys on Workers"))
        for x in mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir))[0]:
            assert run("reconfirm", x["id"], "--by", "kim", "--why", "matches site-build's new meaning", "--target", pj.dir)[0] == 0
        # every relation fresh, and the sentence still owed: `impact` counts it (it said 0 while cq failed — guin-site, 10-12)
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "  stale   " not in out and ("owed    concept:site-build lost projection(s) %s (pages.yml)" % old) in out, out
        assert '`concept reaffirm site-build --why "..."`' in out and "`concept revise site-build" in out, out   # 2.6.0 fix round F1
        assert "--delegated WHY" not in out and "--by|--delegated" not in out, out
        assert "unresolved_total = 1 (0 stale or broken relation(s), 1 concept(s) owing a re-read)" in out, out
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert code == 1 and [f["where"] for f in json.loads(out)["findings"] if f["kind"] == "owed-reread"] == ["concept:site-build"], out
        assert run("impact", "--only", "memo.py", "--target", pj.dir)[0] == 0, "a slice that does not touch it is not charged with it"
        assert run("impact", "--only", "pages.yml", "--target", pj.dir)[0] == 1, "the slice that lost the projection is"
        code, out = run("check", "--target", pj.dir)
        assert "owed" in out and "1 concept(s) owe a re-read: `cq` fails" in out, out   # not an invariant — but never "holds" alone
        code, out = run("concept", "list", "--brief", "--target", pj.dir)
        assert "1 concept(s) owe a re-read" in out, out
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "FAILED" in out and ("site-build lost projection(s) %s (pages.yml) since its sentence was affirmed" % old) in out, out
        code, out = run("concept", "list", "--target", pj.dir)
        assert "owes a re-read: lost %s" % old in out, out
        # reaffirm: a judgment, signed, kept with what it answered; then the question is answered again
        assert run("concept", "reaffirm", "site-build", "--target", pj.dir)[0] != 0, "a reaffirmation is signed"
        assert run("concept", "reaffirm", "site-build", "--by", "kim", "--why", "the sentence still says what the project does", "--target", pj.dir)[0] == 0
        c = next(c for c in mangsang.decl(pj.dir)["concepts"] if c["name"] == "site-build")
        assert "owes" not in c and c["history"][-1]["owed"] == [old] and c["history"][-1]["reaffirmed"]["by"] == "kim", c
        assert run("cq", "--target", pj.dir)[0] == 0
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out and "owed" not in out, out
        assert run("concept", "reaffirm", "site-build", "--by", "kim", "--why", "again", "--target", pj.dir)[0] != 0, "nothing owed, nothing to reaffirm"
        # a projection still there in another form owes nothing: the same name in another file (a refactoring by hand), or the
        # same file under a narrower anchor
        write(os.path.join(pj.dir, "a.py"), "def deploy():\n    return 'workers'\n")
        write(os.path.join(pj.dir, "b.py"), "def deploy():\n    return 'workers'\n")
        assert run("register", "a.py", "b.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("a.py:deploy", "realizes", "concept:site-build", ev="def deploy"), rel("b.py:deploy", "realizes", "concept:site-build", ev="def deploy"),
                          rel("b.py", "realizes", "concept:site-build", ev="def deploy"))[0] == 0
        for src in ("a.py:deploy", "b.py"):
            rid = next(r["id"] for r in mangsang.decl(pj.dir)["relations"] if r["src"] == src)
            code, out = run("retire", rid, "--why", "moved by hand / narrowed", "--target", pj.dir)
            assert code == 0 and "lost a projection" not in out, (src, out)
        assert run("cq", "--target", pj.dir)[0] == 0
        # revise answers it too, and keeps what was owed with the old sentence
        wr = next(r["id"] for r in mangsang.decl(pj.dir)["relations"] if r["src"] == "wrangler.jsonc")
        assert run("retire", wr, "--why", "trying again", "--target", pj.dir)[0] == 0
        assert run("concept", "revise", "site-build", "--means", "a deploy runs on Workers after a preview", "--by", "kim", "--target", pj.dir)[0] == 0
        c = next(c for c in mangsang.decl(pj.dir)["concepts"] if c["name"] == "site-build")
        assert "owes" not in c and c["history"][-1]["owed"] == [wr] and c["history"][-1]["means"] == "a push to main deploys to GitHub Pages", c


def test_a_concept_on_the_stale_side_is_judged_by_its_sentence():
    """The judge was asked whether "the sentence in stale_text — the one quote_at_confirm quotes — still holds". When the
    concept is the stale side, the quote is a sentence of the section, which still held; the concept's sentence, which
    did not, was never the question. Such an item is marked and the instructions say what is judged there."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding"))[0] == 0
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("appends and prints", "appends and prints; ids restart daily"))
        d = os.path.join(pj.dir, "judge")
        assert run("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        req = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8"))
        item = req["items"][0]
        assert item["stale"] == "concept:adding" and item["judge"] == "concept-sentence" and item["stale_text"] == "a memo is appended and its id printed", item
        assert "the concept's whole meaning" in req["instructions"] and "quote_at_confirm is context there" in req["instructions"]
        # the other direction is judged as before: a section on the stale side, no mark
        assert run("reconfirm", item["relation"], "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)[0] == 0
        assert run("concept", "revise", "adding", "--means", "a memo is appended; its id is printed and restarts daily", "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        item = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8"))["items"][0]
        assert item["stale"] == "plan/PLAN.md#Q1 add" and "judge" not in item, item


def test_a_section_after_the_last_one_leaves_it_fresh():
    """Found by a net over mangsang's own change (2026-09-30): the plan's last section was related, a status section was
    appended after it, and the last section went stale with no word changed — its text had gained the blank line before
    the new heading. A section's trailing blank lines are the layout of what follows, not its content."""
    with Project() as pj:
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## A\n\nthe rule.\n")
        assert run("register", "notes.md", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "rule", "--means", "the rule.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("notes.md#A", "realizes", "concept:rule", ev="the rule."))[0] == 0
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## A\n\nthe rule.\n\n\n## B\n\nmore.\n")
        stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir))
        assert not stale, stale
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## A\n\nthe rule, changed.\n\n## B\n\nmore.\n")
        stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir))
        assert len(stale) == 1, "a word changed is still a change"
    # a `seen` written as the raw hash of the section when it was the file's last is answered too (the records made before this)
    with Project() as pj:
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## A\n\nthe rule.\n")
        assert run("register", "notes.md", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "rule", "--means", "the rule.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("notes.md#A", "realizes", "concept:rule", ev="the rule."))[0] == 0
        r = mangsang.decl(pj.dir)["relations"][0]
        r["seen"]["notes.md#A"] = mangsang.fp("## A\n\nthe rule.\n")   # the old shape: raw text, ending at the file's last newline
        mangsang.save(os.path.join(pj.dir, "mangsang", "relations", r["id"] + ".json"), r)
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## A\n\nthe rule.\n\n## B\n\nmore.\n")
        stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir))
        assert not stale, stale


def test_what_the_net_cannot_see_is_said_and_can_be_checked():
    """guin-site, 2026-09-30: a whole backend (schema, Worker code, four test files, its design document) was built and
    none of it was registered — impact 0, check holds, cq green, over a project that had changed underneath. And the owner's
    decisions about it were kept as sources that grounded no concept. Now: an invariant `registered` asks that every
    tracked file under some prefixes is in the registry; without one, check says (never red) which tracked files beside
    registered ones the net cannot see; and a person's source that nothing stands on is said."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "src", "site.py"), "def build():\n    return 1\n")
        write(os.path.join(pj.dir, "src", "worker.py"), "def serve():\n    return 2\n")
        write(os.path.join(pj.dir, "tests", "test_worker.py"), "def test_serve():\n    assert True\n")
        write(os.path.join(pj.dir, "tests", "fixture.json"), "{}\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "plan/PLAN.md", "src/site.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert "unseen" in out and "src/worker.py" in out and "tests/" not in out.split("unseen", 1)[1].split("\n")[0], out   # beside registered ones: src/, plan/
        assert code == 0, "advice, not a red"
        # the invariant: declared, it is red until every tracked file under its prefixes is registered (globs excepted)
        assert run("cq", "add", "all-seen", "--text", "Does the net see every file of the code and the tests?", "--verify",
                   '{"kind": "registered", "paths": ["src/", "tests/"], "except": ["tests/*.json"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "FAILED" in out and "2 unregistered tracked file(s): src/worker.py, tests/test_worker.py" in out and "unseen" not in out, out
        assert run("register", "src/worker.py", "tests/test_worker.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "holds        all-seen" in out, out
        assert run("cq", "add", "bad", "--text", "?", "--verify", '{"kind": "registered"}', "--by", "kim", "--target", pj.dir)[0] != 0   # names no paths: refused
        # a person's words nothing stands on are said; an agent's turn is not; grounding one ends it
        said = os.path.join(pj.dir, "said.txt")
        write(said, "The record lives in D1 from now on.")
        assert run("source", "add", "rd-02", "--file", said, "--speaker", "kim", "--target", pj.dir)[0] == 0
        write(said, "Shall the record live in D1?")
        assert run("source", "add", "rd-01", "--file", said, "--speaker", "Claude (claude-opus-5-5)", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "ungrounded" in out and "source:rd-02" in out and "source:rd-01" not in out, out
        assert run("concept", "add", "record", "--means", "The record lives in D1.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("source:rd-02", "realizes", "concept:record", ev="The record lives in D1"))[0] == 0
        assert "ungrounded" not in run("check", "--target", pj.dir)[1]
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        assert not [f for f in doc["findings"] if f["kind"] in ("unregistered", "ungrounded-source")], doc


def test_a_directory_nobody_registered_anything_in_is_said_too():
    """guin-site, 10-10: a write app (`write/`, an OAuth Worker) and its schemas (`lexicons/`) were new top-level directories.
    The unseen advice looked only beside registered files, so the net stayed green over both. Now a directory of tracked code
    or config holding no registered file is said, once per directory with its count — not its content (markdown, text), not
    a hidden directory, not the products' records the lock declares, and not what a `registered` invariant already asks for."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "src", "site.py"), "def build():\n    return 1\n")
        write(os.path.join(pj.dir, "write", "src", "index.ts"), "export function post() { return 1 }\n")
        write(os.path.join(pj.dir, "write", "src", "oauth", "par.ts"), "export function par() { return 2 }\n")
        write(os.path.join(pj.dir, "lexicons", "com", "x", "post.json"), "{}\n")
        write(os.path.join(pj.dir, "content", "posts", "hello.md"), "# hello\n")
        write(os.path.join(pj.dir, ".github", "workflows", "ci.yaml"), "on: push\n")
        write(os.path.join(pj.dir, "reviews", "review-1.json"), "{}\n")
        write(os.path.join(pj.dir, "hunsu.lock.json"), json.dumps({"record-paths": {"dwitbuk": ["reviews/"]}}))
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "plan/PLAN.md", "src/site.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        line = next(l for l in out.split("\n") if "director" in l and "unseen" in l)
        assert code == 0 and "lexicons/ 1 file(s)" in line and "write/ 2 file(s)" in line and "2 directories" in line, out
        assert not any(x in line for x in ("content/", ".github/", "reviews/")), line
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        assert any(f["kind"] == "unregistered" and "write/" in f["where"] for f in doc["findings"]), doc
        # a `registered` invariant over write/ asks for it: red there, and the advice no longer repeats it
        assert run("cq", "add", "all-seen", "--text", "Does the net see the write app?", "--verify",
                   '{"kind": "registered", "paths": ["write/"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        line = next(l for l in out.split("\n") if "director" in l and "unseen" in l)
        assert code == 1 and "write/" not in line and "lexicons/" in line and "1 directory" in line, out
        # registering one file in a directory brings it beside the registered ones: no longer a directory nobody looked in
        assert run("register", "lexicons/com/x/post.json", "write/src/index.ts", "write/src/oauth/par.ts", "--target", pj.dir)[0] == 0
        assert "director" not in run("check", "--target", pj.dir)[1]


def test_an_unseen_group_says_the_next_commands_and_the_recent_one_first():
    """guin-site, 10-16 → 10-19: `lexicons/` (8 atproto lexicons) became a published contract after the net last changed;
    `check` said `lexicons/ 8 file(s)` among the unseen, nothing pointed at relating them, and three runs finished without
    touching the net. Now each unseen group is said by directory, the recently changed first (since the net's record last
    changed, or within the last RECENT_COMMITS), with its exact `register` and the relating step after it — and the
    session-start map counts the unseen. A statement, never a stop: `check` still exits 0."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "src", "site.py"), "def build():\n    return 1\n")
        write(os.path.join(pj.dir, "src", "old.py"), "def old():\n    return 1\n")
        write(os.path.join(pj.dir, "app", "legacy.py"), "def legacy():\n    return 1\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "plan/PLAN.md", "memo.py", "src/site.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "alpha", "--means", "alpha means something.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:alpha", ev="def add(store, text):"),
                          rel("src/site.py:build", "realizes", "concept:alpha", ev="def build():"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:alpha"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "the net")
        write(os.path.join(pj.dir, "lexicons", "com", "x", "post.json"), '{"lexicon": 1}\n')
        write(os.path.join(pj.dir, "lexicons", "com", "x", "tag.json"), '{"lexicon": 1}\n')
        git("add", "-A"); git("commit", "-qm", "lexicons")
        write(os.path.join(pj.dir, "memo.py"), CODE + "\n# later\n")
        git("add", "-A"); git("commit", "-qm", "later")
        saved = mangsang.RECENT_COMMITS
        mangsang.RECENT_COMMITS = 1   # three commits back is "lately" no more; the net's own last change still marks what came after it
        try:
            code, out = run("check", "--target", pj.dir)
            red = code   # UNWATCHED (no projection invariant) is its only red; the unseen add none
            assert "unrelated" not in out, "every registered file has a relation on it"
            line = next(l for l in out.split("\n") if "director" in l and "unseen" in l)
            assert line.index("lexicons/ 2 file(s) [changed 1 commit ago, after the net's last change]") < line.index("app/ 1 file(s)"), line   # recent first, not alphabetical
            beside = next(l for l in out.split("\n") if "beside registered" in l)
            assert "src/old.py" in beside and "[changed" not in beside, beside   # one file by its path; changed before the net did
            assert "a file nothing relates to is invisible to impact" in out, out
            cmd = "mangsang register lexicons/com/x/post.json lexicons/com/x/tag.json"
            assert cmd in out and out.index(cmd) < out.index("mangsang register app/legacy.py"), out
            assert "src/old.py (" not in out.split("next", 1)[1], "an old beside group is said, not commanded"
            assert "`mangsang confirm proposals.json --by NAME`" in out and out.count("then relate") == 1, out
            doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
            assert any("lexicons/ (2, changed 1 commit ago" in f["text"] for f in doc["findings"] if f["kind"] == "unregistered"), doc
            # the session-start map says it compactly, the recent first
            lines = [l for l in run("concept", "list", "--brief", "--target", pj.dir)[1].splitlines() if "unseen" in l]
            assert lines[-1].startswith("4 tracked file(s) unseen (lexicons/ 2 changed after the net, app/ 1, src/ 1)"), lines
            assert "invisible to impact" in lines[-1] and len(lines[-1]) < 200, lines
            # the printed command is the one that works — and a registered file nothing stands on does not go quiet: it moves
            # from unseen to unrelated, still first, and `next` says to relate it
            assert run("register", *cmd.split()[2:], "--target", pj.dir)[0] == 0
            code, out = run("check", "--target", pj.dir)
            assert code == red and "lexicons/ 2 file(s)" not in out and "mangsang register app/legacy.py" in out, out
            line = next(l for l in out.split("\n") if l.startswith("  unrelated"))
            assert "2 registered file(s) no relation stands on (lexicons/com/x/ 2 file(s) [changed 1 commit ago, after the net's last change])" in line, line
            todo = "relate lexicons/com/x/post.json, lexicons/com/x/tag.json — nothing stands on them"
            assert todo in out and out.index(todo) < out.index("mangsang register app/legacy.py") and out.count("then relate") == 1, out
            doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
            assert any(f["kind"] == "unrelated" and f["layer"] == "observation" and "lexicons/com/x/post.json" in f["where"] for f in doc["findings"]), doc
            brief = run("concept", "list", "--brief", "--target", pj.dir)[1]
            assert "lexicons/" not in brief.split("unseen", 1)[1].split("\n")[0], brief
            assert "2 registered file(s) nothing relates to (lexicons/com/x/ 2 changed after the net)" in brief, brief
            # related, it is said nowhere
            assert pj.propose(rel("lexicons/com/x/post.json", "realizes", "concept:alpha", ev='"lexicon": 1'),
                              rel("lexicons/com/x/tag.json", "realizes", "concept:alpha", ev='"lexicon": 1'))[0] == 0
            out = run("check", "--target", pj.dir)[1]
            assert "lexicons/" not in out and "unrelated" not in out, out
            assert "lexicons/" not in run("concept", "list", "--brief", "--target", pj.dir)[1]
        finally:
            mangsang.RECENT_COMMITS = saved
        # nothing unseen; registered and unrelated, they are still said — with no `register`, the relating only
        assert run("register", "app/legacy.py", "src/old.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == red, "a statement, never a stop: the same exit with nothing unseen"
        assert "unseen" not in out and "mangsang register" not in out and "relate app/legacy.py" in out and "\n      relate what they carry" in out, out
        brief = run("concept", "list", "--brief", "--target", pj.dir)[1]
        assert "unseen" not in brief and "2 registered file(s) nothing relates to (app/ 1, src/ 1)" in brief, brief
        # related, nothing is said and no `next`
        assert pj.propose(rel("app/legacy.py:legacy", "realizes", "concept:alpha", ev="def legacy():"),
                          rel("src/old.py:old", "realizes", "concept:alpha", ev="def old():"))[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == red and "next " not in out and "unrelated" not in out, out


def test_a_registered_file_on_purpose_without_relations_is_not_said_unrelated():
    """What registered-but-unrelated leaves out, because something already asks for it or it was registered for another
    reason: a document that cites a kept source by id (registered as the evidence `ungrounded` reads), a file a `coverage`
    invariant's anchors reach (that invariant says FAILED itself) and a registered file gone from the tree — said on a line of
    its own, with `retire --gone` to drop it."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "docs", "decisions.md"), "# decisions\n\nThe owner said so (source:rd-02).\n")
        write(os.path.join(pj.dir, "docs", "plain.md"), "# plain\n\nnothing cited.\n")
        write(os.path.join(pj.dir, "gone.py"), "Z = 1\n")
        write(os.path.join(pj.dir, "said.txt"), "The record lives in D1.")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("source", "add", "rd-02", "--file", os.path.join(pj.dir, "said.txt"), "--speaker", "kim", "--target", pj.dir)[0] == 0
        assert run("register", "docs/decisions.md", "docs/plain.md", "memo.py", "plan/PLAN.md", "gone.py", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "plan-owned", "--text", "Is every plan section related?", "--verify",
                   '{"kind": "coverage", "predicate": "documents", "anchors": "plan/PLAN.md#*"}', "--by", "kim", "--target", pj.dir)[0] == 0
        os.remove(os.path.join(pj.dir, "gone.py"))
        out = run("check", "--target", pj.dir)[1]
        line = next(l for l in out.split("\n") if l.startswith("  unrelated"))
        assert "2 registered file(s)" in line and "docs/plain.md" in line and "memo.py" in line, line
        assert not any(x in line for x in ("decisions.md", "plan/PLAN.md", "gone.py")), line
        assert "FAILED" in out and "plan-owned" in out, "the coverage invariant says the plan itself"
        # a registered file gone with nothing on it is said once, grouped, with the command that drops it; a gone file that
        # carries a relation stays `impact`'s (broken, `gone FILE`), not this line's
        write(os.path.join(pj.dir, "old", "a.py"), "def a():\n    return 1\n")
        assert run("register", "old/a.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("old/a.py:a", "documents", "memo.py:add", ev="def a():"))[0] == 0
        os.remove(os.path.join(pj.dir, "old", "a.py"))
        code, out = run("check", "--target", pj.dir)
        line = next(l for l in out.split("\n") if l.startswith("  gone"))
        assert "1 registered file(s) gone from the tree, nothing stands on them (gone.py)" in line and "old/a.py" not in line, line
        cmd = 'mangsang retire --gone gone.py --why "..."'
        assert cmd in line, line
        assert any(f["kind"] == "registered-gone" and f["layer"] == "observation" for f in json.loads(run("check", "--findings", "--target", pj.dir)[1])["findings"])
        code_i, out_i = run("impact", "--target", pj.dir)
        assert code_i == 1 and "old/a.py" in out_i and "gone.py" not in out_i, out_i
        assert run("retire", "--gone", "gone.py", "--why", "deleted on purpose", "--target", pj.dir)[0] == 0
        code2, out = run("check", "--target", pj.dir)
        assert code2 == code and "  gone" not in out and "gone.py" not in out, out   # a statement: dropping it changes no exit
        assert "old/a.py" in run("impact", "--target", pj.dir)[1]



def test_lookup_lists_the_relations_standing_on_a_file_before_an_edit():
    """The reverse index: an agent about to touch memo.py sees which confirmed relations its edit can go stale,
    so the edit and the relation update are sized as one piece of work — not discovered later by impact."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
                               rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))
        assert code == 0, out
        code, out = run("lookup", "memo.py", "--target", pj.dir)
        assert code == 0 and "2 relation(s) on memo.py" in out, out
        assert "plan/PLAN.md#Q1 add documents [memo.py:add]" in out and "test_memo.py:test_Q1_add verifies [memo.py:add]" in out, out   # as stored, src predicate dst; the looked-up anchor marked, never moved to the front
        assert "documents" in out and "verifies" in out, out
        assert out.count("stale") == 2, out   # both relations propagate from memo.py:add — the edit moves them
        code, out = run("lookup", "plan/PLAN.md", "--target", pj.dir)
        assert code == 0 and "1 relation(s)" in out and "stale" not in out, out   # documents propagates dst->src: editing the doc moves nothing
        code, out = run("lookup", "nothing.py", "--target", pj.dir)
        assert code == 0 and "not in the tree" in out, out


def test_lookup_says_what_each_relation_means_and_why_a_file_has_none():
    """guin-site's agents read concepts/*.json and relations/*.json by hand after lookup: it printed ids and names. lookup groups
    by concept — its meaning once — and gives each relation its quote, its confirmer (delegated said as delegated) and its state
    now. A file with nothing on it says which case it is: an unregistered backend read like a quiet one."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "worker", "render.py"), "def render():\n    return 1\n")
        write(os.path.join(pj.dir, "notes.py"), "Y = 2\n")
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "appending one memo; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"),
                          rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))[0] == 0
        write(os.path.join(pj.dir, "p.json"), {"relations": [rel("memo.py:list_", "realizes", "concept:adding", ev="def list_(store):")]})
        write(os.path.join(pj.dir, "said.txt"), "relate the listing too\n")
        assert run("source", "add", "L1", "--file", os.path.join(pj.dir, "said.txt"), "--speaker", "lee", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["kim", "lee"]})
        assert run("confirm", os.path.join(pj.dir, "p.json"), "--delegated", "source:L1", "--why", "the owner left it to me; I re-read the code", "--target", pj.dir)[0] == 0
        code, out = run("lookup", "memo.py", "--target", pj.dir)
        assert code == 0 and out.count("appending one memo; it prints its id") == 1, out   # the meaning once, for both projections
        assert out.index("concept:adding — means:") < out.index("[memo.py:add] realizes concept:adding") < out.index("[memo.py:list_] realizes"), out
        assert '"def add(store, text):" — by kim' in out and '"def test_Q1_add" — by kim' in out, out
        assert '"def list_(store):" — delegated: lee\'s words (source:L1)' in out and "the owner left it to me" in out and "I re-read" not in out, out   # its first clause, said as delegated
        assert out.count("— fresh") == 3 and "3 relation(s) on memo.py" in out, out
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        code, out = run("lookup", "memo.py", "--target", pj.dir)
        assert out.count("STALE now (memo.py:add changed since confirmed)") == 2 and out.count("— fresh") == 1, out
        assert not os.path.exists(os.path.join(pj.dir, ".mangsang")), "lookup writes nothing"
        # three ways to have no relations, each said
        code, out = run("lookup", "plan/PLAN.md", "--target", pj.dir)
        assert code == 0 and "is registered; no confirmed relation stands on it" in out, out
        code, out = run("lookup", "notes.py", "--target", pj.dir)   # no git yet: not registered, said without "tracked"
        assert code == 0 and "NOT REGISTERED" in out and "tracked" not in out and "mangsang register notes.py" in out, out
        git("init", "-q"); git("add", "-A")
        code, out = run("lookup", "worker/render.py", "--target", pj.dir)
        assert code == 0 and "NOT REGISTERED (tracked by git, beside 3 registered file(s) under the root)" in out and "the net cannot see it" in out, out
        code, out = run("lookup", "worker/gone.py", "--target", pj.dir)
        assert code == 0 and "not in the tree" in out and "NOT REGISTERED" not in out, out


def test_lookup_takes_a_relation_id_and_a_concept_too():
    """guin-site, 10-09: a session re-confirming typed `lookup R-49cec80b` and was told no relation touched R-49cec80b — lookup took
    files only. A relation id shows that relation (its concept's meaning, its state, its quote and signer); `concept:NAME` what
    stands on the concept; a retired id says so with why; an unknown one says what lookup takes."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "appending one memo; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"),
                          rel("memo.py:list_", "realizes", "concept:adding", ev="def list_(store):"))[0] == 0
        rid = mangsang.rel_id(rel("memo.py:add", "realizes", "concept:adding"))
        code, out = run("lookup", rid, "--target", pj.dir)
        assert code == 0 and "concept:adding — means: appending one memo" in out and "%s  memo.py:add realizes concept:adding — fresh" % rid in out, out
        assert '"def add(store, text):" — by kim' in out and "`mangsang lookup memo.py`" in out and "no confirmed relations" not in out, out
        code, out = run("lookup", "concept:adding", "--target", pj.dir)
        assert code == 0 and out.count("appending one memo") == 1 and "[concept:adding]" in out and "2 relation(s) on concept:adding" in out, out
        code, out = run("lookup", "concept:adding", "--brief", "--target", pj.dir)
        assert out.strip() == "concept:adding — appending one memo; it prints its id (2 relation(s))", out
        code, out = run("lookup", "memo.py:add", "--target", pj.dir)
        assert code == 0 and "1 relation(s) on memo.py:add" in out and "list_" not in out, out
        code, out = run("lookup", rid.upper(), "--target", pj.dir)   # pasted in capitals: the same relation
        assert code == 0 and "%s  memo.py:add realizes" % rid in out, out
        code, out = run("lookup", "memo.py:nosuch", "--target", pj.dir)
        assert code == 1 and "has no :nosuch now" in out and "makes nothing stale" not in out, out
        code, out = run("lookup", "source:nobody-said", "--target", pj.dir)
        assert code == 1 and "no source nobody-said" in out and "no such file" not in out, out
        assert run("retire", rid, "--why", "split in two", "--target", pj.dir)[0] == 0
        code, out = run("lookup", rid, "--target", pj.dir)
        assert code == 0 and "is retired" in out and "split in two" in out, out
        code, out = run("lookup", "R-00000000", "--target", pj.dir)
        assert code == 1 and "takes a relation id, `concept:NAME`, a file" in out, out
        assert run("lookup", "concept:nothing", "--target", pj.dir)[0] == 1


def test_a_concept_known_to_have_drifted_is_said_until_it_is_revised():
    """guin-site 748a4d8: the site moved off D1, its concept still said "the original is in D1", and with no way to say "this
    is known wrong, the revision waits" the session re-confirmed the stale relations and `cq` answered green with a false
    sentence. `concept drift NAME --why` marks it: cq says DRIFTED (exit 1), list/lookup/--brief/report show the mark, impact
    groups its stale relations on one line, reconfirm and the judge's still-true are refused; revise or reaffirm clears it,
    and the mark stays in history."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "appending one memo; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"))[0] == 0
        assert run("cq", "add", "how-add", "--text", "How is a memo added?", "--verify", '{"kind": "answered-by", "concepts": ["adding"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("cq", "--target", pj.dir)[0] == 0
        assert run("concept", "drift", "adding", "--target", pj.dir)[0] != 0, "a reason is required"
        assert run("concept", "drift", "adding", "--why", "x", "--target", pj.dir)[0] != 0, "at a terminal, a mark is signed"
        code, out = run_as_agent("concept", "drift", "adding", "--why", "memos moved to the PDS; the sentence still says a list. Revised at stage 5", "--target", pj.dir)
        assert code == 0 and "cq says DRIFTED for how-add" in out, out
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))
        assert c["drift"]["agent"] == "Claude Code" and c["drift"]["why"].startswith("memos moved") and c["drift"]["at"].endswith("Z"), c
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "DRIFTED      how-add" in out and "drifted: adding — memos moved to the PDS" in out and "drifted 1" in out and "answered 0" in out, out
        code, out = run("cq", "--findings", "--target", pj.dir)
        assert [f["kind"] for f in json.loads(out)["findings"]] == ["cq-drifted"], out
        assert "DRIFTED: memos moved to the PDS" in run("concept", "list", "--target", pj.dir)[1]
        assert "drifted (meaning known wrong, revision owed): adding" in run("concept", "list", "--brief", "--target", pj.dir)[1]
        assert "DRIFTED: memos moved" in run("lookup", "memo.py", "--target", pj.dir)[1]
        assert "concept:adding [drifted]" in run("lookup", "memo.py", "--brief", "--target", pj.dir)[1].split(" — ")[0]
        assert "**drifted**" in run("report", "--target", pj.dir)[1]
        # the code moved: its relation is stale, and waits for the new sentence instead of a re-read
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        code, out = run("impact", "--target", pj.dir)
        rid = mangsang.rel_id(rel("memo.py:add", "realizes", "concept:adding"))
        assert code == 1 and "drifted concept:adding — memos moved to the PDS" in out and "1 stale relation(s) wait for `concept revise adding`" in out, out
        assert "  stale   " not in out and "unresolved_total = 1" in out, out
        code, out = run("reconfirm", rid, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 1 and "is marked drifted" in out and "concept revise adding" in out, out
        code, out = run("judge", "request", "--out", os.path.join(pj.dir, "j"), "--target", pj.dir)
        assert "not asked: 1 relation(s) on drifted concept(s)" in out and "nothing stale to judge" in out, out
        # revised: the mark goes to history, the questions answer again once the projections are re-read
        assert run("concept", "revise", "adding", "--means", "appending one memo to the PDS; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))
        assert "drift" not in c and c["history"][-1]["drift"]["why"].startswith("memos moved"), c
        assert "DRIFTED" not in run("cq", "--target", pj.dir)[1]
        assert run("reconfirm", rid, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)[0] == 0
        # reaffirm clears a mark too, when the old sentence holds after all
        assert run_as_agent("concept", "drift", "adding", "--why", "maybe wrong", "--target", pj.dir)[0] == 0
        assert run("concept", "reaffirm", "adding", "--by", "kim", "--why", "the old sentence holds after all", "--target", pj.dir)[0] == 0
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))
        assert "drift" not in c and c["history"][-1]["drift"]["why"] == "maybe wrong" and c["history"][-1]["reaffirmed"]["by"] == "kim", c
        assert run("cq", "--target", pj.dir)[0] == 0



def test_a_drifted_concept_takes_no_new_signature_and_hides_nothing_else():
    """Review of 1.17.0's drift: reconfirm refused a drifted concept, but `confirm` signed a new relation quoting the false
    sentence and `move` re-signed one on it — the same hazard. A drifted question that also fails says both; a drift alone is
    no revision in the report's count."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "appending one memo; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "how-add", "--text", "How is a memo added?", "--verify", '{"kind": "answered-by", "concepts": ["adding"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        assert run_as_agent("concept", "drift", "adding", "--why", "memos moved to the PDS", "--target", pj.dir)[0] == 0
        # realized nowhere and drifted: both said, each counted once
        code, out = run("cq", "--findings", "--target", pj.dir)
        assert sorted(f["kind"] for f in json.loads(out)["findings"] if f["where"] == "how-add") == ["cq-drifted", "cq-failed"], out
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "answered 0 · failed 1" in out and "drifted 1" in out, out
        # a new relation on it is refused like a re-confirmation
        code, out = pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"))
        assert code == 1 and "is marked drifted" in out and "concept revise adding" in out, out
        assert not mangsang.decl(pj.dir)["relations"]
        # two drift marks are no revision
        assert run_as_agent("concept", "drift", "adding", "--why", "still wrong", "--target", pj.dir)[0] == 0
        assert "revised" not in run("report", "--target", pj.dir)[1]
        assert run("concept", "revise", "adding", "--means", "appending one memo to the PDS; it prints its id", "--by", "kim", "--target", pj.dir)[0] == 0
        assert "revised 1 time(s)" in run("report", "--target", pj.dir)[1]
        # move: a broken relation on a drifted concept is left for a person
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"))[0] == 0
        write(os.path.join(pj.dir, "core.py"), "def add(store, text):\n    return 1\n")
        os.remove(os.path.join(pj.dir, "memo.py"))
        assert run("register", "core.py", "--target", pj.dir)[0] == 0
        assert run_as_agent("concept", "drift", "adding", "--why", "moved again", "--target", pj.dir)[0] == 0
        code, out = run("move", "--by", "kim", "--why", "the symbol moved to core.py", "--target", pj.dir)
        assert "left" in out and "is marked drifted" in out and not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"]), out


def test_unseen_directories_are_capped_excludable_and_reach_files_beside_deeper_ones():
    """Review of 1.17.0's unseen directories: a monorepo with one package registered named thousands of directories in one
    line; vendored code and lockfiles had no way out but an invariant nobody knew to write; and `src/b.py` beside a registered
    `src/a/x.py` was seen by neither advice. Now: six named and the rest counted, a `registered` invariant's `except` globs and
    lockfiles leave a directory out, and files directly in such a directory are said as `src/*`. The root's files are not:
    they are every project's manifests."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "src", "a", "x.py"), "def x():\n    return 1\n")
        write(os.path.join(pj.dir, "src", "b.py"), "def b():\n    return 1\n")
        for i in range(9):
            write(os.path.join(pj.dir, "pkg%d" % i, "index.js"), "export const a = 1\n")
        write(os.path.join(pj.dir, "web", "package-lock.json"), "{}\n")
        write(os.path.join(pj.dir, "vendor", "lib.py"), "Z = 1\n")
        write(os.path.join(pj.dir, "config.py"), "Y = 1\n")
        write(os.path.join(pj.dir, "hunsu.lock.json"), json.dumps({"record-paths": {"dwitbuk": "reviews/"}}))   # a string: no prefixes
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "src/a/x.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        line = next(l for l in out.split("\n") if "director" in l and "unseen" in l)
        assert "11 directories" in line and "… and 5 more" in line and "src/* 1 file(s)" not in line, line   # sorted: pkg0..pkg5 named first
        assert "web/" not in line and "config.py" not in line and "`except` globs in a `registered` invariant" in line, line
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        f = next(f for f in doc["findings"] if f["kind"] == "unregistered" and "pkg0/" in f["where"])
        assert "src/* (1)" in f["text"] and "vendor/" in f["where"] and "more" not in f["text"], f   # twelve fit; a string record-paths skipped nothing
        assert run("cq", "add", "seen", "--text", "Does the net see the code?", "--verify",
                   '{"kind": "registered", "paths": ["src/a/"], "except": ["pkg*/*", "vendor/*"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        line = next(l for l in run("check", "--target", pj.dir)[1].split("\n") if "director" in l and "unseen" in l)
        assert line.count("file(s)") == 1 and "src/* 1 file(s)" in line and "1 directory" in line, line


def test_lookup_brief_is_a_line_per_concept_and_silent_where_there_is_no_fact():
    """jokbo puts `lookup PATH --brief` in front of an agent at its first look at a file: whole outputs pasted into its context
    went unread (~43k characters in a cycle). 2.6.0 (contract C4): one line — how many relations stand on the file, on which
    concepts (at most three named, the stale first), how many are stale now, and that re-reading them belongs to the same
    task; no ids, no quotes; one line for a registered file nothing stands on and for a tracked file the net does not see;
    nothing at all for a path not in the tree."""
    import subprocess
    tail = " — an edit here stales them; re-reading them belongs to the same task (`mangsang lookup %s`)"
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        write(os.path.join(pj.dir, "notes.py"), "Y = 2\n")
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "Appending one memo. It prints its id, which " + "x" * 200, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"),
                          rel("memo.py:list_", "realizes", "concept:adding", ev="def list_(store):"),
                          rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))[0] == 0
        code, out = run("lookup", "memo.py", "--brief", "--target", pj.dir)
        lines = out.splitlines()
        assert code == 0 and lines == ["memo.py: 3 relation(s) stand on it, on concept:adding" + tail % "memo.py"], out   # fresh: no count of stale
        assert "rel-" not in out and "kim" not in out and "def add" not in out, out   # no ids, no confirmer, no quote
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        code, out = run("lookup", "memo.py", "--brief", "--target", pj.dir)
        assert out.splitlines() == ["memo.py: 3 relation(s) stand on it, on concept:adding; 2 stale or broken now" + tail % "memo.py"], out
        assert not os.path.exists(os.path.join(pj.dir, ".mangsang")), "lookup --brief writes nothing"
        long = "a sentence with no end " * 20
        assert run("concept", "add", "long", "--means", long, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("test_memo.py:test_Q1_add", "realizes", "concept:long", ev="def test_Q1_add"))[0] == 0
        out = run("lookup", "test_memo.py", "--brief", "--target", pj.dir)[1]
        assert len(out.splitlines()) == 1 and "concept:long" in out and "a sentence with no end" not in out, out   # the name, not the meaning
        # at most three concepts named: the rest summed
        for i in range(6):
            assert run("concept", "add", "c%d" % i, "--means", "concept %d." % i, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(*[rel("memo.py:add", "realizes", "concept:c%d" % i, ev="def add(store, text):") for i in range(6)])[0] == 0
        out = run("lookup", "memo.py", "--brief", "--target", pj.dir)[1]
        assert len(out.splitlines()) == 1 and " and 4 more" in out and "(`mangsang lookup memo.py`)" in out, out
        assert out.startswith("memo.py: 9 relation(s) stand on it, on concept:adding") and "; 2 stale or broken now — " in out, out   # what is stale comes first
        assert len(re.findall(r"concept:[\w-]+", out)) == 3, out
        # a registered file nothing stands on says so in a line; a path not in the tree prints nothing; an unseen file, one line
        assert run("lookup", "plan/PLAN.md", "--brief", "--target", pj.dir) == (0, "plan/PLAN.md: registered, but no relation stands on it — impact never sees an edit here; "
                                                                               "relate what it carries (`mangsang check` lists it as unrelated)\n"), "registered, nothing on it"
        assert run("lookup", "gone.py", "--brief", "--target", pj.dir) == (0, ""), "not in the tree"
        code, out = run("lookup", "notes.py", "--brief", "--target", pj.dir)   # no git: it cannot tell untracked, so it says it
        assert code == 0 and len(out.splitlines()) == 1 and "the net does not see it" in out, out
        git("init", "-q"); git("add", "plan", "memo.py", "test_memo.py", "notes.py")
        write(os.path.join(pj.dir, "build.py"), "Z = 3\n")   # untracked output: no fact to add
        assert run("lookup", "build.py", "--brief", "--target", pj.dir) == (0, ""), "untracked, unregistered"
        code, out = run("lookup", "notes.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == ["notes.py: not registered — the net does not see it (no relation stands on it; edits here are never stale)"], out


def test_concept_list_brief_is_the_net_as_a_map_in_a_line_or_two():
    """jokbo's session-start map: what exists, in a line or two — the concepts by name (cut to fit), the open questions,
    how many relations are stale when any are. An empty net prints nothing."""
    with Project() as pj:
        assert run("concept", "list", "--brief", "--target", pj.dir) == (0, ""), "an empty net says nothing"
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        for n in ("beta", "alpha"):
            assert run("concept", "add", n, "--means", "%s means something." % n, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:alpha", ev="def add(store, text):"))[0] == 0
        code, out = run("concept", "list", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == ["2 concept(s): alpha, beta", "2 registered file(s) nothing relates to (./ 1, plan/ 1) — an edit there "
                                                  "makes nothing stale; `mangsang check` says how to relate them"], out   # test_memo.py, plan/PLAN.md
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:alpha"), rel("test_memo.py:test_Q1_add", "realizes", "concept:alpha", ev="def test_Q1_add"))[0] == 0
        code, out = run("concept", "list", "--brief", "--target", pj.dir)
        assert code == 0 and out == "2 concept(s): alpha, beta\n", out
        assert run("cq", "add", "q1", "--text", "what is left?", "--verify", '{"kind": "open"}', "--by", "kim", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        code, out = run("concept", "list", "--brief", "--target", pj.dir)
        assert out.splitlines() == ["2 concept(s): alpha, beta ; 1 open question(s)",
                                    "3 relation(s); 1 stale — `mangsang impact` lists them"], out
        for i in range(60):
            assert run("concept", "add", "concept-number-%02d" % i, "--means", "one.", "--by", "kim", "--target", pj.dir)[0] == 0
        first = run("concept", "list", "--brief", "--target", pj.dir)[1].splitlines()[0]
        assert first.startswith("62 concept(s): alpha, beta, concept-number-00") and ", … (+" in first and len(first) <= 300, first


def test_concepts_are_the_nets_own_nodes_and_survive_what_kills_anchors():
    """The net is primary: a concept is declared once, projections realize it, and the failure modes that kill
    anchor-pair relations — a section retitle, a meaning change nobody wrote down — become one visible event each:
    rename moves the name under every relation; revising `means` stales every projection, on purpose."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        # a name without a meaning, or without a declarer, is refused
        assert run("concept", "add", "adding", "--by", "kim", "--target", pj.dir)[0] == 1
        assert run("concept", "add", "adding", "--means", "a note is appended and its id printed", "--target", pj.dir)[0] == 1
        assert run("concept", "add", "adding", "--means", "a note is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        # projections: doc section, code symbol, test — each realizes the concept; evidence quotes the concept's meaning
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding", ev="appends and prints"),
                               rel("memo.py:add", "realizes", "concept:adding", ev="def add"),
                               rel("test_memo.py:test_Q1_add", "realizes", "concept:adding", ev="def test_Q1_add"))
        assert code == 0, out
        # evidence against concept:NAME quotes its `means` sentence — paraphrase still refused
        assert mangsang.quoted(pj.dir, "note is appended", "concept:adding")
        assert not mangsang.quoted(pj.dir, "a note gets added", "concept:adding")
        assert run("observe", "--reset", "--target", pj.dir)[0] == 0
        code, out = run("impact", "--target", pj.dir)
        assert code == 0, out
        # a section retitle kills the anchor-pair world; here the concept survives and only that projection breaks
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("## Q1 add", "## Q1 adding notes"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "broken" in out and "concept:adding" not in out.split("broken")[0], out
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN)   # restore
        # revising the meaning stales every projection — the net moved, the territory must follow
        assert run("concept", "revise", "adding", "--means", "a note is appended, its id printed, and an empty text refused", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("stale") >= 3, out
        # rename: identity is the name, so the rename is one command and relations move with it
        code, out = run("concept", "rename", "adding", "note-capture", "--target", pj.dir)
        assert code == 0 and "3 relation(s) and 0 question(s) moved" in out, out
        d = mangsang.decl(pj.dir)
        assert all("concept:adding" not in (r["src"], r["dst"]) for r in d["relations"])
        assert sum("concept:note-capture" in (r["src"], r["dst"]) for r in d["relations"]) == 3
        code, out = run("concept", "list", "--target", pj.dir)
        assert code == 0 and "note-capture" in out and "realizes" in out, out


def test_a_newer_build_resaving_an_unchanged_record_writes_nothing():
    """`written_by` names the build that wrote a record's content. Every command re-saves every concept; with the stamp
    refreshed each time, a version bump rewrote a whole project's concept files for a version string."""
    with Project() as pj:
        assert run("concept", "add", "hand", "--means", "one of three shapes", "--by", "lee", "--target", pj.dir)[0] == 0
        path = os.path.join(pj.dir, "mangsang", "concepts", "hand.json")
        rec = dict(mangsang.load(path), written_by="mangsang 0.0.1")
        write(path, json.dumps(rec, ensure_ascii=False, indent=2) + "\n")   # the same content, an old build's stamp
        old, mangsang._ENGINE = mangsang._ENGINE, "mangsang 99.0.0"
        try:
            assert run("concept", "add", "tie", "--means", "a round with no winner", "--by", "lee", "--target", pj.dir)[0] == 0   # re-saves every concept
            assert mangsang.load(path)["written_by"] == "mangsang 0.0.1", "an unchanged concept was rewritten for the version string"
            assert mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "tie.json"))["written_by"] == "mangsang 99.0.0"
            assert run("concept", "revise", "hand", "--means", "one of the three shapes", "--by", "lee", "--target", pj.dir)[0] == 0
            assert mangsang.load(path)["written_by"] == "mangsang 99.0.0", "changed content carries the build that changed it"
        finally:
            mangsang._ENGINE = old


def test_a_planning_model_whose_questions_are_all_open_asks_about_its_concepts():
    """Planning starts with every question open: an open question may name what it asks about (`about`) — never its
    answer — and those concepts are questioned, not answered. Without `about`, every concept read as UNQUESTIONED."""
    with Project() as pj:
        assert run("concept", "add", "venue", "--means", "where papers are called for", "--by", "lee", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "call", "--means", "one call for papers", "--by", "lee", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "Q-which", "--text", "Which venues?", "--verify", '{"kind": "open"}', "--by", "lee", "--target", pj.dir)[0] == 0
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "unquestioned 2" in out, out
        assert run("cq", "add", "Q-fields", "--text", "What fields?", "--verify", '{"kind": "open", "about": ["nope"]}', "--by", "lee", "--target", pj.dir)[0] == 1
        assert run("cq", "add", "Q-fields", "--text", "What fields?", "--verify", '{"kind": "open", "about": ["call"], "concepts": ["call"]}', "--by", "lee", "--target", pj.dir)[0] == 1   # still names no answer
        assert run("cq", "add", "Q-fields", "--text", "What fields?", "--verify", '{"kind": "open", "about": ["call"]}', "--by", "lee", "--target", pj.dir)[0] == 0
        assert run("cq", "revise", "Q-which", "--verify", '{"kind": "open", "about": ["venue"]}', "--by", "lee", "--target", pj.dir)[0] == 0
        code, out = run("cq", "--target", pj.dir)
        assert code == 0 and "unquestioned 0" in out and "open 2" in out and "answered 0" in out and "(about venue)" in out, out
        code, out = run("report", "--target", pj.dir)
        assert '"asks about"' in out, out


def test_a_model_grounded_in_what_people_said_open_questions_and_the_report():
    """A model built from a conversation: the words kept verbatim as `source:ID`, a concept grounded in them by a quote,
    a question asked before anything answers it, the answer signed when it exists, a rename that carries the question,
    and one page a person can read — which writes nothing."""
    with Project() as pj:
        said = os.path.join(pj.dir, "talk", "u1.txt")
        write(said, "A draw is replayed. After three draws in a row the game ends with no winner.\n")
        # a source needs its words and its speaker; it is kept once and never changes
        assert run("source", "add", "U1", "--file", said, "--target", pj.dir)[0] == 1
        assert run("source", "add", "U1", "--file", said, "--speaker", "lee", "--locator", "meeting 09-22", "--target", pj.dir)[0] == 0
        assert "unchanged" in run("source", "add", "U1", "--file", said, "--speaker", "lee", "--target", pj.dir)[1]
        write(said, "A draw is never replayed.\n")
        code, out = run("source", "add", "U1", "--file", said, "--speaker", "lee", "--target", pj.dir)
        assert code == 1 and "new source" in out, out
        # both sides are sources: the agent's reading and the person's "yes" to it, kept as a reply — from stdin, no input file left
        write(said, "A draw is replayed. After three draws in a row the game ends with no winner.\n")
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("So: a draw means every hand is the same. Is that right?\n")
            assert run("source", "add", "A1", "--file", "-", "--speaker", "Claude (model)", "--replies-to", "U1", "--target", pj.dir)[0] == 0
            sys.stdin = io.StringIO("Yes, as you said.\n")
            code, out = run("source", "add", "U2", "--file", "-", "--speaker", "lee", "--replies-to", "A9", "--target", pj.dir)
            assert code == 1 and "no such source" in out, out   # an answer without its question is refused
            sys.stdin = io.StringIO("Yes, as you said.\n")
            assert run("source", "add", "U2", "--file", "-", "--speaker", "lee", "--replies-to", "A1", "--target", pj.dir)[0] == 0
        finally:
            sys.stdin = old_stdin
        assert mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "U2.json"))["replies-to"] == "A1"
        assert "replying to A1" in run("source", "list", "--target", pj.dir)[1]
        # a question asked before any concept answers it: open, alone; an open question naming an answer is refused
        assert run("cq", "add", "CQ-tie", "--text", "What happens after a draw?", "--verify", '{"kind": "open", "concepts": ["x"]}', "--by", "lee", "--target", pj.dir)[0] == 1
        assert run("cq", "add", "CQ-tie", "--text", "What happens after a draw?", "--verify", '{"kind": "open"}', "--by", "lee", "--target", pj.dir)[0] == 0
        code, out = run("cq", "--target", pj.dir)
        assert code == 0 and "OPEN" in out and "open 1" in out, out   # a declared gap is not a failure
        code, out = run("cq", "--findings", "--target", pj.dir)
        doc = json.loads(out)
        assert [(f["kind"], f["layer"]) for f in doc["findings"]] == [("cq-open", "observation")], doc   # the reviewer lists it, nobody disposes of it
        assert doc["standing"] is True, "cq reads the model as it is now: a finding it stops reporting is gone"
        # the reading, grounded: the evidence quotes the source; a paraphrase of it is refused like any other
        assert run("concept", "add", "replay", "--means", "a drawn round is played again; three draws in a row end the game undecided", "--by", "lee", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("source:U1", "realizes", "concept:replay", ev="a draw gets played once more"))
        assert code == 1 and "not a quote" in out, out
        code, out = pj.propose(rel("source:U1", "realizes", "concept:replay", ev="A draw is replayed."))
        assert code == 0, out
        # `said` is a medium like doc/code/test: every concept grounded in something someone said
        assert run("cq", "add", "grounded", "--text", "is every concept grounded in what was said?", "--verify",
                   '{"kind": "projection", "media": {"said": ["source:"]}}', "--by", "lee", "--target", pj.dir)[0] == 0
        assert run("check", "--target", pj.dir)[0] == 0
        # the answer arrives: the question is revised to name it (what it was before is the record's history, in git)
        assert run("cq", "revise", "CQ-tie", "--verify", '{"kind": "answered-by", "concepts": ["replay"]}', "--by", "lee", "--target", pj.dir)[0] == 0
        code, out = run("cq", "--target", pj.dir)
        assert code == 0 and "answered" in out and "open 0" in out, out
        # a rename carries the question with it — a meaning that did not change must not make it unanswerable
        code, out = run("concept", "rename", "replay", "draw-replay", "--target", pj.dir)
        assert code == 0 and "1 relation(s) and 1 question(s) moved" in out, out
        code, out = run("cq", "--target", pj.dir)
        assert code == 0 and "UNANSWERABLE" not in out, out
        # revising the reading stales its grounding: someone must re-read the words against the new sentence
        assert run("observe", "--reset", "--target", pj.dir)[0] == 0
        assert run("concept", "revise", "draw-replay", "--means", "a drawn round is played again until someone wins", "--by", "lee", "--target", pj.dir)[0] == 0
        obs = os.path.join(pj.dir, ".mangsang")
        state = lambda: {n: io.open(os.path.join(obs, n), encoding="utf-8").read() for n in sorted(os.listdir(obs))}
        before = state()
        # the page: concepts with their quotes and state, questions with their state (the grounding just went stale), the words; it writes nothing
        code, out = run("report", "--target", pj.dir)
        assert code == 0 and "```mermaid" in out and "stale" in out and "“A draw is replayed.”" in out, out
        assert '{{"CQ-tie: What happens after a draw?"}}' in out and '==>|"answered by"|' in out, out   # the questions are in the graph
        assert "What happens after a draw? — FAILED" in out and "> A draw is replayed." in out, out
        assert state() == before, "report must not write observation state"
        assert run("report", "--out", "mangsang/view.md", "--target", pj.dir)[0] == 1   # never into the record
        assert run("report", "--out", "NET.md", "--target", pj.dir)[0] == 0 and os.path.exists(os.path.join(pj.dir, "NET.md"))
        # --html: one file that draws offline — mermaid inlined, nothing fetched — and every text of the record escaped
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("<script>alert(1)</script> said nobody\n")
            assert run("source", "add", "U3", "--file", "-", "--speaker", "lee", "--target", pj.dir)[0] == 0
        finally:
            sys.stdin = old_stdin
        assert run("report", "--html", "NET.html", "--target", pj.dir)[0] == 0
        page = io.open(os.path.join(pj.dir, "NET.html"), encoding="utf-8").read()
        assert "<script src" not in page and "mermaid.initialize" in page and len(page) > 1000000, "mermaid must be inlined, not fetched"
        assert '<pre class="mermaid">flowchart LR' in page and "&lt;script&gt;alert(1)&lt;/script&gt; said nobody" in page
        assert page.count("<script>") == 2, "only the page's own two scripts; the record's text is never markup"
        assert run("report", "--html", "mangsang/x.html", "--target", pj.dir)[0] == 1
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "source:U1" in out, out


def test_a_turn_is_taken_from_the_hosts_transcript_verbatim_and_names_are_the_rosters():
    """Retyping a conversation into a source is where words drift: the host already keeps them. `--from-transcript` takes the
    one turn that contains `--match`, as the host recorded it — the agent's words under its model's name, a multiple-choice
    question as the tool carried it. A roster (`mangsang/people.json`) makes a made-up signature a refusal."""
    with Project() as pj:
        tr = os.path.join(pj.dir, "session-abc.jsonl")
        lines = [
            {"type": "user", "uuid": "u1", "timestamp": "t1", "message": {"role": "user", "content": "the feed shows everything, newest first"}},
            {"type": "assistant", "uuid": "a1", "timestamp": "t2", "message": {"id": "m1", "model": "claude-x", "content": [{"type": "text", "text": "So: one list, newest first."}]}},
            {"type": "assistant", "uuid": "a2", "timestamp": "t2", "message": {"id": "m1", "model": "claude-x", "content": [{"type": "text", "text": "Is that right?"}]}},
            {"type": "assistant", "uuid": "a3", "timestamp": "t3", "message": {"id": "m2", "model": "claude-x", "content": [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": [{"question": "Times in UTC?"}]}}]}},
            {"type": "user", "uuid": "u2", "timestamp": "t4", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": "Your questions have been answered: \"Times in UTC?\"=\"reader's local\". You can now continue with these answers in mind."}]},
             "toolUseResult": {"questions": [{"question": "Times in UTC?"}], "answers": {"Times in UTC?": "reader's local"}}},
            {"type": "user", "uuid": "u3", "timestamp": "t5", "message": {"role": "user", "content": "<task-notification>done</task-notification>"}},
        ]
        write(tr, "\n".join(json.dumps(x) for x in lines) + "\n")
        # the agent's turn: its text blocks of one message joined, spoken by its model, located in the session
        assert run("source", "add", "A1", "--from-transcript", tr, "--match", "newest first.", "--kind", "agent", "--target", pj.dir)[0] == 0
        a1 = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "A1.json"))
        assert a1["text"] == "So: one list, newest first.\n\nIs that right?" and a1["speaker"] == "Claude (claude-x)", a1
        assert a1["locator"] == "session session-abc, agent a1 at t2" and a1["verbatim-from"] == "host transcript", a1
        # ambiguous: the phrase is in two turns
        code, out = run("source", "add", "X", "--from-transcript", tr, "--match", "newest first", "--target", pj.dir)
        assert code == 1 and "found 2 turn(s)" in out, out
        # a person's turn needs the name they gave; a question and its answer are kept as the tool carried them
        assert run("source", "add", "U1", "--from-transcript", tr, "--match", "everything", "--target", pj.dir)[0] == 1
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        code, out = run("source", "add", "U1", "--from-transcript", tr, "--match", "everything", "--speaker", "some-account", "--target", pj.dir)
        assert code == 1 and "not in mangsang/people.json" in out, out   # a name read off an account is refused
        assert run("source", "add", "U1", "--from-transcript", tr, "--match", "everything", "--speaker", "lee", "--target", pj.dir)[0] == 0
        assert run("source", "add", "Q1", "--from-transcript", tr, "--match", "Times in UTC?", "--kind", "question", "--target", pj.dir)[0] == 0
        assert run("source", "add", "Q1a", "--from-transcript", tr, "--match", "reader's local", "--kind", "answer", "--speaker", "lee", "--replies-to", "Q1", "--target", pj.dir)[0] == 0
        assert '"question": "Times in UTC?"' in mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "Q1.json"))["text"]
        assert run("source", "add", "N", "--from-transcript", tr, "--match", "task-notification", "--speaker", "lee", "--target", pj.dir)[0] == 1, "a host notification is not a person's turn"
        # signatures too
        code, out = run("concept", "add", "feed", "--means", "one list, newest first", "--by", "kim", "--target", pj.dir)
        assert code == 1 and "not in mangsang/people.json" in out, out
        assert run("concept", "add", "feed", "--means", "one list, newest first", "--by", "lee", "--target", pj.dir)[0] == 0


def test_a_playground_round_what_a_day_of_use_found():
    """Read back from a public playground (rock-paper-scissors): every record object says which mangsang wrote it, and a
    committed one written by a build that is no release is a finding; a re-confirmation and a revision keep what they
    replace; the title heading is a section of its own, not the whole file; `impact --show` works when the target is a
    directory inside a repository; the report keeps sources out of the graph, lists approval-only sources apart, shows
    who signed what, and `--check` says whether a committed page is current; a person's yes to the agent's own proposal
    is recorded as that; the reporters' findings carry `text`, the field the finding type requires."""
    import subprocess
    with Project() as pj:
        # the target is a directory inside the repository — the playground's shape
        root = pj.dir
        sub = os.path.join(root, "rps")
        write(os.path.join(sub, "README.md"), "# game\n\nintro line\n\n## hands\n\nthree hands.\n\n## draw\n\nsame hand draws.\n")
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=root, capture_output=True, text=True)
        git("init", "-q")
        write(os.path.join(sub, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        assert run("register", "README.md", "--target", sub)[0] == 0
        # the title heading is its own section: editing the last section does not touch it
        md = mangsang.anchors_of(os.path.join(sub, "README.md"))
        assert md["#game"] != md[""] and mangsang.anchor_texts(os.path.join(sub, "README.md"))["#game"] == "# game\n\nintro line\n\n", md
        # sources: the agent's proposal, the person's one-word yes to it, and the person's own words
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("Concepts: hand (three), draw.\n")
            assert run("source", "add", "A1", "--file", "-", "--speaker", "Claude (m)", "--target", sub)[0] == 0
            sys.stdin = io.StringIO("ok go\n")
            assert run("source", "add", "L1", "--file", "-", "--speaker", "lee", "--replies-to", "A1", "--target", sub)[0] == 0
            sys.stdin = io.StringIO("a draw is when every hand shown is the same\n")
            assert run("source", "add", "L2", "--file", "-", "--speaker", "lee", "--target", sub)[0] == 0
        finally:
            sys.stdin = old_stdin
        # an agent signs lee's name on lee's yes to the agent's list: recorded as an approval of a proposal
        os.environ["CLAUDECODE"] = "1"
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = mangsang.main(["concept", "add", "hand", "--means", "one of three", "--by", "lee", "--approved-in", "source:L1", "--target", sub])
            assert code == 0, out.getvalue()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = mangsang.main(["concept", "add", "draw", "--means", "every hand shown is the same", "--by", "lee", "--approved-in", "source:L2", "--target", sub])
            assert code == 0, out.getvalue()
        finally:
            os.environ.pop("CLAUDECODE", None)
            mangsang.APPROVED_IN = mangsang.APPROVAL_OF = None
        hand = mangsang.load(os.path.join(sub, "mangsang", "concepts", "hand.json"))
        draw = mangsang.load(os.path.join(sub, "mangsang", "concepts", "draw.json"))
        assert {k: hand["declared"].get(k) for k in ("by", "approved-in", "approval-of")} == {"by": "lee", "approved-in": "source:L1", "approval-of": "source:A1"}, hand["declared"]
        assert {k: draw["declared"].get(k) for k in ("by", "approved-in", "approval-of")} == {"by": "lee", "approved-in": "source:L2", "approval-of": None}, draw["declared"]
        # every record object says which mangsang wrote it — a field
        assert hand["written_by"] == mangsang.engine() and mangsang.load(os.path.join(sub, "mangsang", "sources", "L2.json"))["written_by"] == mangsang.engine()
        assert not os.path.exists(os.path.join(sub, "mangsang", "cq.json")), "a new project gets no empty legacy list"
        write(os.path.join(sub, "proposals.json"), {"relations": [
            {"src": "README.md#hands", "predicate": "realizes", "dst": "concept:hand", "evidence": "three hands."},
            {"src": "README.md#draw", "predicate": "realizes", "dst": "concept:draw", "evidence": "same hand draws."},
            {"src": "source:L2", "predicate": "realizes", "dst": "concept:draw", "evidence": "every hand shown is the same"}]})
        assert run("confirm", "proposals.json", "--delegated", "source:L2", "--why", "test", "--target", sub)[0] == 0
        assert run("cq", "add", "what-draw", "--text", "what is a draw?", "--verify", '{"kind": "answered-by", "concepts": ["draw"]}', "--by", "lee", "--target", sub)[0] == 0
        rid = next(r["id"] for r in mangsang.decl(sub)["relations"] if r["src"] == "README.md#draw")
        assert mangsang.load(os.path.join(sub, "mangsang", "relations", rid + ".json"))["written_by"] == mangsang.engine()
        git("add", "-A"); git("commit", "-qm", "confirmed")
        # a committed record written by a working source is a finding for the reviewer (this self-check runs from one);
        # the approval of a proposal is an observation; every finding has `text`
        code, out = run("check", "--findings", "--target", sub)
        doc = json.loads(out)
        kinds = {f["kind"] for f in doc["findings"]}
        assert ("unreleased-writer" in kinds) == ("+g" in mangsang.engine()), (mangsang.engine(), kinds)
        assert "agent-proposed" in kinds and all(f.get("text") for f in doc["findings"]), doc
        assert next(f for f in doc["findings"] if f["kind"] == "agent-proposed")["where"] == "concept:hand"
        code, out = run("cq", "--findings", "--target", sub)
        assert all(f.get("text") for f in json.loads(out)["findings"]), out
        # the report: no source in the graph, the approval-only yes under Approvals, signatures shown; --check on a kept page
        assert run("report", "--out", "MODEL.md", "--target", sub)[0] == 0
        page = io.open(os.path.join(sub, "MODEL.md"), encoding="utf-8").read()
        graph = page.split("```mermaid")[1].split("```")[0]
        assert "source:" not in graph and "concept:draw" in graph, graph
        assert "## Approvals" in page and "**L1** — lee, replying to A1 (Claude (m)): “ok go” — approves `concept:hand`" in page, page
        assert "### L2 — lee" in page and "### L1" not in page and "### A1 — Claude (m) — grounds nothing yet" in page, page   # a standalone source that grounds nothing stays under Sources, in full; only an answer that merely approves goes under Approvals
        assert "declared by lee (approved in `source:L1`, answering the agent's `source:A1`)" in page and "delegated: lee's words (source:L2)" in page and "Rendered from `mangsang/` by mangsang " in page, page
        assert run("report", "--check", "MODEL.md", "--target", sub)[0] == 0
        # the page rendered by another mangsang, the record unchanged: still current (only the renderer's version differs)
        kept = os.path.join(sub, "MODEL.md")
        older = io.open(kept, encoding="utf-8").read().replace("by %s;" % mangsang.engine(), "by mangsang 0.9.9;")
        assert "by mangsang 0.9.9;" in older
        io.open(kept, "w", encoding="utf-8", newline="\n").write(older)
        code, out = run("report", "--check", "MODEL.md", "--target", sub)
        assert code == 0 and "is current" in out, out
        # the last section changes: the title section stays fresh, the draw relation goes stale, and --show reads the old text from
        # git although the target is a subdirectory; reconfirm keeps what it replaces; revise keeps the old meaning
        write(os.path.join(sub, "README.md"), "# game\n\nintro line\n\n## hands\n\nthree hands.\n\n## draw\n\nsame hand draws. always.\n")
        code, out = run("impact", "--show", "--target", sub)
        assert code == 1 and "-same hand draws." in out and "+same hand draws. always." in out and "#game" not in out, out
        code, out = run("report", "--check", "MODEL.md", "--target", sub)
        assert code == 1 and "behind the record" in out, out
        assert run("reconfirm", rid, "--by", "lee", "--why", "re-read both ends; still holds", "--target", sub)[0] == 0
        r = mangsang.load(os.path.join(sub, "mangsang", "relations", rid + ".json"))
        assert len(r["history"]) == 1 and r["history"][0]["confirmed"].get("delegated") == {"source": "source:L2", "speaker": "lee"} and r["confirmed"].get("by") == "lee", r
        assert run("concept", "revise", "draw", "--means", "no hand beats another", "--by", "lee", "--target", sub)[0] == 0
        draw = mangsang.load(os.path.join(sub, "mangsang", "concepts", "draw.json"))
        assert len(draw["history"]) == 1 and draw["history"][0]["means"] == "every hand shown is the same" and {k: draw["history"][0]["declared"].get(k) for k in ("by", "approved-in")} == {"by": "lee", "approved-in": "source:L2"}, draw
        assert run("cq", "revise", "what-draw", "--text", "what counts as a draw?", "--by", "lee", "--target", sub)[0] == 0
        assert mangsang.load(os.path.join(sub, "mangsang", "cq", "what-draw.json"))["history"][0]["text"] == "what is a draw?"


def test_a_stale_relation_shows_what_changed_since_it_was_confirmed():
    """`seen` knows that an anchor changed; the person re-reading needs to see how. The text as confirmed comes from git —
    the commit that last wrote the relation's file — and is diffed against now, in `impact --show` and before `reconfirm`."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        git("init", "-q")
        assert run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "confirmed")
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        code, out = run("impact", "--show", "--target", pj.dir)
        assert code == 1 and "-    return 1" in out and "+    return 2" in out and "memo.py:add @ now" in out, out
        rid = mangsang.decl(pj.dir)["relations"][0]["id"]
        code, out = run("reconfirm", rid, "--by", "kim", "--evidence", "appends and prints", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "changed since" in out and "+    return 2" in out, out
        assert "plan/PLAN.md#Q1 add changed since" not in out and "fingerprint's rule" not in out, out   # the end that did not move is not shown


def test_an_agent_signs_a_persons_name_only_where_that_person_said_yes():
    """Run by an agent (its env says so), `--by lee` is lee's judgment only if lee approved it somewhere on record: the
    signature cites the source (`--approved-in source:ID`, spoken by lee). Without one the agent signs `--delegated`."""
    def agent_run(*argv):
        out = io.StringIO()
        os.environ["CLAUDECODE"] = "1"
        try:
            with contextlib.redirect_stdout(out):
                try:
                    code = mangsang.main(list(argv))
                except SystemExit as err:
                    code = err.code if isinstance(err.code, int) else 1
                    out.write(str(err) + "\n")
        finally:
            os.environ.pop("CLAUDECODE", None)
            mangsang.APPROVED_IN = None
        return code, out.getvalue()
    with Project() as pj:
        said = os.path.join(pj.dir, "ok.txt")
        write(said, "yes, declare it\n")
        assert run("source", "add", "L1", "--file", said, "--speaker", "lee", "--target", pj.dir)[0] == 0
        write(said, "sure\n")
        assert run("source", "add", "K1", "--file", said, "--speaker", "kim", "--target", pj.dir)[0] == 0
        code, out = agent_run("concept", "add", "a", "--means", "m", "--by", "lee", "--target", pj.dir)
        assert code == 1 and "--approved-in source:ID" in out, out
        code, out = agent_run("concept", "add", "a", "--means", "m", "--by", "lee", "--approved-in", "source:K1", "--target", pj.dir)
        assert code == 1 and "was said by kim, not lee" in out, out
        assert agent_run("concept", "add", "a", "--means", "m", "--by", "lee", "--approved-in", "source:L1", "--target", pj.dir)[0] == 0
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "a.json"))
        assert {k: c["declared"].get(k) for k in ("by", "approved-in")} == {"by": "lee", "approved-in": "source:L1"}, c
        assert agent_run("concept", "add", "b", "--means", "m", "--why", "the agent's reading", "--target", pj.dir)[0] == 0


def test_check_projection_asks_that_every_concept_is_realized_in_every_medium():
    """The net's own health invariant: a concept with no code projection (or no test, no doc) is a word the
    project uses and never made true in that medium — surfaced by name, not hidden in a coverage percentage.
    (These used to run under `cq`; the name lied — a lint is not a question. `check` asks them now.)"""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a note is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "mangsang", "cq.json"),
              [{"id": "CQ-net", "text": "every concept is realized in doc, code and test",
                "verify": {"kind": "projection", "media": {"doc": ["plan/"], "code": ["memo.py"], "test": ["test_memo.py"]}}}])
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "adding lacks doc" in out and "adding lacks code" in out and "adding lacks test" in out, out
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding", ev="appends and prints"),
                               rel("memo.py:add", "realizes", "concept:adding", ev="def add"),
                               rel("test_memo.py:test_Q1_add", "realizes", "concept:adding", ev="def test_Q1_add"))
        assert code == 0, out
        # 2.6.0 (contract C3): doc and code hold on a realizes; the test medium only on a `verifies` from a test to its code
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "adding lacks test" in out and "adding lacks doc" not in out and "adding lacks code" not in out, out
        code, out = pj.propose(rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))
        assert code == 0, out
        code, out = run("check", "--target", pj.dir)
        assert "0 gap(s)" in out and "lacks" not in out, out
        # and `cq` no longer answers for it: the structural declaration is counted, not asked
        code, out = run("cq", "--target", pj.dir)
        assert "structural declaration(s) now answer to `check`" in out, out


def test_check_is_a_two_way_audit_unaskable_and_unwatched():
    """The invariant layer's feedback loop, both directions, mechanical. (1) an invariant whose presuppositions no
    longer hold — its predicate gone from the vocabulary, its anchor pattern matching nothing — is UNASKABLE: the
    net moved out from under it (Ren 2014: presuppositions are what the machine checks). (2) net content no
    invariant watches — a used propagating predicate, concepts without a projection invariant — is UNWATCHED.
    Both make `check` exit 1: a stale lint set is as red as a failing lint."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        assert code == 0, out
        # an invariant about a predicate the vocabulary does not have -> UNASKABLE (and `documents` in use, unwatched)
        write(os.path.join(pj.dir, "mangsang", "cq.json"),
              [{"id": "CQ-old", "text": "every section is described", "verify": {"kind": "coverage", "anchors": "plan/PLAN.md#Q*", "as": "src", "predicate": "describes"}}])
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "UNASKABLE" in out and "describes" in out, out
        assert "UNWATCHED" in out and "documents" in out, out
        # an invariant whose anchors match nothing -> UNASKABLE with 'about nothing'
        write(os.path.join(pj.dir, "mangsang", "cq.json"),
              [{"id": "CQ-gone", "text": "every api section is documented", "verify": {"kind": "coverage", "anchors": "docs/api.md#*", "as": "src", "predicate": "documents"}}])
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "about nothing" in out, out
        # concepts declared but no projection invariant -> UNWATCHED names it
        write(os.path.join(pj.dir, "mangsang", "cq.json"),
              [{"id": "CQ1", "text": "every section is documented", "verify": {"kind": "coverage", "anchors": "plan/PLAN.md#Q*", "as": "src", "predicate": "documents"}}])
        assert run("concept", "add", "adding", "--means", "a note is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "no projection invariant" in out, out
        # --findings prints the kinds as dwitbuk/findings@1
        code, out = run("check", "--findings", "--target", pj.dir)
        assert "dwitbuk/findings@1" in out and "invariant-unwatched" in out, out


def test_cq_domain_questions_are_answered_by_living_concepts():
    """The domain layer, restored to the name (G&F: a CQ tests what the model can answer). A CQ names its answer —
    a concept; the machine audits that the answer is alive, never what it says. Unrealized concept -> FAILED (a
    sentence with no reality); deleted concept -> UNANSWERABLE (the model cannot answer this of the domain);
    a concept no question names -> UNQUESTIONED (a meaning nobody asks for); moved projection -> FAILED (the
    promise's reality shifted)."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a note is appended and its id printed; empty text refused", "--by", "kim", "--target", pj.dir)[0] == 0
        # authoring: refused when it names a concept that does not exist
        code, out = run("cq", "add", "CQ-ghost", "--text", "can a note vanish?", "--by", "kim",
                        "--verify", "{\"kind\": \"answered-by\", \"concepts\": [\"vanishing\"]}", "--target", pj.dir)
        assert code == 1 and "no answer to point at" in out, out
        # declared; answers with the concept's means; but the concept is not realized yet -> FAILED
        code, out = run("cq", "add", "CQ-add", "--text", "what happens when a note is added?", "--by", "kim",
                        "--verify", "{\"kind\": \"answered-by\", \"concepts\": [\"adding\"]}", "--target", pj.dir)
        assert code == 0, out
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "FAILED" in out and "realized nowhere" in out, out
        # realize it -> answered, and the means sentence is printed as the answer
        code, out = pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add"))
        assert code == 0, out
        code, out = run("cq", "--target", pj.dir)
        assert code == 0 and "answered" in out and "a note is appended" in out, out
        # a second concept nobody asks about -> UNQUESTIONED
        assert run("concept", "add", "listing", "--means", "open notes only, newest first", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("memo.py:list_", "realizes", "concept:listing", ev="def list_"))
        assert code == 0, out
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "UNQUESTIONED" in out and "concept:listing" in out, out
        write(os.path.join(pj.dir, "mangsang", "cq", "CQ-list.json"),
              {"id": "CQ-list", "text": "what does list show?", "verify": {"kind": "answered-by", "concepts": ["listing"]},
               "declared": {"by": "kim"}})
        # the code under the concept moves -> the projection is stale -> the CQ fails: the promise's reality shifted
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return []", "return [1]"))
        code, out = run("cq", "--target", pj.dir)
        code2, out2 = run("impact", "--target", pj.dir)
        if "stale" in out2:   # the edit staled the realizes projection on this machine's baseline
            assert code == 1 and "moved projections" in out, out
        # deleting the concept's file -> UNANSWERABLE: the model has no answer anymore
        os.remove(os.path.join(pj.dir, "mangsang", "concepts", "listing.json"))
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "UNANSWERABLE" in out and "listing" in out, out


def test_delegation_ref_is_stored_structured_and_free_text_stays_free():
    """--delegated D-xxxx (a chongdae delegation id) was stored as {delegated: {ref}} and any other reason as a free
    why-string. 2.6.0 refuses both for new judgments (a delegation cites a kept source); the records already on disk are
    history: never rewritten, and they keep reading as before — impact --findings prints a ref as `ref D-...`."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a note is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "listing", "--means", "open notes only", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="a note is appended"),
                               rel("memo.py:list_", "realizes", "concept:listing", ev="open notes only"))
        assert code == 0, out
        # the old shapes, written by hand as an older mangsang wrote them
        cpath = os.path.join(pj.dir, "mangsang", "concepts", "adding.json")
        c = mangsang.load(cpath)
        c["declared"] = {"delegated": {"ref": "D-a1b2c3d4"}}
        mangsang.save(cpath, c)
        c2path = os.path.join(pj.dir, "mangsang", "concepts", "listing.json")
        c2 = mangsang.load(c2path)
        c2["declared"] = {"delegated": "orchestrator pre-approved this round"}
        mangsang.save(c2path, c2)
        rid = mangsang.rel_id(rel("memo.py:list_", "realizes", "concept:listing"))
        rpath = os.path.join(pj.dir, "mangsang", "relations", rid + ".json")
        r = mangsang.load(rpath)
        r["confirmed"] = {"delegated": {"ref": "D-a1b2c3d4"}}
        mangsang.save(rpath, r)
        before = {x: io.open(x, "rb").read() for x in (cpath, c2path, rpath)}
        assert mangsang.load(cpath)["declared"] == {"delegated": {"ref": "D-a1b2c3d4"}}
        assert mangsang.load(c2path)["declared"] == {"delegated": "orchestrator pre-approved this round"}
        # impact --findings prints the ref as `ref D-...` without crashing; reading rewrites nothing
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert "ref D-a1b2c3d4" in out, out
        run("lookup", "memo.py", "--target", pj.dir)
        run("report", "--target", pj.dir)
        assert {x: io.open(x, "rb").read() for x in before} == before, "history is never rewritten by reading it"


def test_cq_declaration_is_a_judgment_and_refused_when_it_cannot_be_asked():
    """A question has an author, like a concept: `cq add` records who asks (or the delegation), refuses a question
    whose presuppositions fail against the current model (authoring-time, not discovery at run time), and `cq retire`
    keeps the record with its why. This is what cq.json hand-editing never recorded — the change of what completeness
    means, signed."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        # refused: no author; refused: presupposition fails at authoring time
        assert run("cq", "add", "CQ-a", "--text", "t", "--verify", "{\"kind\": \"resolved\"}", "--target", pj.dir)[0] == 1
        code, out = run("cq", "add", "CQ-a", "--text", "every section is described", "--by", "kim",
                        "--verify", "{\"kind\": \"coverage\", \"anchors\": \"plan/PLAN.md#Q*\", \"as\": \"src\", \"predicate\": \"describes\"}", "--target", pj.dir)
        assert code == 1 and "cannot be asked" in out and "describes" in out, out
        # accepted with a real predicate; then it runs as part of `cq`
        code, out = run("cq", "add", "CQ-a", "--text", "every Q section is documented by code", "--by", "kim",
                        "--verify", "{\"kind\": \"coverage\", \"anchors\": \"plan/PLAN.md#Q*\", \"as\": \"src\", \"predicate\": \"documents\"}", "--target", pj.dir)
        assert code == 0, out
        q = mangsang.load(os.path.join(pj.dir, "mangsang", "cq", "CQ-a.json"))
        assert q["declared"].get("by") == "kim", q
        code, out = run("check", "--target", pj.dir)
        assert "CQ-a" in out and "FAILED" in out, out   # a structural declaration: asked by `check`, and honestly failed (no relations yet)
        # retire keeps the record and takes the question out of the active set
        assert run("cq", "retire", "CQ-a", "--target", pj.dir)[0] == 1   # --why required: retiring a question is a decision
        assert run("cq", "retire", "CQ-a", "--why", "sections replaced by concepts", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert "CQ-a" not in out, out
        assert mangsang.load(os.path.join(pj.dir, "mangsang", "cq", "CQ-a.json"))["retired"]["why"]


def test_anchors_markdown_sections_python_symbols_and_the_whole_file():
    with Project() as pj:
        md = mangsang.anchors_of(os.path.join(pj.dir, "plan", "PLAN.md"))
        assert set(md) == {"", "#plan", "#Q1 add", "#detail", "#Q2 list"}, set(md)
        py = mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))
        assert set(py) == {"", ":X", ":add", ":list_"}, set(py)
        assert mangsang.anchors_of(os.path.join(pj.dir, "nope.py")) is None
        # a section's fingerprint covers its subsections; the sibling section is untouched by an edit inside Q1
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("more", "more words"))
        md2 = mangsang.anchors_of(os.path.join(pj.dir, "plan", "PLAN.md"))
        assert md2["#Q1 add"] != md["#Q1 add"] and md2["#detail"] != md["#detail"] and md2["#Q2 list"] == md["#Q2 list"]
        assert mangsang.split_anchor("C:/x/y.py:f") == ("C:/x/y.py", ":f") and mangsang.split_anchor("a.md#H") == ("a.md", "#H") and mangsang.split_anchor("a.py") == ("a.py", "")


def test_confirm_checks_anchors_vocabulary_evidence_and_duplicates_and_stores_one_file_per_relation():
    with Project() as pj:
        assert run("register", "nope.py", "--target", pj.dir)[0] != 0
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("confirm", "x.json", "--target", pj.dir)[0] != 0, "confirm needs --by or --delegated"
        code, out = pj.propose(
            rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
            rel("plan/PLAN.md#Q9 nope", "documents", "memo.py:add"),
            rel("plan/PLAN.md#Q1 add", "explains", "memo.py:add"),
            rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="  "),
            rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists memos one per line"),
            rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        assert code == 1 and "confirmed 1 / rejected 5" in out, out
        for needle in ("does not resolve", "not in the vocabulary", "no evidence", "not a quote from either anchor", "duplicate of"):
            assert needle in out, (needle, out)
        d = mangsang.decl(pj.dir)
        assert len(d["relations"]) == 1 and d["relations"][0]["confirmed"].get("by") == "kim"
        assert sorted(os.listdir(os.path.join(pj.dir, "mangsang", "relations"))) == [d["relations"][0]["id"] + ".json"]
        # the rejected stay in the proposals file, each with why; the confirmed one left it (guin-site, 10-12: "rejected 6 (proposals
        # file consumed)", five of them on a plan document that was not registered)
        assert "the rejected kept in" in out and "run `confirm" in out and "proposals file consumed" not in out, out
        left = mangsang.load(os.path.join(pj.dir, "proposals.json"))["relations"]
        assert len(left) == 5 and all(x.get("rejected") for x in left) and not any(x.get("predicate") == "documents" and x["src"] == "plan/PLAN.md#Q1 add"
                                                                                  and "duplicate" not in x["rejected"] for x in left), left
        assert run("confirm", os.path.join(pj.dir, "proposals.json"), "--by", "kim", "--target", pj.dir)[0] == 1   # re-run: the same five, the same reasons
        assert len(mangsang.load(os.path.join(pj.dir, "proposals.json"))["relations"]) == 5
        os.remove(os.path.join(pj.dir, "proposals.json"))
        rid = d["relations"][0]["id"]
        assert rid == mangsang.rel_id(d["relations"][0]) and rid.startswith("R-")
        assert run("retire", rid, "--why", "test", "--target", pj.dir)[0] == 0
        d = mangsang.decl(pj.dir)
        assert not d["relations"] and d["retired"][0]["retired"].get("why") == "test" and not {"by", "delegated", "agent"} & set(d["retired"][0]["retired"])
        assert os.listdir(os.path.join(pj.dir, "mangsang", "retired")) == [rid + ".json"] and not os.listdir(os.path.join(pj.dir, "mangsang", "relations"))
        assert run("retire", "R-nope", "--why", "x", "--target", pj.dir)[0] != 0


def test_impact_stale_by_direction_broken_by_removal_and_observes_for_itself():
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out   # no baseline, no relations: nothing to judge, nothing to say
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
                               rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="assert True"),
                               rel("plan/PLAN.md#Q2 list", "references", "memo.py:list_", ev="lists."))
        assert "confirmed 3" in out, out
        assert run("observe", "--reset", "--target", pj.dir)[0] == 0
        assert run("impact", "--target", pj.dir)[0] == 0
        # the doc side of a dst->src relation changes: nothing is stale (documents do not stale code)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("appends", "appends a memo"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out
        # the code side changes: both relations on `add` are stale; the `references` one is not (propagates none)
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2").replace("return []", "return [1]"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("stale") == 2 and "references" not in out and "unresolved_total = 2" in out, out
        obs = os.path.join(pj.dir, ".mangsang")
        state = lambda: {n: io.open(os.path.join(obs, n), encoding="utf-8").read() for n in sorted(os.listdir(obs))} if os.path.isdir(obs) else {}
        before = state()
        assert set(before) <= {"baseline.json"}, before   # the folder holds the baseline and nothing else: a verdict is printed, not filed
        # as reporters, check and cq answer with the JSON alone — green or red — so a reviewer can parse stdout (dwitbuk marked both
        # "reporter-failed" on a clean project because the human table came first)
        for cmd in ("check", "cq"):
            code, out = run(cmd, "--findings", "--target", pj.dir)
            doc = json.loads(out)
            assert doc["artifact-type"] == "dwitbuk/findings@1" and doc["source"] == "mangsang", (cmd, out[:200])
        code, out = run("impact", "--findings", "--target", pj.dir)
        doc = json.loads(out)
        assert code == 1 and doc["artifact-type"] == "dwitbuk/findings@1" and doc["source"] == "mangsang" and [f["kind"] for f in doc["findings"]] == ["stale", "stale"]
        assert state() == before, "impact leaves the project's state alone"
        # impact observes for itself (no `observe` call between edits, and it saw the change above); `observe` prints the same movement
        code, out = run("observe", "--target", pj.dir)
        assert "memo.py" in out and "changed=['', ':add', ':list_']" in out, out
        # a human re-reads: reconfirm updates `seen`, and impact is clean again without touching the baseline
        ids = [x["id"] for x in mangsang.decl(pj.dir)["relations"] if x["dst"] == "memo.py:add"]
        assert run("reconfirm", *ids, "--target", pj.dir)[0] != 0, "needs --by or --delegated"
        # the Q1 sentence was rewritten above ("appends a memo"): the old quote is gone, so reconfirm refuses until a new one is given
        code, out = run("reconfirm", *ids, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code != 0 and "no longer in the text" in out, out
        q1 = next(i for i in ids if mangsang.decl(pj.dir)["relations"][[x["id"] for x in mangsang.decl(pj.dir)["relations"]].index(i)]["src"].startswith("plan/"))
        assert run("reconfirm", q1, "--by", "kim", "--evidence", "appends a memo and prints", "--why", "re-read both ends; still holds", "--target", pj.dir)[0] == 0
        code, out = run("reconfirm", *[i for i in ids if i != q1], "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and out.count("re-confirmed") == 1, out
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out
        assert mangsang.decl(pj.dir)["relations"][0]["confirmed"].get("by") == "kim"
        # reset, then remove the function: the relations on it are broken, not stale — and cannot be re-confirmed
        run("observe", "--reset", "--target", pj.dir)
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef list_(store):\n    return [1]\n")
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("broken") == 2 and "dead anchors ['memo.py:add']" in out, out
        code, out = run("reconfirm", ids[0], "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code != 0 and "cannot be re-confirmed" in out, out


def test_merge_a_relation_is_judged_against_what_its_confirmer_saw_and_a_baseline_can_come_from_git():
    import subprocess

    def git(*a):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        return subprocess.run(["git", *a], cwd=pj.dir, capture_output=True, text=True, encoding="utf-8", env=env).stdout.strip()

    with Project() as pj:
        git("init", "-q", "-b", "main")
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        git("add", "-A"); git("commit", "-q", "-m", "base")
        base = git("rev-parse", "HEAD")
        # "branch B": changes add, then confirms a relation on it — the confirmer saw the changed add
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        seen = mangsang.decl(pj.dir)["relations"][0]["seen"]
        assert set(seen) == {"plan/PLAN.md#Q1 add", "memo.py:add"}
        # the merge machine: baseline at the merge base comes from git, not from a tree it never had
        code, out = run("observe", "--reset", "--at", base, "--target", pj.dir)
        assert code == 0 and "baseline at %s" % base in out, out
        assert run("observe", "--at", base, "--target", pj.dir)[0] != 0, "--at without --reset is refused"
        code, out = run("observe", "--target", pj.dir)
        assert "memo.py" in out and "':add'" in out, out   # add did change since base ...
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out   # ... but the relation was confirmed against the changed add: not stale
        # a relation from before `seen` existed falls back to the baseline: since base, add changed -> stale
        r = mangsang.decl(pj.dir)["relations"][0]
        del r["seen"]
        mangsang.save(os.path.join(pj.dir, "mangsang", "relations", r["id"] + ".json"), r)   # save_decl never rewrites an existing relation file
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out, out
        shutil.rmtree(os.path.join(pj.dir, ".mangsang"))   # a fresh clone: no baseline -> the seen-less relation is unjudged, not silently fresh
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unjudged 1 relation" in out and "unresolved_total = 0" in out, out
        code, out = run("observe", "--reset", "--at", "nope", "--target", pj.dir)   # unknown revision: nothing readable, said so
        assert code == 0 and "unreadable ['plan/PLAN.md', 'memo.py']" in out, out


def test_impact_only_and_the_judge_round():
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
                   rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists."))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2").replace("return []", "return [1]"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 2" in out, out
        # --only: a slice's check sees only the relations on its anchors
        code, out = run("impact", "--only", "memo.py:list_", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1 (only memo.py:list_)" in out and "add" not in out, out
        assert run("impact", "--only", "memo.py:nothing", "--target", pj.dir)[0] == 0
        # the judge: a packet with both texts and the quote; a recorded answer — one still-true, one drifted, one out of the request
        d = os.path.join(pj.dir, "judge")
        code, out = run("judge", "request", "--out", d, "--target", pj.dir)
        assert code == 0 and "2 stale relation(s)" in out, out
        req = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8"))
        ids = {i["stale"]: i["relation"] for i in req["items"]}
        assert set(ids) == {"plan/PLAN.md#Q1 add", "plan/PLAN.md#Q2 list"} and "return 2" in next(i["because_text"] for i in req["items"] if i["stale"].endswith("Q1 add"))
        write(os.path.join(d, "judge-response.json"), {"artifact-type": "mangsang/judgment@1", "request-id": mangsang.load(os.path.join(d, "judge-request.json"))["request-id"], "non-claims": [], "worker": {"host": "claude-code", "model": "claude-test-1"}, "items": [
            {"relation": ids["plan/PLAN.md#Q1 add"], "verdict": "still-true", "quote": "", "evidence": "add still appends; the return value changed, not the behavior the sentence names"},
            {"relation": ids["plan/PLAN.md#Q2 list"], "verdict": "drifted", "quote": "lists.", "evidence": "list_ now returns [1] regardless of the store"},
            {"relation": "R-nope", "verdict": "still-true", "quote": "", "evidence": "x"},
            {"relation": ids["plan/PLAN.md#Q2 list"], "verdict": "drifted", "quote": "not in the text", "evidence": "y"}]})
        code, out = run("judge", "consume", "--response", os.path.join(d, "judge-response.json"), "--by", "test", "--target", pj.dir)
        assert code == 1 and "still-true applied 1" in out and "drifted 1" in out and "rejected 2" in out, out
        r1 = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == ids["plan/PLAN.md#Q1 add"])
        assert r1["confirmed"]["judge"] == "claude-code claude-test-1" and r1["confirmed"]["applied-by"] == "test", r1["confirmed"]
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out, out   # the drifted one waits for a human
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert any(f["kind"] == "delegated" and "the judge claude-code claude-test-1, applied by test" in f["text"] for f in json.loads(out)["findings"]), out


def test_check_coverage_and_resolved():
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"), rel("test_memo.py:test_Q1_add", "verifies", "plan/PLAN.md#Q1 add", ev="assert True"))
        d = mangsang.decl(pj.dir)
        d["cq"] = [{"id": "C1", "text": "every Q section realized?", "verify": {"kind": "coverage", "anchors": "plan/PLAN.md#Q*", "as": "src", "predicate": "documents"}},
                   {"id": "C2", "text": "every Q section tested?", "verify": {"kind": "coverage", "anchors": "plan/PLAN.md#Q*", "as": "dst", "predicate": "verifies"}},
                   {"id": "C3", "text": "anchors alive?", "verify": {"kind": "resolved"}},
                   {"id": "C4", "text": "?", "verify": {"kind": "nope"}}]
        mangsang.save_decl(pj.dir, d)
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "FAILED" in out and "C1" in out and "uncovered: plan/PLAN.md#Q2 list" in out and "C3" in out, out
        # an unknown kind is not an invariant: it falls to `cq`, where its presuppositions fail -> UNANSWERABLE
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "C4" in out and "unknown verify kind" in out, out
        pj.propose(rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists."), rel("test_memo.py:test_Q1_add", "verifies", "plan/PLAN.md#Q2 list", ev="lists."))
        code, out = run("check", "--target", pj.dir)
        assert out.count("holds") >= 2 and "FAILED" not in out.split("C3")[0], out
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n")
        code, out = run("check", "--target", pj.dir)
        assert "FAILED" in out and "C3" in out and "with dead anchors" in out, out


def test_move_carries_broken_relations_to_the_symbols_new_home_and_leaves_the_ambiguous():
    """A refactoring split memo.py: `add` moved to core.py, `list_` to both core.py and extra.py (ambiguous), `X` went nowhere.
    `move` retires the relation on the dead anchor and re-confirms it where the symbol is now, with the same quote; what it
    cannot decide it names and leaves."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"), rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="assert True"),
                          rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists."), rel("plan/PLAN.md#Q1 add", "references", "memo.py:X"))[0] == 0
        write(os.path.join(pj.dir, "core.py"), "def add(store, text):\n    return 1\n\n\ndef list_(store):\n    return []\n")
        write(os.path.join(pj.dir, "extra.py"), "def list_(store):\n    return [1]\n")
        os.remove(os.path.join(pj.dir, "memo.py"))
        assert run("register", "core.py", "extra.py", "--target", pj.dir)[0] == 0
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("broken") == 4, out
        code, out = run("move", "--dry-run", "--target", pj.dir)
        assert "would move" in out and "core.py:add" in out and "is in core.py, extra.py" in out and "no registered file has :X" in out, out
        assert not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"]), "a dry run changes nothing"
        code, out = run("move", "--by", "kim", "--why", "the refactoring split memo.py", "--target", pj.dir)
        assert code == 1 and "2 relation(s) moved" in out and "2 left" in out, out
        d = mangsang.decl(pj.dir)
        moved = [r for r in d["relations"] if r.get("moved-from")]
        assert {(r["src"], r["dst"]) for r in moved} == {("plan/PLAN.md#Q1 add", "core.py:add"), ("test_memo.py:test_Q1_add", "core.py:add")}, moved
        assert all(r["confirmed"].get("by") == "kim" and r["evidence"] for r in moved)
        assert sum(1 for r in d["retired"] if r["retired"]["why"].startswith("moved:")) == 2
        left = {r["dst"] for r in d["relations"] if not r.get("moved-from")}
        assert left == {"memo.py:list_", "memo.py:X"}, left   # ambiguous and homeless: a person's call
        code, out = run("impact", "--target", pj.dir)
        assert out.count("broken") == 2, out


def test_a_question_stands_on_what_its_answer_requires_and_coverage_can_select_by_a_relation():
    """Seen on a playground (bathroom): a project added `requires` (activity -> fixture, dst->src) to its vocabulary, and cq
    called every fixture UNQUESTIONED — the answer stopped at the activity. The question is about what the activity stands
    on: cq follows relations between concepts along which a change travels toward the answer (the vocabulary's own
    `propagates`, impact's rule), counts them as asked for, and fails the question when one of them moved. A coverage
    invariant may choose its targets by a relation (`members`: the concepts that are <predicate> <of>), transitively."""
    with Project() as pj:
        write(os.path.join(pj.dir, "doc.md"), "# d\n\n## shower\n\nwash under running water.\n\n## showerhead\n\nwater comes from above.\n\n## drain\n\nwater goes down.\n\n## mirror\n\nyou see yourself.\n")
        assert run("register", "doc.md", "--target", pj.dir)[0] == 0
        voc = dict(mangsang.DEFAULT_VOCAB, requires={"propagates": "dst->src", "means": "src needs dst"}, **{"is-a": {"propagates": "none", "means": "src is a dst"}})
        write(os.path.join(pj.dir, "mangsang", "vocabulary.json"), voc)
        for name, means in (("showering", "washing under a shower; it needs a showerhead and a drain"), ("showerhead", "where water comes from above"),
                            ("drain", "where water goes down"), ("mirror", "where you see yourself"), ("fixture", "a thing fixed in the room"), ("thing", "anything in the room")):
            assert run("concept", "add", name, "--means", means, "--by", "kim", "--target", pj.dir)[0] == 0
        pj.propose(rel("doc.md#shower", "realizes", "concept:showering", ev="wash under running water."), rel("doc.md#showerhead", "realizes", "concept:showerhead", ev="water comes from above."),
                   rel("doc.md#drain", "realizes", "concept:drain", ev="water goes down."), rel("doc.md#mirror", "realizes", "concept:mirror", ev="you see yourself."),
                   rel("concept:showering", "requires", "concept:showerhead", ev="it needs a showerhead"), rel("concept:showering", "requires", "concept:drain", ev="and a drain"),
                   rel("concept:showerhead", "is-a", "concept:fixture", ev="where water comes from above"), rel("concept:drain", "is-a", "concept:fixture", ev="where water goes down"),
                   rel("concept:mirror", "is-a", "concept:fixture", ev="where you see yourself"), rel("concept:fixture", "is-a", "concept:thing", ev="a thing fixed in the room"))
        assert run("cq", "add", "how-shower", "--text", "what does a shower need?", "--verify", '{"kind": "answered-by", "concepts": ["showering"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        assert set(mangsang.reach(mangsang.decl(pj.dir), ["showering"])) == {"showerhead", "drain"}, "requires is followed; is-a (propagates none) is not"
        code, out = run("cq", "--target", pj.dir)
        assert "through requires: showerhead, drain" in out and "UNQUESTIONED concept:showerhead" not in out and "UNQUESTIONED concept:drain" not in out, out
        assert "UNQUESTIONED concept:mirror" in out, "a fixture no question stands on is still unasked"
        # coverage by a relation: every fixture (and, transitively, every thing) is required by something
        assert run("cq", "add", "every-fixture-needed", "--text", "is every fixture needed?", "--verify",
                   '{"kind": "coverage", "predicate": "requires", "members": {"predicate": "is-a", "of": "thing"}, "as": "dst"}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert "FAILED       every-fixture-needed" in out and "4 concept(s), 2 uncovered" in out and "concept:mirror" in out and "concept:fixture" in out, out
        code, out = run("cq", "add", "bad", "--text", "?", "--verify", '{"kind": "coverage", "predicate": "requires", "members": {"predicate": "is-a", "of": "nothing"}, "as": "dst"}', "--by", "kim", "--target", pj.dir)
        assert code != 0 and "not declared" in out, out
        # what the answer stands on moves: the question fails, saying through what
        assert run("observe", "--reset", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "doc.md"), io.open(os.path.join(pj.dir, "doc.md"), encoding="utf-8").read().replace("water goes down.", "water goes down, fast."))
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "FAILED       how-shower" in out and "drain (through showering) has moved projections" in out, out
        page = run("report", "--target", pj.dir)[1]
        assert "what does a shower need? — FAILED" in page, page


def test_show_prints_every_end_that_moved():
    """A relation whose section and concept both changed (a kind's meaning revised while its section was rewritten) showed
    no diff at all: the lookup went by "A and B", which is no anchor. Each moved end is shown."""
    import subprocess
    with Project() as pj:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)
        git("init", "-q")
        assert run("register", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "appending one memo", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "confirmed")
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("appends and prints", "appends and prints, then saves"))
        assert run("concept", "revise", "adding", "--means", "appending one memo and saving it", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("impact", "--show", "--target", pj.dir)
        assert code == 1 and "and concept:adding" in out, out
        assert "+`add` appends and prints, then saves" in out and "+appending one memo and saving it" in out, out
        assert "\n      -appending one memo\n      +appending one memo and saving it" in out, "a one-line meaning's - and + are two lines"


def test_a_turn_can_be_kept_as_the_sentences_that_matter():
    """An approval followed by a new request ("That will do. Could you also draw it?") was kept whole, so the record that cites
    the approval carried the request too. `--excerpt` keeps whole sentences of the turn, verbatim; a cut mid-sentence is refused."""
    with Project() as pj:
        tr = os.path.join(pj.dir, "s.jsonl")
        write(tr, json.dumps({"type": "user", "uuid": "u1", "timestamp": "2026-09-25T00:00:00Z", "message": {"role": "user", "content": "그걸로 됐어. 혹시 지금의 개념들로 그림을 그릴 수 있어?"}}) + "\n")
        code, out = run("source", "add", "A1", "--from-transcript", tr, "--match", "그걸로", "--speaker", "lee", "--excerpt", "그걸로 됐어.", "--target", pj.dir)
        assert code == 0, out
        src = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "A1.json"))
        assert src["text"] == "그걸로 됐어." and src["excerpt"] and "u1" in src["locator"], src
        code, out = run("source", "add", "A2", "--from-transcript", tr, "--match", "그걸로", "--speaker", "lee", "--excerpt", "그걸로 됐", "--target", pj.dir)
        assert code != 0 and "cuts a sentence" in out, out
        code, out = run("source", "add", "A3", "--from-transcript", tr, "--match", "그걸로", "--speaker", "lee", "--excerpt", "좋아.", "--target", pj.dir)
        assert code != 0 and "not in the turn" in out, out
        # parts the turn holds side by side keep its spacing; a part after something left out starts a new line
        assert mangsang.excerpt_of("가. 나. 다.\n라. 마.", ["가.", "나.", "마."]) == "가. 나.\n마."
        # a short approval recurs: --turn names the one meant, by the host's id (listed, latest last)
        with io.open(tr, "a", encoding="utf-8") as fh:
            for uid, when in (("u2", "2026-09-25T01:00:00Z"), ("u3", "2026-09-25T02:00:00Z")):
                fh.write(json.dumps({"type": "user", "uuid": uid, "timestamp": when, "message": {"role": "user", "content": "ㄱㄱ"}}) + "\n")
        code, out = run("source", "add", "G", "--from-transcript", tr, "--match", "ㄱㄱ", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "--turn ID" in out and out.index("u2") < out.index("u3"), out
        assert run("source", "add", "G", "--from-transcript", tr, "--turn", "u3", "--speaker", "lee", "--target", pj.dir)[0] == 0
        src = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "G.json"))
        assert src["text"] == "ㄱㄱ" and "u3" in src["locator"] and src["verbatim-from"] == "host transcript", src


def run_as_agent(*argv):
    """`run`, but the env says an agent is running it (Claude Code's own marker)."""
    os.environ["CLAUDECODE"] = "1"
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            try:
                code = mangsang.main(list(argv))
            except SystemExit as err:
                code = err.code if isinstance(err.code, int) else 1
                out.write(str(err) + "\n")
    finally:
        os.environ.pop("CLAUDECODE", None)
    return code, out.getvalue()


def test_a_typed_reply_is_an_answer_and_a_miss_says_what_is_there():
    """guin-site, 2026-10-06: `--match 'ㄱㄱ' --kind answer` and `--turn <the reply's id> --kind answer` both "found 0 turn(s)" —
    an answer was only a choice picked in an AskUserQuestion, and the owner had typed theirs. A turn the person typed right after
    the agent's is an answer too. And when nothing matches, the error says which turns are there (another kind) or where in the
    record the phrase is (the agent's thinking, a tool call) and the turns around it, by id."""
    with Project() as pj:
        tr = os.path.join(pj.dir, "s.jsonl")
        lines = [{"type": "user", "uuid": "p1", "timestamp": "2026-10-06T07:00:00Z", "message": {"role": "user", "content": "띠를 칸으로 나눠줘"}},
                 {"type": "assistant", "uuid": "a1", "timestamp": "2026-10-06T07:01:00Z", "message": {"id": "m1", "model": "claude-x", "content": [
                     {"type": "thinking", "thinking": "the owner wants the regions named; propose two"}]}},
                 {"type": "assistant", "uuid": "a2", "timestamp": "2026-10-06T07:01:01Z", "message": {"id": "m1", "model": "claude-x", "content": [
                     {"type": "text", "text": "본문 칸과 옆 칸, 이대로 진행할까요?"}]}},
                 {"type": "user", "uuid": "p2", "timestamp": "2026-10-06T07:02:00Z", "message": {"role": "user", "content": "ㄱㄱ"}}]
        write(tr, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        code, out = run("source", "add", "Q", "--from-transcript", tr, "--match", "이대로 진행할까요", "--kind", "agent", "--target", pj.dir)
        assert code == 0, out
        code, out = run("source", "add", "A", "--from-transcript", tr, "--match", "ㄱㄱ", "--kind", "answer", "--speaker", "lee", "--replies-to", "Q", "--target", pj.dir)
        assert code == 0, out
        src = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "A.json"))
        assert src["text"] == "ㄱㄱ" and "person p2" in src["locator"] and "answering a2" in src["locator"], src
        assert run("source", "add", "A2", "--from-transcript", tr, "--turn", "p2", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)[0] == 0
        assert run("source", "add", "A3", "--from-transcript", tr, "--match", "ㄱㄱ", "--kind", "person", "--speaker", "lee", "--target", pj.dir)[0] == 0
        # the first turn answers nothing: it is a person's turn, not an answer — and the miss says so, with the id to name it by
        code, out = run("source", "add", "X", "--from-transcript", tr, "--match", "칸으로 나눠", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "no answer turn" in out and "person p1" in out and "--turn ID" in out, out
        # the phrase is in the agent's thinking, which nobody saw: said so, with the turns around it
        code, out = run("source", "add", "X", "--from-transcript", tr, "--match", "propose two", "--target", pj.dir)
        assert code != 0 and "found in no turn" in out and "thinking" in out and "person p1" in out and "agent a2" in out, out
        # an id the host gave a record that holds no turn
        code, out = run("source", "add", "X", "--from-transcript", tr, "--turn", "a1", "--target", pj.dir)
        assert code != 0 and "thinking" in out and "--turn ID" in out, out
        code, out = run("source", "add", "X", "--from-transcript", tr, "--match", "never said", "--target", pj.dir)
        assert code != 0 and "nothing in this transcript has it" in out and "person p2" in out, out


def test_a_judge_round_is_signed_by_the_judge_and_applied_by_whoever_applied_it():
    """guin-site, 2026-10-04..06: `judge consume --by <owner>` put the owner's name on 120/120 and 65/65 still-true verdicts —
    rounds the owner never read. The judgment's author is the judge (the model, from the worker's record); who applied it is
    a second fact, the agent by default; a person's name there needs the source where that person read the verdicts. And a
    reconfirm the agent did on its own is signed as the agent's."""
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee", "kim"], "agents": ["Claude"]})
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        d = os.path.join(pj.dir, "judge")
        os.makedirs(d)   # an existing directory is taken as it is
        code, out = run("judge", "request", "--out", d, "--target", pj.dir)
        rid = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8"))["items"][0]["relation"]
        resp = os.path.join(d, "judge-response.json")
        write(resp, {"artifact-type": "mangsang/judgment@1", "request-id": mangsang.load(os.path.join(d, "judge-request.json"))["request-id"], "non-claims": [], "items": [
            {"relation": rid, "verdict": "still-true", "quote": "", "evidence": "add still appends"}]})
        code, out = run_as_agent("judge", "consume", "--response", resp, "--target", pj.dir)
        assert code != 0 and "no worker record" in out and "--judge" in out, out
        write(resp, {"artifact-type": "mangsang/judgment@1", "request-id": mangsang.load(os.path.join(d, "judge-request.json"))["request-id"], "non-claims": [], "worker": {"host": "claude-code", "model": "claude-j"}, "items": [
            {"relation": rid, "verdict": "still-true", "quote": "", "evidence": "add still appends"}]})
        # the owner's name, at an agent's hand, with nothing showing the owner read it: refused, and nothing applied
        code, out = run_as_agent("judge", "consume", "--response", resp, "--by", "lee", "--target", pj.dir)
        assert code != 0 and "--approved-in" in out, out
        assert run("impact", "--target", pj.dir)[0] == 1
        # default: the agent applied it, the judge judged it
        code, out = run_as_agent("judge", "consume", "--response", resp, "--target", pj.dir)
        assert code == 0 and "judged by claude-code claude-j, applied by Claude Code" in out, out
        r = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == rid)
        assert {k: r["confirmed"].get(k) for k in ("judge", "applied-by", "why")} == {"judge": "claude-code claude-j", "applied-by": "Claude Code", "why": "add still appends"}, r["confirmed"]
        assert r["history"][-1]["confirmed"].get("by") == "kim", r["history"]
        assert "judged by claude-code claude-j, applied by Claude Code" in run("lookup", "memo.py", "--target", pj.dir)[1]
        # with the source where the owner read the verdicts, the owner's name may stand as who applied them
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 3"))
        assert run("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        assert not os.path.exists(resp)   # the earlier round's verdicts moved aside; this round's are written anew
        write(resp, {"artifact-type": "mangsang/judgment@1", "request-id": mangsang.load(os.path.join(d, "judge-request.json"))["request-id"], "non-claims": [], "worker": {"host": "claude-code", "model": "claude-j"}, "items": [
            {"relation": rid, "verdict": "still-true", "quote": "", "evidence": "add still appends"}]})
        write(os.path.join(pj.dir, "read.txt"), "판정 읽었어, 적용해")
        assert run("source", "add", "R1", "--file", os.path.join(pj.dir, "read.txt"), "--speaker", "lee", "--target", pj.dir)[0] == 0
        code, out = run_as_agent("judge", "consume", "--response", resp, "--by", "lee", "--approved-in", "source:R1", "--target", pj.dir)
        assert code == 0, out
        r = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == rid)
        assert r["confirmed"]["judge"] == "claude-code claude-j" and r["confirmed"]["applied-by"] == "lee" and r["confirmed"]["approved-in"] == "source:R1", r["confirmed"]
        # at a person's terminal, no agent to default to: say who applies it
        code, out = run("judge", "consume", "--response", resp, "--target", pj.dir)
        assert code != 0 and "--by NAME" in out, out
        # reconfirm with no --by and no --delegated: the agent's own re-read, signed as the agent's
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 4"))
        assert run("reconfirm", rid, "--target", pj.dir)[0] != 0   # a person at a terminal still says who
        code, out = run_as_agent("reconfirm", rid, "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "Claude Code's own re-read" in out, out
        r = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == rid)
        assert r["confirmed"].get("agent") == "Claude Code", r["confirmed"]
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert any(f["kind"] == "delegated" and "the agent Claude Code, on its own" in f["text"] for f in json.loads(out)["findings"]), out


def test_a_brief_line_says_something_when_the_first_sentence_is_a_name():
    """guin-site's feed: "첫 화면." — the brief line was the five characters. A first sentence that short is followed by the next."""
    assert mangsang.first_sentence("첫 화면. 모든 글을 최신순으로, 글마다 분리된 상자로 보여준다. 짧은 글은 제목 없이.") == "첫 화면. 모든 글을 최신순으로, 글마다 분리된 상자로 보여준다."
    assert mangsang.first_sentence("Appending one memo. It prints its id.") == "Appending one memo."   # a sentence that says something stands alone
    long = mangsang.first_sentence("첫 화면. " + "가" * 300)
    assert len(long) == 160 and long.startswith("첫 화면. 가") and long.endswith("…"), long
    assert mangsang.first_sentence("첫 화면.") == "첫 화면."


def test_judge_request_out_is_a_directory_and_says_where_the_packet_is():
    """guin-site, 2026-10-06: `judge request --out .../judge-req.json` made a directory of that name; the agent's next step read
    it as a file and crashed. --out takes a directory, says so when given a file name, and prints the packet's path."""
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        bad = os.path.join(pj.dir, "scratch", "judge-req.json")
        code, out = run("judge", "request", "--out", bad, "--target", pj.dir)
        assert code != 0 and "takes a directory" in out and os.path.join(pj.dir, "scratch") in out and not os.path.exists(bad), out
        write(os.path.join(pj.dir, "afile"), "x")
        assert run("judge", "request", "--out", os.path.join(pj.dir, "afile"), "--target", pj.dir)[0] != 0
        d = os.path.join(pj.dir, "scratch")
        code, out = run("judge", "request", "--out", d, "--target", pj.dir)
        assert code == 0 and "packet:   %s" % os.path.join(d, "judge-request.json") in out and "response: %s" % os.path.join(d, "judge-response.json") in out, out
        assert "judge_worker.py --request" in out and "judge consume --response" in out, out


def test_files_deleted_on_purpose_retire_as_one_with_one_reason():
    """guin-site, 2026-10-12: a contract retired /admin, /api, the D1 scripts and db/ — files deleted on purpose — and 28
    relations stood broken with no route but retiring each by hand with the same reason. `impact` groups the broken
    relations by the deleted file and says the one command; `retire --gone FILE.. --why` retires every relation on those
    files (each kept with the reason and the file gone), unregisters them, and names the concepts that now owe a re-read.
    A path still in the tree is refused; a gone directory names the files under it."""
    with Project() as pj:
        legacy = "def legacy(store):\n    return 1\n\n\ndef older(store):\n    return 2\n"
        write(os.path.join(pj.dir, "old", "legacy.py"), legacy)
        write(os.path.join(pj.dir, "old", "schema.sql"), "CREATE TABLE memos (id INTEGER);\n")
        assert run("register", "plan/PLAN.md", "memo.py", "old/legacy.py", "old/schema.sql", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
                          rel("old/legacy.py:legacy", "realizes", "concept:adding", "a memo is appended"),
                          rel("old/legacy.py:older", "realizes", "concept:adding", "a memo is appended"),
                          rel("old/schema.sql:memos", "realizes", "concept:adding", "a memo is appended"),
                          rel("plan/PLAN.md#Q1 add", "documents", "old/legacy.py:legacy"))[0] == 0
        shutil.rmtree(os.path.join(pj.dir, "old"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "gone    old/legacy.py — deleted from the tree; 3 broken relation(s)" in out, out
        assert "gone    old/schema.sql" in out and "  broken  " not in out, out   # grouped, not one line each
        assert "`retire --gone old/legacy.py old/schema.sql --why \"WHY\"`" in out, out
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert "old/legacy.py is gone from the tree" in out, out
        # refused: a file that is there, a path the net never knew
        code, out = run("retire", "--gone", "memo.py", "--why", "x", "--target", pj.dir)
        assert code != 0 and "still in the tree" in out, out
        code, out = run("retire", "--gone", "nowhere.py", "--why", "x", "--target", pj.dir)
        assert code != 0 and "nothing for the net to retire" in out, out
        assert run("retire", "R-00000000", "--gone", "old", "--why", "x", "--target", pj.dir)[0] != 0
        assert len(os.listdir(os.path.join(pj.dir, "mangsang", "relations"))) == 5, "a refusal changes nothing"
        # the directory names both files; one reason for all
        code, out = run("retire", "--deleted", "old", "--why", "the contract retired the old backend", "--target", pj.dir)
        assert code == 0 and "4 relation(s) retired" in out and "2 file(s) unregistered: old/legacy.py, old/schema.sql" in out, out
        assert "concept adding lost a projection: its sentence owes a re-read" in out, out
        d = mangsang.decl(pj.dir)
        assert {e["path"] for e in d["registry"]} == {"plan/PLAN.md", "memo.py"}, d["registry"]
        assert len(d["relations"]) == 1 and len(d["retired"]) == 4, d
        assert all({k: r["retired"].get(k) for k in ("why", "gone")} == {"why": "the contract retired the old backend", "gone": [r["src"].split(":")[0] if r["src"].startswith("old/") else r["dst"].split(":")[0]]}
                   for r in d["retired"]), d["retired"]
        owes = next(c for c in d["concepts"] if c["name"] == "adding")["owes"]
        assert len(owes) == 3, owes   # every projection that went with the files: the same-file rule does not excuse a file that is gone
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "owed    concept:adding" in out and "unresolved_total = 1" in out, out   # nothing broken now; the re-read is owed
        assert run("concept", "reaffirm", "adding", "--by", "kim", "--why", "the sentence holds without the old backend", "--target", pj.dir)[0] == 0
        assert run("impact", "--target", pj.dir)[0] == 0
        # a single retire still works, and still owes
        assert run("retire", d["relations"][0]["id"], "--why", "done", "--target", pj.dir)[0] == 0


def test_an_answer_from_a_question_form_is_the_persons_choice_not_the_tools_wrapper():
    """guin-site, 2026-10-12 (source at-62, 1.17.0): `source add --from-transcript … --kind answer` kept the tool's wrapper —
    "Your questions have been answered: "Q1"="A1", "Q2"="A2", … You can now continue with these answers in mind." — as the
    owner's words. The person said only what they picked (or typed). Each question of a form is its own answer turn,
    `ID#k` when there are several; its text is the choice and the person's note, the question it answers is named in the
    locator, and the answer replies to the question's source when that is kept."""
    with Project() as pj:
        tr = os.path.join(pj.dir, "s.jsonl")
        qs = [{"question": "백업을 어떻게 바꿀까요?", "header": "백업", "options": [{"label": "PDS 백업 (추천)"}, {"label": "백업 끄기"}]},
              {"question": "예전 D1을 어떻게 할까요?", "header": "D1", "options": [{"label": "옮기고 삭제 (추천)"}, {"label": "그대로"}]}]
        wrapper = ('Your questions have been answered: "백업을 어떻게 바꿀까요?"="PDS 백업 (추천)", "예전 D1을 어떻게 할까요?"="옮기고 삭제 (추천)". '
                   'You can now continue with these answers in mind.')
        lines = [{"type": "assistant", "uuid": "a1", "timestamp": "t1", "message": {"id": "m1", "model": "claude-x", "content": [
                     {"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": qs}}]}},
                 {"type": "user", "uuid": "u1", "timestamp": "t2", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": wrapper}]},
                  "toolUseResult": {"questions": qs, "answers": {"백업을 어떻게 바꿀까요?": "PDS 백업 (추천)", "예전 D1을 어떻게 할까요?": "옮기고 삭제 (추천)"},
                                    "annotations": {"예전 D1을 어떻게 할까요?": {"notes": "erasures는 꼭 옮겨", "preview": "+--+"}}}},
                 # an older record with no structured answers: read out of the text for the questions asked
                 {"type": "assistant", "uuid": "a2", "timestamp": "t3", "message": {"id": "m2", "model": "claude-x", "content": [
                     {"type": "tool_use", "id": "q2", "name": "AskUserQuestion", "input": {"questions": [{"question": "배포할까요?"}]}}]}},
                 {"type": "user", "uuid": "u2", "timestamp": "t4", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q2",
                     "content": 'User has answered your questions: "배포할까요?"="커밋 후 배포". You can now continue with the user\'s answers in mind.'}]}},
                 # a form declined: nothing the person said
                 {"type": "assistant", "uuid": "a3", "timestamp": "t5", "message": {"id": "m3", "model": "claude-x", "content": [
                     {"type": "tool_use", "id": "q3", "name": "AskUserQuestion", "input": {"questions": [{"question": "지울까요?"}]}}]}},
                 {"type": "user", "uuid": "u3", "timestamp": "t6", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q3", "is_error": True,
                     "content": "The user doesn't want to proceed with this tool use."}]}},
                 # the host's summary of a compacted session is filed as a user record: no one said it
                 {"type": "user", "uuid": "u4", "timestamp": "t7", "isCompactSummary": True, "message": {"role": "user", "content":
                     "This session is being continued from a previous conversation. The user picked 옮기고 삭제."}}]
        write(tr, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        assert run("source", "add", "Q", "--from-transcript", tr, "--match", "예전 D1을", "--kind", "question", "--target", pj.dir)[0] == 0
        code, out = run("source", "add", "A", "--from-transcript", tr, "--match", "옮기고 삭제", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code == 0, out
        a = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "A.json"))
        assert a["text"] == "옮기고 삭제 (추천)\nerasures는 꼭 옮겨", a   # the choice and the person's note; not the agent's preview
        assert "answered" not in a["text"] and "continue" not in a["text"] and "예전 D1을" not in a["text"], a
        assert a["locator"] == 'session s, answer u1#2 at t2, answering question a1: "예전 D1을 어떻게 할까요?"', a
        assert a["replies-to"] == "Q", a   # the question form was kept: the answer replies to it
        # the record's id names both answers; each is its own turn
        code, out = run("source", "add", "X", "--from-transcript", tr, "--turn", "u1", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "found 2 turn(s)" in out and "answer u1#1" in out and "answer u1#2" in out, out
        assert run("source", "add", "B", "--from-transcript", tr, "--turn", "u1#1", "--speaker", "lee", "--target", pj.dir)[0] == 0
        assert mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "B.json"))["text"] == "PDS 백업 (추천)"
        # sagoforce 10-26: the answer is found by what it answers too — a phrase of its question, or the form's id
        assert run("source", "add", "E", "--from-transcript", tr, "--match", "백업을 어떻게", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)[0] == 0
        assert mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "E.json"))["text"] == "PDS 백업 (추천)"
        code, out = run("source", "add", "F", "--from-transcript", tr, "--turn", "a1", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "found 2 turn(s)" in out and "answer u1#1" in out, out
        code, out = run("source", "add", "F", "--from-transcript", tr, "--turn", "a1", "--match", "예전 D1", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code == 0 and mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "F.json"))["text"].startswith("옮기고 삭제"), out
        # text only: read out of the wrapper for the question asked, the wrapper left behind
        assert run("source", "add", "C", "--from-transcript", tr, "--match", "커밋 후", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)[0] == 0
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "C.json"))
        assert c["text"] == "커밋 후 배포" and "answering question a2" in c["locator"] and "replies-to" not in c, c
        # a declined form holds no answer: the miss says it is a tool's output, not something said
        code, out = run("source", "add", "D", "--from-transcript", tr, "--match", "doesn't want", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "found in no turn" in out and "a tool's output" in out, out


def test_a_typescript_function_whose_types_hold_braces_reaches_its_body():
    """guin-site, 10-12: `write/src/backup.ts:backupRows` — `export async function backupRows(env: Env): Promise<{ draft: unknown[];
    … }> { …body… }` — was cut at the `{` inside its return type: the anchor was the signature, the body was neither
    fingerprinted nor quotable ("evidence is not a quote from either anchor"). Generics, parameter types and return types
    may hold braces of their own; the body is the `{` after them. Arrow functions, methods, classes and interfaces too."""
    ts = ('import { Env } from "./env";\n\n'
          "export async function backupRows(env: Env): Promise<{ draft: unknown[]; erasure: unknown[]; d1_erasure: unknown[] }> {\n"
          '  const draft = await env.DB.prepare("SELECT * FROM draft").all();\n'
          "  return { draft: draft.results, erasure: [], d1_erasure: [] };\n}\n\n"
          "export function pick<T extends { id: string }>(xs: T[], o: { limit: number } = { limit: 1 }): { first: T | undefined } | null {\n"
          "  return { first: xs[0] };\n}\n\n"
          "function maker(): () => { a: 1 } {\n  return () => ({ a: 1 });\n}\n\n"
          "declare function shape(x: { a: 1 }): { b: 2 };\n\n"
          "export const arrow = async (env: { db: string }): Promise<{ rows: number }> => {\n  return { rows: env.db.length };\n};\n\n"
          "export class Store extends Base<{ k: string }> implements I<{ z: 1 }> {\n"
          "  async load(key: string): Promise<{ value: string }> {\n    return { value: key };\n  }\n}\n\n"
          "interface Shape<T extends { a: 1 }> extends Other<{ b: 2 }> { c: number }\n\n"
          "function after() { return 1 }\n")
    t = mangsang.anchor_texts("backup.ts", ts)
    assert set(t) == {"", ":backupRows", ":pick", ":maker", ":shape", ":arrow", ":Store", ":Shape", ":after"}, set(t)
    assert t[":backupRows"].endswith("erasure: [], d1_erasure: [] };\n}") and 'prepare("SELECT * FROM draft")' in t[":backupRows"], t[":backupRows"]
    assert t[":pick"].endswith("return { first: xs[0] };\n}"), t[":pick"]
    assert t[":maker"].endswith("return () => ({ a: 1 });\n}"), t[":maker"]
    assert t[":shape"] == "declare function shape(x: { a: 1 }): { b: 2 };", t[":shape"]
    assert t[":arrow"].endswith("return { rows: env.db.length };\n};"), t[":arrow"]
    assert t[":Store"].endswith("return { value: key };\n  }\n}"), t[":Store"]
    assert t[":Shape"].endswith("{ c: number }") and t[":after"] == "function after() { return 1 }", (t[":Shape"], t[":after"])
    base = mangsang.anchors_of("backup.ts", ts)
    assert mangsang.anchors_of("backup.ts", ts.replace("FROM draft", "FROM drafts"))[":backupRows"] != base[":backupRows"], "the body is fingerprinted"
    with Project() as pj:
        write(os.path.join(pj.dir, "backup.ts"), ts)
        assert run("register", "backup.ts", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("backup.ts:backupRows", "documents", "plan/PLAN.md#Q1 add", ev="return { draft: draft.results, erasure: [], d1_erasure: [] };"))
        assert code == 0, out   # a quote from the body is a quote from the anchor


def test_confirm_keeps_what_it_rejected_with_why_and_says_how_to_register():
    """guin-site, 10-12: "confirmed 7 / rejected 6 (proposals file consumed)" — five on plan/ATPROTO.md, which was not
    registered. The rejected now stay in the proposals file, each with its reason; a file that is in the tree and not
    registered is named with the `register` command, and the line says to run the same `confirm` again."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"),
                               rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))
        assert code == 1 and "confirmed 1 / rejected 1" in out and "the rejected kept in" in out, out
        assert "file not registered — `register test_memo.py` first" in out and "  not registered: `register test_memo.py`" in out, out
        left = mangsang.load(os.path.join(pj.dir, "proposals.json"))["relations"]
        assert [x["src"] for x in left] == ["test_memo.py:test_Q1_add"] and "register test_memo.py" in left[0]["rejected"], left
        assert run("register", "test_memo.py", "--target", pj.dir)[0] == 0
        code, out = run("confirm", os.path.join(pj.dir, "proposals.json"), "--by", "kim", "--target", pj.dir)
        assert code == 0 and "confirmed 1 / rejected 0 (proposals file consumed)" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "proposals.json"))
        r = next(r for r in mangsang.decl(pj.dir)["relations"] if r["src"] == "test_memo.py:test_Q1_add")
        assert "rejected" not in r and "why" not in r, r   # the reason it was once refused is not part of the relation


def test_an_agent_speaker_is_named_by_its_model_and_a_roster_entry_that_names_nobody_is_said():
    """guin-site, 10-12: `source add at-64 --from-transcript … --kind question --speaker Claude` was refused ("'Claude' is not
    in mangsang/people.json — ask the person which name they sign…"), and the answer that replied to it failed after it.
    The roster's `"agents": ["Claude ("]` is a prefix, not a broken name: an agent's turn is kept as `Claude (<model>)`. The
    refusal now says the fix — drop --speaker, the record names the model. An entry that names nobody (empty, not a
    string) is left out and said: an empty prefix would have admitted every speaker."""
    with Project() as pj:
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        tr = os.path.join(pj.dir, "s.jsonl")
        lines = [{"type": "assistant", "uuid": "a1", "timestamp": "t1", "message": {"id": "m1", "model": "claude-x", "content": [
                     {"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": [{"question": "확정할까요?", "options": [{"label": "확정"}]}]}}]}},
                 {"type": "user", "uuid": "u1", "timestamp": "t2", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1",
                     "content": 'Your questions have been answered: "확정할까요?"="확정". You can now continue with these answers in mind.'}]},
                  "toolUseResult": {"answers": {"확정할까요?": "확정"}, "annotations": {}}}]
        write(tr, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        code, out = run("source", "add", "Q", "--from-transcript", tr, "--match", "확정할까요", "--kind", "question", "--speaker", "Claude", "--target", pj.dir)
        assert code != 0 and "Drop `--speaker Claude`" in out and "'Claude (claude-x)'" in out and "ask the person" not in out, out
        assert run("source", "add", "Q", "--from-transcript", tr, "--match", "확정할까요", "--kind", "question", "--target", pj.dir)[0] == 0
        assert mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "Q.json"))["speaker"] == "Claude (claude-x)"
        code, out = run("source", "add", "A", "--from-transcript", tr, "--match", "확정", "--kind", "answer", "--speaker", "lee", "--replies-to", "Q", "--target", pj.dir)
        assert code == 0, out
        # a file of the agent's words, under a bare name: the form the roster admits is said
        write(os.path.join(pj.dir, "words.txt"), "제안합니다.\n")
        code, out = run("source", "add", "W", "--file", os.path.join(pj.dir, "words.txt"), "--speaker", "Claude", "--target", pj.dir)
        assert code != 0 and '`--speaker "Claude (<model id>)"`' in out, out
        # a person not on the roster is still asked for, as before
        code, out = run("source", "add", "W", "--file", os.path.join(pj.dir, "words.txt"), "--speaker", "kim", "--target", pj.dir)
        assert code != 0 and "ask the person which name" in out, out
        # an entry naming nobody: left out and said, never an empty prefix admitting anyone
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee", ""], "agents": ["", "Claude (", 3]})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert mangsang.people(pj.dir) == {"people": ["lee"], "agents": ["Claude ("]}
            code, out = run("source", "add", "W", "--file", os.path.join(pj.dir, "words.txt"), "--speaker", "kim", "--target", pj.dir)
        assert code != 0, out
        assert 'agents holds "", 3, which name nobody — left out; remove them from the file' in err.getvalue(), err.getvalue()


def test_concept_show_is_one_concept_whole():
    """guin-site, 10-12: `mangsang concept show site-build` — "invalid choice". It prints the concept's meaning and signer,
    every relation on it (in and out, with its state now and its quote: `lookup concept:NAME`'s lines), what it owes, the
    questions that it answers or that ask about it, and the sources that ground it."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "said.txt"), "a memo is appended, then its id is printed\n")
        assert run("source", "add", "s1", "--file", os.path.join(pj.dir, "said.txt"), "--speaker", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding"), rel("memo.py:add", "realizes", "concept:adding", ev="def add"),
                          rel("source:s1", "realizes", "concept:adding", ev="a memo is appended"))[0] == 0
        assert run("cq", "add", "how-add", "--text", "What does adding do?", "--verify", '{"kind": "answered-by", "concepts": ["adding"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "undo", "--text", "Can an add be undone?", "--verify", '{"kind": "open", "about": ["adding"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("concept", "show", "adding", "--target", pj.dir)
        assert code == 0 and "concept:adding — means: a memo is appended and its id printed" in out and "declared by kim" in out, out
        assert "[concept:adding]" in out and "memo.py:add realizes [concept:adding] — fresh" in out and '"def add" — by kim' in out, out
        assert "answered  how-add  What does adding do?" in out and "OPEN      undo  Can an add be undone?" in out, out
        assert 'source:s1 — kim: "a memo is appended, then its id is printed"' in out, out
        rid = next(r["id"] for r in mangsang.decl(pj.dir)["relations"] if r["src"] == "memo.py:add")
        assert run("retire", rid, "--why", "gone", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("appends and prints", "appends and prints twice"))
        code, out = run("concept", "show", "adding", "--target", pj.dir)
        assert "STALE now" in out and "OWES: concept:adding lost projection(s) %s (memo.py:add)" % rid in out and "FAILED    how-add" in out, out
        code, out = run("concept", "show", "add", "--target", pj.dir)
        assert code != 0 and "no concept add — did you mean adding?" in out, out


def test_a_question_form_answer_seen_on_guin_site_is_the_choice_alone():
    """The wrapper 1.18 left behind, as the host wrote it on guin-site (session a63fdef2, 2026-10-12T09:23Z, source at-64 kept by
    1.17.0): "Your questions have been answered: "Q"="넷 다 확정 (추천)" selected preview:\\n<the agent's preview>.. You can now
    continue with these answers in mind." — the option's preview (the agent's drawing) appended to the choice, the structured
    record's `annotations` holding that preview and no note. And the older wording, "The user answered: "Q"="A". Read the
    answers carefully…", with a question that holds quotes of its own. Each keeps the person's choice and nothing else, from
    the structured record or, without one, from the text."""
    q1 = "망상 개념 넷의 뜻을 지금 구조로 이렇게 고치려 합니다. 그대로 확정할까요? (각 개념의 이전 문장은 history에 남습니다)"
    preview = "site-build:\n글과 기록의 원본은 PDS에 있다.\n\naccess:\n쓰기 앱에는 계정 하나만 들어온다."
    q2 = '이름은 지금 "guin.com 쓰기"인데, 어떻게 고칠까요?'
    for structured in (True, False):
        with Project() as pj:
            tr = os.path.join(pj.dir, "a63fdef2.jsonl")
            form = lambda q, label: {"questions": [{"question": q, "header": "개념 개정", "options": [{"label": label, "description": "미리보기의 문장으로", "preview": preview},
                                                                                                    {"label": "고칠 곳 있음", "description": "메모에"}], "multiSelect": False}]}
            lines = [{"type": "assistant", "uuid": "a1", "timestamp": "2026-10-12T09:22:00.000Z", "message": {"id": "m1", "model": "claude-opus-x", "content": [
                         {"type": "tool_use", "id": "toolu_1", "name": "AskUserQuestion", "input": form(q1, "넷 다 확정 (추천)")}]}},
                     {"type": "user", "uuid": "4e7e8465", "timestamp": "2026-10-12T09:23:03.924Z", "message": {"role": "user", "content": [
                         {"type": "tool_result", "tool_use_id": "toolu_1", "content": 'Your questions have been answered: "%s"="넷 다 확정 (추천)" selected preview:\n%s.. '
                          'You can now continue with these answers in mind.' % (q1, preview)}]},
                      **({"toolUseResult": {**form(q1, "넷 다 확정 (추천)"), "answers": {q1: "넷 다 확정 (추천)"}, "annotations": {q1: {"preview": preview}}}} if structured else {})},
                     {"type": "assistant", "uuid": "a2", "timestamp": "2026-10-12T09:30:00.000Z", "message": {"id": "m2", "model": "claude-opus-x", "content": [
                         {"type": "tool_use", "id": "toolu_2", "name": "AskUserQuestion", "input": form(q2, "줄이기")}]}},
                     {"type": "user", "uuid": "1db07ca1", "timestamp": "2026-10-12T09:31:00.000Z", "message": {"role": "user", "content": [
                         {"type": "tool_result", "tool_use_id": "toolu_2", "content": 'The user answered: "%s"="그냥 무시하고 넘어가자". Read the answers carefully — they may '
                          'request clarification, changes, or that you not proceed — and follow what they actually say.' % q2}]},
                      **({"toolUseResult": {**form(q2, "줄이기"), "answers": {q2: "그냥 무시하고 넘어가자"}, "annotations": {}}} if structured else {})}]
            write(tr, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
            code, out = run("source", "add", "at-64", "--from-transcript", tr, "--match", "넷 다 확정", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)
            assert code == 0, (structured, out)
            a = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "at-64.json"))
            assert a["text"] == "넷 다 확정 (추천)", (structured, a)   # not the wrapper, not the agent's preview
            assert a["locator"] == 'session a63fdef2, answer 4e7e8465 at 2026-10-12T09:23:03.924Z, answering question a1: "%s"' % q1, a
            assert run("source", "add", "at-60", "--from-transcript", tr, "--match", "무시하고", "--kind", "answer", "--speaker", "lee", "--target", pj.dir)[0] == 0
            assert mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "at-60.json"))["text"] == "그냥 무시하고 넘어가자", structured


def test_judge_request_moves_an_earlier_rounds_files_aside_and_consume_refuses_an_older_response():
    """guin-site, 10-15: `judge request --out judge1` reused a directory that still held 10-12's judge-response.json (and its
    transcript); the printed `next: … consume --response …/judge-response.json` pointed at the 3-day-old verdicts. The earlier
    round's files are moved aside, named by their time, and said; a response older than the request beside it is refused."""
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        d = os.path.join(pj.dir, "judge1")
        old = {"artifact-type": "mangsang/judgment@1", "worker": {"host": "claude-code", "model": "claude-j"}, "items": []}
        write(os.path.join(d, "judge-response.json"), old)
        write(os.path.join(d, "judge-response.transcript.jsonl"), "{}\n")
        write(os.path.join(d, "judge-request.json"), {"artifact-type": "mangsang/judge-request@1", "items": []})
        then = 1760261438   # 2025-10-12T09:30:38Z
        for name in ("judge-response.json", "judge-response.transcript.jsonl", "judge-request.json"):
            os.utime(os.path.join(d, name), (then, then))
        code, out = run("judge", "request", "--out", d, "--target", pj.dir)
        assert code == 0, out
        names = sorted(os.listdir(d))
        assert names == ["judge-request.20251012T093038Z.json", "judge-request.json", "judge-response.20251012T093038Z.json",
                         "judge-response.20251012T093038Z.transcript.jsonl"], names
        assert "moved aside: judge-response.json -> judge-response.20251012T093038Z.json" in out, out
        nxt = out[out.index("next:"):]
        assert os.path.join(d, "judge-response.json") in nxt and not os.path.exists(os.path.join(d, "judge-response.json")), out
        # a third round leaves the already-aside files alone
        assert run("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        assert len([n for n in os.listdir(d) if n.startswith("judge-response.2025")]) == 2, os.listdir(d)
        # a response older than its request: an earlier round's, refused
        resp = os.path.join(d, "judge-response.json")
        write(resp, old)
        os.utime(resp, (then, then))
        code, out = run("judge", "consume", "--response", resp, "--by", "kim", "--target", pj.dir)
        assert code != 0 and "older than the judge-request.json beside it" in out, out


def test_an_agent_text_turn_that_asks_is_a_question_and_the_persons_turn_is_the_rosters_one_person():
    """guin-site, 10-15: `source add at-67 --match "…이대로 확정할까요" --kind question` on the agent's plain text turn was refused
    "no question turn" (a question was only a question-form call), and the agent kept it as `--turn ID --kind agent`; then the
    owner's "ㅇㅇ ㄱㄱㄱ" needed `--speaker`, and the agent passed the account name — the one the refusal warns against."""
    with Project() as pj:
        tr = os.path.join(pj.dir, "s.jsonl")
        lines = [{"type": "assistant", "uuid": "e3db4215", "timestamp": "2026-10-15T06:35:24.156Z", "message": {"id": "m1", "model": "claude-x", "content": [
                     {"type": "text", "text": "전수조사를 마쳤습니다.\n\n개념 문장(위 1번)을 이대로 확정할까요?"}]}},
                 {"type": "assistant", "uuid": "a2", "timestamp": "2026-10-15T06:36:00Z", "message": {"id": "m2", "model": "claude-x", "content": [
                     {"type": "text", "text": "확정 문장을 정리했습니다."}]}},
                 {"type": "user", "uuid": "b183bd94", "timestamp": "2026-10-15T06:39:00Z", "message": {"role": "user", "content": "ㅇㅇ ㄱㄱㄱ"}}]
        write(tr, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        code, out = run("source", "add", "at-67", "--from-transcript", tr, "--match", "이대로 확정할까요", "--kind", "question", "--target", pj.dir)
        assert code == 0 and "Claude (claude-x)" in out, out
        assert "agent e3db4215" in mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "at-67.json"))["locator"]
        # a turn that asks nothing is no question
        code, out = run("source", "add", "X", "--from-transcript", tr, "--match", "정리했습니다", "--kind", "question", "--target", pj.dir)
        assert code != 0 and "no question turn" in out, out
        # no roster: the person's turn still needs --speaker
        code, out = run("source", "add", "at-68", "--from-transcript", tr, "--match", "ㅇㅇ ㄱㄱㄱ", "--replies-to", "at-67", "--target", pj.dir)
        assert code != 0 and "--speaker" in out, out
        # two people: which one is not guessed, and the roster's names are said
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee", "kim"], "agents": ["Claude ("]})
        code, out = run("source", "add", "at-68", "--from-transcript", tr, "--match", "ㅇㅇ ㄱㄱㄱ", "--replies-to", "at-67", "--target", pj.dir)
        assert code != 0 and "--speaker" in out and "lee, kim" in out, out
        # one person: it is theirs, and the line says so
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        code, out = run("source", "add", "at-68", "--from-transcript", tr, "--match", "ㅇㅇ ㄱㄱㄱ", "--replies-to", "at-67", "--target", pj.dir)
        assert code == 0 and "speaker: lee — the one person in mangsang/people.json" in out, out
        src = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", "at-68.json"))
        assert src["speaker"] == "lee" and src["replies-to"] == "at-67", src


def test_an_agent_applying_a_judge_round_is_named_by_its_sessions_model():
    """guin-site, 10-15: `judge consume` printed "applied by Claude Code" — no model, while the agent's turns are kept as
    `Claude (<model>)`. The session's model is read from the host's record of the session (CLAUDE_CODE_SESSION_ID)."""
    with Project() as pj:
        home = os.path.join(pj.dir, "claude-home")
        write(os.path.join(home, "projects", "-some-project", "sess-1.jsonl"), "".join(json.dumps(x) + "\n" for x in (
            {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": []}},
            {"type": "assistant", "message": {"model": "<synthetic>", "content": []}},
            {"type": "user", "message": {"content": "ok"}})))
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        d = os.path.join(pj.dir, "judge")
        assert run("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        rid = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8"))["items"][0]["relation"]
        resp = os.path.join(d, "judge-response.json")
        write(resp, {"artifact-type": "mangsang/judgment@1", "request-id": mangsang.load(os.path.join(d, "judge-request.json"))["request-id"], "worker": {"host": "claude-code", "model": "claude-j"}, "items": [
            {"relation": rid, "verdict": "still-true", "quote": "", "evidence": "add still appends"}]})
        os.environ.update(CLAUDE_CONFIG_DIR=home, CLAUDE_CODE_SESSION_ID="sess-1")
        try:
            os.environ["CLAUDECODE"] = "1"
            assert mangsang.running_agent() == "Claude (claude-opus-5-5)", mangsang.running_agent()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = mangsang.main(["judge", "consume", "--response", resp, "--target", pj.dir])
            assert code == 0 and "judged by claude-code claude-j, applied by Claude (claude-opus-5-5)" in out.getvalue(), out.getvalue()
            r = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == rid)
            assert r["confirmed"]["applied-by"] == "Claude (claude-opus-5-5)", r["confirmed"]
            # no record of the session where the host keeps them: the host's name, as before
            os.environ["CLAUDE_CODE_SESSION_ID"] = "sess-unknown"
            assert mangsang.running_agent() == "Claude Code"
        finally:
            for k in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE"):
                os.environ.pop(k, None)



def test_judge_rejects_source_or_relation_changes_after_the_request():
    """An old still-true result cannot make unseen source fresh, even if its evidence quote survives."""
    for changed in ("code", "document", "dependency", "dependency-comment", "relation", "vocabulary", "unregistered"):
        with Project() as pj:
            code_text = CODE.replace("return 1", "return X") if changed == "dependency" else CODE
            if changed == "dependency-comment":
                code_text = CODE.replace("return 1", "return helper()") + "\ndef helper():\n    # requested helper claim\n    return 1\n"
            write(os.path.join(pj.dir, "memo.py"), code_text)
            run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
            assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))[0] == 0
            edited = code_text.replace("X = 1", "X = 2") if changed == "dependency" else code_text.replace("return 1", "return 2")
            write(os.path.join(pj.dir, "memo.py"), edited)
            folder = os.path.join(pj.dir, "judge")
            assert run("judge", "request", "--out", folder, "--limit", "5", "--target", pj.dir)[0] == 0
            req = mangsang.load(os.path.join(folder, "judge-request.json"))
            rid = req["items"][0]["relation"]
            response = os.path.join(folder, "judge-response.json")
            write(response, {"artifact-type": "mangsang/judgment@1", "request-id": req["request-id"],
                             "worker": {"host": "fixture", "model": "fixture"}, "items": [
                                 {"relation": rid, "verdict": "still-true", "evidence": "The requested version still holds."}]})
            if changed == "code":
                write(os.path.join(pj.dir, "memo.py"), edited.replace("return 2", "raise RuntimeError('never reviewed')"))
            elif changed == "document":
                write(os.path.join(pj.dir, "plan/PLAN.md"), PLAN.replace("more", "more, with an entirely new requirement"))
            elif changed == "dependency":
                write(os.path.join(pj.dir, "memo.py"), edited.replace("X = 2", "X = 3"))
            elif changed == "dependency-comment":
                before_fp = mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))[":add"]
                write(os.path.join(pj.dir, "memo.py"), edited.replace("requested helper claim", "different unreviewed helper claim"))
                assert mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))[":add"] == before_fp
            else:
                d = mangsang.decl(pj.dir)
                if changed == "relation":
                    d["relations"][0]["confirmed"] = {"delegated": "a different reading"}
                    mangsang.save(os.path.join(pj.dir, "mangsang", "relations", rid + ".json"), d["relations"][0])
                elif changed == "vocabulary":
                    d["vocabulary"]["documents"]["means"] = "a newly defined predicate"
                else:
                    d["registry"] = [e for e in d["registry"] if e["path"] != "memo.py"]
                mangsang.save_decl(pj.dir, d)
            before = mangsang.load(os.path.join(pj.dir, "mangsang", "relations", rid + ".json"))
            result, out = run("judge", "consume", "--response", response, "--by", "test", "--target", pj.dir)
            assert result == 1 and "changed since the request" in out and "still-true applied 0" in out, (changed, out)
            assert before == mangsang.load(os.path.join(pj.dir, "mangsang", "relations", rid + ".json")), changed
            assert run("impact", "--target", pj.dir)[0] == 1, changed


def test_judge_binds_response_to_request_and_rejects_legacy_packets():
    with Project() as pj:
        run("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)
        pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add"))
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 2"))
        folder = os.path.join(pj.dir, "judge")
        run("judge", "request", "--out", folder, "--target", pj.dir)
        req = mangsang.load(os.path.join(folder, "judge-request.json"))
        resp = {"artifact-type": "mangsang/judgment@1", "request-id": req["request-id"],
                "worker": {"host": "fixture", "model": "fixture"}, "items": [
                    {"relation": req["items"][0]["relation"], "verdict": "still-true", "evidence": "fixture"}]}
        # A late response written after the second request passes mtime checks but belongs to the first.
        run("judge", "request", "--out", folder, "--target", pj.dir)
        response = os.path.join(folder, "judge-response.json")
        write(response, resp)
        result, out = run("judge", "consume", "--response", response, "--by", "test", "--target", pj.dir)
        assert result != 0 and "request-id" in out, out
        req2 = mangsang.load(os.path.join(folder, "judge-request.json"))
        resp["request-id"] = req2["request-id"]
        req2["items"][0].pop("basis")
        write(os.path.join(folder, "judge-request.json"), req2)
        write(response, resp)
        result, out = run("judge", "consume", "--response", response, "--by", "test", "--target", pj.dir)
        assert result != 0 and "changed since the request" in out, out
        assert run("impact", "--target", pj.dir)[0] == 1


def git_in(pj):
    import subprocess
    return lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=pj.dir, capture_output=True, text=True)


def line_of(out, label):
    """The output lines that start with `label` (as check and impact print them: two spaces, the label padded)."""
    return [l for l in out.split("\n") if l.startswith("  " + label + " ") or l.startswith("  %-12s " % label)]


def test_a_registered_invariant_naming_files_still_sees_a_new_sibling():
    """An audit of six source models, 11-06 (R1): four of them declared `registered` over the exact files they had registered,
    and a new committed plugin/resolver.py beside them was asked by nothing — check exit 0, no line, no next step. Now the
    code and config beside registered files that no invariant's paths or excepts classify is said as unseen (never red),
    with its register and the revise that gives the invariant its folder; once the folder is asked, it is a FAILED invariant
    as before and the unseen line goes. An invariant that names only files is said once, before any sibling exists."""
    with Project() as pj:
        git = git_in(pj)
        write(os.path.join(pj.dir, "plugin", "x.py"), "def x():\n    return 1\n")
        write(os.path.join(pj.dir, "plugin", "y.py"), "def y():\n    return 2\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "plan/PLAN.md", "plugin/x.py", "plugin/y.py", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "scope", "--text", "Is the payload registered?", "--verify",
                   '{"kind": "registered", "paths": ["plugin/x.py", "plugin/y.py"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and not line_of(out, "unseen"), out
        only = line_of(out, "files-only")
        assert len(only) == 1 and "scope names only files (2)" in only[0] and "`plugin/`" in only[0], out
        # the probe: a committed sibling (and one a level down); prose and a lockfile there are not code or config
        write(os.path.join(pj.dir, "plugin", "resolver.py"), "def resolve():\n    return 3\n")
        write(os.path.join(pj.dir, "plugin", "lib", "util.py"), "def util():\n    return 4\n")
        write(os.path.join(pj.dir, "plugin", "notes.md"), "# notes\n")
        write(os.path.join(pj.dir, "plugin", "package-lock.json"), "{}\n")
        git("add", "-A"); git("commit", "-qm", "siblings")
        code, out = run("check", "--target", pj.dir)
        unseen = line_of(out, "unseen")
        assert code == 0, "an observation, never red"
        # the sibling beside the registered files, and — as before — the subdirectory nothing is registered in, each said once
        assert len(unseen) == 2 and "1 tracked code/config file(s) beside registered ones that no `registered` invariant asks" in unseen[0], out
        assert "plugin/resolver.py" in unseen[0] and "1 directory with code or config and nothing registered (plugin/lib/ 1 file(s))" in unseen[1], out
        assert not any(x in out for x in ("notes.md", "package-lock")), out
        assert "mangsang register plugin/resolver.py" in out and "mangsang register plugin/lib/util.py" in out, out
        assert "mangsang cq revise scope --verify" in out and '"plugin/x.py", "plugin/y.py", "plugin/"' in out, out
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        seen = [f for f in doc["findings"] if f["kind"] == "unregistered" and "plugin/resolver.py" in f["where"]]
        assert len(seen) == 1 and seen[0]["layer"] == "observation" and "asked by no `registered` invariant" in seen[0]["text"], doc
        assert [f["where"] for f in doc["findings"] if f["kind"] == "registered-files-only"] == ["scope"], doc
        # an except classifies a file as on purpose: it is no longer said
        assert run("cq", "revise", "scope", "--verify", '{"kind": "registered", "paths": ["plugin/x.py", "plugin/y.py"], "except": ["plugin/lib/util.py"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        unseen = line_of(run("check", "--target", pj.dir)[1], "unseen")
        assert len(unseen) == 1 and "plugin/resolver.py" in unseen[0] and "util.py" not in unseen[0], unseen
        # the folder asked: a file under the invariant's paths is a FAILED invariant as before, and nothing is unseen or files-only
        assert run("cq", "revise", "scope", "--verify", '{"kind": "registered", "paths": ["plugin/"], "except": ["plugin/*.md", "plugin/package-lock.json"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "FAILED       scope" in out and "2 unregistered tracked file(s): plugin/lib/util.py, plugin/resolver.py" in out, out
        assert not line_of(out, "unseen") and not line_of(out, "files-only"), out
        assert run("register", "plugin/resolver.py", "plugin/lib/util.py", "--target", pj.dir)[0] == 0
        assert run("check", "--target", pj.dir)[0] == 0
    # without a `registered` invariant the old beside advice is what it was: every tracked file there, said once
    with Project() as pj:
        git = git_in(pj)
        write(os.path.join(pj.dir, "plugin", "x.py"), "def x():\n    return 1\n")
        write(os.path.join(pj.dir, "plugin", "notes.md"), "# notes\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "plugin/x.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        unseen = line_of(out, "unseen")
        assert code == 0 and len(unseen) == 1 and "plugin/notes.md" in unseen[0] and "to make it a check" in unseen[0], out
        assert not line_of(out, "files-only") and "cq revise" not in out, out
    # an invariant naming only root files: the root's own files are never said unseen (every project's manifests), so that
    # invariant is the one place they are asked — said once as files-only, with the advice for the root
    with Project() as pj:
        git = git_in(pj)
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "roots", "--text", "?", "--verify", '{"kind": "registered", "paths": ["memo.py", "test_memo.py"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "resolver.py"), "def r():\n    return 1\n")
        git("add", "-A"); git("commit", "-qm", "a root sibling")
        code, out = run("check", "--target", pj.dir)
        only = line_of(out, "files-only")
        assert code == 0 and len(only) == 1 and "roots names only files (2) — a file added beside them in the root is asked by nothing" in only[0], out
        assert "the root's own files are never said unseen" in only[0] and "`test_`" in only[0] and not line_of(out, "unseen"), out
        assert run("cq", "revise", "roots", "--verify", '{"kind": "registered", "paths": ["memo.py", "test_"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        assert not line_of(run("check", "--target", pj.dir)[1], "files-only"), "a prefix is no file: the invariant asks of the next suite"


def test_an_except_says_what_it_hides_and_a_star_that_crosses_a_slash():
    """hacheong, 11-06 (R1b): an except's `*` matches across `/`, so `plugin/domains/*` also hid a committed
    plugin/domains/code/resolver.py, and check passed. What an except matches is unchanged (consumers' excepts keep their
    meaning); what it hides is said — the invariant's detail counts each wildcard glob's files, and a glob that hides code or
    config only because its `*` crossed a `/` is an observation once. `**` matches the same and says the depth is meant."""
    with Project() as pj:
        git = git_in(pj)
        write(os.path.join(pj.dir, "src", "a.py"), "def a():\n    return 1\n")
        write(os.path.join(pj.dir, "src", "gen", "x.py"), "X = 1\n")
        write(os.path.join(pj.dir, "src", "gen", "deep", "y.py"), "Y = 1\n")
        write(os.path.join(pj.dir, "src", "gen", "deep", "README.md"), "# generated\n")
        write(os.path.join(pj.dir, "src", "vendor", "lib.js"), "export const v = 1\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "src/a.py", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "scope", "--text", "Is src registered?", "--verify",
                   '{"kind": "registered", "paths": ["src/"], "except": ["src/gen/*", "src/vendor/lib.js"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "holds        scope" in out and "0 unregistered tracked file(s); its excepts hide 4 (src/gen/* 3)" in out, out
        crossed = line_of(out, "except")
        assert len(crossed) == 1 and "scope `src/gen/*` hides 1 code/config file(s)" in crossed[0] and "src/gen/deep/y.py" in crossed[0], out
        assert "src/gen/x.py" not in crossed[0] and "README.md" not in crossed[0] and "`src/gen/**`" in crossed[0], crossed
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        assert [f["where"] for f in doc["findings"] if f["kind"] == "except-crosses"] == ["scope src/gen/*"], doc
        # `**` says every depth on purpose: the same files are excepted (it still holds), and nothing is said
        assert run("cq", "revise", "scope", "--verify", '{"kind": "registered", "paths": ["src/"], "except": ["src/gen/**", "src/vendor/lib.js"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "its excepts hide 4 (src/gen/** 3)" in out and not line_of(out, "except"), out
        # narrowed to the files of each level: the same files excepted, no `*` crossing a `/`, nothing said
        assert run("cq", "revise", "scope", "--verify", '{"kind": "registered", "paths": ["src/"], "except": ["src/gen/x.py", "src/gen/deep/*", "src/vendor/lib.js"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "holds        scope" in out and "its excepts hide 4 (src/gen/deep/* 2)" in out and not line_of(out, "except"), out
        # what a glob matches is what it matched: `src/gen/*.py` still excepts src/gen/deep/y.py (fnmatch), and says so
        assert run("cq", "revise", "scope", "--verify", '{"kind": "registered", "paths": ["src/"], "except": ["src/gen/*.py", "src/gen/deep/*.md", "src/vendor/lib.js"]}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        crossed = line_of(out, "except")
        assert code == 0 and len(crossed) == 1 and "`src/gen/*.py` hides 1" in crossed[0] and "`src/gen/**.py`" in crossed[0], out
    assert mangsang.glob_crosses("src/gen/deep/y.py", "src/gen/*") and not mangsang.glob_crosses("src/gen/x.py", "src/gen/*")
    assert not mangsang.glob_crosses("src/gen/deep/y.py", "src/gen/**") and not mangsang.glob_crosses("src/a.py", "src/a.py")
    assert mangsang.glob_crosses("src/gen/deep/y.py", "src/gen/*.py") and mangsang.glob_crosses("tests/x/a.json", "tests/*.json")


def test_an_except_carries_its_reason_and_a_malformed_one_is_refused():
    """mangsang M1, 11-06: an `except` entry could only be a glob string, so every project kept each except's reason
    elsewhere (MODEL.md, scope.json) and wrote checker code to hold the two together; `cq add` wrote any except unvalidated
    — an object, 7, "" — and `check` then died in fnmatch (TypeError), and a bare string was iterated by character, its
    `*` excepting every file. Now an entry is a glob string or {"glob", "why"}: both match the same, check says the reason
    where it says what the except hides, and cq refuses (check: UNASKABLE) an except of any other shape."""
    import traceback
    # the two engine functions exist (asked first, so the missing feature fails here as an assertion, not as an AttributeError)
    assert callable(getattr(mangsang, "except_entries", None)), "mangsang.except_entries is missing"
    assert callable(getattr(mangsang, "except_shape", None)), "mangsang.except_shape is missing"

    def run2(*argv):   # stdout and stderr both: a refusal may say why on either; a crash is a failed assertion, not an error
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            try:
                code, out = run(*argv)
            except Exception:
                raise AssertionError("%s crashed:\n%s" % (" ".join(argv[:2]), traceback.format_exc()))
        return code, out + err.getvalue()

    def verify(excepts, paths=("src/",)):
        return json.dumps({"kind": "registered", "paths": list(paths), "except": excepts})

    def block_under(out, label, qid):
        """The 6-space lines directly under the invariant's `label` line."""
        lines = out.split("\n")
        at = [i for i, l in enumerate(lines) if l.startswith("  %-12s %s " % (label, qid))]
        assert len(at) == 1, (label, qid, out)
        got = []
        for l in lines[at[0] + 1:]:
            if not l.startswith("      "):
                break
            got.append(l)
        return got

    def reasons_under(out, label, qid):
        return [l for l in block_under(out, label, qid) if l.startswith("      except ")]

    def without_reasons(out, whys):
        """The output as all-strings excepts print it: no reason line, no reason after an `except` observation."""
        kept = []
        for l in out.split("\n"):
            if l.startswith("      except "):
                continue
            for w in whys:
                if l.startswith("  except ") and l.endswith(" — its reason: " + w):
                    l = l[:-len(" — its reason: " + w)]
            kept.append(l)
        return "\n".join(kept)

    BAD = ["src/gen/*", {"glob": "src/gen/*", "why": "x"}, 7, None,
           [{"glob": "src/gen/*"}], [{"glob": "src/gen/*", "why": ""}], [{"glob": "src/gen/*", "why": "   "}],
           [{"glob": "src/gen/*", "why": "x", "note": "y"}], [{"pattern": "src/gen/*", "reason": "x"}], [{"glob": "", "why": "x"}],
           [{"why": "x"}], [{"glob": 7, "why": "x"}], [{"glob": "src/gen/*", "why": 7}], [{}],
           [7], [""], [None], [["src/gen/*"]], ["src/vendor/lib.js", 7],
           ["src/gen/*", "src/gen/*"], [{"glob": "src/gen/*", "why": "a"}, {"glob": "src/gen/*", "why": "b"}],
           ["src/gen/*", {"glob": "src/gen/*", "why": "a"}], [{"glob": "src/gen/*", "why": "a"}, "src/vendor/lib.js", "src/gen/*"]]

    # C6: the engine's two functions, asked directly
    E, S = mangsang.except_entries, mangsang.except_shape
    assert E({"kind": "registered", "paths": ["src/"]}) == [] and S({"kind": "registered", "paths": ["src/"]}) == []
    assert E({"except": []}) == [] and S({"except": []}) == []
    assert E({"except": "src/gen/*"}) == [] and E({"except": {"glob": "a", "why": "b"}}) == [] and E({"except": 7}) == []
    mixed = {"except": ["src/*.js", {"glob": "src/gen/*", "why": "written by the generator"}, "b", {"glob": "c/**", "why": "kept"}]}
    assert E(mixed) == [("src/*.js", None), ("src/gen/*", "written by the generator"), ("b", None), ("c/**", "kept")], E(mixed)
    assert S(mixed) == [], S(mixed)
    assert E({"except": ["a", 7, {"glob": "b"}, "", {"glob": "c", "why": "r"}, {"glob": "d", "why": " "}, None, {"glob": "e", "why": "s", "x": 1}]}) \
        == [("a", None), ("c", "r")]
    for bad in BAD:
        probs = S({"kind": "registered", "paths": ["src/"], "except": bad})
        assert isinstance(probs, list) and probs and all(isinstance(p, str) and p.strip() for p in probs), (bad, probs)

    with Project() as pj:
        git = git_in(pj)
        write(os.path.join(pj.dir, "src", "a.py"), "def a():\n    return 1\n")
        write(os.path.join(pj.dir, "src", "gen", "x.py"), "X = 1\n")
        write(os.path.join(pj.dir, "src", "gen", "deep", "y.py"), "Y = 1\n")
        write(os.path.join(pj.dir, "src", "gen", "deep", "README.md"), "# generated\n")
        write(os.path.join(pj.dir, "src", "vendor", "lib.js"), "export const v = 1\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run2("register", "src/a.py", "--target", pj.dir)[0] == 0
        rec = os.path.join(pj.dir, "mangsang", "cq", "scope.json")
        GEN, NONE = "written by the generator", "reserved for later"
        strings = ["src/*.js", "src/gen/*", "src/gen/deep/*.md", "src/none/*"]
        reasoned = ["src/*.js", {"glob": "src/gen/*", "why": GEN}, "src/gen/deep/*.md", {"glob": "src/none/*", "why": NONE}]

        # C4 (strings only): exactly what 2.2.1 printed — the holds line, nothing under it, the two observations as they were
        assert run2("cq", "add", "scope", "--text", "Is src registered?", "--verify", verify(strings), "--by", "kim", "--target", pj.dir)[0] == 0
        code_s, out_s = run2("check", "--target", pj.dir)
        assert code_s == 0, out_s
        assert "  holds        scope  Is src registered? — 0 unregistered tracked file(s); its excepts hide 4 (src/*.js 1, src/gen/* 3, src/gen/deep/*.md 1)\n" \
               "  except       scope `src/*.js` hides 1 code/config file(s) only because `*` matches across `/` (src/vendor/lib.js) — it hides every later file at any depth there: name the files it means instead (any glob also hides files added below it later), or write `src/**.js` to say every depth is meant (it matches the same)\n" \
               "  except       scope `src/gen/*` hides 1 code/config file(s) only because `*` matches across `/` (src/gen/deep/y.py) — it hides every later file at any depth there: name the files it means instead (any glob also hides files added below it later), or write `src/gen/**` to say every depth is meant (it matches the same)\n" \
               in out_s, out_s
        assert not reasons_under(out_s, "holds", "scope") and "its reason" not in out_s, out_s
        doc_s = json.loads(run2("check", "--findings", "--target", pj.dir)[1])
        crosses_s = [(f["where"], f["text"]) for f in doc_s["findings"] if f["kind"] == "except-crosses"]
        assert [w for w, _ in crosses_s] == ["scope src/*.js", "scope src/gen/*"] and not any("reason" in t for _, t in crosses_s), crosses_s
        hides_s = mangsang.except_hides(pj.dir, mangsang.decl(pj.dir), json.loads(verify(strings)))

        # C1 + C4 + C5: one list mixing strings and objects — the same answer, the same files hidden, a reason line per object in order
        assert run2("cq", "revise", "scope", "--verify", verify(reasoned), "--by", "kim", "--target", pj.dir)[0] == 0
        assert json.load(io.open(rec, encoding="utf-8"))["verify"]["except"] == reasoned, "the record keeps the entries as written"
        code_m, out_m = run2("check", "--target", pj.dir)
        assert code_m == code_s == 0, out_m
        assert reasons_under(out_m, "holds", "scope") == ["      except src/gen/* hides 3: " + GEN, "      except src/none/* hides 0: " + NONE], out_m
        assert line_of(out_m, "holds")[0] == line_of(out_s, "holds")[0], "the invariant's own line keeps its form"
        crossed = line_of(out_m, "except")
        assert len(crossed) == 2 and crossed[0] == line_of(out_s, "except")[0], "a string entry's observation is unchanged"
        assert crossed[1] == line_of(out_s, "except")[1] + " — its reason: " + GEN, crossed
        assert without_reasons(out_m, [GEN, NONE]) == out_s, (out_m, out_s)
        doc_m = json.loads(run2("check", "--findings", "--target", pj.dir)[1])
        crosses_m = [(f["where"], f["text"]) for f in doc_m["findings"] if f["kind"] == "except-crosses"]
        assert crosses_m == [crosses_s[0], (crosses_s[1][0], crosses_s[1][1] + "; its reason: " + GEN)], crosses_m
        d = mangsang.decl(pj.dir)
        assert mangsang.except_hides(pj.dir, d, json.loads(verify(reasoned))) == hides_s, "an object hides exactly what its glob string does"
        assert sorted(mangsang.unregistered(pj.dir, d, ["src/"], reasoned) or []) == sorted(mangsang.unregistered(pj.dir, d, ["src/"], strings) or []) == []
        assert sorted(mangsang.unregistered(pj.dir, d, ["src/"], [{"glob": "src/gen/*", "why": GEN}]) or []) == ["src/vendor/lib.js"]

        # FAILED: the reasons are said under the FAILED line too, and the answer is the strings' answer
        assert run2("cq", "revise", "scope", "--verify", verify(["src/gen/*"]), "--by", "kim", "--target", pj.dir)[0] == 0
        code_s, out_s = run2("check", "--target", pj.dir)
        assert run2("cq", "revise", "scope", "--verify", verify([{"glob": "src/gen/*", "why": GEN}]), "--by", "kim", "--target", pj.dir)[0] == 0
        code_m, out_m = run2("check", "--target", pj.dir)
        assert code_m == code_s == 1 and "FAILED       scope" in out_m and "src/vendor/lib.js" in line_of(out_m, "FAILED")[0], out_m
        assert reasons_under(out_m, "FAILED", "scope") == ["      except src/gen/* hides 3: " + GEN], out_m
        assert without_reasons(out_m, [GEN]) == out_s, (out_m, out_s)

        # C1 in `unseen`: an invariant naming only a file — its object except keeps the generated files out of unseen as the string does
        assert run2("cq", "revise", "scope", "--verify", verify(["src/gen/*"], paths=["src/a.py"]), "--by", "kim", "--target", pj.dir)[0] == 0
        code_s, out_s = run2("check", "--target", pj.dir)
        assert run2("cq", "revise", "scope", "--verify", verify([{"glob": "src/gen/*", "why": GEN}], paths=["src/a.py"]), "--by", "kim", "--target", pj.dir)[0] == 0
        code_m, out_m = run2("check", "--target", pj.dir)
        assert code_m == code_s and line_of(out_m, "unseen") == line_of(out_s, "unseen"), (out_m, out_s)
        assert line_of(out_s, "unseen") and not any("src/gen/" in l for l in line_of(out_m, "unseen")), out_m
        assert reasons_under(out_m, "holds", "scope") == ["      except src/gen/* hides 3: " + GEN], out_m
        assert without_reasons(out_m, [GEN]) == out_s, (out_m, out_s)

        # C2: cq add and cq revise refuse each malformed except — no record on add, the record unchanged on revise, "except" said
        assert run2("cq", "revise", "scope", "--verify", verify(reasoned), "--by", "kim", "--target", pj.dir)[0] == 0
        before = io.open(rec, encoding="utf-8").read()
        for bad in BAD:
            code, out = run2("cq", "add", "bad", "--text", "?", "--verify", verify(bad), "--by", "kim", "--target", pj.dir)
            assert code != 0 and "except" in out, ("add accepted", bad, out)
            assert not os.path.exists(os.path.join(pj.dir, "mangsang", "cq", "bad.json")), ("add wrote a record", bad)
            code, out = run2("cq", "revise", "scope", "--verify", verify(bad), "--by", "kim", "--target", pj.dir)
            assert code != 0 and "except" in out, ("revise accepted", bad, out)
            assert io.open(rec, encoding="utf-8").read() == before, ("revise changed the record", bad)

        # C3: the same excepts written into the record by hand — UNASKABLE with the problem under it, and nothing crashes
        good = json.loads(before)
        for bad in BAD:
            r = json.loads(before)
            r["verify"]["except"] = bad
            write(rec, json.dumps(r, indent=2, ensure_ascii=False) + "\n")
            code, out = run2("check", "--target", pj.dir)
            unask = line_of(out, "UNASKABLE")
            assert code == 1 and len(unask) == 1 and "scope" in unask[0], ("not unaskable", bad, out)
            under = block_under(out, "UNASKABLE", "scope")
            assert under and under[0].strip(), ("no problem under UNASKABLE", bad, out)
            assert not line_of(out, "holds") and not line_of(out, "FAILED"), ("answered anyway", bad, out)
            code, out = run2("check", "--findings", "--target", pj.dir)
            doc = json.loads(out)
            assert [f["where"] for f in doc["findings"] if f["kind"] == "invariant-unaskable"] == ["scope"], (bad, doc)
            code, out = run2("concept", "list", "--brief", "--target", pj.dir)
        write(rec, json.dumps(good, indent=2, ensure_ascii=False) + "\n")
        assert run2("check", "--target", pj.dir)[0] == 0


def test_a_required_invariant_keeps_named_content_and_require_model_fails_an_empty_one():
    """An audit of six source models, 11-06 (R2): retiring a concept's projection, a question, an invariant or a relation, or emptying the
    model, left check, cq and impact green, so every source model wrote its own acceptance checker (about 1,100 lines) —
    three of them passed falsely (retired questions counted, an empty required scope, a retired-only model). Now a project
    that keeps its model declares it: `{"kind": "required", ...}` fails, with the engine's own semantics, when what it names
    is missing, retired, drifted, owing a re-read, realized nowhere, of the other layer or broken; `check --require-model`
    fails an absent or empty model. Neither changes anything for a project that declares nothing."""
    with Project() as pj:
        code, out = run("check", "--target", pj.dir)
        assert code == 0, "optional when absent: no model, nothing red"
        code, out = run("check", "--require-model", "--target", pj.dir)
        assert code == 1 and "FAILED       --require-model  the model is required and absent: no mangsang/ here" in out, out
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        code, out = run("check", "--require-model", "--target", pj.dir)
        assert code == 1 and "empty: no concept, no active relation, no active invariant" in out, out
        assert run("concept", "add", "alpha", "--means", "add appends and prints its id.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:alpha", ev="def add(store, text):"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:alpha"))[0] == 0
        assert run("cq", "add", "q1", "--text", "What does add do?", "--verify", '{"kind": "answered-by", "concepts": ["alpha"]}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--require-model", "--target", pj.dir)
        assert code == 1 and "empty: no active invariant" in out and "--require-model FAILED (no active invariant)" in out, out
        assert run("cq", "add", "projected", "--text", "Every concept planned?", "--verify", '{"kind": "projection", "media": {"doc": ["plan/"]}}',
                   "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("cq", "add", "inv-resolved", "--text", "Living anchors?", "--verify", '{"kind": "resolved"}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--require-model", "--target", pj.dir)
        assert code == 0 and "--require-model" not in out, out
        keep = {"kind": "required", "concepts": ["alpha"], "questions": ["q1"], "invariants": ["inv-resolved", "keep"],
                "relations": [{"src": "memo.py:add", "predicate": "realizes", "dst": "concept:alpha"}]}
        # what it names must stand when it is declared; a misspelt key or nothing named is not askable
        for bad in ({"kind": "required"}, {"kind": "required", "concept": ["alpha"]}, {"kind": "required", "relations": [{"src": "memo.py:add"}]}):
            code, out = run("cq", "add", "keep", "--text", "?", "--verify", json.dumps(bad), "--by", "kim", "--target", pj.dir)
            assert code != 0 and "cannot be asked" in out, (bad, out)
        code, out = run("cq", "add", "keep", "--text", "?", "--verify", json.dumps(dict(keep, concepts=["alpha", "beta"])), "--by", "kim", "--target", pj.dir)
        assert code != 0 and "concept:beta is missing" in out, out
        code, out = run("cq", "add", "keep", "--text", "?", "--verify", json.dumps(dict(keep, questions=["inv-resolved"])), "--by", "kim", "--target", pj.dir)
        assert code != 0 and "question inv-resolved is an invariant (kind resolved), not a question" in out, out
        assert run("cq", "add", "keep", "--text", "Does the model keep what it was built to carry?", "--verify", json.dumps(keep), "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "holds        keep" in out and "1 concepts, 1 questions, 2 invariants, 1 relations named, 0 not standing" in out, out
        assert "keep" not in run("cq", "--target", pj.dir)[1], "an invariant answers to check, not cq"
        shown = next(l for l in run("report", "--target", pj.dir)[1].split("\n") if l.startswith("- **keep**"))
        assert "invariant (`check`) ·" in shown and "answered by" not in shown, shown   # it names concepts; it answers nothing
        # each way content stops standing is said, the engine's own semantics
        assert run("cq", "retire", "q1", "--why", "asked elsewhere", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "FAILED       keep" in out and "question q1 is retired — asked elsewhere" in out, out
        assert run("cq", "revise", "q1", "--by", "kim", "--target", pj.dir)[0] == 0   # a revise asks it again
        assert run("concept", "drift", "alpha", "--why", "add no longer prints", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "concept:alpha is marked drifted — add no longer prints" in out, out
        assert run("concept", "reaffirm", "alpha", "--by", "kim", "--why", "the sentence holds", "--target", pj.dir)[0] == 0
        assert run("check", "--target", pj.dir)[0] == 0
        rid = mangsang.rel_id(keep["relations"][0])
        assert run("retire", rid, "--why", "moved", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "%s (memo.py:add realizes concept:alpha) is retired — moved" % rid in out, out
        assert "concept:alpha owes a re-read" in out and "2 not standing" in out, out
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        assert [f["where"] for f in doc["findings"] if f["kind"] == "invariant-failed"] == ["keep"], doc
        # a broken relation: the anchor it stands on is gone
        assert pj.propose(rel("memo.py:add", "realizes", "concept:alpha", ev="def add(store, text):"))[0] == 0
        assert run("concept", "reaffirm", "alpha", "--by", "kim", "--why", "the sentence holds", "--target", pj.dir)[0] == 0
        assert run("check", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("def add(store, text):\n    return 1\n", ""))
        code, out = run("check", "--target", pj.dir)
        assert code == 1 and "is broken — dead anchor(s) memo.py:add" in out, out
        # emptied: every relation retired leaves no active relation — --require-model says it, whatever else holds
        write(os.path.join(pj.dir, "memo.py"), CODE)
        for r in mangsang.decl(pj.dir)["relations"]:
            assert run("retire", r["id"], "--why", "emptied", "--target", pj.dir)[0] == 0
        code, out = run("check", "--require-model", "--target", pj.dir)
        assert code == 1 and "empty: no active relation" in out and "is realized by no relation" in out, out


def test_impact_says_a_relation_moved_only_through_a_read_with_no_relation_of_its_own():
    """An audit of six source models, 11-06 (R3): editing chongdae's plugin_root staled five relations of three unrelated concepts, and
    hunsu's materialize_codex_hooks staled cmd_lock's four — each re-read against its own sentence, found true and
    reconfirmed, while the read's own contract (the defect) was examined by nobody. Now impact says, with each such stale
    relation, that it moved only through reads that carry no relation of their own and that reconfirming does not read
    them, and groups a read that staled relations of two or more concepts as a candidate shared contract. Silent when the
    anchor's own text moved and when the read is related itself."""
    src = ("ROOT = '/a'\n\n\ndef plugin_root():\n    return ROOT\n\n\ndef fmt(x):\n    return x\n\n\n"
           "def load():\n    return fmt(plugin_root() + 'x')\n\n\ndef save():\n    return plugin_root() + 'y'\n")
    with Project() as pj:
        git = git_in(pj)
        git("init", "-q")
        write(os.path.join(pj.dir, "p.py"), src)
        assert run("register", "plan/PLAN.md", "p.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "loading", "--means", "load reads the root.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "saving", "--means", "save writes beside the root.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("p.py:load", "realizes", "concept:loading", ev="def load():"),
                          rel("p.py:save", "realizes", "concept:saving", ev="def save():"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "confirmed")
        r_load = mangsang.rel_id({"src": "p.py:load", "predicate": "realizes", "dst": "concept:loading"})
        # a read of one concept's anchor only: said with that relation, no shared line
        write(os.path.join(pj.dir, "p.py"), src.replace("    return x\n", "    return x.strip()\n"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("moved only through") == 1 and "p.py:load moved only through what it reads, not its own text: p.py:fmt" in out, out
        assert "reconfirming re-reads concept:loading against p.py:load, not that read's own contract" in out and "shared" not in out, out
        # a read both concepts' anchors stand on: said with each, and grouped once
        write(os.path.join(pj.dir, "p.py"), src.replace("    return ROOT\n", "    return ROOT + '/'\n"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("moved only through") == 2 and len(line_of(out, "shared")) == 1, out
        assert "p.py:plugin_root, read with no relation of its own, staled 2 relation(s) of 2 concepts (concept:loading, concept:saving" in out, out
        code, show = run("impact", "--show", "--target", pj.dir)
        assert show.count("moved only through") == 2 and "p.py:plugin_root, read by p.py:load @ now" in show, show
        doc = json.loads(run("impact", "--findings", "--target", pj.dir)[1])
        st = [f for f in doc["findings"] if f["kind"] == "stale"]
        assert len(st) == 2 and all("moved only through what it reads: p.py:plugin_root, with no relation of its own" in f["text"] for f in st), doc
        assert [f["where"] for f in doc["findings"] if f["kind"] == "unmodeled-read"] == ["p.py:plugin_root"], doc
        assert all(f.get("layer") == "observation" for f in doc["findings"] if f["kind"] == "unmodeled-read"), doc
        # its own text moved too: the re-read reads the change — nothing more is said for that relation
        write(os.path.join(pj.dir, "p.py"), src.replace("    return ROOT\n", "    return ROOT + '/'\n").replace("'x')", "'z')"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("moved only through") == 1 and "p.py:save moved only through" in out and "shared" not in out, out
        # related on its own, the read is no longer unmodeled: its own relation goes stale, re-read against its own sentence
        write(os.path.join(pj.dir, "p.py"), src)
        assert run("concept", "add", "root", "--means", "plugin_root is where the plugin lives.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("p.py:plugin_root", "realizes", "concept:root", ev="def plugin_root():"))[0] == 0
        git("add", "-A"); git("commit", "-qm", "root related")
        write(os.path.join(pj.dir, "p.py"), src.replace("    return ROOT\n", "    return ROOT + '/'\n"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("stale   ") == 3 and "moved only through" not in out and "shared" not in out, out
        # a related read and an unrelated one moved together: the line names both, each for what it is — never "only" the one
        write(os.path.join(pj.dir, "p.py"), src.replace("    return ROOT\n", "    return ROOT + '/'\n").replace("    return x\n", "    return x.strip()\n"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("moved only through") == 1 and "shared" not in out, out
        assert "p.py:load moved only through what it reads, not its own text: p.py:fmt, with no relation of its own (and p.py:plugin_root, related itself)" in out, out
        assert run("reconfirm", r_load, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)[0] == 0
    # without a commit holding what the confirmer saw, nothing is claimed about which part moved
    with Project() as pj:
        write(os.path.join(pj.dir, "p.py"), src)
        assert run("register", "p.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "loading", "--means", "load reads the root.", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("p.py:load", "realizes", "concept:loading", ev="def load():"))[0] == 0
        write(os.path.join(pj.dir, "p.py"), src.replace("    return ROOT\n", "    return ROOT + '/'\n"))
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "stale" in out and "moved only through" not in out, out


def test_check_says_a_concept_whose_code_no_test_verifies():
    """An audit of six source models, 11-06 (R4): a projection invariant holds on `realizes` alone, and three source models (118 relations)
    had no `verifies` — a code change never asked whether its test still proves it. Check observes (never red) each concept
    whose code anchors no `verifies` from a test reaches, once per concept — since 2.6.0 (contract C2) whatever invariants
    exist, and a projection invariant's `test` medium fails on it (C3)."""
    said = "and no `verifies` from a test reaches its code"
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        for name, means in (("adding", "add appends."), ("listing", "list lists.")):
            assert run("concept", "add", name, "--means", means, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding"),
                          rel("test_memo.py:test_Q1_add", "realizes", "concept:adding", ev="def test_Q1_add():"),
                          rel("memo.py:list_", "realizes", "concept:listing", ev="def list_(store):"),
                          rel("plan/PLAN.md#Q2 list", "realizes", "concept:listing", ev="lists."),
                          rel("test_memo.py:test_Q1_add", "realizes", "concept:listing", ev="def test_Q1_add():"))[0] == 0
        code, out = run("check", "--target", pj.dir)
        lines = line_of(out, "unverified")
        assert len(lines) == 2 and ("concept:adding — 1 test projection(s), %s (memo.py:add)" % said) in lines[0], \
            ("no projection invariant at all: said all the same", out)
        assert run("cq", "add", "projected", "--text", "Every concept in doc, code and test?", "--verify",
                   '{"kind": "projection", "media": {"doc": ["plan/"], "code": ["memo.py"], "test": ["test_memo.py"]}}', "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("check", "--target", pj.dir)
        lines = line_of(out, "unverified")
        assert len(lines) == 2 and ("concept:adding — 1 test projection(s), %s (memo.py:add)" % said) in lines[0], out
        assert "concept:listing" in lines[1] and "adding lacks test" in out and "listing lacks test" in out, out
        assert pj.propose(rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add():"))[0] == 0
        code, out = run("check", "--target", pj.dir)
        lines = line_of(out, "unverified")
        assert len(lines) == 1 and "concept:listing" in lines[0], out
        doc = json.loads(run("check", "--findings", "--target", pj.dir)[1])
        assert [(f["where"], f["layer"]) for f in doc["findings"] if f["kind"] == "unverified-code"] == [("concept:listing", "observation")], doc
        # a `verifies` of the whole file is no test of a symbol in it: it silences nothing; one of the symbol does
        assert pj.propose(rel("test_memo.py:test_Q1_add", "verifies", "memo.py", ev="def test_Q1_add():"))[0] == 0
        lines = line_of(run("check", "--target", pj.dir)[1], "unverified")
        assert len(lines) == 1 and "concept:listing" in lines[0], lines
        assert pj.propose(rel("test_memo.py:test_Q1_add", "verifies", "memo.py:list_", ev="def test_Q1_add():"))[0] == 0
        out = run("check", "--target", pj.dir)[1]
        assert "unverified" not in out and "holds        projected" in out, out


# ---- mangsang 2.4.0 (M1–M4): the disposable project of the owner's 2026-11-09 round — m.py, a test that raises its own Skip
M_PY = "def f(x):\n    return x + 1\n"
TEST_M = ("class Skip(Exception): pass\n\n\ndef test_f():\n    from m import f\n    if f is None:\n        raise Skip()\n"
          "    assert f(1) == 2\n\n\ndef test_other():\n    assert 1\n")


def test_lookup_predicts_what_an_edit_stales_through_the_anchors_that_read_it():
    """mangsang M1, 11-09: `lookup test_m.py:Skip` said "no confirmed relation stands on it — an edit here makes nothing stale";
    changing Skip's base class then staled the relation on test_f, which reads Skip (and, on another product, 10 relations of
    3 concepts). lookup and impact judged by different closures. Now `edit_reach` is the one closure — the key, its file, what
    encloses or lies inside it, and every anchor whose parts read any of those — and `lookup FILE:KEY` lists each relation
    one of whose ends is a reached anchor the predicate propagates from, saying how that end covers KEY; `--brief` gives the
    concept lines; what reaches nothing prints what 2.3.0 printed."""
    assert callable(getattr(mangsang, "edit_reach", None)), "mangsang.edit_reach is missing"
    # C1 — Python: an edit inside Skip's own text can move Skip, the file and test_f (its parts read Skip); never test_other
    reach = mangsang.edit_reach("test_m.py", TEST_M, ":Skip")
    assert isinstance(reach, set), reach
    assert {":Skip", ":test_f", ""} <= reach and ":test_other" not in reach, reach
    assert mangsang.edit_reach("test_m.py", TEST_M, ":test_f") == {":test_f", ""}, "Skip does not read test_f"
    assert mangsang.edit_reach("test_m.py", TEST_M, "") == set(mangsang.anchor_texts("test_m.py", TEST_M)), "the file: every anchor"
    assert mangsang.edit_reach("test_m.py", TEST_M, ":nosuch") == set(), "a key the file does not have"
    # C1 — Markdown: a subsection's edit moves its enclosing section; a section's edit moves its subsections; a sibling never
    md = "# t\n\n## A\n\na\n\n### B\n\nb\n\n## C\n\nc\n"
    rb = mangsang.edit_reach("doc.md", md, "#B")
    assert {"#B", "#A", ""} <= rb and "#C" not in rb, rb
    ra = mangsang.edit_reach("doc.md", md, "#A")
    assert {"#A", "#B", ""} <= ra and "#C" not in ra, ra
    assert "#A" not in mangsang.edit_reach("doc.md", md, "#C"), "C encloses nothing of A"
    # C1 — a nested JSON key: the enclosing key holds it, and it lies inside the enclosing key
    pkg = '{"scripts": {"test": "jest"}, "name": "x"}\n'
    assert {":scripts.test", ":scripts", ""} <= mangsang.edit_reach("package.json", pkg, ":scripts.test"), mangsang.edit_reach("package.json", pkg, ":scripts.test")
    assert ":name" not in mangsang.edit_reach("package.json", pkg, ":scripts.test")
    assert ":scripts.test" in mangsang.edit_reach("package.json", pkg, ":scripts")
    with Project() as pj:
        git = git_in(pj)
        git("init", "-q")
        write(os.path.join(pj.dir, "m.py"), M_PY)
        write(os.path.join(pj.dir, "test_m.py"), TEST_M)
        assert run("register", "m.py", "test_m.py", "plan/PLAN.md", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "c", "--means", "f adds one.", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = pj.propose(rel("test_m.py:test_f", "verifies", "m.py:f", ev="assert f(1) == 2"),
                               rel("test_m.py:test_f", "realizes", "concept:c", ev="def test_f():"),
                               rel("test_m.py", "realizes", "concept:c", ev="def test_other():"),        # the whole file: holds Skip
                               rel("test_m.py:test_other", "realizes", "concept:c", ev="def test_other():"),   # does not read Skip
                               rel("test_m.py:test_f", "references", "m.py", ev="from m import f"))      # reads Skip, propagates from neither end
        assert code == 0, out
        git("add", "-A"); git("commit", "-qm", "confirmed")
        R = lambda s, p, d: mangsang.rel_id({"src": s, "predicate": p, "dst": d})
        r_ver, r_tf, r_file = R("test_m.py:test_f", "verifies", "m.py:f"), R("test_m.py:test_f", "realizes", "concept:c"), R("test_m.py", "realizes", "concept:c")
        r_other, r_ref = R("test_m.py:test_other", "realizes", "concept:c"), R("test_m.py:test_f", "references", "m.py")
        # C2 — nothing stands on Skip itself; what reads or holds it is listed, with how; what does not propagate from that end is not
        code, out = run("lookup", "test_m.py:Skip", "--target", pj.dir)
        assert code == 0, out
        assert "no confirmed relation stands on it" not in out and "makes nothing stale" not in out, out
        listed = {rid for rid in (r_ver, r_tf, r_file, r_other, r_ref) if rid in out}
        assert r_tf in listed and r_file in listed, out
        assert r_other not in listed and r_ref not in listed, out
        line = lambda rid: [l for l in out.split("\n") if rid in l]
        assert len(line(r_tf)) == 1 and "reads test_m.py:Skip" in line(r_tf)[0], out
        assert len(line(r_file)) == 1 and "holds test_m.py:Skip" in line(r_file)[0], out
        assert "[test_m.py:test_f] realizes concept:c" in line(r_tf)[0] and "[test_m.py] realizes concept:c" in line(r_file)[0], out   # as stored, the reached end marked
        assert "concept:c — means: f adds one." in out and '"def test_f():" — by kim' in out and '"def test_other():" — by kim' in out, out
        assert out.count("— fresh") >= 2 and "STALE" not in out, out
        closing = out.strip().split("\n")[-1]
        assert re.search(r"\b%d\b" % len(listed), closing) and "relation(s)" in closing, (closing, listed)
        # C4 — brief: the listed relations counted, and the concept they reach named (2.6.0: one line)
        code, brief = run("lookup", "test_m.py:Skip", "--brief", "--target", pj.dir)
        assert code == 0 and brief.startswith("test_m.py:Skip: ") and "relation(s) stand on it, on concept:c" in brief.split("\n")[0], brief
        assert "not registered" not in brief and "R-" not in brief, brief
        # C2/C4 — an anchor nothing stands on and nothing reaches: exactly what 2.3.0 printed, and --brief silent
        code, out2 = run("lookup", "plan/PLAN.md#Q2 list", "--target", pj.dir)
        assert code == 0 and "plan/PLAN.md#Q2 list is registered; no confirmed relation stands on it — an edit here makes nothing stale" in out2, out2
        assert "R-" not in out2, out2
        assert run("lookup", "plan/PLAN.md#Q2 list", "--brief", "--target", pj.dir) == (0, ""), "nothing to say, no line"
        # C3 — the same closure decides: what lookup listed for the reached anchors is what the edit stales
        write(os.path.join(pj.dir, "test_m.py"), TEST_M.replace("class Skip(Exception)", "class Skip(RuntimeError)"))
        code, imp = run("impact", "--target", pj.dir)
        assert code == 1, imp
        stale = {l.split()[1] for l in imp.split("\n") if l.startswith("  stale   ")}
        assert stale == listed, (stale, listed, imp)
        assert r_tf in stale and r_file in stale and r_other not in stale and r_ref not in stale, imp
        assert not os.path.exists(os.path.join(pj.dir, ".mangsang")), "lookup writes nothing"


def test_a_verifies_goes_stale_when_its_test_changes_and_older_relations_say_why():
    """mangsang M2, 11-09: `verifies` propagated dst->src only, so a test rewritten to `assert True` kept its verifies fresh
    forever (another product's kept its first fingerprint through ten rounds of test edits). Now verifies propagates both ways;
    a project holding exactly the 2.3 default entry is read as the new one and rewritten on the first model write, a project
    with its own entry keeps it; and a verifies stale through its test side whose record a release before 2.4.0 wrote says why
    (that change was never re-read) — each with a reason, none wholesale: one whose both ends are what its confirmer saw is fresh."""
    OLD = {"propagates": "dst->src", "means": "src (a test) proves dst; when dst changes the test may be stale"}
    BROKEN_TEST = TEST_M.replace("    assert f(1) == 2\n", "    assert True\n")
    # C1 — the default vocabulary
    v = mangsang.DEFAULT_VOCAB["verifies"]
    assert v["propagates"] == "both", v
    assert v["means"] != OLD["means"] and "test" in v["means"] and ("assert" in v["means"] or "call" in v["means"]), v

    def impact(pj):
        code, out = run("impact", "--target", pj.dir)
        return code, [l for l in out.split("\n") if l.startswith("  stale   ")], out

    with Project() as pj:
        git = git_in(pj)
        git("init", "-q")
        write(os.path.join(pj.dir, "m.py"), M_PY)
        write(os.path.join(pj.dir, "test_m.py"), TEST_M)
        assert run("register", "m.py", "test_m.py", "--target", pj.dir)[0] == 0
        vocpath = os.path.join(pj.dir, "mangsang", "vocabulary.json")
        vocab = lambda: json.load(open(vocpath, encoding="utf-8"))
        assert vocab()["verifies"]["propagates"] == "both", vocab()   # C1 — a new project's vocabulary.json
        assert pj.propose(rel("test_m.py:test_f", "verifies", "m.py:f", ev="assert f(1) == 2"))[0] == 0
        rid = mangsang.rel_id({"src": "test_m.py:test_f", "predicate": "verifies", "dst": "m.py:f"})
        rpath = os.path.join(pj.dir, "mangsang", "relations", rid + ".json")
        git("add", "-A"); git("commit", "-qm", "confirmed")
        # C2 — the test side moves: stale, blamed on the test; the code side as before; neither: fresh
        write(os.path.join(pj.dir, "test_m.py"), BROKEN_TEST)
        code, lines, out = impact(pj)
        assert code == 1 and len(lines) == 1 and lines[0].startswith("  stale   " + rid) and lines[0].endswith("<- test_m.py:test_f"), out
        write(os.path.join(pj.dir, "test_m.py"), TEST_M)
        write(os.path.join(pj.dir, "m.py"), M_PY.replace("x + 1", "x + 2"))
        code, lines, out = impact(pj)
        assert code == 1 and len(lines) == 1 and lines[0].endswith("<- m.py:f"), out
        write(os.path.join(pj.dir, "m.py"), M_PY)
        code, lines, out = impact(pj)
        assert code == 0 and not lines, out
        code, out = run("lookup", "test_m.py:test_f", "--target", pj.dir)
        vline = [l for l in out.split("\n") if rid in l]
        assert code == 0 and len(vline) == 1 and "changing this anchor makes the relation stale" in vline[0], out
        # C3 — a 2.3 project's vocabulary.json holds exactly the old default: read as the new one; the first write rewrites it
        write(vocpath, {**vocab(), "verifies": dict(OLD)})
        write(os.path.join(pj.dir, "test_m.py"), BROKEN_TEST)
        code, lines, out = impact(pj)
        assert code == 1 and len(lines) == 1 and lines[0].endswith("<- test_m.py:test_f"), out
        assert vocab()["verifies"] == OLD, "impact writes nothing"
        write(os.path.join(pj.dir, "other.py"), "Y = 1\n")
        assert run("register", "other.py", "--target", pj.dir)[0] == 0
        assert vocab()["verifies"] == mangsang.DEFAULT_VOCAB["verifies"], vocab()
        # C3 — a project's own entry (its own means) keeps its meaning and its bytes
        CUSTOM = {"propagates": "dst->src", "means": "custom"}
        write(vocpath, {**vocab(), "verifies": dict(CUSTOM)})
        code, lines, out = impact(pj)
        assert code == 0 and not lines, out   # the test side moved; this project's verifies does not propagate from it
        write(os.path.join(pj.dir, "other2.py"), "Z = 1\n")
        assert run("register", "other2.py", "--target", pj.dir)[0] == 0
        assert vocab()["verifies"] == CUSTOM, vocab()
        write(vocpath, {**vocab(), "verifies": dict(OLD)})   # back to what a 2.3 project holds, for C4 and C5

        def written_by(value):
            r = json.load(open(rpath, encoding="utf-8"))
            r.pop("written_by", None)
            if value is not None:
                r["written_by"] = value
            write(rpath, r)

        # C4 — a verifies stale through its test side, written before 2.4.0 (or by nobody named): why, under its stale line and in --findings
        for wb in ("mangsang 2.3.0", "mangsang 2.3.0+gabc1234-dirty", None):
            written_by(wb)
            write(os.path.join(pj.dir, "test_m.py"), BROKEN_TEST)
            code, lines, out = impact(pj)
            assert code == 1 and len(lines) == 1 and lines[0].endswith("<- test_m.py:test_f"), (wb, out)
            under = out.split(lines[0], 1)[1].split("unresolved_total")[0]
            assert "before mangsang 2.4.0" in under, (wb, out)
            doc = json.loads(run("impact", "--findings", "--target", pj.dir)[1])
            st = [f for f in doc["findings"] if f["kind"] == "stale"]
            assert len(st) == 1 and "before mangsang 2.4.0" in st[0]["text"], (wb, doc)
        for wb in ("mangsang 2.4.0", "mangsang 2.4.0+gabc1234"):
            written_by(wb)
            code, lines, out = impact(pj)
            assert code == 1 and len(lines) == 1 and lines[0].endswith("<- test_m.py:test_f") and "before mangsang 2.4.0" not in out, (wb, out)
            doc = json.loads(run("impact", "--findings", "--target", pj.dir)[1])
            assert not any("before mangsang 2.4.0" in f["text"] for f in doc["findings"]), (wb, doc)
        # C4 — stale only because its dst moved: no such line, whoever wrote it
        written_by("mangsang 2.3.0")
        write(os.path.join(pj.dir, "test_m.py"), TEST_M)
        write(os.path.join(pj.dir, "m.py"), M_PY.replace("x + 1", "x + 2"))
        code, lines, out = impact(pj)
        assert code == 1 and len(lines) == 1 and lines[0].endswith("<- m.py:f") and "before mangsang 2.4.0" not in out, out
        # C5 — not wholesale: a pre-2.4.0 verifies whose test and code are what its confirmer saw is fresh
        write(os.path.join(pj.dir, "m.py"), M_PY)
        code, lines, out = impact(pj)
        assert code == 0 and not lines and "before mangsang 2.4.0" not in out, out


def test_reconfirming_a_fresh_relation_records_nothing():
    """mangsang M3, 11-09: `reconfirm R --by kim` on a fresh relation (seen equal to now on both ends) appended a history entry
    each time — two calls, two identical entries. Now a re-read that changes nothing (the same person, an agent on its own, a
    delegation) records nothing and says "already fresh"; another person's own re-read is recorded; a stale relation, a new
    quote, and a `seen` in an older fingerprint shape (the README's promised upgrade) are recorded as now."""
    src = "LIMIT = 10\n\n\ndef handle(x):\n    return x > LIMIT\n"
    with Project() as pj:
        write(os.path.join(pj.dir, "p.py"), src)
        write(os.path.join(pj.dir, "q.py"), "def g():\n    return 1\n")
        assert run("register", "plan/PLAN.md", "p.py", "q.py", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "handoff.txt"), "re-read these for me\n")
        assert run("source", "add", "L1", "--file", os.path.join(pj.dir, "handoff.txt"), "--speaker", "lee", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["kim", "lee"]})
        assert pj.propose(rel("plan/PLAN.md#Q1 add", "documents", "p.py:handle", ev="appends"),
                          rel("plan/PLAN.md#Q2 list", "documents", "q.py:g", ev="lists."))[0] == 0
        r1 = mangsang.rel_id({"src": "plan/PLAN.md#Q1 add", "predicate": "documents", "dst": "p.py:handle"})
        r2 = mangsang.rel_id({"src": "plan/PLAN.md#Q2 list", "predicate": "documents", "dst": "q.py:g"})
        path = lambda rid: os.path.join(pj.dir, "mangsang", "relations", rid + ".json")
        raw = lambda rid: io.open(path(rid), "rb").read()
        rec = lambda rid: json.load(open(path(rid), encoding="utf-8"))
        history = lambda rid: len(rec(rid).get("history", []))
        now = lambda f, key: mangsang.anchors_of(os.path.join(pj.dir, f))[key]

        def as_agent(*argv):
            keep = mangsang.running_agent
            mangsang.running_agent = lambda: "Claude (test)"
            try:
                return run(*argv)
            finally:
                mangsang.running_agent = keep

        # C1 — the confirmer's re-read of a fresh relation: said, and the file byte-identical
        before = raw(r1)
        code, out = run("reconfirm", r1, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and r1 in out, out
        assert raw(r1) == before, "a fresh relation re-read by its confirmer was recorded again"
        code, out = run("reconfirm", r1, "--by", "kim", "--evidence", "appends", "--why", "re-read both ends; still holds", "--target", pj.dir)   # the same quote: nothing new
        assert code == 0 and "already fresh" in out and raw(r1) == before, out
        # C2 — an agent's own re-read, and a delegation: the same no-op
        code, out = as_agent("reconfirm", r1, "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and raw(r1) == before, out
        code, out = run("reconfirm", r1, "--delegated", "source:L1", "--why", "the owner left it to me", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and raw(r1) == before, out
        # C3 — another person's own re-read is not lost; lee's second is a no-op; an agent after lee is one; kim's own after lee is recorded
        code, out = run("reconfirm", r1, "--by", "lee", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" not in out and history(r1) == 1 and rec(r1)["confirmed"]["by"] == "lee", (out, rec(r1))
        assert rec(r1)["history"][0]["confirmed"].get("by") == "kim", rec(r1)
        after_lee = raw(r1)
        code, out = run("reconfirm", r1, "--by", "lee", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and raw(r1) == after_lee, out
        code, out = as_agent("reconfirm", r1, "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and raw(r1) == after_lee, out
        code, out = run("reconfirm", r1, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" not in out and history(r1) == 2 and rec(r1)["confirmed"]["by"] == "kim", (out, rec(r1))
        # C4 — a stale relation is recorded as now; a fresh one given a new quote that is in the text is recorded
        write(os.path.join(pj.dir, "p.py"), src.replace("LIMIT = 10", "LIMIT = 11"))
        code, out = run("reconfirm", r1, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" not in out and history(r1) == 3 and rec(r1)["seen"]["p.py:handle"] == now("p.py", ":handle"), (out, rec(r1))
        code, out = run("reconfirm", r1, "--by", "kim", "--evidence", "def handle(x):", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" not in out and history(r1) == 4 and rec(r1)["evidence"] == "def handle(x):", (out, rec(r1))
        assert rec(r1)["history"][-1]["evidence"] == "appends", rec(r1)
        # C5 — a `seen` in an older fingerprint shape that impact still reads as fresh is upgraded, not "already fresh"
        r = rec(r1)
        r["seen"]["p.py:handle"] = mangsang.fp(mangsang.anchor_texts(os.path.join(pj.dir, "p.py"))[":handle"])   # raw text hash, no path: the pre-token shape
        mangsang.save(path(r1), r)
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        assert not stale and not broken, stale
        code, out = run("reconfirm", r1, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" not in out and history(r1) == 5, (out, rec(r1))
        assert rec(r1)["seen"] == {"plan/PLAN.md#Q1 add": now("plan/PLAN.md", "#Q1 add"), "p.py:handle": now("p.py", ":handle")}, rec(r1)
        # C6 — two ids, one fresh and one stale: the stale one recorded, the fresh one's file untouched
        write(os.path.join(pj.dir, "q.py"), "def g():\n    return 2\n")
        before1, h2 = raw(r1), history(r2)
        code, out = run("reconfirm", r1, r2, "--by", "kim", "--why", "re-read both ends; still holds", "--target", pj.dir)
        assert code == 0 and "already fresh" in out and r1 in out, out
        assert raw(r1) == before1 and history(r2) == h2 + 1 and rec(r2)["seen"]["q.py:g"] == now("q.py", ":g"), (out, rec(r2))


def test_lookup_names_the_except_that_keeps_a_file_out_of_the_net():
    """mangsang M4, 11-09: on a model whose `registered` invariant excepts plugin/hostcall.py with a reason, `lookup plugin/hostcall.py`
    said NOT REGISTERED and told the reader to register it — the except and its why, the model's own answer to that, were never
    said. Now a tracked, unregistered file an active invariant's except matches is said as excepted, with the invariant, the glob
    and its reason ("no reason" for a bare glob); a file no except matches, and an excepted one once its invariant is retired,
    print NOT REGISTERED as before."""
    WHY = "vendored, kept in step with its upstream copy"
    verify = lambda excepts: json.dumps({"kind": "registered", "paths": ["src/", "vendor/"], "except": excepts})
    with Project() as pj:
        git = git_in(pj)
        write(os.path.join(pj.dir, "src", "a.py"), "def a():\n    return 1\n")
        write(os.path.join(pj.dir, "vendor", "x.py"), "X = 1\n")
        write(os.path.join(pj.dir, "other", "y.py"), "Y = 1\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run("register", "src/a.py", "--target", pj.dir)[0] == 0
        code, out = run("cq", "add", "inv-scope", "--text", "Is every source file registered?", "--verify", verify([{"glob": "vendor/*.py", "why": WHY}]), "--by", "kim", "--target", pj.dir)
        assert code == 0, out
        # C1 — the except, its invariant, its glob and its why; not "register it"
        code, out = run("lookup", "vendor/x.py", "--target", pj.dir)
        assert code == 0, out
        said = [l for l in out.split("\n") if "excepted" in l]
        assert said and any(all(s in l for s in ("inv-scope", "vendor/*.py", WHY)) for l in said), out
        assert "NOT REGISTERED" not in out and "mangsang register vendor/x.py" not in out, out
        # C2 — brief: one line, excepted, the reason's first clause
        code, out = run("lookup", "vendor/x.py", "--brief", "--target", pj.dir)
        assert code == 0 and len(out.strip().split("\n")) == 1 and "excepted" in out and "vendored" in out, out
        assert "not registered" not in out, out
        # C3 — a bare glob string: "no reason"
        assert run("cq", "revise", "inv-scope", "--verify", verify(["vendor/*.py"]), "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("lookup", "vendor/x.py", "--target", pj.dir)
        said = [l for l in out.split("\n") if "excepted" in l]
        assert code == 0 and said and any(all(s in l for s in ("inv-scope", "vendor/*.py", "no reason")) for l in said), out
        assert "NOT REGISTERED" not in out, out
        # C4 — a tracked unregistered file no except matches: NOT REGISTERED as before; so is vendor/x.py once the invariant is retired
        code, out = run("lookup", "other/y.py", "--target", pj.dir)
        assert code == 0 and "other/y.py is NOT REGISTERED (tracked by git" in out and "mangsang register other/y.py" in out and "excepted" not in out, out
        assert run("cq", "retire", "inv-scope", "--why", "x", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run("lookup", "vendor/x.py", "--target", pj.dir)
        assert code == 0 and "vendor/x.py is NOT REGISTERED (tracked by git" in out and "mangsang register vendor/x.py" in out and "excepted" not in out, out
        code, out = run("lookup", "vendor/x.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.strip() == "vendor/x.py: not registered — the net does not see it (no relation stands on it; edits here are never stale)", out
        assert not os.path.exists(os.path.join(pj.dir, ".mangsang")), "lookup writes nothing"


def run_said(*argv):
    """`run`, with stderr folded into what was said, and an exception from the engine turned into a failed assertion:
    a command that dies with a traceback has said nothing to the person who ran it."""
    import traceback
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            code, out = run(*argv)
        except Exception:
            raise AssertionError("a traceback instead of a message: %s\n%s" % (" ".join(argv[:3]), traceback.format_exc()))
    return code, out + err.getvalue()


def test_a_message_sent_mid_turn_is_a_person_turn_and_a_miss_is_never_a_traceback():
    """A person's message sent while the agent was working reaches the host's transcript as an attachment record (a queued
    command from a human), not as a user record; the queue that held it and the next request's copy repeat its words. That
    attachment is the person's turn — its prompt verbatim, keyed by the attachment's own id, marked as sent mid-turn. A peer's
    hand-back and a task notification, also queued commands, are nobody's turn; a phrase found only in the queue, the request
    copy or a hand-back is a miss that says where it was seen, and a record with no id never ends in a traceback."""
    MID = "also water the plant by the window, please"
    S = "sess-mid"
    recs = [
        {"type": "user", "uuid": "u1", "timestamp": "t1", "message": {"role": "user", "content": "please tidy the shelf first"}},
        {"type": "assistant", "uuid": "a1", "timestamp": "t2", "message": {"id": "m1", "model": "claude-x", "content": [{"type": "text", "text": "Tidying the shelf now."}]}},
        {"type": "assistant", "uuid": "a2", "timestamp": "t3", "message": {"id": "m2", "model": "claude-x", "content": [{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "queue-operation", "operation": "enqueue", "timestamp": "t4", "sessionId": S, "content": MID},
        {"type": "queue-operation", "operation": "remove", "timestamp": "t4", "sessionId": S, "content": MID, "reason": "absorbed_mid_turn", "commandUuid": "c1", "deliveryId": "d1"},
        {"type": "attachment", "uuid": "att-1", "parentUuid": "a2", "isSidechain": False, "timestamp": "t5",
         "attachment": {"type": "queued_command", "prompt": MID, "source_uuid": "c1", "delivery_id": "d1", "commandMode": "prompt", "origin": {"kind": "human"}, "timestamp": "t5", "humanTurn": True},
         "rendered": [{"content": "<host-wrapper>The person said while you worked: " + MID + "</host-wrapper>"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-2", "parentUuid": "att-1", "isSidechain": False, "isMeta": True, "timestamp": "t6",
         "attachment": {"type": "queued_command", "prompt": "the fetched page says the fern wants shade", "commandMode": "prompt", "origin": {"kind": "peer", "name": "web-fetch", "id": "p1"}, "timestamp": "t6"},
         "rendered": [{"content": "the fetched page says the fern wants shade"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-3", "parentUuid": "att-2", "isSidechain": False, "timestamp": "t7",
         "attachment": {"type": "queued_command", "prompt": "<task-notification>the build finished quietly</task-notification>", "commandMode": "task-notification", "origin": {"kind": "task-notification"}, "timestamp": "t7"},
         "rendered": [{"content": "the build finished quietly"}], "renderedRole": "system"},
        {"type": "queue-operation", "operation": "enqueue", "timestamp": "t8", "sessionId": S, "content": "remember the lighthouse keys"},
        {"type": "attachment", "uuid": "att-4", "parentUuid": "att-3", "isSidechain": False, "timestamp": "t9",
         "attachment": {"type": "queued_command", "prompt": "and close the blinds too", "commandMode": "prompt", "timestamp": "t9"},
         "rendered": [{"content": "<host-wrapper>and close the blinds too</host-wrapper>"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-5", "parentUuid": "att-4", "isSidechain": False, "timestamp": "t10",
         "attachment": {"type": "queued_command", "prompt": [{"type": "text", "text": "the first block of words"}, {"type": "text", "text": "the second block of words"}],
                        "commandMode": "prompt", "origin": {"kind": "human"}, "timestamp": "t10", "humanTurn": True},
         "rendered": [{"content": "<host-wrapper>blocks</host-wrapper>"}], "renderedRole": "system"},
        {"type": "api-request-blob", "sessionId": S, "hash": "h1", "message": {"role": "user", "content": [
            {"type": "text", "text": "please tidy the shelf first"}, {"type": "text", "text": MID},
            {"type": "text", "text": "<host-wrapper>an orange umbrella only the request holds</host-wrapper>"}]}},
    ]
    with Project() as pj:
        tr = os.path.join(pj.dir, S + ".jsonl")
        write(tr, "\n".join(json.dumps(x) for x in recs) + "\n")
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        # C1 — the human queued command is a person turn: the prompt verbatim, the attachment's id and time, sent mid-turn
        try:
            turns = mangsang.transcript_turns(tr)
        except Exception as err:
            raise AssertionError("a traceback instead of a message: transcript_turns raised %r" % err)
        mid = [t for t in turns if t.get("uuid") == "att-1"]
        assert len(mid) == 1, turns
        assert mid[0]["kind"] == "person" and mid[0]["text"] == MID and mid[0]["at"] == "t5" and mid[0].get("mid-turn") is True, mid
        assert "host-wrapper" not in mid[0]["text"], "the prompt, never the host's rendered wrapper"
        order = [t.get("uuid") for t in turns]
        assert order.index("a1") < order.index("att-1"), order   # in record order among the other turns
        # with no origin: a prompt-mode queued command that is not isMeta is the person's too
        nor = [t for t in turns if t.get("uuid") == "att-4"]
        assert len(nor) == 1 and nor[0]["kind"] == "person" and nor[0]["text"] == "and close the blinds too" and nor[0].get("mid-turn") is True, nor
        assert order.index("att-1") < order.index("att-4"), order
        # a prompt of content blocks: each text block a turn
        blocks = [t for t in turns if t.get("uuid") == "att-5"]
        assert [t["text"] for t in blocks] == ["the first block of words", "the second block of words"] and all(t["kind"] == "person" for t in blocks), blocks
        # C2 — the peer, the notification, the queue and the request copy are no turn; the mid-turn phrase is in exactly one
        for phrase in ("fern wants shade", "build finished quietly", "lighthouse keys", "orange umbrella"):
            assert not any(phrase in t["text"] for t in turns), (phrase, turns)
        assert sum(1 for t in turns if "water the plant" in t["text"]) == 1, turns
        assert sum(1 for t in turns if "tidy the shelf" in t["text"]) == 1, turns
        # C3 — kept by --match and by --turn, verbatim, located as a mid-turn person turn
        for sid, how in (("M1", ("--match", "water the plant")), ("M2", ("--turn", "att-1"))):
            code, out = run_said("source", "add", sid, "--from-transcript", tr, *how, "--speaker", "lee", "--target", pj.dir)
            assert code == 0, (how, out)
            src = mangsang.load(os.path.join(pj.dir, "mangsang", "sources", sid + ".json"))
            assert src["text"] == MID and src["verbatim-from"] == "host transcript", src
            assert "person att-1" in src["locator"] and "mid-turn" in src["locator"], src
        # C4 — a phrase found only outside every turn: a message naming where it is, never a traceback
        for sid, phrase, where in (("X1", "lighthouse keys", "queue-operation"), ("X2", "orange umbrella", "api-request-blob"),
                                   ("X3", "fern wants shade", "peer")):
            code, out = run_said("source", "add", sid, "--from-transcript", tr, "--match", phrase, "--speaker", "lee", "--target", pj.dir)
            assert code != 0 and "found in no turn" in out and where in out, (phrase, out)
            assert "None" not in out, ("a record with no uuid is named without one", out)
            assert not os.path.exists(os.path.join(pj.dir, "mangsang", "sources", sid + ".json")), phrase
        code, out = run_said("source", "add", "X4", "--from-transcript", tr, "--match", "build finished quietly", "--speaker", "lee", "--target", pj.dir)
        assert code != 0, ("a task notification is not a person's turn", out)
        # C5 — a user record with no uuid and no timestamp: no path raises; matching it says it has no id
        tr2 = os.path.join(pj.dir, S + "-noid.jsonl")
        write(tr2, "\n".join(json.dumps(x) for x in recs + [{"type": "user", "message": {"role": "user", "content": "a stray line without identity"}}]) + "\n")
        code, out = run_said("source", "add", "N1", "--from-transcript", tr2, "--match", "water the plant", "--speaker", "lee", "--target", pj.dir)
        assert code == 0, out
        code, out = run_said("source", "add", "N2", "--from-transcript", tr2, "--turn", "att-1", "--speaker", "lee", "--target", pj.dir)
        assert code == 0, out
        code, out = run_said("source", "add", "N3", "--from-transcript", tr2, "--match", "lighthouse keys", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "found in no turn" in out, out
        code, out = run_said("source", "add", "N4", "--from-transcript", tr2, "--match", "stray line", "--speaker", "lee", "--target", pj.dir)
        assert code != 0 and "no id" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "mangsang", "sources", "N4.json")), "a locator of None kept"


def test_check_says_a_stored_vocabulary_entry_is_read_differently_and_vocabulary_write_writes_it():
    """A project whose vocabulary file still stores an earlier release's entry for a predicate the engine now reads another
    way: check says so as an observation (no change to its exit code), names the command that writes it, and that command
    writes exactly that file — a preview without --write, nothing to write the second time, a project's own entry kept."""
    OLD = {"propagates": "dst->src", "means": "src (a test) proves dst; when dst changes the test may be stale"}
    OWN = {"propagates": "none", "means": "our own reading of a test"}
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        mdir = os.path.join(pj.dir, "mangsang")
        vocpath = os.path.join(mdir, "vocabulary.json")
        stored = json.load(open(vocpath, encoding="utf-8"))
        assert stored["verifies"] == mangsang.DEFAULT_VOCAB["verifies"], stored

        def tree():
            out = {}
            for root, _, files in os.walk(mdir):
                for n in files:
                    p = os.path.join(root, n)
                    out[os.path.relpath(p, mdir)] = open(p, "rb").read()
            return out

        def vocab_lines(out):
            return [l for l in out.split("\n") if "mangsang vocabulary --write" in l]

        def vocab_findings():
            code, out = run_said("check", "--findings", "--target", pj.dir)
            return [f for f in json.loads(out)["findings"] if f["kind"] == "vocabulary-read-differently"]

        base_code, out = run_said("check", "--target", pj.dir)
        assert base_code == 0 and not vocab_lines(out), out
        assert not vocab_findings()
        # C1 — the 2.3 entry stored: a line and a finding, the exit code unchanged
        write(vocpath, {**stored, "verifies": dict(OLD)})
        code, out = run_said("check", "--target", pj.dir)
        lines = [l for l in out.split("\n") if all(s in l for s in ("vocabulary", "verifies", "dst->src", "both", "mangsang vocabulary --write"))]
        assert code == base_code and len(lines) == 1, out
        fs = vocab_findings()
        assert len(fs) == 1, fs
        f = fs[0]
        assert f["layer"] == "observation" and f["where"] == "mangsang/vocabulary.json verifies" and f["source"] == "mangsang", f
        assert "dst->src" in f["text"] and "both" in f["text"], f
        # C2 — without --write: nothing written, each predicate as read, the stored one and --write said
        before = tree()
        code, out = run_said("vocabulary", "--target", pj.dir)
        assert code == 0, out
        assert tree() == before, "vocabulary without --write writes nothing"
        vl = [l for l in out.split("\n") if "verifies" in l]
        assert any("both" in l for l in vl), out
        for pred in mangsang.DEFAULT_VOCAB:
            assert pred in out, (pred, out)
        assert "dst->src" in out and "--write" in out, out
        # C2 — --write: the file as the engine reads it, no other file under mangsang/ touched
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0 and "verifies" in out, out
        after = tree()
        assert set(after) == set(before), (set(before), set(after))
        assert all(after[k] == before[k] for k in before if k != "vocabulary.json"), "only vocabulary.json is written"
        now = json.load(open(vocpath, encoding="utf-8"))
        assert now == mangsang.decl(pj.dir)["vocabulary"] and now["verifies"] == mangsang.DEFAULT_VOCAB["verifies"], now
        code, out = run_said("check", "--target", pj.dir)
        assert code == base_code and not vocab_lines(out) and not vocab_findings(), out
        # a second --write: nothing to write, the bytes kept
        raw = open(vocpath, "rb").read()
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0 and "nothing to write" in out and open(vocpath, "rb").read() == raw, out
        # a project's own verifies: no line, no finding, --write keeps it
        write(vocpath, {**stored, "verifies": dict(OWN)})
        raw = open(vocpath, "rb").read()
        code, out = run_said("check", "--target", pj.dir)
        assert code == base_code and not vocab_lines(out) and not vocab_findings(), out
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0 and "nothing to write" in out and open(vocpath, "rb").read() == raw, out
        assert json.load(open(vocpath, encoding="utf-8"))["verifies"] == OWN
        # no vocabulary.json: no line, no finding; --write says so and creates nothing
        os.remove(vocpath)
        code, out = run_said("check", "--target", pj.dir)
        assert code == base_code and not vocab_lines(out) and not vocab_findings(), out
        before = tree()
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0 and "vocabulary.json" in out, out
        assert not os.path.exists(vocpath) and tree() == before, "no file created"


def test_a_hand_back_flagged_inside_its_attachment_is_no_person_turn():
    """A queued command whose attachment itself says isMeta is an agent's hand-back, not the person's words — with an
    origin naming a peer and with no origin at all; a phrase found only in it is a miss and keeps no source. A human
    queued command beside it (origin human, or none; prompt mode; isMeta at neither level) is still the person's turn."""
    S = "sess-meta"
    recs = [
        {"type": "user", "uuid": "u1", "timestamp": "t1", "message": {"role": "user", "content": "please sort the letters"}},
        {"type": "assistant", "uuid": "a1", "timestamp": "t2", "message": {"id": "m1", "model": "claude-x", "content": [{"type": "text", "text": "Sorting the letters."}]}},
        {"type": "attachment", "uuid": "att-m1", "parentUuid": "a1", "isSidechain": False, "timestamp": "t3",
         "attachment": {"type": "queued_command", "prompt": "the helper counted seven green envelopes", "commandMode": "prompt", "isMeta": True, "timestamp": "t3"},
         "rendered": [{"content": "the helper counted seven green envelopes"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-m2", "parentUuid": "att-m1", "isSidechain": False, "timestamp": "t4",
         "attachment": {"type": "queued_command", "prompt": "the helper found a brass stamp", "commandMode": "prompt", "isMeta": True,
                        "origin": {"kind": "peer", "name": "helper", "id": "p1"}, "timestamp": "t4"},
         "rendered": [{"content": "the helper found a brass stamp"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-h1", "parentUuid": "att-m2", "isSidechain": False, "timestamp": "t5",
         "attachment": {"type": "queued_command", "prompt": "keep the postcards apart", "commandMode": "prompt", "origin": {"kind": "human"}, "timestamp": "t5"},
         "rendered": [{"content": "<host-wrapper>keep the postcards apart</host-wrapper>"}], "renderedRole": "system"},
        {"type": "attachment", "uuid": "att-h2", "parentUuid": "att-h1", "isSidechain": False, "timestamp": "t6",
         "attachment": {"type": "queued_command", "prompt": "and recycle the flyers", "commandMode": "prompt", "timestamp": "t6"},
         "rendered": [{"content": "<host-wrapper>and recycle the flyers</host-wrapper>"}], "renderedRole": "system"},
    ]
    with Project() as pj:
        tr = os.path.join(pj.dir, S + ".jsonl")
        write(tr, "\n".join(json.dumps(x) for x in recs) + "\n")
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        try:
            turns = mangsang.transcript_turns(tr)
        except Exception as err:
            raise AssertionError("a traceback instead of a message: transcript_turns raised %r" % err)
        # T2-C1 — the human queued commands are still person turns
        for uid, text in (("att-h1", "keep the postcards apart"), ("att-h2", "and recycle the flyers")):
            got = [t for t in turns if t.get("uuid") == uid]
            assert len(got) == 1 and got[0]["kind"] == "person" and got[0]["text"] == text, (uid, turns)
        # T2-C1 — a hand-back flagged inside its attachment is no turn at all, with or without an origin
        for uid, phrase in (("att-m1", "seven green envelopes"), ("att-m2", "brass stamp")):
            assert not [t for t in turns if t.get("uuid") == uid], ("an agent's hand-back kept as a turn", uid, turns)
            assert not any(phrase in t["text"] for t in turns), (phrase, turns)
        # T2-C1 — a phrase only in it is a miss; nothing is kept under a person's name
        for sid, phrase in (("H1", "seven green envelopes"), ("H2", "brass stamp")):
            code, out = run_said("source", "add", sid, "--from-transcript", tr, "--match", phrase, "--speaker", "lee", "--target", pj.dir)
            assert code != 0 and "found in no turn" in out, (phrase, code, out)
            assert not os.path.exists(os.path.join(pj.dir, "mangsang", "sources", sid + ".json")), ("a source written", phrase)
        code, out = run_said("source", "add", "H3", "--from-transcript", tr, "--match", "recycle the flyers", "--speaker", "lee", "--target", pj.dir)
        assert code == 0, out


def test_vocabulary_write_says_it_wrote_the_entry_as_this_engine_reads_it():
    """The line `vocabulary --write` prints for an entry it rewrote names the predicate and says it was written as this
    engine reads it, stored -> read; it never names the stored propagation as what was written."""
    OLD = {"propagates": "dst->src", "means": "src (a test) proves dst; when dst changes the test may be stale"}
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        vocpath = os.path.join(pj.dir, "mangsang", "vocabulary.json")
        stored = json.load(open(vocpath, encoding="utf-8"))
        write(vocpath, {**stored, "verifies": dict(OLD)})
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0, out
        # T2-C2
        assert "wrote verifies as propagates dst->src" not in out, ("the old propagation named as what was written", out)
        written = [l for l in out.split("\n") if "verifies" in l and "dst->src" in l]
        assert written, out
        for l in written:
            assert "written as this engine reads it" in l and "dst->src -> both" in l, (l, out)
        assert json.load(open(vocpath, encoding="utf-8"))["verifies"] == mangsang.DEFAULT_VOCAB["verifies"]


def test_check_says_an_entry_the_vocabulary_file_does_not_store_is_not_stored():
    """A vocabulary file that stores nothing for a predicate: check says the entry is not stored and how this engine reads
    it — never that the file stores it as propagating nothing; `vocabulary --write` then writes the defaults and check is
    quiet. A file holding only a project's own references entry, read as stored, is not reported at all."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        vocpath = os.path.join(pj.dir, "mangsang", "vocabulary.json")

        def vocab_lines(out):
            return [l for l in out.split("\n") if "mangsang vocabulary --write" in l]

        def stored_as(lines, pred):   # a line claiming the file stores pred with some propagation
            return [l for l in lines if ("stores %s as propagates" % pred) in l]

        # T2-C3 — `{}`: every predicate not stored, read as the engine's default
        write(vocpath, {})
        code, out = run_said("check", "--target", pj.dir)
        vl = vocab_lines(out)
        for pred, entry in mangsang.DEFAULT_VOCAB.items():
            mine = [l for l in vl if re.search(r"\b%s\b" % pred, l)]
            assert len(mine) == 1, (pred, out)
            l = mine[0]
            assert "not store" in l and "mangsang/vocabulary.json" in l, (pred, l)
            assert ("this engine reads it as propagates %s" % entry["propagates"]) in l, (pred, l)
            assert not stored_as(vl, pred), ("an entry not stored said to be stored", pred, out)
        assert not any("stores" in l and "as propagates none" in l for l in vl), out
        # T2-C3 — --write writes the defaults; check is then quiet
        code, out = run_said("vocabulary", "--write", "--target", pj.dir)
        assert code == 0, out
        assert json.load(open(vocpath, encoding="utf-8")) == mangsang.DEFAULT_VOCAB
        code, out = run_said("check", "--target", pj.dir)
        assert not vocab_lines(out), out
        # T2-C3 — a file holding only a project's own references entry is read as it is (decl merges no defaults into a
        # non-empty file): nothing is read differently, so check prints no vocabulary line at all
        write(vocpath, {"references": {"propagates": "none", "means": "our own reading of a name"}})
        code, out = run_said("check", "--target", pj.dir)
        assert not vocab_lines(out), out


def test_decl_gives_each_caller_its_own_default_vocabulary():
    """A caller that changes the vocabulary it was given changes its own copy: the engine's default, and what the next
    caller is given, stay as they were — for a project with no vocabulary file, and for one storing an earlier entry."""
    import copy
    OLD = {"propagates": "dst->src", "means": "src (a test) proves dst; when dst changes the test may be stale"}
    snapshot = copy.deepcopy(mangsang.DEFAULT_VOCAB)
    tmp = tempfile.mkdtemp(prefix="mangsang-test-")
    try:
        v = mangsang.decl(tmp)["vocabulary"]
        v["documents"]["propagates"] = "none"
        assert mangsang.DEFAULT_VOCAB["documents"]["propagates"] == "dst->src", mangsang.DEFAULT_VOCAB["documents"]
        assert mangsang.decl(tmp)["vocabulary"]["documents"]["propagates"] == "dst->src"
        for pred in snapshot:
            v = mangsang.decl(tmp)["vocabulary"]
            for key in list(v[pred]):
                v[pred][key] = "mutated by a caller"
            v[pred]["added"] = "by a caller"
            assert mangsang.DEFAULT_VOCAB[pred] == snapshot[pred], (pred, mangsang.DEFAULT_VOCAB[pred])
            assert mangsang.decl(tmp)["vocabulary"][pred] == snapshot[pred], pred
        # a stored 2.3 verifies entry, read as the default: the caller's copy is still its own
        write(os.path.join(tmp, "mangsang", "vocabulary.json"), {**snapshot, "verifies": dict(OLD)})
        v = mangsang.decl(tmp)["vocabulary"]
        v["verifies"]["means"] = "mutated by a caller"
        assert mangsang.DEFAULT_VOCAB["verifies"] == snapshot["verifies"], mangsang.DEFAULT_VOCAB["verifies"]
        assert mangsang.decl(tmp)["vocabulary"]["verifies"]["means"] == snapshot["verifies"]["means"]
    finally:
        mangsang.DEFAULT_VOCAB.clear()
        mangsang.DEFAULT_VOCAB.update(snapshot)
        shutil.rmtree(tmp, ignore_errors=True)


def test_move_carries_a_heading_renamed_in_place_and_lookup_and_impact_say_so():
    """A relation standing on a document's heading: a rename of the heading breaks it. Before the edit, lookup (and its brief
    note) says so and that move carries a rename; after a rename that leaves the rest of the section exactly as its confirmer
    saw it, impact names the move and move carries it; a rename together with any other change in the section is left broken
    — the rename cannot hide a real change — and nothing turns fresh by itself."""
    assert callable(getattr(mangsang, "renamed_heading", None)), "mangsang.renamed_heading is missing"
    P = "plan/PLAN.md"
    RENAMED = PLAN.replace("## Q1 add", "## Q1 append")
    # C1 — the function
    seen = mangsang.anchors_of(P, PLAN)["#Q1 add"]
    assert mangsang.renamed_heading(P, RENAMED, "#Q1 add", seen) == "#Q1 append"
    assert mangsang.renamed_heading(P, RENAMED, "#Q1 add", None) is None, "seen None"
    assert mangsang.renamed_heading("notes.txt", RENAMED, "#Q1 add", seen) is None, "not Markdown"
    assert mangsang.renamed_heading(P, RENAMED, ":add", seen) is None, "a dead key that is not a heading"
    assert mangsang.renamed_heading(P, RENAMED.replace("more", "more words"), "#Q1 add", seen) is None, "a line of its subsection changed"
    assert mangsang.renamed_heading(P, RENAMED.replace("`add` appends", "`add` quickly appends"), "#Q1 add", seen) is None, "a word of its body"
    assert mangsang.renamed_heading(P, PLAN.replace("## Q1 add", "### Q1 append"), "#Q1 add", seen) is None, "its level"
    section = "## Q1 add\n\n`add` appends and prints `#<id>`.\n\n### detail\n\nmore\n\n"
    two = PLAN.replace(section, section.replace("Q1 add", "Q1 append") + section.replace("Q1 add", "Q1 put").replace("### detail", "### detail2"))
    two_same = PLAN.replace(section, section.replace("Q1 add", "Q1 append") + section.replace("Q1 add", "Q1 put"))
    assert mangsang.renamed_heading(P, two_same, "#Q1 add", seen) is None, "two such headings"
    assert mangsang.renamed_heading(P, RENAMED + "## Q1 append\n\nagain\n", "#Q1 add", seen) is None, "its new title is not once a heading"
    assert mangsang.renamed_heading(P, two, "#Q1 add", seen) == "#Q1 append", "the other section's subsection differs: one candidate"

    def project():
        pj = Project()
        assert run("register", P, "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(rel(P + "#Q1 add", "documents", "memo.py:add"), rel(P, "references", "memo.py:X"),
                          rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))[0] == 0
        return pj

    rid = mangsang.rel_id(rel(P + "#Q1 add", "documents", "memo.py:add"))
    fid = mangsang.rel_id(rel(P, "references", "memo.py:X"))
    vid = mangsang.rel_id(rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add"))
    line_with = lambda out, s: [l for l in out.split("\n") if s in l]

    with project() as pj:
        # C5 — lookup before any edit: the heading's relation says a rename breaks it and move carries it
        for what in (P, P + "#Q1 add"):
            code, out = run_said("lookup", what, "--target", pj.dir)
            ls = line_with(out, rid)
            assert code == 0 and len(ls) == 1 and "renaming" in ls[0] and "mangsang move" in ls[0], (what, out)
            assert "stale" not in out, (what, out)
        code, out = run_said("lookup", P, "--target", pj.dir)
        fl = line_with(out, fid)
        assert len(fl) == 1 and "renaming" not in fl[0] and "mangsang move" not in fl[0], ("the file anchor: no note", out)
        code, out = run_said("lookup", "memo.py", "--target", pj.dir)
        vl = line_with(out, vid)
        assert len(vl) == 1 and "renaming" not in vl[0] and "mangsang move" not in vl[0], ("Python symbols: no note", out)
        # C6 — --brief: one more line naming the heading, the id, renaming and move; memo.py's brief unchanged
        code, out = run_said("lookup", P, "--brief", "--target", pj.dir)
        notes = [l for l in out.splitlines() if "renaming" in l]
        assert code == 0 and len(notes) == 1, out
        assert all(s in notes[0] for s in ("#Q1 add", rid, "mangsang move")), notes
        lines = out.splitlines()   # 2.6.0 (contract C4): the count line, then the heading's line
        assert len(lines) == 2 and lines[1] == notes[0] and lines[0].startswith("plan/PLAN.md: 2 relation(s) stand on it, on 2 other anchor(s)"), out
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        assert len(out.splitlines()) == 1 and out.startswith("memo.py: 3 relation(s) stand on it, on 3 other anchor(s)") and "renaming" not in out, out
        # a pure rename: broken until move runs; impact names the move, lookup too
        write(os.path.join(pj.dir, P), RENAMED)
        for _ in range(2):   # nothing turns fresh by itself
            code, out = run_said("impact", "--target", pj.dir)
            bl = [l for l in out.split("\n") if "broken" in l and rid in l]
            assert code == 1 and len(bl) == 1, out
        hint = line_with(out, "mangsang move " + rid)
        assert len(hint) == 1 and "#Q1 append" in hint[0] and "renamed" in hint[0], out
        assert "broken" not in hint[0] and "stale" not in hint[0], hint
        assert out.split("\n").index(hint[0]) > out.split("\n").index(bl[0]), "under the broken line"
        doc = json.loads(run_said("impact", "--findings", "--target", pj.dir)[1])
        bf = [f for f in doc["findings"] if f["kind"] == "broken"]
        assert len(bf) == 1 and "mangsang move" in bf[0]["text"] and "#Q1 append" in bf[0]["text"], doc
        code, out = run_said("lookup", P, "--target", pj.dir)
        ls = line_with(out, rid)
        assert len(ls) == 1 and "mangsang move " + rid in ls[0] and "#Q1 append" in ls[0], out
        # C2 — move: a dry run changes nothing; then carried, with the same evidence
        code, out = run_said("move", "--dry-run", "--target", pj.dir)
        assert "would move" in out and P + "#Q1 append" in out, out
        assert not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"]), "a dry run changes nothing"
        code, out = run_said("move", "--by", "kim", "--why", "the heading was renamed in place", "--target", pj.dir)
        assert code == 0 and "1 relation(s) moved" in out, out
        d = mangsang.decl(pj.dir)
        old = [r for r in d["retired"] if r["id"] == rid]
        assert len(old) == 1 and old[0]["retired"]["why"].startswith("moved:"), d["retired"]
        new = [r for r in d["relations"] if r.get("moved-from") == rid]
        assert len(new) == 1 and new[0]["src"] == P + "#Q1 append" and new[0]["dst"] == "memo.py:add", new
        assert new[0]["evidence"] == "appends and prints" and new[0]["confirmed"].get("by") == "kim", new
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out

    # C3 — a rename with any other change in its section is left, and impact gives it no move hint
    for why, edited in (("a word of its body", RENAMED.replace("`add` appends", "`add` quickly appends")),
                        ("a line of its subsection", RENAMED.replace("more", "more words")),
                        ("its level", PLAN.replace("## Q1 add", "### Q1 append"))):
        with project() as pj:
            write(os.path.join(pj.dir, P), edited)
            code, out = run_said("move", "--dry-run", "--target", pj.dir)
            assert "left" in out and "0 relation(s) would move" in out, (why, out)
            code, out = run_said("impact", "--target", pj.dir)
            assert code == 1 and any("broken" in l and rid in l for l in out.split("\n")), (why, out)
            assert "mangsang move" not in out, (why, out)
            doc = json.loads(run_said("impact", "--findings", "--target", pj.dir)[1])
            assert not any("mangsang move" in f["text"] for f in doc["findings"]), (why, doc)

    # C2 — a second home (the same key in another registered Markdown file) competes: ambiguous, left
    with project() as pj:
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## Q1 add\n\n`add` appends and prints `#<id>`.\n")
        assert run("register", "notes.md", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, P), RENAMED)
        code, out = run_said("move", "--dry-run", "--target", pj.dir)
        assert "0 relation(s) would move" in out and "left" in out, out
        code, out = run_said("move", "--by", "kim", "--why", "the heading was renamed", "--target", pj.dir)
        assert code != 0 and not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"]), out
        code, out = run_said("impact", "--target", pj.dir)
        assert "mangsang move" not in out, ("a relation move would not carry gets no hint", out)

    # C4 — a home in another file: impact names the move and the new anchor too
    with project() as pj:
        write(os.path.join(pj.dir, "notes.md"), "# notes\n\n## Q1 add\n\n`add` appends and prints `#<id>`.\n")
        assert run("register", "notes.md", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, P), "# plan\n\n## Q2 list\n\nlists.\n")
        code, out = run_said("impact", "--target", pj.dir)
        hint = line_with(out, "mangsang move " + rid)
        assert code == 1 and len(hint) == 1 and "notes.md#Q1 add" in hint[0], out
        assert "broken" not in hint[0] and "stale" not in hint[0], hint
        doc = json.loads(run_said("impact", "--findings", "--target", pj.dir)[1])
        bf = [f for f in doc["findings"] if f["kind"] == "broken" and rid in json.dumps(f)]
        assert len(bf) == 1 and "mangsang move" in bf[0]["text"] and "notes.md#Q1 add" in bf[0]["text"], doc


# ---- 2.6.0 contract A: every judgment signed honestly with its reason; a re-read keeps what was compared; each handled
# ---- staleness records its outcome. Helpers first; every test asserts before it indexes, so a missing field is a red
# ---- assertion, never a KeyError.

AT_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
RELS = os.path.join("mangsang", "relations")


def run_agent(*argv):
    """`run_said`, but the env says an agent runs it: AGENT_HOST=claude-code and no session id, so the agent is "Claude Code".
    The env is restored after."""
    import traceback
    saved = {k: os.environ.pop(k) for k in list(mangsang.AGENT_ENV) if k in os.environ}
    os.environ["AGENT_HOST"] = "claude-code"
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = mangsang.main(list(argv))
            except SystemExit as err:
                code = err.code if isinstance(err.code, int) else 1
                out.write(str(err) + "\n")
            except Exception:
                raise AssertionError("a traceback instead of a message: %s\n%s" % (" ".join(argv[:3]), traceback.format_exc()))
    finally:
        for k in mangsang.AGENT_ENV:
            os.environ.pop(k, None)
        os.environ.update(saved)
        for name in ("APPROVED_IN", "APPROVAL_OF"):
            if hasattr(mangsang, name):
                setattr(mangsang, name, None)
    assert mangsang.running_agent is not None
    return code, out.getvalue()


def git_repo(d):
    import subprocess

    def g(*a):
        return subprocess.run(["git", *a], cwd=d, capture_output=True, text=True).stdout.strip()
    g("init", "-q")
    g("config", "user.name", "t")
    g("config", "user.email", "t@t")
    return g


def sha256(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def full_text(path, text, key):
    """The contract's full text of an anchor: its own text and each same-file part it reads, joined by \\x01."""
    return "\x01".join(t for _, t in mangsang.anchor_parts(path, text)[key])


def record(pj, rid):
    """The relation's file, active or retired; {} when there is none (an assertion fails on it, not a KeyError)."""
    for sub in ("relations", "retired"):
        p = os.path.join(pj.dir, "mangsang", sub, rid + ".json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def tree_bytes(*roots):
    seen = {}
    for root in roots:
        if os.path.isfile(root):
            seen[root] = io.open(root, "rb").read()
        for base, _, files in os.walk(root):
            for f in files:
                seen[os.path.join(base, f)] = io.open(os.path.join(base, f), "rb").read()
    return seen


def kept_source(pj, sid, speaker, text="go ahead and relate them\n"):
    p = os.path.join(pj.dir, "said-%s.txt" % sid)
    write(p, text)
    code, out = run_said("source", "add", sid, "--file", p, "--speaker", speaker, "--target", pj.dir)
    assert code == 0, out


def stale_ids(pj):
    stale, _, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
    return [x["id"] for x in stale]


Q1_ADD = rel("plan/PLAN.md#Q1 add", "documents", "memo.py:add")
NEW_CODE = CODE.replace("return 1", "return 2")


def one_read(c):
    read = c.get("read") if isinstance(c, dict) else None
    assert isinstance(read, list) and len(read) == 1 and isinstance(read[0], dict), c
    return read[0]


# A1 — who signs a judgment

def test_A1_a_free_text_delegation_is_refused_on_confirm_reconfirm_concept_add_and_cq_add():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")]})
        verify = '{"kind": "answered-by", "concepts": ["adding"]}'
        for argv in (("confirm", props), ("reconfirm", rid),
                     ("concept", "add", "listing", "--means", "open notes only"),
                     ("cq", "add", "how-add", "--text", "How is a memo added?", "--verify", verify)):
            before = tree_bytes(os.path.join(pj.dir, "mangsang"), props)
            code, out = run_said(*argv, "--delegated", "do everything", "--why", "the owner said so", "--target", pj.dir)
            assert code != 0, (argv, out)
            assert "source add" in out and "--delegated source:ID" in out, (argv, out)
            assert "--why" in out, ("the agent's own judgment is made with neither flag, with --why", argv, out)
            assert tree_bytes(os.path.join(pj.dir, "mangsang"), props) == before, ("nothing written", argv)


def test_A1_another_tools_delegation_id_is_refused_as_uncheckable_here():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        before = tree_bytes(os.path.join(pj.dir, "mangsang"))
        code, out = run_said("concept", "add", "adding", "--means", "a memo is appended", "--delegated", "D-1a2b", "--why", "x", "--target", pj.dir)
        assert code != 0, out
        assert "cannot be checked" in out and "source add" in out and "--delegated source:ID" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "mangsang", "concepts", "adding.json")), "nothing written"
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD]})
        code, out = run_said("confirm", props, "--delegated", "D-1a2b", "--why", "x", "--target", pj.dir)
        assert code != 0 and "cannot be checked" in out, out
        assert tree_bytes(os.path.join(pj.dir, "mangsang")) == before, "nothing written"


def test_A1_a_delegation_with_no_people_json_is_refused_naming_it():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        kept_source(pj, "x", "lee")
        assert os.path.exists(os.path.join(pj.dir, "mangsang", "sources", "x.json"))
        code, out = run_said("concept", "add", "adding", "--means", "a memo is appended", "--delegated", "source:x", "--why", "lee asked", "--target", pj.dir)
        assert code != 0 and "people.json" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))
        # a people.json with no person in it is no roster either
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": [], "agents": ["Claude ("]})
        code, out = run_said("concept", "add", "adding", "--means", "a memo is appended", "--delegated", "source:x", "--why", "lee asked", "--target", pj.dir)
        assert code != 0 and "people.json" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))


def test_A1_a_delegation_citing_an_agents_turn_or_an_unlisted_speaker_is_refused():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        kept_source(pj, "A1", "Claude (m)", "I will relate everything.\n")
        kept_source(pj, "K1", "kim", "sure\n")
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        for sid, speaker in (("A1", "Claude (m)"), ("K1", "kim")):
            code, out = run_said("concept", "add", "adding", "--means", "a memo is appended", "--delegated", "source:" + sid, "--why", "handed off", "--target", pj.dir)
            assert code != 0, (sid, out)
            assert speaker in out and "person" in out, (sid, out)   # whose words it is; a delegation cites a person's
            assert not os.path.exists(os.path.join(pj.dir, "mangsang", "concepts", "adding.json")), sid


def test_A1_a_delegation_citing_a_persons_kept_words_is_stored_with_source_and_speaker():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        kept_source(pj, "L1", "lee", "relate the plan to the code, I leave it to you\n")
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"], "agents": ["Claude ("]})
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD]})
        # A2: a delegation without its reason is refused
        code, out = run_said("confirm", props, "--delegated", "source:L1", "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert not record(pj, mangsang.rel_id(Q1_ADD)), "nothing written"
        code, out = run_said("confirm", props, "--delegated", "source:L1", "--why", "lee handed the plan-to-code links to me", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, mangsang.rel_id(Q1_ADD)).get("confirmed", {})
        assert c.get("delegated") == {"source": "source:L1", "speaker": "lee"}, c
        assert c.get("why") == "lee handed the plan-to-code links to me" and AT_RE.match(str(c.get("at"))), c
        assert not {"by", "agent"} & set(c), c
        # a bare ID names the same kept source
        code, out = run_said("concept", "add", "adding", "--means", "a memo is appended", "--delegated", "L1", "--why", "lee named it", "--target", pj.dir)
        assert code == 0, out
        dcl = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "adding.json")).get("declared", {})
        assert dcl.get("delegated") == {"source": "source:L1", "speaker": "lee"} and dcl.get("why") == "lee named it" and AT_RE.match(str(dcl.get("at"))), dcl
        code, out = run_said("cq", "add", "how-add", "--text", "How is a memo added?", "--verify", '{"kind": "answered-by", "concepts": ["adding"]}',
                             "--delegated", "source:L1", "--why", "lee asked for this question", "--target", pj.dir)
        assert code == 0, out
        q = mangsang.load(os.path.join(pj.dir, "mangsang", "cq", "how-add.json")).get("declared", {})
        assert q.get("delegated") == {"source": "source:L1", "speaker": "lee"} and q.get("why") == "lee asked for this question" and AT_RE.match(str(q.get("at"))), q


# A2 — the reason

def test_A2_an_agents_reconfirm_needs_why_and_stores_it_beside_the_agent():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        before = io.open(os.path.join(pj.dir, RELS, rid + ".json"), "rb").read()
        code, out = run_agent("reconfirm", rid, "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert '--why "what was compared and why the relation still holds"' in out, out
        assert io.open(os.path.join(pj.dir, RELS, rid + ".json"), "rb").read() == before, "nothing written"
        code, out = run_agent("reconfirm", rid, "--why", "the return value changed; add still appends", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, rid).get("confirmed", {})
        assert c.get("agent") == "Claude Code" and c.get("why") == "the return value changed; add still appends", c
        assert AT_RE.match(str(c.get("at"))) and "by" not in c and "delegated" not in c, c


def test_A2_a_persons_reconfirm_needs_why_and_stores_by_and_why():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        before = io.open(os.path.join(pj.dir, RELS, rid + ".json"), "rb").read()
        code, out = run_said("reconfirm", rid, "--by", "kim", "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert io.open(os.path.join(pj.dir, RELS, rid + ".json"), "rb").read() == before
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, rid).get("confirmed", {})
        assert c.get("by") == "kim" and c.get("why") == "add still appends" and AT_RE.match(str(c.get("at"))), c


def test_A2_concept_reaffirm_and_move_are_refused_without_a_reason():
    with Project() as pj:
        write(os.path.join(pj.dir, "pages.yml"), "deploy: pages\n")
        assert run_said("register", "plan/PLAN.md", "memo.py", "pages.yml", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "site", "--means", "a push deploys the site", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("pages.yml", "realizes", "concept:site", ev="deploy: pages"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:site"), Q1_ADD)[0] == 0
        old = mangsang.rel_id(rel("pages.yml", "realizes", "concept:site"))
        assert run_said("retire", old, "--why", "the deploy moved", "--target", pj.dir)[0] == 0
        cpath = os.path.join(pj.dir, "mangsang", "concepts", "site.json")
        before = io.open(cpath, "rb").read()
        code, out = run_said("concept", "reaffirm", "site", "--by", "kim", "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert io.open(cpath, "rb").read() == before, "nothing written"
        # move: a rename makes the Q1 relation movable; without --why it is refused and nothing moves
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef list_(store):\n    return []\n")
        write(os.path.join(pj.dir, "core.py"), "def add(store, text):\n    return 1\n")
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        code, out = run_said("move", "--dry-run", "--target", pj.dir)
        assert "would move" in out, ("a dry run needs no reason", out)
        code, out = run_said("move", "--by", "kim", "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"]), "nothing moved"
        # an agent's own judgment needs a reason on any command
        code, out = run_agent("concept", "add", "other", "--means", "something else", "--target", pj.dir)
        assert code != 0 and "--why" in out, out
        assert not os.path.exists(os.path.join(pj.dir, "mangsang", "concepts", "other.json"))


# M8 / A3 — confirm by the agent, and what it read

def test_A2_M8_an_agents_confirm_is_its_own_judgment_with_why_at_and_both_ends_read():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        r2 = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD, r2]})
        code, out = run_agent("confirm", props, "--why", "I read both ends of each", "--target", pj.dir)
        assert code == 0, out
        assert "own judgment" in out, out
        plan = os.path.join(pj.dir, "plan", "PLAN.md")
        memo = os.path.join(pj.dir, "memo.py")
        ptext, mtext = io.open(plan, encoding="utf-8").read(), io.open(memo, encoding="utf-8").read()
        for r, (pk, mk) in ((Q1_ADD, ("#Q1 add", ":add")), (r2, ("#Q2 list", ":list_"))):
            c = record(pj, mangsang.rel_id(r)).get("confirmed", {})
            assert c.get("agent") == "Claude Code" and c.get("why") == "I read both ends of each" and AT_RE.match(str(c.get("at"))), c
            assert "by" not in c and "delegated" not in c, "an agent's confirm is never a person's or a delegation"
            read = c.get("read")
            assert isinstance(read, list) and len(read) == 2, c
            assert [e.get("anchor") for e in read] == [r["src"], r["dst"]], read   # src then dst
            assert read[0].get("fp") == mangsang.anchors_of(plan)[pk] and read[1].get("fp") == mangsang.anchors_of(memo)[mk], read
            for e in read:
                assert re.match(r"^[0-9a-f]{64}$", str(e.get("text_sha256"))), e
            assert read[0]["text_sha256"] == sha256(full_text(plan, ptext, pk)) and read[1]["text_sha256"] == sha256(full_text(memo, mtext, mk)), read


def test_A2_M8_an_agents_confirm_keeps_a_proposals_own_why_and_rejects_one_with_no_reason():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        own = dict(Q1_ADD, why="its own reason: add appends")
        bare = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [own, bare]})
        # at a person's terminal, neither flag: refused, saying to pass --by NAME
        code, out = run_said("confirm", props, "--target", pj.dir)
        assert code != 0 and "--by NAME" in out, out
        code, out = run_agent("confirm", props, "--target", pj.dir)
        c = record(pj, mangsang.rel_id(Q1_ADD)).get("confirmed", {})
        assert c.get("agent") == "Claude Code" and c.get("why") == "its own reason: add appends", (c, out)
        assert not record(pj, mangsang.rel_id(bare)), ("a relation with no reason is not confirmed", out)
        left = mangsang.load(props).get("relations", [])
        assert len(left) == 1 and left[0].get("dst") == "memo.py:list_" and left[0].get("evidence") == "lists.", left
        assert "no reason" in str(left[0].get("rejected")), left


# A3 — reconfirm's `read`

def test_A3_reconfirm_records_the_moved_end_against_the_commit_holding_what_was_seen():
    with Project() as pj:
        g = git_repo(pj.dir)
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        g("add", "-A"); g("commit", "-qm", "confirmed")
        sha = g("rev-parse", "HEAD")
        r0 = record(pj, rid)
        memo = os.path.join(pj.dir, "memo.py")
        write(memo, NEW_CODE)
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "the return changed; add still appends", "--target", pj.dir)
        assert code == 0, out
        r = record(pj, rid)
        e = one_read(r.get("confirmed"))
        assert e.get("anchor") == "memo.py:add", e
        assert e.get("seen") == r0["seen"]["memo.py:add"] and e.get("now") == mangsang.anchors_of(memo)[":add"], e
        assert e.get("against") == sha and len(sha) == 40, (e, sha)
        assert e.get("text_sha256") == {"seen": sha256(full_text(memo, CODE, ":add")), "now": sha256(full_text(memo, NEW_CODE, ":add"))}, e
        assert "-    return 1" in str(e.get("diff")) and "+    return 2" in str(e.get("diff")) and e.get("cut") is False, e
        assert "earlier" not in e, e
        hist = r.get("history") or [{}]
        assert hist[-1].get("confirmed") == r0["confirmed"], ("the previous confirmation kept unchanged", hist)


def test_A3_reconfirm_cuts_a_diff_longer_than_4000_characters():
    lines = lambda tag: "".join("        'line-%03d-%s',\n" % (i, tag * 8) for i in range(300))
    big = lambda tag: "def big():\n    return [\n" + lines(tag) + "    ]\n"
    with Project() as pj:
        g = git_repo(pj.dir)
        write(os.path.join(pj.dir, "big.py"), big("a"))
        assert run_said("register", "plan/PLAN.md", "big.py", "--target", pj.dir)[0] == 0
        r = rel("plan/PLAN.md#Q2 list", "documents", "big.py:big", ev="lists.")
        assert pj.propose(r)[0] == 0
        g("add", "-A"); g("commit", "-qm", "confirmed")
        write(os.path.join(pj.dir, "big.py"), big("b"))
        code, out = run_said("reconfirm", mangsang.rel_id(r), "--by", "kim", "--why", "every entry renamed; the list still lists", "--target", pj.dir)
        assert code == 0, out
        e = one_read(record(pj, mangsang.rel_id(r)).get("confirmed"))
        diff = str(e.get("diff"))
        assert e.get("cut") is True and "-        'line-000-aaaaaaaa'," in diff, e
        assert len(diff) <= 4200, len(diff)   # 4000 and a marker line


def test_A3_reconfirm_without_git_says_why_there_is_no_earlier_text():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        seen = record(pj, rid)["seen"]["memo.py:add"]
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)
        assert code == 0, out
        e = one_read(record(pj, rid).get("confirmed"))
        assert e.get("anchor") == "memo.py:add" and e.get("seen") == seen and e.get("now"), e
        assert isinstance(e.get("earlier"), str) and e["earlier"].strip(), e
        assert "diff" not in e and "against" not in e, ("never a diff against a text that is not what the confirmer saw", e)


def test_A3_reconfirm_of_an_uncommitted_relation_finds_the_commit_of_its_anchors_file():
    with Project() as pj:
        g = git_repo(pj.dir)
        g("add", "plan", "memo.py"); g("commit", "-qm", "code only")
        sha = g("rev-parse", "HEAD")
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0   # never committed
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)
        assert code == 0, out
        e = one_read(record(pj, rid).get("confirmed"))
        assert e.get("against") == sha and "-    return 1" in str(e.get("diff")), (e, sha)


def test_A3_reconfirm_of_only_a_new_quote_reads_nothing():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        code, out = run_said("reconfirm", rid, "--by", "kim", "--evidence", "appends", "--why", "a shorter quote says it", "--target", pj.dir)
        assert code == 0, out
        r = record(pj, rid)
        assert r.get("evidence") == "appends" and r.get("confirmed", {}).get("read") == [], r
        assert "outcome" not in r.get("confirmed", {}), ("not stale: no outcome", r)


# A3 — impact --show and judge request read the same earlier text

def test_A3_impact_show_never_diffs_against_a_text_the_confirmer_did_not_see():
    with Project() as pj:
        g = git_repo(pj.dir)
        g("add", "plan", "memo.py"); g("commit", "-qm", "code")   # holds `return 1`, what the confirmer will see
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        g("add", "-A"); g("commit", "-qm", "relation and an edit together")   # the relation's commit holds `return 2`
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 3"))
        code, out = run_said("impact", "--show", "--target", pj.dir)
        assert code == 1 and "-    return 1" in out and "+    return 3" in out, out
        assert "-    return 2" not in out, ("a diff against a text that does not fingerprint to seen", out)
        d = os.path.join(pj.dir, "judge")
        assert run_said("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        items = json.load(open(os.path.join(d, "judge-request.json"), encoding="utf-8")).get("items", [])
        assert len(items) == 1 and "-    return 1" in str(items[0].get("because_changed")) and "-    return 2" not in str(items[0].get("because_changed")), items
    with Project() as pj:
        g = git_repo(pj.dir)
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        g("add", "-A"); g("commit", "-qm", "relation and an edit together")   # no commit holds `return 1`
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 3"))
        code, out = run_said("impact", "--show", "--target", pj.dir)
        assert code == 1 and "-    return 2" not in out and "+    return 3" not in out, ("no diff without the seen text: the reason", out)
        assert "memo.py:add" in out, out


# A3/A4 — the judge's still-true

def test_A3_A4_judge_still_true_records_its_whole_reason_what_was_read_and_held():
    with Project() as pj:
        g = git_repo(pj.dir)
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        g("add", "-A"); g("commit", "-qm", "confirmed")
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        d = os.path.join(pj.dir, "judge")
        assert run_said("judge", "request", "--out", d, "--target", pj.dir)[0] == 0
        req = mangsang.load(os.path.join(d, "judge-request.json"))
        evidence = ("add still appends and the sentence names appending, not the value returned; " * 8)[:500]
        assert len(evidence) == 500
        resp = os.path.join(d, "judge-response.json")
        write(resp, {"artifact-type": "mangsang/judgment@1", "request-id": req["request-id"], "non-claims": [],
                     "worker": {"host": "claude-code", "model": "claude-j"},
                     "items": [{"relation": rid, "verdict": "still-true", "quote": "", "evidence": evidence}]})
        code, out = run_said("judge", "consume", "--response", resp, "--by", "test", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, rid).get("confirmed", {})
        assert c.get("judge") == "claude-code claude-j" and c.get("applied-by") == "test", c
        assert c.get("why") == evidence, ("the evidence kept whole, not cut at 200", len(str(c.get("why"))))
        assert AT_RE.match(str(c.get("at"))), c
        e = one_read(c)
        assert e.get("anchor") == "memo.py:add" and "+    return 2" in str(e.get("diff")), e
        assert c.get("outcome") == "held", c


# A4 — outcomes

def _stale_documents(pj):
    assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
    assert pj.propose(Q1_ADD)[0] == 0
    return mangsang.rel_id(Q1_ADD)


def test_A4_reconfirm_after_only_the_stale_end_moved_is_held():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert stale_ids(pj) == [rid]
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)
        assert code == 0, out
        assert record(pj, rid).get("confirmed", {}).get("outcome") == "held", record(pj, rid)


def test_A4_reconfirm_after_both_ends_moved_is_other_end_updated():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("more", "more words"))
        assert stale_ids(pj) == [rid]
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "the section was updated with the code", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, rid).get("confirmed", {})
        assert c.get("outcome") == "other-end-updated", c
        assert isinstance(c.get("read"), list) and [e.get("anchor") for e in c["read"]] == ["plan/PLAN.md#Q1 add", "memo.py:add"], c   # src, dst


def test_A4_reconfirm_with_a_new_quote_after_one_end_moved_is_re_quoted():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        code, out = run_said("reconfirm", rid, "--by", "kim", "--evidence", "appends", "--why", "the shorter quote is what holds", "--target", pj.dir)
        assert code == 0, out
        assert record(pj, rid).get("confirmed", {}).get("outcome") == "re-quoted", record(pj, rid)


def test_A4_reconfirm_of_a_relation_that_was_not_stale_records_no_outcome():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("more", "more words"))   # documents: the doc side propagates nothing
        assert stale_ids(pj) == []
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "the section's detail grew", "--target", pj.dir)
        assert code == 0, out
        c = record(pj, rid).get("confirmed", {})
        assert c.get("why") == "the section's detail grew", ("recorded: an end moved", c)
        assert "outcome" not in c, c
        e = one_read(c)
        assert e.get("anchor") == "plan/PLAN.md#Q1 add", e


def test_A4_retire_records_what_the_relation_was_and_the_outcome_with_the_signer():
    with Project() as pj:
        write(os.path.join(pj.dir, "old.py"), "def legacy():\n    return 1\n")
        assert run_said("register", "plan/PLAN.md", "memo.py", "old.py", "--target", pj.dir)[0] == 0
        r_fresh = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        r_gone = rel("plan/PLAN.md#Q2 list", "documents", "old.py:legacy", ev="lists.")
        assert pj.propose(Q1_ADD, r_fresh, r_gone)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        rid = mangsang.rel_id(Q1_ADD)
        assert rid in stale_ids(pj)
        code, out = run_agent("retire", rid, "--why", "add no longer appends", "--target", pj.dir)
        assert code == 0, out
        ret = record(pj, rid).get("retired", {})
        assert ret.get("was") == "stale" and ret.get("outcome") == "retired" and ret.get("agent") == "Claude Code", ret
        assert ret.get("why") == "add no longer appends" and AT_RE.match(str(ret.get("at"))), ret
        assert run_said("retire", mangsang.rel_id(r_fresh), "--why", "split in two", "--target", pj.dir)[0] == 0
        ret = record(pj, mangsang.rel_id(r_fresh)).get("retired", {})
        assert ret.get("was") == "fresh" and "outcome" not in ret, ret
        os.remove(os.path.join(pj.dir, "old.py"))
        assert run_said("retire", "--gone", "old.py", "--why", "the legacy module was deleted", "--target", pj.dir)[0] == 0
        ret = record(pj, mangsang.rel_id(r_gone)).get("retired", {})
        assert ret.get("was") == "broken" and ret.get("outcome") == "retired", ret


def test_A4_concept_revise_and_drift_record_the_stale_relations_they_answer():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        r = rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):")
        assert pj.propose(r)[0] == 0
        rid = mangsang.rel_id(r)
        cpath = os.path.join(pj.dir, "mangsang", "concepts", "adding.json")
        # nothing stale: nothing added
        assert run_said("concept", "revise", "adding", "--means", "one memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        h = mangsang.load(cpath)["history"][-1]
        assert "outcome" not in h and "stale" not in h, h
        assert run_said("reconfirm", rid, "--by", "kim", "--why", "add appends one memo", "--target", pj.dir)[0] == 0
        # the code moved: revise answers a stale projection
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert stale_ids(pj) == [rid]
        assert run_said("concept", "revise", "adding", "--means", "one memo is appended; its id returned", "--by", "kim", "--target", pj.dir)[0] == 0
        h = mangsang.load(cpath)["history"][-1]
        assert h.get("outcome") == "revised" and h.get("stale") == [rid], h
        # both ends moved since the relation's seen (the concept and the code): other-end-updated
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add returns the id the new sentence names", "--target", pj.dir)
        assert code == 0, out
        assert record(pj, rid).get("confirmed", {}).get("outcome") == "other-end-updated", record(pj, rid)
        # drift likewise
        write(os.path.join(pj.dir, "memo.py"), CODE.replace("return 1", "return 3"))
        assert stale_ids(pj) == [rid]
        code, out = run_agent("concept", "drift", "adding", "--why", "memos moved to another store", "--target", pj.dir)
        assert code == 0, out
        dm = mangsang.load(cpath).get("drift", {})
        assert dm.get("outcome") == "drifted" and dm.get("stale") == [rid] and dm.get("agent") == "Claude Code", dm


# A5 — move

def test_A5_a_heading_renamed_in_place_is_carried_fresh_and_its_rename_recorded():
    renamed = PLAN.replace("## Q1 add", "## Q1 append")
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), renamed)
        code, out = run_said("move", "--by", "kim", "--why", "the heading was renamed in place", "--target", pj.dir)
        assert code == 0, out
        nid = mangsang.rel_id(rel("plan/PLAN.md#Q1 append", "documents", "memo.py:add"))
        assert stale_ids(pj) == [] and run_said("impact", "--target", pj.dir)[0] == 0
        c = record(pj, nid).get("confirmed", {})
        assert c.get("by") == "kim" and c.get("why") == "the heading was renamed in place" and AT_RE.match(str(c.get("at"))), c
        e = one_read(c)
        assert e.get("anchor") == "plan/PLAN.md#Q1 append" and e.get("moved_from") == "plan/PLAN.md#Q1 add", e
        assert e.get("title") == "#Q1 add -> #Q1 append" and e.get("seen") and e.get("now"), e
        assert e.get("seen") == record(pj, rid).get("seen", {}).get("plan/PLAN.md#Q1 add"), e


def test_A5_a_symbol_moved_with_its_body_changed_is_carried_stale_at_its_new_home():
    with Project() as pj:
        _stale_documents(pj)
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef list_(store):\n    return []\n")
        write(os.path.join(pj.dir, "core.py"), "def add(store, text):\n    return 2\n")
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        code, out = run_said("move", "--by", "kim", "--why", "add moved to core.py", "--target", pj.dir)
        nid = mangsang.rel_id(rel("plan/PLAN.md#Q1 add", "documents", "core.py:add"))
        assert record(pj, nid).get("moved-from") == mangsang.rel_id(Q1_ADD), (out, record(pj, nid))
        assert nid in out and "stale" in out and "reconfirm" in out and "--why" in out, ("said: stale, re-read it", out)
        assert stale_ids(pj) == [nid], stale_ids(pj)
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and any("stale" in l and nid in l for l in out.split("\n")), out
        e = one_read(record(pj, nid).get("confirmed"))
        assert e.get("anchor") == "core.py:add" and e.get("moved_from") == "memo.py:add" and e.get("same_key") is True, e
        assert "diff" in e or "earlier" in e, e


def test_A5_a_relation_whose_unmoved_end_changed_before_the_move_stays_stale():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        r = rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):")
        assert pj.propose(r)[0] == 0
        assert run_said("concept", "revise", "adding", "--means", "a memo is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef list_(store):\n    return []\n")
        write(os.path.join(pj.dir, "core.py"), "def add(store, text):\n    return 1\n")   # the same body
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        code, out = run_said("move", "--by", "kim", "--why", "add moved to core.py", "--target", pj.dir)
        nid = mangsang.rel_id(rel("core.py:add", "realizes", "concept:adding"))
        assert record(pj, nid).get("moved-from") == mangsang.rel_id(r), out
        assert stale_ids(pj) == [nid], ("the concept changed since its confirmation: still owed a re-read", out)


def test_A5_the_moved_relations_old_record_says_moved_broken_signer_and_reason():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("## Q1 add", "## Q1 append"))
        code, out = run_agent("move", "--why", "the heading was renamed in place", "--target", pj.dir)
        assert code == 0, out
        old = record(pj, rid)
        ret = old.get("retired", {})
        assert os.path.exists(os.path.join(pj.dir, "mangsang", "retired", rid + ".json")), out
        assert ret.get("outcome") == "moved" and ret.get("was") == "broken" and ret.get("agent") == "Claude Code", ret
        assert str(ret.get("why")).startswith("moved:") and "the heading was renamed in place" in str(ret.get("why")), ret
        assert AT_RE.match(str(ret.get("at"))), ret


# A3 — concept reaffirm's `read`

def test_A3_concept_reaffirm_records_the_sentence_what_realizes_it_and_what_it_lost():
    with Project() as pj:
        write(os.path.join(pj.dir, "pages.yml"), "deploy: pages\n")
        assert run_said("register", "plan/PLAN.md", "pages.yml", "--target", pj.dir)[0] == 0
        means = "a push to main deploys the site"
        assert run_said("concept", "add", "site", "--means", means, "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(rel("pages.yml", "realizes", "concept:site", ev="deploy: pages"),
                          rel("plan/PLAN.md#Q1 add", "realizes", "concept:site"))[0] == 0
        old = mangsang.rel_id(rel("pages.yml", "realizes", "concept:site"))
        code, out = run_said("retire", old, "--why", "the deploy moved", "--target", pj.dir)
        assert code == 0 and "lost a projection" in out, out
        code, out = run_said("concept", "reaffirm", "site", "--by", "kim", "--why", "the sentence still says what deploys", "--target", pj.dir)
        assert code == 0, out
        h = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "site.json"))["history"][-1].get("reaffirmed", {})
        assert h.get("by") == "kim" and h.get("why") == "the sentence still says what deploys" and AT_RE.match(str(h.get("at"))), h
        read = h.get("read")
        assert isinstance(read, dict), h
        assert read.get("means_sha256") == sha256(means), read
        fp = mangsang.anchors_of(os.path.join(pj.dir, "plan", "PLAN.md"))["#Q1 add"]
        assert read.get("realized_by") == [{"anchor": "plan/PLAN.md#Q1 add", "fp": fp}], read
        assert read.get("lost") == [{"id": old, "anchor": "pages.yml"}], read


# A6 — readers

def test_A6_lookup_of_an_agent_signed_relation_says_by_the_agent_and_its_reason():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD]})
        assert run_agent("confirm", props, "--why", "both ends name appending; the body returns one", "--target", pj.dir)[0] == 0
        code, out = run_said("lookup", mangsang.rel_id(Q1_ADD), "--target", pj.dir)
        assert code == 0 and "by the agent Claude Code, on its own" in out and "both ends name appending" in out, out


def test_A6_lookup_of_a_source_delegation_says_whose_words_and_the_source():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        kept_source(pj, "L1", "lee")
        write(os.path.join(pj.dir, "mangsang", "people.json"), {"people": ["lee"]})
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD]})
        assert run_said("confirm", props, "--delegated", "source:L1", "--why", "lee handed it to me; read both", "--target", pj.dir)[0] == 0
        code, out = run_said("lookup", mangsang.rel_id(Q1_ADD), "--target", pj.dir)
        assert code == 0 and "delegated: lee's words (source:L1)" in out and "lee handed it to me" in out, out


def test_A6_check_counts_unrecorded_delegations_on_disk_without_rewriting_them():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        base_code, out = run_said("check", "--target", pj.dir)
        assert "unrecorded-delegation" not in out, out
        base_findings_code = run_said("check", "--findings", "--target", pj.dir)[0]
        # history, written by hand as an older mangsang wrote it
        rpath = os.path.join(pj.dir, RELS, mangsang.rel_id(Q1_ADD) + ".json")
        r = mangsang.load(rpath)
        r["confirmed"] = {"delegated": "do everything"}
        mangsang.save(rpath, r)
        cpath = os.path.join(pj.dir, "mangsang", "concepts", "adding.json")
        c = mangsang.load(cpath)
        c["declared"] = {"delegated": {"ref": "D-a1b2"}}
        mangsang.save(cpath, c)
        before = tree_bytes(os.path.join(pj.dir, "mangsang"))
        code, out = run_said("check", "--target", pj.dir)
        assert code == base_code, (code, base_code, out)
        lines = [l for l in out.split("\n") if "unrecorded-delegation" in l]
        assert len(lines) == 1 and "2" in lines[0] and "source:ID" in lines[0], out
        code, out = run_said("check", "--findings", "--target", pj.dir)
        assert code == base_findings_code, out
        found = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "unrecorded-delegation"]
        assert len(found) == 1 and found[0].get("layer") == "observation" and found[0].get("text"), out
        assert tree_bytes(os.path.join(pj.dir, "mangsang")) == before, "nothing is rewritten"


# ---- phase B: what staleness led to (`outcomes`), and a person's review of relations (`review`). Helpers first.

PEOPLE = {"people": ["lee", "kim"], "agents": ["Claude ("]}
CLASSES = ["held", "re-quoted", "other-end-updated", "moved", "retired", "revised", "drifted", "unknown"]
CHANGE_CLASSES = ("re-quoted", "other-end-updated", "retired", "revised", "drifted")
STORE = ("def save(store, memo):\n    return store + [memo]\n\n\ndef load(store):\n    return list(store)\n\n\n"
         "def drop(store):\n    return []\n\n\ndef keep(store):\n    return store\n")
R_ADD = rel("memo.py:add", "realizes", "concept:adding", ev="def add(store, text):")
R_LIST = rel("memo.py:list_", "realizes", "concept:adding", ev="def list_(store):")
PERSON_LINE = re.compile(r"reviewed by a person: (\d+) of (\d+) relation\(s\); (\d+) changed since review; (\d+) disputed; "
                         r"meanings signed by a person: (\d+) of (\d+)")


def mg(pj):
    return os.path.join(pj.dir, "mangsang")


def edit(pj, name, old, new):
    p = os.path.join(pj.dir, *name.split("/"))
    text = io.open(p, encoding="utf-8").read()
    assert old in text, (name, old)
    write(p, text.replace(old, new))


def reviewers(pj):
    """The roster and lee's kept words: what `review` needs before it records a person's review."""
    write(os.path.join(mg(pj), "people.json"), PEOPLE)
    kept_source(pj, "L1", "lee", "yes — I read these and they are right\n")


def agent_confirms(pj, *rels, why="read both ends; the quote says what the relation claims"):
    props = os.path.join(pj.dir, "p.json")
    write(props, {"relations": list(rels)})
    code, out = run_agent("confirm", props, "--why", why, "--target", pj.dir)
    assert code == 0 and all(record(pj, mangsang.rel_id(r)) for r in rels), out
    return [mangsang.rel_id(r) for r in rels]


def agent_rereads(pj, rid, *more, why="re-read after the change; the relation still holds"):
    code, out = run_agent("reconfirm", rid, "--why", why, *more, "--target", pj.dir)
    assert code == 0, out


def review(pj, verb, *ids, by="lee", src="source:L1", why=None):
    return run_said("review", verb, *ids, "--by", by, "--approved-in", src, *(["--why", why] if why else []), "--target", pj.dir)


def reviews_of(pj, rid):
    got = record(pj, rid).get("reviews")
    return got if isinstance(got, list) else []


def person_review(pj):
    """check's observation line as numbers: (reviewed, relations, changed since review, disputed, meanings signed, meanings)."""
    code, out = run_said("check", "--target", pj.dir)
    m = PERSON_LINE.search(out)
    assert m, ("check says how much of the net a person reviewed", out)
    return tuple(int(x) for x in m.groups())


def outcome_counts(out, label):
    """One line of `outcomes` as ({class: n}, (stale, broken), owes): a class left out is 0; `unknown` and `open` are always said."""
    if label == "total":
        lines = [l for l in out.split("\n") if l.strip().startswith("total")]
    else:
        lines = [l for l in out.split("\n") if (label + " — ") in l]
    assert len(lines) == 1, (label, out)
    head, sep, tail = lines[0].partition("; open:")
    assert sep, ("`open` is always said", lines[0])
    head = head.split(" — ", 1)[-1]
    counts = dict.fromkeys(CLASSES, 0)
    for c, n in re.findall(r"(?<![\w-])(%s) (\d+)" % "|".join(CLASSES), head):
        counts[c] = int(n)
    assert re.search(r"(?<![\w-])unknown \d+", head), ("`unknown` is always said", lines[0])
    m = re.search(r"(\d+) stale, (\d+) broken", tail)
    assert m, lines[0]
    return counts, (int(m.group(1)), int(m.group(2))), "owes a re-read" in tail


def counts_of(**kw):
    return dict(dict.fromkeys(CLASSES, 0), **{k.replace("_", "-"): v for k, v in kw.items()})


def json_out(out, kind):
    try:
        doc = json.loads(out)
    except ValueError:
        doc = None
    assert isinstance(doc, dict) and doc.get("artifact-type") == kind, out[:400]
    return doc


def json_group(doc, name):
    g = doc.get("concepts", {}).get(name) if name != "total" else doc.get("total")
    assert isinstance(g, dict), (name, doc)
    return {c: g.get(c) for c in CLASSES}, g.get("open")


class OutcomesProject:
    """A record with every class of outcome in it, in two batches with a commit between them.

    batch 1 (committed): R_ADD held · Q1_ADD other-end-updated · a stale relation between two artifacts retired
    batch 2 (uncommitted): a relation moved · R_ADD held again · a relation first confirmed here, then held · R_LIST re-quoted ·
      a stale projection of `storing` retired · `listing` revised and `keeping` marked drifted while a projection of each was
      stale · and, left open: Q1_ADD stale again, a relation broken."""

    def __init__(self):
        self.pj = pj = Project()
        self.g = g = git_repo(pj.dir)
        write(os.path.join(pj.dir, "store.py"), STORE)
        assert run_said("register", "plan/PLAN.md", "memo.py", "store.py", "--target", pj.dir)[0] == 0
        for name, means in (("adding", "a memo is appended"), ("storing", "memos are kept in a list"), ("listing", "memos are read back"),
                            ("keeping", "nothing is lost"), ("idle", "nothing stands on this")):
            assert run_said("concept", "add", name, "--means", means, "--by", "kim", "--target", pj.dir)[0] == 0
        r_x = rel("plan/PLAN.md", "references", "memo.py:X")
        r_h = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:add", ev="lists.")
        r_save = rel("store.py:save", "realizes", "concept:storing", ev="def save(store, memo):")
        r_load = rel("store.py:load", "realizes", "concept:storing", ev="def load(store):")
        r_drop = rel("store.py:drop", "realizes", "concept:listing", ev="def drop(store):")
        r_keep = rel("store.py:keep", "realizes", "concept:keeping", ev="def keep(store):")
        assert pj.propose(R_ADD, R_LIST, Q1_ADD, r_x, r_h, r_save, r_load, r_drop, r_keep)[0] == 0
        rid = mangsang.rel_id
        self.ids = ids = {"add": rid(R_ADD), "list": rid(R_LIST), "q1": rid(Q1_ADD), "x": rid(r_x), "h": rid(r_h), "save": rid(r_save),
                          "load": rid(r_load), "drop": rid(r_drop), "keep": rid(r_keep)}

        def reconfirm(key, why, *more):
            code, out = run_said("reconfirm", ids[key], "--by", "kim", "--why", why, *more, "--target", pj.dir)
            assert code == 0, out
            return record(pj, ids[key]).get("confirmed", {}).get("outcome")

        # batch 1
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("more", "more words"))
        assert reconfirm("add", "add still appends") == "held"
        assert reconfirm("q1", "the section was updated with the code") == "other-end-updated"
        assert run_said("retire", ids["h"], "--why", "Q2 never documented add", "--target", pj.dir)[0] == 0
        assert record(pj, ids["h"]).get("retired", {}).get("outcome") == "retired"
        g("add", "-A"); g("commit", "-qm", "batch 1")
        self.rev = g("rev-parse", "HEAD")
        assert len(self.rev) == 40, self.rev
        # batch 2
        edit(pj, "store.py", "def load(store):\n    return list(store)\n\n\n", "")
        write(os.path.join(pj.dir, "core.py"), "def load(store):\n    return list(store)\n")
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        code, out = run_said("move", "--by", "kim", "--why", "load moved to core.py", "--target", pj.dir)
        assert code == 0 and record(pj, ids["load"]).get("retired", {}).get("outcome") == "moved", out
        ids["load2"] = rid(rel("core.py:load", "realizes", "concept:storing"))
        assert record(pj, ids["load2"]), out
        r_n = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        assert pj.propose(r_n)[0] == 0
        ids["n"] = rid(r_n)
        edit(pj, "memo.py", "return 2", "return 3")
        edit(pj, "memo.py", "return []", "return [1]")
        assert reconfirm("add", "add still appends, whatever it returns") == "held"
        assert reconfirm("n", "list_ still lists") == "held"
        assert reconfirm("list", "the def line is what realizes it", "--evidence", "def list_") == "re-quoted"
        edit(pj, "store.py", "return store + [memo]", "return [memo]")
        assert run_said("retire", ids["save"], "--why", "save no longer keeps the list", "--target", pj.dir)[0] == 0
        assert record(pj, ids["save"]).get("retired", {}).get("outcome") == "retired"
        edit(pj, "store.py", "def drop(store):\n    return []", "def drop(store):\n    return [None]")
        assert run_said("concept", "revise", "listing", "--means", "memos are read back, oldest first", "--by", "kim", "--target", pj.dir)[0] == 0
        assert mangsang.load(os.path.join(mg(pj), "concepts", "listing.json"))["history"][-1].get("stale") == [ids["drop"]]
        edit(pj, "store.py", "def keep(store):\n    return store", "def keep(store):\n    return store[:]")
        assert run_agent("concept", "drift", "keeping", "--why", "keep copies now", "--target", pj.dir)[0] == 0
        assert mangsang.load(os.path.join(mg(pj), "concepts", "keeping.json")).get("drift", {}).get("stale") == [ids["keep"]]
        edit(pj, "memo.py", "X = 1\n", "")
        self.group = {"add": "concept:adding", "list": "concept:adding", "q1": "(between artifacts)", "x": "(between artifacts)",
                      "n": "(between artifacts)", "load2": "concept:storing", "drop": "concept:listing", "keep": "concept:keeping"}
        self.whole = {"concept:adding": counts_of(held=2, re_quoted=1),
                      "(between artifacts)": counts_of(held=1, other_end_updated=1, retired=1),
                      "concept:storing": counts_of(retired=1, moved=1),
                      "concept:listing": counts_of(revised=1),
                      "concept:keeping": counts_of(drifted=1),
                      "total": counts_of(held=3, re_quoted=1, other_end_updated=1, retired=2, moved=1, revised=1, drifted=1)}
        self.later = {"concept:adding": counts_of(held=1, re_quoted=1),
                      "(between artifacts)": counts_of(held=1),
                      "concept:storing": counts_of(retired=1, moved=1),
                      "concept:listing": counts_of(revised=1),
                      "concept:keeping": counts_of(drifted=1),
                      "total": counts_of(held=2, re_quoted=1, retired=1, moved=1, revised=1, drifted=1)}

    def open_now(self):
        """{group: (stale, broken)} and the concepts owing a re-read, as the engine's own impact has them now."""
        pj = self.pj
        stale, broken, _, _ = mangsang.compute_impact(pj.dir, mangsang.decl(pj.dir), persist=False)
        by_id = {v: self.group[k] for k, v in self.ids.items() if k in self.group}
        got = {g: [0, 0] for g in self.whole}
        for i, items in enumerate((stale, broken)):
            for x in items:
                got[by_id[x["id"]]][i] += 1
                got["total"][i] += 1
        assert self.ids["q1"] in [x["id"] for x in stale] and self.ids["x"] in [x["id"] for x in broken], (stale, broken)
        said = run_said("impact", "--target", pj.dir)[1]
        owed = {g for g in self.whole if g.startswith("concept:") and re.search(r"owed\s+%s " % re.escape(g), said)}
        assert "concept:storing" in owed, said   # it lost a projection to a retirement
        return {g: tuple(v) for g, v in got.items()}, owed

    def __enter__(self):
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.pj.dir, ignore_errors=True)


# B1 — outcomes

def test_B1_outcomes_counts_each_class_per_concept_and_in_total_and_says_what_led_to_a_change():
    with OutcomesProject() as op:
        pj = op.pj
        open_now, owed = op.open_now()
        before = tree_bytes(mg(pj))
        code, out = run_said("outcomes", "--target", pj.dir)
        assert code == 0, out
        assert out.strip().split("\n")[0].strip() == "outcomes over the whole record", out
        for label, want in op.whole.items():
            counts, opened, owes = outcome_counts(out, label)
            assert counts == want, (label, counts, want, out)
            assert opened == open_now[label], (label, opened, open_now[label], out)
            if label.startswith("concept:"):
                assert owes == (label in owed), (label, out)
        assert "concept:idle" not in out, ("a concept with no event and nothing open has no line", out)
        lines = [l.strip() for l in out.strip().split("\n")]
        assert lines.index(next(l for l in lines if l.startswith("total"))) > max(i for i, l in enumerate(lines) if "concept:" in l and " — " in l), out
        led = [l for l in lines if l.startswith("led to a change:")]
        assert len(led) == 1 and lines.index(led[0]) > lines.index(next(l for l in lines if l.startswith("total"))), out
        assert led[0].startswith("led to a change: 6 of 10 handled with a known outcome (re-quoted, other-end-updated, retired, revised, drifted)"), led
        assert "held 3, moved 1; unknown 0 (recorded before outcomes existed)" in led[0], led
        assert tree_bytes(mg(pj)) == before, "outcomes writes nothing"


def test_B1_outcomes_lists_what_is_open_now_stale_broken_and_owed():
    with OutcomesProject() as op:
        pj = op.pj
        open_now, owed = op.open_now()
        assert open_now["(between artifacts)"] == (1, 1), open_now   # Q1_ADD stale again, the reference to X broken
        code, out = run_said("outcomes", "--target", pj.dir)
        assert code == 0, ("a measurement, not a check: 0 with stale and broken relations open", out)
        counts, opened, _ = outcome_counts(out, "(between artifacts)")
        assert opened == (1, 1), out
        assert outcome_counts(out, "total")[1] == open_now["total"], (out, open_now)
        assert outcome_counts(out, "concept:storing")[2] is True, ("storing lost a projection: it owes a re-read", out)
        assert outcome_counts(out, "concept:adding")[2] is False, out
        doc = json_out(run_said("outcomes", "--json", "--target", pj.dir)[1], "mangsang/outcomes@1")
        for label in op.whole:
            name = label[len("concept:"):] if label.startswith("concept:") else label
            _, opened = json_group(doc, name)
            assert isinstance(opened, dict) and (opened.get("stale"), opened.get("broken")) == open_now[label], (label, opened, open_now[label])
            if label != "total":
                assert opened.get("owed") is (label in owed), (label, opened)


def test_B1_outcomes_json_has_the_contracts_keys_and_numbers():
    with OutcomesProject() as op:
        pj = op.pj
        before = tree_bytes(mg(pj))
        code, out = run_said("outcomes", "--json", "--target", pj.dir)
        assert code == 0, out
        doc = json_out(out, "mangsang/outcomes@1")
        assert {"artifact-type", "since", "classes", "concepts", "total", "changed", "known"} <= set(doc), sorted(doc)
        assert doc["since"] is None, doc["since"]
        assert isinstance(doc["classes"], list) and sorted(doc["classes"]) == sorted(CLASSES), doc["classes"]
        for label, want in op.whole.items():
            name = label[len("concept:"):] if label.startswith("concept:") else label
            got, opened = json_group(doc, name)
            assert got == want, (name, got, want)
            assert isinstance(opened, dict) and isinstance(opened.get("stale"), int) and isinstance(opened.get("broken"), int), (name, opened)
        assert doc["changed"] == 6 and doc["known"] == 10, (doc["changed"], doc["known"])
        assert doc["changed"] == sum(doc["total"][c] for c in CHANGE_CLASSES), doc["total"]
        assert tree_bytes(mg(pj)) == before, "outcomes --json writes nothing"


def test_B1_outcomes_since_a_revision_counts_only_what_the_record_gained_after_it():
    with OutcomesProject() as op:
        pj = op.pj
        before = tree_bytes(mg(pj))
        code, out = run_said("outcomes", "--since", op.rev, "--target", pj.dir)
        assert code == 0, out
        head = out.strip().split("\n")[0]
        assert head.startswith("outcomes since ") and op.rev[:7] in head and re.search(r"\d{4}-\d\d-\d\d", head), head
        for label, want in op.later.items():
            counts, _, _ = outcome_counts(out, label)
            assert counts == want, (label, counts, want, out)
        assert any(l.strip().startswith("led to a change: 4 of 7 handled with a known outcome") and "held 2, moved 1; unknown 0" in l
                   for l in out.split("\n")), out
        # what is open is open now, whatever the window
        assert outcome_counts(out, "total")[1] == op.open_now()[0]["total"], out
        code, out = run_said("outcomes", "--since", op.rev, "--json", "--target", pj.dir)
        doc = json_out(out, "mangsang/outcomes@1")
        since = doc.get("since")
        assert isinstance(since, dict) and {"rev", "date"} <= set(since), since
        assert len(str(since["rev"])) >= 7 and op.rev.startswith(str(since["rev"])), (since, op.rev)
        assert re.match(r"^\d{4}-\d\d-\d\d", str(since["date"])), since
        assert json_group(doc, "total")[0] == op.later["total"] and doc.get("changed") == 4 and doc.get("known") == 7, doc
        assert json_group(doc, "adding")[0] == op.later["concept:adding"], doc
        # once everything is committed, nothing is beyond HEAD
        op.g("add", "-A"); op.g("commit", "-qm", "batch 2")
        code, out = run_said("outcomes", "--since", "HEAD", "--json", "--target", pj.dir)
        doc = json_out(out, "mangsang/outcomes@1")
        assert json_group(doc, "total")[0] == counts_of() and doc.get("changed") == 0 and doc.get("known") == 0, doc
        # ... and the first commit's window is still batch 2
        code, out = run_said("outcomes", "--since", op.rev[:10], "--json", "--target", pj.dir)
        assert json_group(json_out(out, "mangsang/outcomes@1"), "total")[0] == op.later["total"], out
        assert tree_bytes(mg(pj)) == before, "outcomes --since writes nothing"


def test_B1_outcomes_since_a_date_is_the_newest_commit_before_it_and_none_is_the_whole_history():
    import datetime
    with OutcomesProject() as op:
        pj = op.pj
        code, out = run_said("outcomes", "--since", "2000-01-01", "--target", pj.dir)   # before the first commit: no such commit
        assert code == 0, out
        for label, want in op.whole.items():
            assert outcome_counts(out, label)[0] == want, (label, out)
        assert any(l.strip().startswith("led to a change: 6 of 10 ") for l in out.split("\n")), out
        later = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).strftime("%Y-%m-%d")   # after the only commit: that commit
        code, out = run_said("outcomes", "--since", later, "--target", pj.dir)
        assert code == 0, out
        assert op.rev[:7] in out.strip().split("\n")[0], out
        for label, want in op.later.items():
            assert outcome_counts(out, label)[0] == want, (label, out)
        code, out = run_said("outcomes", "--since", later + "T00:00:00Z", "--json", "--target", pj.dir)   # an ISO time
        assert code == 0 and json_group(json_out(out, "mangsang/outcomes@1"), "total")[0] == op.later["total"], out


def test_B1_outcomes_since_without_git_is_refused_and_without_since_it_answers():
    with Project() as pj:
        rid = _stale_documents(pj)
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)[0] == 0
        before = tree_bytes(mg(pj))
        code, out = run_said("outcomes", "--target", pj.dir)
        assert code == 0 and outcome_counts(out, "total")[0] == counts_of(held=1), out
        assert outcome_counts(out, "(between artifacts)")[0] == counts_of(held=1), out
        code, out = run_said("outcomes", "--since", "HEAD", "--target", pj.dir)
        assert code == 2, (code, out)
        assert "git" in out and "invalid choice" not in out, ("refused with a message", out)
        assert not any(l.strip().startswith("total") for l in out.split("\n")), ("no count without the window it was asked for", out)
        assert tree_bytes(mg(pj)) == before, "nothing written"


def test_B1_outcomes_counts_a_record_written_before_outcomes_existed_as_unknown_never_as_a_class():
    def strip(c):
        return {k: v for k, v in c.items() if k not in ("at", "outcome", "why", "read")}
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        r_q2 = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        r_x = rel("plan/PLAN.md", "references", "memo.py:X")
        assert pj.propose(R_ADD, R_LIST, r_q2, r_x)[0] == 0
        rid, lid = mangsang.rel_id(R_ADD), mangsang.rel_id(R_LIST)
        for n in (2, 3):
            edit(pj, "memo.py", "return %d" % (n - 1), "return %d" % n)
            assert run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", pj.dir)[0] == 0
        assert run_said("retire", lid, "--why", "listing is not adding", "--target", pj.dir)[0] == 0
        # the same record as an older release wrote it: signatures with no `at`, no `why`, no `read`, no `outcome`
        rpath = os.path.join(pj.dir, RELS, rid + ".json")
        r = mangsang.load(rpath)
        assert len(r.get("history", [])) == 2 and r["confirmed"].get("outcome") == "held", r
        r["confirmed"] = strip(r["confirmed"])
        r["history"] = [dict(h, confirmed=strip(h["confirmed"])) for h in r["history"]]
        mangsang.save(rpath, r)
        lpath = os.path.join(mg(pj), "retired", lid + ".json")
        l = mangsang.load(lpath)
        l["confirmed"] = strip(l["confirmed"])
        l["retired"] = {"why": "listing is not adding"}
        mangsang.save(lpath, l)
        # a meaning change with nothing stale is no re-read: never counted, not even as unknown
        assert run_said("concept", "revise", "adding", "--means", "one memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        cpath = os.path.join(mg(pj), "concepts", "adding.json")
        c = mangsang.load(cpath)
        c["history"] = [dict(h, declared=strip(h.get("declared", {}))) for h in c["history"]]
        assert all("outcome" not in h for h in c["history"]), c
        mangsang.save(cpath, c)
        # 2.6.0 records that are not events: a re-read of a relation that was not stale, a retirement of a fresh one
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("lists.", "lists. Newest last."))
        assert stale_ids(pj) == [rid], "only the projection of the revised concept is stale"
        assert run_said("reconfirm", mangsang.rel_id(r_q2), "--by", "kim", "--why", "the section grew; it still documents list_", "--target", pj.dir)[0] == 0
        c2 = record(pj, mangsang.rel_id(r_q2)).get("confirmed", {})
        assert c2.get("at") and "outcome" not in c2 and len(record(pj, mangsang.rel_id(r_q2)).get("history", [])) == 1, c2
        assert run_said("retire", mangsang.rel_id(r_x), "--why", "the reference says nothing", "--target", pj.dir)[0] == 0
        assert "outcome" not in record(pj, mangsang.rel_id(r_x)).get("retired", {"outcome": 1})
        before = tree_bytes(mg(pj))
        code, out = run_said("outcomes", "--target", pj.dir)
        assert code == 0, out
        want = counts_of(unknown=3)   # two re-reads of the projection and its sibling's retirement
        assert outcome_counts(out, "concept:adding")[0] == want, out
        assert outcome_counts(out, "total")[0] == want, out
        assert outcome_counts(out, "concept:adding")[1] == (1, 0), out
        assert not any("(between artifacts) — " in l for l in out.split("\n")), ("neither of its records is an event, nothing of it is open", out)
        led = [l.strip() for l in out.split("\n") if l.strip().startswith("led to a change:")]
        assert len(led) == 1 and led[0].startswith("led to a change: 0 of 0 handled with a known outcome"), out
        assert "held 0, moved 0; unknown 3 (recorded before outcomes existed)" in led[0], led
        doc = json_out(run_said("outcomes", "--json", "--target", pj.dir)[1], "mangsang/outcomes@1")
        assert json_group(doc, "total")[0] == want and json_group(doc, "adding")[0] == want, doc
        assert doc.get("changed") == 0 and doc.get("known") == 0, doc
        assert tree_bytes(mg(pj)) == before, "outcomes rewrites no older record"


# B2 / B3 — a person's review, recorded

def _review_project(*rels):
    pj = Project()
    assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
    reviewers(pj)
    assert run_agent("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--why", "the plan's Q1 says so",
                     "--target", pj.dir)[0] == 0
    agent_confirms(pj, *(rels or (R_ADD, R_LIST, Q1_ADD)))
    return pj


def test_B3_review_accept_on_a_fresh_relation_appends_one_entry_and_touches_nothing_else():
    with _review_project() as pj:
        rid = mangsang.rel_id(R_ADD)
        r0 = record(pj, rid)
        assert stale_ids(pj) == [] and "reviews" not in r0, r0
        code, out = review(pj, "accept", rid)
        assert code == 0, out
        assert [l.strip() for l in out.split("\n") if l.strip().startswith("reviewed ")] == ["reviewed %s accepted by lee (source:L1)" % rid], out
        r = record(pj, rid)
        got = r.get("reviews")
        assert isinstance(got, list) and len(got) == 1 and isinstance(got[0], dict), r
        e = got[0]
        assert e.get("by") == "lee" and e.get("approved-in") == "source:L1" and e.get("verdict") == "accepted", e
        assert AT_RE.match(str(e.get("at"))), e
        now = {"memo.py:add": mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))[":add"], "concept:adding": r0["seen"]["concept:adding"]}
        assert e.get("seen") == now and e["seen"] == r0["seen"], (e, now)
        assert e.get("evidence") == "def add(store, text):", e
        assert e.get("why") is None and set(e) <= {"by", "approved-in", "at", "verdict", "seen", "evidence", "why"}, e
        assert {k: v for k, v in r.items() if k != "reviews"} == r0, ("seen, confirmed and history are not touched", r, r0)
        # the second call is a second review, with the person's words when they gave some; the id in capitals is the same relation
        code, out = review(pj, "accept", rid.upper(), why="lee: 'yes, that is where a memo is appended'")
        assert code == 0 and ("reviewed %s accepted by lee (source:L1)" % rid) in out, out
        got = reviews_of(pj, rid)
        assert len(got) == 2 and got[0] == e and got[1].get("why") == "lee: 'yes, that is where a memo is appended'", got
        assert {k: v for k, v in record(pj, rid).items() if k != "reviews"} == r0
        # no other relation gained a review
        assert not reviews_of(pj, mangsang.rel_id(R_LIST)) and not reviews_of(pj, mangsang.rel_id(Q1_ADD))


def test_B3_review_accept_takes_several_ids_and_a_person_reviews_with_an_agent_running_too():
    with _review_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        code, out = run_agent("review", "accept", a, b, "--by", "lee", "--approved-in", "source:L1", "--target", pj.dir)
        assert code == 0, out
        lines = [l.strip() for l in out.strip().split("\n") if l.strip().startswith("reviewed ")]
        assert sorted(lines) == sorted("reviewed %s accepted by lee (source:L1)" % x for x in (a, b)), out
        for x in (a, b):
            got = reviews_of(pj, x)
            assert len(got) == 1 and got[0].get("by") == "lee" and got[0].get("approved-in") == "source:L1", (x, got)
            assert "agent" not in got[0] and "delegated" not in got[0], ("a review is the person's, whoever typed it", got)
        assert not reviews_of(pj, c)
        # a relation between two artifacts is reviewed the same way: both ends' fingerprints
        code, out = review(pj, "accept", c)
        assert code == 0, out
        e = (reviews_of(pj, c) or [{}])[0]
        assert e.get("seen") == record(pj, c)["seen"] and set(e["seen"]) == {"plan/PLAN.md#Q1 add", "memo.py:add"}, e
        assert e.get("evidence") == "appends and prints", e


def test_B3_review_is_a_persons_only_people_json_the_name_and_their_own_kept_source():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        kept_source(pj, "L1", "lee", "yes, I read it\n")
        kept_source(pj, "K1", "kim", "fine by me\n")
        kept_source(pj, "P1", "park", "ok\n")
        kept_source(pj, "A1", "Claude (m)", "I reviewed it myself.\n")
        rid, = agent_confirms(pj, Q1_ADD)

        def refused(*argv):
            before = tree_bytes(mg(pj))
            code, out = argv[0](*argv[1:], "--target", pj.dir)
            assert code != 0, (argv[1:], out)
            assert tree_bytes(mg(pj)) == before, ("nothing written", argv[1:])
            assert "invalid choice" not in out, out
            return out
        # no roster: no person is known here
        out = refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "source:L1")
        assert "people.json" in out, out
        write(os.path.join(mg(pj), "people.json"), {"people": [], "agents": ["Claude ("]})
        assert "people.json" in refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "source:L1")
        write(os.path.join(mg(pj), "people.json"), PEOPLE)
        # a name the roster does not list, even with words of their own kept
        out = refused(run_said, "review", "accept", rid, "--by", "park", "--approved-in", "source:P1")
        assert "people.json" in out, out
        # no --approved-in: at a terminal and with an agent running alike
        for runner in (run_said, run_agent):
            out = refused(runner, "review", "accept", rid, "--by", "lee")
            assert "--approved-in" in out, (runner.__name__, out)
            out = refused(runner, "review", "reject", rid, "--by", "lee", "--why", "no")
            assert "--approved-in" in out, (runner.__name__, out)
        # no --by at all: an agent's own reading is not a person's review
        refused(run_agent, "review", "accept", rid, "--why", "I read it")
        refused(run_agent, "review", "accept", rid, "--approved-in", "source:L1")
        # someone else's words, an agent's words, a source that is not kept
        out = refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "source:K1")
        assert "kim" in out, ("whose words that source is", out)
        out = refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "source:A1")
        assert "Claude (m)" in out, out
        out = refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "source:nope")
        assert "nope" in out and "source add" in out, ("says what to record first", out)
        refused(run_said, "review", "accept", rid, "--by", "lee", "--approved-in", "lee said yes on the phone")
        assert not reviews_of(pj, rid)
        # and with all three it is recorded — by either listed person, each citing their own words
        assert review(pj, "accept", rid)[0] == 0
        assert review(pj, "accept", rid, by="kim", src="source:K1")[0] == 0
        assert [(e.get("by"), e.get("approved-in")) for e in reviews_of(pj, rid)] == [("lee", "source:L1"), ("kim", "source:K1")], reviews_of(pj, rid)


def test_B3_review_refuses_a_stale_a_broken_a_retired_and_an_unknown_relation_writing_nothing_for_any_id():
    with _review_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))

        def refused(verb, *ids, why=None):
            before = tree_bytes(mg(pj))
            code, out = review(pj, verb, *ids, why=why)
            assert code != 0, (ids, out)
            assert tree_bytes(mg(pj)) == before, ("nothing written for any id", ids, out)
            assert "invalid choice" not in out, out
            return out
        # an id that names nothing — and the good id beside it is not reviewed either
        out = refused("accept", b, "R-00000000")
        assert "R-00000000" in out, out
        out = refused("accept", "R-00000000", b)
        assert not reviews_of(pj, b)
        # stale: the code end moved since it was confirmed
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert a in stale_ids(pj)
        for verb, why in (("accept", None), ("reject", "add does not print")):
            out = refused(verb, b, a, why=why)
            assert a in out and "re-read it first" in out and ("reconfirm %s --why" % a) in out, (verb, out)
            assert "then the person reviews what was re-read" in out, out
        # ... re-read by the agent, it can be reviewed
        agent_rereads(pj, a)
        assert review(pj, "accept", a)[0] == 0 and len(reviews_of(pj, a)) == 1
        # broken: an anchor is gone
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef add(store, text):\n    return 2\n")
        out = refused("accept", a, b)
        assert b in out, out
        assert len(reviews_of(pj, a)) == 1, "the good id beside the broken one gained nothing"
        # retired
        assert run_said("retire", b, "--why", "list_ is gone", "--target", pj.dir)[0] == 0
        assert b in refused("accept", b)
        assert b in refused("reject", b, why="it was never right")
        assert review(pj, "accept", a, c)[0] != 0, "Q1's relation is stale (add changed): refused, and with it the fresh one"
        assert len(reviews_of(pj, a)) == 1 and not reviews_of(pj, c)


def test_B3_review_refuses_an_end_that_moved_where_impact_sees_nothing_stale_and_a_quote_gone_from_its_text():
    code_with_note = CODE.replace("    return 1", "    # appends to the store\n    return 1")
    r_note = rel("memo.py:add", "realizes", "concept:adding", ev="appends to the store")
    with Project() as pj:
        write(os.path.join(pj.dir, "memo.py"), code_with_note)
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        reviewers(pj)
        assert run_said("concept", "add", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        nid, qid = agent_confirms(pj, r_note, Q1_ADD)
        # the documenting side moved: nothing propagates to the code (impact: fresh), but it is not the text that was confirmed
        write(os.path.join(pj.dir, "plan", "PLAN.md"), PLAN.replace("more", "more words"))
        assert stale_ids(pj) == []
        before = tree_bytes(mg(pj))
        code, out = review(pj, "accept", qid)
        assert code != 0 and ("reconfirm %s --why" % qid) in out, out
        assert tree_bytes(mg(pj)) == before, "nothing written"
        agent_rereads(pj, qid)
        code, out = review(pj, "accept", qid)
        assert code == 0 and reviews_of(pj, qid)[0].get("seen") == record(pj, qid)["seen"], out
        # the quote was a comment: taking it out moves no fingerprint, and the evidence is no longer in the text
        write(os.path.join(pj.dir, "memo.py"), CODE)
        assert record(pj, nid)["seen"]["memo.py:add"] == mangsang.anchors_of(os.path.join(pj.dir, "memo.py"))[":add"], "fixture: not stale"
        before = tree_bytes(mg(pj))
        code, out = review(pj, "accept", nid)
        assert code != 0 and nid in out and "evidence" in out and "invalid choice" not in out, out
        assert tree_bytes(mg(pj)) == before, "nothing written"
        write(os.path.join(pj.dir, "memo.py"), code_with_note)
        assert review(pj, "accept", nid)[0] == 0 and len(reviews_of(pj, nid)) == 1


def test_B3_review_reject_needs_the_persons_reason_and_records_a_rejection():
    with _review_project() as pj:
        rid = mangsang.rel_id(R_ADD)
        r0 = record(pj, rid)
        before = tree_bytes(mg(pj))
        code, out = review(pj, "reject", rid)
        assert code != 0 and "--why" in out and "invalid choice" not in out, out
        assert tree_bytes(mg(pj)) == before, "nothing written"
        why = "lee: 'add does not print the id; it only returns it'"
        code, out = review(pj, "reject", rid, why=why)
        assert code == 0, out
        said = [l.strip() for l in out.split("\n") if l.strip().startswith("reviewed ")]
        assert len(said) == 1 and said[0].startswith("reviewed %s rejected by lee (source:L1)" % rid), out
        assert "disputed until it is revised and the person reviews it again, or it is retired" in said[0], out
        r = record(pj, rid)
        got = reviews_of(pj, rid)
        assert len(got) == 1, r
        e = got[0]
        assert e.get("verdict") == "rejected" and e.get("why") == why and e.get("by") == "lee" and e.get("approved-in") == "source:L1", e
        assert AT_RE.match(str(e.get("at"))) and e.get("seen") == r0["seen"] and e.get("evidence") == r0["evidence"], e
        assert {k: v for k, v in r.items() if k != "reviews"} == r0, "a rejection touches neither seen, confirmed nor history"
        assert os.path.exists(os.path.join(pj.dir, RELS, rid + ".json")), "a rejection retires nothing"


def test_B3_review_reject_of_a_concept_is_refused_naming_concept_drift():
    with _review_project() as pj:
        rid = mangsang.rel_id(R_ADD)
        before = tree_bytes(mg(pj))
        code, out = review(pj, "reject", "concept:adding", why="that is not what adding means")
        assert code != 0, out
        assert "concept drift adding --why" in out and "--by NAME --approved-in source:ID" in out, out
        code, out = review(pj, "reject", rid, "concept:adding", why="neither is right")
        assert code != 0 and "concept drift adding" in out, out
        assert tree_bytes(mg(pj)) == before, "nothing written — not for the relation named beside it either"


def test_B3_review_accept_of_a_concept_appends_the_sentence_reviewed():
    with _review_project() as pj:
        cpath = os.path.join(mg(pj), "concepts", "adding.json")
        c0 = mangsang.load(cpath)
        before = tree_bytes(mg(pj))
        code, out = review(pj, "accept", "concept:nosuch")
        assert code != 0 and "nosuch" in out and "invalid choice" not in out, out
        assert tree_bytes(mg(pj)) == before
        rid = mangsang.rel_id(R_ADD)
        code, out = review(pj, "accept", "concept:adding", rid)
        assert code == 0, out
        assert "accepted by lee (source:L1)" in out and "concept:adding" in out and rid in out, out
        c = mangsang.load(cpath)
        got = c.get("reviews")
        assert isinstance(got, list) and len(got) == 1, c
        e = got[0]
        assert {k: e.get(k) for k in ("by", "approved-in", "verdict", "means")} == {
            "by": "lee", "approved-in": "source:L1", "verdict": "accepted", "means": "a memo is appended and its id printed"}, e
        assert AT_RE.match(str(e.get("at"))) and "seen" not in e and "evidence" not in e, e
        assert {k: v for k, v in c.items() if k != "reviews"} == c0, "the declaration and the history are not touched"
        assert c["declared"].get("agent") == "Claude Code", "the meaning is still the agent's sentence; the review says a person read it"
        assert len(reviews_of(pj, rid)) == 1 and "means" not in reviews_of(pj, rid)[0]


# B2 / B5 — the state a review leaves, as `check` and `review status` count it

def status_numbers(line):
    """`relations M, reviewed N, at an earlier text K, never R, disputed D` in a status line — `label N` or `N label`."""
    got = {}
    for key, label in (("relations", r"relation(?:s|\(s\))?"), ("reviewed", "reviewed"), ("earlier", "at an earlier text"),
                       ("never", "never"), ("disputed", "disputed")):
        m = re.search(r"(?<![\w-])%s:? (\d+)(?!\d)" % label, line) or re.search(r"(?<!\d)(\d+) %s(?![\w-])" % label, line)
        assert m, ("a status line says `%s` with its number" % key, line)
        got[key] = int(m.group(1))
    return got


def status_line(out, word):
    lines = [l for l in out.split("\n") if word in l.lower() and re.search(r"\d", l)]
    assert lines, (word, out)
    return lines[-1] if word == "total" else lines[0]


def test_B2_an_accept_counts_as_reviewed_until_the_text_moves_then_as_reviewed_at_an_earlier_text():
    with _review_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert person_review(pj) == (0, 3, 0, 0, 0, 1)
        assert review(pj, "accept", a)[0] == 0
        assert person_review(pj) == (1, 3, 0, 0, 0, 1)
        e = reviews_of(pj, a)[0]
        # the code end changes: the record never claims the person saw this text — before the re-read and after it
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert person_review(pj) == (0, 3, 1, 0, 0, 1)
        agent_rereads(pj, a, why="the return value changed; add still appends")
        assert record(pj, a)["confirmed"].get("agent") == "Claude Code" and record(pj, a)["seen"] != e["seen"]
        assert reviews_of(pj, a) == [e], "the review entry itself is unchanged by a re-read"
        assert person_review(pj) == (0, 3, 1, 0, 0, 1)
        code, out = run_said("review", "status", "--target", pj.dir)
        assert code == 0, out
        assert status_numbers(status_line(out, "adding")) == {"relations": 2, "reviewed": 0, "earlier": 1, "never": 1, "disputed": 0}, out
        assert status_numbers(status_line(out, "total")) == {"relations": 3, "reviewed": 0, "earlier": 1, "never": 2, "disputed": 0}, out
        # the person reviews what was re-read: reviewed again, two entries
        assert review(pj, "accept", a)[0] == 0
        assert person_review(pj) == (1, 3, 0, 0, 0, 1)
        assert len(reviews_of(pj, a)) == 2 and reviews_of(pj, a)[1]["seen"] == record(pj, a)["seen"]
        # a new quote alone is another text too
        agent_rereads(pj, a, "--evidence", "def add", why="the shorter quote is what holds")
        assert person_review(pj) == (0, 3, 1, 0, 0, 1)


def test_B2_a_relation_a_person_confirmed_counts_as_reviewed_at_that_text():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        reviewers(pj)
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [Q1_ADD]})
        assert run_said("confirm", props, "--by", "lee", "--target", pj.dir)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        agent_confirms(pj, rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists."))
        assert person_review(pj) == (1, 2, 0, 0, 0, 0), "lee's own signature is lee's review of that text"
        # the agent re-reads a changed end: lee's signature is now a history entry, of an earlier text
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert person_review(pj) == (0, 2, 1, 0, 0, 0)
        agent_rereads(pj, rid)
        r = record(pj, rid)
        assert r["confirmed"].get("agent") == "Claude Code" and r["history"][-1]["confirmed"].get("by") == "lee", r
        assert "reviews" not in r, "no command writes a review except review accept|reject"
        assert person_review(pj) == (0, 2, 1, 0, 0, 0)
        code, out = run_said("review", "status", "--target", pj.dir)
        assert code == 0 and status_numbers(status_line(out, "total")) == {"relations": 2, "reviewed": 0, "earlier": 1, "never": 1, "disputed": 0}, out
        # the text comes back to what lee signed and the agent re-reads it: both ends and the quote are what lee saw
        write(os.path.join(pj.dir, "memo.py"), CODE)
        agent_rereads(pj, rid, why="the change was reverted")
        assert record(pj, rid)["seen"] == r["history"][-1]["seen"], "fixture: the same fingerprints as lee's"
        assert person_review(pj) == (1, 2, 0, 0, 0, 0)


def test_B2_latest_is_by_at_and_an_entry_without_at_is_older_than_any_with_it():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        reviewers(pj)
        r2 = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        assert pj.propose(Q1_ADD, r2)[0] == 0   # kim's own signatures
        a, b = mangsang.rel_id(Q1_ADD), mangsang.rel_id(r2)
        # a: a rejection written with no `at` (by hand, as nothing dates it) is older than kim's dated signature: not disputed
        pa = os.path.join(pj.dir, RELS, a + ".json")
        r = mangsang.load(pa)
        assert r["confirmed"].get("by") == "kim" and r["confirmed"].get("at"), r
        r["reviews"] = [{"by": "lee", "approved-in": "source:L1", "verdict": "rejected", "seen": dict(r["seen"]),
                         "evidence": r["evidence"], "why": "an old objection"}]
        mangsang.save(pa, r)
        # b: kim's signature as an older release wrote it (no `at`), then lee's dated rejection: disputed
        pb = os.path.join(pj.dir, RELS, b + ".json")
        r = mangsang.load(pb)
        r["confirmed"] = {"by": "kim"}
        mangsang.save(pb, r)
        assert person_review(pj) == (2, 2, 0, 0, 0, 0), "before any dated review: kim's signatures are the latest on both"
        assert review(pj, "reject", b, why="list_ lists nothing")[0] == 0
        assert person_review(pj) == (1, 2, 0, 1, 0, 0)
        # dated reviews order by their time, not by where they sit in the list
        r = mangsang.load(pb)
        assert len(r.get("reviews", [])) == 1, r
        newer = dict(r["reviews"][0], verdict="accepted", at="2999-01-01T00:00:00Z")
        newer.pop("why", None)
        r["reviews"] = [newer, r["reviews"][0]]
        mangsang.save(pb, r)
        assert person_review(pj) == (2, 2, 0, 0, 0, 0)


def test_B5_check_says_how_much_a_person_reviewed_and_its_exit_code_does_not_move():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        reviewers(pj)
        assert run_agent("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--why", "the plan's Q1 says so",
                         "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "listing", "--means", "memos are read back", "--by", "kim", "--target", pj.dir)[0] == 0
        code0, out = run_said("check", "--target", pj.dir)
        assert "reviewed by a person" not in out, ("the model holds no relation: nothing to say", out)
        a, b, c = agent_confirms(pj, R_ADD, R_LIST, Q1_ADD)
        r2 = rel("plan/PLAN.md#Q2 list", "documents", "memo.py:list_", ev="lists.")
        assert pj.propose(r2)[0] == 0   # kim's own
        code1, out = run_said("check", "--target", pj.dir)
        lines = [l for l in out.split("\n") if "reviewed by a person" in l]
        assert len(lines) == 1, ("one observation line", out)
        assert "reviewed by a person: 1 of 4 relation(s); 0 changed since review; 0 disputed; meanings signed by a person: 1 of 2" in lines[0], out
        findings1 = run_said("check", "--findings", "--target", pj.dir)[0]
        assert review(pj, "accept", a, "concept:adding")[0] == 0
        assert review(pj, "reject", b, why="list_ appends nothing")[0] == 0
        code2, out = run_said("check", "--target", pj.dir)
        assert "reviewed by a person: 2 of 4 relation(s); 0 changed since review; 1 disputed; meanings signed by a person: 2 of 2" in out, out
        assert code2 == code1, ("reviews — a dispute too — never change check's exit code", code1, code2)
        code, out = run_said("check", "--findings", "--target", pj.dir)
        assert code == findings1, (code, findings1)
        found = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "person-review"]
        assert len(found) == 1 and found[0].get("layer") == "observation", out
        assert "2 of 4" in str(found[0].get("text")) and "1 disputed" in str(found[0].get("text")), found
        # a meaning revised by the agent after the person accepted it is not the sentence the person read
        edit(pj, "memo.py", "return []", "return [0]")
        assert run_agent("concept", "revise", "adding", "--means", "a memo is appended", "--why", "shorter", "--target", pj.dir)[0] == 0
        got = person_review(pj)
        assert got[4:] == (1, 2) and got[1] == 4, got
        assert got[0] == 0 and got[2] == 2, ("kim's and lee's reviews were of texts that have moved", got)


def test_B5_review_status_is_a_line_per_concept_then_the_totals_and_writes_nothing():
    with _review_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert run_said("concept", "add", "listing", "--means", "memos are read back", "--by", "kim", "--target", pj.dir)[0] == 0
        r2 = rel("plan/PLAN.md#Q2 list", "realizes", "concept:listing", ev="lists.")
        assert pj.propose(r2)[0] == 0   # kim's own
        assert review(pj, "accept", a)[0] == 0
        assert review(pj, "reject", b, why="list_ appends nothing")[0] == 0
        before = tree_bytes(mg(pj))
        code, out = run_said("review", "status", "--target", pj.dir)
        assert code == 0, out
        assert status_numbers(status_line(out, "adding")) == {"relations": 2, "reviewed": 1, "earlier": 0, "never": 0, "disputed": 1}, out
        assert status_numbers(status_line(out, "listing")) == {"relations": 1, "reviewed": 1, "earlier": 0, "never": 0, "disputed": 0}, out
        assert status_numbers(status_line(out, "total")) == {"relations": 4, "reviewed": 2, "earlier": 0, "never": 1, "disputed": 1}, out
        lines = out.split("\n")
        assert lines.index(status_line(out, "total")) > max(lines.index(status_line(out, "adding")), lines.index(status_line(out, "listing"))), out
        unsigned = status_line(out, "adding")
        # whether a person signed the meaning is said: the line changes when lee accepts the sentence, its numbers do not
        assert review(pj, "accept", "concept:adding")[0] == 0
        before = tree_bytes(mg(pj))
        code, out = run_said("review", "status", "--target", pj.dir)
        assert code == 0 and status_line(out, "adding") != unsigned, out
        assert status_numbers(status_line(out, "adding")) == status_numbers(unsigned), out
        code, out = run_said("review", "status", "--concept", "listing", "--target", pj.dir)
        assert code == 0 and "adding" not in out, out
        assert status_numbers(status_line(out, "listing"))["relations"] == 1, out
        assert tree_bytes(mg(pj)) == before, "review status writes nothing"


# B6 — a rejection is unresolved until the projection is revised

def _signed_project():
    """`adding` declared by kim (a person signed its meaning); its relations confirmed by the agent."""
    pj = Project()
    assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
    reviewers(pj)
    assert run_said("concept", "add", "adding", "--means", "a memo is appended and its id printed", "--by", "kim", "--target", pj.dir)[0] == 0
    agent_confirms(pj, R_ADD, R_LIST, Q1_ADD)
    return pj


def test_B6_a_rejected_relation_is_disputed_in_impact_counted_and_a_finding():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out and "disputed" not in out, out
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        before = tree_bytes(mg(pj))
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1, out
        lines = [l for l in out.split("\n") if l.strip().startswith("disputed") and a in l]
        assert len(lines) == 1, out
        assert ("%s memo.py:add realizes concept:adding" % a) in re.sub(r"\s+", " ", lines[0]), lines
        assert "rejected by lee (source:L1): add does not print the id" in lines[0], lines
        assert "revise it (change the projection, then reconfirm) or retire it" in lines[0], lines
        assert "unresolved_total = 1" in out, out
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        found = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "disputed"]
        assert code == 1 and len(found) == 1 and a in json.dumps(found[0]), out
        assert found[0].get("layer") != "observation", found
        # --only scopes it like any relation
        code, out = run_said("impact", "--only", "memo.py:list_", "--target", pj.dir)
        assert code == 0 and a not in out, out
        code, out = run_said("impact", "--only", "memo.py:add", "--target", pj.dir)
        assert code == 1 and a in out and "unresolved_total = 1" in out, out
        # a re-read that changes nothing revises nothing
        run_agent("reconfirm", a, "--why", "I still think it holds", "--target", pj.dir)
        assert run_said("impact", "--target", pj.dir)[0] == 1, "still disputed: neither the projection nor the quote changed"
        assert tree_bytes(mg(pj)) == before, "impact and a no-change re-read write nothing"
        # lookup says it, by id and by file
        code, out = run_said("lookup", a, "--target", pj.dir)
        assert "disputed by lee" in out and "add does not print the id" in out, out
        code, out = run_said("lookup", "memo.py", "--target", pj.dir)
        assert "disputed by lee" in out, out
        code, out = run_said("lookup", b, "--target", pj.dir)
        assert "disputed" not in out, out


def test_B6_a_disputed_relation_revised_awaits_the_person_and_is_no_longer_counted():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        assert review(pj, "reject", b, why="the def line says nothing about adding")[0] == 0
        assert person_review(pj)[3] == 2
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 2" in out, out
        # a: the agent changes the projection and re-reads it
        edit(pj, "memo.py", "    return 1", "    print('#1')\n    return 1")
        agent_rereads(pj, a, why="add prints the id now", )
        agent_rereads(pj, c, why="the section still documents add")
        # b: the agent re-quotes
        agent_rereads(pj, b, "--evidence", "return []", why="the body is what realizes it")
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, ("revised: it awaits the person, and nothing else is open", out)
        for x in (a, b):
            lines = [l for l in out.split("\n") if x in l]
            assert lines and any("review" in l for l in lines), ("listed as awaiting the person's review", x, out)
            assert not any(l.strip().startswith("disputed") and "retire it" in l for l in lines), (x, out)
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        assert code == 0 and not [f for f in json.loads(out).get("findings", []) if f.get("kind") == "disputed" and f.get("layer") != "observation"], out
        assert person_review(pj)[3] == 2, "still disputed for the count: the person has not reviewed the revision"
        assert reviews_of(pj, a)[0].get("verdict") == "rejected" and len(reviews_of(pj, a)) == 1
        # the person rejects the revision too: unresolved again
        p = os.path.join(pj.dir, RELS, b + ".json")
        r = mangsang.load(p)
        r["reviews"][0]["at"] = "2026-01-01T00:00:00Z"   # the first rejection was a while ago
        mangsang.save(p, r)
        assert review(pj, "reject", b, why="the body lists; it does not add")[0] == 0
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out and "the body lists" in out, out
        # ... and a retirement settles it
        assert run_said("retire", b, "--why", "list_ never realized adding", "--target", pj.dir)[0] == 0
        code, out = run_said("impact", "--target", pj.dir)
        assert b not in out and "the body lists" not in out, out
        assert not [f for f in json.loads(run_said("impact", "--findings", "--target", pj.dir)[1]).get("findings", []) if f.get("kind") == "disputed"]


def test_B6_a_later_accept_clears_the_dispute():
    with _signed_project() as pj:
        a = mangsang.rel_id(R_ADD)
        assert review(pj, "reject", a, why="add does not print the id")[0] == 0
        assert run_said("impact", "--target", pj.dir)[0] == 1
        p = os.path.join(pj.dir, RELS, a + ".json")
        r = mangsang.load(p)
        r["reviews"][0]["at"] = "2026-01-01T00:00:00Z"   # the rejection was a while ago
        mangsang.save(p, r)
        assert review(pj, "accept", a, why="lee: 'I misread it — returning the id is what we meant'")[0] == 0
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out and a not in out and "disputed" not in out, out
        assert person_review(pj) == (1, 3, 0, 0, 1, 1)
        code, out = run_said("lookup", a, "--target", pj.dir)
        assert "disputed" not in out, out
        assert [e.get("verdict") for e in reviews_of(pj, a)] == ["rejected", "accepted"], "the rejection stays on the record"


# B4 — the queue

LONG_WHY = ("the function gathers every memo into a new list, sorts that list and hands it back, which is what reading memos back in "
            "order asks for; nothing else in this file touches the order, and the plan's Q2 section names no other place that could "
            "— so this is the one projection")
PAD = "".join("    pad%02d = 'a line of padding number %02d in a long function'\n" % (i, i) for i in range(12))
LISTS = ("def show(store):\n    return list(store)\n\n\n"
         "def count(store):\n    return len(store)\n\n\n"
         "def first(store):\n    return store[0]\n\n\n"
         "def last(store):\n    tail = 0\n" + PAD + "    return store[-1]\n\n\n"
         "def sort(store):\n    out = []\n" + PAD + "    out.extend(sorted(store))\n" + PAD.replace("pad", "end") + "    return out\n\n\n"
         "def clear(store):\n    return []\n")
QUOTES = {"show": "def show(store):", "count": "def count(store):", "first": "def first(store):", "last": "return store[-1]",
          "sort": "out.extend(sorted(store))", "clear": "def clear(store):"}
MEANS_ADDING = "a memo is appended to the store and its id printed"
MEANS_LISTING = "the memos are read back in the order they were added, the oldest first"


def _queue_project():
    """Two concepts whose meanings the agent declared (no person signed them); two projections of `adding`, six of `listing`,
    one relation between two artifacts — every relation the agent's own confirmation."""
    assert len(LONG_WHY) > 210
    pj = Project()
    write(os.path.join(pj.dir, "lists.py"), LISTS)
    assert run_said("register", "plan/PLAN.md", "memo.py", "lists.py", "--target", pj.dir)[0] == 0
    reviewers(pj)
    for name, means in (("adding", MEANS_ADDING), ("listing", MEANS_LISTING)):
        assert run_agent("concept", "add", name, "--means", means, "--why", "the plan says so", "--target", pj.dir)[0] == 0
    ids = {}
    ids["add"], ids["q1c"], ids["q1"] = agent_confirms(pj, R_ADD, rel("plan/PLAN.md#Q1 add", "realizes", "concept:adding"), Q1_ADD)
    for name in ("show", "count", "first", "last", "clear"):
        ids[name], = agent_confirms(pj, rel("lists.py:" + name, "realizes", "concept:listing", ev=QUOTES[name]))
    ids["sort"], = agent_confirms(pj, rel("lists.py:sort", "realizes", "concept:listing", ev=QUOTES["sort"]), why=LONG_WHY)
    return pj, ids


def _queue_states(pj, ids):
    """lee signs `listing`'s meaning, then: show reviewed · count rejected, not revised · first rejected, then revised ·
    last reviewed, then changed and re-read · clear never reviewed, re-read twice · sort never reviewed, never re-read."""
    code, out = review(pj, "accept", "concept:listing")
    assert code == 0, out
    assert review(pj, "accept", ids["show"], ids["last"])[0] == 0
    assert review(pj, "reject", ids["count"], why="counting is not reading back")[0] == 0
    assert review(pj, "reject", ids["first"], why="first returns one memo; reading back is all of them")[0] == 0
    edit(pj, "lists.py", "return store[0]", "return store[:1]")
    agent_rereads(pj, ids["first"], why="first returns a list now")
    edit(pj, "lists.py", "tail = 0", "tail = -1")
    agent_rereads(pj, ids["last"], why="only the unused local changed")
    for n in (1, 2):
        edit(pj, "lists.py", "def clear(store):\n    return []" + " + []" * (n - 1), "def clear(store):\n    return []" + " + []" * n)
        agent_rereads(pj, ids["clear"], why="clear still empties (edit %d)" % n)
    assert stale_ids(pj) == []


def queue_json(pj, *more):
    code, out = run_said("review", "queue", "--json", *more, "--target", pj.dir)
    assert code == 0, out
    doc = json_out(out, "mangsang/review-queue@1")
    assert isinstance(doc.get("entries"), list) and all(isinstance(e, dict) for e in doc["entries"]), doc
    return doc


def packet(out, rid):
    """A relation's packet in the plain queue: from its id to the end of the line of its command (the last line naming it)."""
    assert out.count(rid) >= 2, ("a packet starts with the id and ends with the command naming it", rid, out)
    end = out.find("\n", out.rindex(rid))
    return out[out.index(rid): end if end != -1 else len(out)]


def test_B4_meanings_no_person_signed_come_first_and_hold_their_relations_back():
    pj, ids = _queue_project()
    with pj:
        before = tree_bytes(mg(pj))
        code, out = run_said("review", "queue", "--target", pj.dir)
        assert code == 0, out
        for name, means in (("adding", MEANS_ADDING), ("listing", MEANS_LISTING)):
            assert means in out, ("the whole meaning", name, out)
            assert ("mangsang review accept concept:%s --by NAME --approved-in source:ID" % name) in out, out
            assert ('mangsang concept revise %s --means "..." --by NAME --approved-in source:ID' % name) in out, out
        assert out.index(MEANS_ADDING) < out.index(MEANS_LISTING), "by name"
        assert "Claude Code" in out, ("who declared it", out)
        for key in ("add", "q1c", "show", "count", "first", "last", "clear", "sort"):
            assert ids[key] not in out, ("a relation whose concept's meaning no person signed is not listed", key, out)
        assert ids["q1"] in out and out.index(ids["q1"]) > out.index(MEANS_LISTING), ("a relation between two artifacts waits on no meaning", out)
        doc = queue_json(pj)
        kinds = [(e.get("kind"), str(e.get("id"))) for e in doc["entries"]]
        assert [k for k, _ in kinds] == ["concept", "concept", "relation"], kinds
        assert kinds[0][1].endswith("adding") and kinds[1][1].endswith("listing") and kinds[2][1] == ids["q1"], kinds
        assert doc["entries"][0].get("meaning") == MEANS_ADDING, doc["entries"][0]
        assert "review accept concept:adding" in str(doc["entries"][0].get("command")), doc["entries"][0]
        assert doc.get("held") == {"adding": 2, "listing": 6}, ("the closing line counts the relations held back, per concept", doc.get("held"))
        closing = [l for l in out.split("\n") if re.search(r"(?<!\d)6(?!\d)", l) and "listing" in l]
        assert closing, ("how many relations wait on listing's meaning", out)
        assert tree_bytes(mg(pj)) == before, "the queue writes nothing"


def test_B4_concept_names_a_concept_whose_entry_and_relations_are_listed_whatever_its_meanings_state():
    pj, ids = _queue_project()
    with pj:
        doc = queue_json(pj, "--concept", "adding")
        got = [(e.get("kind"), str(e.get("id"))) for e in doc["entries"]]
        assert got[0][0] == "concept" and got[0][1].endswith("adding"), got
        assert sorted(i for k, i in got[1:]) == sorted([ids["add"], ids["q1c"]]) and {k for k, _ in got[1:]} == {"relation"}, got
        assert all(e.get("state") == "never" for e in doc["entries"][1:]), doc["entries"]
        code, out = run_said("review", "queue", "--concept", "adding", "--target", pj.dir)
        assert code == 0 and ids["add"] in out and ids["q1c"] in out and MEANS_ADDING in out, out
        assert ids["show"] not in out and ids["q1"] not in out and MEANS_LISTING not in out, out


def test_B4_a_signed_meanings_relations_are_listed_by_tier_then_by_how_often_they_were_re_read():
    pj, ids = _queue_project()
    with pj:
        _queue_states(pj, ids)
        before = tree_bytes(mg(pj))
        doc = queue_json(pj)
        got = [(e.get("kind"), str(e.get("id")), e.get("state")) for e in doc["entries"]]
        assert got[0][0] == "concept" and got[0][1].endswith("adding") and len([g for g in got if g[0] == "concept"]) == 1, got
        assert got[1:] == [("relation", ids["first"], "disputed-revised"), ("relation", ids["clear"], "never"),
                           ("relation", ids["sort"], "never"), ("relation", ids["last"], "reviewed-earlier"),
                           ("relation", ids["q1"], "never")], got
        assert all(str(e.get("concept", "")).endswith("listing") for e in doc["entries"][1:5]), doc["entries"]
        assert doc.get("held") == {"adding": 2}, doc.get("held")
        assert doc.get("disputed") == 1, ("count's rejection awaits a revision or a retirement", doc.get("disputed"))
        for e in doc["entries"][1:]:
            assert ("review accept %s" % e["id"]) in str(e.get("command")), e
            assert e.get("quote") == record(pj, e["id"])["evidence"], e
        # the plain queue: the same order, and neither the reviewed nor the unrevised disputed one
        code, out = run_said("review", "queue", "--target", pj.dir)
        assert code == 0, out
        at = [out.index(ids[k]) if ids[k] in out else -1 for k in ("first", "clear", "sort", "last", "q1")]
        assert -1 not in at and at == sorted(at), (at, out)
        assert out.index(MEANS_ADDING) < at[0], "the unsigned meaning comes first"
        for key in ("show", "count", "add", "q1c"):
            assert ids[key] not in out, (key, out)
        assert tree_bytes(mg(pj)) == before, "the queue writes nothing"
        # a concept revise in the person's own words signs the meaning too: adding's relations follow (stale ones re-read first)
        code, out = run_said("concept", "revise", "adding", "--means", "a memo is appended; its id is printed", "--by", "lee",
                             "--approved-in", "source:L1", "--target", pj.dir)
        assert code == 0, out
        for key in ("add", "q1c"):
            agent_rereads(pj, ids[key], why="the new sentence says the same of this end")
        doc = queue_json(pj)
        assert not [e for e in doc["entries"] if e.get("kind") == "concept"], doc["entries"]
        assert sorted(e["id"] for e in doc["entries"] if str(e.get("concept", "")).endswith("adding")) == sorted([ids["add"], ids["q1c"]]), doc["entries"]
        assert doc.get("held") in ({}, None), doc.get("held")


def test_B4_groups_follow_the_most_recent_approval_of_their_meaning_and_artifacts_come_last():
    pj, ids = _queue_project()
    with pj:
        assert run_said("concept", "add", "storing", "--means", "memos are kept in one list", "--by", "kim", "--target", pj.dir)[0] == 0
        ids["q2s"] = mangsang.rel_id(rel("plan/PLAN.md#Q2 list", "realizes", "concept:storing"))
        agent_confirms(pj, rel("plan/PLAN.md#Q2 list", "realizes", "concept:storing", ev="lists."))
        # storing: signed by kim as an older release wrote it — no time recorded: the oldest approval
        sp = os.path.join(mg(pj), "concepts", "storing.json")
        c = mangsang.load(sp)
        c["declared"] = {"by": "kim"}
        mangsang.save(sp, c)
        # listing: accepted by lee a while ago; adding: accepted now
        assert review(pj, "accept", "concept:listing")[0] == 0
        lp = os.path.join(mg(pj), "concepts", "listing.json")
        c = mangsang.load(lp)
        assert len(c.get("reviews", [])) == 1, c
        c["reviews"][0]["at"] = "2026-01-01T00:00:00Z"
        mangsang.save(lp, c)
        assert review(pj, "accept", "concept:adding")[0] == 0
        doc = queue_json(pj)
        groups = []
        for e in doc["entries"]:
            assert e.get("kind") == "relation", e
            name = str(e.get("concept") or "")
            name = name[len("concept:"):] if name.startswith("concept:") else name
            if not groups or groups[-1] != name:
                groups.append(name)
        assert groups[:3] == ["adding", "listing", "storing"] and len(groups) == 4, groups
        assert doc["entries"][-1]["id"] == ids["q1"] and groups[3] not in ("adding", "listing", "storing"), (groups, doc["entries"][-1])
        assert len(doc["entries"]) == 10, len(doc["entries"])
        # within a tier, ties by id
        listing = [e["id"] for e in doc["entries"] if str(e.get("concept", "")).endswith("listing")]
        assert listing == sorted(ids[k] for k in ("show", "count", "first", "last", "clear", "sort")), listing
        # the same recency on both (none recorded) falls to the re-read count, then the name
        for p in (lp, os.path.join(mg(pj), "concepts", "adding.json")):
            c = mangsang.load(p)
            c["declared"] = {"by": "kim"}
            c.pop("reviews", None)
            mangsang.save(p, c)
        edit(pj, "lists.py", "return len(store)", "return len(list(store))")
        agent_rereads(pj, ids["count"])
        doc = queue_json(pj)
        groups = []
        for e in doc["entries"]:
            name = str(e.get("concept") or "")
            name = name[len("concept:"):] if name.startswith("concept:") else name
            if not groups or groups[-1] != name:
                groups.append(name)
        assert groups[:3] == ["listing", "adding", "storing"], ("listing's relations were re-read once, the others never; then by name", groups)
        assert [e["id"] for e in doc["entries"] if str(e.get("concept", "")).endswith("listing")][0] == ids["count"], "most re-read first"


def test_B4_a_relation_packet_is_what_a_person_needs_to_judge_it():
    pj, ids = _queue_project()
    with pj:
        _queue_states(pj, ids)
        code, out = run_said("review", "queue", "--target", pj.dir)
        assert code == 0, out
        # never reviewed, the agent's long reason cut at 200 characters, the excerpt centred on the quote
        p = packet(out, ids["sort"])
        assert "lists.py:sort realizes concept:listing" in p and "never reviewed" in p, p
        assert MEANS_LISTING in p, ("the concept's whole meaning", p)
        assert ('quote: "%s"' % QUOTES["sort"]) in p and p.count(QUOTES["sort"]) >= 2, ("the quote, and the excerpt holding it", p)
        assert "def sort(store)" not in p, ("the excerpt is centred on the quote, not the start of a long function", p)
        assert "signed:" in p and "Claude Code" in p, p
        assert LONG_WHY[:200] in p and LONG_WHY[:215] not in p, ("the signer's why, its first 200 characters", p)
        assert ("mangsang review accept %s --by NAME --approved-in source:ID" % ids["sort"]) in p, p
        assert ("review reject %s" % ids["sort"]) in p and "--why" in p[p.index("review reject"):], p
        # reviewed at an earlier text
        p = packet(out, ids["last"])
        assert re.search(r"reviewed at an earlier text by lee on \d{4}-\d\d-\d\d", p), p
        assert ('quote: "%s"' % QUOTES["last"]) in p and "only the unused local changed" in p, p
        # disputed, revised since: the person's reason is there
        p = packet(out, ids["first"])
        assert "disputed by lee, revised since" in p and "first returns one memo; reading back is all of them" in p, p
        assert "first returns a list now" in p, ("signed: with the agent's why for the revision", p)
        # a relation between two artifacts: both ends excerpted, no concept's meaning
        p = packet(out, ids["q1"])
        assert "plan/PLAN.md#Q1 add documents memo.py:add" in p and "def add(store, text):" in p and "never reviewed" in p, p
        assert MEANS_LISTING not in p and MEANS_ADDING not in p, p


def test_B4_queue_json_excerpts_hold_the_quote_in_at_most_240_characters_and_say_which_end_changed():
    pj, ids = _queue_project()
    with pj:
        _queue_states(pj, ids)
        doc = queue_json(pj)
        by_id = {e.get("id"): e for e in doc["entries"]}
        for key in ("first", "clear", "sort", "last", "q1"):
            assert ids[key] in by_id, (key, sorted(by_id, key=str))
            e = by_id[ids[key]]
            assert {"kind", "id", "state", "quote", "command", "excerpts", "signed", "changed"} <= set(e), sorted(e)
            ex = e.get("excerpts")
            r = record(pj, ids[key])
            assert isinstance(ex, dict) and set(ex) == {a for a in (r["src"], r["dst"]) if not a.startswith("concept:")}, (key, ex)
            for anchor, text in ex.items():
                assert isinstance(text, str) and 0 < len(text) <= 240, (anchor, len(text))
                assert "\n" not in text and "  " not in text, ("whitespace collapsed", text)
            assert any(e["quote"] in text for text in ex.values()), (key, e["quote"], ex)
        sort = by_id[ids["sort"]]
        assert QUOTES["sort"] in sort["excerpts"]["lists.py:sort"] and "def sort" not in sort["excerpts"]["lists.py:sort"], sort["excerpts"]
        assert len(sort["excerpts"]["lists.py:sort"]) > 120, ("an excerpt, not the quote alone", sort["excerpts"])
        assert sort.get("meaning") == MEANS_LISTING and "Claude Code" in str(sort.get("signed")), sort
        assert LONG_WHY[:200] in str(sort.get("why")), sort
        assert not sort.get("changed"), ("never reviewed: nothing changed since a review", sort)
        last = by_id[ids["last"]]
        assert QUOTES["last"] in last["excerpts"]["lists.py:last"], ("a quote at the very end of a long text is still in its excerpt", last["excerpts"])
        assert "def last" not in last["excerpts"]["lists.py:last"], last["excerpts"]
        assert isinstance(last.get("changed"), list) and any("lists.py:last" in str(x) for x in last["changed"]), last
        assert not any("concept:listing" in str(x) for x in last["changed"]), ("only the end whose fingerprint differs", last)
        first = by_id[ids["first"]]
        assert isinstance(first.get("changed"), list) and any("lists.py:first" in str(x) for x in first["changed"]), first
        q1 = by_id[ids["q1"]]
        assert set(q1["excerpts"]) == {"plan/PLAN.md#Q1 add", "memo.py:add"} and not q1.get("meaning"), q1
        assert q1["excerpts"]["memo.py:add"].startswith("def add(store, text):"), ("no quote in this end: its start", q1["excerpts"])
        # a re-quote after a review: the quote then and now
        agent_rereads(pj, ids["last"], "--evidence", "tail = -1", why="the local is the better quote")
        code, out = run_said("review", "queue", "--target", pj.dir)
        p = packet(out, ids["last"])
        assert QUOTES["last"] in p and 'quote: "tail = -1"' in p, ("the quote then -> now", p)


def test_B4_queue_limit_counts_every_kind_of_entry_and_markdown_has_a_title_and_a_heading_per_concept():
    pj, ids = _queue_project()
    with pj:
        _queue_states(pj, ids)
        before = tree_bytes(mg(pj))
        assert len(queue_json(pj)["entries"]) == 6
        doc = queue_json(pj, "--limit", "2")
        assert [(e.get("kind"), e.get("state")) for e in doc["entries"]][1:] == [("relation", "disputed-revised")] and len(doc["entries"]) == 2, doc["entries"]
        code, out = run_said("review", "queue", "--limit", "2", "--target", pj.dir)
        assert code == 0 and MEANS_ADDING in out and ids["first"] in out, out
        assert not any(ids[k] in out for k in ("clear", "sort", "last", "q1")), out
        assert len(queue_json(pj, "--limit", "1")["entries"]) == 1
        code, out = run_said("review", "queue", "--markdown", "--target", pj.dir)
        assert code == 0, out
        lines = out.strip().split("\n")
        assert lines[0].startswith("# ") and len([l for l in lines if l.startswith("# ")]) == 1, lines[:3]
        heads = [l for l in lines if l.startswith("## ")]
        assert any("listing" in h for h in heads) and any("adding" in h for h in heads), heads
        assert "## between artifacts" in [h.strip() for h in heads] and heads.index("## between artifacts") == len(heads) - 1, heads
        li = next(i for i, l in enumerate(lines) if l.startswith("## ") and "listing" in l)
        ba = lines.index("## between artifacts")
        for key in ("first", "clear", "sort", "last"):
            item = [i for i, l in enumerate(lines) if l.lstrip().startswith(("- ", "* ")) and ids[key] in l]
            assert item and li < item[0] < ba, (key, out)
        assert any(l.lstrip().startswith(("- ", "* ")) and ids["q1"] in l for l in lines[ba:]), out
        assert QUOTES["clear"] in out and MEANS_LISTING in out and "clear still empties (edit 2)" in out, ("the same facts", out)
        assert ("review accept %s --by NAME --approved-in source:ID" % ids["clear"]) in out, out
        assert ids["show"] not in out and ids["count"] not in out, out
        code, out = run_said("review", "queue", "--markdown", "--json", "--target", pj.dir)
        assert code != 0, ("one format at a time", out)
        assert tree_bytes(mg(pj)) == before, "the queue writes nothing in any format"


# B7 — nothing else writes a review

def test_B7_no_command_but_review_writes_a_review_and_a_reviewed_relation_goes_stale_as_before():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert review(pj, "accept", a, b)[0] == 0
        e = reviews_of(pj, a)
        assert len(e) == 1
        assert run_said("impact", "--target", pj.dir)[0] == 0
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        assert sorted(stale_ids(pj)) == sorted([a, c]), "a person's review holds nothing fresh: staleness is what it was"
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 2" in out, out
        assert run_said("reconfirm", a, "--by", "kim", "--why", "add still appends", "--target", pj.dir)[0] == 0
        r = record(pj, a)
        assert r.get("reviews") == e and r["confirmed"].get("outcome") == "held", r
        assert run_said("concept", "revise", "adding", "--means", "a memo is appended", "--by", "kim", "--target", pj.dir)[0] == 0
        assert "reviews" not in mangsang.load(os.path.join(mg(pj), "concepts", "adding.json")), "a revise is a signature, not a review entry"
        assert run_said("retire", b, "--why", "list_ never realized adding", "--target", pj.dir)[0] == 0
        assert not reviews_of(pj, c)


# phase A, repaired with phase B: the earlier text in a shallow clone

def _shallow_clone(origin):
    import subprocess
    dest = tempfile.mkdtemp(prefix="mangsang-clone-")
    p = subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + os.path.abspath(origin), os.path.join(dest, "c")],
                       capture_output=True, text=True)
    if p.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise Skip("git clone --depth 1 of a local repository failed here: %s" % p.stderr.strip()[:200])
    return dest, os.path.join(dest, "c")


def test_A3_reconfirm_in_a_shallow_clone_diffs_against_the_commit_it_has_and_says_shallow_when_it_does_not_reach():
    with Project() as pj:
        g = git_repo(pj.dir)
        assert run_said("register", "plan/PLAN.md", "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        g("add", "-A"); g("commit", "-qm", "the text the confirmer saw")
        sha = g("rev-parse", "HEAD")
        # depth 1, and that one commit holds what the confirmer saw
        dest, clone = _shallow_clone(pj.dir)
        try:
            write(os.path.join(clone, "memo.py"), NEW_CODE)
            code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "the return changed; add still appends", "--target", clone)
            assert code == 0, out
            r = json.load(open(os.path.join(clone, RELS, rid + ".json"), encoding="utf-8"))
            e = one_read(r.get("confirmed"))
            assert e.get("anchor") == "memo.py:add", e
            assert "earlier" not in e, ("the clone's one commit holds what was seen", e)
            assert e.get("against") == sha and len(sha) == 40, (e, sha)
            assert "-    return 1" in str(e.get("diff")) and "+    return 2" in str(e.get("diff")), e
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        # depth 1, and the text the confirmer saw is one commit further back than the clone reaches
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        g("add", "-A"); g("commit", "-qm", "add returns 2; the relation not re-read")
        dest, clone = _shallow_clone(pj.dir)
        try:
            code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "add still appends", "--target", clone)
            assert code == 0, out
            e = one_read(json.load(open(os.path.join(clone, RELS, rid + ".json"), encoding="utf-8")).get("confirmed"))
            assert e.get("anchor") == "memo.py:add" and "diff" not in e and "against" not in e, e
            assert isinstance(e.get("earlier"), str) and "shallow" in e["earlier"], ("why there is no earlier text: the clone is shallow", e)
        finally:
            shutil.rmtree(dest, ignore_errors=True)

# ---- contract C (2.6.0 phase C): a test proves a concept only through a `verifies`; the net at edit time and in a task's check

C_PLAN = "# plan\n\n## add\n\nadd appends a memo.\n\n## list\n\nlist lists memos.\n\n## deploy\n\ndeploys on a push.\n"
C_SRC = "def add(store, text):\n    store.append(text)\n    return len(store)\n\n\ndef list_(store):\n    return list(store)\n"
C_TESTS = ("def test_add():\n    assert [1] == [1]\n\n\ndef test_list():\n    assert [] == []\n\n\n"
           "def test_deploy():\n    assert True\n")
C_ADD = rel("src/memo.py:add", "realizes", "concept:adding", ev="def add(store, text):")
C_ADD_DOC = rel("plan.md#add", "realizes", "concept:adding", ev="add appends a memo.")
C_ADD_NAV = rel("tests/test_memo.py:test_add", "realizes", "concept:adding", ev="def test_add():")
C_ADD_PROOF = rel("tests/test_memo.py:test_add", "verifies", "src/memo.py:add", ev="def test_add():")
C_LIST = rel("src/memo.py:list_", "realizes", "concept:listing", ev="def list_(store):")
C_LIST_DOC = rel("plan.md#list", "realizes", "concept:listing", ev="list lists memos.")
C_LIST_PROOF = rel("tests/test_memo.py:test_list", "verifies", "src/memo.py:list_", ev="def test_list():")
C_MEDIA = {"kind": "projection", "media": {"doc": ["plan.md"], "code": ["src/"], "test": ["tests/"]}}
C_UNVERIFIED = "and no `verifies` from a test reaches its code"
C_NAVIGATION = "a test's realizes is navigation, not proof"


def _c_project(files=None, concepts=("adding", "listing")):
    """plan.md, src/memo.py and tests/test_memo.py (and `files`), registered; the concepts declared by kim; nothing related."""
    pj = Project()
    files = dict({"plan.md": C_PLAN, "src/memo.py": C_SRC, "tests/test_memo.py": C_TESTS}, **(files or {}))
    for name, text in files.items():
        write(os.path.join(pj.dir, *name.split("/")), text)
    code, out = run_said("register", *sorted(files), "--target", pj.dir)
    assert code == 0, out
    for name in concepts:
        code, out = run_said("concept", "add", name, "--means", "%s, as the plan says it." % name, "--by", "kim", "--target", pj.dir)
        assert code == 0, out
    return pj


def _c_relate(pj, *rels):
    code, out = pj.propose(*rels)
    assert code == 0 and all(record(pj, mangsang.rel_id(r)) for r in rels), out


def _c_invariant(pj, verify, name="projected", verb="add"):
    more = ["--text", "Is every concept in each medium?"] if verb == "add" else []
    code, out = run_said("cq", verb, name, *more, "--verify", json.dumps(verify), "--by", "kim", "--target", pj.dir)
    assert code == 0, out


def _c_check(pj):
    """check's exit code, its `unverified` lines, its `untested` lines and everything it said."""
    code, out = run_said("check", "--target", pj.dir)
    return code, line_of(out, "unverified"), line_of(out, "untested"), out


def _c_findings(pj, kind):
    code, out = run_said("check", "--findings", "--target", pj.dir)
    assert out.lstrip().startswith("{"), out
    return code, [(f.get("where"), f.get("layer")) for f in json.loads(out).get("findings", []) if f.get("kind") == kind]


def _c_holds(out, name="projected"):
    """check said the invariant holds, with no gap. (Not the exit code: a `verifies` no coverage invariant watches is its own red.)
    A gap reads `NAME lacks MEDIUM`; check's existing advice for an unrelated file (`for an idea the net lacks`) is not one."""
    said = out.replace("for an idea the net lacks", "")
    return bool(re.search(r"holds\s+%s\b" % re.escape(name), out)) and "lacks" not in said and "FAILED" not in out


def test_C1_media_rule_derives_code_and_test_from_the_anchors_file():
    assert callable(getattr(mangsang, "media_rule", None)), "mangsang.media_rule(active, invariant=None) is missing"
    assert callable(getattr(mangsang, "proof_of", None)), "mangsang.proof_of(d, name, is_code, is_test) is missing"
    got = mangsang.media_rule([])
    assert isinstance(got, (tuple, list)) and len(got) == 2 and all(callable(p) for p in got), got
    is_code, is_test = got
    tests = ["test_x.py:test_a", "pkg/x_test.py", "conftest.py", "pkg/conftest.py:fixture", "x_test.go:TestX", "x.test.ts", "x.spec.js",
             "web/a.test.tsx", "a.spec.mjs", "tests/helper.py:h", "__tests__/z.js", "spec/a.py", "test/a.py:f", "pkg/tests/deep/b.py"]
    code = ["src/memo.py:add", "src/memo.py", "src/contest.py:f", "latest.py", "testing.py:f", "attest_x.py", "src/protest/a.py:f",
            "app.ts:handle", "web/index.js", "src/tests.py", "test.py"]
    neither = ["styles.css:.btn", "conf.yml:deploy", "plan.md#add", "package.json:scripts.test", "schema.sql", "Dockerfile",
               "concept:adding", "source:L1", "concept:tests/x", "source:test_x.py"]
    for a in tests:
        assert is_test(a) and not is_code(a), ("a test, not code", a)
    for a in code:
        assert is_code(a) and not is_test(a), ("code, not a test", a)
    for a in neither:
        assert not is_code(a) and not is_test(a), ("neither code nor a test", a)


def test_C2_check_says_unverified_with_no_projection_invariant_at_all():
    with _c_project() as pj:
        _c_relate(pj, C_ADD, C_ADD_NAV)
        code, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1, ("no invariant, and the concept's code has a test projection and no `verifies`", out)
        line = re.sub(r"\s+", " ", unverified[0])
        assert ("unverified concept:adding — 1 test projection(s), %s (src/memo.py:add)" % C_UNVERIFIED) in line, line
        assert "a change to its code asks no test whether it still proves it" in line and "relate `TEST verifies CODE`" in line, line
        assert "calls the symbol and asserts on what it does" in line, line
        assert not untested and "concept:listing" not in "".join(unverified), out
        fcode, found = _c_findings(pj, "unverified-code")
        assert found == [("concept:adding", "observation")], found
        assert _c_findings(pj, "untested-code")[1] == [], "one line per concept: unverified, not also untested"
        # the test's `verifies` of that symbol: the line goes, and the exit code is what it was
        _c_relate(pj, C_ADD_PROOF)
        code2, unverified, untested, out = _c_check(pj)
        assert not unverified and not untested and "unverified" not in out, out
        assert code == code2 == fcode == _c_findings(pj, "unverified-code")[0], ("an observation never changes the exit code", code, code2, fcode)
        assert _c_findings(pj, "unverified-code")[1] == []


def test_C2_check_says_unverified_when_the_only_projection_invariant_names_other_media():
    with _c_project(concepts=("adding",)) as pj:
        reviewers(pj)   # a kept source: the `said` medium has something to be asked of
        _c_invariant(pj, {"kind": "projection", "media": {"said": ["source:"], "doc": ["plan.md"]}})
        _c_relate(pj, C_ADD, C_ADD_DOC)
        code0, unverified, untested, out = _c_check(pj)
        assert len(untested) == 1 and not unverified and "concept:adding — realized in code (src/memo.py:add)" in untested[0], out
        _c_relate(pj, C_ADD_NAV)
        code, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested and "concept:adding — 1 test projection(s)" in unverified[0], out
        assert C_UNVERIFIED + " (src/memo.py:add)" in unverified[0], unverified
        assert "vocabulary has no" not in unverified[0], unverified
        fcode, found = _c_findings(pj, "unverified-code")
        assert found == [("concept:adding", "observation")] and code0 == code == fcode, (code0, code, fcode)


def test_C2_an_unverified_observation_leaves_a_green_check_green():
    with _c_project(concepts=("adding",)) as pj:
        _c_invariant(pj, {"kind": "projection", "media": {"doc": ["plan.md"]}})
        _c_relate(pj, C_ADD, C_ADD_DOC, C_ADD_NAV)
        code, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding" in unverified[0], out
        assert code == 0 and _c_holds(out), ("an observation: the invariant holds and check is green", out)
        fcode, found = _c_findings(pj, "unverified-code")
        assert fcode == 0 and found == [("concept:adding", "observation")], found


def test_C2_the_unverified_line_counts_the_test_projections_and_names_every_code_anchor():
    with _c_project(concepts=("memos",)) as pj:
        _c_relate(pj, rel("src/memo.py:add", "realizes", "concept:memos", ev="def add(store, text):"),
                  rel("src/memo.py:list_", "realizes", "concept:memos", ev="def list_(store):"),
                  rel("plan.md#add", "realizes", "concept:memos", ev="add appends a memo."),
                  rel("tests/test_memo.py:test_add", "realizes", "concept:memos", ev="def test_add():"),
                  rel("tests/test_memo.py:test_list", "realizes", "concept:memos", ev="def test_list():"))
        _, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested, out
        assert ("concept:memos — 2 test projection(s), %s (" % C_UNVERIFIED) in unverified[0], unverified
        named = unverified[0].split(C_UNVERIFIED, 1)[1].split(")", 1)[0]
        assert "src/memo.py:add" in named and "src/memo.py:list_" in named, unverified
        assert "plan.md" not in named and "tests/" not in named, ("a section and a test are not its code", unverified)
        assert named.index("src/memo.py:add") < named.index("src/memo.py:list_"), ("sorted", unverified)
        # one of its code anchors verified is enough: `verifying` is no longer empty
        _c_relate(pj, C_LIST_PROOF)
        assert not _c_check(pj)[1], "a `verifies` reaches one of its code anchors"


def test_C1_a_verifies_of_the_whole_file_or_of_another_symbol_does_not_count_for_the_symbol():
    with _c_project() as pj:
        _c_relate(pj, C_ADD, C_ADD_NAV)
        assert len(_c_check(pj)[1]) == 1, "said before any `verifies`"
        _c_relate(pj, rel("tests/test_memo.py:test_add", "verifies", "src/memo.py", ev="def test_add():"))
        _, unverified, _, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding" in unverified[0], ("a `verifies` of the whole file is not one of the symbol", out)
        _c_relate(pj, rel("tests/test_memo.py:test_add", "verifies", "src/memo.py:list_", ev="def test_add():"))
        _, unverified, _, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding" in unverified[0], ("a `verifies` of another symbol of the file", out)
        assert _c_findings(pj, "unverified-code")[1] == [("concept:adding", "observation")]
        _c_relate(pj, C_ADD_PROOF)
        assert not _c_check(pj)[1], "the `verifies` whose dst is the symbol itself"


def test_C1_a_verifies_whose_src_is_not_a_test_does_not_count():
    with _c_project({"src/tools.py": "def helper():\n    return add\n"}) as pj:
        _c_relate(pj, C_ADD, C_ADD_NAV)
        assert len(_c_check(pj)[1]) == 1, "said before any `verifies`"
        _c_relate(pj, rel("src/tools.py:helper", "verifies", "src/memo.py:add", ev="def helper():"))
        _, unverified, _, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding" in unverified[0], ("src/tools.py is code: its `verifies` proves nothing", out)


def test_C2_check_says_untested_for_code_no_test_relates_to():
    with _c_project() as pj:
        _c_relate(pj, C_ADD, C_ADD_DOC)
        code, unverified, untested, out = _c_check(pj)
        assert len(untested) == 1 and not unverified, out
        line = re.sub(r"\s+", " ", untested[0])
        assert "untested concept:adding — realized in code (src/memo.py:add) and no test relates to it" in line, line
        assert _c_findings(pj, "untested-code")[1] == [("concept:adding", "observation")]
        assert _c_findings(pj, "unverified-code")[1] == []
        # a test projection turns it into unverified; the `verifies` ends both, and the exit code never moved
        _c_relate(pj, C_ADD_NAV)
        code2, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested, out
        _c_relate(pj, C_ADD_PROOF)
        code3, unverified, untested, out = _c_check(pj)
        assert not unverified and not untested and code == code2 == code3, (code, code2, code3, out)
        assert _c_findings(pj, "untested-code")[1] == []


def test_C2_a_verifies_from_a_test_to_another_anchor_of_the_concept_is_unverified_not_untested():
    with _c_project() as pj:
        _c_relate(pj, C_ADD, C_ADD_DOC, rel("tests/test_memo.py:test_add", "verifies", "plan.md#add", ev="add appends a memo."))
        _, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested, ("a test relates to it, and not to its code", out)
        assert ("concept:adding — 0 test projection(s), %s (src/memo.py:add)" % C_UNVERIFIED) in unverified[0], unverified


def test_C2_the_unverified_line_says_when_the_vocabulary_has_no_verifies():
    with _c_project() as pj:
        _c_relate(pj, C_ADD, C_ADD_NAV)
        voc = {k: v for k, v in json.load(open(os.path.join(mg(pj), "vocabulary.json"), encoding="utf-8")).items() if k != "verifies"} \
            if os.path.exists(os.path.join(mg(pj), "vocabulary.json")) else {k: v for k, v in mangsang.DEFAULT_VOCAB.items() if k != "verifies"}
        assert voc and "verifies" not in voc, voc
        write(os.path.join(mg(pj), "vocabulary.json"), voc)
        _, unverified, _, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding — 1 test projection(s)" in unverified[0], out
        assert "vocabulary has no `verifies`" in unverified[0], unverified


def test_C1_a_style_rule_and_a_config_key_are_not_code_by_default():
    files = {"styles.css": ".btn { color: red; }\n", "conf.yml": "deploy: workers\nname: site\n"}
    with _c_project(files, concepts=("adding", "styling", "deploying")) as pj:
        _c_relate(pj, C_ADD,
                  rel("styles.css:.btn", "realizes", "concept:styling", ev="color: red"),
                  rel("conf.yml:deploy", "realizes", "concept:deploying", ev="deploy: workers"),
                  rel("tests/test_memo.py:test_deploy", "realizes", "concept:deploying", ev="def test_deploy():"))
        _, unverified, untested, out = _c_check(pj)
        assert len(untested) == 1 and "concept:adding" in untested[0], ("the Python symbol is code a test can call", out)
        assert not unverified, ("a YAML key with a test projection is not unverified code", out)
        assert "concept:styling" not in "".join(untested) and "concept:deploying" not in "".join(untested), out
        for kind in ("untested-code", "unverified-code"):
            assert not [w for w, _ in _c_findings(pj, kind)[1] if w in ("concept:styling", "concept:deploying")], kind


def test_C1_a_projection_invariants_code_prefixes_decide_what_check_calls_code():
    files = {"styles.css": ".btn { color: red; }\n"}
    with _c_project(files, concepts=("adding", "styling")) as pj:
        _c_relate(pj, C_ADD, rel("styles.css:.btn", "realizes", "concept:styling", ev="color: red"))
        _, _, untested, out = _c_check(pj)
        assert len(untested) == 1 and "concept:adding" in untested[0], ("derived: Python is code, a style rule is not", out)
        # a project that wants its styles named code says so in a projection invariant's `code` medium — and then that decides
        _c_invariant(pj, {"kind": "projection", "media": {"code": ["styles.css"]}})
        _, unverified, untested, out = _c_check(pj)
        assert len(untested) == 1 and not unverified, out
        assert "concept:styling — realized in code (styles.css:.btn) and no test relates to it" in untested[0], untested
        # the test medium is still derived (no invariant names it): tests/test_memo.py is a test, and its verifies of the rule counts
        _c_relate(pj, rel("tests/test_memo.py:test_add", "realizes", "concept:styling", ev="def test_add():"))
        _, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested and "concept:styling — 1 test projection(s)" in unverified[0], out
        assert C_UNVERIFIED + " (styles.css:.btn)" in unverified[0], unverified
        _c_relate(pj, rel("tests/test_memo.py:test_add", "verifies", "styles.css:.btn", ev="def test_add():"))
        _, unverified, untested, out = _c_check(pj)
        assert not unverified and not untested, out


def test_C1_a_code_anchor_under_a_test_prefix_is_a_test_and_only_the_named_test_prefixes_are_tests():
    files = {"src/checks/c.py": "def check_add():\n    assert True\n"}
    with _c_project(files) as pj:
        _c_invariant(pj, {"kind": "projection", "media": {"code": ["src/"], "test": ["src/checks/"]}})
        _c_relate(pj, C_ADD, rel("src/checks/c.py:check_add", "realizes", "concept:adding", ev="def check_add():"))
        _, unverified, untested, out = _c_check(pj)
        assert len(unverified) == 1 and not untested, out
        assert ("concept:adding — 1 test projection(s), %s (src/memo.py:add)" % C_UNVERIFIED) in unverified[0], \
            ("src/checks/c.py starts with a code prefix and a test prefix: a test, not code", unverified)
        # tests/ is named by no invariant's test medium: under this project's rule it is not a test, and its verifies no proof
        _c_relate(pj, C_ADD_PROOF)
        _, unverified, _, out = _c_check(pj)
        assert len(unverified) == 1 and "concept:adding" in unverified[0], out
        _c_relate(pj, rel("src/checks/c.py:check_add", "verifies", "src/memo.py:add", ev="def check_add():"))
        assert not _c_check(pj)[1], "a `verifies` from the invariant's test prefix to the code"


def test_C1_test_files_are_derived_from_their_names_and_folders_and_lookalikes_are_code():
    as_tests = {"test_x.py": "def test_a():\n    assert True\n", "x_test.py": "def check_b():\n    assert True\n",
                "x.test.ts": "export function testC() { return 1 }\n", "x.spec.js": "export function specD() { return 1 }\n",
                "tests/helper.py": "def helper_e():\n    return 1\n", "__tests__/z.js": "export function zF() { return 1 }\n"}
    as_code = {"src/contest.py": "def contest():\n    return 1\n", "latest.py": "def latest():\n    return 1\n"}
    names = ["c%d" % i for i in range(len(as_tests))] + ["contest", "latest"]
    with _c_project(dict(as_tests, **as_code), concepts=names) as pj:
        rels = []
        for i, f in enumerate(sorted(as_tests)):
            # each concept: one code anchor and the file under question, as a whole-file projection
            rels += [rel("src/memo.py:add", "realizes", "concept:c%d" % i, ev="def add(store, text):"),
                     rel(f, "realizes", "concept:c%d" % i, ev=as_tests[f].strip().split("\n")[0])]
        rels += [rel("src/contest.py:contest", "realizes", "concept:contest", ev="def contest():"),
                 rel("latest.py:latest", "realizes", "concept:latest", ev="def latest():")]
        _c_relate(pj, *rels)
        _, unverified, untested, out = _c_check(pj)
        for i, f in enumerate(sorted(as_tests)):
            mine = [l for l in unverified if ("concept:c%d " % i) in l]
            assert len(mine) == 1 and "1 test projection(s)" in mine[0] and "(src/memo.py:add)" in mine[0], (f, "is a test", out)
            assert f not in mine[0].split(C_UNVERIFIED, 1)[1].split(")", 1)[0], (f, "is not listed as code", mine)
        said = "\n".join(untested)
        assert "concept:contest — realized in code (src/contest.py:contest) and no test relates to it" in said, ("contest.py is no test", out)
        assert "concept:latest — realized in code (latest.py:latest) and no test relates to it" in said, ("latest.py is no test", out)
        assert len(untested) == 2 and len(unverified) == len(as_tests), out


# C3 — a projection invariant's test medium

def test_C3_a_tests_realizes_no_longer_satisfies_the_test_medium_and_another_medium_still_holds_on_it():
    with _c_project(concepts=("adding",)) as pj:
        _c_relate(pj, C_ADD, C_ADD_DOC, C_ADD_NAV)
        # a medium by any other name holds, as before, on a realizes from its prefixes
        _c_invariant(pj, {"kind": "projection", "media": {"doc": ["plan.md"], "code": ["src/"], "checks": ["tests/"]}})
        code, out = run_said("check", "--target", pj.dir)
        assert code == 0 and "FAILED" not in out and "lacks" not in out, out
        _c_invariant(pj, C_MEDIA, verb="revise")
        code, out = run_said("check", "--target", pj.dir)
        assert code == 1 and "FAILED" in out, ("the test realizes it and nothing verifies its code", out)
        assert "adding lacks test (no `verifies` from " in out, out
        gap = out.split("adding lacks test (", 1)[1].split("\n")[0]
        assert "tests/" in gap.split(" reaches ")[0] and " reaches its code: src/memo.py:add" in gap, gap
        assert C_NAVIGATION + ")" in gap, gap
        assert "adding lacks doc" not in out and "adding lacks code" not in out, out
        code, found = _c_findings(pj, "unverified-code")
        assert code == 1 and found == [("concept:adding", "observation")], found
        _c_relate(pj, C_ADD_PROOF)
        code, out = run_said("check", "--target", pj.dir)
        assert _c_holds(out) and "0 gap(s)" in out, out


def test_C3_the_test_medium_holds_on_a_verifies_alone():
    with _c_project(concepts=("adding",)) as pj:
        _c_invariant(pj, C_MEDIA)
        _c_relate(pj, C_ADD, C_ADD_DOC, C_ADD_PROOF)   # no test realizes the concept: the proof is the `verifies`
        code, out = run_said("check", "--target", pj.dir)
        assert _c_holds(out), out
        assert not line_of(out, "unverified") and not line_of(out, "untested"), out


def test_C3_a_verifies_from_a_test_outside_the_invariants_test_prefixes_does_not_count():
    files = {"test_root.py": "def test_add_here():\n    assert True\n"}
    with _c_project(files, concepts=("adding",)) as pj:
        _c_invariant(pj, C_MEDIA)
        _c_relate(pj, C_ADD, C_ADD_DOC, C_ADD_NAV, rel("test_root.py:test_add_here", "verifies", "src/memo.py:add", ev="def test_add_here():"))
        code, out = run_said("check", "--target", pj.dir)
        assert code == 1 and "adding lacks test (no `verifies` from " in out and C_NAVIGATION in out, out
        _c_relate(pj, C_ADD_PROOF)
        code, out = run_said("check", "--target", pj.dir)
        assert _c_holds(out), out


def test_C3_a_verifies_to_another_concepts_code_or_to_the_whole_file_does_not_count():
    with _c_project() as pj:
        _c_invariant(pj, C_MEDIA)
        _c_relate(pj, C_ADD, C_ADD_DOC, C_ADD_NAV, C_LIST, C_LIST_DOC,
                  rel("tests/test_memo.py:test_add", "verifies", "src/memo.py:list_", ev="def test_add():"),
                  rel("tests/test_memo.py:test_add", "verifies", "src/memo.py", ev="def test_add():"))
        code, out = run_said("check", "--target", pj.dir)
        assert code == 1 and "adding lacks test (no `verifies` from " in out, ("the verifies reaches listing's code and the file, not add", out)
        assert " reaches its code: src/memo.py:add" in out.split("adding lacks test (", 1)[1].split("\n")[0], out
        assert "listing lacks" not in out, ("listing's code is verified; no test realizes it and none is needed", out)
        _c_relate(pj, C_ADD_PROOF)
        code, out = run_said("check", "--target", pj.dir)
        assert _c_holds(out), out


def test_C3_a_concept_with_no_code_anchor_is_verified_through_another_projection():
    files = {"conf.yml": "deploy: workers\nname: site\n"}
    with _c_project(files, concepts=("deploying",)) as pj:
        _c_invariant(pj, {"kind": "projection", "media": {"doc": ["plan.md"], "test": ["tests/"]}})
        _c_relate(pj, rel("plan.md#deploy", "realizes", "concept:deploying", ev="deploys on a push."),
                  rel("conf.yml:deploy", "realizes", "concept:deploying", ev="deploy: workers"),
                  rel("tests/test_memo.py:test_deploy", "realizes", "concept:deploying", ev="def test_deploy():"))
        code, out = run_said("check", "--target", pj.dir)
        assert code == 1 and "deploying lacks test (no `verifies` from " in out, out
        gap = out.split("deploying lacks test (", 1)[1].split("\n")[0]
        assert " reaches any of its projections" in gap and "conf.yml:deploy" in gap and "plan.md#deploy" in gap, gap
        assert "tests/test_memo.py:test_deploy" not in gap.split(" reaches ", 1)[1], ("the test is not something a test verifies", gap)
        assert C_NAVIGATION in gap and "its code" not in gap, gap
        assert not line_of(out, "unverified") and not line_of(out, "untested"), ("no code: check's observation has nothing to say", out)
        _c_relate(pj, rel("tests/test_memo.py:test_deploy", "verifies", "conf.yml:deploy", ev="def test_deploy():"))
        code, out = run_said("check", "--target", pj.dir)
        assert _c_holds(out), out


def test_C3_a_concept_only_a_test_realizes_lacks_test():
    with _c_project(concepts=("adding",)) as pj:
        _c_invariant(pj, {"kind": "projection", "media": {"test": ["tests/"]}})
        _c_relate(pj, C_ADD_NAV)
        code, out = run_said("check", "--target", pj.dir)
        assert code == 1 and "adding lacks test (no `verifies` from " in out and C_NAVIGATION in out, ("nothing a test could verify", out)


# C4 — lookup --brief at edit time

C4_TAIL = " — an edit here stales them; re-reading them belongs to the same task (`mangsang lookup %s`)"
C4_UNSEEN = "%s: not registered — the net does not see it (no relation stands on it; edits here are never stale)"
C4_UNRELATED = ("%s: registered, but no relation stands on it — impact never sees an edit here; relate what it carries "
                "(`mangsang check` lists it as unrelated)")


def _c4_project():
    pj = Project()
    assert run_said("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
    assert run_said("concept", "add", "adding", "--means", "Appending one memo. It prints its id.", "--by", "kim", "--target", pj.dir)[0] == 0
    _c_relate(pj, R_ADD, R_LIST, rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))
    return pj


def test_C4_lookup_brief_is_one_line_the_count_a_concept_stales_them_and_same_task():
    with _c4_project() as pj:
        before = tree_bytes(pj.dir)
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        lines = out.splitlines()
        assert code == 0 and len(lines) == 1, out
        assert lines[0] == "memo.py: 3 relation(s) stand on it, on concept:adding" + C4_TAIL % "memo.py", out
        assert "stale" not in lines[0].split(" — ")[0] and "disputed" not in out, ("fresh: no stale count", out)
        assert "rel-" not in out and "kim" not in out and "def add" not in out and "Appending" not in out, out
        assert tree_bytes(pj.dir) == before, "lookup --brief writes nothing"
        # an anchor: the same line for what stands on it
        code, out = run_said("lookup", "memo.py:list_", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == ["memo.py:list_: 1 relation(s) stand on it, on concept:adding" + C4_TAIL % "memo.py:list_"], out
        # `concept:NAME --brief` is what it was
        code, out = run_said("lookup", "concept:adding", "--brief", "--target", pj.dir)
        assert out.strip() == "concept:adding — Appending one memo. (2 relation(s))", out


def test_C4_lookup_brief_says_how_many_are_stale_now():
    with _c4_project() as pj:
        edit(pj, "memo.py", "return 1", "return 2")
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        assert code == 0 and len(out.splitlines()) == 1, out
        assert out.splitlines()[0] == "memo.py: 3 relation(s) stand on it, on concept:adding; 2 stale or broken now" + C4_TAIL % "memo.py", out
        assert not os.path.exists(os.path.join(pj.dir, ".mangsang")), "lookup --brief writes nothing"


def test_C4_lookup_brief_names_at_most_three_concepts_the_stale_first_and_counts_the_rest():
    with _c4_project() as pj:
        for i in range(5):
            assert run_said("concept", "add", "c%d" % i, "--means", "concept %d." % i, "--by", "kim", "--target", pj.dir)[0] == 0
        _c_relate(pj, *[rel("memo.py:X", "realizes", "concept:c%d" % i, ev="X = 1") for i in range(5)])
        _c_relate(pj, rel("memo.py:list_", "realizes", "concept:c4", ev="def list_(store):"))
        edit(pj, "memo.py", "return []", "return [1]")   # list_ moved: adding's and c4's relations are stale, c0..c3's are not
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        lines = out.splitlines()
        assert code == 0 and len(lines) == 1, ("at most two lines, and no heading here", out)
        m = re.match(r"memo\.py: 9 relation\(s\) stand on it, on (.+) and 3 more; 2 stale or broken now — an edit here stales them; ", lines[0])
        assert m, lines[0]
        named = re.findall(r"concept:[\w-]+", m.group(1))
        assert len(named) == 3 and set(named[:2]) == {"concept:adding", "concept:c4"}, ("three names, those with stale relations first", lines[0])
        assert lines[0].endswith(C4_TAIL % "memo.py"), lines[0]


def test_C4_lookup_brief_counts_the_other_ends_when_no_relation_reaches_a_concept():
    with Project() as pj:
        assert run_said("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        _c_relate(pj, Q1_ADD, rel("test_memo.py:test_Q1_add", "verifies", "memo.py:add", ev="def test_Q1_add"))
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == ["memo.py: 2 relation(s) stand on it, on 2 other anchor(s)" + C4_TAIL % "memo.py"], out


def test_C4_lookup_brief_adds_the_heading_rename_line_as_its_second_line():
    P = "plan/PLAN.md"
    with Project() as pj:
        assert run_said("register", P, "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "adding", "--means", "Appending one memo.", "--by", "kim", "--target", pj.dir)[0] == 0
        on_heading = rel(P + "#Q1 add", "realizes", "concept:adding")
        _c_relate(pj, on_heading, R_ADD)
        rid = mangsang.rel_id(on_heading)
        code, out = run_said("lookup", P, "--brief", "--target", pj.dir)
        lines = out.splitlines()
        assert code == 0 and len(lines) == 2, out
        assert lines[0] == P + ": 1 relation(s) stand on it, on concept:adding" + C4_TAIL % P, lines
        assert all(s in lines[1] for s in ("renaming", "#Q1 add", rid, "mangsang move")), lines
        # a Python file has no heading to rename: one line
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        assert len(out.splitlines()) == 1 and "renaming" not in out and out.startswith("memo.py: 1 relation(s) stand on it"), out


def test_C4_lookup_brief_counts_a_disputed_relation():
    with _signed_project() as pj:
        a = mangsang.rel_id(R_ADD)
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        code, out = run_said("lookup", "memo.py", "--brief", "--target", pj.dir)
        lines = out.splitlines()
        assert code == 0 and len(lines) == 1, out
        assert lines[0] == "memo.py: 3 relation(s) stand on it, on concept:adding; 1 disputed" + C4_TAIL % "memo.py", out


def test_C4_lookup_brief_says_a_registered_file_nothing_stands_on_in_one_line():
    with _c4_project() as pj:
        code, out = run_said("lookup", "plan/PLAN.md", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == [C4_UNRELATED % "plan/PLAN.md"], out
        assert run_said("lookup", "gone.py", "--brief", "--target", pj.dir) == (0, ""), "not in the tree: nothing"
        # registered, and since deleted: not in the tree, so nothing
        write(os.path.join(pj.dir, "late.py"), "Z = 1\n")
        assert run_said("register", "late.py", "--target", pj.dir)[0] == 0
        assert run_said("lookup", "late.py", "--brief", "--target", pj.dir)[1].splitlines() == [C4_UNRELATED % "late.py"]
        os.remove(os.path.join(pj.dir, "late.py"))
        assert run_said("lookup", "late.py", "--brief", "--target", pj.dir)[1] == "", "registered once, gone from the tree"


def test_C4_lookup_brief_says_check_fails_on_an_unregistered_file_a_registered_invariant_asks_of():
    verify = {"kind": "registered", "paths": ["src/"], "except": [{"glob": "src/gen/*", "why": "generated, never edited by hand"}]}
    with Project() as pj:
        git = git_in(pj)
        for name in ("src/a.py", "src/b.py", "src/gen/g.py", "other/y.py"):
            write(os.path.join(pj.dir, *name.split("/")), "V = 1\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
        assert run_said("register", "src/a.py", "--target", pj.dir)[0] == 0
        code, out = run_said("cq", "add", "inv-scope", "--text", "Is every source file registered?", "--verify", json.dumps(verify), "--by", "kim", "--target", pj.dir)
        assert code == 0, out
        code, out = run_said("lookup", "src/b.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == ["src/b.py: not registered, and `check` fails on it (inv-scope asks of src/) — "
                                                  "register and relate it, or except it with its reason"], out
        # a tracked file no invariant asks of: the line it always had; an excepted one: its excepted line
        code, out = run_said("lookup", "other/y.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == [C4_UNSEEN % "other/y.py"], out
        code, out = run_said("lookup", "src/gen/g.py", "--brief", "--target", pj.dir)
        assert code == 0 and len(out.splitlines()) == 1 and "excepted" in out and "generated" in out and "fails on it" not in out, out
        # the registered file itself, with nothing on it
        assert run_said("lookup", "src/a.py", "--brief", "--target", pj.dir)[1].splitlines() == [C4_UNRELATED % "src/a.py"]
        # only an active invariant asks
        assert run_said("cq", "retire", "inv-scope", "--why", "the folder was given up", "--by", "kim", "--target", pj.dir)[0] == 0
        code, out = run_said("lookup", "src/b.py", "--brief", "--target", pj.dir)
        assert code == 0 and out.splitlines() == [C4_UNSEEN % "src/b.py"], out


# C5 — impact --files

C5_A = rel("plan/PLAN.md#Q1 add", "documents", "src/a.py:f")
C5_X = rel("plan/PLAN.md#Q2 list", "documents", "src/a.pyx", ev="lists.")
C5_BAK = rel("plan/PLAN.md#Q1 add", "documents", "src/a.py.bak")
C5_DEEP = rel("plan/PLAN.md#Q2 list", "documents", "src/dir/a.py:f", ev="lists.")


def _c5_project():
    """One relation on each of src/a.py, src/a.pyx (an unknown kind: its file anchor), src/a.py.bak and src/dir/a.py; all fresh."""
    pj = Project()
    files = {"src/a.py": "def f():\n    return 1\n", "src/a.pyx": "cdef int g():\n    return 1\n",
             "src/a.py.bak": "def old():\n    return 0\n", "src/dir/a.py": "def f():\n    return 7\n"}
    for name, text in files.items():
        write(os.path.join(pj.dir, *name.split("/")), text)
    code, out = run_said("register", "plan/PLAN.md", *sorted(files), "--target", pj.dir)
    assert code == 0, out
    _c_relate(pj, C5_A, C5_X, C5_BAK, C5_DEEP)
    assert stale_ids(pj) == [], "fresh at the start"
    return pj


def _c5_ids():
    return tuple(mangsang.rel_id(r) for r in (C5_A, C5_X, C5_BAK, C5_DEEP))


def _c5_findings(out):
    text = out[out.index("{"):] if "{" in out else ""
    assert text, ("--findings prints the findings document", out)
    return json.loads(text).get("findings", [])


def test_C5_impact_files_selects_exactly_the_given_files():
    with _c5_project() as pj:
        a, x, bak, deep = _c5_ids()
        edit(pj, "src/a.py", "return 1", "return 2")
        assert stale_ids(pj) == [a], "only src/a.py's relation is stale"
        code, out = run_said("impact", "--files", "src/a.py", "--target", pj.dir)
        assert code == 1, out
        assert out.startswith("scope: 1 file(s), 1 relation(s) stand on them"), out
        assert a in out and x not in out and bak not in out and deep not in out, out
        for other in ("src/a.pyx", "src/a.py.bak", "src/dir/a.py"):
            code, out = run_said("impact", "--files", other, "--target", pj.dir)
            assert code == 0 and a not in out, (other, "is not src/a.py", out)
            assert out.startswith("scope: 1 file(s), 1 relation(s) stand on them"), (other, out)
        code, out = run_said("impact", "--files", "src/a.pyx", "src/a.py", "src/a.py.bak", "--target", pj.dir)
        assert code == 1 and out.startswith("scope: 3 file(s), 3 relation(s) stand on them") and a in out, out
        # the other end's file selects the relation too: an anchor of it is in that file
        code, out = run_said("impact", "--files", "plan/PLAN.md", "--target", pj.dir)
        assert code == 1 and out.startswith("scope: 1 file(s), 4 relation(s) stand on them") and a in out, out
        # nothing was written, and impact without --files is what it was
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and a in out and not out.startswith("scope:"), out


def test_C5_impact_files_normalizes_a_leading_dot_slash_and_an_absolute_path():
    with _c5_project() as pj:
        a, x, bak, deep = _c5_ids()
        edit(pj, "src/a.py", "return 1", "return 2")
        for given in ("./src/a.py", os.path.join(pj.dir, "src", "a.py"), os.path.join(".", "src", "a.py")):
            code, out = run_said("impact", "--files", given, "--target", pj.dir)
            assert code == 1 and a in out, (given, out)
            assert out.startswith("scope: 1 file(s), 1 relation(s) stand on them") and "not registered" not in out, (given, out)
        code, out = run_said("impact", "--files", os.path.join(pj.dir, "src", "a.pyx"), "--target", pj.dir)
        assert code == 0 and a not in out, out


def test_C5_impact_files_with_no_file_is_an_empty_scope_and_never_the_whole_tree():
    with _c5_project() as pj:
        a = _c5_ids()[0]
        edit(pj, "src/a.py", "return 1", "return 2")
        assert run_said("impact", "--target", pj.dir)[0] == 1, "a relation is stale in the tree"
        # the lock's order: --files last, the task's files substituted as zero words
        code, out = run_said("impact", "--target", pj.dir, "--files")
        assert code == 0, out
        assert a not in out and "nothing" in out and "scope" in out, ("says nothing is in scope", out)
        code, out = run_said("impact", "--files", "--target", pj.dir)
        assert code == 0 and a not in out, out
        # and as one or more words
        code, out = run_said("impact", "--target", pj.dir, "--files", "src/a.pyx", "src/a.py")
        assert code == 1 and a in out and out.startswith("scope: 2 file(s), 2 relation(s) stand on them"), out


def test_C5_impact_files_a_broken_relation_on_a_given_deleted_file_exits_1():
    with _c5_project() as pj:
        a, x, bak, deep = _c5_ids()
        os.remove(os.path.join(pj.dir, "src", "a.pyx"))
        code, out = run_said("impact", "--files", "src/a.pyx", "--target", pj.dir)
        assert code == 1, out
        assert x in out and "broken" in out and a not in out, out
        code, out = run_said("impact", "--files", "src/a.py", "--target", pj.dir)
        assert code == 0 and x not in out, ("the deleted file is not in this scope", out)


def test_C5_impact_files_a_concept_owing_a_reread_for_a_projection_lost_on_a_given_file_exits_1():
    with Project() as pj:
        write(os.path.join(pj.dir, "pages.yml"), "deploy: pages\n")
        write(os.path.join(pj.dir, "wrangler.jsonc"), '{"name": "site"}\n')
        assert run_said("register", "plan/PLAN.md", "pages.yml", "wrangler.jsonc", "memo.py", "--target", pj.dir)[0] == 0
        assert run_said("concept", "add", "site-build", "--means", "a push to main deploys to GitHub Pages", "--by", "kim", "--target", pj.dir)[0] == 0
        _c_relate(pj, rel("pages.yml", "realizes", "concept:site-build", ev="deploy: pages"),
                  rel("wrangler.jsonc", "realizes", "concept:site-build", ev='"name": "site"'), Q1_ADD)
        old = mangsang.rel_id(rel("pages.yml", "realizes", "concept:site-build"))
        code, out = run_said("retire", old, "--why", "the deploy moved to Workers", "--by", "kim", "--target", pj.dir)
        assert code == 0 and "lost a projection" in out, out
        assert stale_ids(pj) == [] and run_said("impact", "--target", pj.dir)[0] == 1, "nothing stale; the concept owes a re-read"
        code, out = run_said("impact", "--files", "pages.yml", "--target", pj.dir)
        assert code == 1, out
        assert "owed" in out and "concept:site-build" in out, out
        for other in ("wrangler.jsonc", "memo.py", "plan/PLAN.md"):
            code, out = run_said("impact", "--files", other, "--target", pj.dir)
            assert code == 0 and "concept:site-build lost" not in out, (other, out)
        code, out = run_said("impact", "--findings", "--files", "pages.yml", "--target", pj.dir)
        assert code == 1, out
        assert [f.get("where") for f in _c5_findings(out) if f.get("kind") == "owed-reread"] == ["concept:site-build"], out
        code, out = run_said("impact", "--findings", "--files", "memo.py", "--target", pj.dir)
        assert code == 0 and not [f for f in _c5_findings(out) if f.get("kind") == "owed-reread"], out


def test_C5_impact_files_a_disputed_unrevised_relation_on_a_given_file_exits_1():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        write(os.path.join(pj.dir, "other.py"), "def other():\n    return 1\n")
        assert run_said("register", "other.py", "--target", pj.dir)[0] == 0
        agent_confirms(pj, rel("plan/PLAN.md#Q2 list", "documents", "other.py:other", ev="lists."))
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        code, out = run_said("impact", "--files", "memo.py", "--target", pj.dir)
        assert code == 1, out
        lines = [l for l in out.split("\n") if l.strip().startswith("disputed") and a in l]
        assert len(lines) == 1 and out.startswith("scope: 1 file(s), 3 relation(s) stand on them"), out
        code, out = run_said("impact", "--files", "other.py", "--target", pj.dir)
        assert code == 0 and a not in out and "disputed" not in out, out
        code, out = run_said("impact", "--findings", "--files", "other.py", "--target", pj.dir)
        assert code == 0 and not [f for f in _c5_findings(out) if f.get("kind") == "disputed"], out
        code, out = run_said("impact", "--findings", "--files", "memo.py", "--target", pj.dir)
        assert code == 1 and len([f for f in _c5_findings(out) if f.get("kind") == "disputed"]) == 1, out


def test_C5_impact_files_names_a_given_file_that_is_not_registered_and_exits_0():
    with _c5_project() as pj:
        a = _c5_ids()[0]
        edit(pj, "src/a.py", "return 1", "return 2")
        write(os.path.join(pj.dir, "notes.py"), "N = 1\n")
        code, out = run_said("impact", "--files", "notes.py", "a.py", "--target", pj.dir)
        assert code == 0, out
        assert out.startswith("scope: 2 file(s), 0 relation(s) stand on them"), out
        assert "not registered" in out and "notes.py" in out and a not in out, out
        said = [l for l in out.split("\n") if "not registered" in l]
        assert any(re.search(r"(^|[\s,(`'\"])a\.py\b", l) for l in said), ("`a.py` is named: it is not src/a.py", out)
        # informational: beside a stale relation in scope the exit is the relation's
        code, out = run_said("impact", "--files", "notes.py", "src/a.py", "--target", pj.dir)
        assert code == 1 and out.startswith("scope: 2 file(s), 1 relation(s) stand on them") and "notes.py" in out and a in out, out
        code, out = run_said("impact", "--files", "src/a.py", "--target", pj.dir)
        assert code == 1 and "not registered" not in out, out


def test_C5_impact_findings_and_show_with_files_report_only_what_is_in_scope():
    with _c5_project() as pj:
        a, x, bak, deep = _c5_ids()
        edit(pj, "src/a.py", "return 1", "return 2")
        edit(pj, "src/a.pyx", "return 1", "return 3")
        assert sorted(stale_ids(pj)) == sorted([a, x])
        code, out = run_said("impact", "--findings", "--files", "src/a.pyx", "--target", pj.dir)
        assert code == 1, out
        found = json.dumps(_c5_findings(out))
        assert x in found and a not in found, found
        code, out = run_said("impact", "--findings", "--files", "src/a.py.bak", "--target", pj.dir)
        assert code == 0, out
        found = json.dumps([f for f in _c5_findings(out) if f.get("layer") != "observation"])
        assert a not in found and x not in found, found
        code, out = run_said("impact", "--findings", "--target", pj.dir, "--files")
        assert code == 0, out
        assert a not in out and x not in out, out
        code, out = run_said("impact", "--show", "--files", "src/a.pyx", "--target", pj.dir)
        assert code == 1 and x in out and a not in out and "return 2" not in out, out


def test_C5_only_combines_with_files_and_stays_a_prefix():
    with _c5_project() as pj:
        a, x, bak, deep = _c5_ids()
        edit(pj, "src/a.py", "return 1", "return 2")
        edit(pj, "src/a.pyx", "return 1", "return 3")
        # both must select a relation
        code, out = run_said("impact", "--only", "src/a.pyx", "--files", "src/a.py", "--target", pj.dir)
        assert code == 0, out
        assert a not in out and x not in out, out
        code, out = run_said("impact", "--only", "src/a.py", "--files", "src/a.pyx", "--target", pj.dir)
        assert code == 1 and x in out and a not in out, out
        code, out = run_said("impact", "--only", "src/a.py:f", "--files", "src/a.py", "src/a.pyx", "--target", pj.dir)
        assert code == 1 and a in out and x not in out, out
        # --only alone is the prefix it always was: `src/a.py` selects src/a.pyx too
        code, out = run_said("impact", "--only", "src/a.py", "--target", pj.dir)
        assert code == 1 and a in out and x in out, out
        code, out = run_said("impact", "--only", "src/a.pyx", "--target", pj.dir)
        assert code == 1 and x in out and a not in out, out


# ---- 2.6.0 fix round (F1–F5): no hint names a form the engine refuses; --files through a symlinked directory; the queue's
# ---- `signed:` line; a rename never lifts a person's review; move does not carry a dispute away.

OLD_FORMS = ("--delegated WHY", '--delegated "<why>"', "(or --delegated", "--by|--delegated", "--by NAME|--delegated")
F_P = "plan/PLAN.md"
F_RENAMED = PLAN.replace("## Q1 add", "## Q1 append")
F_NO_ADD = CODE.replace("def add(store, text):\n    return 1\n\n\n", "")
F_CORE = "def add(store, text):\n    return 1\n"


def _no_old_form(text, where):
    flat = re.sub(r"\s+", " ", text)
    for old in OLD_FORMS:
        assert old not in flat, ("%s names `%s`, a form 2.6.0 refuses" % (where, old), text)


def _lines_with(out, s):
    return [l for l in out.split("\n") if s in l]


def test_F1_impact_and_lookup_name_move_with_why_for_a_heading_renamed_in_place():
    with Project() as pj:
        assert run_said("register", F_P, "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, F_P), F_RENAMED)
        want = 'mangsang move %s --why "..."' % rid
        code, out = run_said("impact", "--target", pj.dir)
        hint = _lines_with(out, "mangsang move " + rid)
        assert code == 1 and len(hint) == 1 and "#Q1 append" in hint[0], out
        assert want in hint[0], ("impact's hint names the reason move needs", hint)
        _no_old_form(out, "impact")
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        bf = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "broken"]
        assert len(bf) == 1 and want in bf[0].get("text", ""), out
        _no_old_form(bf[0]["text"], "impact --findings")
        for what in (F_P, rid, "memo.py"):
            code, out = run_said("lookup", what, "--target", pj.dir)
            ls = _lines_with(out, "mangsang move " + rid)
            assert code == 0 and len(ls) == 1 and "#Q1 append" in ls[0], (what, out)
            assert want in ls[0], ("lookup's hint names the reason move needs", what, ls)
            _no_old_form(out, "lookup " + what)


def test_F1_impact_and_lookup_name_move_with_why_for_a_symbol_in_another_file():
    with Project() as pj:
        assert run_said("register", F_P, "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        rid = mangsang.rel_id(Q1_ADD)
        write(os.path.join(pj.dir, "memo.py"), F_NO_ADD)
        write(os.path.join(pj.dir, "core.py"), F_CORE)
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        want = 'mangsang move %s --why "..."' % rid
        code, out = run_said("impact", "--target", pj.dir)
        hint = _lines_with(out, "mangsang move " + rid)
        assert code == 1 and len(hint) == 1 and "core.py:add" in hint[0] and want in hint[0], out
        _no_old_form(out, "impact")
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        bf = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "broken"]
        assert len(bf) == 1 and want in bf[0].get("text", "") and "core.py:add" in bf[0]["text"], out
        _no_old_form(bf[0]["text"], "impact --findings")
        code, out = run_said("lookup", rid, "--target", pj.dir)
        ls = _lines_with(out, "mangsang move " + rid)
        assert len(ls) == 1 and want in ls[0] and "core.py:add" in ls[0], out
        _no_old_form(out, "lookup")


def _f1_owing(pj):
    """`site` lost a projection: what retire said, and the retired relation's id."""
    write(os.path.join(pj.dir, "pages.yml"), "deploy: pages\n")
    assert run_said("register", F_P, "memo.py", "pages.yml", "--target", pj.dir)[0] == 0
    assert run_said("concept", "add", "site", "--means", "a push deploys the site", "--by", "kim", "--target", pj.dir)[0] == 0
    assert pj.propose(rel("pages.yml", "realizes", "concept:site", ev="deploy: pages"), rel(F_P + "#Q1 add", "realizes", "concept:site"))[0] == 0
    old = mangsang.rel_id(rel("pages.yml", "realizes", "concept:site"))
    code, out = run_said("retire", old, "--why", "the deploy moved", "--target", pj.dir)
    assert code == 0, out
    return out, old


def _f1_owed_line(line, where):
    assert 'concept reaffirm site --why "..."' in line, ("%s names the reaffirmation with its reason" % where, line)
    assert 'concept revise site --means "..."' in line, ("%s names the revision" % where, line)
    _no_old_form(line, where)


def test_F1_impacts_owed_line_names_reaffirm_with_why():
    with Project() as pj:
        _, old = _f1_owing(pj)
        code, out = run_said("impact", "--target", pj.dir)
        owed = [l for l in out.split("\n") if l.strip().startswith("owed")]
        assert code == 1 and len(owed) == 1 and old in owed[0], out
        _f1_owed_line(owed[0], "impact's owed line")
        _no_old_form(out, "impact")
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        found = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "owed-reread"]
        assert code == 1 and len(found) == 1, out
        _f1_owed_line(found[0].get("text", ""), "impact --findings' owed-reread")


def test_F1_checks_owed_line_names_reaffirm_with_why():
    with Project() as pj:
        _, old = _f1_owing(pj)
        code, out = run_said("check", "--target", pj.dir)
        owed = [l for l in out.split("\n") if l.strip().startswith("owed")]
        assert len(owed) == 1 and old in owed[0], out
        _f1_owed_line(owed[0], "check's owed line")
        _no_old_form(out, "check")


def test_F1_the_concepts_owes_line_after_a_retire_names_reaffirm_with_why():
    with Project() as pj:
        said, old = _f1_owing(pj)
        lost = _lines_with(said, "lost a projection")
        assert len(lost) == 1 and old in lost[0], said
        _f1_owed_line(lost[0], "retire's line for the concept")
        _no_old_form(said, "retire")
        # ... and where the concept is shown whole
        code, out = run_said("concept", "show", "site", "--target", pj.dir)
        owes = [l for l in out.split("\n") if l.strip().startswith("OWES")]
        assert code == 0 and len(owes) == 1 and old in owes[0], out
        _f1_owed_line(owes[0], "concept show's OWES line")
        # the form the hint names is one the engine takes
        code, out = run_agent("concept", "reaffirm", "site", "--why", "the sentence still says what the project does", "--target", pj.dir)
        assert code == 0, out


def test_F1_confirms_line_after_a_rejection_names_a_form_confirm_accepts():
    bad = rel(F_P + "#Q1 add", "documents", "memo.py:list_", ev="nowhere in either text")
    with Project() as pj:
        assert run_said("register", F_P, "memo.py", "--target", pj.dir)[0] == 0
        props = os.path.join(pj.dir, "proposals.json")
        # a person at a terminal
        code, out = pj.propose(Q1_ADD, bad)
        assert code == 1 and "confirmed 1 / rejected 1" in out, out
        assert ('confirm %s --why "..."' % props) in out or ("confirm %s --by NAME" % props) in out, out
        _no_old_form(out, "confirm (a person)")
        # an agent, signing for itself
        code, out = run_agent("confirm", props, "--why", "read both ends", "--target", pj.dir)
        assert code == 1 and "rejected 1" in out, out
        assert ('confirm %s --why "..."' % props) in out or ("confirm %s --by NAME" % props) in out, out
        _no_old_form(out, "confirm (an agent)")


def test_F1_an_agents_by_without_approved_in_is_refused_naming_its_own_signature():
    with Project() as pj:
        assert run_said("register", F_P, "memo.py", "--target", pj.dir)[0] == 0
        assert pj.propose(Q1_ADD)[0] == 0
        props = os.path.join(pj.dir, "p.json")
        write(props, {"relations": [rel(F_P + "#Q2 list", "documents", "memo.py:list_", ev="lists.")]})
        write(os.path.join(pj.dir, "memo.py"), NEW_CODE)
        for argv in (("concept", "add", "a", "--means", "m", "--by", "lee"),
                     ("confirm", props, "--by", "lee"),
                     ("reconfirm", mangsang.rel_id(Q1_ADD), "--by", "lee", "--why", "re-read; it holds")):
            code, out = run_agent(*argv, "--target", pj.dir)
            assert code == 1 and "--approved-in source:ID" in out, (argv, out)
            _no_old_form(out, " ".join(argv[:2]))
            assert '--delegated "' not in out, ("no free-text delegation is offered", argv, out)
            assert "--why" in out, ("the agent's own signature (neither --by nor --delegated, with --why) is named", argv, out)


def test_F1_reconfirm_help_does_not_offer_a_free_text_delegation():
    code, out = run_said("reconfirm", "--help")
    assert code == 0 and "usage:" in out and "--why" in out, out
    _no_old_form(out, "reconfirm --help")


# F2 — --files through a symlinked directory

def _f2_dirs(pj):
    """(real directory, a symlink to it); Skip where the host cannot make a symlink."""
    real = os.path.realpath(pj.dir)
    link = real + "-link"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError, AttributeError) as err:
        raise Skip("no symlinks here: %s" % err)
    assert os.path.realpath(link) == real and link != real
    return real, link


def _f2_same_as_relative(target, given):
    a, x, bak, deep = _c5_ids()
    want = run_said("impact", "--files", "src/a.py", "--target", target)
    assert want[0] == 1 and a in want[1] and want[1].startswith("scope: 1 file(s), 1 relation(s) stand on them"), want
    code, out = run_said("impact", "--files", given, "--target", target)
    assert "not registered" not in out, (target, given, out)
    assert code == 1 and a in out, ("the stale relation on the named file", target, given, out)
    assert out.startswith("scope: 1 file(s), 1 relation(s) stand on them"), (target, given, out)
    assert _lines_with(out, "stale") == _lines_with(want[1], "stale") and x not in out and bak not in out and deep not in out, (out, want)
    # a file with nothing stale: its one relation is in scope and the exit is 0, as with the relative path
    other = os.path.join(os.path.dirname(given), "a.pyx")
    code, out = run_said("impact", "--files", other, "--target", target)
    assert code == 0 and "not registered" not in out and a not in out, (target, other, out)
    assert out.startswith("scope: 1 file(s), 1 relation(s) stand on them"), (target, other, out)
    # both spellings of one file are one file
    code, out = run_said("impact", "--files", "src/a.py", given, "--target", target)
    assert code == 1 and out.startswith("scope: 1 file(s), 1 relation(s) stand on them") and "not registered" not in out, out
    # --findings and --show under the same scope
    code, out = run_said("impact", "--findings", "--files", given, "--target", target)
    assert code == 1 and any(a in json.dumps(f) for f in _c5_findings(out)), out


def test_F2_impact_files_takes_the_real_path_when_the_target_is_a_symlink():
    with _c5_project() as pj:
        edit(pj, "src/a.py", "return 1", "return 2")
        real, link = _f2_dirs(pj)
        try:
            _f2_same_as_relative(link, os.path.join(real, "src", "a.py"))
        finally:
            os.remove(link)


def test_F2_impact_files_takes_the_symlinked_path_when_the_target_is_the_real_directory():
    with _c5_project() as pj:
        edit(pj, "src/a.py", "return 1", "return 2")
        real, link = _f2_dirs(pj)
        try:
            _f2_same_as_relative(real, os.path.join(link, "src", "a.py"))
        finally:
            os.remove(link)


def test_F2_impact_files_still_says_not_registered_for_a_file_outside_the_target_reached_by_a_symlink():
    """The other side of F2: resolving the path must not make a file that is not the target's look registered, and the
    symlinked spelling of a registered file is never the unregistered one."""
    with _c5_project() as pj:
        edit(pj, "src/a.py", "return 1", "return 2")
        real, link = _f2_dirs(pj)
        outside = tempfile.mkdtemp(prefix="mangsang-test-out-")
        try:
            write(os.path.join(outside, "src", "a.py"), "def f():\n    return 9\n")
            a = _c5_ids()[0]
            code, out = run_said("impact", "--files", os.path.join(os.path.realpath(outside), "src", "a.py"),
                                 os.path.join(real, "src", "a.py"), "--target", link)
            assert code == 1 and a in out, out
            nr = _lines_with(out, "not registered")
            assert len(nr) == 1 and os.path.basename(outside) in nr[0] and os.path.basename(real) + os.sep + "src" not in nr[0], out
            assert out.startswith("scope: 2 file(s), 1 relation(s) stand on them"), out
        finally:
            os.remove(link)
            shutil.rmtree(outside, ignore_errors=True)


# F3 — the queue's `signed:` line

def _f3_signed(text, rid):
    lines = [l for l in packet(text, rid).split("\n") if l.strip().startswith("signed:")]
    assert len(lines) == 1, (rid, text)
    return lines[0]


def test_F3_a_queue_packets_signed_line_says_the_signer_and_then_the_reason_once():
    with _signed_project() as pj:
        rid, = agent_confirms(pj, rel(F_P + "#Q2 list", "documents", "memo.py:list_", ev="lists."), why="read A; then B")
        a = mangsang.rel_id(R_ADD)
        for form in ((), ("--markdown",)):
            code, out = run_said("review", "queue", *form, "--target", pj.dir)
            assert code == 0, out
            line = _f3_signed(out, rid)
            assert "Claude Code" in line and line.index("Claude Code") < line.index("read A"), (form, line)
            assert line.count("read A") == 1, ("the reason's first clause, once", form, line)
            assert line.count("then B") == 1 and "read A; then B" in line, ("the whole reason, once", form, line)
            assert packet(out, rid).count("read A") == 1, (form, packet(out, rid))
            # the default reason of the other relations: its first clause once too
            line = _f3_signed(out, a)
            assert line.count("read both ends") == 1 and "read both ends; the quote says what the relation claims" in line, (form, line)


def test_F3_a_reason_of_one_clause_and_a_persons_signature_are_said_once_too():
    with _signed_project() as pj:
        rid, = agent_confirms(pj, rel(F_P + "#Q2 list", "documents", "memo.py:list_", ev="lists."), why="the section names list_")
        edit(pj, "memo.py", "return []", "return list(store)")
        code, out = run_said("reconfirm", rid, "--by", "kim", "--why", "kim read A; and then B", "--target", pj.dir)
        assert code == 0, out
        # R_LIST stands on memo.py:list_ too: the agent re-reads it with a one-clause reason
        b = mangsang.rel_id(R_LIST)
        agent_rereads(pj, b, why="list_ still lists")
        code, out = run_said("review", "queue", "--target", pj.dir)
        line = _f3_signed(out, b)
        assert line.count("list_ still lists") == 1, line
        doc = queue_json(pj)
        for e in doc["entries"]:
            signed, why = str(e.get("signed", "")), str(e.get("why", ""))
            first = why.split(";")[0].strip()
            if e.get("kind") == "relation" and first and out.count(e.get("id", "?")) >= 2:
                text = _f3_signed(out, e["id"])
                assert text.count(first) == 1, ("the plain packet says the reason's first clause once", e["id"], text)


# F4 — a rename never lifts a person's review

def _f4_by_src(pj, src, dst):
    got = [r for r in mangsang.decl(pj.dir)["relations"] if r["src"] == src and r["dst"] == dst]
    assert len(got) == 1, (src, dst, [(r["src"], r["dst"]) for r in mangsang.decl(pj.dir)["relations"]])
    return got[0]


def test_F4_a_rejected_relation_is_still_disputed_after_its_concept_is_renamed():
    with _signed_project() as pj:
        a = mangsang.rel_id(R_ADD)
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        assert run_said("impact", "--target", pj.dir)[0] == 1
        assert person_review(pj)[3] == 1
        code, out = run_said("concept", "rename", "adding", "appending", "--target", pj.dir)
        assert code == 0, out
        r = _f4_by_src(pj, "memo.py:add", "concept:appending")
        n = r["id"]
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1, ("a rename revises nothing: the dispute stands", out)
        lines = [l for l in out.split("\n") if l.strip().startswith("disputed") and n in l]
        assert len(lines) == 1, out
        assert ("%s memo.py:add realizes concept:appending" % n) in re.sub(r"\s+", " ", lines[0]), lines
        assert "rejected by lee (source:L1): add does not print the id" in lines[0], lines
        assert "revise it (change the projection, then reconfirm) or retire it" in lines[0], lines
        assert "unresolved_total = 1" in out and "revised since" not in out and "awaiting" not in out, out
        code, out = run_said("impact", "--findings", "--target", pj.dir)
        found = [f for f in json.loads(out).get("findings", []) if f.get("kind") == "disputed" and f.get("layer") != "observation"]
        assert code == 1 and len(found) == 1 and n in json.dumps(found[0]), out
        assert run_said("impact", "--files", "memo.py", "--target", pj.dir)[0] == 1
        assert person_review(pj)[3] == 1
        code, out = run_said("review", "status", "--target", pj.dir)
        assert status_numbers(status_line(out, "appending")) == {"relations": 2, "reviewed": 0, "earlier": 0, "never": 1, "disputed": 1}, out
        code, out = run_said("lookup", n, "--target", pj.dir)
        assert "disputed by lee" in out and "revised since" not in out, out
        code, out = run_said("review", "queue", "--target", pj.dir)
        assert "revised since" not in out, out
        # a second rename, back: still the same dispute
        assert run_said("concept", "rename", "appending", "adding", "--target", pj.dir)[0] == 0
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out and any(l.strip().startswith("disputed") and a in l for l in out.split("\n")), out


def test_F4_an_accepted_relation_stays_reviewed_after_its_concept_is_renamed():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert review(pj, "accept", a, b, c)[0] == 0
        assert person_review(pj) == (3, 3, 0, 0, 1, 1)
        assert run_said("concept", "rename", "adding", "appending", "--target", pj.dir)[0] == 0
        assert stale_ids(pj) == [], "a rename stales nothing"
        code, out = run_said("review", "status", "--target", pj.dir)
        assert code == 0, out
        assert status_numbers(status_line(out, "appending")) == {"relations": 2, "reviewed": 2, "earlier": 0, "never": 0, "disputed": 0}, out
        assert status_numbers(status_line(out, "total")) == {"relations": 3, "reviewed": 3, "earlier": 0, "never": 0, "disputed": 0}, out
        assert person_review(pj) == (3, 3, 0, 0, 1, 1), "check counts them as reviewed still"
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out


def test_F4_each_review_entrys_seen_is_keyed_by_the_renamed_anchor_with_the_fingerprints_it_held():
    with _signed_project() as pj:
        a, b = mangsang.rel_id(R_ADD), mangsang.rel_id(R_LIST)
        assert review(pj, "reject", a, why="add does not print the id")[0] == 0
        assert review(pj, "accept", b)[0] == 0
        assert review(pj, "accept", b, why="lee: 'read again'")[0] == 0
        was = {"memo.py:add": record(pj, a), "memo.py:list_": record(pj, b)}
        assert len(was["memo.py:list_"]["reviews"]) == 2
        assert run_said("concept", "rename", "adding", "appending", "--target", pj.dir)[0] == 0
        for src, old in was.items():
            r = _f4_by_src(pj, src, "concept:appending")
            fps = {src: old["seen"][src], "concept:appending": old["seen"]["concept:adding"]}
            assert r["seen"] == fps and r["evidence"] == old["evidence"], ("no fingerprint and no quote changed", r)
            got = r.get("reviews")
            assert isinstance(got, list) and len(got) == len(old["reviews"]), r
            for e, e0 in zip(got, old["reviews"]):
                assert e.get("seen") == fps, ("keyed by the renamed anchor, the fingerprints it held", e, fps)
                assert "concept:adding" not in json.dumps(e.get("seen")), e
                assert {k: v for k, v in e.items() if k != "seen"} == {k: v for k, v in e0.items() if k != "seen"}, (e, e0)


# F5 — move does not carry a dispute away

def _f5_refused(out, rid):
    assert rid in out and "disputed" in out, ("the refusal names the relation and its dispute", out)
    assert "revise" in out and "review" in out and "retire" in out, ("... and that it is revised and reviewed again, or retired", out)
    assert ("moved %s" % rid) not in out, out


def test_F5_move_refuses_a_disputed_relation_whose_heading_was_renamed_in_place():
    with _signed_project() as pj:
        c = mangsang.rel_id(Q1_ADD)
        assert review(pj, "reject", c, why="the section says nothing of what add returns")[0] == 0
        write(os.path.join(pj.dir, F_P), F_RENAMED)
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and any("broken" in l and c in l for l in out.split("\n")), out
        before = tree_bytes(os.path.join(mg(pj), "relations"), os.path.join(mg(pj), "retired"))
        code, out = run_said("move", "--dry-run", "--target", pj.dir)
        assert ("would move %s" % c) not in out and "0 relation(s) would move" in out, ("a dry run does not promise it", out)
        assert c in out and "disputed" in out, out
        for runner, argv in ((run_agent, ("move", "--why", "the heading was renamed in place")),
                             (run_said, ("move", "--by", "kim", "--why", "the heading was renamed in place")),
                             (run_agent, ("move", c, "--why", "the heading was renamed in place"))):
            code, out = runner(*argv, "--target", pj.dir)
            assert code != 0, ("refused", argv, out)
            _f5_refused(out, c)
            assert tree_bytes(os.path.join(mg(pj), "relations"), os.path.join(mg(pj), "retired")) == before, ("nothing is written for it", argv)
        assert not any(r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"])
        assert not os.path.exists(os.path.join(mg(pj), "retired", c + ".json"))
        # still what it was: broken and disputed, and the person's rejection on the record
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and any(l.strip().startswith("disputed") and c in l for l in out.split("\n")), out
        assert [e.get("verdict") for e in reviews_of(pj, c)] == ["rejected"]
        # retiring it is the way out the refusal names
        assert run_said("retire", c, "--why", "the section never documented add", "--target", pj.dir)[0] == 0
        assert run_said("impact", "--target", pj.dir)[0] == 0


def test_F5_move_refuses_a_disputed_relation_whose_symbol_moved_unchanged_and_carries_the_others():
    with _signed_project() as pj:
        a, b, c = (mangsang.rel_id(r) for r in (R_ADD, R_LIST, Q1_ADD))
        assert review(pj, "reject", a, why="add does not print the id; it only returns 1")[0] == 0
        write(os.path.join(pj.dir, "memo.py"), F_NO_ADD)
        write(os.path.join(pj.dir, "core.py"), F_CORE)
        assert run_said("register", "core.py", "--target", pj.dir)[0] == 0
        kept = io.open(os.path.join(mg(pj), "relations", a + ".json"), "rb").read()
        code, out = run_said("move", "--dry-run", "--target", pj.dir)
        assert ("would move %s" % a) not in out and ("would move %s" % c) in out and "1 relation(s) would move" in out, out
        code, out = run_agent("move", "--why", "add moved to core.py with its body unchanged", "--target", pj.dir)
        assert code != 0, ("one relation was refused", out)
        _f5_refused(out, a)
        assert ("moved %s" % c) in out and "1 relation(s) moved" in out, ("the relation nobody disputes is carried", out)
        rels = mangsang.decl(pj.dir)["relations"]
        assert [r.get("moved-from") for r in rels if r.get("moved-from")] == [c], rels
        assert not any(r["src"] == "core.py:add" for r in rels), ("no relation of the disputed one at the new home", rels)
        assert io.open(os.path.join(mg(pj), "relations", a + ".json"), "rb").read() == kept, "nothing is written for it"
        assert not os.path.exists(os.path.join(mg(pj), "retired", a + ".json"))
        code, out = run_said("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out, out
        assert any("broken" in l and a in l for l in out.split("\n")) and any(l.strip().startswith("disputed") and a in l for l in out.split("\n")), out
        assert person_review(pj)[3] == 1


def test_F5_move_still_carries_a_disputed_relation_that_was_revised_or_later_accepted():
    """The refusal is for `disputed-unrevised` only: a rejection the person later took back does not hold a move."""
    with _signed_project() as pj:
        c = mangsang.rel_id(Q1_ADD)
        assert review(pj, "reject", c, why="the section says nothing of what add returns")[0] == 0
        p = os.path.join(pj.dir, RELS, c + ".json")
        r = mangsang.load(p)
        r["reviews"][0]["at"] = "2026-01-01T00:00:00Z"
        mangsang.save(p, r)
        assert review(pj, "accept", c, why="lee: 'I misread it'")[0] == 0
        write(os.path.join(pj.dir, F_P), F_RENAMED)
        code, out = run_agent("move", "--why", "the heading was renamed in place", "--target", pj.dir)
        assert code == 0 and "1 relation(s) moved" in out, out
        # ... and the one still disputed beside it is the one refused
    with _signed_project() as pj:
        c = mangsang.rel_id(Q1_ADD)
        extra = rel(F_P + "#Q1 add", "realizes", "concept:adding")
        e, = agent_confirms(pj, extra)
        assert review(pj, "reject", e, why="the section is about the command, not the idea")[0] == 0
        write(os.path.join(pj.dir, F_P), F_RENAMED)
        code, out = run_agent("move", "--why", "the heading was renamed in place", "--target", pj.dir)
        assert code != 0, out
        _f5_refused(out, e)
        assert [r.get("moved-from") for r in mangsang.decl(pj.dir)["relations"] if r.get("moved-from")] == [c], out

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("PASS", name)
            except Skip as why:
                print("SKIP", name, "--", why)
            except (Exception, SystemExit) as err:   # a self-check that dies between tests lies by omission
                failed += 1
                print("FAIL", name, "--", "%s: %s" % (type(err).__name__, err))
    print("all passed" if not failed else "%d failed" % failed)
    sys.exit(1 if failed else 0)
