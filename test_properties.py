"""Property self-check for mangsang: the engine's rules, tried against situations a machine makes up.

  python test_properties.py            (Hypothesis on: `pip install hypothesis`; without it every property is SKIPped)

`test_mangsang.py` plays the situations a person thought of. Four of the seven defects a day on a playground turned up
(2026-09-24) were in situations nobody had thought of: a title heading whose section was the whole file, a stale relation
blaming the wrong end, `--show` never working in a target inside a repository, `reconfirm` overwriting the earlier
judgment. Each property below states a rule of the design; Hypothesis generates the files, relations and command
sequences, runs the real engine, and shrinks a failure to its smallest example. Nothing here reaches the plugin's
runtime: it is a developer's check, run before a release like the example tests. No model calls.
"""
import contextlib
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "plugin")   # the installed payload; the root mangsang.py is only its CLI wrapper
sys.path.insert(0, PLUGIN)
import mangsang  # noqa: E402

try:
    from hypothesis import HealthCheck, given, settings, strategies as st
    HYPOTHESIS = True
except ImportError:   # the property tests need a generator; without one they say so instead of passing silently
    HYPOTHESIS = False


class Skip(unittest.SkipTest):
    """Raised by a test that cannot run on this host; the runner reports it as SKIP, never as PASS. A unittest.SkipTest,
    so a harness that runs these functions under unittest (hacheong's red-before-build) reads it as a skip, not an error."""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False))


def run(*argv):
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


def need_hypothesis():
    if not HYPOTHESIS:
        raise Skip("hypothesis is not installed (pip install hypothesis)")


PROPERTY = dict(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture]) if HYPOTHESIS else {}


# ---------------------------------------------------------------- 1. a section edit moves that section's anchors and no other

def markdown_of(heads):
    """heads: [(level, title, body)] -> the file, with one body line under each heading."""
    return "".join("%s %s\n\n%s\n\n" % ("#" * level, title, body) for level, title, body in heads)


def contains(heads, j, i):
    """Does heading j's section contain heading i? By the design: a section runs to the next heading of its level or higher;
    a title heading (level 1) runs only to the next heading of any level, so it contains no other heading."""
    if not j < i:
        return False
    lj = heads[j][0]
    if lj == 1:
        return False
    return heads[i][0] > lj and all(heads[k][0] > lj for k in range(j + 1, i))


if HYPOTHESIS:
    headings = st.lists(st.tuples(st.integers(min_value=1, max_value=3), st.text(alphabet="abcdefgh", min_size=1, max_size=3), st.sampled_from(["x", "y y", "z z z"])),
                        min_size=1, max_size=6).filter(lambda hs: len({t for _, t, _ in hs}) == len(hs))   # titles unique: an anchor is its title


def test_a_section_edit_moves_exactly_that_sections_anchors():
    need_hypothesis()

    @given(heads=headings, which=st.data())
    @settings(**PROPERTY)
    def prop(heads, which):
        i = which.draw(st.integers(min_value=0, max_value=len(heads) - 1))
        before = mangsang.anchors_of("doc.md", markdown_of(heads))
        edited = list(heads)
        edited[i] = (heads[i][0], heads[i][1], heads[i][2] + " more")
        after = mangsang.anchors_of("doc.md", markdown_of(edited))
        moved = {k for k in before if before[k] != after.get(k)}
        expected = {"", "#" + heads[i][1]} | {"#" + heads[j][1] for j in range(len(heads)) if contains(heads, j, i)}
        assert moved == expected, (heads, i, moved, expected)
        # (a file whose only heading is its title has "" and "#title" with the same text — the property found that on its
        # first run; it is not the defect: both move together, and the title stops standing for the file as soon as a
        # second heading exists. Uniqueness of anchor texts is therefore not a rule of the design.)

    prop()


# ---------------------------------------------------------------- 2. stale iff a propagating end changed; `because` is that end

