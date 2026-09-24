"""mangsang — the net-shaped model (網狀): named concepts, their projections into documents, code and tests, and what went stale.

The net is primary; prose documents are one projection of it, not the source of truth. A concept is declared once
(`concept add NAME --means "..."`), lives at the anchor `concept:NAME`, and survives any rename of the files and
sections that realize it. Relations tie projections to concepts (`realizes`) and artifacts to each other
(`documents`, `verifies`); staleness is judged against what a confirmer saw, per anchor fingerprint.

  register <path>...            watch these files (anchors: `file`, `file#heading` for Markdown, `file:symbol` for Python)
  source add ID --file F|- --speaker WHO [--locator L] [--replies-to ID]
                                keep what was said or written, verbatim and unchangeable, as the anchor `source:ID` — a concept
                                grounded in a conversation relates to it like to any projection, with a quote as evidence. Both
                                sides of a conversation are sources: "yes, both" means nothing without the question it answers
  concept [add|revise|rename|list] declare/change the net's own nodes; `concept:NAME` anchors relations; revising `means` stales every projection
  confirm <proposals.json> --by NAME | --delegated WHY
                                store relations after checking: anchors exist, predicate is in the vocabulary, no duplicates
  observe [--reset [--at REV]]  fingerprint every anchor; --reset takes a new baseline (from git at REV if given), otherwise diff against it -> events
  impact [--findings] [--only ANCHOR-PREFIX...]
                                observe, then events x relations -> stale / broken. exit 1 when anything is unresolved (usable as a check);
                                --only judges only relations touching those anchors (a slice's check); --findings prints `dwitbuk/findings@1`
  judge request --out DIR [--ids ID...]   the stale relations as a packet: the possibly-stale text, the changed text, the quote confirmed
  judge consume --response FILE --by WHO  the judge's verdicts: still-true -> re-confirmed by delegation (recorded as such), drifted (with a
                                quote from the text) and cannot-tell -> printed for a human; judge_worker.py runs one packet
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
  lookup <path>                 before touching a file: the confirmed relations standing on it (read-only) — size the edit as code + relations
  move [ID...] --by NAME | --delegated WHY [--dry-run]   after a refactoring: a broken relation whose dead `file:symbol` / `file#heading` has exactly one
                                new home is retired (why: moved) and re-confirmed there with the same evidence; ambiguous or homeless ones are left for a person
  reconfirm <id>... --by NAME | --delegated WHY [--evidence "..."]
                                a human re-read a stale relation and it still holds: `seen` becomes what the tree has now; the evidence must still be in the text

Two places. `mangsang/` is the project's knowledge (registry, vocabulary, cq, one file per relation) — committed, changed only when a human
confirms. `.mangsang/` is this machine's observation (baseline, events, impact) — not committed.
mangsang never proposes a relation and never judges meaning; it checks, stores, fingerprints and diffs.
`source add` keeps what people said as anchors (`mangsang/sources/<id>.json`); a model can be grounded in a conversation as
well as in a plan, and the same quote rule holds.
"""
import argparse
import ast
import hashlib
import io
import json
import os
import re
import sys

DECL = "mangsang"
OBS = ".mangsang"
DELEGATION_REF = re.compile(r"^D-[0-9a-f]+$")


