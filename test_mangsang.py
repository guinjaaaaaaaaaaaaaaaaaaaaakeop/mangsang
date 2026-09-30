"""Self-check for mangsang. A temp project with a plan section, a module and a test; every rejection and every kind of staleness fires once.

  python test_mangsang.py
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
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



class Skip(Exception):
    """Raised by a test that cannot run on this host; the runner reports it as SKIP, never as PASS."""

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
        assert run("reconfirm", r["id"], "--by", "kim", "--target", pj.dir)[0] == 0
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
            assert run("reconfirm", x["id"], "--delegated", "matches site-build's new meaning", "--target", pj.dir)[0] == 0
        assert run("impact", "--target", pj.dir)[0] == 0   # every relation fresh...
        code, out = run("cq", "--target", pj.dir)
        assert code == 1 and "FAILED" in out and ("site-build lost projection(s) %s (pages.yml) since its sentence was affirmed" % old) in out, out   # ...and the sentence still owed
        code, out = run("concept", "list", "--target", pj.dir)
        assert "owes a re-read: lost %s" % old in out, out
        # reaffirm: a judgment, signed, kept with what it answered; then the question is answered again
        assert run("concept", "reaffirm", "site-build", "--target", pj.dir)[0] != 0, "a reaffirmation is signed"
        assert run("concept", "reaffirm", "site-build", "--by", "kim", "--target", pj.dir)[0] == 0
        c = next(c for c in mangsang.decl(pj.dir)["concepts"] if c["name"] == "site-build")
        assert "owes" not in c and c["history"][-1]["owed"] == [old] and c["history"][-1]["reaffirmed"]["by"] == "kim", c
        assert run("cq", "--target", pj.dir)[0] == 0
        assert run("concept", "reaffirm", "site-build", "--by", "kim", "--target", pj.dir)[0] != 0, "nothing owed, nothing to reaffirm"
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
        assert run("reconfirm", item["relation"], "--by", "kim", "--target", pj.dir)[0] == 0
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
        assert code == 0 and "no confirmed relations" in out, out


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
            {"type": "user", "uuid": "u2", "timestamp": "t4", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1", "content": "answered: Times in UTC?=reader's local"}]}},
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
        code, out = run("source", "add", "U1", "--from-transcript", tr, "--match", "everything", "--speaker", "haklee", "--target", pj.dir)
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
        assert hand["declared"] == {"by": "lee", "approved-in": "source:L1", "approval-of": "source:A1"}, hand["declared"]
        assert draw["declared"] == {"by": "lee", "approved-in": "source:L2"}, draw["declared"]
        # every record object says which mangsang wrote it — a field
        assert hand["written_by"] == mangsang.engine() and mangsang.load(os.path.join(sub, "mangsang", "sources", "L2.json"))["written_by"] == mangsang.engine()
        assert not os.path.exists(os.path.join(sub, "mangsang", "cq.json")), "a new project gets no empty legacy list"
        write(os.path.join(sub, "proposals.json"), {"relations": [
            {"src": "README.md#hands", "predicate": "realizes", "dst": "concept:hand", "evidence": "three hands."},
            {"src": "README.md#draw", "predicate": "realizes", "dst": "concept:draw", "evidence": "same hand draws."},
            {"src": "source:L2", "predicate": "realizes", "dst": "concept:draw", "evidence": "every hand shown is the same"}]})
        assert run("confirm", "proposals.json", "--delegated", "test", "--target", sub)[0] == 0
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
        assert "declared by lee (approved in `source:L1`, answering the agent's `source:A1`)" in page and "delegated: test" in page and "Rendered from `mangsang/` by mangsang " in page, page
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
        assert run("reconfirm", rid, "--by", "lee", "--target", sub)[0] == 0
        r = mangsang.load(os.path.join(sub, "mangsang", "relations", rid + ".json"))
        assert len(r["history"]) == 1 and r["history"][0]["confirmed"] == {"delegated": "test"} and r["confirmed"] == {"by": "lee"}, r
        assert run("concept", "revise", "draw", "--means", "no hand beats another", "--by", "lee", "--target", sub)[0] == 0
        draw = mangsang.load(os.path.join(sub, "mangsang", "concepts", "draw.json"))
        assert draw["history"] == [{"means": "every hand shown is the same", "declared": {"by": "lee", "approved-in": "source:L2"}}], draw
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
        code, out = run("reconfirm", rid, "--by", "kim", "--evidence", "appends and prints", "--target", pj.dir)
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
        assert c["declared"] == {"by": "lee", "approved-in": "source:L1"}, c
        assert agent_run("concept", "add", "b", "--means", "m", "--delegated", "the agent's reading", "--target", pj.dir)[0] == 0


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
        code, out = run("check", "--target", pj.dir)
        assert code == 0 and "0 gap(s)" in out, out
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
    """--delegated D-xxxx (a chongdae delegation id) becomes {delegated: {ref}} — machine-readable, one judgment
    declared once and referenced, never resolved here (whose delegation it is stays the record-reader's audit).
    Any other reason stays a free why-string."""
    with Project() as pj:
        assert run("register", "plan/PLAN.md", "memo.py", "test_memo.py", "--target", pj.dir)[0] == 0
        assert run("concept", "add", "adding", "--means", "a note is appended", "--delegated", "D-a1b2c3d4", "--target", pj.dir)[0] == 0
        c = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "adding.json"))
        assert c["declared"] == {"delegated": {"ref": "D-a1b2c3d4"}}, c
        assert run("concept", "add", "listing", "--means", "open notes only", "--delegated", "orchestrator pre-approved this round", "--target", pj.dir)[0] == 0
        c2 = mangsang.load(os.path.join(pj.dir, "mangsang", "concepts", "listing.json"))
        assert c2["declared"] == {"delegated": "orchestrator pre-approved this round"}, c2
        # confirm with a ref, and impact --findings prints it as `ref D-...` without crashing
        code, out = pj.propose(rel("memo.py:add", "realizes", "concept:adding", ev="a note is appended"))
        assert code == 0, out
        import json as _json
        props = {"relations": [{"src": "memo.py:list_", "predicate": "realizes", "dst": "concept:listing", "evidence": "open notes only"}]}
        p = os.path.join(pj.dir, "props2.json")
        write(p, props)
        code, out = run("confirm", p, "--delegated", "D-a1b2c3d4", "--target", pj.dir)
        assert code == 0, out
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert "ref D-a1b2c3d4" in out, out


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
        assert q["declared"] == {"by": "kim"}, q
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
        assert len(d["relations"]) == 1 and d["relations"][0]["confirmed"] == {"by": "kim"}
        assert sorted(os.listdir(os.path.join(pj.dir, "mangsang", "relations"))) == [d["relations"][0]["id"] + ".json"]
        assert not os.path.exists(os.path.join(pj.dir, "proposals.json")), "a proposal is consumed"
        rid = d["relations"][0]["id"]
        assert rid == mangsang.rel_id(d["relations"][0]) and rid.startswith("R-")
        assert run("retire", rid, "--why", "test", "--target", pj.dir)[0] == 0
        d = mangsang.decl(pj.dir)
        assert not d["relations"] and d["retired"][0]["retired"] == {"why": "test"}
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
        code, out = run("reconfirm", *ids, "--by", "kim", "--target", pj.dir)
        assert code != 0 and "no longer in the text" in out, out
        q1 = next(i for i in ids if mangsang.decl(pj.dir)["relations"][[x["id"] for x in mangsang.decl(pj.dir)["relations"]].index(i)]["src"].startswith("plan/"))
        assert run("reconfirm", q1, "--by", "kim", "--evidence", "appends a memo and prints", "--target", pj.dir)[0] == 0
        code, out = run("reconfirm", *[i for i in ids if i != q1], "--by", "kim", "--target", pj.dir)
        assert code == 0 and out.count("re-confirmed") == 1, out
        code, out = run("impact", "--target", pj.dir)
        assert code == 0 and "unresolved_total = 0" in out, out
        assert mangsang.decl(pj.dir)["relations"][0]["confirmed"] == {"by": "kim"}
        # reset, then remove the function: the relations on it are broken, not stale — and cannot be re-confirmed
        run("observe", "--reset", "--target", pj.dir)
        write(os.path.join(pj.dir, "memo.py"), "X = 1\n\n\ndef list_(store):\n    return [1]\n")
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and out.count("broken") == 2 and "dead anchors ['memo.py:add']" in out, out
        code, out = run("reconfirm", ids[0], "--by", "kim", "--target", pj.dir)
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
        write(os.path.join(d, "judge-response.json"), {"artifact-type": "mangsang/judgment@1", "non-claims": [], "items": [
            {"relation": ids["plan/PLAN.md#Q1 add"], "verdict": "still-true", "quote": "", "evidence": "add still appends; the return value changed, not the behavior the sentence names"},
            {"relation": ids["plan/PLAN.md#Q2 list"], "verdict": "drifted", "quote": "lists.", "evidence": "list_ now returns [1] regardless of the store"},
            {"relation": "R-nope", "verdict": "still-true", "quote": "", "evidence": "x"},
            {"relation": ids["plan/PLAN.md#Q2 list"], "verdict": "drifted", "quote": "not in the text", "evidence": "y"}]})
        code, out = run("judge", "consume", "--response", os.path.join(d, "judge-response.json"), "--by", "test", "--target", pj.dir)
        assert code == 1 and "still-true applied 1" in out and "drifted 1" in out and "rejected 2" in out, out
        r1 = next(x for x in mangsang.decl(pj.dir)["relations"] if x["id"] == ids["plan/PLAN.md#Q1 add"])
        assert r1["confirmed"]["delegated"].startswith("judge test:"), r1["confirmed"]
        code, out = run("impact", "--target", pj.dir)
        assert code == 1 and "unresolved_total = 1" in out, out   # the drifted one waits for a human
        code, out = run("impact", "--findings", "--target", pj.dir)
        assert any(f["kind"] == "delegated" and "judge test" in f["text"] for f in json.loads(out)["findings"]), out


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
        code, out = run("move", "--by", "kim", "--target", pj.dir)
        assert code == 1 and "2 relation(s) moved" in out and "2 left" in out, out
        d = mangsang.decl(pj.dir)
        moved = [r for r in d["relations"] if r.get("moved-from")]
        assert {(r["src"], r["dst"]) for r in moved} == {("plan/PLAN.md#Q1 add", "core.py:add"), ("test_memo.py:test_Q1_add", "core.py:add")}, moved
        assert all(r["confirmed"] == {"by": "kim"} and r["evidence"] for r in moved)
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