def test_stale_names_the_end_that_changed_and_only_when_it_propagates():
    """Exhaustive over the vocabulary's propagation kinds and which ends change — a small world, every case."""
    kinds = {"documents": "dst->src", "verifies": "both", "references": "none", "realizes": "both"}
    for pred, change_src, change_dst in itertools.product(kinds, (False, True), (False, True)):
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            write(os.path.join(tmp, "plan.md"), "# p\n\n## Q1\n\nthe rule.\n")
            write(os.path.join(tmp, "code.py"), "def f():\n    return 1\n")
            assert run("register", "plan.md", "code.py", "--target", tmp)[0] == 0
            write(os.path.join(tmp, "proposals.json"), {"relations": [{"src": "plan.md#Q1", "predicate": pred, "dst": "code.py:f", "evidence": "the rule."}]})
            assert run("confirm", "proposals.json", "--by", "kim", "--target", tmp)[0] == 0
            if change_src:
                write(os.path.join(tmp, "plan.md"), "# p\n\n## Q1\n\nthe rule. still.\n")
            if change_dst:
                write(os.path.join(tmp, "code.py"), "def f():\n    return 2\n")
            d = mangsang.decl(tmp)
            stale, broken, _, _ = mangsang.compute_impact(tmp, d, persist=False)
            prop = kinds[pred]
            should = (change_dst and prop in ("dst->src", "both")) or (change_src and prop in ("src->dst", "both"))
            assert bool(stale) == should and not broken, (pred, change_src, change_dst, stale)
            if stale:
                # `because` names the changed end that propagates — a changed end whose direction does not propagate is no cause
                because = stale[0]["because"]
                causes = {a for a, ch, props in (("plan.md#Q1", change_src, prop in ("src->dst", "both")), ("code.py:f", change_dst, prop in ("dst->src", "both"))) if ch and props}
                if len(causes) == 1:
                    assert because in causes, (pred, because, causes)
                else:
                    assert " and " in because, (pred, because, causes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 3. `--show` reads the earlier text wherever the target sits in the repository

def test_show_finds_the_earlier_text_at_any_depth_inside_a_repository():
    for depth in (0, 1, 2):
        root = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=root, capture_output=True, text=True)
            git("init", "-q")
            target = os.path.join(root, *["d%d" % i for i in range(depth)])
            os.makedirs(target, exist_ok=True)
            write(os.path.join(target, "plan.md"), "# p\n\n## Q1\n\nthe rule.\n")
            assert run("register", "plan.md", "--target", target)[0] == 0
            assert run("concept", "add", "c", "--means", "a meaning", "--by", "kim", "--target", target)[0] == 0
            write(os.path.join(target, "proposals.json"), {"relations": [{"src": "plan.md#Q1", "predicate": "realizes", "dst": "concept:c", "evidence": "the rule."}]})
            assert run("confirm", "proposals.json", "--by", "kim", "--target", target)[0] == 0
            git("add", "-A"); git("commit", "-qm", "confirmed")
            # the section changes: the diff comes from git although the target is a subdirectory
            write(os.path.join(target, "plan.md"), "# p\n\n## Q1\n\nthe rule. still.\n")
            code, out = run("impact", "--show", "--target", target)
            assert code == 1 and "+the rule. still." in out, (depth, out)
            # the concept changes instead: its earlier meaning comes from git too
            write(os.path.join(target, "plan.md"), "# p\n\n## Q1\n\nthe rule.\n")
            assert run("concept", "revise", "c", "--means", "another meaning", "--by", "kim", "--target", target)[0] == 0
            code, out = run("impact", "--show", "--target", target)
            assert code == 1 and "-a meaning" in out and "+another meaning" in out and "concept:c" in out, (depth, out)
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- 4. judgments accumulate; renames lose nothing