APPROVED_IN = None   # set by main when an agent signs in a person's name: the source where that person approved
APPROVAL_OF = None   # and, when that approval answers an agent's own words (a proposal), the source it answers
AGENT_ENV = ("CLAUDECODE", "CODEX_THREAD_ID", "AGENT_WORKER")
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
        data = {**{k: v for k, v in data.items() if k != "written_by"}, "written_by": engine()}
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
    """Fingerprint of an anchor's content. For Python anchors the token stream is hashed instead of the raw text, so a
    comment, blank line or reformatting does not change the fingerprint — only code does. (Every doc-drift tool that ran
    in anger converged on normalized fingerprints; raw hashes cried stale at formatters.) Token *names* (tok_name), not
    numbers: 3.12 renumbered the token table (OP 54->55) and every numeric fingerprint changed with it — a machine on
    3.12 disagreed with the same tree on 3.11. Names are the stable interface; numbers are an implementation detail.
    Markdown and unknown files hash their text: in prose, wording *is* the content."""
    text = text.replace("\r\n", "\n")
    if path and path.endswith(".py"):
        import tokenize, token as tok
        try:
            toks = ["%s\x00%s" % (tok.tok_name[t.type], t.string) for t in tokenize.generate_tokens(io.StringIO(text).readline)
                    if t.type not in (tokenize.COMMENT, tokenize.NL, tok.NEWLINE, tokenize.ENCODING, tok.ENDMARKER)]
            return hashlib.sha256("\x01".join(toks).encode("utf-8")).hexdigest()[:12]
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass   # a fragment that will not tokenize is fingerprinted as text — never silently unfingerprinted
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


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
    """{anchor: text} for one file (or for `text` as if it were that file). The whole file is always an anchor ("")."""
    if text is None:
        text = io.open(path, encoding="utf-8", newline=None).read() if os.path.exists(path) else None
    if text is None:
        return None
    out = {"": text}
    if path.endswith(".md"):
        heads = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in re.finditer(r"^(#{1,6}) +(.+?)\s*$", text, re.M)]
        for i, (start, level, title) in enumerate(heads):
            # a section runs to the next heading of its level or higher — except the title (level 1), which runs only to
            # the next heading of any level: as a section it would be the whole file, a duplicate of the file anchor "",
            # and every relation on it went stale on every edit anywhere in the file
            end = next((s for s, l, _ in heads[i + 1:] if l <= level or level == 1), len(text))
            out["#" + title] = text[start:end]
    elif path.endswith(".py"):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return out
        lines = text.split("\n")
        for node in tree.body:
            names = [node.name] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else \
                    [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else []
            for name in names:
                out[":" + name] = "\n".join(lines[node.lineno - 1:node.end_lineno])
    return out


def anchors_of(path, text=None):
    """{anchor: fingerprint} for one file."""
    texts = anchor_texts(path, text)
    return None if texts is None else {k: fp(v, path) for k, v in texts.items()}


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
    """'file', 'file#heading', 'file:symbol' -> (file, key)."""
    for sep in ("#", ":"):
        if sep in anchor:
            # Windows drive letters: only treat ':' as a separator after the first two characters
            i = anchor.find(sep, 2 if sep == ":" else 0)
            if i > 0:
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
                why = why or "%s anchor %r does not resolve (%s)" % (end, p.get(end), "file not registered" if f not in files else "no such heading/symbol")
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
    os.remove(args.proposals)   # a proposal is consumed; what survived is in mangsang.json, what did not is printed
    print("confirmed %d / rejected %d (proposals file consumed)" % (len(kept), len(rejected)))
    for r in rejected:
        print("  rejected %s %s %s — %s" % (r.get("src"), r.get("predicate"), r.get("dst"), r["why"]))
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
    base_path, ev_path = os.path.join(args.target, OBS, "baseline.json"), os.path.join(args.target, OBS, "events.json")
    if args.at and not args.reset:
        raise SystemExit("--at goes with --reset: a baseline is taken at a revision, a diff is against the tree")
    if args.reset or not os.path.exists(base_path):
        if args.at:
            files, unreadable = snapshot(args.target, d["registry"], at=args.at)   # the merging machine has no past; git does
        save(base_path, {"files": files, "at": args.at})
        save(ev_path, {"events": {}, "unreadable": unreadable})
        print("baseline%s: %d files, %d anchors%s" % (" at %s" % args.at if args.at else "", len(files), sum(len(a) for a in files.values()),
                                                       " · unreadable %s" % unreadable if unreadable else ""))
        return 0
    events = diff_events(load(base_path)["files"], files)
    for path, ev in events.items():
        print("  %-28s changed=%s added=%s removed=%s" % (path, ev["changed"], ev["added"], ev["removed"]))
    save(ev_path, {"events": events, "unreadable": unreadable})
    print("changed files %d / registered %d" % (len(events), len(d["registry"])))
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


def compute_impact(target, d, only=None, persist=True):
    """(stale, broken, unjudged, files). Stale = an anchor the relation propagates from differs from what its confirmer saw (`seen`);
    relations without `seen` are judged against this machine's baseline, or listed as unjudged when there is none."""
    base_path = os.path.join(target, OBS, "baseline.json")
    files, _ = snapshot(target, d["registry"])
    ev = diff_events(load(base_path)["files"], files) if os.path.exists(base_path) else None
    if ev is not None and persist:
        save(os.path.join(target, OBS, "events.json"), {"events": ev})
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
            # text hash (pre-token era) or a numeric-token hash (pre-tok_name era). If either recomputation over the
            # current bytes equals the stored value, the bytes have not changed since the confirmer read them — only
            # the fingerprint format did. Not stale; the record upgrades itself on the next confirm/reconfirm.
            texts = texts_of(target, f)
            if not (texts and key in texts):
                return True
            old = r["seen"][anchor]
            return not (fp(texts[key]) == old or fp_legacy_numeric(texts[key], f) == old)
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
            stale.append({"id": r["id"], "stale": other if len(changed) == 1 else r["src"], "because": changed[0] if len(changed) == 1 else "%s and %s" % (r["src"], r["dst"])})
    return stale, broken, sorted(set(unjudged)), files


def what_changed(target, r, anchor):
    """The anchor's text as its confirmer saw it and as it reads now, as a unified diff — so a person re-reading a stale
    relation reads the change, not just the fact of one. `seen` keeps fingerprints, not text; git keeps the text: the commit
    that last wrote the relation's file is when it was confirmed, and the anchor is read from the tree at that commit
    (a concept's `means` from its file then). None when there is no such commit (the relation was never committed)."""
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
    elif f == "source":
        return None   # what was said does not change
    else:
        old = git("show", "%s:./%s" % (c, f))
        old_text = (anchor_texts(f, old.stdout.replace("\r\n", "\n")) or {}).get(key) if old.returncode == 0 else None
    new_text = (texts_of(target, f) or {}).get(key)
    if old_text is None or new_text is None:
        return None
    if old_text == new_text:
        # the words are the same and the fingerprint is not: the rule that cuts the anchor changed under it (a title heading's
        # section, a token-fingerprint format) — nothing to re-read; a reconfirm records the new fingerprint
        return "(the text of %s is exactly what it was at %s — only its fingerprint's rule changed; nothing to re-read)" % (anchor, c[:8])
    return "".join(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True), "%s @ %s" % (anchor, c[:8]), "%s @ now" % anchor, n=1))


