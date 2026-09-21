"""mangsang — the net-shaped model (網狀): named concepts, their projections into documents, code and tests, and what went stale.

The net is primary; prose documents are one projection of it, not the source of truth. A concept is declared once
(`concept add NAME --means "..."`), lives at the anchor `concept:NAME`, and survives any rename of the files and
sections that realize it. Relations tie projections to concepts (`realizes`) and artifacts to each other
(`documents`, `verifies`); staleness is judged against what a confirmer saw, per anchor fingerprint.

  register <path>...            watch these files (anchors: `file`, `file#heading` for Markdown, `file:symbol` for Python)
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
                                (the model moved out from under it), model content no question examines is UNQUESTIONED; exit 1 on any of the three
  cq add|revise|retire ID       declare a question (--text + --verify JSON, --by|--delegated) — refused if it cannot be asked of the current model;
                                retiring keeps the record (--why). One file per CQ under mangsang/cq/; legacy cq.json still read
  retire <id> --why WHY         drop a relation, keeping it (and why) in `retired`
  lookup <path>                 before touching a file: the confirmed relations standing on it (read-only) — size the edit as code + relations
  reconfirm <id>... --by NAME | --delegated WHY [--evidence "..."]
                                a human re-read a stale relation and it still holds: `seen` becomes what the tree has now; the evidence must still be in the text

Two places. `mangsang/` is the project's knowledge (registry, vocabulary, cq, one file per relation) — committed, changed only when a human
confirms. `.mangsang/` is this machine's observation (baseline, events, impact) — not committed.
mangsang never proposes a relation and never judges meaning; it checks, stores, fingerprints and diffs.
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


def signature(by, delegated):
    """The judgment's author line. A --delegated value matching a delegation id (D-xxxx, chongdae's `delegate`)
    is stored as a structured reference — machine-readable, so no reason string is pasted N times — but mangsang
    never resolves it: whose delegation it is and whether it exists is the record-reader's audit (dwitbuk), not
    this engine's coupling. Any other value stays a free-form why-string, as before."""
    if by:
        return {"by": by}
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
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


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
         "relations": [], "retired": [], "concepts": [], "cq_declared": []}
    for kind, key in (("relations", "relations"), ("retired", "retired"), ("concepts", "concepts"), ("cq", "cq_declared")):
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
    save(os.path.join(root, "cq.json"), d["cq"])
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
            end = next((s for s, l, _ in heads[i + 1:] if l <= level), len(text))
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
    """{anchor-key: text} for a file — or for the reserved virtual file `concept`, whose anchors are the concepts
    themselves and whose text is each concept's `means` sentence. One reader for real and net-own anchors alike."""
    if f == "concept":
        return {":" + c["name"]: c["means"] for c in decl(target)["concepts"]}
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


def snapshot(target, registry, at=None, concepts=None):
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
    if concepts is None:
        concepts = decl(target)["concepts"]
    if concepts:
        files["concept"] = {":" + c["name"]: fp(c["means"]) for c in concepts}
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