def test_any_sequence_of_reconfirm_revise_and_rename_keeps_history_and_answerability():
    need_hypothesis()

    @given(ops=st.lists(st.sampled_from(["reconfirm", "revise", "rename", "cq-revise", "edit"]), min_size=1, max_size=6))
    @settings(**PROPERTY)
    def prop(ops):
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            write(os.path.join(tmp, "plan.md"), "# p\n\n## Q1\n\nthe rule.\n")
            assert run("register", "plan.md", "--target", tmp)[0] == 0
            name, means_n, edits = "c", 0, 0
            assert run("concept", "add", name, "--means", "meaning 0", "--by", "kim", "--target", tmp)[0] == 0
            write(os.path.join(tmp, "proposals.json"), {"relations": [{"src": "plan.md#Q1", "predicate": "realizes", "dst": "concept:c", "evidence": "the rule."}]})
            assert run("confirm", "proposals.json", "--by", "kim", "--target", tmp)[0] == 0
            assert run("cq", "add", "q", "--text", "what is c?", "--verify", '{"kind": "answered-by", "concepts": ["c"]}', "--by", "kim", "--target", tmp)[0] == 0
            expect = {"rel_history": 0, "concept_history": 0, "cq_history": 0}
            # who last confirmed the relation and whether an end has moved since: a re-read of a fresh relation by the same
            # person records nothing ("already fresh"); another person's re-read, or any re-read of a stale relation, is recorded
            last_by, stale = "kim", False
            for op in ops:
                rid = mangsang.decl(tmp)["relations"][0]["id"]
                if op == "reconfirm":
                    code, out = run("reconfirm", rid, "--by", "lee", "--why", "re-read: the sentence still holds", "--target", tmp)
                    assert code == 0, out
                    if stale or last_by != "lee":
                        expect["rel_history"] += 1
                    else:
                        assert "already fresh" in out and rid in out, (ops, op, out)
                    last_by, stale = "lee", False
                elif op == "revise":
                    means_n += 1
                    assert run("concept", "revise", name, "--means", "meaning %d" % means_n, "--by", "kim", "--target", tmp)[0] == 0
                    expect["concept_history"] += 1
                elif op == "rename":
                    new = name + "x"
                    code, out = run("concept", "rename", name, new, "--target", tmp)
                    assert code == 0, out
                    name = new
                elif op == "cq-revise":
                    assert run("cq", "revise", "q", "--text", "what is %s?" % name, "--by", "kim", "--target", tmp)[0] == 0
                    expect["cq_history"] += 1
                elif op == "edit":
                    edits += 1
                    write(os.path.join(tmp, "plan.md"), "# p\n\n## Q1\n\nthe rule.%s\n" % (" more" * edits))
                if op in ("revise", "edit"):
                    stale = True
                d = mangsang.decl(tmp)
                # nothing is lost: one relation, still on the (renamed) concept, its history as long as the reconfirms so far
                assert len(d["relations"]) == 1 and d["relations"][0]["dst"] == "concept:" + name, (ops, op, d["relations"])
                assert len(d["relations"][0].get("history", [])) == expect["rel_history"], (ops, op)
                c = next(x for x in d["concepts"] if x["name"] == name)
                assert len(c.get("history", [])) == expect["concept_history"], (ops, op, c)
                q = next(x for x in d["cq_declared"] if x["id"] == "q")
                assert len(q.get("history", [])) == expect["cq_history"] and q["verify"]["concepts"] == [name], (ops, op, q)
                # the question is never UNANSWERABLE: a rename moved it, a revise or an edit can only make it FAILED (a re-read is due)
                code, out = run("cq", "--target", tmp)
                assert "UNANSWERABLE" not in out, (ops, op, out)
                # a re-confirmation right after a change makes impact green again; then nothing is stale
                if op in ("revise", "edit"):
                    assert run("impact", "--target", tmp)[0] == 1, (ops, op)
                    assert run("reconfirm", rid, "--by", "lee", "--why", "re-read: the sentence still holds", "--target", tmp)[0] == 0
                    expect["rel_history"] += 1  # the relation was stale: recorded whoever re-reads it
                    last_by, stale = "lee", False
                assert run("impact", "--target", tmp)[0] == 0, (ops, op, run("impact", "--target", tmp)[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    prop()


# ---------------------------------------------------------------- 5. invariants are functions of the net, and more relations never make coverage worse

def test_coverage_and_projection_are_deterministic_and_monotone_in_relations():
    need_hypothesis()

    @given(sections=st.integers(min_value=1, max_value=4), covered=st.data())
    @settings(**PROPERTY)
    def prop(sections, covered):
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            write(os.path.join(tmp, "plan.md"), "# p\n\n" + "".join("## Q%d\n\nrule %d.\n\n" % (i, i) for i in range(sections)))
            assert run("register", "plan.md", "--target", tmp)[0] == 0
            assert run("concept", "add", "c", "--means", "a meaning", "--by", "kim", "--target", tmp)[0] == 0
            assert run("cq", "add", "owned", "--text", "every section owned?", "--verify", '{"kind": "coverage", "predicate": "realizes", "anchors": "plan.md#Q*", "as": "src"}', "--by", "kim", "--target", tmp)[0] == 0
            assert run("cq", "add", "grounded", "--text", "every concept written?", "--verify", '{"kind": "projection", "media": {"written": ["plan.md#"]}}', "--by", "kim", "--target", tmp)[0] == 0
            order = covered.draw(st.permutations(list(range(sections))))
            k = covered.draw(st.integers(min_value=0, max_value=sections))
            uncovered_before = None
            for step, i in enumerate(order[:k]):
                write(os.path.join(tmp, "proposals.json"), {"relations": [{"src": "plan.md#Q%d" % i, "predicate": "realizes", "dst": "concept:c", "evidence": "rule %d." % i}]})
                assert run("confirm", "proposals.json", "--by", "kim", "--target", tmp)[0] == 0
                d = mangsang.decl(tmp)
                files, _ = mangsang.snapshot(tmp, d["registry"])
                all_anchors = ["%s%s" % (f, kk) for f, ks in files.items() for kk in ks]
                own = next(q for q in d["cq_declared"] if q["id"] == "owned")
                ok1, detail1 = mangsang.eval_invariant(d, files, all_anchors, own)
                ok2, detail2 = mangsang.eval_invariant(d, files, all_anchors, own)
                assert (ok1, detail1) == (ok2, detail2), "the same net must give the same answer twice"
                uncovered = sections - (step + 1)
                assert ok1 == (uncovered == 0) and ("%d uncovered" % uncovered) in detail1, (sections, order, step, detail1)
                assert uncovered_before is None or uncovered < uncovered_before, "another relation never uncovers a section"
                uncovered_before = uncovered
                grounded = next(q for q in d["cq_declared"] if q["id"] == "grounded")
                okg, _ = mangsang.eval_invariant(d, files, all_anchors, grounded)
                assert okg, "one projection in the medium grounds the concept"
            if k == 0:
                assert run("check", "--target", tmp)[0] == 1   # nothing covered, nothing grounded: red, honestly
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    prop()


# ---------------------------------------------------------------- 6. a question stands on exactly what a change would reach it from

def test_reach_is_the_reverse_of_where_a_change_travels():
    need_hypothesis()
    kinds = {"needs": "dst->src", "feeds": "src->dst", "twin": "both", "names": "none"}

    @given(edges=st.lists(st.tuples(st.integers(0, 4), st.sampled_from(sorted(kinds)), st.integers(0, 4)), max_size=8), start=st.integers(0, 4))
    @settings(**PROPERTY)
    def prop(edges, start):
        d = {"vocabulary": {k: {"propagates": v} for k, v in kinds.items()},
             "relations": [{"id": "R%d" % i, "src": "concept:c%d" % a, "predicate": p, "dst": "concept:c%d" % b} for i, (a, p, b) in enumerate(edges) if a != b]}
        got = set(mangsang.reach(d, ["c%d" % start]))
        # independently: X is reached iff a change at X travels, relation by relation, to the start
        def moves(frm):   # the concepts a change at `frm` makes stale, one step
            out = set()
            for r in d["relations"]:
                s_, t = r["src"][8:], r["dst"][8:]
                pr = kinds[r["predicate"]]
                if t == frm and pr in ("dst->src", "both"): out.add(s_)
                if s_ == frm and pr in ("src->dst", "both"): out.add(t)
            return out
        want = set()
        for x in ("c%d" % i for i in range(5)):
            seen, frontier = set(), {x}
            while frontier:
                seen |= frontier
                frontier = set().union(*(moves(f) for f in frontier)) - seen
            if "c%d" % start in seen and x != "c%d" % start:
                want.add(x)
        assert got == want, (edges, start, got, want)

    prop()


# ---------------------------------------------------------------- 7. beside a registered file, no code or config is silent

POOL = ["plugin/a.py", "plugin/b.py", "plugin/c.json", "plugin/d.md", "plugin/sub/e.py", "plugin/sub/f.yaml", "plugin/sub/deep/g.py", "plugin/sub/h.md"]
EXCEPTS = ["plugin/sub/*", "plugin/*.json", "plugin/sub/deep/g.py", "plugin/*.md", "plugin/b.py"]


def test_beside_a_registered_file_no_code_or_config_is_silent():
    """Whatever the registered files, the `registered` invariant's paths (the registered files, a folder, or both) and its
    excepts: every tracked code or config file in a registered file's folder below the root is registered, asked by the
    invariant (FAILED lists it), excepted by a glob, or said unseen — and said at most once (beside, or as a directory
    nothing is registered in). The root's own files are never said unseen (every project's manifests), so none is drawn. A probe of six source models, 11-06, generalized: four of them named files and a new sibling was asked by nothing."""
    need_hypothesis()

    @given(reg=st.sets(st.sampled_from(POOL[1:]), max_size=4), files_only=st.booleans(), folder=st.sampled_from(["", "plugin/sub/", "plugin/"]),
           excepts=st.sets(st.sampled_from(EXCEPTS), max_size=3))
    @settings(**dict(PROPERTY, max_examples=40))
    def prop(reg, files_only, folder, excepts):
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            for p in POOL:
                write(os.path.join(tmp, p), "{}\n" if p.endswith(".json") else "k: 1\n" if p.endswith(".yaml") else "# t\n" if p.endswith(".md") else "X = 1\n")
            git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp, capture_output=True, text=True)
            git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
            registered = sorted({"plugin/a.py"} | reg)
            assert run("register", *registered, "--target", tmp)[0] == 0
            paths = (registered if files_only else []) + ([folder] if folder else [])
            if paths:
                verify = {"kind": "registered", "paths": paths, "except": sorted(excepts)}
                assert run("cq", "add", "scope", "--text", "?", "--verify", json.dumps(verify), "--by", "kim", "--target", tmp)[0] == 0
            d = mangsang.decl(tmp)
            active = [q for q in mangsang.cq_active(d) if q.get("verify", {}).get("kind") in mangsang.INVARIANT_KINDS]
            _, near, blind, _ = mangsang.unseen_groups(tmp, d, active)
            said = [f for g in near + blind for f in g["files"]]
            assert len(said) == len(set(said)), ("said twice", near, blind)
            failed = set(mangsang.unregistered(tmp, d, paths, sorted(excepts))) if paths else set()
            import fnmatch
            for f in POOL:
                if f.endswith(".md") or f in registered:
                    continue
                accounted = f in failed or f in said or (paths and any(fnmatch.fnmatch(f, g) for g in excepts))
                assert accounted, ("silent", f, registered, paths, sorted(excepts), near, blind)
                assert not (f in failed and f in said), ("both red and unseen", f)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    prop()


# ---------------------------------------------------------------- 8. an except's breadth is said, never changed

def test_any_depth_said_on_purpose_matches_the_same_and_crossing_is_exactly_what_segments_refuse():
    """What an except matches is fnmatch's, unchanged: writing `**` for each `*` matches exactly the same paths. `glob_crosses`
    is true exactly when fnmatch matches and a segment-by-segment match would not — never for a glob holding `**`."""
    need_hypothesis()
    import fnmatch
    seg = st.sampled_from(["a", "b", "x.py", "y.json", "*", "*.py", "a*", "?"])
    path = st.lists(st.sampled_from(["a", "b", "x.py", "y.json", "ab"]), min_size=1, max_size=4).map("/".join)

    @given(glob=st.lists(seg, min_size=1, max_size=3).map("/".join), p=path)
    @settings(**PROPERTY)
    def prop(glob, p):
        anydepth = glob.replace("*", "**")
        assert fnmatch.fnmatch(p, glob) == fnmatch.fnmatch(p, anydepth), (glob, p)
        segmentwise = len(p.split("/")) == len(glob.split("/")) and all(fnmatch.fnmatch(x, g) for x, g in zip(p.split("/"), glob.split("/")))
        assert mangsang.glob_crosses(p, glob) == (fnmatch.fnmatch(p, glob) and not segmentwise and any(c in glob for c in "*?[")), (glob, p)
        assert not mangsang.glob_crosses(p, anydepth) or "*" not in glob, (glob, p)

    prop()


def test_a_reasoned_except_hides_exactly_what_its_glob_does():
    """mangsang M1, 11-06: an except entry is a glob string or {"glob", "why"}; the reason changes nothing it matches. Whatever
    the registered files, the invariant's paths and its excepts, writing any subset of the excepts as objects gives the same
    unregistered files, the same unseen files, the same files hidden per glob and the same `check` exit code as all strings."""
    need_hypothesis()
    assert callable(getattr(mangsang, "except_entries", None)), "mangsang.except_entries is missing: an except cannot carry its reason"
    import traceback
    WHYS = ["generated by the build", "vendored as is", "생성됨 — not the net's", "x"]

    @given(reg=st.sets(st.sampled_from(POOL[1:]), max_size=4), files_only=st.booleans(), folder=st.sampled_from(["", "plugin/sub/", "plugin/"]),
           excepts=st.lists(st.sampled_from(EXCEPTS), min_size=1, max_size=4, unique=True), which=st.data())
    @settings(**dict(PROPERTY, max_examples=40))
    def prop(reg, files_only, folder, excepts, which):
        reasoned = [{"glob": g, "why": which.draw(st.sampled_from(WHYS))} if which.draw(st.booleans()) else g for g in excepts]
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            for p in POOL:
                write(os.path.join(tmp, p), "{}\n" if p.endswith(".json") else "k: 1\n" if p.endswith(".yaml") else "# t\n" if p.endswith(".md") else "X = 1\n")
            git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp, capture_output=True, text=True)
            git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")
            registered = sorted({"plugin/a.py"} | reg)
            assert run("register", *registered, "--target", tmp)[0] == 0
            paths = (registered if files_only else []) + ([folder] if folder else []) or registered

            def observe(ex):
                code, out = run("cq", "revise" if os.path.exists(os.path.join(tmp, "mangsang", "cq", "scope.json")) else "add", "scope", "--text", "?",
                                "--verify", json.dumps({"kind": "registered", "paths": paths, "except": ex}), "--by", "kim", "--target", tmp)
                assert code == 0, ("refused", ex, out)
                try:
                    d = mangsang.decl(tmp)
                    q = next(x for x in d["cq_declared"] if x["id"] == "scope")
                    active = [x for x in mangsang.cq_active(d) if x.get("verify", {}).get("kind") in mangsang.INVARIANT_KINDS]
                    _, near, blind, _ = mangsang.unseen_groups(tmp, d, active)
                    hides = {g: sorted(fs) for g, fs in mangsang.except_hides(tmp, d, q["verify"]).items()}
                    return (sorted(mangsang.unregistered(tmp, d, paths, ex) or []), sorted(f for g in near + blind for f in g["files"]), hides,
                            run("check", "--target", tmp)[0])
                except Exception:
                    raise AssertionError("crashed on %r:\n%s" % (ex, traceback.format_exc()))

            as_strings = observe(list(excepts))
            as_reasoned = observe(reasoned)
            assert as_reasoned == as_strings, (registered, paths, reasoned, as_strings, as_reasoned)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    prop()