def cmd_impact(args):
    d = decl(args.target)
    stale, broken, unjudged, files = compute_impact(args.target, d, args.only)
    if not args.findings:   # as a reporter (--findings) impact answers and leaves nothing behind: a review must not write the project's state
        save(os.path.join(args.target, OBS, "impact.json"), {"stale": stale, "broken": broken, "unjudged": unjudged, "only": args.only, "unresolved_total": len(stale) + len(broken)})
    if args.findings:
        findings = [{"kind": "stale", "where": "%s %s" % (x["id"], x["stale"]), "text": "stale because %s changed since it was confirmed" % x["because"]} for x in stale]
        findings += [{"kind": "broken", "where": "%s %s" % (x["id"], ", ".join(x["dead"])), "text": "dead anchor(s): the relation points at nothing"} for x in broken]
        findings += [{"kind": "delegated", "where": "%s %s %s %s" % (r["id"], r["src"], r["predicate"], r["dst"]), "text": "re-confirmed by delegation: %s" % (("ref " + r["confirmed"]["delegated"]["ref"]) if isinstance(r["confirmed"]["delegated"], dict) else r["confirmed"]["delegated"])}
                     for r in d["relations"] if isinstance(r.get("confirmed"), dict) and r["confirmed"].get("delegated")]
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "findings": findings}, ensure_ascii=False, indent=1))
        return 1 if stale or broken else 0
    for x in stale:
        print("  stale   %s  %s  <- %s" % (x["id"], x["stale"], x["because"]))
        if getattr(args, "show", False):
            rel = next((r for r in d["relations"] if r["id"] == x["id"]), None)
            diff = what_changed(args.target, rel, x["because"]) if rel else None
            print("\n".join("      " + l for l in (diff or "(no earlier text in git to compare against — the relation was not committed when it was confirmed, or the anchor is a source, which never changes; the change is known by its fingerprint)").rstrip().split("\n")))
    for b in broken:
        print("  broken  %s  dead anchors %s" % (b["id"], b["dead"]))
    if unjudged:
        print("  unjudged %d relation(s) confirmed before `seen` existed, and this machine has no baseline: %s — `observe --reset --at REV` to judge them from REV"
              % (len(unjudged), ", ".join(unjudged)))
    print("unresolved_total = %d%s" % (len(stale) + len(broken), " (only %s)" % ", ".join(args.only) if args.only else ""))
    return 1 if stale or broken else 0


