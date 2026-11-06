"""Source guard for mangsang's own model (scope: MODEL.md). Read-only: it never writes, regenerates or reconfirms a record.

  python3 check_model.py [--target DIR] [--engine PATH]

First it reads mangsang/ itself and fails when the model is absent or has lost what it was built to carry: the expected
concepts, questions, invariants, registered files, a doc/code/test projection of each concept, the verifies on each
verified symbol, and the registered scope — inv-registered-scope still asks of every file under plugin/ and test_ (and
AGENTS.md, MODEL.md), and holds no except that EXCEPTS below does not classify or MODEL.md's Not claimed does not name.
Then it asks the installed, released mangsang engine `check`, `cq` and `impact` of the target and fails when any of them
does; `check` fails on a tracked file in that scope that is neither registered nor excepted. Exit 0 only when all of it
holds; 1 when something does not; 2 when there is no usable engine.

The engine is the released one, never this checkout's plugin/: --engine, else MANGSANG_ENGINE, else the version
hunsu.json pins at the Claude Code plugin cache (CLAUDE_CONFIG_DIR or ~/.claude), then the Codex one (CODEX_HOME or
~/.codex). An engine inside the target is refused.
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
    """What the model was built to carry, read from mangsang/ directly. [] when it holds."""
    root = os.path.join(target, "mangsang")
    if not os.path.isdir(root) or read_json(os.path.join(root, "registry.json")) is None:
        return ["the model is absent: no mangsang/ with a registry.json in %s" % target]
    problems = []
    concepts, cq = records(os.path.join(root, "concepts")), records(os.path.join(root, "cq"))
    relations = list(records(os.path.join(root, "relations")).values())
    for name in CONCEPTS:
        if not str((concepts.get(name) or {}).get("means", "")).strip():
            problems.append("concept %s is missing or has no meaning" % name)
    for qid, concept in QUESTIONS.items():
        q = cq.get(qid)
        verify = (q or {}).get("verify") or {}
        if q is None or q.get("retired"):
            problems.append("question %s is missing or retired" % qid)
        elif verify.get("kind") != "answered-by" or concept not in (verify.get("concepts") or []):
            problems.append("question %s is not answered by concept %s" % (qid, concept))
    for qid, kind in INVARIANTS.items():
        q = cq.get(qid)
        if q is None or q.get("retired") or ((q.get("verify") or {}).get("kind") != kind):
            problems.append("invariant %s is missing, retired or no longer a %s invariant" % (qid, kind))
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
    print("engine: mangsang %s at %s" % (engine_version(engine), engine))
    problems = guard(target)
    for p in problems:
        print("guard FAILED: %s" % p)
    print("guard: %s" % ("holds — concepts %d, questions %d, invariants %d, files %d, verified symbols %d, scope %s with %d classified except(s)"
                         % (len(CONCEPTS), len(QUESTIONS), len(INVARIANTS), len(FILES), len(VERIFIED), " ".join(SCOPE), len(EXCEPTS))
                         if not problems else "%d problem(s)" % len(problems)))
    if not os.path.isdir(os.path.join(target, "mangsang")):
        return 1
    codes = {}
    for command in ("check", "cq", "impact"):
        print("--- mangsang %s" % command, flush=True)
        codes[command] = subprocess.run([sys.executable, engine, command, "--target", target]).returncode
    print("engine: " + ", ".join("%s exit %d" % kv for kv in codes.items()))
    return 0 if not problems and not any(codes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