# ---------------------------------------------------------------- 9. a required invariant holds exactly while what it names stands

def test_a_required_invariant_holds_exactly_while_what_it_names_stands():
    """Any sequence of retiring and re-confirming a projection, marking a concept drifted, reaffirming it, retiring and asking
    a question again: a `required` invariant over any part of the model holds exactly when each concept it names is declared,
    unmarked, owes nothing and is realized, each question is asked, and each relation is live — the semantics a project's
    own checker had to rebuild (three of six rebuilt them wrong, 11-05)."""
    need_hypothesis()
    ops = st.lists(st.tuples(st.sampled_from(["retire", "confirm", "drift", "reaffirm", "retire-q", "ask-q"]), st.integers(0, 2)), max_size=7)

    @given(seq=ops, need=st.tuples(st.sets(st.integers(0, 2)), st.sets(st.integers(0, 2)), st.sets(st.integers(0, 2))).filter(lambda t: any(t)))
    @settings(**dict(PROPERTY, max_examples=40))
    def prop(seq, need):
        tmp = tempfile.mkdtemp(prefix="mangsang-prop-")
        try:
            write(os.path.join(tmp, "plan.md"), "# p\n\n" + "".join("## Q%d\n\nrule %d.\n\n" % (i, i) for i in range(3)))
            assert run("register", "plan.md", "--target", tmp)[0] == 0
            for i in range(3):
                assert run("concept", "add", "c%d" % i, "--means", "rule %d holds." % i, "--by", "kim", "--target", tmp)[0] == 0
            props = lambda i: {"relations": [{"src": "plan.md#Q%d" % i, "predicate": "realizes", "dst": "concept:c%d" % i, "evidence": "rule %d." % i}]}
            for i in range(3):
                write(os.path.join(tmp, "p.json"), props(i))
                assert run("confirm", "p.json", "--by", "kim", "--target", tmp)[0] == 0
                assert run("cq", "add", "q%d" % i, "--text", "?", "--verify", json.dumps({"kind": "answered-by", "concepts": ["c%d" % i]}), "--by", "kim", "--target", tmp)[0] == 0
            nc, nq, nr = need
            verify = {"kind": "required", "concepts": ["c%d" % i for i in sorted(nc)], "questions": ["q%d" % i for i in sorted(nq)],
                      "relations": [{"src": "plan.md#Q%d" % i, "predicate": "realizes", "dst": "concept:c%d" % i} for i in sorted(nr)]}
            verify = {k: v for k, v in verify.items() if v or k == "kind"}
            assert run("cq", "add", "keep", "--text", "?", "--verify", json.dumps(verify), "--by", "kim", "--target", tmp)[0] == 0, "it stands when declared"
            live, drift, owes, asked = [True] * 3, [False] * 3, [False] * 3, [True] * 3
            for op, i in seq:
                rid = mangsang.rel_id({"src": "plan.md#Q%d" % i, "predicate": "realizes", "dst": "concept:c%d" % i})
                if op == "retire" and live[i]:
                    assert run("retire", rid, "--why", "w", "--target", tmp)[0] == 0
                    live[i], owes[i] = False, True
                elif op == "confirm" and not live[i] and not drift[i]:
                    write(os.path.join(tmp, "p.json"), props(i))
                    assert run("confirm", "p.json", "--by", "kim", "--target", tmp)[0] == 0
                    live[i] = True
                elif op == "drift" and not drift[i]:
                    assert run("concept", "drift", "c%d" % i, "--why", "w", "--by", "kim", "--target", tmp)[0] == 0
                    drift[i] = True
                elif op == "reaffirm" and (drift[i] or owes[i]):
                    assert run("concept", "reaffirm", "c%d" % i, "--by", "kim", "--why", "read against what realizes it now", "--target", tmp)[0] == 0
                    drift[i] = owes[i] = False
                elif op == "retire-q" and asked[i]:
                    assert run("cq", "retire", "q%d" % i, "--why", "w", "--target", tmp)[0] == 0
                    asked[i] = False
                elif op == "ask-q" and not asked[i]:
                    assert run("cq", "revise", "q%d" % i, "--by", "kim", "--target", tmp)[0] == 0   # a revise asks a retired question again
                    asked[i] = True
                want = all(live[i] and not drift[i] and not owes[i] for i in nc) and all(asked[i] for i in nq) and all(live[i] for i in nr)
                d = mangsang.decl(tmp)
                files, _ = mangsang.snapshot(tmp, d["registry"])
                keep = next(q for q in d["cq_declared"] if q["id"] == "keep")
                ok, detail = mangsang.eval_invariant(d, files, [], keep, tmp)
                assert ok == want, (seq, need, op, i, detail)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    prop()