JUDGE_REQUEST, JUDGMENT = "mangsang/judge-request@1", "mangsang/judgment@1"
VERDICTS = ("still-true", "drifted", "cannot-tell")


def cmd_judge(args):
    """The judge pattern for staleness: mangsang packs the two texts and the quote; a fresh read-only session says whether the sentence
    still holds; mangsang validates (a drifted verdict quotes the text as it is) and applies only what is safe to apply."""
    d = decl(args.target)
    if args.mode == "request":
        stale, broken, unjudged, files = compute_impact(args.target, d)
        rels = {r["id"]: r for r in d["relations"]}
        wanted = set(args.ids or [])
        items = []
        for x in stale:
            r = rels[x["id"]]
            if wanted and r["id"] not in wanted:
                continue
            texts = {a: (texts_of(args.target, split_anchor(a)[0]) or {}).get(split_anchor(a)[1], "") for a in (x["stale"], x["because"])}
            items.append({"relation": r["id"], "predicate": r["predicate"], "means": d["vocabulary"].get(r["predicate"], {}).get("means"),
                          "stale": x["stale"], "stale_text": texts[x["stale"]][:args.limit],
                          "because": x["because"], "because_text": texts[x["because"]][:args.limit],
                          "quote_at_confirm": r.get("evidence")})
        if not items:
            print("nothing stale to judge")
            return 0
        packet = {"artifact-type": JUDGE_REQUEST, "target": os.path.abspath(args.target).replace(os.sep, "/"), "items": items, "verdicts": list(VERDICTS),
                  "instructions": ("For each item, read stale_text (the side that may be stale) against because_text (the side that changed since the relation "
                                   "was confirmed) and decide whether the sentence in stale_text — the one quote_at_confirm quotes — still holds. "
                                   "still-true: it does; say why in evidence. drifted: it does not; put the sentence that no longer holds in `quote`, "
                                   "verbatim from stale_text, and why in evidence from because_text. cannot-tell: say what the texts do not settle. "
                                   "Judge only the relations in the request. Similar names are not evidence. Read files under target if you must. Change no files.")}
        os.makedirs(args.out, exist_ok=True)
        save(os.path.join(args.out, "judge-request.json"), packet)
        print("judge packet: %d stale relation(s) -> %s. Run judge_worker.py on it, then `judge consume --response %s --by WHO`"
              % (len(items), os.path.join(args.out, "judge-request.json"), os.path.join(args.out, "judge-response.json")))
        return 0
    # consume
    resp = load(args.response)
    req = load(os.path.join(os.path.dirname(os.path.abspath(args.response)), "judge-request.json"))
    if resp.get("artifact-type") != JUDGMENT or not isinstance(resp.get("items"), list) or not req:
        raise SystemExit("a judgment is %s with `items`, next to its judge-request.json" % JUDGMENT)
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
        if it["verdict"] == "still-true":
            # the one safe application: what a human would do after reading — recorded as a delegation, never as a person's confirmation
            if all(split_anchor(a)[0] in files and split_anchor(a)[1] in files[split_anchor(a)[0]] for a in (r["src"], r["dst"])) and quoted(args.target, r["evidence"], r["src"], r["dst"]):
                r["seen"] = {a: files[split_anchor(a)[0]][split_anchor(a)[1]] for a in (r["src"], r["dst"])}
                r["confirmed"] = {"delegated": "judge %s: %s" % (args.by, it["evidence"][:200])}
                save(os.path.join(args.target, DECL, "relations", r["id"] + ".json"), r)
                applied.append(r["id"])
            else:
                rejected.append("%s: still-true, but its quote is no longer in the text — a human re-reads (`reconfirm --evidence`)" % r["id"])
    save(os.path.join(args.target, OBS, "judgments.json"), {"artifact-type": JUDGMENT, "by": args.by, "items": kept, "rejected": rejected, "applied": applied})
    for it in kept:
        print("  %-11s %s%s — %s" % (it["verdict"], it["relation"], (" (re-confirmed by delegation)" if it["relation"] in applied else ""), it["evidence"][:100]))
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
    elif v.get("kind") == "open":
        # asked before anything answers it: a model built from conversation starts with what nobody has answered yet.
        # It presupposes nothing — and names no answer, so a later `revise` to answered-by is where the answer is signed
        if set(v) != {"kind"}:
            missing.append("an open question names no answer — `{\"kind\": \"open\"}` alone; `cq revise` to answered-by when one exists")
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


