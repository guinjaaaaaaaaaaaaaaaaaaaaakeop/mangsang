"""mangsang — the net-shaped model (網狀): named concepts, their projections into documents, code and tests, and what went stale.

The net is primary; prose documents are one projection of it, not the source of truth. A concept is declared once
(`concept add NAME --means "..."`), lives at the anchor `concept:NAME`, and survives any rename of the files and
sections that realize it. Relations tie projections to concepts (`realizes`) and artifacts to each other
(`documents`, `verifies`); staleness is judged against what a confirmer saw, per anchor fingerprint.

  register <path>...            watch these files (anchors: `file`; `file#heading` for Markdown; `file:symbol` for Python, JS/TS, CSS/SCSS,
                                HTML and Astro/Vue/Svelte, SQL, Prisma/GraphQL/proto, Dockerfile; `file:key` for JSON, YAML, TOML, INI and
                                .env files, nested keys dotted — see anchors.py for the one rule behind them)
  source add ID --file F|- --speaker WHO [--locator L] [--replies-to ID]
  source add ID --from-transcript JSONL --match PHRASE|--turn ID [--kind person|agent|question|answer]
                                (a typed reply right after the agent's turn is a person turn and an answer both, an agent's text turn
                                asking the person an agent turn and a question both; the person's turn is the roster's one person
                                when people.json lists one; a choice picked in a
                                question form is only what the person picked or typed, one turn per question (ID#k), its locator naming
                                the question — never the tool's wrapper; a miss says which turns are there, or where in the record the
                                phrase is, and the ids to name one by)
                                keep what was said or written, verbatim and unchangeable, as the anchor `source:ID` — a concept
                                grounded in a conversation relates to it like to any projection, with a quote as evidence. Both
                                sides of a conversation are sources: "yes, both" means nothing without the question it answers
  concept [add|revise|reaffirm|drift|rename|list|show] declare/change the net's own nodes (`show NAME`: one concept whole — meaning, relations
                                in and out with their state, what it owes, its questions, its sources); `concept:NAME` anchors relations; revising `means` stales every
                                projection; retiring a projection leaves the concept owing a re-read (`owes`) until `revise` or `reaffirm`;
                                `drift NAME --why` marks a sentence known wrong whose revision waits: cq DRIFTED, its relations not re-confirmed
  concept list --brief          the net as a map in a line or two: `N concept(s): a, b, … ; M open question(s)` (names cut to fit ~300
                                characters), then how many relations are stale or broken when any are, and how many tracked files
                                are unseen and how many registered ones nothing relates to (by directory, the recently changed
                                first); an empty net prints nothing
  confirm <proposals.json> --by NAME | --delegated WHY
                                store relations after checking: anchors exist, predicate is in the vocabulary, no duplicates; the
                                rejected stay in the file, each with why (a file not registered: its `register` command) — fix, run again
  observe [--reset [--at REV]]  this machine's change list: --reset takes a baseline (from git at REV if given), otherwise prints what moved since it
  impact [--findings] [--only ANCHOR-PREFIX...]
                                observe, then events x relations -> stale / broken (grouped by file when the file is gone), and the concepts
                                owing a re-read (`owed`; cq fails them). exit 1 when anything is unresolved (usable as a check);
                                --only judges only relations touching those anchors (a slice's check); --findings prints `dwitbuk/findings@1`
  judge request --out DIR [--ids ID...]   the stale relations as a packet: the possibly-stale text, the changed text, the quote confirmed.
                                DIR is a directory (an existing one is used as is): the packet is DIR/judge-request.json, its path printed;
                                an earlier round's request and response there are moved aside, named by their time
  judge consume --response FILE [--by WHO [--approved-in source:ID]] [--judge "HOST MODEL"]
                                the judge's verdicts: still-true -> re-confirmed as `{judge: "<host> <model>", applied-by: ...}` — the
                                judge from the response's worker record, the applier the agent running this unless --by names one; a
                                person's name there, at an agent's hand, needs --approved-in (where they read the verdicts). drifted
                                (with a quote from the text) and cannot-tell -> printed for a human; judge_worker.py runs one packet
  cq [run]                      ask the competency questions; audits both directions — a question whose presuppositions fail is UNANSWERABLE
                                (the model moved out from under it), model content no question examines is UNQUESTIONED; exit 1 on any of the three.
                                A question declared `{"kind": "open"}` is asked before anything answers it: listed OPEN, an observation, not a failure
  cq add|revise|retire ID       declare a question (--text + --verify JSON, --by|--delegated) — refused if it cannot be asked of the current model;
                                retiring keeps the record (--why). One file per CQ under mangsang/cq/; legacy cq.json still read
  report [--out FILE] [--html FILE]
                                the net as one page for a person: concepts and what realizes them, the questions and their state,
                                the sources; a Mermaid graph. Markdown, or --html: one self-contained file whose graph draws in any
                                browser with no network (mermaid is vendored and inlined). Read-only — derived, not committed
  retire <id> --why WHY         drop a relation, keeping it (and why) in `retired`
  retire --gone FILE.. --why WHY
                                files deleted on purpose (or a directory): every relation on them retired with that one reason, the
                                files unregistered, the concepts that lost a projection owing a re-read; a path still in the tree is
                                refused. `impact` groups broken relations by a deleted file and prints this command
  lookup <path>                 before touching a file: the confirmed relations standing on it, grouped by concept (its meaning once),
                                each with its quote, its confirmer and fresh/stale now; or which of not registered / registered with
                                nothing on it / not in the tree (read-only) — size the edit as code + relations. Also an anchor
                                (`concept:NAME`, `file:symbol`), or a relation id (that relation, whole)
  lookup <path> --brief         the same as at most five lines, one per concept (or other end) reached: its meaning's first sentence
                                (and the next, when the first is a bare name like "첫 화면."), cut at ~160 characters,
                                and `(N relation(s); K stale)` when any is stale; no ids, no quotes. A tracked file the net does not see
                                gets one line; registered with nothing on it, or not in the tree, prints nothing — a reader's first look
  move [ID...] --by NAME | --delegated WHY [--dry-run]   after a refactoring: a broken relation whose dead `file:symbol` / `file#heading` has exactly one
                                new home is retired (why: moved) and re-confirmed there with the same evidence; ambiguous or homeless ones are left for a person
  reconfirm <id>... [--by NAME | --delegated WHY] [--evidence "..."]
                                a re-read stale relation still holds: `seen` becomes what the tree has now; the evidence must still be in the text.
                                Run by an agent with neither flag, it is the agent's own re-read, signed `{agent: ...}` — never a person's name

Two places. `mangsang/` is the project's knowledge (registry, vocabulary, cq, one file per relation) — committed, changed only when a human
confirms. `.mangsang/` holds this machine's baseline for `observe` — not committed, and nothing a judgment depends on: staleness is judged
against `seen` in each relation, so a fresh clone answers the same as the machine that confirmed.
mangsang never proposes a relation and never judges meaning; it checks, stores, fingerprints and diffs.
`source add` keeps what people said as anchors (`mangsang/sources/<id>.json`); a model can be grounded in a conversation as
well as in a plan, and the same quote rule holds.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import uuid

import anchors   # what in a file can be named, how far it reaches, what it reads — one module per rule, one scanner per language

DECL = "mangsang"
OBS = ".mangsang"
DELEGATION_REF = re.compile(r"^D-[0-9a-f]+$")


APPROVED_IN = None   # set by main when an agent signs in a person's name: the source where that person approved
APPROVAL_OF = None   # and, when that approval answers an agent's own words (a proposal), the source it answers
AGENT_ENV = ("CLAUDECODE", "CODEX_THREAD_ID", "AGENT_WORKER", "CLAUDE_CODE_SESSION_ID", "AGENT_HOST")


def session_model():
    """The model of the Claude Code session running this command, from the host's own record of it (the session's JSONL,
    found by CLAUDE_CODE_SESSION_ID): the model of its latest agent message. None when the host gives no session or the
    record is not where it keeps them."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid or not re.fullmatch(r"[\w-]+", sid):
        return None
    root = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "projects")
    try:
        paths = [os.path.join(root, x, sid + ".jsonl") for x in os.listdir(root)]
    except OSError:
        return None
    for path in (x for x in paths if os.path.isfile(x)):
        with io.open(path, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - (1 << 20)))   # the latest megabyte: the latest agent message is near the end
            lines = fh.read().decode("utf-8", "replace").splitlines()
        for line in reversed(lines):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            model = isinstance(d, dict) and d.get("type") == "assistant" and (d.get("message") or {}).get("model")
            if model and isinstance(model, str) and not model.startswith("<"):   # "<synthetic>": the host's own note
                return model
    return None


def running_agent():
    """The agent running this command, named from its host's env (None at a person's terminal). Not a person's name: what an
    agent does on its own is signed as the agent's, so it stops wearing the person's. A Claude Code session is named by its
    model, as its turns are kept (`Claude (<model>)`) — guin-site, 10-15: `judge consume` printed "applied by Claude Code",
    which says no model; "Claude Code" only when the host's record of the session is not found.
    Read the host's env now: stripped, case-sensitive AGENT_HOST wins over inherited markers (a worker host call sets it to
    the child's host and keeps the parent's CLAUDECODE). codex uses its thread or "Codex"; claude-code uses its recorded
    model or "Claude Code". An unknown host is "an agent worker" with AGENT_WORKER, else "an agent". With no host,
    infer CODEX_THREAD_ID, then CLAUDECODE, then AGENT_WORKER, else None."""
    host = os.environ.get("AGENT_HOST", "").strip()
    if host == "codex":
        thread = os.environ.get("CODEX_THREAD_ID")
        return "Codex (thread %s)" % thread if thread else "Codex"
    if host == "claude-code":
        model = session_model()
        return "Claude (%s)" % model if model else "Claude Code"
    if host:
        return "an agent worker" if os.environ.get("AGENT_WORKER") else "an agent"
    if os.environ.get("CODEX_THREAD_ID"):
        return "Codex (thread %s)" % os.environ["CODEX_THREAD_ID"]
    if os.environ.get("CLAUDECODE"):
        model = session_model()
        return "Claude (%s)" % model if model else "Claude Code"
    if os.environ.get("AGENT_WORKER"):
        return "an agent worker"
    return None


RECORD_KINDS = ("relations", "retired", "concepts", "cq", "sources")   # the folders whose files are record objects: each says which mangsang wrote it


def signature(by, delegated):
    """The judgment's author line. A --delegated value matching a delegation id (D-xxxx, chongdae's `delegate`)
    is stored as a structured reference — machine-readable, so no reason string is pasted N times — but mangsang
    never resolves it: whose delegation it is and whether it exists is the record-reader's audit (dwitbuk), not
    this engine's coupling. Any other value stays a free-form why-string, as before. A person's name put there by an
    agent cites where the person approved (`approved-in`) and, when that approval is a reply to the agent's own
    proposal, the proposal (`approval-of`): a one-word yes to an agent's list is a weaker ground than the person's own
    words, and the record says which it was."""
    if by:
        return {"by": by, **({"approved-in": APPROVED_IN} if APPROVED_IN else {}), **({"approval-of": APPROVAL_OF} if APPROVED_IN and APPROVAL_OF else {})}
    if delegated and DELEGATION_REF.match(delegated.strip()):
        return {"delegated": {"ref": delegated.strip()}}
    return {"delegated": delegated}
DEFAULT_VOCAB = {
    "documents": {"propagates": "dst->src", "means": "src (a document section) describes dst's behavior; when dst changes the section may be stale"},
    "verifies": {"propagates": "dst->src", "means": "src (a test) proves dst; when dst changes the test may be stale"},
    "references": {"propagates": "none", "means": "src names dst; no content dependency"},
    "realizes": {"propagates": "both", "means": "src (a document section, code or test) is a projection of dst (a concept): src expresses in its medium what the concept means. "
                                                "When the concept's meaning changes every projection may be stale; when a projection changes it may have outgrown the meaning"},
}


def load(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    if isinstance(data, dict) and os.path.basename(os.path.dirname(path)) in RECORD_KINDS and os.path.basename(os.path.dirname(os.path.dirname(path))) == DECL:
        # every record object says which mangsang wrote it — a JSON field, read as one (chongdae's rule for its records):
        # a later version knows the shape it is reading, and a reviewer can see a record written by a build that is no release
        bare = {k: v for k, v in data.items() if k != "written_by"}
        if os.path.exists(path):
            try:
                if {k: v for k, v in load(path).items() if k != "written_by"} == bare:
                    return   # the content is what is on disk: `written_by` names who wrote that content — a newer build re-saving it wrote nothing (every concept file of a project rewritten for a version string)
            except (ValueError, AttributeError):
                pass
        data = {**bare, "written_by": engine()}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


_ENGINE = None


def engine():
    """`mangsang <version>` — with `+g<sha>[-dirty]` when this is a working source, not an installed release, so a record
    never passes an unreleased build off as the release."""
    global _ENGINE
    if _ENGINE is None:
        import subprocess
        root = os.path.dirname(os.path.abspath(__file__))
        v = next((load(os.path.join(root, mf)).get("version") for mf in (os.path.join(".claude-plugin", "plugin.json"), "plugin.json")
                  if load(os.path.join(root, mf)).get("version")), "unknown")
        rev = ""
        try:
            top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
            if top.returncode == 0 and os.path.realpath(top.stdout.strip()) == os.path.realpath(root):
                sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
                dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True).stdout.strip()
                rev = "+g%s%s" % (sha, "-dirty" if dirty else "") if sha else ""
        except OSError:
            pass
        _ENGINE = "mangsang %s%s" % (v, rev)
    return _ENGINE


def decl(target):
    """The project's declarations, read from the `mangsang/` directory.

    One relation = one file (`relations/<id>.json`), so relations added on different branches merge as distinct files.
    A single JSON array was the first design; two people adding to it produced a merge conflict in the first collaboration scene.
    Concepts (`concepts/<name>.json`) are the net's own nodes — one per file for the same reason.
    """
    root = os.path.join(target, DECL)
    d = {"registry": load(os.path.join(root, "registry.json"), []),
         "vocabulary": load(os.path.join(root, "vocabulary.json"), None) or dict(DEFAULT_VOCAB),
         "cq": load(os.path.join(root, "cq.json"), []),
         "relations": [], "retired": [], "concepts": [], "cq_declared": [], "sources": []}
    for kind, key in (("relations", "relations"), ("retired", "retired"), ("concepts", "concepts"), ("cq", "cq_declared"), ("sources", "sources")):
        folder = os.path.join(root, kind)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if name.endswith(".json"):
                d[key].append(load(os.path.join(folder, name)))
    return d


def save_decl(target, d):
    """Write back only what a command changes; relation files are written or moved one by one, never as a set."""
    root = os.path.join(target, DECL)
    save(os.path.join(root, "registry.json"), d["registry"])
    save(os.path.join(root, "vocabulary.json"), d["vocabulary"])
    if d["cq"] or os.path.exists(os.path.join(root, "cq.json")):
        save(os.path.join(root, "cq.json"), d["cq"])   # the legacy list, kept where it exists; a new project gets one file per question and no empty list
    for kind in ("relations", "retired"):
        folder = os.path.join(root, kind)
        have = {n[:-5] for n in os.listdir(folder)} if os.path.isdir(folder) else set()
        want = {r["id"] for r in d[kind]}
        for r in d[kind]:
            if r["id"] not in have or kind == "retired":
                save(os.path.join(folder, r["id"] + ".json"), r)
        for gone in have - want:
            os.remove(os.path.join(folder, gone + ".json"))
    folder = os.path.join(root, "concepts")
    have = {n[:-5] for n in os.listdir(folder)} if os.path.isdir(folder) else set()
    want = {c["name"] for c in d["concepts"]}
    for c in d["concepts"]:
        save(os.path.join(folder, c["name"] + ".json"), c)
    for gone in have - want:
        os.remove(os.path.join(folder, gone + ".json"))


def fp(text, path=None):
    """Fingerprint of an anchor's content — of what `anchors.normalize` leaves of it: for Python and JS/TS the token stream,
    so a comment, blank line or reformatting does not change the fingerprint — only code does (every doc-drift tool that
    ran in anger converged on normalized fingerprints; raw hashes cried stale at formatters); for JSON the canonical value;
    for YAML/TOML/INI/env the comment-free lines; for Markdown and unknown files the text: in prose, wording *is* the
    content. Python token *names* (tok_name), not numbers: 3.12 renumbered the token table and every numeric fingerprint
    changed with it. A fragment that will not tokenize is fingerprinted as text — never silently unfingerprinted."""
    return hashlib.sha256(anchors.normalize(path or "", text).encode("utf-8")).hexdigest()[:12]


def fp_parts(path, parts):
    """The fingerprint of an anchor with what it reads: one part -> its own fingerprint (a constant, a heading, a file: the
    same value as before parts existed, so nothing goes stale for the rule changing); several -> a hash over the parts'
    fingerprints, so a change in any same-file declaration or import the anchor reads changes the anchor's fingerprint."""
    fps = [fp(text, path) for _, text in parts]
    return fps[0] if len(fps) == 1 else hashlib.sha256("\x01".join(fps).encode("utf-8")).hexdigest()[:12]


def fp_legacy_numeric(text, path):
    """The first token fingerprint hashed numeric token types; every `seen` written before the tok_name fix holds these.
    Recomputed only as a compatibility answer in `impact` (bytes unchanged -> not stale); new writes never use it."""
    if not (path and path.endswith(".py")):
        return None   # only Python anchors ever had numeric-token fingerprints
    import tokenize, token as tok
    try:
        toks = ["%d\x00%s" % (t.type, t.string) for t in tokenize.generate_tokens(io.StringIO(text.replace("\r\n", "\n")).readline)
                if t.type not in (tokenize.COMMENT, tokenize.NL, tok.NEWLINE, tokenize.ENCODING, tok.ENDMARKER)]
        return hashlib.sha256("\x01".join(toks).encode("utf-8")).hexdigest()[:12]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None


# ---------------------------------------------------------------- anchors

def anchor_texts(path, text=None):
    """{anchor: own text} for one file (or for `text` as if it were that file). The whole file is always an anchor ("").
    Which declarations become anchors, and how far each one's text reaches, is `anchors.scan` — one rule, a scanner per kind."""
    if text is None:
        text = io.open(path, encoding="utf-8", newline=None).read() if os.path.exists(path) else None
    if text is None:
        return None
    return anchors.scan(path, text).texts


def anchor_parts(path, text=None):
    """{anchor: [(label, text), ...]} — each anchor's own text and, after it, what it reads in the same file (`:name` for
    another declaration, `import name` for an import binding). What a fingerprint covers, and what `--show` diffs."""
    if text is None:
        text = io.open(path, encoding="utf-8", newline=None).read() if os.path.exists(path) else None
    if text is None:
        return None
    return anchors.parts(path, text)


def anchors_of(path, text=None):
    """{anchor: fingerprint} for one file."""
    parts = anchor_parts(path, text)
    return None if parts is None else {k: fp_parts(path, v) for k, v in parts.items()}


def texts_of(target, f):
    """{anchor-key: text} for a file — or for a reserved virtual file: `concept`, whose anchors are the concepts themselves
    and whose text is each concept's `means` sentence; `source`, whose anchors are what people said, verbatim. One reader
    for real and net-own anchors alike."""
    if f == "concept":
        return {":" + c["name"]: c["means"] for c in decl(target)["concepts"]}
    if f == "source":
        return {":" + x["id"]: x["text"] for x in decl(target)["sources"]}
    return anchor_texts(os.path.join(target, f))


def quoted(target, evidence, *anchors):
    """Evidence is a quote: it must appear (whitespace-normalized) in the text of one of the anchors. Paraphrase is not evidence.
    For a `concept:NAME` anchor the text is the concept's `means` sentence — evidence against a concept quotes its meaning."""
    norm = lambda t: " ".join(str(t).split())
    for a in anchors:
        f, key = split_anchor(a)
        texts = texts_of(target, f)
        if texts and key in texts and norm(evidence) in norm(texts[key]):
            return True
    return False


def split_anchor(anchor):
    """'file', 'file#heading', 'file:symbol' -> (file, key). The separator is the leftmost `#` or `:` — a path holds
    neither, a key may hold both (`styles.css:#hero`, `plan.md#Q1: add`, `openapi.yaml:paths./users/{id}`)."""
    # Windows drive letters: only treat ':' as a separator after the first two characters
    cuts = [i for i in (anchor.find("#"), anchor.find(":", 2)) if i > 0]
    if cuts:
        i = min(cuts)
        return anchor[:i], anchor[i:]
    return anchor, ""


def snapshot(target, registry, at=None, concepts=None, sources=None):
    """Anchors of every registered file — from the working tree, or from git at revision `at` (a merge base, a release).
    Concepts enter as a virtual file `concept`: each is an anchor `concept:NAME` whose text is its `means` sentence.
    So the net's own nodes go through the same machinery as everything else — a concept's meaning is fingerprinted,
    relations hold `seen` against it, and changing what a concept *means* makes every projection on it stale.
    Concepts are read from the tree even with `at`: they are the net, not the territory."""
    import subprocess
    files, unreadable = {}, []
    for entry in registry:
        if at:
            done = subprocess.run(["git", "show", "%s:%s" % (at, entry["path"])], cwd=target, capture_output=True)
            got = anchors_of(entry["path"], done.stdout.decode("utf-8", "replace").replace("\r\n", "\n")) if done.returncode == 0 else None
        else:
            got = anchors_of(os.path.join(target, entry["path"]))
        if got is None:
            unreadable.append(entry["path"])
        else:
            files[entry["path"]] = got
    if concepts is None or sources is None:
        d = decl(target)
        concepts = d["concepts"] if concepts is None else concepts
        sources = d["sources"] if sources is None else sources
    if concepts:
        files["concept"] = {":" + c["name"]: fp(c["means"]) for c in concepts}
    if sources:   # what someone said does not change; a source is an anchor that can only die (never stale), like the record it is
        files["source"] = {":" + x["id"]: fp(x["text"]) for x in sources}
    return files, unreadable


# ---------------------------------------------------------------- commands

def cmd_register(args):
    d = decl(args.target)
    have = {e["path"] for e in d["registry"]}
    added = []
    for p in args.paths:
        rel = p.replace(os.sep, "/")
        if not os.path.exists(os.path.join(args.target, rel)):
            raise SystemExit("%s does not exist" % rel)
        if rel not in have:
            d["registry"].append({"path": rel})
            added.append(rel)
    save_decl(args.target, d)
    print("registered %d (%d already): %s" % (len(added), len(args.paths) - len(added), ", ".join(added) or "-"))
    return 0


def rel_id(r):
    return "R-" + hashlib.sha1(("%s|%s|%s" % (r["src"], r["predicate"], r["dst"])).encode("utf-8")).hexdigest()[:8]