# ---------------------------------------------------------------- 10. an edit inside an anchor moves nothing `edit_reach` did not predict

PY_NAMES = ["a", "b", "c", "d", "e", "f", "g", "h"]
MD_TITLES = ["A", "B", "C", "D", "E", "F", "G", "H"]


def python_of(decls):
    """decls: [(name, is_def, n, reads)] -> the file: `name = n`, or a def returning n plus the names it reads."""
    return "\n\n".join("def %s():\n    return %s\n" % (name, " + ".join([str(n)] + list(reads))) if is_def else "%s = %d\n" % (name, n)
                       for name, is_def, n, reads in decls)


if HYPOTHESIS:
    @st.composite
    def python_edits(draw):
        """2–8 top-level declarations with distinct names, constants or defs that read some of the others; K, whose literal changes."""
        names = draw(st.lists(st.sampled_from(PY_NAMES), unique=True, min_size=2, max_size=8))
        decls = []
        for name in names:
            is_def = draw(st.booleans())
            n = draw(st.integers(min_value=0, max_value=9))
            reads = draw(st.lists(st.sampled_from([x for x in names if x != name]), unique=True)) if is_def else []
            decls.append((name, is_def, n, reads))
        return decls, draw(st.integers(min_value=0, max_value=len(decls) - 1))

    @st.composite
    def markdown_edits(draw):
        """A level-1 title, then 2–8 headings at levels 2–4 with distinct titles, a body line under each; K, and a body line inside
        K's own text (K's own, or a subsection's when K encloses it) that changes."""
        titles = draw(st.lists(st.sampled_from(MD_TITLES), unique=True, min_size=2, max_size=8))
        heads = [(1, "t", "title line")] + [(draw(st.integers(min_value=2, max_value=4)), t, draw(st.sampled_from(["x", "y y", "z z z"]))) for t in titles]
        k = draw(st.integers(min_value=1, max_value=len(heads) - 1))
        i = draw(st.sampled_from([k] + [j for j in range(len(heads)) if contains(heads, k, j)]))
        return heads, k, i