INVARIANT_KINDS = ("coverage", "projection", "resolved")


def eval_invariant(d, files, all_anchors, q):
    """One invariant, evaluated: (ok, detail). These are the net's health checks — the fsck, not the questions."""
    v = q.get("verify", {})
    if v.get("kind") == "coverage":
        pat = re.compile("^" + re.escape(v["anchors"]).replace("\\*", ".*") + "$")
        targets = [a for a in all_anchors if pat.match(a)]
        role = v.get("as", "src")
        covered = {r[role] for r in d["relations"] if r["predicate"] == v.get("predicate", r["predicate"])}
        missing = [a for a in targets if a not in covered]
        ok = bool(targets) and not missing
        return ok, "%d anchors, %d uncovered%s" % (len(targets), len(missing), (": " + ", ".join(missing)) if missing else "")
    if v.get("kind") == "projection":
        media = v.get("media") or {}
        missing = []
        for c in d["concepts"]:
            pro = [r["src"] for r in d["relations"] if r["predicate"] == "realizes" and r["dst"] == "concept:" + c["name"]]
            for medium, prefixes in media.items():
                if not any(a.startswith(tuple(prefixes)) for a in pro):
                    missing.append("%s lacks %s" % (c["name"], medium))
        return not missing, "%d concept(s), %d gap(s)%s" % (len(d["concepts"]), len(missing), ("; ".join([": "] + missing).replace(": ; ", ": ") if missing else ""))
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
        ok, detail = eval_invariant(d, files, all_anchors, q)
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
    if proposed:
        say("  %-12s %d declaration(s) signed in a person's name on their yes to the agent's proposal: %s" % ("proposed", len(proposed), ", ".join(proposed)))
        findings.append({"kind": "agent-proposed", "layer": "observation", "where": ", ".join(proposed), "source": "mangsang",
                         "text": "%d declaration(s) stand on a person's approval of the agent's own proposal (approval-of), not on the person's words" % len(proposed)})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "findings": findings}, ensure_ascii=False, indent=1))
    say("invariants %d · holds %d · failed %d · unaskable %d · unwatched %d"
          % (len(active), len(active) - failed - unaskable, failed, unaskable, len(unwatched)))
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
    shaky = {}   # concept name -> relation ids whose realizes-projection moved or died
    for x in stale:
        rel = next(r for r in d["relations"] if r["id"] == x["id"])
        if rel["predicate"] == "realizes" and rel["dst"].startswith("concept:"):
            shaky.setdefault(rel["dst"][len("concept:"):], []).append(x["id"])
    for b in broken:
        rel = next((r for r in d["relations"] if r["id"] == b["id"]), None)
        if rel and rel["predicate"] == "realizes" and rel["dst"].startswith("concept:"):
            shaky.setdefault(rel["dst"][len("concept:"):], []).append(b["id"])
    byname = {c["name"]: c for c in d["concepts"]}
    failed = unanswerable = 0
    findings = []
    opened = [q for q in active if q.get("verify", {}).get("kind") == "open"]
    for q in opened:
        say("  %-12s %s  %s" % ("OPEN", q["id"], q["text"]))
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
        problems = []
        for n in names:
            pro = [r for r in d["relations"] if r["predicate"] == "realizes" and r["dst"] == "concept:" + n]
            if not pro:
                problems.append("%s is declared but realized nowhere — the answer is a sentence with no reality behind it" % n)
            elif n in shaky:
                problems.append("%s has moved projections (%s) — the sentence stands but what realizes it changed since confirmation" % (n, ", ".join(shaky[n])))
        ok = not problems
        failed += not ok
        if not ok:
            findings.append({"kind": "cq-failed", "where": q["id"], "source": "mangsang", "text": "; ".join(problems)})
        answer = "; ".join("%s: %s" % (n, byname[n]["means"]) for n in names if n in byname)
        say("  %-12s %s  %s" % ("answered" if ok else "FAILED", q["id"], q["text"]))
        say("      %s %s" % ("=" if ok else "?", answer[:240]))
        for p in problems:
            say("      %s" % p)
    # the reverse audit: which concepts does no question name? (G&F: content the questions do not justify)
    named = {n for q in active for n in q.get("verify", {}).get("concepts", [])}
    unquestioned = sorted(c["name"] for c in d["concepts"] if c["name"] not in named)
    for u in unquestioned:
        say("  %-12s concept:%s — the model holds this meaning and no question asks for it; write the CQ or say why not" % ("UNQUESTIONED", u))
        findings.append({"kind": "cq-unquestioned", "where": "concept:" + u, "source": "mangsang",
                         "text": "declared and realized, but named by no competency question"})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "findings": findings}, ensure_ascii=False, indent=1))
    tail = " · %d structural declaration(s) now answer to `check`" % structural if structural else ""
    say("cq %d · answered %d · failed %d · unanswerable %d · unquestioned %d · open %d%s"
          % (len(active) + len(opened), len(active) - failed - unanswerable, failed, unanswerable, len(unquestioned), len(opened), tail))
    return 1 if failed or unanswerable or unquestioned else 0


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