def cmd_confirm(args):
    if not (args.by or args.delegated):
        raise SystemExit("say who confirmed (--by) or why the human delegated it (--delegated)")
    d = decl(args.target)
    files, unreadable = snapshot(args.target, d["registry"])
    known = {r["id"] for r in d["relations"]}
    if not os.path.exists(args.proposals):
        args.proposals = os.path.join(args.target, args.proposals)   # relative to the target, like everything else here
    proposals = load(args.proposals).get("relations", [])
    if not proposals:
        raise SystemExit("%s has no `relations`" % args.proposals)
    kept, rejected = [], []
    for p in proposals:
        why = None
        if p.get("predicate") not in d["vocabulary"]:
            why = "predicate %r is not in the vocabulary (%s)" % (p.get("predicate"), ", ".join(d["vocabulary"]))
        for end in ("src", "dst"):
            f, key = split_anchor(p.get(end, ""))
            if f not in files or key not in files[f]:
                why = why or "%s anchor %r does not resolve (%s)" % (end, p.get(end), "file not registered — `register %s` first" % f
                                                                        if f not in files and f not in ("concept", "source") and os.path.exists(os.path.join(args.target, f))
                                                                        else "file not registered" if f not in files else "no such heading/symbol")
        held = drifted_end(d, p.get("src", ""), p.get("dst", ""))
        if held:
            why = why or drift_refusal(d, held)   # the same hazard reconfirm refuses: a new relation quoting the false sentence
        if not str(p.get("evidence", "")).strip():
            why = why or "no evidence — quote the sentence that makes this relation true"
        elif not why and not quoted(args.target, p["evidence"], p["src"], p["dst"]):
            why = "evidence is not a quote from either anchor — quote the sentence (or line) as it is in the text"
        rid = rel_id(p) if not why else None
        if rid and rid in known:
            why = "duplicate of %s" % rid
        if why:
            rejected.append({**p, "why": why})
            continue
        known.add(rid)
        # `seen`: the fingerprints the human confirmed against. Staleness is judged against these, not against a machine's baseline,
        # so a relation confirmed on one branch stays fresh through a merge unless the other branch changed what it saw.
        kept.append({"id": rid, "src": p["src"], "predicate": p["predicate"], "dst": p["dst"], "evidence": p["evidence"],
                     "seen": {a: files[split_anchor(a)[0]][split_anchor(a)[1]] for a in (p["src"], p["dst"])},
                     "confirmed": signature(args.by, args.delegated)})
    d["relations"] += kept
    save_decl(args.target, d)
    # what was confirmed is in relations/; what was rejected stays in the proposals file, each entry with why, so fixing it and
    # running the same command again is the route — the file used to be consumed whole, and guin-site's six rejected
    # proposals (five on a plan document nobody had registered) were left only as printed lines
    if rejected:
        save(args.proposals, {"relations": [{**{k: v for k, v in r.items() if k != "why"}, "rejected": r["why"]} for r in rejected]})
    else:
        os.remove(args.proposals)
    print("confirmed %d / rejected %d (%s)" % (len(kept), len(rejected), "the rejected kept in %s, each with why" % args.proposals if rejected else "proposals file consumed"))
    for r in rejected:
        print("  rejected %s %s %s — %s" % (r.get("src"), r.get("predicate"), r.get("dst"), r["why"]))
    if rejected:
        import shlex
        unreg = sorted({f for r in rejected for f in (split_anchor(r.get("src", ""))[0], split_anchor(r.get("dst", ""))[0])
                        if f and f not in files and f not in ("concept", "source") and os.path.exists(os.path.join(args.target, f))})
        if unreg:
            print("  not registered: `register %s`" % " ".join(shlex.quote(f) for f in unreg))
        print("  fix them (or delete the ones that were wrong) and run `confirm %s --by NAME|--delegated WHY` again — the confirmed ones are not in it any more"
              % shlex.quote(args.proposals))
    return 1 if rejected else 0


def ignore_obs(target):
    """`.mangsang/` is this machine's; the first write says so to git."""
    path = os.path.join(target, ".gitignore")
    lines = io.open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    if OBS + "/" not in lines:
        io.open(path, "a", encoding="utf-8", newline="\n").write(("" if not lines or lines[-1] == "" else "\n") + OBS + "/\n")


def cmd_observe(args):
    ignore_obs(args.target)
    d = decl(args.target)
    files, unreadable = snapshot(args.target, d["registry"])
    base_path = os.path.join(args.target, OBS, "baseline.json")
    if args.at and not args.reset:
        raise SystemExit("--at goes with --reset: a baseline is taken at a revision, a diff is against the tree")
    if args.reset or not os.path.exists(base_path):
        if args.at:
            files, unreadable = snapshot(args.target, d["registry"], at=args.at)   # the merging machine has no past; git does
        save(base_path, {"files": files, "at": args.at})
        print("baseline%s: %d files, %d anchors%s" % (" at %s" % args.at if args.at else "", len(files), sum(len(a) for a in files.values()),
                                                       " · unreadable %s" % unreadable if unreadable else ""))
        return 0
    events = diff_events(load(base_path)["files"], files)
    for path, ev in events.items():
        print("  %-28s changed=%s added=%s removed=%s" % (path, ev["changed"], ev["added"], ev["removed"]))
    # what is printed is the record: an events file was written here and read by nothing (the baseline is the one file a later command needs)
    print("changed files %d / registered %d%s" % (len(events), len(d["registry"]), " · unreadable %s" % unreadable if unreadable else ""))
    return 0


def diff_events(base, files):
    events = {}
    for path in sorted(set(base) | set(files)):
        old, new = base.get(path, {}), files.get(path, {})
        ev = {"changed": sorted(k for k in old if k in new and old[k] != new[k]),
              "added": sorted(k for k in new if k not in old), "removed": sorted(k for k in old if k not in new)}
        if any(ev.values()):
            events[path] = ev
    return events


def compute_impact(target, d, only=None, persist=False):
    """(stale, broken, unjudged, files). Stale = an anchor the relation propagates from differs from what its confirmer saw (`seen`);
    relations without `seen` are judged against this machine's baseline, or listed as unjudged when there is none. Reads the tree
    and the record, writes nothing (`persist` is kept for callers; the events and impact files it once wrote were read by nothing)."""
    base_path = os.path.join(target, OBS, "baseline.json")
    files, _ = snapshot(target, d["registry"])
    ev = diff_events(load(base_path)["files"], files) if os.path.exists(base_path) else None
    unjudged = []

    def alive(anchor):
        f, key = split_anchor(anchor)
        return f in files and key in files[f]

    def touched(anchor, r):
        f, key = split_anchor(anchor)
        if anchor in r.get("seen", {}):
            if files[f][key] == r["seen"][anchor]:
                return False
            # fingerprint-format compatibility: `seen` written before the current format holds an older shape — a raw
            # text hash (pre-token era), a numeric-token hash (pre-tok_name era), or the anchor's own tokens alone (before
            # a fingerprint covered what the anchor reads). If any recomputation over the current bytes equals the stored
            # value, the bytes the confirmer read have not changed — only the fingerprint format did. Not stale; the record
            # upgrades itself on the next confirm/reconfirm. (What the anchor reads may have moved meanwhile; an old
            # `seen` cannot tell, and says so only by being upgraded.)
            texts = texts_of(target, f)
            if not (texts and key in texts):
                return True
            old = r["seen"][anchor]
            # (a Markdown `seen` from before trailing blank lines left the fingerprint was a raw hash of the section as it stood —
            # often the file's last section, ending at one newline: that shape is tried too)
            return not (fp(texts[key]) == old or fp(texts[key], f) == old or fp_legacy_numeric(texts[key], f) == old
                        or (anchors.kind_of(f) == "markdown" and fp(texts[key].rstrip() + "\n") == old))
        if ev is None:
            unjudged.append(r["id"])
            return False
        e = ev.get(f, {})
        return key in e.get("changed", []) or (key == "" and bool(e))

    stale, broken = [], []
    for r in d["relations"]:
        if only and not any(a.startswith(tuple(only)) for a in (r["src"], r["dst"])):
            continue
        dead = [a for a in (r["src"], r["dst"]) if not alive(a)]
        if dead:
            broken.append({"id": r["id"], "dead": dead})
            continue
        prop = d["vocabulary"].get(r["predicate"], {}).get("propagates", "none")
        changed = [a for a, ok in ((r["dst"], prop in ("dst->src", "both")), (r["src"], prop in ("src->dst", "both"))) if ok and touched(a, r)]
        if changed:
            # `because` is the end that actually changed — for `both` it used to name dst whatever had moved, so a section
            # edit read as "<- concept:x" and `--show` went looking for a change in the concept
            other = r["src"] if changed[0] == r["dst"] else r["dst"]
            stale.append({"id": r["id"], "stale": other if len(changed) == 1 else r["src"], "because": changed[0] if len(changed) == 1 else "%s and %s" % (r["src"], r["dst"]),
                          "changed": changed})   # the ends that moved, as anchors — `because` is their name for a reader
    return stale, broken, sorted(set(unjudged)), files


def what_changed(target, r, anchor):
    """The anchor's text as its confirmer saw it and as it reads now, as a unified diff — so a person re-reading a stale
    relation reads the change, not just the fact of one. `seen` keeps fingerprints, not text; git keeps the text: the commit
    that last wrote the relation's file is when it was confirmed, and the anchor is read from the tree at that commit
    (a concept's `means` from its file then). When the anchor's own text is what it was and something it reads moved — a
    constant, a helper, an import — that part is diffed, named. None when there is no such commit (the relation was never
    committed)."""
    import difflib, subprocess
    git = lambda *a: subprocess.run(["git", *a], cwd=target, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for folder in ("relations", "retired"):
        c = git("log", "-1", "--format=%H", "--", "%s/%s/%s.json" % (DECL, folder, r["id"])).stdout.strip()
        if c:
            break
    else:
        return None
    f, key = split_anchor(anchor)
    # `REV:path` in git is the repository root's path; `REV:./path` is this directory's — and a target is often a
    # directory inside a repository (a playground of several models, a project in a monorepo): the first form never
    # found anything there and the message blamed a missing commit
    if f == "concept":
        old = git("show", "%s:./%s/concepts/%s.json" % (c, DECL, key.lstrip(":")))
        old_text = json.loads(old.stdout).get("means") if old.returncode == 0 and old.stdout.strip() else None
        new_text = (texts_of(target, f) or {}).get(key)
        old_parts = [(key, old_text)] if old_text is not None else None
        new_parts = [(key, new_text)] if new_text is not None else None
    elif f == "source":
        return None   # what was said does not change
    else:
        old = git("show", "%s:./%s" % (c, f))
        old_parts = (anchor_parts(f, old.stdout.replace("\r\n", "\n")) or {}).get(key) if old.returncode == 0 else None
        new_parts = (anchor_parts(os.path.join(target, f)) or {}).get(key)
    if old_parts is None or new_parts is None:
        return None
    olds, news = dict(old_parts), dict(new_parts)
    nl = lambda t: t if t.endswith("\n") else t + "\n"   # a concept's meaning is one line with no newline: without one, the - and + lines ran together
    out = []
    for label in [l for l, _ in new_parts] + [l for l, _ in old_parts if l not in news]:
        o, n = olds.get(label, ""), news.get(label, "")
        if o == n:
            continue
        # the anchor itself, another declaration of its file it reads, or an import binding it reads
        name = anchor if label == key else ("%s%s, read by %s" % (f, label, anchor) if not label.startswith("import ") else "%s: `%s`, read by %s" % (f, label, anchor))
        out.append("".join(difflib.unified_diff(nl(o).splitlines(True), nl(n).splitlines(True), "%s @ %s" % (name, c[:8]), "%s @ now" % name, n=1)))
    if not out:
        # the words are the same and the fingerprint is not: the rule that cuts the anchor changed under it (a title heading's
        # section, a token-fingerprint format) — nothing to re-read; a reconfirm records the new fingerprint
        return "(the text of %s is exactly what it was at %s — only its fingerprint's rule changed; nothing to re-read)" % (anchor, c[:8])
    return "".join(out)


def unread_by_a_person(sig):
    """How a relation was re-confirmed when no person read it (None when one did): by delegation, by a judge's verdict
    applied, or by the agent on its own."""
    if sig.get("delegated"):
        dl = sig["delegated"]
        return "by delegation: %s" % (("ref " + dl["ref"]) if isinstance(dl, dict) else dl)
    if sig.get("judge") and not sig.get("approved-in"):
        return "by the judge %s, applied by %s: %s" % (sig["judge"], sig.get("applied-by") or "?", sig.get("why", ""))
    if sig.get("agent"):
        return "by the agent %s, on its own" % sig["agent"]
    return None


def homes_of(files, anchor):
    """The registered files of the same kind, other than its own, that have a dead `file:symbol` / `file#heading`'s key now —
    where `move` would take it (a Python symbol moves to a Python file, a YAML key to a YAML file: `:name` in package.json
    is no home for a `def name`)."""
    f, key = split_anchor(anchor)
    if not key or f in ("concept", "source"):
        return []
    return sorted(c for c, keys in files.items() if c != f and key in keys and anchors.kind_of(c) == anchors.kind_of(f))


def gone_groups(target, d, broken, files):
    """{deleted file: [broken relation ids on it]} — a broken relation whose dead anchor's file is no longer in the tree,
    grouped under the first such file. Not one whose dead symbol or section is in another registered file now: that is a
    rename or a split — `move`'s, or a person's choice between homes — not a deletion."""
    out = {}
    for b in broken:
        f = next((file_of(a) for a in b["dead"] if gone_from_tree(target, file_of(a))), None)
        if f is None or any(homes_of(files, a) for a in b["dead"]):
            continue
        out.setdefault(f, []).append(b["id"])
    return out


def owed_rereads(d, only=None):
    """[(concept, [(retired id, the projection it was)])] — the concepts that lost a projection and owe a re-read (`owes`):
    `cq` fails every question they answer until `concept revise` or `concept reaffirm`. Not a relation's state, so `impact`
    used to leave them out — guin-site, 10-12: two retires printed the debt, `impact` said `unresolved_total = 0`, `check`
    held, and it surfaced 22 hours later as two cq-failed objections in review. With `only`, the concepts those prefixes
    name, or whose lost projection was on them."""
    gone = {r["id"]: r["src"] for r in d.get("retired", [])}
    out = []
    for c in sorted((c for c in d["concepts"] if c.get("owes")), key=lambda c: c["name"]):
        lost = [(i, gone.get(i, "?")) for i in c["owes"]]
        if only and not ("concept:" + c["name"]).startswith(tuple(only)) and not any(src.startswith(tuple(only)) for _, src in lost):
            continue
        out.append((c, lost))
    return out


def owed_text(c, lost):
    return ("concept:%s lost projection(s) %s since its sentence was affirmed — the questions it answers FAIL in `cq` until "
            "`concept revise %s --means \"...\"` (it no longer holds) or `concept reaffirm %s --by NAME|--delegated WHY` (it does); "
            "reconfirming what remains does not answer it" % (c["name"], ", ".join("%s (%s)" % x for x in lost), c["name"], c["name"]))


def cmd_impact(args):
    d = decl(args.target)
    stale, broken, unjudged, files = compute_impact(args.target, d, args.only)   # answers and leaves nothing behind: the verdict is what it prints
    owed = owed_rereads(d, args.only)
    if args.findings:
        on_drift = lambda x: next(("; concept:%s is marked drifted — %s" % (a[len("concept:"):], drift_line(drift_of(d, a[len("concept:"):])))
                                   for r in d["relations"] if r["id"] == x["id"] for a in (r["src"], r["dst"])
                                   if a.startswith("concept:") and drift_of(d, a[len("concept:"):])), "")
        findings = [{"kind": "stale", "where": "%s %s" % (x["id"], x["stale"]), "text": "stale because %s changed since it was confirmed%s" % (x["because"], on_drift(x))} for x in stale]
        findings += [{"kind": "broken", "where": "%s %s" % (x["id"], ", ".join(x["dead"])), "text": "dead anchor(s): the relation points at nothing%s" % (
                         "; %s is gone from the tree" % ", ".join(sorted({file_of(a) for a in x["dead"] if gone_from_tree(args.target, file_of(a))}))
                         if any(gone_from_tree(args.target, file_of(a)) for a in x["dead"]) else "")} for x in broken]
        # no person read these: a delegation, a judge's verdict applied, an agent's own re-read — observations of the record
        findings += [{"kind": "delegated", "where": "%s %s %s %s" % (r["id"], r["src"], r["predicate"], r["dst"]), "text": "re-confirmed %s" % unread_by_a_person(r["confirmed"])}
                     for r in d["relations"] if isinstance(r.get("confirmed"), dict) and unread_by_a_person(r["confirmed"])]
        findings += [{"kind": "owed-reread", "where": "concept:" + c["name"], "text": owed_text(c, lost)} for c, lost in owed]
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "standing": True, "findings": findings}, ensure_ascii=False, indent=1))
        return 1 if stale or broken or owed else 0
    held = {}
    for x in stale:
        rel = next((r for r in d["relations"] if r["id"] == x["id"]), None) or {}
        n = next((a[len("concept:"):] for a in (rel.get("src", ""), rel.get("dst", "")) if a.startswith("concept:") and drift_of(d, a[len("concept:"):])), None)
        if n:
            held.setdefault(n, []).append(x["id"])
    for n, ids in sorted(held.items()):
        # one line for a concept known wrong: its stale relations wait for the new sentence, not for a re-read each
        print("  drifted concept:%s — %s: %d stale relation(s) wait for `concept revise %s` (%s)" % (n, drift_line(drift_of(d, n)), len(ids), n, ", ".join(ids)))
    for x in stale:
        if any(x["id"] in ids for ids in held.values()) and not getattr(args, "show", False):
            continue
        print("  stale   %s  %s  <- %s" % (x["id"], x["stale"], x["because"]))
        if getattr(args, "show", False):
            rel = next((r for r in d["relations"] if r["id"] == x["id"]), None)
            # every end that moved: a relation whose section and concept both changed shows both (it used to show neither —
            # "A and B" is no anchor, and the diff was looked up by it)
            for end in x.get("changed") or [x["because"]]:
                diff = what_changed(args.target, rel, end) if rel else None
                print("\n".join("      " + l for l in (diff or "(%s: no earlier text in git to compare against — the relation was not committed when it was confirmed, or the anchor is a source, which never changes; the change is known by its fingerprint)" % end).rstrip().split("\n")))
    gone = gone_groups(args.target, d, broken, files)
    for b in broken:
        if not any(b["id"] in ids for ids in gone.values()):
            print("  broken  %s  dead anchors %s" % (b["id"], b["dead"]))
    for f, ids in sorted(gone.items()):
        # a file deleted on purpose: its relations are one fact, not N — and `retire --gone` disposes of them as one
        print("  gone    %s — deleted from the tree; %d broken relation(s) on it: %s" % (f, len(ids), ", ".join(ids)))
    if gone:
        import shlex
        print("  deleted on purpose? `retire --gone %s --why \"WHY\"` retires every relation on them with that one reason "
              "(kept in retired/), unregisters the files and says which concepts owe a re-read — after `move` takes what has a new home"
              % " ".join(shlex.quote(f) for f in sorted(gone)))
    if unjudged:
        print("  unjudged %d relation(s) confirmed before `seen` existed, and this machine has no baseline: %s — `observe --reset --at REV` to judge them from REV"
              % (len(unjudged), ", ".join(unjudged)))
    for c, lost in owed:
        # not a relation's state, and still the session's to act on: every question the concept answers fails until it is read
        print("  owed    " + owed_text(c, lost))
    parts = [x for x in ("only %s" % ", ".join(args.only) if args.only else "",
                         "%d stale or broken relation(s), %d concept(s) owing a re-read" % (len(stale) + len(broken), len(owed)) if owed else "") if x]
    print("unresolved_total = %d%s" % (len(stale) + len(broken) + len(owed), " (%s)" % "; ".join(parts) if parts else ""))
    return 1 if stale or broken or owed else 0


JUDGE_REQUEST, JUDGMENT = "mangsang/judge-request@1", "mangsang/judgment@1"
VERDICTS = ("still-true", "drifted", "cannot-tell")


