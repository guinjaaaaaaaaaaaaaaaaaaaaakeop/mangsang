# mangsang

The net-shaped (網狀) coherence model of a project. The net is primary: named concepts are its nodes, declared once
(`concept add NAME --means "..."`) and living at the anchor `concept:NAME`; documents, code and tests are projections
of them (`realizes`), and prose is one projection of the net, not the source of truth. A concept survives any rename
of the files and sections that realize it; revising what it *means* stales every projection — on purpose. Relations
also tie artifacts to each other (`documents`, `verifies`); each is confirmed by a human, fingerprinted, and reported
stale when an end changed. Machines keep the net because the next agent has no memory and nobody can read everything.

A model can also start from people rather than from a plan: what was said in a planning talk or an interview — by the
person and by the agent they talked to — is kept verbatim as a source (`source:ID`), an answer with the turn it answers;
a concept is grounded in it by a quote, and what the talk asked but did not answer is kept as an open question until
something does.

## Install

```
claude plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang
claude plugin install mangsang@mangsang
```

Codex: `codex plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang`, `codex plugin add mangsang@mangsang` (the skill is `$mangsang:operate`).

## Commands

Each runs the engine and shows its output. `mangsang.py --help` for arguments.

| command | does |
|---|---|
| `/mangsang:register` | Watch these files (anchors: file, file#heading for Markdown, file:symbol for Python) |
| `/mangsang:source` | Keep what was said or written, verbatim, as the anchor `source:ID` (`add ID --file F\|- --speaker WHO [--locator WHERE] [--replies-to ID]`; `-` reads stdin). Both sides of a conversation are sources, and an answer is kept with the turn it answers. The same id with other text is refused — a correction is a new source. `list` shows what each source grounds |
| `/mangsang:concept` | The net's own nodes: `add NAME --means "..."` declares one (with `--by` or `--delegated`); `revise` changes its meaning and stales every projection; `rename` moves the name under every relation and every question that names it, in one command; `list` shows each concept with its projections |
| `/mangsang:confirm` | Store proposed relations after checking anchors, vocabulary, evidence (a quote that appears in one anchor's text — paraphrase is rejected) and duplicates |
| `/mangsang:observe` | Fingerprint every anchor; `--reset` takes a new baseline, `--reset --at REV` takes it from git (a merge base) |
| `/mangsang:impact` | Report stale and broken relations; exit 1 when anything is unresolved. `--only ANCHOR-PREFIX..` judges only the relations touching those anchors — a slice's check; the whole-tree invariant belongs to the merge and goal checks. `--findings` prints `dwitbuk/findings@1` (stale, broken, and relations re-confirmed by delegation) |
| `/mangsang:judge` | The judge round for stale relations: `request` packs, per relation, the text that may be stale, the text that changed and the quote confirmed; `judge_worker.py` runs it in a fresh read-only session; `consume` validates (drifted must quote the stale text verbatim) and applies only still-true — as a delegation, recorded on the relation and reported to the reviewer. Drifted and cannot-tell wait for a person |
| `/mangsang:cq` | Ask the domain questions (`answered-by`: a concept's `means` carries the answer); audit that answers are alive, both directions (see below). `add`/`revise`/`retire` declare questions and invariants alike. `--findings` prints the red as `dwitbuk/findings@1` |
| `/mangsang:check` | Ask the net's invariants (`coverage`/`projection`/`resolved`) — its health, not its questions. `--findings` prints the red as `dwitbuk/findings@1` |
| `/mangsang:lookup` | Before touching a file: the confirmed relations standing on it, and which ones the edit would make stale — size the task as the edit plus those relations. Read-only |
| `/mangsang:report` | The net on one page for a person: each concept with its meaning and what realizes it (fresh, stale or broken, with the confirmed quote), each question with its state, the sources, and a Mermaid graph of concepts, projections and questions. Read-only; `--out FILE` writes it as Markdown, `--html FILE` as one self-contained page whose graph draws in any browser with no network and nothing installed — anywhere but the record or a registered file. Derived — regenerate it, do not commit it |
| `/mangsang:retire` | Drop a relation, keeping it and the reason in retired/ |
| `/mangsang:reconfirm` | A human re-read stale relations and they still hold: `seen` becomes what the tree has now. Refused on a dead anchor (retire) or when the evidence quote is gone from the text (`--evidence` gives the sentence that holds now) |

## Files in your project

| path | committed | what |
|---|---|---|
| `mangsang/registry.json`, `vocabulary.json` | yes | what is watched; what a predicate means and which way it propagates |
| `mangsang/concepts/<name>.json` | yes | the net's nodes — one per file, each a name, its `means` sentence, and who declared it |
| `mangsang/relations/<id>.json`, `mangsang/retired/<id>.json` | yes | one relation per file, so relations added on different branches merge as distinct files; each carries `seen`, the anchor fingerprints its confirmer saw |
| `mangsang/cq/<id>.json` (and legacy `cq.json`) | yes | one competency question per file: text for people, a verify spec for the engine, its author; retired questions keep the record |
| `mangsang/sources/<id>.json` | yes | what a person said or wrote, verbatim, with the speaker and where — one per file, never rewritten. Committed like every record: in a public repository, their words are public |
| `.mangsang/` | no | this machine's baseline (for `observe` events, and for judging relations from before `seen`), events, impact |

## Anchors, predicates, quotes

`file`, `file#Heading text` (Markdown), `file:symbol` (Python top-level def/class/constant), `concept:NAME` and
`source:ID` — concepts and sources pass through the same machinery as files, a concept's `means` sentence or a source's
words as the anchor's text. A source never changes, so a relation on it goes stale only from its other end: revise the
concept a conversation grounded, and someone must re-read the words against the new sentence. In a `projection`
invariant `source:` is a medium like any prefix — `{"said": ["source:"]}` asks that every concept be grounded in
something someone said.
`documents` and `verifies` propagate `dst->src` (when the code changes, the section or test may be stale); `realizes`
propagates both ways (a revised meaning stales the projection; a changed projection may have outgrown the meaning);
`references` propagates nothing.
A relation id is the hash of (src, predicate, dst); the same relation proposed twice is a duplicate.
Every judgment (`confirm`, `reconfirm`, `concept`, `cq`) carries `--by` or `--delegated`; a `--delegated` value that
is a delegation id (`D-xxxx`, chongdae's `delegate`) is stored as `{delegated: {ref}}` — machine-readable, declared
once, never a pasted paragraph — though mangsang does not resolve it (whose delegation it is stays the record
reader's audit, not a coupling).

A relation's `evidence` is a **quote**: the machine checks that it appears in one anchor's text — for a concept, that
it quotes its `means` — not that it is true; truth is the confirmer's.
A relation is stale when an anchor it propagates from differs from what its confirmer saw (`seen`) — the same verdict
on every machine and across a merge. Broken when an anchor is gone.
Fingerprints are per anchor, LF-normalized. Python anchors hash the token stream by token *name*, so a comment, blank
line or reformatting never cries stale, and the hash is the same across 3.9–3.12 (numeric token types renumbered in
3.12; older numeric-token `seen` values are still answered for compatibility, never written). Markdown and unknown
files hash their text: in prose, wording *is* the content.

## Invariants and competency questions

Two layers, two commands — they used to share one name, and the name lied: a lint is not a question.

**`check` asks the net's invariants** — its health, `git fsck` not code review. Verify kinds: `coverage` (anchors
matching a pattern each carry a relation), `projection` (every concept realized in each named medium — doc, code,
test), `resolved` (no relation on a dead anchor). Three reds: **FAILED** (the invariant does not hold — propose the
missing relations), **UNASKABLE** (the net moved out from under it — its predicate or anchors are gone; revise it),
**UNWATCHED** (the net holds something no invariant watches — a used predicate, concepts without a projection
invariant; declare one or say why not).

**`cq` asks the domain questions** — what the model can answer, after Grüninger & Fox. A domain CQ names its answer:
`{"kind": "answered-by", "concepts": ["NAME"]}` — the concept's `means` sentence carries the answer, and `cq` prints
it. The machine never judges whether the sentence answers the words (the declarer's signature carries that, like every
confirm); it audits that the answer is *alive*. Three reds: **FAILED** (the answering concept is realized nowhere, or
its projections moved since confirmation — the promise's reality shifted; re-read before trusting the sentence),
**UNANSWERABLE** (the concept a question names is gone: the model cannot answer this of the domain), **UNQUESTIONED**
(a concept no question names — the model holds a meaning nobody asks for; write the question or say why not).
A question may also be asked before anything answers it — `{"kind": "open"}`, naming no concept: `cq` lists it
**OPEN**, and `--findings` reports it as an observation, not a red. When a concept carries the answer, `cq revise` to
`answered-by`.

Both layers' declarations live in `mangsang/cq/` and are judgments alike: `cq add ID --text "..." --verify '{...}'
--by WHO` records the author, is refused when the current model cannot support it, and `cq retire --why` keeps the
record. Structural kinds declared there answer to `check`; `answered-by` answers to `cq`. Both exit 1 on any red.

## Limits

- Never proposes a relation and never judges meaning — not even between two sources that disagree; that is a person's question, asked with both quotes. A stale relation is a question for a human (or a judge role); the answer is `retire` or `reconfirm`, after reading.
- Optional for a project. Absent, what it would have watched is a non-claim.
- The judge is a proposal: still-true is applied as a delegation (`confirmed: {delegated: "judge …"}`), never as a person's confirmation; drifted is a quote a person acts on. The old product's judge measured recall 1.00 / specificity 1.00 on planted drift; this port is not re-measured.
- `report --html` inlines mermaid 11.17.2, vendored unmodified under `vendor/mermaid/` (MIT; provenance and hash in `SOURCE.md`) — the one piece of code here not written for mangsang, pinned so that it changes only with a mangsang version.
- Not built yet: repair candidates after a rename, other languages' symbols.

## Versioning

Semver, and a version names one content: every change to the source — code, skill or command text, hooks, this README — bumps
the version in all three manifests (`plugin.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`) and the
marketplace entries before it is used anywhere. Hosts copy a plugin at install and do not look again while the version stands,
so an unbumped edit is a copy nobody can tell from the old one. **patch**: behavior or wording, every interface unchanged.
**minor**: a new command, skill, field, hook or artifact key; what exists keeps working. **major**: an artifact type, lock or
record that other products read changes shape. hunsu's `check` fails a linked plugin whose source differs from the installed
copy under one version; `hunsu install --refresh <plugin>` recopies after the bump.

## Self-check

`python test_mangsang.py` — a temp project; every stop, rejection and kind of finding fires once, with recorded provider responses where a model would have answered. No model calls.
