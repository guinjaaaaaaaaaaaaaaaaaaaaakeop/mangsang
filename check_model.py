"""Source guard for mangsang's own model (scope: MODEL.md). Read-only: it never writes, regenerates or reconfirms a record.

  python3 check_model.py [--target DIR] [--engine PATH]

What the engine says, the engine says: it asks the installed, released mangsang engine (2.2.0 or later) `check
--require-model` — an absent or empty model fails there — `cq` and `impact`, and fails when any of them does. The model's
inv-required invariant (a `required` invariant over CONCEPTS, QUESTIONS and INVARIANTS below) makes `check` fail, with the
engine's own semantics, when one of them is missing, retired, marked drifted, owing a re-read or realized by nothing;
`check` also fails on a tracked file in the registered scope that is neither registered nor excepted.
What the engine cannot say, it reads from mangsang/ itself: that inv-required is there and still names every expected
concept, question and invariant; a concept with an empty meaning; which concept answers each question and each
invariant's kind; the registry and its files; a doc/code/test projection of each concept; the verifies on each verified
symbol; and the registered scope — inv-registered-scope still asks of every file under plugin/ and test_ (and AGENTS.md,
MODEL.md), and holds no except that EXCEPTS below does not classify or MODEL.md's Not claimed does not name. Exit 0 only
when all of it holds; 1 when something does not; 2 when there is no usable engine.

The engine is the released one, never this checkout's plugin/: --engine, else MANGSANG_ENGINE, else the version
hunsu.json pins at the Claude Code plugin cache (CLAUDE_CONFIG_DIR or ~/.claude), then the Codex one (CODEX_HOME or
~/.codex). An engine inside the target is refused, and so is one older than 2.2.0 (it has no `required` kind or
`--require-model`).
"""
import argparse
import json
import os
import subprocess
import sys

CONCEPTS = ("evidence-gate", "staleness-against-seen", "same-file-reads", "living-answer", "owed-reread")
QUESTIONS = {"cq-relation-stored": "evidence-gate", "cq-stale-or-broken": "staleness-against-seen", "cq-edit-reach": "same-file-reads",
             "cq-question-answered": "living-answer", "cq-retired-projection": "owed-reread"}
INVARIANTS = {"inv-registered-scope": "registered", "inv-projection": "projection", "inv-resolved": "resolved",
              "inv-verified-confirm": "coverage", "inv-verified-impact": "coverage", "inv-verified-parts": "coverage",
              "inv-verified-answer-health": "coverage", "inv-verified-owe-for": "coverage"}
# the engine keeps the three lists above through this invariant (missing, retired, drifted, owed, unrealized); this guard keeps
# that the invariant itself is there and names them all — the one thing a `required` invariant cannot say of itself
REQUIRED = "inv-required"
ENGINE_FLOOR = (2, 2, 0)   # the `required` kind and `check --require-model`
FILES = ("plugin/mangsang.py", "plugin/anchors.py", "plugin/README.md", "test_mangsang.py", "AGENTS.md", "MODEL.md")
MEDIA = {"doc": ("plugin/README.md#",), "code": ("plugin/mangsang.py:", "plugin/anchors.py:"), "test": ("test_mangsang.py:",)}
VERIFIED = ("plugin/mangsang.py:cmd_confirm", "plugin/mangsang.py:compute_impact", "plugin/anchors.py:parts",
            "plugin/mangsang.py:answer_health", "plugin/mangsang.py:owe_for")