def judge_basis(target, d, r, files):
    """Bind a verdict to its relation, vocabulary and the full anchors read, including dependency fingerprints.

    Keep text as well: token fingerprints intentionally ignore comments, but a judge can read their claims.
    This is independent of git HEAD and of the packet's display truncation.
    """
    ends = (r["src"], r["dst"])
    reads = {}
    for a in ends:
        f, key = split_anchor(a)
        if f not in ("concept", "source"):
            reads[a] = (anchor_parts(os.path.join(target, f)) or {}).get(key, [])[1:]
    basis = {"relation": r, "vocabulary": d["vocabulary"].get(r["predicate"]), "reads": reads,
             "anchors": {a: files.get(split_anchor(a)[0], {}).get(split_anchor(a)[1]) for a in ends},
             "texts": {a: (texts_of(target, split_anchor(a)[0]) or {}).get(split_anchor(a)[1]) for a in ends}}
    return hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def cmd_judge(args):
    """The judge pattern for staleness: mangsang packs the two texts and the quote; a fresh read-only session says whether the sentence
    still holds; mangsang validates (a drifted verdict quotes the text as it is) and applies only what is safe to apply."""
    d = decl(args.target)
    if args.mode == "request":
        # --out is a directory: the packet is written into it as judge-request.json and the response goes beside it. Seen:
        # `--out .../judge-req.json` made a directory of that name, and the agent's next step crashed reading it as a file
        if os.path.isfile(args.out) or (args.out.lower().endswith(".json") and not os.path.isdir(args.out)):
            raise SystemExit("judge request --out DIR takes a directory (the packet is written into it as judge-request.json, the response "
                             "goes beside it as judge-response.json); %s is a file name — give the directory, e.g. --out %s"
                             % (args.out, os.path.dirname(args.out) or "."))
        stale, broken, unjudged, files = compute_impact(args.target, d)
        rels = {r["id"]: r for r in d["relations"]}
        wanted = set(args.ids or [])
        items, held = [], []
        for x in stale:
            r = rels[x["id"]]
            if wanted and r["id"] not in wanted:
                continue
            if any(a.startswith("concept:") and drift_of(d, a[len("concept:"):]) for a in (r["src"], r["dst"])):
                held.append(r["id"])   # its concept is known wrong: nothing for a judge to find still true
                continue
            texts = {a: (texts_of(args.target, split_anchor(a)[0]) or {}).get(split_anchor(a)[1], "") for a in (x["stale"], x["because"])}
            # since 1.11 an anchor is stale when what it *reads* moved, its own text unchanged: a judge given the two texts alone saw
            # nothing to judge and said still-true — applied as a delegation. The packet carries the change itself (the diff since the
            # confirming commit, when git has it) and the declarations the changed side reads now, so the judge reads what a person would.
            ends = x.get("changed") or [x["because"]]
            diffs = [what_changed(args.target, r, end) for end in ends]
            reads = {}
            for end in ends:
                f, key = split_anchor(end)
                for label, text in ((anchor_parts(os.path.join(args.target, f)) if f not in ("concept", "source") else None) or {}).get(key, [])[1:]:
                    reads["%s%s" % (f, label) if not label.startswith("import ") else "%s: %s" % (f, label)] = text[:args.limit]
            items.append({"relation": r["id"], "basis": judge_basis(args.target, d, r, files),
                          "predicate": r["predicate"], "means": d["vocabulary"].get(r["predicate"], {}).get("means"),
                          "stale": x["stale"], "stale_text": texts[x["stale"]][:args.limit],
                          "because": x["because"], "because_text": texts[x["because"]][:args.limit],
                          "because_changed": "\n".join(dd for dd in diffs if dd)[:args.limit * 2] or None,
                          "because_reads": reads or None,
                          "quote_at_confirm": r.get("evidence"),
                          # the concept is the stale side: the sentence under judgment is its whole meaning, not the quote — the quote is
                          # a sentence of the projection, which still held when a deploy moved and the concept still named the old one
                          **({"judge": "concept-sentence"} if x["stale"].startswith("concept:") else {})})
        if held:
            print("not asked: %d relation(s) on drifted concept(s) (%s) — they wait for `concept revise`" % (len(held), ", ".join(held)))
        if not items:
            print("nothing stale to judge")
            return 0
        packet = {"artifact-type": JUDGE_REQUEST, "request-id": uuid.uuid4().hex,
                  "target": os.path.abspath(args.target).replace(os.sep, "/"), "items": items, "verdicts": list(VERDICTS),
                  "instructions": ("For each item, read stale_text (the side that may be stale) against because_text (the side that changed since the relation "
                                   "was confirmed) and decide whether the sentence in stale_text — the one quote_at_confirm quotes — still holds. "
                                   "because_changed is the change itself, as a diff since the confirmation, when git has it; because_reads are the "
                                   "declarations because_text reads now (a constant, a helper, an import) — when because_text itself did not change, "
                                   "the change is there. An item with \"judge\": \"concept-sentence\" has a concept on its stale side: the sentence "
                                   "under judgment is stale_text, the concept's whole meaning — does it still describe what because_text and "
                                   "because_changed now say? quote_at_confirm is context there, not the sentence under judgment. "
                                   "still-true: it does; say why in evidence. drifted: it does not; put the sentence that no longer holds in `quote`, "
                                   "verbatim from stale_text, and why in evidence from because_text. cannot-tell: say what the texts do not settle. "
                                   "Judge only the relations in the request. Similar names are not evidence. Read files under target if you must. Change no files.")}
        os.makedirs(args.out, exist_ok=True)
        packet_path, response_path = os.path.join(args.out, "judge-request.json"), os.path.join(args.out, "judge-response.json")
        # an earlier round's files in the same directory are moved aside, named by their time: guin-site, 10-15, reused a
        # directory that still held 10-12's judge-response.json, and the `next:` line pointed consume at the 3-day-old verdicts
        for name in sorted(os.listdir(args.out)):
            base = next((b for b in ("judge-request", "judge-response") if name.startswith(b + ".")), None)
            path = os.path.join(args.out, name)
            if base and os.path.isfile(path) and not re.match(r"\.\d{8}T\d{6}Z\.", name[len(base):]):
                stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(os.path.getmtime(path)))
                aside = os.path.join(args.out, "%s.%s%s" % (base, stamp, name[len(base):]))
                os.replace(path, aside)
                print("moved aside: %s -> %s (an earlier round's, %s)" % (name, os.path.basename(aside), stamp))
        save(packet_path, packet)
        print("judge packet: %d stale relation(s)\n  packet:   %s\n  response: %s (judge_worker.py writes it there; consume reads the packet beside it)\n"
              "next: python3 %s --request %s --response %s\n      mangsang judge consume --response %s"
              % (len(items), packet_path, response_path, os.path.join(os.path.dirname(os.path.abspath(__file__)), "judge_worker.py"),
                 packet_path, response_path, response_path))
        return 0
    # consume
    if not args.response:
        raise SystemExit("judge consume --response FILE: the judgment judge_worker.py wrote (beside its judge-request.json)")
    resp = load(args.response)
    req_path = os.path.join(os.path.dirname(os.path.abspath(args.response)), "judge-request.json")
    req = load(req_path)
    if req and os.path.isfile(args.response) and os.path.getmtime(args.response) < os.path.getmtime(req_path):
        # verdicts written before the packet beside them are an earlier round's — never applied to this one
        raise SystemExit("judge consume: %s is older than the judge-request.json beside it — an earlier round's verdicts, not this "
                         "request's; run the judge on this request (judge_worker.py --request %s --response FILE) and consume that"
                         % (args.response, req_path))
    if resp.get("artifact-type") != JUDGMENT or not isinstance(resp.get("items"), list) or not req:
        raise SystemExit("a judgment is %s with `items`, next to its judge-request.json" % JUDGMENT)
    if not req.get("request-id") or resp.get("request-id") != req["request-id"]:
        raise SystemExit("judge consume: response does not name this request-id — create a fresh request and judge it again")
    if os.path.realpath(req.get("target") or "") != os.path.realpath(args.target):
        raise SystemExit("judge consume: request belongs to another target — create a request for this project")
    # the judgment's author is the judge — the model that read the texts, from the worker's own record of the call; who
    # applied it is a second fact. On guin-site 120/120 and 65/65 still-true were applied as `judge <owner>`, rounds the
    # owner never read: a person's name goes on a judgment only with the source where that person read it (--approved-in)
    worker = resp.get("worker") if isinstance(resp.get("worker"), dict) else {}
    judge = args.judge or " ".join(str(x) for x in (worker.get("host"), worker.get("model")) if x)
    if not judge:
        raise SystemExit("the response has no worker record (judge_worker.py writes one): say which model judged, --judge \"<host> <model>\"")
    roster = people(args.target) or {}
    agents = tuple(roster.get("agents") or ()) + ("Claude", "Codex", "an agent")
    if args.by and not str(args.by).startswith(agents):
        sign_as_agent(args)   # a person's name: at an agent's hand, only with the source where that person read the verdicts
        applied_by = {"applied-by": args.by, **({"approved-in": APPROVED_IN} if APPROVED_IN else {})}
    elif args.by:
        applied_by = {"applied-by": args.by}
    elif running_agent():
        applied_by = {"applied-by": running_agent()}
    else:
        raise SystemExit("say who applies the judge's verdicts: --by NAME (run by an agent: --by is yours to omit, or a person's "
                         "name with --approved-in source:ID where they read the verdicts)")
    asked = {i["relation"]: i for i in req.get("items", [])}
    rels = {r["id"]: r for r in d["relations"]}
    norm = lambda t: " ".join(str(t).split())
    kept, rejected = [], []
    for it in resp["items"]:
        rid, verdict = it.get("relation"), it.get("verdict")
        if rid not in asked or rid not in rels:
            rejected.append("%s: not in the request" % rid)
        elif verdict not in VERDICTS or not str(it.get("evidence", "")).strip():
            rejected.append("%s: verdict must be one of %s with a non-empty evidence" % (rid, "/".join(VERDICTS)))
        elif verdict == "drifted" and norm(it.get("quote", "")) not in norm(asked[rid]["stale_text"]) or (verdict == "drifted" and not norm(it.get("quote", ""))):
            rejected.append("%s: drifted must quote the sentence verbatim from the stale text" % rid)
        else:
            kept.append(it)
    files, _ = snapshot(args.target, d["registry"])
    applied = []
    for it in kept:
        r = rels[it["relation"]]
        if asked[r["id"]].get("basis") != judge_basis(args.target, d, r, files):
            rejected.append("%s: relation or source changed since the request — request a fresh judgment" % r["id"])
            continue
        if it["verdict"] == "still-true" and any(a.startswith("concept:") and drift_of(d, a[len("concept:"):]) for a in (r["src"], r["dst"])):
            rejected.append("%s: still-true, but its concept is marked drifted — `concept revise` first" % r["id"])
        elif it["verdict"] == "still-true":
            # the one safe application: what a human would do after reading — recorded as a delegation, never as a person's confirmation
            if all(split_anchor(a)[0] in files and split_anchor(a)[1] in files[split_anchor(a)[0]] for a in (r["src"], r["dst"])) and quoted(args.target, r["evidence"], r["src"], r["dst"]):
                was_seen = r.get("seen")
                r["seen"] = {a: files[split_anchor(a)[0]][split_anchor(a)[1]] for a in (r["src"], r["dst"])}
                r.setdefault("history", []).append({"confirmed": r.get("confirmed"), "seen": was_seen, "evidence": r["evidence"]})
                r["confirmed"] = {"judge": judge, **applied_by, "why": it["evidence"][:200]}
                save(os.path.join(args.target, DECL, "relations", r["id"] + ".json"), r)
                applied.append(r["id"])
            else:
                rejected.append("%s: still-true, but its quote is no longer in the text — a human re-reads (`reconfirm --evidence`)" % r["id"])
    save(os.path.join(args.target, OBS, "judgments.json"), {"artifact-type": JUDGMENT, "judge": judge, **applied_by, "items": kept, "rejected": rejected, "applied": applied})
    for it in kept:
        print("  %-11s %s%s — %s" % (it["verdict"], it["relation"], (" (re-confirmed: judged by %s, applied by %s)" % (judge, applied_by["applied-by"]) if it["relation"] in applied else ""), it["evidence"][:100]))
        if it["verdict"] == "drifted":
            print("      quote: %s" % it["quote"][:120])
    for line in rejected:
        print("  rejected %s" % line)
    print("judgments: %d · still-true applied %d · drifted %d (a human retires or re-confirms with a new quote) · cannot-tell %d · rejected %d"
          % (len(kept), len(applied), sum(i["verdict"] == "drifted" for i in kept), sum(i["verdict"] == "cannot-tell" for i in kept), len(rejected)))
    return 1 if rejected else 0


def cq_presuppositions(d, files, q):
    """What a question assumes before it can be asked (Ren et al. 2014: a CQ presupposes its terms exist; the
    presuppositions, not the answer, are what the machine can check at authoring time). A question whose
    presuppositions fail is not *failed* — it is UNANSWERABLE: the model moved out from under it, and the question
    itself is what must change. This is the model->cq half of the feedback loop, mechanical."""
    v = q.get("verify", {})
    missing = []
    if v.get("kind") == "coverage":
        pred = v.get("predicate")
        if pred and pred not in d["vocabulary"]:
            missing.append("presupposes predicate %r — not in the vocabulary" % pred)
        if v.get("as") not in (None, "src", "dst"):
            missing.append("`as` must be src or dst")
        if isinstance(v.get("members"), dict):
            # the targets are chosen by a relation: the concepts that are <predicate> concept:<of>
            m = v["members"]
            if m.get("predicate") not in d["vocabulary"]:
                missing.append("presupposes predicate %r (members) — not in the vocabulary" % m.get("predicate"))
            if m.get("of") not in {c["name"] for c in d["concepts"]}:
                missing.append("presupposes concept %r (members) — not declared" % m.get("of"))
            elif not members(d, m):
                missing.append("presupposes concepts that are %s %s — none are; the question is about nothing" % (m.get("predicate"), m.get("of")))
        else:
            pat = re.compile("^" + re.escape(v.get("anchors", "")).replace("\\*", ".*") + "$")
            all_anchors = ["%s%s" % (f, k) for f, ks in files.items() for k in ks]
            if not any(pat.match(a) for a in all_anchors):
                missing.append("presupposes anchors matching %r — nothing in the tree matches; the question is about nothing" % v.get("anchors"))
    elif v.get("kind") == "projection":
        if "realizes" not in d["vocabulary"]:
            missing.append("presupposes predicate 'realizes' — not in the vocabulary")
        if not d["concepts"]:
            missing.append("presupposes declared concepts — none exist (`concept add`)")
        anchors_now = ["%s%s" % (f, k) for f, ks in files.items() for k in ks]   # anchors, not only file names: `source:` names a virtual file's anchors
        for medium, prefixes in (v.get("media") or {}).items():
            if not any(a.startswith(tuple(prefixes)) for a in anchors_now):
                missing.append("presupposes medium %r (%s) — no registered file matches" % (medium, ", ".join(prefixes)))
        if not v.get("media"):
            missing.append("presupposes `media` naming each medium's anchor prefixes")
    elif v.get("kind") == "resolved":
        pass   # asks only about the relations themselves; always askable
    elif v.get("kind") == "registered":
        if not v.get("paths"):
            missing.append("presupposes `paths` — the tracked prefixes whose every file must be registered (\"src/\", \"tests/\" …)")
    elif v.get("kind") == "open":
        # asked before anything answers it: a model built from conversation starts with what nobody has answered yet.
        # It names no answer — a later `revise` to answered-by is where the answer is signed — but it may say what it asks
        # about (`about`): a planning model starts with most of its questions open, and those are what its concepts are for
        if set(v) - {"kind", "about"}:
            missing.append("an open question names no answer — `{\"kind\": \"open\"}`, with `about` for the concepts it asks about; `cq revise` to answered-by when one exists")
        have = {c["name"] for c in d["concepts"]}
        for n in v.get("about") or []:
            if n not in have:
                missing.append("asks about concept %r — not declared" % n)
    elif v.get("kind") == "answered-by":
        # a domain question presupposes its answer's home: the named concepts. The machine cannot judge whether a
        # means-sentence really answers the text (that is the declarer's signature); it checks that the answer exists.
        names = v.get("concepts") or []
        if not names:
            missing.append("presupposes `concepts` naming who carries the answer — an unaddressed question is asked of no one")
        have = {c["name"] for c in d["concepts"]}
        for n in names:
            if n not in have:
                missing.append("presupposes concept %r — not declared; the model has no answer to point at" % n)
        if "realizes" not in d["vocabulary"]:
            missing.append("presupposes predicate 'realizes' — not in the vocabulary")
    else:
        missing.append("unknown verify kind %r — not a question this engine can ask" % v.get("kind"))
    return missing


INVARIANT_KINDS = ("coverage", "projection", "resolved", "registered")


def tracked_files(target):
    """Files git tracks under the target, relative to it (a target inside a repository is fine), or None without git."""
    import subprocess
    done = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=target, capture_output=True)
    if done.returncode:
        return None
    return sorted(p.decode("utf-8", "replace").replace("\\", "/") for p in done.stdout.split(b"\0") if p)


def unregistered(target, d, paths, excepts=()):
    """Tracked files under `paths` the registry does not hold — what the net cannot see. None without git."""
    import fnmatch
    have = {e["path"] for e in d["registry"]}
    got = tracked_files(target)
    if got is None:
        return None
    return [f for f in got if f.startswith(tuple(paths)) and f not in have and not any(fnmatch.fnmatch(f, g) for g in excepts)
            and not f.startswith((DECL + "/", OBS + "/"))]


UNSEEN_KINDS = ("python", "js", "component", "css", "html", "sql", "block", "dockerfile", "json", "yaml", "toml", "ini", "env")   # not markdown or text: in a directory nobody registered, that is content and assets


def record_prefixes(target):
    """The products' records and the environment, not the project: `record-paths` in hunsu.lock.json (each plugin declares its
    `records`), else this product's own. A product knows no other by name; the lock says what is whose."""
    lock = load(os.path.join(target, "hunsu.lock.json")) if os.path.isfile(os.path.join(target, "hunsu.lock.json")) else {}
    declared = lock.get("record-paths") if isinstance(lock, dict) else None
    others = {p for ps in declared.values() if isinstance(ps, list) for p in ps if isinstance(p, str)} if isinstance(declared, dict) else set()   # a string is no list of prefixes (its characters would skip nearly every file)
    return tuple(sorted(others | {DECL + "/", OBS + "/"}))


LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "deno.lock", "composer.lock",
             "Cargo.lock", "poetry.lock", "Pipfile.lock", "uv.lock", "Gemfile.lock", "go.sum"}   # a resolver's output: nothing in it is the project's to say


def unseen_directories(target, d, covered=(), excepts=(), with_files=False):
    """Directories holding tracked code or config and no registered file at all, each with its count — the shallowest such
    directory under one that has some. guin-site, 10-10: `write/` (an OAuth Worker, 11 files) and `lexicons/` (8 schemas)
    were new top-level directories; the advice beside registered files never looked there, and the net stayed green. A
    hidden directory, the products' records, lockfiles, what a `registered` invariant already asks for and what its `except`
    globs leave out are left out. Files directly in a directory whose registered files are all deeper (`src/b.py` beside
    `src/a/x.py`) are said as `src/*` — neither this nor the advice beside registered files looked there. The root's own
    files are not: they are the project's manifests and settings, in every project, and a `registered` invariant names
    them when they matter."""
    import fnmatch
    got = tracked_files(target)
    if got is None:
        return {} if with_files else []
    have = {e["path"] for e in d["registry"]}
    direct = {p.rsplit("/", 1)[0] + "/" for p in have if "/" in p}
    held = set()
    for p in have:
        parts = p.split("/")[:-1]
        held.update("/".join(parts[:i]) + "/" for i in range(1, len(parts) + 1))
    skip = record_prefixes(target) + tuple(covered)
    found = {}
    for f in got:
        parts = f.split("/")
        if len(parts) < 2 or f in have or f.startswith(skip) or any(x.startswith(".") for x in parts[:-1]):
            continue
        if anchors.kind_of(f) not in UNSEEN_KINDS or parts[-1] in LOCKFILES or any(fnmatch.fnmatch(f, g) for g in excepts):
            continue
        top = next(("/".join(parts[:i]) + "/" for i in range(1, len(parts)) if "/".join(parts[:i]) + "/" not in held), None)
        if not top and "/".join(parts[:-1]) + "/" not in direct:
            top = "/".join(parts[:-1]) + "/*"   # its directory holds registered files only deeper down
        if top:
            found.setdefault(top, []).append(f)
    return sorted((k, len(v)) for k, v in found.items()) if not with_files else found


RECENT_COMMITS = 20   # "changed lately", when the net's record says nothing later: about a working week of commits on guin-site


def recent_changes(target):
    """({path: commits ago}, commits since the net's record last changed or None, whether the history is longer than
    RECENT_COMMITS) — the files changed in the last RECENT_COMMITS commits or since `mangsang/` last changed, whichever
    reaches further back (at most 500). guin-site,
    10-16: `lexicons/` became a published contract six commits after the net last moved, and `check` said it only as one
    count among the unseen. {}, None, False without git."""
    import subprocess
    run = lambda *a: subprocess.run(["git", *a], cwd=target, capture_output=True, text=True, encoding="utf-8", errors="replace")
    net = run("log", "-1", "--format=%H", "--", DECL).stdout.strip()
    since = run("rev-list", "--count", net + "..HEAD").stdout.strip() if net else ""
    since = int(since) if since.isdigit() else None
    total = run("rev-list", "--count", "HEAD").stdout.strip()
    done = run("log", "-n", str(min(500, max(RECENT_COMMITS, since or 0))), "--relative", "--name-only", "--format=%x00", "--", ".")
    if done.returncode:
        return {}, None, False
    ago = {}
    for i, chunk in enumerate(done.stdout.split("\0")[1:]):
        for f in chunk.split("\n"):
            if f.strip():
                ago.setdefault(f.strip().replace("\\", "/"), i)
    # a history no longer than the window makes everything "lately", which singles nothing out: the window counts only past it
    return ago, since, total.isdigit() and int(total) > RECENT_COMMITS


def unrelated_files(target, d, active, files=None):
    """Registered files no live relation stands on — in the registry, so `lookup` says "registered; nothing on it" and
    `check` said nothing: an edit there makes nothing stale, as invisible to impact as a file never registered. guin-site,
    10-19: the eight lexicons registered from `check`'s own `next` went quiet the moment they were registered. Left out, as
    registered on purpose or already asked: a file no longer in the tree (`impact` says it broken or gone), a file that cites
    a kept source by id (`source:ID` — registered as the evidence that grounds a person's words, which `ungrounded` reads),
    and a file a `coverage` invariant's `anchors` reach (that invariant is the check: FAILED for what it misses)."""
    on = {f for r in d["relations"] for f in map(file_of, (r["src"], r["dst"])) if f}
    if files is None:
        files, _ = snapshot(target, d["registry"])
    pats = [re.compile("^" + re.escape(q["verify"]["anchors"]).replace("\\*", ".*") + "$") for q in active
            if q.get("verify", {}).get("kind") == "coverage" and isinstance(q["verify"].get("anchors"), str)]
    cite = re.compile(r"source:(%s)(?![\w-])" % "|".join(re.escape(x["id"]) for x in d["sources"])) if d["sources"] else None
    out = []
    for e in d["registry"]:
        p = e["path"]
        path = os.path.join(target, p)
        if p in on or not os.path.isfile(path) or p.startswith(record_prefixes(target)):
            continue
        if any(pat.match(p + k) for pat in pats for k in files.get(p, {"": None})):
            continue
        if cite and cite.search(io.open(path, encoding="utf-8", errors="replace").read()):
            continue
        out.append(p)
    return sorted(out)


def unseen_groups(target, d, active, files=None):
    """What the net cannot see, grouped by directory, the recently changed first: (the registered directories the `beside`
    advice looked in, the groups beside registered files, the groups in directories nothing is registered in, the groups of
    registered files no relation stands on — `unrelated_files`). Each group
    is {group, files, ago, after_net}: `ago` is how many commits back its newest change is when that is recent (since the
    net's record last changed, or within RECENT_COMMITS), else None. `check` and `concept list --brief` say the same groups."""
    ago, since, window = recent_changes(target)
    def group(name, files):
        n = min((ago[f] for f in files if f in ago), default=None)
        recent = n is not None and ((window and n < RECENT_COMMITS) or (since is not None and n < since))
        return {"group": name, "files": sorted(files), "ago": n if recent else None, "after_net": bool(recent and since is not None and n < since)}
    order = lambda gs: sorted(gs, key=lambda g: (g["ago"] is None, g["ago"] or 0, g["group"]))
    beside, near = [], []
    if not any(q.get("verify", {}).get("kind") == "registered" for q in active):
        beside = sorted({e["path"].rsplit("/", 1)[0] + "/" for e in d["registry"] if "/" in e["path"]})
        by = {}
        for f in (unregistered(target, d, beside) if beside else None) or []:
            by.setdefault(f.rsplit("/", 1)[0] + "/", []).append(f)
        near = order(group(k, v) for k, v in by.items())
    asks = [q["verify"] for q in active if q.get("verify", {}).get("kind") == "registered"]
    covered = beside + [p for v in asks for p in v.get("paths") or []]
    blind = unseen_directories(target, d, covered, [g for v in asks for g in v.get("except") or []], with_files=True)
    by = {}
    for f in unrelated_files(target, d, active, files):
        by.setdefault(f.rsplit("/", 1)[0] + "/" if "/" in f else "./", []).append(f)
    return beside, near, order(group(k, v) for k, v in blind.items()), order(group(k, v) for k, v in by.items())