def compute_impact(target, d, only=None):
    """(stale, broken, unjudged, files). Stale = an anchor the relation propagates from differs from what its confirmer saw (`seen`);
    relations without `seen` are judged against this machine's baseline, or listed as unjudged when there is none."""
    base_path = os.path.join(target, OBS, "baseline.json")
    files, _ = snapshot(target, d["registry"])
    ev = diff_events(load(base_path)["files"], files) if os.path.exists(base_path) else None
    if ev is not None:
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
        if (prop in ("dst->src", "both") and touched(r["dst"], r)) or (prop in ("src->dst", "both") and touched(r["src"], r)):
            stale.append({"id": r["id"], "stale": r["src"] if prop != "src->dst" else r["dst"], "because": r["dst"] if prop != "src->dst" else r["src"]})
    return stale, broken, sorted(set(unjudged)), files


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
        for medium, prefixes in (v.get("media") or {}).items():
            if not any(p.startswith(tuple(prefixes)) for p in files):
                missing.append("presupposes medium %r (%s) — no registered file matches" % (medium, ", ".join(prefixes)))
        if not v.get("media"):
            missing.append("presupposes `media` naming each medium's anchor prefixes")
    elif v.get("kind") == "resolved":
        pass   # asks only about the relations themselves; always askable
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
            print("  %-12s %s  %s" % ("UNASKABLE", q["id"], q["text"]))
            for m in presup:
                print("      %s" % m)
            findings.append({"kind": "invariant-unaskable", "where": q["id"], "source": "mangsang", "note": "; ".join(presup)})
            continue
        ok, detail = eval_invariant(d, files, all_anchors, q)
        failed += not ok
        if not ok:
            findings.append({"kind": "invariant-failed", "where": q["id"], "source": "mangsang", "note": detail})
        print("  %-12s %s  %s — %s" % ("holds" if ok else "FAILED", q["id"], q["text"], detail))
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
        print("  %-12s %s — the net holds this and no invariant watches it; declare one or say why not" % ("UNWATCHED", u))
        findings.append({"kind": "invariant-unwatched", "where": u, "source": "mangsang",
                         "note": "in use by confirmed relations (or declared concepts) but watched by no declared invariant"})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "findings": findings}, ensure_ascii=False, indent=1))
    print("invariants %d · holds %d · failed %d · unaskable %d · unwatched %d"
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
    for q in active:
        presup = cq_presuppositions(d, files, q)
        if presup:
            unanswerable += 1
            print("  %-12s %s  %s" % ("UNANSWERABLE", q["id"], q["text"]))
            for m in presup:
                print("      %s" % m)
            findings.append({"kind": "cq-unanswerable", "where": q["id"], "source": "mangsang",
                             "note": "; ".join(presup)})
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
            findings.append({"kind": "cq-failed", "where": q["id"], "source": "mangsang", "note": "; ".join(problems)})
        answer = "; ".join("%s: %s" % (n, byname[n]["means"]) for n in names if n in byname)
        print("  %-12s %s  %s" % ("answered" if ok else "FAILED", q["id"], q["text"]))
        print("      %s %s" % ("=" if ok else "?", answer[:240]))
        for p in problems:
            print("      %s" % p)
    # the reverse audit: which concepts does no question name? (G&F: content the questions do not justify)
    named = {n for q in active for n in q.get("verify", {}).get("concepts", [])}
    unquestioned = sorted(c["name"] for c in d["concepts"] if c["name"] not in named)
    for u in unquestioned:
        print("  %-12s concept:%s — the model holds this meaning and no question asks for it; write the CQ or say why not" % ("UNQUESTIONED", u))
        findings.append({"kind": "cq-unquestioned", "where": "concept:" + u, "source": "mangsang",
                         "note": "declared and realized, but named by no competency question"})
    if getattr(args, "findings", False):
        print(json.dumps({"artifact-type": "dwitbuk/findings@1", "source": "mangsang", "findings": findings}, ensure_ascii=False, indent=1))
    tail = " · %d structural declaration(s) now answer to `check`" % structural if structural else ""
    print("cq %d · answered %d · failed %d · unanswerable %d · unquestioned %d%s"
          % (len(active), len(active) - failed - unanswerable, failed, unanswerable, len(unquestioned), tail))
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
        if args.evidence:
            r["evidence"] = args.evidence
        if not quoted(args.target, r["evidence"], r["src"], r["dst"]):
            raise SystemExit("%s: its evidence is no longer in the text (%r) — re-read and give the sentence that holds now: --evidence \"...\", or retire" % (rid, r["evidence"][:80]))
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
                rels.append((r["id"], a, r["predicate"], other, moves))
                break
    if not rels:
        print("no confirmed relations touch %s" % args.path)
        return 0
    for rid, a, pred, other, moves in rels:
        print("  %s  %s %s %s%s" % (rid, a, pred, other, "  — changing this anchor makes the relation stale" if moves else ""))
    print("%d relation(s) on %s — an edit here and their update are one piece of work, not two" % (len(rels), args.path))
    return 0


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
        save_decl(args.target, d)
        print("concept %s -> %s: %d relation(s) moved with it — the name is the identity, so the rename is one command, not a retirement" % (args.name, args.new, moved))
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mangsang", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("register", "confirm", "observe", "impact", "cq", "check", "retire", "reconfirm", "judge", "lookup", "concept"):
        p = sub.add_parser(name)
        p.add_argument("--target", default=".")
        if name == "register":
            p.add_argument("paths", nargs="+")
        if name == "confirm":
            p.add_argument("proposals")
            p.add_argument("--by", default=None)
            p.add_argument("--delegated", default=None)
        if name == "cq":
            p.add_argument("mode", nargs="?", default="run", choices=["run", "add", "revise", "retire"])
            p.add_argument("id", nargs="?", default=None)
            p.add_argument("--text", default=None, help="the question, for people")
            p.add_argument("--verify", default=None, help="JSON: domain questions are {\"kind\": \"answered-by\", \"concepts\": [...]} — the named concepts carry the answer; structural kinds (coverage|projection|resolved) are declared here too but answer to `check`")
            p.add_argument("--why", default=None, help="retire: what made this question no longer worth asking")
            p.add_argument("--by", default=None)
            p.add_argument("--delegated", default=None)
            p.add_argument("--findings", action="store_true", help="print failed/unanswerable/unquestioned as dwitbuk/findings@1 JSON")
        if name == "check":
            p.add_argument("--findings", action="store_true", help="print failed/unaskable/unwatched as dwitbuk/findings@1 JSON")
        if name == "impact":
            p.add_argument("--findings", action="store_true", help="print stale/broken as dwitbuk/findings@1 JSON")
            p.add_argument("--only", nargs="*", default=None, help="judge only relations touching these anchor prefixes (a slice's check)")
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
            p.add_argument("--by", default=None)
            p.add_argument("--delegated", default=None)
            p.add_argument("--evidence", default=None, help="the sentence that holds now, when the old quote is gone from the text (one id at a time)")
        if name == "lookup":
            p.add_argument("path", help="a file (as registered): print the confirmed relations standing on it before you touch it")
        if name == "concept":
            p.add_argument("mode", nargs="?", default="list", choices=["add", "revise", "rename", "list"])
            p.add_argument("name", nargs="?", default=None)
            p.add_argument("new", nargs="?", default=None, help="rename: the new name")
            p.add_argument("--means", default=None, help="one sentence: what this name means in this project")
            p.add_argument("--by", default=None)
            p.add_argument("--delegated", default=None)
    args = ap.parse_args(argv)
    return {"register": cmd_register, "confirm": cmd_confirm, "observe": cmd_observe, "impact": cmd_impact,
            "cq": cmd_cq, "check": cmd_check, "retire": cmd_retire, "reconfirm": cmd_reconfirm, "judge": cmd_judge,
            "lookup": cmd_lookup, "concept": cmd_concept}[args.cmd](args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