def cmd_retire(args):
    d = decl(args.target)
    r = next((x for x in d["relations"] if x["id"] == args.id), None)
    if not r:
        raise SystemExit("no relation %s" % args.id)
    d["relations"].remove(r)
    d["retired"].append({**r, "retired": {"why": args.why}})
    save_decl(args.target, d)
    print("retired %s (%s %s %s) — kept in `retired`" % (r["id"], r["src"], r["predicate"], r["dst"]))
    return 0


def cmd_reconfirm(args):
    """A stale relation that still holds after someone read it. Only what the tree has now is recorded; a dead anchor is refused (retire it)."""
    if not (args.by or args.delegated):
        raise SystemExit("say who re-read it (--by) or why the human delegated it (--delegated)")
    d = decl(args.target)
    files, _ = snapshot(args.target, d["registry"])
    root = os.path.join(args.target, DECL, "relations")
    for rid in args.ids:
        r = next((x for x in d["relations"] if x["id"] == rid), None)
        if not r:
            raise SystemExit("no relation %s" % rid)
        dead = [a for a in (r["src"], r["dst"]) if split_anchor(a)[0] not in files or split_anchor(a)[1] not in files[split_anchor(a)[0]]]
        if dead:
            raise SystemExit("%s: anchor %s is gone — a relation on a dead anchor cannot be re-confirmed; retire it" % (rid, dead))
        for a in (r["src"], r["dst"]):   # what the person re-read: the change itself, printed with the record of it
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
        r["confirmed"] = signature(args.by, args.delegated)
        save(os.path.join(root, rid + ".json"), r)   # save_decl never rewrites an existing relation; this is the one command that does
        print("re-confirmed %s (%s %s %s)" % (rid, r["src"], r["predicate"], r["dst"]))
    return 0


def cmd_lookup(args):
    """Before touching a file: which confirmed relations stand on it? The reverse index every drift tool grew
    (drift `refs`, docdrift `lookup`) — here so an agent can size its task as 'the edit plus these relations',
    instead of learning about them afterwards from `impact`. Read-only; prints nothing but the record."""
    d = decl(args.target)
    rels = []
    for r in d["relations"]:
        for a in (r["src"], r["dst"]):
            f, key = split_anchor(a)
            if f == args.path or (key == "" and args.path == f):
                prop = d["vocabulary"].get(r["predicate"], {}).get("propagates", "none")
                other = r["dst"] if a == r["src"] else r["src"]
                moves = (a == r["dst"] and prop in ("dst->src", "both")) or (a == r["src"] and prop in ("src->dst", "both"))
                rels.append((r["id"], r["src"], r["predicate"], r["dst"], a, moves))
                break
    if not rels:
        print("no confirmed relations touch %s" % args.path)
        return 0
    for rid, src, pred, dst, a, moves in rels:
        # the relation as it is stored, src predicate dst — never reordered around the looked-up anchor (a reader who copied the
        # line into a proposal got src and dst swapped when the anchor was the dst)
        mark = lambda x: "[%s]" % x if x == a else x
        print("  %s  %s %s %s%s" % (rid, mark(src), pred, mark(dst), "  — changing this anchor makes the relation stale" if moves else ""))
    print("%d relation(s) on %s — an edit here and their update are one piece of work, not two" % (len(rels), args.path))
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
    homes = {}   # key (":symbol" / "#heading") -> [files that have it now]
    for f, keys in files.items():
        for k in keys:
            if k:
                homes.setdefault(k, []).append(f)
    moved, refused = [], []
    for b in broken:
        r = next((x for x in d["relations"] if x["id"] == b["id"]), None)
        if not r or (wanted and r["id"] not in wanted):
            continue
        new = dict(r)
        why = None
        for end in ("src", "dst"):
            if r[end] not in b["dead"]:
                continue
            f, key = split_anchor(r[end])
            if not key or f in ("concept", "source"):
                why = "%s is not a moved symbol or section" % r[end]
                break
            cands = sorted(set(homes.get(key, [])) - {f})
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