def when_text(g):
    """`changed in the last commit` / `changed 3 commits ago, after the net's last change` — a recent group's change, said."""
    if g["ago"] is None:
        return ""
    return ("changed in the last commit" if g["ago"] == 0 else "changed %d commit%s ago" % (g["ago"], "" if g["ago"] == 1 else "s")) + (", after the net's last change" if g["after_net"] else "")


def group_text(g):
    """One group as the unseen lines name it: a lone file by its path, else `dir/ N file(s)`; a recent one says when."""
    head = g["files"][0] if len(g["files"]) == 1 and not g["group"].endswith("*") or g["group"] == "./" else "%s %d file(s)" % (g["group"], len(g["files"]))
    return head + (" [%s]" % when_text(g) if g["ago"] is not None else "")


def register_command(g):
    """The exact `register` for a group: its files, named, up to twenty; past that, what git tracks there."""
    if len(g["files"]) <= 20:
        return "mangsang register " + " ".join(g["files"])
    return "mangsang register $(git ls-files -- '%s')" % g["group"].rstrip("*")


def next_steps(groups, say, k=3):
    """What to do about the unseen and the unrelated groups, said as commands — never a stop: the why once, per group (the
    recent first, `k` at most) its exact `register`, or for registered files nothing stands on, the files to relate; then the
    relating. guin-site, 10-16 → 10-19: `lexicons/` (8 published atproto schemas) was said as `lexicons/ 8 file(s)` among the
    unseen, nothing pointed at relating them, and three runs finished without touching the net."""
    if not groups:
        return
    say("  %-12s a file nothing relates to is invisible to impact — relate them, the recently changed first:" % "next")
    for g in groups[:k]:
        when = ", ".join(x for x in ("%d %sfile(s)" % (len(g["files"]), "registered " if g.get("unrelated") else ""), when_text(g)) if x)
        say("      %s (%s): %s" % (g["group"], when, register_command(g) if not g.get("unrelated") else "relate %s%s — nothing stands on them" % (
            ", ".join(g["files"][:6]), " +%d" % (len(g["files"]) - 6) if len(g["files"]) > 6 else "")))
    if len(groups) > k:
        say("      … and %d more group(s) the same way" % (len(groups) - k))
    say("      %s what they carry in a proposals.json — each anchor `realizes concept:NAME`, a quote as evidence (`concept add` "
        "first for an idea the net lacks) — show it to the person, and `mangsang confirm proposals.json --by NAME`"
        % ("then relate" if any(not g.get("unrelated") for g in groups[:k]) else "relate"))


def ungrounded_sources(d, target):
    """A person's words kept as a source that nothing stands on — no relation uses it, no signature cites it (approved-in,
    approval-of), no registered document cites it by id. guin-site's owner decided the backend's read path and five more of its questions (source:rd-02,
    source:bd2-02): kept verbatim, grounding no concept, and nothing said so."""
    roster = people(target) or {}
    agents = tuple(roster.get("agents") or ()) + ("Claude (",)
    records = json.dumps([d["relations"], d["retired"], d["concepts"], d["cq_declared"], d["cq"]], ensure_ascii=False)
    # a registered document that cites it by id (a plan quoting the owner's decision) grounds it in text the net watches;
    # measured on guin-site: 37 person sources nothing related, 31 of them cited by the plan — the 6 left were real
    for e in d["registry"]:
        path = os.path.join(target, e["path"])
        if os.path.isfile(path):
            records += io.open(path, encoding="utf-8", errors="replace").read()
    out = []
    for x in d["sources"]:
        if str(x.get("speaker", "")).startswith(agents) or x.get("kind") in ("agent", "question"):
            continue
        if not re.search(r"source:%s(?![\w-])" % re.escape(x["id"]), records):   # the id itself, however it is quoted (JSON, backticks)
            out.append(x["id"])
    return out


def reach(d, names):
    """What the concepts `names` stand on: every concept reachable through relations between concepts along which a change
    travels toward them — the vocabulary's `propagates`, the rule `impact` already judges staleness by. A project that adds
    `requires` (dst->src) to its vocabulary says "when the fixture changes, the activity may be stale"; the same sentence
    says the activity's question is also about the fixture. Returns {name: (from, relation id)} for each reached concept
    (the starts excluded), so a caller can say how it was reached. Relations to or from anything but a concept (a document
    section, code, a source) are projections, not dependencies, and are not followed."""
    out, queue = {}, list(names)
    starts = set(names)
    while queue:
        cur = queue.pop(0)
        for r in d["relations"]:
            if not (r["src"].startswith("concept:") and r["dst"].startswith("concept:")):
                continue
            prop = d["vocabulary"].get(r["predicate"], {}).get("propagates", "none")
            src, dst = r["src"][len("concept:"):], r["dst"][len("concept:"):]
            nxt = dst if src == cur and prop in ("dst->src", "both") else src if dst == cur and prop in ("src->dst", "both") else None
            if nxt and nxt not in starts and nxt not in out:
                out[nxt] = (cur, r["id"])
                queue.append(nxt)
    return out


def drift_of(d, name):
    """The mark on a concept whose sentence is known not to hold any more, its revision owed (`concept drift`) — or None."""
    return (next((c for c in d["concepts"] if c["name"] == name), None) or {}).get("drift")


def drift_line(mark):
    """A drift mark as a line: the reason's first clause, and who marked it."""
    return "%s (marked %s)" % (first_clause(mark.get("why", "?"), 120), who_signed(mark))


def drifted_end(d, *ends):
    """The first concept among a relation's ends that is marked drifted, or None — a sentence known not to hold is not one
    to sign a relation against (confirm, move, reconfirm)."""
    return next((a[len("concept:"):] for a in ends if str(a).startswith("concept:") and drift_of(d, a[len("concept:"):])), None)


def drift_refusal(d, name):
    """What a refused signature on a drifted concept says, and what to do instead."""
    return ("concept:%s is marked drifted — %s. Its sentence is known not to hold, so a signature now would record it as read and true: "
            "`concept revise %s --means \"...\"` (then relate its projections to the new sentence), or `concept reaffirm %s` if the old "
            "sentence holds after all" % (name, drift_line(drift_of(d, name)), name, name))


def drifts_reached(d, names, reached):
    """[(name, via, mark)] for the drifted concepts a question's answer names or stands on."""
    return [(n, "" if n in names else " (through %s)" % reached[n][0], drift_of(d, n)) for n in list(names) + list(reached) if drift_of(d, n)]


def answer_health(d, names, moved):
    """(problems, reached) for a question answered by `names`: each named concept must be realized somewhere; it and
    everything it stands on (`reach`) must have no moved projection, and the relations it stands on must not have moved.
    `moved`: relation id -> "stale" | "broken"."""
    reached = reach(d, names)
    problems = []
    for n in names:
        if not any(r["predicate"] == "realizes" and r["dst"] == "concept:" + n for r in d["relations"]):
            problems.append("%s is declared but realized nowhere — the answer is a sentence with no reality behind it" % n)
    for n in list(names) + list(reached):
        ids = [r["id"] for r in d["relations"] if r["predicate"] == "realizes" and r["dst"] == "concept:" + n and r["id"] in moved]
        via = "" if n in names else " (through %s)" % reached[n][0]
        if ids:
            problems.append("%s%s has moved projections (%s) — the sentence stands but what realizes it changed since confirmation" % (n, via, ", ".join(ids)))
    owing = {c["name"]: c.get("owes") for c in d["concepts"] if c.get("owes")}
    gone = {r["id"]: r["src"] for r in d.get("retired", [])}
    for n in list(names) + list(reached):
        if n in owing:
            via = "" if n in names else " (through %s)" % reached[n][0]
            lost = ", ".join("%s (%s)" % (i, gone[i]) if i in gone else i for i in owing[n])
            problems.append("%s%s lost projection(s) %s since its sentence was affirmed — does it still hold? `concept revise` or `concept reaffirm`; "
                            "reconfirming what remains does not answer it" % (n, via, lost))
    for n, (frm, rid) in reached.items():
        if rid in moved:
            rel = next(r for r in d["relations"] if r["id"] == rid)
            problems.append("%s %s %s (%s) is %s — what %s stands on changed since it was confirmed; re-read it"
                            % (rel["src"][len("concept:"):], rel["predicate"], rel["dst"][len("concept:"):], rid, moved[rid], frm))
    return problems, reached


def members(d, spec):
    """The concepts a relation selects: every concept X with `X <predicate> concept:<of>` — followed transitively along the
    same predicate, so `shower is-a fixture` and `fixture is-a thing` put shower among the things."""
    pred, of = spec.get("predicate"), spec.get("of")
    out, frontier = set(), {of}
    while frontier:
        nxt = {r["src"][len("concept:"):] for r in d["relations"] if r["predicate"] == pred and r["src"].startswith("concept:")
               and r["dst"] in {"concept:" + f for f in frontier}} - out - {of}
        out |= nxt
        frontier = nxt
    return sorted(out)


def eval_invariant(d, files, all_anchors, q, target="."):
    """One invariant, evaluated: (ok, detail). These are the net's health checks — the fsck, not the questions."""
    v = q.get("verify", {})
    if v.get("kind") == "coverage":
        if isinstance(v.get("members"), dict):
            targets = ["concept:" + n for n in members(d, v["members"])]
        else:
            pat = re.compile("^" + re.escape(v["anchors"]).replace("\\*", ".*") + "$")
            targets = [a for a in all_anchors if pat.match(a)]
        role = v.get("as", "src")
        covered = {r[role] for r in d["relations"] if r["predicate"] == v.get("predicate", r["predicate"])}
        missing = [a for a in targets if a not in covered]
        ok = bool(targets) and not missing
        return ok, "%d %s, %d uncovered%s" % (len(targets), "concept(s)" if isinstance(v.get("members"), dict) else "anchors", len(missing), (": " + ", ".join(missing)) if missing else "")
    if v.get("kind") == "projection":
        media = v.get("media") or {}
        missing = []
        for c in d["concepts"]:
            pro = [r["src"] for r in d["relations"] if r["predicate"] == "realizes" and r["dst"] == "concept:" + c["name"]]
            for medium, prefixes in media.items():
                if not any(a.startswith(tuple(prefixes)) for a in pro):
                    missing.append("%s lacks %s" % (c["name"], medium))
        return not missing, "%d concept(s), %d gap(s)%s" % (len(d["concepts"]), len(missing), ("; ".join([": "] + missing).replace(": ; ", ": ") if missing else ""))
    if v.get("kind") == "registered":
        missing = unregistered(target, d, v.get("paths") or [], v.get("except") or [])
        if missing is None:
            return False, "no git here — which files are tracked cannot be told"
        return not missing, "%d unregistered tracked file(s)%s" % (len(missing), (": " + ", ".join(missing[:12]) + (" … and %d more" % (len(missing) - 12) if len(missing) > 12 else "")) if missing else "")
    # resolved
    dead = [r["id"] for r in d["relations"] if any((split_anchor(a)[0] not in files or split_anchor(a)[1] not in files[split_anchor(a)[0]]) for a in (r["src"], r["dst"]))]
    return not dead, "%d relations, %d with dead anchors%s" % (len(d["relations"]), len(dead), (": " + ", ".join(dead)) if dead else "")


def cmd_check(args):
    """Ask the net's invariants — its health, not its questions. `git fsck`, not code review.

    These used to live under `cq`, and the name lied: coverage/projection/resolved are lints — 'is the net formally
    whole' — while a competency question asks 'does the model answer this'. Same declaration machinery (an invariant
    is declared, signed, retired like a CQ — which patterns must be covered is per-project policy), separate name,
    separate command, so `cq 4/4 answered` can never again mean 'lint passed'."""
    say = (lambda *a, **k: None) if getattr(args, "findings", False) else print   # as a reporter, stdout is the findings JSON and nothing else
    d = decl(args.target)
    files, _ = snapshot(args.target, d["registry"])
    all_anchors = ["%s%s" % (f, k) for f, ks in files.items() for k in ks]
    active = [q for q in cq_active(d) if q.get("verify", {}).get("kind") in INVARIANT_KINDS]
    failed = unaskable = 0
    findings = []
    for q in active:
        presup = cq_presuppositions(d, files, q)
        if presup:
            unaskable += 1
            say("  %-12s %s  %s" % ("UNASKABLE", q["id"], q["text"]))
            for m in presup:
                say("      %s" % m)
            findings.append({"kind": "invariant-unaskable", "where": q["id"], "source": "mangsang", "text": "; ".join(presup)})
            continue
        ok, detail = eval_invariant(d, files, all_anchors, q, args.target)
        failed += not ok
        if not ok:
            findings.append({"kind": "invariant-failed", "where": q["id"], "source": "mangsang", "text": detail})
        say("  %-12s %s  %s — %s" % ("holds" if ok else "FAILED", q["id"], q["text"], detail))
    # the audit: parts of the net no invariant watches (was cq's predicate-level `unquestioned` — it belongs here:
    # 'no lint covers this predicate' is a health gap, not a domain question nobody asked)
    questioned = set()
    any_projection = False
    for q in active:
        v = q.get("verify", {})
        if v.get("kind") == "coverage" and v.get("predicate"):
            questioned.add(v["predicate"])
        if v.get("kind") == "projection":
            any_projection = True
            questioned.add("realizes")
    used = {r["predicate"] for r in d["relations"] if d["vocabulary"].get(r["predicate"], {}).get("propagates", "none") != "none"}
    unwatched = sorted(used - questioned) + (["concepts (no projection invariant)"] if d["concepts"] and not any_projection else [])
    for u in unwatched:
        say("  %-12s %s — the net holds this and no invariant watches it; declare one or say why not" % ("UNWATCHED", u))
        findings.append({"kind": "invariant-unwatched", "where": u, "source": "mangsang",
                         "text": "in use by confirmed relations (or declared concepts) but watched by no declared invariant"})
    # facts of the record, for the reviewer — not health, so they never fail `check`: records a build that is no release
    # wrote (committed, so others read them), and declarations that stand on a person's yes to the agent's own proposal
    import subprocess
    root = os.path.join(args.target, DECL)
    for kind in RECORD_KINDS:
        folder = os.path.join(root, kind)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            w = str(load(os.path.join(folder, name)).get("written_by", "")) if name.endswith(".json") else ""
            rel = "%s/%s/%s" % (DECL, kind, name)
            if "+g" in w and subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=args.target, capture_output=True).returncode == 0:
                findings.append({"kind": "unreleased-writer", "where": rel, "source": "mangsang",
                                 "text": "committed as written by %s — a build that is not a release; nobody can install what wrote it" % w})
    proposed = [("concept:" + c["name"]) for c in d["concepts"] if (c.get("declared") or {}).get("approval-of")] + \
               [("cq:" + q["id"]) for q in d["cq_declared"] if (q.get("declared") or {}).get("approval-of")]
    # what the net cannot see, said as advice (never red): tracked files beside the registered ones that nobody registered,
    # when no `registered` invariant asks — guin-site's whole backend was outside the net and every command was green — and
    # directories nobody registered anything in (the advice beside registered files never looked there: guin-site's write
    # app and its lexicons), each grouped by directory, the recently changed first, with the commands that relate them
    _, near, blind, loose_files = unseen_groups(args.target, d, active, files)
    if near:
        missing = [f for g in near for f in g["files"]]
        say("  %-12s %d tracked file(s) beside registered ones are not registered (%s%s) — the net cannot see them; register them, or declare "
            "`{\"kind\": \"registered\", \"paths\": [...]}` to make it a check" % ("unseen", len(missing), ", ".join(group_text(g) for g in near[:6]),
                                                                                " … and %d more director%s" % (len(near) - 6, "y" if len(near) == 7 else "ies") if len(near) > 6 else ""))
        findings.append({"kind": "unregistered", "layer": "observation", "where": ", ".join(missing[:12]), "source": "mangsang",
                         "text": "%d tracked file(s) in registered directories are not registered; no invariant asks%s" % (len(missing), "".join(
                             "; %s %s" % (g["group"], when_text(g)) for g in near if g["ago"] is not None))})
    if blind:
        # named up to a few: a monorepo with one package registered has thousands of such directories, and one line naming
        # them all is no line anyone reads
        more = lambda k: " … and %d more" % (len(blind) - k) if len(blind) > k else ""
        say("  %-12s %d director%s with code or config and nothing registered (%s%s) — the net cannot see them; register what in them the "
            "project is about, or exclude it — `except` globs in a `registered` invariant" % ("unseen", len(blind), "y" if len(blind) == 1 else "ies",
                                                                                         ", ".join("%s %d file(s)%s" % (g["group"], len(g["files"]), " [%s]" % when_text(g) if g["ago"] is not None else "")
                                                                                                   for g in blind[:6]), more(6)))
        findings.append({"kind": "unregistered", "layer": "observation", "where": ", ".join(g["group"] for g in blind[:12]), "source": "mangsang",
                         "text": "%d director%s of tracked code or config hold no registered file: %s%s" % (len(blind), "y" if len(blind) == 1 else "ies",
                                                                                                     ", ".join("%s (%d%s)" % (g["group"], len(g["files"]), ", " + when_text(g) if g["ago"] is not None else "")
                                                                                                               for g in blind[:12]), more(12))})
    # the next commands, for the groups nothing in them is registered and for the recently changed beside registered ones:
    # three at most, the recent first — a statement of what to do, never a stop
    # registered, and nothing stands on them: as invisible to impact as the unseen, said the same way (never red)
    if loose_files:
        n = sum(len(g["files"]) for g in loose_files)
        say("  %-12s %d registered file(s) no relation stands on (%s%s) — the net holds them and sees nothing in them: an edit there "
            "makes nothing stale" % ("unrelated", n, ", ".join(group_text(g) for g in loose_files[:6]),
                                     " … and %d more director%s" % (len(loose_files) - 6, "y" if len(loose_files) == 7 else "ies") if len(loose_files) > 6 else ""))
        findings.append({"kind": "unrelated", "layer": "observation", "where": ", ".join(f for g in loose_files for f in g["files"][:12])[:2000],
                         "source": "mangsang", "text": "%d registered file(s) no relation stands on: %s" % (n, ", ".join(
                             "%s (%d%s)" % (g["group"], len(g["files"]), ", " + when_text(g) if g["ago"] is not None else "") for g in loose_files[:12]))})
    for g in loose_files:
        g["unrelated"] = True
    # registry entries for files gone from the tree that nothing stands on: `impact` says a gone file only through the
    # relations broken on it, so these sat silently (guin-site, 10-19: 11 — src/worker/api.ts, db/schema.sql, scripts/…)
    stray = sorted(e["path"] for e in d["registry"] if not os.path.exists(os.path.join(args.target, e["path"]))
                   and not any(file_of(a) == e["path"] for r in d["relations"] for a in (r["src"], r["dst"])))
    if stray:
        by = {}
        for f in stray:
            by.setdefault(f.rsplit("/", 1)[0] + "/" if "/" in f else "./", []).append(f)
        gs = sorted(({"group": k, "files": v, "ago": None} for k, v in by.items()), key=lambda g: (-len(g["files"]), g["group"]))
        say("  %-12s %d registered file(s) gone from the tree, nothing stands on them (%s%s) — the registry still lists them; to drop "
            "them: `mangsang retire --gone %s --why \"...\"`" % ("gone", len(stray), ", ".join(group_text(g) for g in gs[:6]),
                                                              " … and %d more director%s" % (len(gs) - 6, "y" if len(gs) == 7 else "ies") if len(gs) > 6 else "",
                                                              " ".join(stray)))
        findings.append({"kind": "registered-gone", "layer": "observation", "where": ", ".join(stray[:12]), "source": "mangsang",
                         "text": "%d registered file(s) are gone from the tree and no relation stands on them; `retire --gone FILE.. --why` drops them" % len(stray)})
    todo = sorted(blind + [g for g in near if g["ago"] is not None] + loose_files, key=lambda g: (g["ago"] is None, g["ago"] or 0))
    next_steps(todo, say)
    loose = ungrounded_sources(d, args.target)
    if loose:
        say("  %-12s %d thing(s) a person said ground nothing — no relation uses them, no signature or registered document cites them: %s" % ("ungrounded", len(loose), ", ".join("source:" + i for i in loose)))
        findings.append({"kind": "ungrounded-source", "layer": "observation", "where": ", ".join("source:" + i for i in loose), "source": "mangsang",
                         "text": "a person's words kept as a source that no concept stands on — a decision the model does not carry yet"})
    if proposed:
        say("  %-12s %d declaration(s) signed in a person's name on their yes to the agent's proposal: %s" % ("proposed", len(proposed), ", ".join(proposed)))
        findings.append({"kind": "agent-proposed", "layer": "observation", "where": ", ".join(proposed), "source": "mangsang",
                         "text": "%d declaration(s) stand on a person's approval of the agent's own proposal (approval-of), not on the person's words" % len(proposed)})
    # not an invariant, so it fails no `check`: but a session reading "holds" must not take the net for clean while a concept
    # owes a re-read and `cq` fails the questions it answers (guin-site, 10-12: found 22 hours later, in review)
    owed = owed_rereads(d)
    for c, lost in owed:
        say("  %-12s %s" % ("owed", owed_text(c, lost)))
    if owed:
        findings.append({"kind": "owed-reread", "layer": "observation", "where": ", ".join("concept:" + c["name"] for c, _ in owed), "source": "mangsang",
                         "text": "%d concept(s) lost a projection and owe a re-read; `cq` fails the questions they answer (`impact` counts them)" % len(owed)})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "standing": True, "findings": findings}, ensure_ascii=False, indent=1))
    say("invariants %d · holds %d · failed %d · unaskable %d · unwatched %d%s"
          % (len(active), len(active) - failed - unaskable, failed, unaskable, len(unwatched),
             " — and %d concept(s) owe a re-read: `cq` fails until each is revised or reaffirmed" % len(owed) if owed else ""))
    return 1 if failed or unaskable or unwatched else 0


def cq_active(d):
    """The questions currently asked: legacy cq.json entries plus declared per-file CQs that are not retired."""
    return list(d["cq"]) + [q for q in d["cq_declared"] if not q.get("retired")]


