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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mangsang  # noqa: E402

try:
    from hypothesis import HealthCheck, given, settings, strategies as st
    HYPOTHESIS = True
except ImportError:   # the property tests need a generator; without one they say so instead of passing silently
    HYPOTHESIS = False


class Skip(Exception):
    """Raised by a test that cannot run on this host; the runner reports it as SKIP, never as PASS."""


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
    kinds = {"documents": "dst->src", "verifies": "dst->src", "references": "none", "realizes": "both"}
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
            for op in ops:
                rid = mangsang.decl(tmp)["relations"][0]["id"]
                if op == "reconfirm":
                    code, out = run("reconfirm", rid, "--by", "lee", "--target", tmp)
                    assert code == 0, out
                    expect["rel_history"] += 1
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
                    assert run("reconfirm", rid, "--by", "lee", "--target", tmp)[0] == 0
                    expect["rel_history"] += 1
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
                assert run("confirm", "proposals.json", "--delegated", "prop", "--target", tmp)[0] == 0
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