def test_an_edit_changes_only_what_edit_reach_predicts():
    """`lookup FILE:KEY` predicts what an edit inside KEY stales through `mangsang.edit_reach`; `impact` judges by fingerprints.
    The two agree only if every anchor whose fingerprint an edit inside KEY's own text moves is in edit_reach(KEY) — for
    Python, through what reads K transitively; for Markdown, through what encloses the edited line."""
    need_hypothesis()
    assert callable(getattr(mangsang, "edit_reach", None)), "mangsang.edit_reach is missing"

    @given(case=python_edits())
    @settings(**PROPERTY)
    def prop_python(case):
        decls, k = case
        name, is_def, n, reads = decls[k]
        edited = list(decls)
        edited[k] = (name, is_def, n + 1, reads)   # the literal changes; K stays the same anchor
        before, after = python_of(decls), python_of(edited)
        fb, fa = mangsang.anchors_of("p.py", before), mangsang.anchors_of("p.py", after)
        assert set(fb) == set(fa), (before, after)
        moved = {key for key in fb if fb[key] != fa[key]}
        reach = mangsang.edit_reach("p.py", before, ":" + name)
        assert ":" + name in moved and moved <= reach, (before, name, moved, reach)

    @given(case=markdown_edits())
    @settings(**PROPERTY)
    def prop_markdown(case):
        heads, k, i = case
        edited = list(heads)
        edited[i] = (heads[i][0], heads[i][1], heads[i][2] + " more")
        before, after = markdown_of(heads), markdown_of(edited)
        fb, fa = mangsang.anchors_of("doc.md", before), mangsang.anchors_of("doc.md", after)
        assert set(fb) == set(fa), (before, after)
        moved = {key for key in fb if fb[key] != fa[key]}
        reach = mangsang.edit_reach("doc.md", before, "#" + heads[k][1])
        assert "#" + heads[k][1] in moved and moved <= reach, (before, k, i, moved, reach)

    prop_python()
    prop_markdown()