def cmd_cq(args):
    """Ask the project's competency questions — the domain questions, whose answers are concepts.

    Grüninger & Fox (1995): a CQ tests what the model can answer, in the model's own terminology. The structural
    checks that used to sit here were lints wearing this name (`check` asks those now). A domain CQ names its
    answer: verify {kind: answered-by, concepts: [...]} — 'this question is carried by that concept's means
    sentence'. The machine cannot judge whether the sentence answers the words (the declarer's signature carries
    that, like every confirm); it audits that the answer is alive: the concept exists (else UNANSWERABLE — the
    model cannot answer this question of the domain), is realized somewhere, and none of its projections have
    moved since confirmation (else FAILED — the promise's reality shifted; re-read before trusting the sentence).
    The reverse audit: a concept no question names is UNQUESTIONED — the model holds a meaning nobody asks for."""
    if getattr(args, "mode", "run") != "run":
        return cq_declare(args)
    say = (lambda *a, **k: None) if getattr(args, "findings", False) else print   # as a reporter, stdout is the findings JSON and nothing else
    d = decl(args.target)
    files, _ = snapshot(args.target, d["registry"])
    active = [q for q in cq_active(d) if q.get("verify", {}).get("kind") not in INVARIANT_KINDS]
    structural = len(cq_active(d)) - len(active)
    stale, broken, _, _ = compute_impact(args.target, d, None)
    moved = {x["id"]: "stale" for x in stale}
    moved.update({x["id"]: "broken" for x in broken})
    byname = {c["name"]: c for c in d["concepts"]}
    failed = unanswerable = drifted = answered = 0
    findings = []
    opened = [q for q in active if q.get("verify", {}).get("kind") == "open"]
    for q in opened:
        say("  %-12s %s  %s%s" % ("OPEN", q["id"], q["text"], "  (about %s)" % ", ".join(q["verify"]["about"]) if q.get("verify", {}).get("about") else ""))
        findings.append({"kind": "cq-open", "layer": "observation", "where": q["id"], "source": "mangsang",
                         "text": "asked and not yet answered — a declared gap, not a failure"})
    active = [q for q in active if q not in opened]
    for q in active:
        presup = cq_presuppositions(d, files, q)
        if presup:
            unanswerable += 1
            say("  %-12s %s  %s" % ("UNANSWERABLE", q["id"], q["text"]))
            for m in presup:
                say("      %s" % m)
            findings.append({"kind": "cq-unanswerable", "where": q["id"], "source": "mangsang",
                             "text": "; ".join(presup)})
            continue
        names = q["verify"].get("concepts", [])
        problems, reached = answer_health(d, names, moved)
        q["_reached"] = reached
        # a sentence someone marked as no longer true is not an answer, whatever its projections say (guin-site 748a4d8: the
        # site moved off D1, the stale relations were re-confirmed "to be revised at stage 5", and two questions read green
        # with a sentence false in production)
        drifts = drifts_reached(d, names, reached)
        ok = not problems and not drifts
        failed += bool(problems)
        drifted += bool(drifts)
        answered += ok
        if drifts:
            findings.append({"kind": "cq-drifted", "where": q["id"], "source": "mangsang",
                             "text": "; ".join("%s%s is marked drifted: %s" % (n, via, drift_line(m)) for n, via, m in drifts)})
        if problems:   # a drift does not hide what else is wrong with the answer
            findings.append({"kind": "cq-failed", "where": q["id"], "source": "mangsang", "text": "; ".join(problems)})
        answer = "; ".join("%s: %s" % (n, byname[n]["means"]) for n in names if n in byname)
        say("  %-12s %s  %s" % ("answered" if ok else "DRIFTED" if drifts else "FAILED", q["id"], q["text"]))
        say("      %s %s" % ("=" if ok else "!" if drifts else "?", answer[:240]))
        for n, via, m in drifts:
            say("      drifted: %s%s — %s; the answer waits for `concept revise %s`" % (n, via, drift_line(m), n))
        if reached:
            by = {}
            for n, (frm, rid) in reached.items():
                pred = next(r["predicate"] for r in d["relations"] if r["id"] == rid)
                by.setdefault(pred, []).append(n)
            say("        through %s" % "; ".join("%s: %s" % (p, ", ".join(ns)) for p, ns in sorted(by.items())))
        for p in problems:
            say("      %s" % p)
    # the reverse audit: which concepts does no question name? (G&F: content the questions do not justify)
    # a concept is asked for when a question names it or stands on it (`reach`)
    named = {n for q in active for n in q.get("verify", {}).get("concepts", [])} | {n for q in active for n in q.pop("_reached", {})}
    named |= {n for q in opened for n in q.get("verify", {}).get("about") or []}   # asked about, not yet answered: still asked
    unquestioned = sorted(c["name"] for c in d["concepts"] if c["name"] not in named)
    for u in unquestioned:
        say("  %-12s concept:%s — the model holds this meaning and no question asks for it; write the CQ or say why not" % ("UNQUESTIONED", u))
        findings.append({"kind": "cq-unquestioned", "where": "concept:" + u, "source": "mangsang",
                         "text": "declared and realized, but named by no competency question"})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "standing": True, "findings": findings}, ensure_ascii=False, indent=1))
    tail = " · %d structural declaration(s) now answer to `check`" % structural if structural else ""
    say("cq %d · answered %d · failed %d · unanswerable %d · unquestioned %d · open %d%s%s"
          % (len(active) + len(opened), answered, failed, unanswerable, len(unquestioned), len(opened),
             " · drifted %d" % drifted if drifted else "", tail))
    return 1 if failed or unanswerable or unquestioned or drifted else 0


def cq_declare(args):
    """A question is a declaration like a concept: it has an author (or a recorded delegation), it is refused at
    authoring time if its presuppositions do not hold against the current model (Ren: authoring tests fire when the
    question is written, not later), and retiring it keeps the record. One file per CQ, same merge logic as relations."""
    d = decl(args.target)
    folder = os.path.join(args.target, DECL, "cq")
    byid = {q["id"]: q for q in d["cq_declared"]}
    legacy = {q.get("id") for q in d["cq"]}
    if args.mode in ("add", "revise"):
        if not args.id or not re.fullmatch(r"[\w-]+", args.id):
            raise SystemExit("a CQ id is a word: letters, digits, _ or -")
        if not (args.by or args.delegated):
            raise SystemExit("say who asks this question (--by) or why the human delegated it (--delegated)")
        if args.mode == "add" and (args.id in byid or args.id in legacy):
            raise SystemExit("CQ %s exists — `cq revise` changes it" % args.id)
        if args.mode == "revise" and args.id not in byid:
            raise SystemExit("no declared CQ %s%s" % (args.id, " (it is in legacy cq.json — move it here by `cq add` under a new id)" if args.id in legacy else ""))
        q = dict(byid.get(args.id) or {"id": args.id})
        if args.mode == "revise":
            q.setdefault("history", []).append({k: q[k] for k in ("text", "verify", "declared") if k in q})   # what was asked before, and by whom
        if args.text:
            q["text"] = args.text
        if args.verify:
            try:
                q["verify"] = json.loads(args.verify)
            except ValueError as err:
                raise SystemExit("--verify is not JSON (%s)" % err)
        if not (q.get("text") and q.get("verify")):
            raise SystemExit("a CQ is --text \"the question\" plus --verify '{\"kind\": ...}' — the text for people, the verify for the engine; neither substitutes for the other")
        files, _ = snapshot(args.target, d["registry"])
        presup = cq_presuppositions(d, files, q)
        if presup:
            raise SystemExit("CQ %s cannot be asked of the current model:\n  %s\n(declare the missing terms first, or fix the question)" % (args.id, "\n  ".join(presup)))
        q.pop("retired", None)
        q["declared"] = signature(args.by, args.delegated)
        save(os.path.join(folder, args.id + ".json"), q)
        print("CQ %s %s: %s" % (args.id, "declared" if args.mode == "add" else "revised", q["text"]))
        return 0
    if args.mode == "retire":
        q = byid.get(args.id)
        if not q:
            raise SystemExit("no declared CQ %s" % args.id)
        if not args.why:
            raise SystemExit("--why: a retired question is a decision — what made it no longer worth asking?")
        q["retired"] = {"why": args.why}
        save(os.path.join(folder, args.id + ".json"), q)
        print("CQ %s retired: %s (kept in the record)" % (args.id, args.why))
        return 0
    raise SystemExit("cq [run|add|revise|retire]")


def owe_for(d, r):
    """The concept that owes a re-read now that `r` is retired — its id added to the concept's `owes` — or None.
    A projection of a concept retired: what the concept's sentence was affirmed over has changed, and reconfirming the
    projections that remain answers only whether each still realizes it — not whether the sentence still says what the
    project does (guin-site, 2026-09-30: a deploy moved, three projections retired, three added, nine reconfirmed, and the
    sentence still named the old deploy). The concept owes a re-read until `concept revise` or `concept reaffirm`.
    Owes nothing: adding a projection; a `move`; a projection that is still there in another form — the same file (an
    anchor narrowed to a symbol) or the same name in another file (a refactoring done by hand: retire, re-propose) — and a
    source (grounding, not a projection of what the project does). Measured on guin-site's history: 73 retired projections,
    15 debts in 3 commits — the Workers deploy, the rewrite from Python to Astro, tags leaving the post header.
    `d["relations"]` must no longer hold `r` (nor anything retired with it)."""
    rf, rk = split_anchor(r["src"])
    still = [x for x in d["relations"] if x["predicate"] == "realizes" and x["dst"] == r["dst"]
             and (split_anchor(x["src"])[0] == rf or (rk and split_anchor(x["src"])[1] == rk))]
    if r["predicate"] != "realizes" or not r["dst"].startswith("concept:") or r["src"].startswith("source:") or still:
        return None
    owed = next((c for c in d["concepts"] if c["name"] == r["dst"][len("concept:"):]), None)
    if owed is not None and r["id"] not in owed.setdefault("owes", []):
        owed["owes"].append(r["id"])
    return owed


def owes_line(c):
    return ("  concept %s lost a projection: its sentence owes a re-read (%s) — `concept revise %s --means \"...\"` if it no longer holds, "
            "`concept reaffirm %s --by|--delegated` if it does; until then the questions it answers fail"
            % (c["name"], ", ".join(c["owes"]), c["name"], c["name"]))


def cmd_retire(args):
    if args.gone:
        if args.id:
            raise SystemExit("retire takes a relation id or --gone FILE.., not both")
        return retire_gone(args)
    if not args.id:
        raise SystemExit("retire <id> --why WHY, or retire --gone FILE.. --why WHY (every relation on files deleted on purpose)")
    d = decl(args.target)
    r = next((x for x in d["relations"] if x["id"] == args.id), None)
    if not r:
        raise SystemExit("no relation %s" % args.id)
    d["relations"].remove(r)
    d["retired"].append({**r, "retired": {"why": args.why}})
    owed = owe_for(d, r)
    save_decl(args.target, d)
    print("retired %s (%s %s %s) — kept in `retired`" % (r["id"], r["src"], r["predicate"], r["dst"]))
    if owed is not None:
        print(owes_line(owed))
    return 0


def file_of(anchor):
    """The tree file an anchor is in, or None for the net's own (`concept:`, `source:`)."""
    f = split_anchor(anchor)[0]
    return None if f in ("concept", "source") else f


def gone_from_tree(target, f):
    return f is not None and not os.path.exists(os.path.join(target, f))


def retire_gone(args):
    """Files deleted on purpose (a contract retired a backend, its routes, its scripts): every relation with an anchor in
    them is broken, and none has a home for `move` to find. Retiring them one by one — twenty-eight on guin-site, each with
    the same reason — is the session's afternoon; this is one command and one reason. Each is kept in `retired/` with the
    why and the file(s) gone; the files leave the registry; the concepts whose projections went with them owe a re-read
    (the `owes` rule, as for one retire). A path still in the tree is refused: what is there is not gone. A directory that
    is gone names every file under it the net knew."""
    d = decl(args.target)
    norm = lambda p: os.path.normpath(p.replace(os.sep, "/")).replace(os.sep, "/")
    known = {e["path"] for e in d["registry"]} | {f for r in d["relations"] for f in map(file_of, (r["src"], r["dst"])) if f}
    files = set()
    for p in args.gone:
        q = norm(p)
        if os.path.exists(os.path.join(args.target, q)):
            raise SystemExit("%s is still in the tree — `--gone` is for files deleted on purpose; a relation on a file that is there is "
                             "retired by its id (or moved: `move`)" % q)
        under = {f for f in known if f == q or f.startswith(q.rstrip("/") + "/")}
        if not under:
            raise SystemExit("%s: not registered, and no relation stands on it — nothing for the net to retire" % q)
        files |= under
    hits = [r for r in d["relations"] if any(file_of(a) in files for a in (r["src"], r["dst"]))]
    for r in hits:
        d["relations"].remove(r)
    owed = {}
    for r in hits:
        d["retired"].append({**r, "retired": {"why": args.why, "gone": sorted({file_of(a) for a in (r["src"], r["dst"]) if file_of(a) in files})}})
    for r in hits:
        c = owe_for(d, r)
        if c is not None:
            owed[c["name"]] = c
    before = len(d["registry"])
    d["registry"] = [e for e in d["registry"] if e["path"] not in files]
    save_decl(args.target, d)
    for r in hits:
        print("  retired %s (%s %s %s)" % (r["id"], r["src"], r["predicate"], r["dst"]))
    print("%d relation(s) retired — kept in `retired` with why: %s; %d file(s) unregistered: %s"
          % (len(hits), args.why, before - len(d["registry"]), ", ".join(sorted(files))))
    for name in sorted(owed):
        print(owes_line(owed[name]))
    return 0


def cmd_reconfirm(args):
    """A stale relation that still holds after someone read it. Only what the tree has now is recorded; a dead anchor is refused (retire it)."""
    if not (args.by or args.delegated or running_agent()):
        raise SystemExit("say who re-read it (--by) or why the human delegated it (--delegated)")
    # an agent that re-read it itself signs as itself: {"agent": ...} — no person's name, no made-up delegation
    sig = signature(args.by, args.delegated) if (args.by or args.delegated) else {"agent": running_agent()}
    d = decl(args.target)
    files, _ = snapshot(args.target, d["registry"])
    root = os.path.join(args.target, DECL, "relations")
    for rid in args.ids:
        r = next((x for x in d["relations"] if x["id"] == rid), None)
        if not r:
            raise SystemExit("no relation %s" % rid)
        held = drifted_end(d, r["src"], r["dst"])
        if held:
            # re-reading against a sentence known to be false records the false sentence as re-read (guin-site 748a4d8)
            raise SystemExit("%s: %s" % (rid, drift_refusal(d, held)))
        dead = [a for a in (r["src"], r["dst"]) if split_anchor(a)[0] not in files or split_anchor(a)[1] not in files[split_anchor(a)[0]]]
        if dead:
            raise SystemExit("%s: anchor %s is gone — a relation on a dead anchor cannot be re-confirmed; retire it" % (rid, dead))
        for a in (r["src"], r["dst"]):   # what the person re-read: the change itself, printed with the record of it
            if (r.get("seen") or {}).get(a) == files[split_anchor(a)[0]][split_anchor(a)[1]]:
                continue   # this end did not move: nothing of it to re-read (it used to say "only its fingerprint's rule changed")
            diff = what_changed(args.target, r, a)
            if diff:
                print("  %s changed since %s was confirmed:\n%s" % (a, rid, "\n".join("      " + l for l in diff.rstrip().split("\n"))))
        was = {"confirmed": r["confirmed"], "seen": r.get("seen"), "evidence": r["evidence"]}
        if args.evidence:
            r["evidence"] = args.evidence
        if not quoted(args.target, r["evidence"], r["src"], r["dst"]):
            raise SystemExit("%s: its evidence is no longer in the text (%r) — re-read and give the sentence that holds now: --evidence \"...\", or retire" % (rid, r["evidence"][:80]))
        # a re-confirmation is a judgment on top of the earlier one, not instead of it: who confirmed first, on what text,
        # and how many times this relation has been re-read stay in the file (they used to be overwritten — a record with no history)
        r.setdefault("history", []).append(was)
        r["seen"] = {a: files[split_anchor(a)[0]][split_anchor(a)[1]] for a in (r["src"], r["dst"])}
        r["confirmed"] = dict(sig)
        save(os.path.join(root, rid + ".json"), r)   # save_decl never rewrites an existing relation; this is the one command that does
        print("re-confirmed %s (%s %s %s)%s" % (rid, r["src"], r["predicate"], r["dst"], " as %s's own re-read — no person's" % sig["agent"] if sig.get("agent") else ""))
    return 0


def first_clause(text, limit=80):
    """A delegation's reason, cut to its first clause for a line that must stay short — the whole reason is in the record."""
    text = " ".join(str(text).split())
    cut = min([i for i in (text.find(c) for c in ("; ", ": ", " — ", ". ", "；", "。")) if i > 0] or [len(text)])
    text = text[:cut]
    return text if len(text) <= limit else text[:limit - 1] + "…"


def who_signed(sig):
    """The confirmer, as a terminal line: `by NAME (approved in source:…)` or `delegated: <first clause>` (said as delegated)."""
    sig = sig or {}
    if sig.get("by"):
        return "by %s" % sig["by"] + (" (approved in %s)" % sig["approved-in"] if sig.get("approved-in") else "")
    if sig.get("judge"):
        return "judged by %s, applied by %s" % (sig["judge"], sig.get("applied-by") or "?") + (" (read in %s)" % sig["approved-in"] if sig.get("approved-in") else "")
    if sig.get("agent"):
        return "by the agent %s, on its own" % sig["agent"]
    dl = sig.get("delegated")
    if isinstance(dl, dict):
        return "delegated: ref %s" % dl.get("ref", "?")
    return "delegated: %s" % first_clause(dl or "?") if dl else "unsigned"


def cmd_lookup(args):
    """Before touching a file: which confirmed relations stand on it, and what they say? The reverse index every drift tool
    grew (drift `refs`, docdrift `lookup`) — here so an agent can size its task as 'the edit plus these relations', instead
    of learning about them afterwards from `impact`. Grouped by what each relation reaches: a concept's `means` once, then
    each relation with its quote, its confirmer and whether it is fresh now — what agents on guin-site opened
    concepts/*.json and relations/*.json by hand to learn, because lookup printed only ids and names. A file with nothing
    on it says which of three it is: not registered (the net cannot see it), registered with nothing on it, or not in the
    tree — "no relations" read the same for all three, and a whole unregistered backend looked like a quiet one.
    Read-only; prints nothing but the record.
    Also takes a relation id (that relation, whole) and `concept:NAME` or another anchor (what stands on that anchor) — a
    session re-confirming typed `lookup R-49cec80b` and was told nothing touched it (guin-site, 10-09)."""
    d = decl(args.target)
    if RELATION_ID.fullmatch(args.path):
        args.path = "R-" + args.path[2:].lower()   # ids are written lower-case; a pasted R-3DE794C9 is the same one
        return lookup_relation(args, d)
    concepts = {"concept:" + c["name"]: c for c in d["concepts"]}
    if args.path.startswith("concept:") and args.path not in concepts:
        print("no concept %s — `concept list` names them" % args.path[len("concept:"):])
        return 1
    if args.path.startswith("source:") and args.path[len("source:"):] not in {x["id"] for x in d["sources"]}:
        print("no source %s — `source list` names them" % args.path[len("source:"):])
        return 1
    rels = []
    for r in d["relations"]:
        for a in (r["src"], r["dst"]):
            f, key = split_anchor(a)
            if f == args.path or a == args.path:
                prop = d["vocabulary"].get(r["predicate"], {}).get("propagates", "none")
                moves = (a == r["dst"] and prop in ("dst->src", "both")) or (a == r["src"] and prop in ("src->dst", "both"))
                other = r["dst"] if a == r["src"] else r["src"]
                if split_anchor(other)[0] == args.path:
                    other = r["dst"]   # both ends on this file: grouped under dst, as stored
                rels.append((r, a, other, moves))
                break
    path = args.path if os.path.exists(os.path.join(args.target, args.path)) or args.path.startswith("concept:") else split_anchor(args.path)[0]
    registered = any(e["path"] == path for e in d["registry"])
    on_disk = os.path.exists(os.path.join(args.target, path))
    if getattr(args, "brief", False):
        return lookup_brief(args, d, rels, registered, on_disk)
    c = concepts.get(args.path)
    if c is not None:   # the concept itself first: its meaning, and a mark when it is known wrong
        print("%s — means: %s" % (args.path, " ".join(c.get("means", "").split())))
        if c.get("drift"):
            print("  DRIFTED: %s — the sentence is known not to hold; `concept revise %s` owed" % (drift_line(c["drift"]), c["name"]))
        if not rels:
            print("nothing stands on %s — nothing realizes it" % args.path)
            return 0
    if not rels and args.path.startswith("source:"):
        print("%s is kept; no confirmed relation stands on it — it grounds nothing yet" % args.path)
        return 0
    if not rels and registered and on_disk and path != args.path:
        f, key = split_anchor(args.path)
        files, _ = snapshot(args.target, [e for e in d["registry"] if e["path"] == path])
        if key not in files.get(f, {}):
            print("%s: %s is registered, but has no %s now — no such heading, symbol or key (moved or renamed? `lookup %s` names what stands on the file)"
                  % (args.path, f, key, f))
            return 1
    if not rels:
        if registered:
            print("%s is registered; no confirmed relation stands on it — an edit here makes nothing stale%s"
                  % (args.path, "" if on_disk else " (it is not in the tree now: deleted or moved? `register` the new path)"))
        elif not on_disk:
            print("%s is not in the tree (no such file under %s) and not registered — nothing stands on it" % (args.path, args.target))
        else:
            tracked = tracked_files(args.target)
            near = ""
            if tracked is not None and args.path in tracked:
                parts = args.path.split("/")[:-1]
                for n in range(len(parts), -1, -1):   # the nearest directory holding registered files: "beside" them
                    pre = "/".join(parts[:n]) + "/" if n else ""
                    have = [e["path"] for e in d["registry"] if e["path"].startswith(pre)]
                    if have:
                        near = ", beside %d registered file(s) under %s" % (len(have), pre or "the root")
                        break
            print("%s is NOT REGISTERED%s — the net cannot see it: no relation stands on it and no edit to it is ever stale. "
                  "Not a file with nothing on it: an unseen one." % (args.path, " (tracked by git%s)" % near if tracked is not None and args.path in tracked else ""))
            print("  to watch it: `mangsang register %s`, then relate its anchors to the concepts they realize (`confirm`)" % args.path)
        return 0
    stale, broken, unjudged, _ = compute_impact(args.target, d, persist=False)
    state = {x["id"]: "STALE now (%s changed since confirmed)" % x["because"] for x in stale}
    state.update({x["id"]: "BROKEN now (%s gone)" % ", ".join(x["dead"]) for x in broken})
    state.update({i: "unjudged (no `seen`, no baseline)" for i in unjudged if i not in state})
    groups = {}
    for item in rels:
        groups.setdefault(item[2], []).append(item)
    for other in sorted(groups):
        c = concepts.get(other)
        if c is not None:
            print("%s — means: %s" % (other, " ".join(c.get("means", "").split())))
            if c.get("drift"):
                print("  DRIFTED: %s — the sentence is known not to hold; `concept revise %s` owed" % (drift_line(c["drift"]), c["name"]))
        elif other.startswith("concept:"):
            print("%s — no such concept is declared" % other)
        else:
            print(other)
        for r, a, _, moves in groups[other]:
            # the relation as it is stored, src predicate dst — never reordered around the looked-up anchor (a reader who copied
            # the line into a proposal got src and dst swapped when the anchor was the dst)
            mark = lambda x: "[%s]" % x if x == a else x
            print("  %s  %s %s %s — %s%s" % (r["id"], mark(r["src"]), r["predicate"], mark(r["dst"]), state.get(r["id"], "fresh"),
                                            "; changing this anchor makes the relation stale" if moves else ""))
            print("      \"%s\" — %s" % ("\n        ".join(r.get("evidence", "").split("\n")), who_signed(r.get("confirmed"))))
    print("%d relation(s) on %s, reaching %d concept(s) or anchor(s) — an edit here and their update are one piece of work, not two"
          % (len(rels), args.path, len(groups)))
    return 0