def transcript_turns(path):
    """A host session transcript (Claude Code's JSONL) as the turns a person would recognize: what the person typed, what the
    agent answered in text (blocks of one message joined), each multiple-choice question it asked and the answer it got —
    each as the host recorded it, with its id, time and (for the agent) model. Tool traffic other than questions is left out:
    it is how the agent worked, not what was said."""
    turns, agent = [], {}
    for line in io.open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("isSidechain"):
            continue
        msg, when, uid = d.get("message") or {}, d.get("timestamp"), d.get("uuid")
        c = msg.get("content")
        if d.get("type") == "user" and isinstance(c, str) and not d.get("isMeta"):
            turns.append({"kind": "person", "text": c, "uuid": uid, "at": when})
        elif d.get("type") == "user" and isinstance(c, list):
            for x in c:
                if isinstance(x, dict) and x.get("type") == "text" and not d.get("isMeta"):
                    turns.append({"kind": "person", "text": x.get("text", ""), "uuid": uid, "at": when})
                if isinstance(x, dict) and x.get("type") == "tool_result" and x.get("tool_use_id") in agent.get("asks", {}):
                    body = x.get("content")
                    body = "\n".join(b.get("text", "") for b in body if isinstance(b, dict)) if isinstance(body, list) else str(body)
                    turns.append({"kind": "answer", "text": body, "uuid": uid, "at": when})
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
                    agent.setdefault("asks", {})[x.get("id")] = True
                    turns.append({"kind": "question", "text": json.dumps(x.get("input"), ensure_ascii=False, indent=1), "uuid": uid, "at": when,
                                  "model": msg.get("model")})
    host_notes = ("<task-notification>", "<local-command", "<command-name>", "<system-reminder>", "[Request interrupted")
    return [t for t in turns if t["text"].strip() and not (t["kind"] == "person" and t["text"].lstrip().startswith(host_notes))]


def people(target):
    """`mangsang/people.json` — who may sign and speak here: {"people": [names], "agents": [speaker prefixes]}. Absent, any
    name is taken (the old behavior); present, a name that is not on it is refused, so a signature cannot be made up from
    an account or an email."""
    return load(os.path.join(target, DECL, "people.json"), None)


def check_person(target, name, as_speaker=False):
    roster = people(target)
    if not roster or name is None:
        return
    if name in roster.get("people", []) or (as_speaker and any(name.startswith(a) for a in roster.get("agents", []))):
        return
    raise SystemExit("%r is not in mangsang/people.json — ask the person which name they sign and speak under and add it there; "
                     "never derive one from an account, an email or session metadata" % name)


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
        # the words taken from the host's own record of the session, not retyped: exactly one turn must contain --match
        if not args.match:
            raise SystemExit("--from-transcript needs --match \"a phrase from the turn\" — the one turn that contains it is kept, whole")
        hits = [t for t in transcript_turns(args.from_transcript) if args.match in t["text"] and (not args.kind or t["kind"] == args.kind)]
        if len(hits) != 1:
            raise SystemExit("--match found %d turn(s) in the transcript%s — give a phrase that only the turn you mean contains"
                             % (len(hits), "".join("\n  %s %s: %s" % (t["kind"], t["uuid"], " ".join(t["text"].split())[:80]) for t in hits[:5])))
        turn = hits[0]
        if turn["kind"] in ("agent", "question"):
            args.speaker = args.speaker or "Claude (%s)" % (turn.get("model") or "unknown model")
        elif not args.speaker:
            raise SystemExit("this turn is the person's: --speaker says who they are (the name they gave, not one read from the account)")
        session = os.path.splitext(os.path.basename(args.from_transcript))[0]
        args.locator = args.locator or "session %s, %s %s at %s" % (session, turn["kind"], turn["uuid"], turn["at"])
        args.file = None
        text = turn["text"].replace("\r\n", "\n")
    else:
        if not (args.file and args.speaker):
            raise SystemExit("--file (the words, verbatim; `-` reads stdin) or --from-transcript, and --speaker (who said them) — a source without both is hearsay")
        text = (sys.stdin.read() if args.file == "-" else io.open(args.file, encoding="utf-8").read()).replace("\r\n", "\n")
    check_person(args.target, args.speaker, as_speaker=True)
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
    out += ["```", "", "Rounded nodes are concepts, hexagons are questions (OPEN: nothing answers it yet); a dotted edge is a relation "
            "whose end moved since it was confirmed. Sources are not drawn; each concept lists the words that ground it below.", ""]
    return out