# ---------------------------------------------------------------- a renamed heading is carried only when nothing else in its section changed

def test_a_renamed_heading_is_carried_only_when_the_rest_of_its_section_is_what_was_confirmed():
    """`move` carries a relation on a heading renamed in place through `mangsang.renamed_heading`. Generate a document, rename
    one heading, and change nothing else — or its body, another section's body, its level, a heading inside its extent, its
    body removed. The renamed heading is found exactly when its section, its title put back, is the confirmed section's text
    (up to trailing blank lines) and no other heading of the file is found the same way; whatever heading it returns, that
    section with its title put back is the confirmed text — so whenever it carries a relation, nothing but the title changed."""
    need_hypothesis()
    assert callable(getattr(mangsang, "renamed_heading", None)), "mangsang.renamed_heading is missing"

    def trimmed(text):
        lines = text.split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    def put_back(section, new, old):
        first, _, rest = section.partition("\n")
        assert first.endswith(" " + new), (first, new)
        return first[: len(first) - len(new)] + old + ("\n" + rest if _ else "")

    @given(heads=headings, data=st.data())
    @settings(**PROPERTY)
    def prop(heads, data):
        titles = {t for _, t, _ in heads}
        i = data.draw(st.integers(min_value=0, max_value=len(heads) - 1))
        new = data.draw(st.text(alphabet="abcdefghij", min_size=1, max_size=4).filter(lambda t: t not in titles))
        level, old, body = heads[i]
        original = markdown_of(heads)
        seen = mangsang.anchors_of("doc.md", original)["#" + old]
        edit = data.draw(st.sampled_from(["nothing", "body", "other body", "level", "heading inside", "body removed"]))
        edited = list(heads)
        edited[i] = (level, new, body)
        if edit == "body":
            edited[i] = (level, new, body + " more")
        elif edit == "other body" and len(heads) > 1:
            j = data.draw(st.sampled_from([k for k in range(len(heads)) if k != i]))
            edited[j] = (heads[j][0], heads[j][1], heads[j][2] + " more")
        elif edit == "level":
            edited[i] = (data.draw(st.sampled_from([l for l in (1, 2, 3) if l != level])), new, body)
        elif edit == "heading inside":
            edited.insert(i + 1, (min(level + 1, 6), "ZZ", "w"))
        elif edit == "body removed":
            edited[i] = (level, new, "")
        text = markdown_of(edited)
        got = mangsang.renamed_heading("doc.md", text, "#" + old, seen)
        want_section = trimmed(mangsang.anchor_texts("doc.md", original)["#" + old])
        now = mangsang.anchor_texts("doc.md", text)
        found = []
        for _, t, _ in edited:   # every heading of the edited file that, its title put back to the old one, is the confirmed section
            if ("#" + t) in now and trimmed(put_back(now["#" + t], t, old)) == want_section:
                found.append("#" + t)
        # the one such heading, else none (renamed_heading's own rule: two such headings are ambiguous); when another heading's
        # section is the confirmed text too, that is the one found or the rename is ambiguous — never a section that changed
        expected = found[0] if len(found) == 1 else None
        assert got == expected, (original, text, edit, old, new, got, found)
        if got is not None:
            title = got[1:]
            assert trimmed(put_back(now[got], title, old)) == want_section, (text, got)
        if found == ["#" + new]:
            assert got == "#" + new, (original, text, edit, got)
        if "#" + new not in found:
            assert got != "#" + new, ("the renamed section changed beyond its title", original, text, edit)

    prop()


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
            except (Exception, SystemExit) as err:
                failed += 1
                print("FAIL", name, "--", "%s: %s" % (type(err).__name__, str(err)[:1500]))
    print("all passed" if not failed else "%d failed" % failed)
    sys.exit(1 if failed else 0)