RELATION_ID = re.compile(r"[Rr]-[0-9a-fA-F]{8}")


def lookup_relation(args, d):
    """`lookup R-xxxxxxxx`: one relation as `lookup` shows it — its ends (a concept's meaning, and its drift mark), its state now,
    its quote and who confirmed it, how often it was re-read. A retired one says so, with why."""
    r = next((x for x in d["relations"] if x["id"] == args.path), None)
    if not r:
        gone = next((x for x in d.get("retired", []) if x["id"] == args.path), None)
        if gone:
            why = gone.get("retired")
            print("%s is retired: %s %s %s — %s" % (gone["id"], gone["src"], gone["predicate"], gone["dst"], why.get("why", "?") if isinstance(why, dict) else why))
            return 0
        print("no relation %s — `lookup` takes a relation id, `concept:NAME`, a file (as registered) or an anchor in one" % args.path)
        return 1
    stale, broken, unjudged, _ = compute_impact(args.target, d, persist=False)
    state = {x["id"]: "STALE now (%s changed since confirmed)" % x["because"] for x in stale}
    state.update({x["id"]: "BROKEN now (%s gone)" % ", ".join(x["dead"]) for x in broken})
    state.update({i: "unjudged (no `seen`, no baseline)" for i in unjudged if i not in state})
    for a in (r["src"], r["dst"]):
        c = next((c for c in d["concepts"] if "concept:" + c["name"] == a), None)
        if c is not None:
            print("%s — means: %s" % (a, " ".join(c.get("means", "").split())))
            if c.get("drift"):
                print("  DRIFTED: %s — the sentence is known not to hold; `concept revise %s` owed, not a re-confirmation" % (drift_line(c["drift"]), c["name"]))
    print("  %s  %s %s %s — %s" % (r["id"], r["src"], r["predicate"], r["dst"], state.get(r["id"], "fresh")))
    print("      \"%s\" — %s%s" % ("\n        ".join(r.get("evidence", "").split("\n")), who_signed(r.get("confirmed")),
                                  "; re-confirmed %d time(s)" % len(r["history"]) if r.get("history") else ""))
    files = sorted({split_anchor(a)[0] for a in (r["src"], r["dst"])} - {"concept", "source"})
    if files:
        print("everything else on its file(s): %s" % "; ".join("`mangsang lookup %s`" % f for f in files))
    return 0


BRIEF_AT_LEAST = 10   # a first sentence shorter than this ("첫 화면.", five characters) names a thing without saying it: the next follows


def first_sentence(text, limit=160):
    """A concept's `means`, cut to its first sentence and to one short line — the whole sentence is in the record. A first
    sentence too short to say anything ("첫 화면." — the home page, of what?) is followed by the next, the line cut at the limit."""
    text = " ".join(str(text).split())
    out, rest = "", text
    while rest and len(out) < BRIEF_AT_LEAST:
        m = re.search(r"[.!?。](\s|$)", rest)
        piece = rest[:m.end()].rstrip() if m else rest
        out = (out + " " + piece).strip() if out else piece
        rest = rest[m.end():].strip() if m else ""
    return out if len(out) <= limit else out[:limit - 1].rstrip() + "…"


BRIEF_LINES = 5


def lookup_brief(args, d, rels, registered, on_disk):
    """`lookup PATH --brief`: what a reader (jokbo) puts in front of an agent at its first look at a file — one line per concept
    (or other end) the file's confirmed relations reach, its meaning's first sentence, and how many of them are stale when any is.
    Whole outputs pasted into an agent's context were not read (~43k characters in one cycle); a line per fact is. No ids, no
    quotes: `lookup PATH` has them. A tracked file the net does not see gets one line saying so; a registered file with nothing
    on it, or a path not in the tree, prints nothing — a reader adds no line where there is no fact. A concept: its own line."""
    c = next((c for c in d["concepts"] if "concept:" + c["name"] == args.path), None)
    if c is not None:
        stale, broken, _, _ = compute_impact(args.target, d, persist=False) if rels else ([], [], [], [])
        k = len({x["id"] for x in stale + broken} & {r["id"] for r, _, _, _ in rels})
        print("%s — %s%s (%d relation(s)%s)" % (args.path, first_sentence(c.get("means", "")),
                                               " [DRIFTED, known not to hold: %s]" % first_clause(c["drift"].get("why", "?"), 80) if c.get("drift") else "",
                                               len(rels), "; %d stale" % k if k else ""))
        return 0
    if not rels:
        if registered or not on_disk:
            return 0
        tracked = tracked_files(args.target)
        if tracked is None or args.path in tracked:
            print("%s: not registered — the net does not see it (no relation stands on it; edits here are never stale)" % args.path)
        return 0
    stale, broken, _, _ = compute_impact(args.target, d, persist=False)
    bad = {x["id"] for x in stale} | {x["id"] for x in broken}
    concepts = {"concept:" + c["name"]: c for c in d["concepts"]}
    groups = {}
    for r, a, other, _ in rels:
        groups.setdefault(other, []).append(r)
    order = sorted(groups, key=lambda o: (-sum(r["id"] in bad for r in groups[o]), not o.startswith("concept:"), -len(groups[o]), o))
    shown = order if len(order) <= BRIEF_LINES else order[:BRIEF_LINES - 1]
    for other in shown:
        rs = groups[other]
        k = sum(r["id"] in bad for r in rs)
        c = concepts.get(other)
        say = first_sentence(c.get("means", "")) if c else ", ".join(sorted({r["predicate"] for r in rs}))
        if c and c.get("drift"):
            say += " [DRIFTED, known not to hold: %s]" % first_clause(c["drift"].get("why", "?"), 80)
        print("%s — %s%s" % (other, say, " (%d relation(s); %d stale)" % (len(rs), k) if k else ""))
    if len(shown) < len(order):
        rest = order[len(shown):]
        k = sum(r["id"] in bad for o in rest for r in groups[o])
        print("… and %d more (%d relation(s)%s) — `mangsang lookup %s` for all"
              % (len(rest), sum(len(groups[o]) for o in rest), "; %d stale" % k if k else "", args.path))
    return 0


def concept_map(args, d):
    """`concept list --brief`: the net in a line or two, for a reader's session-start map — how many concepts and their names
    (cut to fit), the open questions, and how many relations are stale or broken when any are. An empty net prints nothing."""
    if not d["concepts"] and not d["relations"]:
        return 0
    names = sorted(c["name"] for c in d["concepts"])
    opened = sum(1 for q in cq_active(d) if (q.get("verify") or {}).get("kind") == "open")
    gone = sorted(c["name"] for c in d["concepts"] if c.get("drift"))
    tail = (" ; %d open question(s)" % opened if opened else "") + (" ; drifted (meaning known wrong, revision owed): %s" % ", ".join(gone) if gone else "")
    head = "%d concept(s): " % len(names)
    shown, budget = [], 300 - len(head) - len(tail) - len(", … (+999)")
    for n in names:
        if len(", ".join(shown + [n])) > budget:
            break
        shown.append(n)
    listed = ", ".join(shown) + (", … (+%d)" % (len(names) - len(shown)) if len(shown) < len(names) else "")
    print(head + (listed or "none declared") + tail)
    stale, broken, _, _ = compute_impact(args.target, d, persist=False) if d["relations"] else ([], [], [], [])
    owed = owed_rereads(d)
    if stale or broken or owed:
        print("%d relation(s); %s — `mangsang impact` lists them" % (len(d["relations"]), "; ".join(
            x for x in ("%d stale" % len(stale) if stale else "", "%d broken" % len(broken) if broken else "",
                        "%d concept(s) owe a re-read" % len(owed) if owed else "") if x)))
    # what the net cannot see, counted, so it reaches the session at its start and not only whoever runs `check`
    active = [q for q in cq_active(d) if q.get("verify", {}).get("kind") in INVARIANT_KINDS]
    _, near, blind, loose_files = unseen_groups(args.target, d, active)
    named = lambda gs: ", ".join("%s %d%s" % (g["group"], len(g["files"]), " changed after the net" if g["after_net"] else " changed lately" if g["ago"] is not None else "")
                                 for g in gs[:3]) + (", … +%d" % (len(gs) - 3) if len(gs) > 3 else "")
    groups = sorted(blind + near, key=lambda g: (g["ago"] is None, g["ago"] or 0, g in near, g["group"]))
    if groups:
        print("%d tracked file(s) unseen (%s) — a file nothing relates to is invisible to impact; `mangsang check` gives the commands"
              % (sum(len(g["files"]) for g in groups), named(groups)))
    if loose_files:
        print("%d registered file(s) nothing relates to (%s) — an edit there makes nothing stale; `mangsang check` says how to relate them"
              % (sum(len(g["files"]) for g in loose_files), named(loose_files)))
    return 0


def cmd_move(args):
    """A refactoring moved a symbol or a section: the anchor died and the relation on it is `broken`, though the thing it
    named is right there under another file. Retire-and-repropose by hand for twenty-one relations was a refactoring's
    afternoon (and three were missed, found by counting). `move` does the mechanical part: for each broken relation whose
    dead anchor is `file:symbol` or `file#heading`, the registered files are searched for the same key; exactly one home ->
    the relation is retired (why: moved) and re-confirmed on the new anchor with the same evidence — which must still be a
    quote there, or the move is refused for that relation. Ambiguous (two homes) or homeless keys are printed, untouched:
    naming the home is a judgment. `--dry-run` only reports."""
    if not (args.by or args.delegated or args.dry_run):
        raise SystemExit("say who moves them (--by) or why the human delegated it (--delegated), or --dry-run to see what would move")
    d = decl(args.target)
    _, broken, _, files = compute_impact(args.target, d, persist=False)
    wanted = set(args.ids or [])
    moved, refused = [], []
    for b in broken:
        r = next((x for x in d["relations"] if x["id"] == b["id"]), None)
        if not r or (wanted and r["id"] not in wanted):
            continue
        new = dict(r)
        why = drift_refusal(d, drifted_end(d, r["src"], r["dst"])) if drifted_end(d, r["src"], r["dst"]) else None
        for end in ("src", "dst") if not why else ():
            if r[end] not in b["dead"]:
                continue
            f, key = split_anchor(r[end])
            if not key or f in ("concept", "source"):
                why = "%s is not a moved symbol or section" % r[end]
                break
            # a home is a file of the same kind (config keys as anchors made every common key ambiguous): `homes_of`
            cands = homes_of(files, r[end])
            if len(cands) != 1:
                why = "%s: %s" % (r[end], "no registered file has %s now" % key if not cands else "%s is in %s — say which" % (key, ", ".join(cands)))
                break
            new[end] = cands[0] + key
        if not why and new["src"] == r["src"] and new["dst"] == r["dst"]:
            why = "nothing to move"
        if not why and not quoted(args.target, r["evidence"], new["src"], new["dst"]):
            why = "the evidence %r is not in the text at %s — the words moved too; propose it anew with the sentence that holds there" % (r["evidence"][:60], new["src"] if new["src"] != r["src"] else new["dst"])
        if why:
            refused.append((r, why))
            continue
        moved.append((r, new))
    for r, why in refused:
        print("  left    %s  %s %s %s — %s" % (r["id"], r["src"], r["predicate"], r["dst"], why))
    for r, new in moved:
        print("  %s %s -> %s %s %s" % ("would move" if args.dry_run else "moved", r["id"], new["src"], new["predicate"], new["dst"]))
    if args.dry_run or not moved:
        print("%d relation(s) %s, %d left" % (len(moved), "would move" if args.dry_run else "moved", len(refused)))
        return 0 if moved or not refused else 1
    root = os.path.join(args.target, DECL, "relations")
    known = {x["id"] for x in d["relations"]}
    for r, new in moved:
        d["relations"].remove(r)
        d["retired"].append({**r, "retired": {"why": "moved: %s %s %s -> %s %s %s" % (r["src"], r["predicate"], r["dst"], new["src"], new["predicate"], new["dst"])}})
        nid = rel_id(new)
        if nid in known:
            print("  (the relation already exists at %s as %s; the old one is retired)" % (new["src"], nid))
            continue
        known.add(nid)
        d["relations"].append({"id": nid, "src": new["src"], "predicate": new["predicate"], "dst": new["dst"], "evidence": r["evidence"],
                               "seen": {a: files[split_anchor(a)[0]][split_anchor(a)[1]] for a in (new["src"], new["dst"])},
                               "confirmed": signature(args.by, args.delegated), "moved-from": r["id"]})
    save_decl(args.target, d)
    print("%d relation(s) moved (the old ones retired with why: moved), %d left for a person" % (len(moved), len(refused)))
    return 0 if not refused else 1


def transcript_records(path):
    """The host's records, one JSON object per line, in order (a line that is not one is skipped)."""
    for line in io.open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict):
            yield d


def transcript_turns(path):
    """A host session transcript (Claude Code's JSONL) as the turns a person would recognize: what the person typed, what the
    agent answered in text (blocks of one message joined), each multiple-choice question it asked and the answer it got —
    each as the host recorded it, with its id, time and (for the agent) model. Tool traffic other than questions is left out:
    it is how the agent worked, not what was said. A turn the person typed right after the agent's turn is also an answer
    to it (`answers`: that turn's id) — "ㄱㄱ" and "1번" are answers as much as a choice picked in a question is."""
    turns, agent, n = [], {}, -1
    for n, d in enumerate(transcript_records(path)):
        if d.get("isSidechain") or d.get("isCompactSummary"):
            continue   # a subagent's side talk; the host's summary of a compacted session, filed as a user record — no one said either
        for t in turns[::-1]:   # each turn knows its record's place, so a phrase found elsewhere can be shown among its neighbours
            if "n" in t:
                break
            t["n"] = n - 1
        msg, when, uid = d.get("message") or {}, d.get("timestamp"), d.get("uuid")
        c = msg.get("content")
        if d.get("type") == "user" and isinstance(c, str) and not d.get("isMeta"):
            turns.append({"kind": "person", "text": c, "uuid": uid, "at": when})
        elif d.get("type") == "user" and isinstance(c, list):
            for x in c:
                if isinstance(x, dict) and x.get("type") == "text" and not d.get("isMeta"):
                    turns.append({"kind": "person", "text": x.get("text", ""), "uuid": uid, "at": when})
                if isinstance(x, dict) and x.get("type") == "tool_result" and x.get("tool_use_id") in agent.get("asks", {}):
                    ask = agent["asks"][x["tool_use_id"]]
                    got = picked_answers(d, x, ask["questions"])
                    for i, (q, a) in enumerate(got):
                        # one turn per question answered, its text only what the person picked or typed: the tool's
                        # wrapper ("Your questions have been answered: "Q"="A", … You can now continue…") is the host
                        # talking to the agent, not the person; the question it answers is named, not quoted into it
                        turns.append({"kind": "answer", "text": a, "uuid": uid if len(got) == 1 else "%s#%d" % (uid, i + 1), "at": when,
                                      "answers": ask["uuid"], "question": q})
        elif d.get("type") == "assistant" and isinstance(c, list):
            mid = msg.get("id") or uid
            for x in c:
                if not isinstance(x, dict):
                    continue
                if x.get("type") == "text":
                    last = turns[-1] if turns else None
                    if last and last.get("kind") == "agent" and last.get("message") == mid:
                        last["text"] += "\n\n" + x.get("text", "")
                    else:
                        turns.append({"kind": "agent", "text": x.get("text", ""), "uuid": uid, "at": when, "message": mid, "model": msg.get("model")})
                elif x.get("type") == "tool_use" and x.get("name") == "AskUserQuestion":
                    agent.setdefault("asks", {})[x.get("id")] = {"uuid": uid, "questions": [
                        q.get("question", "") for q in ((x.get("input") or {}).get("questions") or []) if isinstance(q, dict)]}
                    turns.append({"kind": "question", "text": json.dumps(x.get("input"), ensure_ascii=False, indent=1), "uuid": uid, "at": when,
                                  "model": msg.get("model")})
    for t in turns[::-1]:
        if "n" in t:
            break
        t["n"] = n
    host_notes = ("<task-notification>", "<local-command", "<command-name>", "<system-reminder>", "[Request interrupted")
    turns = [t for t in turns if t["text"].strip() and not (t["kind"] == "person" and t["text"].lstrip().startswith(host_notes))]
    for before, t in zip([None] + turns, turns):
        if t["kind"] == "person" and before and before["kind"] in ("agent", "question"):
            t["answers"] = before["uuid"]
    return turns


def picked_answers(record, result, questions):
    """[(question, what the person picked or typed)] from one AskUserQuestion result, in the questions' order. The host's
    structured record (`toolUseResult.answers`, keyed by question) when it is there; otherwise read out of the tool's
    text, `"QUESTION"="ANSWER"`, for the questions the agent asked. A note the person typed beside a choice
    (`annotations[Q].notes`) is theirs and kept under the answer; a preview the agent drew is not. Nothing that can be
    read out (a question declined, a shape this does not know) -> [] — never the wrapper in the person's mouth."""
    tr = record.get("toolUseResult")
    if isinstance(tr, dict) and isinstance(tr.get("answers"), dict):
        notes = tr.get("annotations") if isinstance(tr.get("annotations"), dict) else {}
        order = [q for q in questions if q in tr["answers"]] + [q for q in tr["answers"] if q not in questions]
        out = []
        for q in order:
            a = tr["answers"][q]
            a = ", ".join(map(str, a)) if isinstance(a, list) else str(a)
            note = (notes.get(q) or {}).get("notes") if isinstance(notes.get(q), dict) else None
            out.append((q, a + ("\n" + note if isinstance(note, str) and note.strip() else "")))
        return [(q, a) for q, a in out if a.strip()]
    if result.get("is_error"):
        return []
    body = result.get("content")
    body = "\n".join(b.get("text", "") for b in body if isinstance(b, dict)) if isinstance(body, list) else str(body or "")
    out = []
    for q in questions:
        m = re.search(re.escape('"%s"="' % q) + r'((?:[^"\\]|\\.)*)"', body)
        if m and m.group(1).strip():
            out.append((q, m.group(1).replace('\\"', '"')))
    return out


def turn_named(t, turn_id):
    """--turn ID: the host's id for the record — which names every answer in it when one question form asked several
    (`ID#1`, `ID#2`, …: each its own turn; the listing shows them) — or one of those."""
    return t["uuid"] == turn_id or t["uuid"].split("#")[0] == turn_id


def turn_hit(t, match, turn_id, kind):
    """Is `t` the turn `--match`/`--turn`/`--kind` ask for? An answer picked in a question form is found by what it answers
    too: a phrase of its question, or the question form's id (each answer `ID#k` is then its own turn). sagoforce 10-26:
    `--match "1/6" --kind answer` (the phrase was the question's, the answer "맞다") and `--turn <the form's id> --kind
    answer` were both refused as "no answer turn", and the agent read the transcript by hand for the result's id."""
    asked = kind == "answer" and t.get("question") is not None
    return ((not match or match in t["text"] or (asked and match in t["question"]))
            and (not turn_id or turn_named(t, turn_id) or (asked and t.get("answers") == turn_id)) and turn_is(t, kind))


def turn_is(t, kind):
    """--kind KIND: a typed reply right after the agent's turn is a `person` turn and an `answer` both; an agent's text turn
    that asks the person (a line of it ends with a question mark) is an `agent` turn and a `question` both — guin-site, 10-15:
    "…이대로 확정할까요?" was refused as "no question turn", a question being only a question-form tool call."""
    return (not kind or t["kind"] == kind or (kind == "answer" and t["kind"] == "person" and bool(t.get("answers")))
            or (kind == "question" and t["kind"] == "agent" and bool(re.search(r"[?？]\s*$", t["text"], re.M))))


def record_place(d):
    """Where in the host's record a phrase sits when it is in no turn: the agent's thinking, a tool call, a tool's output…"""
    msg = d.get("message") or {}
    c = msg.get("content")
    if d.get("isSidechain"):
        return "a subagent's side conversation"
    if d.get("type") == "assistant" and isinstance(c, list):
        kinds = [x.get("type") for x in c if isinstance(x, dict)]
        if "tool_use" in kinds:
            return "the agent's %s call" % next(x.get("name") for x in c if isinstance(x, dict) and x.get("type") == "tool_use")
        if "thinking" in kinds:
            return "the agent's thinking (never shown as said)"
    if d.get("type") == "user" and isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
        return "a tool's output"
    if d.get("type") == "user" and (d.get("isMeta") or isinstance(c, str)):
        return "a host note (a command, a reminder, a notification)"
    return "the host's %s record" % (d.get("type") or "")