def render_concepts(d, moved):
    """Each concept: its meaning, who declared it, and every relation on it with its state, signature and quote."""
    out = ["## Concepts", ""]
    for c in sorted(d["concepts"], key=lambda c: c["name"]):
        out += ["### %s" % c["name"], "", "> %s" % esc(c["means"]), "",
                "declared %s%s" % (signed(c.get("declared")), "; revised %d time(s)" % len(c["history"]) if c.get("history") else ""), ""]
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
            shaky = [r["id"] for r in d["relations"] if r["predicate"] == "realizes" and r["dst"][len("concept:"):] in v.get("concepts", []) and r["id"] in moved]
            realized = all(any(r["predicate"] == "realizes" and r["dst"] == "concept:" + n for r in d["relations"]) for n in v.get("concepts", []))
            state = "answered" if realized and not shaky else "FAILED"
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
        if have == text:
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
        c.setdefault("history", []).append({"means": c["means"], "declared": c["declared"]})   # what the word meant before, and on whose word
        c["means"] = args.means.strip()
        c["declared"] = signature(args.by, args.delegated)
        save_decl(args.target, d)
        n = sum(1 for r in d["relations"] if "concept:" + args.name in (r["src"], r["dst"]))
        print("concept %s now means: %s — %d projection relation(s) will go stale; that is the point" % (args.name, c["means"], n))
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
    # list
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
    return 0


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
            p.add_argument("--out", default="mangsang-judge")
            p.add_argument("--ids", nargs="*", default=None)
            p.add_argument("--limit", type=int, default=6000)
            p.add_argument("--response", default=None)
            p.add_argument("--by", default="unknown")
        if name == "observe":
            p.add_argument("--reset", action="store_true")
            p.add_argument("--at", default=None, help="with --reset: take the baseline from git at this revision (e.g. the merge base)")
        if name == "retire":
            p.add_argument("id")
            p.add_argument("--why", required=True)
        if name == "reconfirm":
            p.add_argument("ids", nargs="+")
            signing(p)
            p.add_argument("--evidence", default=None, help="the sentence that holds now, when the old quote is gone from the text (one id at a time)")
        if name == "lookup":
            p.add_argument("path", help="a file (as registered): print the confirmed relations standing on it before you touch it")
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
            p.add_argument("--kind", default=None, choices=["person", "agent", "question", "answer"], help="with --from-transcript: only turns of this kind")
        if name == "report":
            p.add_argument("--out", default=None, help="write the Markdown page here (never into mangsang/, .mangsang/ or a registered file); default stdout")
            p.add_argument("--html", default=None, help="write one self-contained HTML page here: the graph draws in any browser, offline")
            p.add_argument("--check", default=None, help="a page written earlier with --out: exit 0 when it is what the record renders now, 1 when it is behind (for a page kept in git)")
        if name == "concept":
            p.add_argument("mode", nargs="?", default="list", choices=["add", "revise", "rename", "list"])
            p.add_argument("name", nargs="?", default=None)
            p.add_argument("new", nargs="?", default=None, help="rename: the new name")
            p.add_argument("--means", default=None, help="one sentence: what this name means in this project")
            signing(p)
    args = ap.parse_args(argv)
    if getattr(args, "by", None) and args.cmd != "judge":
        sign_as_agent(args)
    return {"register": cmd_register, "confirm": cmd_confirm, "observe": cmd_observe, "impact": cmd_impact,
            "cq": cmd_cq, "check": cmd_check, "retire": cmd_retire, "reconfirm": cmd_reconfirm, "judge": cmd_judge,
            "lookup": cmd_lookup, "move": cmd_move, "concept": cmd_concept, "source": cmd_source, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