# inv-registered-scope's paths: prefixes, so a file committed later under the payload or as a root suite is asked about
SCOPE = ("plugin/", "test_", "AGENTS.md", "MODEL.md")
# every except that invariant may hold, each with its reason (MODEL.md's Not claimed names each and says it in full).
# An except not here fails the guard: classifying another file is a change to this table and to MODEL.md together.
EXCEPTS = {
    "plugin/.claude-plugin/plugin.json": "a manifest: host integration and packaging",
    "plugin/.codex-plugin/plugin.json": "a manifest: host integration and packaging",
    "plugin/plugin.json": "a manifest: packaging",
    "plugin/LICENSE": "the license text",
    "plugin/commands/*.md": "the Claude command adapters; a later .md there is one more adapter, any other kind is not excepted",
    "plugin/skills/operate/SKILL.md": "the operate skill: installed operation, not engine semantics",
    "plugin/hostcall.py": "vendored, kept in step with the other copies",
    "plugin/judge_worker.py": "the judge's worker; judge is not claimed",
    "plugin/vendor/mermaid/*": "the vendored third-party mermaid; every file in that directory belongs to that copy",
    "test_package.py": "another suite",
    "test_properties.py": "another suite",
    "test_running_agent.py": "another suite",
    "test_model_guard.py": "the regression suite of this guard, not a mangsang contract",
}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def section(path, heading):
    """The text of a `## heading` section of a Markdown file, up to the next `## `; "" when the file or heading is absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    out, inside = [], False
    for line in lines:
        if line.startswith("## "):
            inside = line[3:].strip() == heading
        elif inside:
            out.append(line)
    return "\n".join(out)


def records(folder):
    out = {}
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        data = read_json(os.path.join(folder, name)) if name.endswith(".json") else None
        if isinstance(data, dict):
            out[name[:-len(".json")]] = data
    return out


def engine_path(target, given):
    if given:
        return given
    if os.environ.get("MANGSANG_ENGINE"):
        return os.environ["MANGSANG_ENGINE"]
    pin = ((read_json(os.path.join(target, "hunsu.json")) or {}).get("plugins") or {}).get("mangsang", {}).get("version")
    if not pin:
        return None
    for home in (os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"),
                 os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")):
        path = os.path.join(home, "plugins", "cache", "mangsang", "mangsang", pin, "mangsang.py")
        if os.path.isfile(path):
            return path
    return None


def engine_version(path):
    root = os.path.dirname(path)
    for manifest in (os.path.join(root, ".claude-plugin", "plugin.json"), os.path.join(root, ".codex-plugin", "plugin.json"),
                     os.path.join(root, "plugin.json")):
        version = (read_json(manifest) or {}).get("version")
        if version:
            return version
    return "unknown"


def guard(target):
    """What the engine cannot say about the model, read from mangsang/ directly. [] when it holds — and for an absent model,
    which the engine's `check --require-model` fails, naming it."""
    root = os.path.join(target, "mangsang")
    if not os.path.isdir(root):
        return []
    if read_json(os.path.join(root, "registry.json")) is None:
        return ["mangsang/registry.json is absent or not JSON — the model registers nothing"]
    problems = []
    concepts, cq = records(os.path.join(root, "concepts")), records(os.path.join(root, "cq"))
    relations = list(records(os.path.join(root, "relations")).values())
    # presence, retirement, a drift mark, an owed re-read and a realization are inv-required's, in the engine; what it cannot
    # say of itself — that it is there and names everything — and the pairings and kinds below are this guard's
    req = cq.get(REQUIRED)
    rv = (req or {}).get("verify") or {}
    if req is None or req.get("retired") or rv.get("kind") != "required":
        problems.append("invariant %s is missing, retired or no longer a required invariant — nothing asks the engine to keep the "
                        "model's concepts, questions and invariants" % REQUIRED)
    else:
        for part, want in (("concepts", CONCEPTS), ("questions", tuple(QUESTIONS)), ("invariants", tuple(INVARIANTS))):
            for x in want:
                if x not in (rv.get(part) or []):
                    problems.append("invariant %s no longer requires %s %s" % (REQUIRED, part[:-1], x))
    for name in CONCEPTS:
        if name in concepts and not str(concepts[name].get("means", "")).strip():
            problems.append("concept %s has no meaning" % name)
    for qid, concept in QUESTIONS.items():
        q = cq.get(qid)
        verify = (q or {}).get("verify") or {}
        if q is not None and not q.get("retired") and (verify.get("kind") != "answered-by" or concept not in (verify.get("concepts") or [])):
            problems.append("question %s is not answered by concept %s" % (qid, concept))
    for qid, kind in INVARIANTS.items():
        q = cq.get(qid)
        if q is not None and not q.get("retired") and (q.get("verify") or {}).get("kind") != kind:
            problems.append("invariant %s is no longer a %s invariant" % (qid, kind))
    scope = ((cq.get("inv-registered-scope") or {}).get("verify") or {})
    if scope.get("kind") == "registered":
        for p in SCOPE:
            if p not in (scope.get("paths") or []):
                problems.append("invariant inv-registered-scope no longer asks of %s — a file committed there would pass check unseen" % p)
        named = section(os.path.join(target, "MODEL.md"), "Not claimed")
        for g in scope.get("except") or []:
            if g not in EXCEPTS:
                problems.append("invariant inv-registered-scope excepts %s, which check_model.py does not classify — give it a reason "
                                "in MODEL.md's Not claimed and an EXCEPTS entry, or drop it" % g)
            elif "`%s`" % g not in named:
                problems.append("invariant inv-registered-scope excepts %s, which MODEL.md's Not claimed does not name — its reason "
                                "belongs there" % g)
    registered = {e.get("path") for e in read_json(os.path.join(root, "registry.json")) or [] if isinstance(e, dict)}
    for f in FILES:
        if f not in registered:
            problems.append("file %s is not registered" % f)
    for name in CONCEPTS:
        srcs = [r.get("src", "") for r in relations if r.get("predicate") == "realizes" and r.get("dst") == "concept:" + name]
        for medium, prefixes in MEDIA.items():
            if not any(s.startswith(prefixes) for s in srcs):
                problems.append("concept %s has no %s projection (%s)" % (name, medium, " or ".join(p.rstrip("#:") for p in prefixes)))
    for symbol in VERIFIED:
        if not any(r.get("predicate") == "verifies" and r.get("dst") == symbol and str(r.get("src", "")).startswith("test_mangsang.py:")
                   for r in relations):
            problems.append("%s (%s) is verified by no test_mangsang.py test" % (symbol, symbol.split(":", 1)[1]))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="check_model.py", description=__doc__.split("\n")[0])
    ap.add_argument("--target", default=os.path.dirname(os.path.abspath(__file__)), help="the checkout (default: this file's directory)")
    ap.add_argument("--engine", default=None, help="the released mangsang.py (default: MANGSANG_ENGINE, else the hunsu.json pin)")
    args = ap.parse_args(argv)
    target = os.path.realpath(args.target)
    engine = engine_path(target, args.engine)
    if not engine or not os.path.isfile(engine):
        print("check_model: no released mangsang engine — pass --engine PATH or set MANGSANG_ENGINE (looked for %s)" % (engine or "the hunsu.json pin"))
        return 2
    engine = os.path.realpath(engine)
    if engine == target or engine.startswith(target.rstrip(os.sep) + os.sep):
        print("check_model: refusing engine %s — it is inside the target, a working source, not the released engine" % engine)
        return 2
    version = engine_version(engine)
    print("engine: mangsang %s at %s" % (version, engine))
    try:
        floor = tuple(int(x) for x in version.split("+")[0].split(".")[:3]) >= ENGINE_FLOOR
    except ValueError:
        floor = False
    if not floor:
        print("check_model: refusing engine mangsang %s — this model declares a `required` invariant and the guard asks "
              "`check --require-model`, both mangsang %s or later; pass --engine with such a release" % (version, ".".join(map(str, ENGINE_FLOOR))))
        return 2
    problems = guard(target)
    for p in problems:
        print("guard FAILED: %s" % p)
    absent = not os.path.isdir(os.path.join(target, "mangsang"))
    print("guard: %s" % ("no model here — the engine's `check --require-model` fails it" if absent else
                         "holds — %s keeps concepts %d, questions %d, invariants %d; files %d, verified symbols %d, scope %s with %d classified except(s)"
                         % (REQUIRED, len(CONCEPTS), len(QUESTIONS), len(INVARIANTS), len(FILES), len(VERIFIED), " ".join(SCOPE), len(EXCEPTS))
                         if not problems else "%d problem(s)" % len(problems)))
    codes = {}
    for command in (["check", "--require-model"], ["cq"], ["impact"]):
        print("--- mangsang %s" % " ".join(command), flush=True)
        codes[" ".join(command)] = subprocess.run([sys.executable, engine] + command + ["--target", target]).returncode
    print("engine: " + ", ".join("%s exit %d" % kv for kv in codes.items()))
    return 0 if not problems and not absent and not any(codes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