def strings_in(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings_in(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings_in(v)


def turn_line(t):
    return "  %s %s at %s%s: %s" % (t["kind"], t["uuid"], t["at"], " (answers %s)" % t["answers"] if t.get("answers") else "",
                                    " ".join(t["text"].split())[:80])


def why_no_turn(path, turns, match, turn_id, kind):
    """Nothing matched: say what the transcript has there — turns of another kind that contain the phrase, or the record it
    is in (thinking, a tool call) and the turns around it — and how to name one. "found 0 turn(s)" said none of this."""
    out = []
    asked = ("--match %r" % match if match else "") + (" --turn %s" % turn_id if turn_id else "") + (" --kind %s" % kind if kind else "")
    near = [t for t in turns if (not match or match in t["text"]) and (not turn_id or turn_named(t, turn_id))]
    if near:
        out.append("%s: no %s turn — the turn(s) there are of another kind; name one with --kind KIND or --turn ID:" % (asked.strip(), kind))
        out += [turn_line(t) for t in near[-5:]]
        return "\n".join(out)
    found = [(n, d) for n, d in enumerate(transcript_records(path))
             if (turn_id and d.get("uuid") == turn_id) or (match and any(match in x for x in strings_in(d.get("message") or d)))]
    if found:
        # a tool call often holds the phrase only because the agent passed it (this very command, or a grep for it): the
        # other places say more, so the turns shown are around the first of those
        places = {}
        for n, d in found:
            places.setdefault(record_place(d), []).append(d.get("uuid"))
        out.append("%s: found in no turn — it is in %s; none of that is something said." % (asked.strip(), "; ".join(
            "%s (%s)" % (k, ", ".join(v[:2]) + (" and %d more" % (len(v) - 2) if len(v) > 2 else "")) for k, v in places.items())))
        n = next((n for n, d in found if d.get("type") != "assistant" or "call" not in record_place(d)), found[0][0])
        around = [t for t in turns if t["n"] < n][-2:] + [t for t in turns if t["n"] > n][:2]
        if around:
            out.append("the turns around it — keep the one that was said, by --turn ID:")
            out += [turn_line(t) for t in around]
        return "\n".join(out)
    out.append("%s: nothing in this transcript has it — is it the session the words were said in? The latest turns, by --turn ID:" % asked.strip())
    out += [turn_line(t) for t in turns[-3:]]
    return "\n".join(out)


AGENT_NAMES = ("Claude", "Claude Code", "Codex")   # how a host agent is called when it is not named by its model
_ROSTER_SAID = set()


def people(target):
    """`mangsang/people.json` — who may sign and speak here: {"people": [names], "agents": [speaker prefixes]}. Absent, any
    name is taken (the old behavior); present, a name that is not on it is refused, so a signature cannot be made up from
    an account or an email. mangsang never writes it — a person (or an agent, on their word) does — so it is read
    tolerantly: an entry that is no name (not a string, empty, only spaces — an empty prefix would admit every speaker) is
    left out, and said on stderr with the repair. `"Claude ("` is a prefix, not a broken name: it admits what an agent's
    turn is kept under, `Claude (<model>)`."""
    path = os.path.join(target, DECL, "people.json")
    if not os.path.exists(path):
        return None
    roster = load(path)
    if not isinstance(roster, dict):
        sys.stderr.write("mangsang/people.json is not an object — write it as {\"people\": [names], \"agents\": [speaker prefixes]}; read as absent\n")
        return None
    out = {}
    for field in ("people", "agents"):
        v = roster.get(field) or []
        v = v if isinstance(v, list) else [v]
        good = [x.strip() if field == "people" else x for x in v if isinstance(x, str) and x.strip()]
        bad = [x for x in v if not (isinstance(x, str) and x.strip())]
        if bad and (target, field) not in _ROSTER_SAID:
            _ROSTER_SAID.add((target, field))   # said once per command, not at every check
            sys.stderr.write("mangsang/people.json: %s holds %s, which name%s nobody — left out; remove %s from the file\n"
                             % (field, ", ".join(json.dumps(x, ensure_ascii=False) for x in bad), "" if len(bad) > 1 else "s", "them" if len(bad) > 1 else "it"))
        out[field] = good
    return {**roster, **out}


def check_person(target, name, as_speaker=False, agent_turn=None):
    """A name may sign (`people`) or speak (`people`, or an `agents` prefix). `agent_turn`: the name the host's record gives
    the turn being kept (`Claude (<model>)`), when it is an agent's — the fix to name when a bare agent name is refused."""
    roster = people(target)
    if not roster or name is None:
        return
    agents = roster.get("agents", [])
    if name in roster.get("people", []) or (as_speaker and any(name.startswith(a) for a in agents)):
        return
    near = [a for a in agents if a.rstrip(" (").strip() == name.strip() or (a.startswith(name) and len(name) >= 3)]
    if as_speaker and (agent_turn or near or name in AGENT_NAMES):
        # an agent named without its model (guin-site, 10-12: `--speaker Claude` on a question turn, refused with advice to ask the
        # person for a name, and the answer that replied to it failed after it)
        if agent_turn and any(agent_turn.startswith(a) for a in agents):
            raise SystemExit("--speaker %s: this turn is the agent's, and the roster's agents are speaker prefixes (%s) — an agent speaks under "
                             "its model's name. Drop `--speaker %s`: the turn is kept as %r, which the roster admits"
                             % (name, ", ".join(json.dumps(a, ensure_ascii=False) for a in agents), name, agent_turn))
        if agents:
            raise SystemExit("--speaker %s: people.json's agents are speaker prefixes (%s), and %r starts with none — an agent speaks under its "
                             "model's name: `--speaker \"%s<model id>)\"` (or `--from-transcript … --kind agent|question` without --speaker, "
                             "which names it from the record)" % (name, ", ".join(json.dumps(a, ensure_ascii=False) for a in agents), name,
                                                                   near[0] if near and near[0].endswith("(") else "Claude ("))
        raise SystemExit("--speaker %s: mangsang/people.json lists no agents — an agent's turn is kept as `Claude (<model id>)`; to let agents "
                         "speak, add the prefix: `\"agents\": [\"Claude (\"]`" % name)
    raise SystemExit("%r is not in mangsang/people.json — ask the person which name they sign and speak under and add it there; "
                     "never derive one from an account, an email or session metadata" % name)


def excerpt_of(text, parts):
    """The given parts of a turn, each whole sentences of it and verbatim, in the turn's order. Two parts the turn holds side
    by side (only spaces between them) keep the turn's own spacing; parts with anything left out between them are joined
    by a newline. A part
    not in the turn, or one that starts or ends inside a sentence, is refused: an excerpt that could change what was said
    is not an excerpt."""
    found = []
    for part in parts:
        part = part.strip()
        i = text.find(part)
        if not part or i < 0:
            raise SystemExit("--excerpt %r is not in the turn, verbatim — copy the sentence(s) exactly as they were said" % part[:60])
        before, after = text[:i].rstrip(" \t"), text[i + len(part):]
        starts_whole = not before or before[-1] in ".!?\n" or before.endswith(("다.", "요.")) or before[-1] in "…"
        ends_whole = part[-1] in ".!?…" or not after.strip(" \t") or after.lstrip(" \t")[:1] in ("\n", "")
        if not (starts_whole and ends_whole):
            raise SystemExit("--excerpt %r cuts a sentence — an excerpt is whole sentences (from after a . ! ? or a line break, to one); "
                             "when the turn does not split cleanly, keep it whole" % part[:60])
        found.append((i, part))
    out, end = "", None
    for i, part in sorted(found):
        gap = text[end:i] if end is not None else ""
        out += (gap if end is not None and gap.strip(" \t") == "" and "\n" not in gap else ("\n" if end is not None else "")) + part
        end = i + len(part)
    return out


def cmd_source(args):
    """What a person said or wrote, kept verbatim as the anchor `source:ID`. A model built from a conversation needs its
    ground on record the way a model built from a plan has the plan: the concept's `means` is the project's reading, the
    source is what was actually said, and the relation between them carries the quote — so a later reader can check the
    reading against the words, and a revised meaning stales the grounding like any projection. A source never changes:
    a correction is a new source (the person said something else later), never an edit — the same id with other text
    is refused. The engine does not read meaning out of it; the agent proposes, a person confirms, as everywhere."""
    d = decl(args.target)
    folder = os.path.join(args.target, DECL, "sources")
    if args.mode == "list":
        for x in d["sources"]:
            used = [r["id"] for r in d["relations"] if "source:" + x["id"] in (r["src"], r["dst"])]
            print("  %s  %s%s%s — %s" % (x["id"], x["speaker"], " (%s)" % x["locator"] if x.get("locator") else "",
                                        ", replying to %s" % x["replies-to"] if x.get("replies-to") else "",
                                        "grounds %s" % ", ".join(used) if used else "grounds nothing yet"))
        print("%d source(s)" % len(d["sources"]))
        return 0
    if not re.fullmatch(r"[\w-]+", args.id or ""):
        raise SystemExit("a source id is a word: letters, digits, _ or -")
    if args.from_transcript:
        # the words taken from the host's own record of the session, not retyped: exactly one turn — the one --turn names
        # (the host's id for it), or the one that contains --match. A short approval ("ok", "go") recurs; a phrase cannot
        # tell those apart, the host's id can
        if not (args.match or args.turn):
            raise SystemExit("--from-transcript needs --match \"a phrase from the turn\" (or --turn ID) — the one turn that contains it is kept, whole")
        turns = transcript_turns(args.from_transcript)
        hits = [t for t in turns if turn_hit(t, args.match, args.turn, args.kind)]
        if not hits:
            raise SystemExit(why_no_turn(args.from_transcript, turns, args.match, args.turn, args.kind))
        if len(hits) != 1:
            raise SystemExit("%s found %d turn(s) in the transcript — give a phrase that only the turn you mean contains, or --turn ID "
                             "(the latest are listed last):\n%s" % ("--turn" if args.turn and not args.match else "--match", len(hits),
                             "\n".join(turn_line(t) for t in hits[-5:])))
        turn = hits[0]
        if turn["kind"] in ("agent", "question"):
            args.speaker = args.speaker or "Claude (%s)" % (turn.get("model") or "unknown model")
        elif not args.speaker:
            # the person's turn: with one person on the roster, it is theirs (guin-site, 10-15: the refusal sent the agent to pass
            # the account name, the very thing it warns against — it was the roster's one name, but by luck)
            listed = (people(args.target) or {}).get("people") or []
            if len(listed) != 1:
                raise SystemExit("this turn is the person's: --speaker says who they are (the name they gave, not one read from the account)"
                                 + ("; mangsang/people.json lists %s" % ", ".join(listed) if listed else ""))
            args.speaker = listed[0]
            print("speaker: %s — the one person in mangsang/people.json (--speaker NAME, when another said it)" % listed[0])
        session = os.path.splitext(os.path.basename(args.from_transcript))[0]
        args.locator = args.locator or "session %s, %s %s at %s%s" % (session, turn["kind"], turn["uuid"], turn["at"],
                                                                      ", answering %s" % turn["answers"] if turn.get("answers") and args.kind == "answer" and not turn.get("question") else
                                                                      ", answering question %s: \"%s\"" % (turn["answers"], turn["question"]) if turn.get("question") else "")
        if turn.get("question") and not args.replies_to:
            # the question form kept as a source already: the answer replies to it, as a typed reply would be told to
            asked = next((y for y in d["sources"] if ", question %s at " % turn["answers"] in (y.get("locator") or "")), None)
            if asked:
                args.replies_to = asked["id"]
        args.file = None
        text = turn["text"].replace("\r\n", "\n")
        if args.excerpt:
            # a turn that clearly splits into sentences keeps only the ones that ground or approve something: "yes, that
            # one. And can you also draw it?" is an approval and a new request, and only the first belongs to the record
            # that cites it. Each excerpt is whole sentences of the turn, verbatim; a cut mid-sentence is refused.
            text = excerpt_of(text, args.excerpt)
    else:
        if not (args.file and args.speaker):
            raise SystemExit("--file (the words, verbatim; `-` reads stdin) or --from-transcript, and --speaker (who said them) — a source without both is hearsay")
        text = (sys.stdin.read() if args.file == "-" else io.open(args.file, encoding="utf-8").read()).replace("\r\n", "\n")
    check_person(args.target, args.speaker, as_speaker=True,
                 agent_turn="Claude (%s)" % (turn.get("model") or "unknown model") if args.from_transcript and turn["kind"] in ("agent", "question") else None)
    if not text.strip():
        raise SystemExit("%s is empty" % ("stdin" if args.file == "-" else args.file))
    if args.replies_to and not any(y["id"] == args.replies_to for y in d["sources"]):
        # an answer is only as meaningful as its question: "both are right" records nothing unless the turn it answers is kept too
        raise SystemExit("--replies-to %s: no such source — keep the turn it answers first (whoever said it)" % args.replies_to)
    x = {"id": args.id, "text": text, "speaker": args.speaker, **({"locator": args.locator} if args.locator else {}),
         **({"replies-to": args.replies_to} if args.replies_to else {})}
    old = next((y for y in d["sources"] if y["id"] == args.id), None)
    if old:
        if old["text"] == text:
            print("source %s already kept, unchanged" % args.id)
            return 0
        raise SystemExit("source %s exists with other text — what was said does not change; keep the correction as a new source" % args.id)
    if args.from_transcript:
        x["verbatim-from"] = "host transcript"
        if args.excerpt:
            x["excerpt"] = "whole sentences of the turn, the rest left out"   # the locator names the whole turn
    save(os.path.join(folder, args.id + ".json"), x)
    if args.file and args.file != "-":
        print("(the input %s is not the record — %s is; remove it or keep it, it is not read again)" % (args.file, os.path.join(DECL, "sources", args.id + ".json")))
    print("source %s kept (%d chars, %s) — relate a concept to it as `source:%s realizes concept:NAME`, the quote as evidence"
          % (args.id, len(text), args.speaker, args.id))
    return 0


def esc(t):
    """Text as one line, safe in a Markdown table cell or list."""
    return " ".join(str(t).split()).replace("|", "\\|")


def node(a):
    """A Mermaid node id for an anchor."""
    return "n" + hashlib.sha1(a.encode("utf-8")).hexdigest()[:8]


def label(a):
    return a.replace("#", "#35;").replace('"', "#quot;")   # Mermaid reads `#...;` as an entity: a heading anchor's `#` must be one


def signed(sig):
    """A judgment's author line, for a reader: by whom, on which approval — or delegated, and why."""
    sig = sig or {}
    if sig.get("by"):
        where = sig.get("approved-in")
        return "by %s" % sig["by"] + ((" (approved in `%s`%s)" % (where, ", answering the agent's `%s`" % sig["approval-of"] if sig.get("approval-of") else "")) if where else "")
    if sig.get("judge"):
        return "judged by %s, applied by %s" % (esc(sig["judge"]), esc(sig.get("applied-by") or "?")) + (" (read in `%s`)" % sig["approved-in"] if sig.get("approved-in") else "")
    if sig.get("agent"):
        return "by the agent %s, on its own" % esc(sig["agent"])
    dl = sig.get("delegated")
    why = ("ref " + dl["ref"]) if isinstance(dl, dict) else esc(dl)
    return "delegated: %s" % (why if len(why) <= 80 else why[:77] + "…")   # the whole reason is in the record; a page of twenty relations need not repeat it twenty times


def render_graph(d, moved):
    """The Mermaid graph: concepts, the projections that realize them, the questions and what answers them."""
    out = []
    domain = [q for q in cq_active(d) if q.get("verify", {}).get("kind") not in INVARIANT_KINDS]
    if not (d["relations"] or d["concepts"] or domain):
        return out
    out += ["```mermaid", "flowchart LR"]
    # sources are listed below, not drawn: a conversation of a dozen turns, each grounding several concepts, is more
    # edges than the rest of the net and says nothing a reader can act on in a picture
    drawn = [r for r in d["relations"] if not (r["src"].startswith("source:") or r["dst"].startswith("source:"))]
    ends = {a for r in drawn for a in (r["src"], r["dst"])} | {"concept:" + c["name"] for c in d["concepts"]}
    for a in sorted(ends):
        shape = '(["%s"])' if a.startswith("concept:") else '["%s"]'
        out.append("  %s%s" % (node(a), shape % label(a)))
    for r in drawn:
        state = moved.get(r["id"])
        out.append('  %s %s|"%s"| %s' % (node(r["src"]), "-.->" if state else "-->", r["predicate"] + (" (%s)" % state if state else ""), node(r["dst"])))
    for q in domain:   # the questions are part of the model: what it must answer, and who answers it (or that nobody does yet)
        qn = node("cq:" + q.get("id", "?"))
        kind = q.get("verify", {}).get("kind")
        out.append('  %s{{"%s"}}' % (qn, label("%s%s: %s" % ("OPEN " if kind == "open" else "", q.get("id", "?"), " ".join(q.get("text", "").split())[:80]))))
        for n in q.get("verify", {}).get("concepts", []):
            out.append('  %s ==>|"answered by"| %s' % (qn, node("concept:" + n)))
        for n in q.get("verify", {}).get("about") or []:
            out.append('  %s -.-|"asks about"| %s' % (qn, node("concept:" + n)))
    out += ["```", "", "Rounded nodes are concepts, hexagons are questions (OPEN: nothing answers it yet — `asks about` names what it is about); a dotted edge is a relation "
            "whose end moved since it was confirmed. Sources are not drawn; each concept lists the words that ground it below.", ""]
    return out


def render_concepts(d, moved):
    """Each concept: its meaning, who declared it, and every relation on it with its state, signature and quote."""
    out = ["## Concepts", ""]
    for c in sorted(d["concepts"], key=lambda c: c["name"]):
        out += ["### %s" % c["name"], "", "> %s" % esc(c["means"]), "",
                "declared %s%s" % (signed(c.get("declared")), "; revised %d time(s)" % len([h for h in c["history"] if "means" in h]) if any("means" in h for h in c.get("history") or []) else ""), ""]
        if c.get("drift"):
            out += ["**drifted** — the sentence above is known not to hold; revision owed: %s (marked %s)" % (esc(c["drift"].get("why", "")), signed(c["drift"])), ""]
        for r in (r for r in d["relations"] if "concept:" + c["name"] in (r["src"], r["dst"])):
            other = r["src"] if r["dst"] == "concept:" + c["name"] else r["dst"]
            out.append("- `%s` %s — %s · %s%s · “%s”" % (other, r["predicate"], moved.get(r["id"], "fresh"), signed(r.get("confirmed")),
                                                       " · re-confirmed %d time(s)" % len(r["history"]) if r.get("history") else "", esc(r["evidence"])))
        if not any("concept:" + c["name"] in (r["src"], r["dst"]) for r in d["relations"]):
            out.append("- nothing realizes it yet")
        out.append("")
    return out


def render_questions(d, files, moved):
    """Each question with its state — OPEN, invariant, UNANSWERABLE, answered or FAILED — and who asked it."""
    out = ["## Questions", ""]
    named = {c["name"] for c in d["concepts"]}
    for q in cq_active(d):
        v = q.get("verify", {})
        if v.get("kind") == "open":
            state = "OPEN"
        elif v.get("kind") in INVARIANT_KINDS:
            state = "invariant (`check`)"
        elif cq_presuppositions(d, files, q):
            state = "UNANSWERABLE"
        else:
            problems, reached = answer_health(d, v.get("concepts", []), moved)
            state = "DRIFTED" if drifts_reached(d, v.get("concepts", []), reached) else "answered" if not problems else "FAILED"
        out.append("- **%s** %s — %s%s · %s" % (q.get("id", "?"), esc(q.get("text", "")), state,
                                                "; answered by " + ", ".join(n for n in v.get("concepts", []) if n in named) if v.get("concepts") else "", signed(q.get("declared"))))
    return out


def render_sources(d):
    """What people said, in full, where it grounds something; a yes that only approves declarations is one line under
    Approvals — a reader saw "sounds good, go" set beside the words that carry the model and asked what it was doing there."""
    cited = {a for r in d["relations"] for a in (r["src"], r["dst"]) if a.startswith("source:")}
    approves = {}
    for c in d["concepts"]:
        approves.setdefault((c.get("declared") or {}).get("approved-in"), []).append("concept:" + c["name"])
    for q in d["cq_declared"]:
        approves.setdefault((q.get("declared") or {}).get("approved-in"), []).append("cq:" + q["id"])
    # an approval is an answer (`replies-to`) that grounds nothing and is cited only by declarations; a person's standalone
    # words that ground nothing yet stay under Sources, in full — they may be the ground of the next concept
    approvals = [x for x in d["sources"] if x.get("replies-to") and "source:" + x["id"] not in cited and "source:" + x["id"] in approves]
    out = ["", "## Sources", ""]
    for x in d["sources"]:
        if x in approvals:
            continue
        out += ["### %s — %s%s%s%s" % (x["id"], x["speaker"], " (%s)" % x["locator"] if x.get("locator") else "",
                                        ", replying to %s" % x["replies-to"] if x.get("replies-to") else "",
                                        "" if "source:" + x["id"] in cited else " — grounds nothing yet"), ""]
        out += ["> " + line if line.strip() else ">" for line in x["text"].rstrip().split("\n")] + [""]
    if approvals:
        out += ["## Approvals", "", "Said to approve, not to describe: each grounds no relation and is cited only by declarations signed on it.", ""]
        for x in approvals:
            answered = next((y for y in d["sources"] if y["id"] == x.get("replies-to")), None)
            out.append("- **%s** — %s%s: “%s” — approves %s" % (x["id"], x["speaker"], ", replying to %s (%s)" % (answered["id"], answered["speaker"]) if answered else "",
                                                             esc(x["text"])[:120], ", ".join("`%s`" % a for a in approves["source:" + x["id"]])))
        out.append("")
    return out


def report_text(target):
    """The page as Markdown, and its title. Read-only: the impact is computed without persisting an observation."""
    d = decl(target)
    stale, broken, _, files = compute_impact(target, d, persist=False)
    moved = {x["id"]: "stale" for x in stale}
    moved.update({x["id"]: "broken" for x in broken})
    title = "%s — the net" % os.path.basename(os.path.abspath(target))
    out = ["# " + title, "",
           "Rendered from `mangsang/` by %s; the record is the source, this page is not. %d concept(s), %d relation(s), %d question(s), %d source(s)."
           % (engine(), len(d["concepts"]), len(d["relations"]), len(cq_active(d)), len(d["sources"])), ""]
    # the graph first, then each concept with its ground, the questions, and last what people said — in full where it grounds
    # something, approvals apart
    out += render_graph(d, moved) + render_concepts(d, moved) + render_questions(d, files, moved) + render_sources(d)
    return "\n".join(out).rstrip() + "\n", title, d


def cmd_report(args):
    """The net for a person to read, on one page: each concept with its meaning and what realizes it (fresh, stale or
    broken, with the quote it was confirmed on), each question with its state, the sources, and a Mermaid graph.
    Nothing here is new judgment — it is a rendering of the record, regenerable any time and read-only (no baseline,
    event or impact file is written), so it is not committed; the record is."""
    text, title, d = report_text(args.target)
    if getattr(args, "check", None):
        # a committed rendering (a page kept on purpose, where the record itself is not what people open) is either what the
        # record renders now, or behind it — a mechanical answer, so a stale page is caught before anyone reads it as current
        path = args.check if os.path.isabs(args.check) else os.path.join(args.target, args.check)
        have = io.open(path, encoding="utf-8").read() if os.path.exists(path) else None
        # the page names the mangsang that rendered it; a new mangsang rendering the same record is not a newer page,
        # so that one clause is left out of the comparison — a page kept in git went "behind" at every release otherwise
        same = lambda t: re.sub(r"^(Rendered from `mangsang/` by )mangsang \S+;", r"\1mangsang;", t, count=1, flags=re.M)
        if have is not None and same(have) == same(text):
            print("%s is current" % args.check)
            return 0
        print("%s is behind the record — regenerate it (`report --out %s`)" % (args.check, args.check) if have is not None else "%s does not exist" % args.check)
        return 1
    if not (args.out or args.html):
        print(text, end="")
        return 0
    guarded = [os.path.abspath(os.path.join(args.target, x)) for x in (DECL, OBS)]
    registered = {os.path.abspath(os.path.join(args.target, e["path"])) for e in d["registry"]}
    for given, body in ((args.out, lambda: text), (args.html, lambda: report_html(text, title))):
        if not given:
            continue
        dest = os.path.abspath(given if os.path.isabs(given) else os.path.join(args.target, given))
        if any(dest == g or dest.startswith(g + os.sep) for g in guarded) or dest in registered:
            raise SystemExit("%s is part of the record or a registered file — a rendering goes elsewhere" % given)
        with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body())
        print("report -> %s (derived from the record: regenerate rather than edit; if you keep it in git, `report --check %s` says when it is behind)" % (given, given))
    return 0


MERMAID_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "mermaid", "mermaid.min.js")


def report_html(md, title):
    """The report's Markdown as one self-contained HTML page. The graph is drawn in the reader's browser by mermaid,
    vendored in this plugin (vendor/mermaid, pinned) and inlined here — no network, nothing to install, and the file
    still draws when it is moved or sent. The Markdown is mangsang's own, so a converter for exactly its shapes
    (headings, lists, quotes, the mermaid fence, `code`, **bold**) is enough; every text is escaped before markup."""
    import html as H
    inline = lambda t: re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", re.sub(r"`([^`]+)`", r"<code>\1</code>", H.escape(t, quote=False)))
    body, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```mermaid"):
            j = lines.index("```", i + 1)
            body.append('<pre class="mermaid">%s</pre>' % H.escape("\n".join(lines[i + 1:j]), quote=False))   # mermaid reads textContent
            i = j + 1
            continue
        m = re.match(r"^(#{1,3}) (.*)", line)
        if m:
            body.append("<h%d>%s</h%d>" % (len(m.group(1)), inline(m.group(2)), len(m.group(1))))
        elif line.startswith("> ") or line == ">":
            quote = []
            while i < len(lines) and (lines[i].startswith("> ") or lines[i] == ">"):
                quote.append(inline(lines[i][2:]))
                i += 1
            body.append("<blockquote>%s</blockquote>" % "<br>".join(quote))
            continue
        elif line.startswith("- "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("  - ")):
                items.append(("<li class=sub>" if lines[i].startswith("  ") else "<li>") + inline(lines[i].strip()[2:]) + "</li>")
                i += 1
            body.append("<ul>%s</ul>" % "".join(items))
            continue
        elif line.strip():
            body.append("<p>%s</p>" % inline(line))
        i += 1
    with io.open(MERMAID_JS, encoding="utf-8") as fh:
        js = fh.read().replace("</script", "<\\/script")
    return ("<!doctype html>\n<html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>%s</title><style>body{font:15px/1.55 -apple-system,system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 16px;color:#1d1d1f}"
            "blockquote{margin:.4em 0 .8em;padding:.2em .9em;border-left:3px solid #c7c7cc;color:#3a3a3c}code{background:#f2f2f7;padding:0 .25em;border-radius:3px}"
            "pre.mermaid{overflow:auto;background:#fafafa;border:1px solid #e5e5ea;border-radius:6px;padding:1em}li.sub{margin-left:1.5em;list-style:circle}"
            "@media (prefers-color-scheme:dark){body{background:#1c1c1e;color:#e5e5ea}blockquote{color:#c7c7cc;border-color:#48484a}code{background:#2c2c2e}"
            "pre.mermaid{background:#fff}}</style></head><body>\n%s\n<script>%s</script>\n"
            "<script>mermaid.initialize({startOnLoad:true,securityLevel:'strict',maxTextSize:500000,flowchart:{htmlLabels:false}});</script>\n</body></html>\n"
            % (H.escape(title), "\n".join(body), js))


def cmd_concept(args):
    """The net's own nodes. `concept add NAME --means "..."` declares what a name means — one sentence, the concept's
    identity. Documents, code and tests then *realize* it (predicate `realizes`, src = the projection, dst = concept:NAME).
    The name survives renames of any projection: a section retitle kills an anchor, never a concept.
    `concept rename OLD NEW` moves the name under every relation; `concept list` shows each concept with its projections.
    Changing `means` is changing what the project means by the word — every projection goes stale, on purpose:
    that is the net replacing the document as the place where meaning lives."""
    d = decl(args.target)
    byname = {c["name"]: c for c in d["concepts"]}
    if args.mode == "add":
        if not re.fullmatch(r"[\w-]+", args.name or ""):
            raise SystemExit("a concept name is a word: letters, digits, _ or -")
        if not (args.means or "").strip():
            raise SystemExit("say what %r means (--means \"one sentence\") — a name without a meaning is a label, not a concept" % args.name)
        if not (args.by or args.delegated):
            raise SystemExit("say who declared it (--by) or why the human delegated it (--delegated)")
        if args.name in byname:
            raise SystemExit("concept %s exists — `concept revise` changes what it means (and stales its projections)" % args.name)
        d["concepts"].append({"name": args.name, "means": args.means.strip(),
                              "declared": signature(args.by, args.delegated)})
        save_decl(args.target, d)
        print("concept %s: %s — projections relate to it as `<anchor> realizes concept:%s`" % (args.name, args.means.strip(), args.name))
        return 0
    if args.mode == "revise":
        c = byname.get(args.name)
        if not c:
            raise SystemExit("no concept %s" % args.name)
        if not (args.means or "").strip():
            raise SystemExit("--means \"the new sentence\"")
        if not (args.by or args.delegated):
            raise SystemExit("say who revised it (--by) or why the human delegated it (--delegated)")
        c.setdefault("history", []).append({"means": c["means"], "declared": c["declared"], **({"owed": c["owes"]} if c.get("owes") else {}),
                                            **({"drift": c["drift"]} if c.get("drift") else {})})   # what the word meant before, and on whose word
        c.pop("owes", None)   # a new sentence answers what was owed: every projection goes stale and is re-read against it
        c.pop("drift", None)   # and what was marked wrong: the new sentence is the revision it waited for
        c["means"] = args.means.strip()
        c["declared"] = signature(args.by, args.delegated)
        save_decl(args.target, d)
        n = sum(1 for r in d["relations"] if "concept:" + args.name in (r["src"], r["dst"]))
        print("concept %s now means: %s — %d projection relation(s) will go stale; that is the point" % (args.name, c["means"], n))
        return 0
    if args.mode == "reaffirm":
        c = byname.get(args.name)
        if not c:
            raise SystemExit("no concept %s" % args.name)
        if not (args.by or args.delegated):
            raise SystemExit("say who re-read it (--by) or why the human delegated it (--delegated)")
        if not c.get("owes") and not c.get("drift"):
            raise SystemExit("concept %s owes nothing — reaffirm answers a retired projection or a drift mark; it has neither" % args.name)
        # the sentence stands, read against what realizes it now: recorded as a judgment beside the declaration, with what it answered
        c.setdefault("history", []).append({"reaffirmed": signature(args.by, args.delegated), **({"owed": c.pop("owes")} if c.get("owes") else {}),
                                            **({"drift": c.pop("drift")} if c.get("drift") else {})})
        save_decl(args.target, d)
        now = [r["src"] for r in d["relations"] if r["predicate"] == "realizes" and r["dst"] == "concept:" + args.name]
        print("concept %s reaffirmed: \"%s\" — read against what realizes it now: %s" % (args.name, c["means"], ", ".join(now) or "nothing"))
        return 0
    if args.mode == "drift":
        # the sentence no longer says what the project does and its revision waits (a stage later, a person's word): said, so
        # nothing reads it as true meanwhile. Seen without it (guin-site 748a4d8): the stale relations were re-confirmed with a
        # note "revised at stage 5", and `cq` answered two questions green with a sentence false in production
        c = byname.get(args.name)
        if not c:
            raise SystemExit("no concept %s" % args.name)
        if not (args.why or "").strip():
            raise SystemExit("say what no longer holds (--why \"...\") — the mark is read where the sentence is")
        if not (args.by or args.delegated or running_agent()):
            raise SystemExit("say who marked it (--by) or why the human delegated it (--delegated)")
        sig = signature(args.by, args.delegated) if (args.by or args.delegated) else {"agent": running_agent()}
        if c.get("drift"):
            c.setdefault("history", []).append({"drift": c["drift"]})
        c["drift"] = {"why": " ".join(args.why.split()), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **sig}
        save_decl(args.target, d)
        asked = [q["id"] for q in cq_active(d) if args.name in ((q.get("verify") or {}).get("concepts") or [])]
        print("concept %s marked drifted: \"%s\" — %s. Until `concept revise %s --means \"...\"` (or `concept reaffirm %s`): cq says DRIFTED for %s; "
              "its relations are not re-confirmed" % (args.name, first_sentence(c["means"]), c["drift"]["why"], args.name, args.name, ", ".join(asked) or "no question"))
        return 0
    if args.mode == "rename":
        c = byname.get(args.name)
        if not c:
            raise SystemExit("no concept %s" % args.name)
        if not re.fullmatch(r"[\w-]+", args.new or ""):
            raise SystemExit("rename to a word: letters, digits, _ or -")
        if args.new in byname:
            raise SystemExit("concept %s exists" % args.new)
        old_a, new_a = "concept:" + args.name, "concept:" + args.new
        root = os.path.join(args.target, DECL, "relations")
        moved = 0
        for r in d["relations"]:
            if old_a in (r["src"], r["dst"]):
                os.remove(os.path.join(root, r["id"] + ".json"))
                r["src"], r["dst"] = (new_a if r["src"] == old_a else r["src"]), (new_a if r["dst"] == old_a else r["dst"])
                if old_a in r.get("seen", {}):
                    r["seen"][new_a] = r["seen"].pop(old_a)
                r["id"] = rel_id(r)
                save(os.path.join(root, r["id"] + ".json"), r)
                moved += 1
        c["name"] = args.new
        os.remove(os.path.join(args.target, DECL, "concepts", args.name + ".json"))
        # the questions that name it as their answer move with it too (retired ones included: a retired question can be
        # re-added); left behind, every one of them would read UNANSWERABLE after a rename that changed no meaning
        asked = 0
        for q in d["cq"] + d["cq_declared"]:
            names = (q.get("verify") or {}).get("concepts") or []
            if args.name in names:
                q["verify"]["concepts"] = [args.new if n == args.name else n for n in names]
                asked += 1
                if q in d["cq_declared"]:
                    save(os.path.join(args.target, DECL, "cq", q["id"] + ".json"), q)
        save_decl(args.target, d)
        print("concept %s -> %s: %d relation(s) and %d question(s) moved with it — the name is the identity, so the rename is one command, not a retirement"
              % (args.name, args.new, moved, asked))
        return 0
    if args.mode == "show":
        return concept_show(args, d)
    # list
    if getattr(args, "brief", False):
        return concept_map(args, d)
    if not d["concepts"]:
        print("no concepts — `concept add NAME --means \"...\" --by WHO` declares the net's first node")
        return 0
    for c in sorted(d["concepts"], key=lambda x: x["name"]):
        pro = [r for r in d["relations"] if "concept:" + c["name"] in (r["src"], r["dst"])]
        print("  %s — %s" % (c["name"], c["means"]))
        for r in pro:
            other = r["src"] if r["dst"] == "concept:" + c["name"] else r["dst"]
            print("      %s %s (%s)" % (r["predicate"], other, r["id"]))
        if not pro:
            print("      (no projections — nothing yet realizes this concept)")
        if c.get("owes"):
            print("      owes a re-read: lost %s since its sentence was affirmed (`concept revise` or `concept reaffirm`)" % ", ".join(c["owes"]))
        if c.get("drift"):
            print("      DRIFTED: %s — the sentence is known not to hold; `concept revise %s` owed" % (drift_line(c["drift"]), c["name"]))
    return 0


def concept_show(args, d):
    """`concept show NAME`: one concept whole — its meaning, who declared it and what it owes, every relation on it (in and out,
    with its state now, its quote and its signer: `lookup concept:NAME`'s lines), the questions it answers or that ask about
    it, and the sources that ground it. An agent typed `concept show site-build` (guin-site, 10-12) and got "invalid choice"."""
    c = next((c for c in d["concepts"] if c["name"] == args.name), None) if args.name else None
    if c is None:
        names = sorted(x["name"] for x in d["concepts"])
        near = [n for n in names if args.name and (args.name in n or n in args.name)]
        raise SystemExit("concept show NAME: %s — %s" % ("no concept %s" % args.name if args.name else "which one?",
                         "did you mean %s?" % ", ".join(near) if near else "`concept list` names them"))
    a = "concept:" + c["name"]
    code = cmd_lookup(argparse.Namespace(target=args.target, path=a, brief=False))
    print("declared %s%s" % (who_signed(c.get("declared")), "; revised %d time(s)" % sum(1 for h in c.get("history", []) if "means" in h)
                             if any("means" in h for h in c.get("history", [])) else ""))
    owed = owed_rereads(d, [a])
    for oc, lost in owed:
        print("  OWES: " + owed_text(oc, lost))
    asked = [q for q in cq_active(d) if c["name"] in ((q.get("verify") or {}).get("concepts") or [])
             or c["name"] in ((q.get("verify") or {}).get("about") or [])]
    if asked:
        stale, broken, _, _ = compute_impact(args.target, d, persist=False)
        moved = {x["id"]: "stale" for x in stale}
        moved.update({x["id"]: "broken" for x in broken})
    print("questions (%d):" % len(asked) if asked else "questions: none names it — `cq add ID --text \"...\" --verify '{\"kind\": \"answered-by\", \"concepts\": [\"%s\"]}'`" % c["name"])
    for q in asked:
        v = q.get("verify") or {}
        if v.get("kind") == "open":
            print("  OPEN      %s  %s — asked about it, not yet answered" % (q["id"], q["text"]))
            continue
        names = v.get("concepts") or []
        problems, reached = answer_health(d, names, moved)
        drifts = drifts_reached(d, names, reached)
        print("  %-9s %s  %s%s" % ("answered" if not problems and not drifts else "DRIFTED" if drifts else "FAILED", q["id"], q["text"],
                                   "" if names == [c["name"]] else " (answered by %s)" % ", ".join(names)))
        for m in problems:
            print("      " + m)
    grounds = sorted({r["src" if r["src"].startswith("source:") else "dst"][len("source:"):] for r in d["relations"]
                      if a in (r["src"], r["dst"]) and "source:" in (r["src"][:7], r["dst"][:7])})
    if grounds:
        print("sources (%d):" % len(grounds))
    for i in grounds:
        x = next((y for y in d["sources"] if y["id"] == i), None)
        if x is None:
            print("  source:%s — not kept" % i)
            continue
        print("  source:%s — %s%s: \"%s\"" % (i, x.get("speaker", "?"), " (%s)" % x["locator"] if x.get("locator") else "", first_sentence(x.get("text", ""))))
    return code


def signing(p):
    """The judgment's author: `--by NAME` (with `--approved-in` when an agent runs it) or `--delegated WHY`."""
    p.add_argument("--by", default=None)
    p.add_argument("--approved-in", default=None, help="with --by, when an agent runs this: source:ID where that person approved")
    p.add_argument("--delegated", default=None)


def sign_as_agent(args):
    """A person's name on a judgment, put there by an agent, needs the place that person said yes."""
    check_person(args.target, args.by)   # a signature is a person's: with a roster, only a listed name signs
    if not any(os.environ.get(k) for k in AGENT_ENV):
        return
    # an agent is running this: a person's name on a judgment needs the place that person said yes — a source they
    # spoke — or it is the agent's judgment wearing their name (seen: a relation signed as the owner by mistake)
    ref = (getattr(args, "approved_in", None) or "").replace("source:", "")
    src = next((x for x in decl(args.target)["sources"] if x["id"] == ref), None) if ref else None
    if not src:
        raise SystemExit("an agent signs --by %s only with --approved-in source:ID — the source where %s approved this; "
                         "otherwise sign --delegated \"<why>\"" % (args.by, args.by))
    if src.get("speaker") != args.by:
        raise SystemExit("--approved-in source:%s was said by %s, not %s" % (ref, src.get("speaker"), args.by))
    global APPROVED_IN, APPROVAL_OF
    APPROVED_IN = "source:" + ref
    # a yes that answers the agent's own words is an approval of a proposal: recorded as such (seen on a playground:
    # ten declarations in the owner's name stood on "sounds good, go" said to the agent's list)
    asked = next((x for x in decl(args.target)["sources"] if x["id"] == src.get("replies-to")), None) if src.get("replies-to") else None
    roster = people(args.target) or {}
    APPROVAL_OF = "source:" + asked["id"] if asked and any(str(asked.get("speaker", "")).startswith(a) for a in roster.get("agents", [])) else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mangsang", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("register", "confirm", "observe", "impact", "cq", "check", "retire", "reconfirm", "judge", "lookup", "move", "concept", "source", "report"):
        p = sub.add_parser(name)
        p.add_argument("--target", default=".")
        if name == "register":
            p.add_argument("paths", nargs="+")
        if name == "confirm":
            p.add_argument("proposals")
            signing(p)
        if name == "cq":
            p.add_argument("mode", nargs="?", default="run", choices=["run", "add", "revise", "retire"])
            p.add_argument("id", nargs="?", default=None)
            p.add_argument("--text", default=None, help="the question, for people")
            p.add_argument("--verify", default=None, help="JSON: domain questions are {\"kind\": \"answered-by\", \"concepts\": [...]} — the named concepts carry the answer; {\"kind\": \"open\"} is asked before anything answers it; structural kinds (coverage|projection|resolved) are declared here too but answer to `check`")
            p.add_argument("--why", default=None, help="retire: what made this question no longer worth asking")
            signing(p)
            p.add_argument("--findings", action="store_true", help="print failed/unanswerable/unquestioned as dwitbuk/findings@1 JSON")
        if name == "check":
            p.add_argument("--findings", action="store_true", help="print failed/unaskable/unwatched as dwitbuk/findings@1 JSON")
        if name == "impact":
            p.add_argument("--findings", action="store_true", help="print stale/broken as dwitbuk/findings@1 JSON")
            p.add_argument("--only", nargs="*", default=None, help="judge only relations touching these anchor prefixes (a slice's check)")
            p.add_argument("--show", action="store_true", help="for each stale relation, print what changed: the anchor's text when it was confirmed (from git) against now")
        if name == "judge":
            p.add_argument("mode", choices=["request", "consume"])
            p.add_argument("--out", default="mangsang-judge", help="request: a directory (created, or an existing one used as is) — the packet is written into it as judge-request.json, its path printed; not a file name")
            p.add_argument("--ids", nargs="*", default=None)
            p.add_argument("--limit", type=int, default=6000)
            p.add_argument("--response", default=None, help="consume: the judgment judge_worker.py wrote, beside its judge-request.json")
            p.add_argument("--by", default=None, help="consume: who applies the verdicts (default: the agent running this). A person's name, when an agent runs it, only with --approved-in")
            p.add_argument("--approved-in", default=None, help="consume, with --by a person: source:ID where that person read the verdicts")
            p.add_argument("--judge", default=None, help="consume: who judged, as \"<host> <model>\" — only when the response carries no worker record (a host subagent answered --prompt-only)")
        if name == "observe":
            p.add_argument("--reset", action="store_true")
            p.add_argument("--at", default=None, help="with --reset: take the baseline from git at this revision (e.g. the merge base)")
        if name == "retire":
            p.add_argument("id", nargs="?", default=None)
            p.add_argument("--why", required=True)
            p.add_argument("--gone", "--deleted", nargs="+", default=None, metavar="FILE",
                           help="files (or a directory) deleted on purpose: retire every relation with an anchor in them, with the one --why, "
                                "and unregister them; refused for a path still in the tree")
        if name == "reconfirm":
            p.add_argument("ids", nargs="+")
            signing(p)
            p.description = ("a re-read stale relation still holds. Sign --by NAME (with --approved-in source:ID when an agent runs it) or "
                             "--delegated WHY; an agent that re-read it itself passes neither and is recorded as itself ({\"agent\": ...})")
            p.add_argument("--evidence", default=None, help="the sentence that holds now, when the old quote is gone from the text (one id at a time)")
        if name == "lookup":
            p.add_argument("path", help="a file (as registered): print the confirmed relations standing on it — the concept's meaning, the quote, who confirmed, fresh or stale — before you touch it. "
                                        "Also an anchor (`concept:NAME`, `file:symbol`): what stands on it; or a relation id (R-xxxxxxxx): that relation")
            p.add_argument("--brief", action="store_true", help="one line per concept the file's relations reach (its meaning's first sentence; how many are stale, when any) — for a reader's first look; silent when there is nothing to say")
        if name == "move":
            p.add_argument("ids", nargs="*", default=None, help="broken relations to move (default: every broken one)")
            signing(p)
            p.add_argument("--dry-run", action="store_true", help="report what would move and what is ambiguous; change nothing")
        if name == "source":
            p.add_argument("mode", nargs="?", default="list", choices=["add", "list"])
            p.add_argument("id", nargs="?", default=None)
            p.add_argument("--file", default=None, help="the words, verbatim (UTF-8); `-` reads them from stdin, leaving no input file behind")
            p.add_argument("--replies-to", default=None, help="the source this turn answers — an answer is kept with its question")
            p.add_argument("--speaker", default=None, help="who said or wrote them")
            p.add_argument("--locator", default=None, help="where they were said: a meeting, a transcript, a URL")
            p.add_argument("--from-transcript", default=None, help="a host session transcript (Claude Code JSONL): take the turn from it, verbatim, instead of --file")
            p.add_argument("--match", default=None, help="with --from-transcript: a phrase only the wanted turn contains")
            p.add_argument("--turn", default=None, help="with --from-transcript: the host's id for the turn (listed when --match finds several); ID#k for one answer of a question form that asked several")
            p.add_argument("--kind", default=None, choices=["person", "agent", "question", "answer"], help="with --from-transcript: only turns of this kind — `answer` is a choice picked in a question (only what was picked or typed, one turn per question: ID#k) or a reply the person typed right after the agent's turn (that one is `person` too)")
            p.add_argument("--excerpt", action="append", default=None, help="with --from-transcript: keep only these sentences of the turn (repeatable), verbatim and whole — when the turn clearly splits into what the record needs and what it does not")
        if name == "report":
            p.add_argument("--out", default=None, help="write the Markdown page here (never into mangsang/, .mangsang/ or a registered file); default stdout")
            p.add_argument("--html", default=None, help="write one self-contained HTML page here: the graph draws in any browser, offline")
            p.add_argument("--check", default=None, help="a page written earlier with --out: exit 0 when it is what the record renders now, 1 when it is behind (for a page kept in git)")
        if name == "concept":
            p.add_argument("mode", nargs="?", default="list", choices=["add", "revise", "reaffirm", "drift", "rename", "list", "show"])
            p.add_argument("name", nargs="?", default=None)
            p.add_argument("new", nargs="?", default=None, help="rename: the new name")
            p.add_argument("--means", default=None, help="one sentence: what this name means in this project")
            p.add_argument("--brief", action="store_true", help="list: the net as a map in a line or two — concepts by name, open questions, stale relations")
            p.add_argument("--why", default=None, help="drift: what no longer holds — the sentence is known wrong and its revision waits")
            signing(p)
    args = ap.parse_args(argv)
    global APPROVED_IN, APPROVAL_OF
    APPROVED_IN = APPROVAL_OF = None   # one command's approval is not the next one's (main runs many times in one process: the self-check)
    if getattr(args, "by", None) and args.cmd != "judge":
        sign_as_agent(args)
    return {"register": cmd_register, "confirm": cmd_confirm, "observe": cmd_observe, "impact": cmd_impact,
            "cq": cmd_cq, "check": cmd_check, "retire": cmd_retire, "reconfirm": cmd_reconfirm, "judge": cmd_judge,
            "lookup": cmd_lookup, "move": cmd_move, "concept": cmd_concept, "source": cmd_source, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
