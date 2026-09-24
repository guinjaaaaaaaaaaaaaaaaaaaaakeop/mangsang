# mangsang

The net-shaped (網狀) coherence model of a project. The net is primary: named concepts are its nodes, declared once
(`concept add NAME --means "..."`) and living at the anchor `concept:NAME`; documents, code and tests are projections
of them (`realizes`), and prose is one projection of the net, not the source of truth. A concept survives any rename
of the files and sections that realize it; revising what it *means* stales every projection — on purpose. Relations
also tie artifacts to each other (`documents`, `verifies`); each is confirmed by a human, fingerprinted, and reported
stale when an end changed. Machines keep the net because the next agent has no memory and nobody can read everything.

A model can also start from people rather than from a plan: what was said in a planning talk or an interview — by the
person and by the agent they talked to — is kept verbatim as a source (`source:ID`), an answer with the turn it
answers;
a concept is grounded in it by a quote, and what the talk asked but did not answer is kept as an open question until
something does.

## Install

```
claude plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang
claude plugin install mangsang@mangsang
```

Codex: `codex plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang`, `codex plugin add mangsang@mangsang`
(the skill is `$mangsang:operate`).

## Commands

Each runs the engine and shows its output. `mangsang.py --help` for arguments.

### `/mangsang:register`

Watch these files (anchors: file, file#heading for Markdown, file:symbol for Python)

### `/mangsang:source`

Keep what was said or written, verbatim, as the anchor `source:ID` (`add ID --file F|- --speaker WHO [--locator WHERE]
[--replies-to ID]`; `-` reads stdin — or `--from-transcript SESSION.jsonl --match "phrase" [--kind
person|agent|question|answer]`, which takes the one turn containing the phrase from the host's own session record,
verbatim, the agent's turn under its model's name, the locator filled in). Both sides of a conversation are sources,
and an answer is kept with the turn it answers. `--excerpt "sentence"` (repeatable) keeps only those sentences of the turn —
whole sentences, verbatim, a cut mid-sentence refused — when a turn clearly splits into what the record needs and what
it does not (an approval followed by a new request); the source says it is an excerpt, and its locator names the whole
turn. The same id with other text is refused — a correction is a new source.
`list` shows what each source grounds

### `/mangsang:concept`

The net's own nodes: `add NAME --means "..."` declares one (with `--by` or `--delegated`); `revise` changes its
meaning and stales every projection; `rename` moves the name under every relation and every question that names it, in
one command; `list` shows each concept with its projections

### `/mangsang:confirm`

Store proposed relations after checking anchors, vocabulary, evidence (a quote that appears in one anchor's text —
paraphrase is rejected) and duplicates

### `/mangsang:observe`

Fingerprint every anchor; `--reset` takes a new baseline, `--reset --at REV` takes it from git (a merge base)

### `/mangsang:impact`

Report stale and broken relations; exit 1 when anything is unresolved. `--only ANCHOR-PREFIX..` judges only the
relations touching those anchors — a slice's check; the whole-tree invariant belongs to the merge and goal checks.
`--findings` prints `dwitbuk/findings@1` (stale, broken, and relations re-confirmed by delegation). `--show` prints,
for each stale relation, what changed: the anchor's text as it was when the relation was confirmed (from git, the
commit that last wrote the relation) against now; `reconfirm` prints the same before it records

### `/mangsang:judge`

The judge round for stale relations: `request` packs, per relation, the text that may be stale, the text that changed
and the quote confirmed; `judge_worker.py` runs it in a fresh read-only session; `consume` validates (drifted must
quote the stale text verbatim) and applies only still-true — as a delegation, recorded on the relation and reported to
the reviewer. Drifted and cannot-tell wait for a person

### `/mangsang:cq`

Ask the domain questions (`answered-by`: a concept's `means` carries the answer); audit that answers are alive, both
directions (see below). `add`/`revise`/`retire` declare questions and invariants alike. `--findings` prints the red as
`dwitbuk/findings@1`

### `/mangsang:check`

Ask the net's invariants (`coverage`/`projection`/`resolved`) — its health, not its questions. `--findings` prints the
red as `dwitbuk/findings@1`, plus two facts of the record that never fail the check: `unreleased-writer` (a committed
record written by a build that is no release) and `agent-proposed` (an observation: declarations signed in a person's
name on their yes to the agent's own proposal — `approval-of`)

### `/mangsang:lookup`

Before touching a file: the confirmed relations standing on it, and which ones the edit would make stale — size the
task as the edit plus those relations. Read-only

### `/mangsang:move`

After a refactoring moved symbols or sections: every broken relation whose dead `file:symbol` / `file#heading` has
exactly one new home among the registered files is retired (`why: moved …`) and re-confirmed on the new anchor with
the same evidence (`moved-from` names the old id) — the evidence must still be a quote there, or that relation is
left; two homes or none are left too, named. `--dry-run` reports only. A site's refactoring moved 21 relations by hand
in four tasks and missed three; this is one command

### `/mangsang:report`

The net on one page for a person: each concept with its meaning, who declared it and on what (`by lee (approved in
source:…, answering the agent's source:…)` or `delegated: why`), and what realizes it (fresh, stale or broken, with
the confirmed quote, who confirmed it, how many times it was re-confirmed); each question with its state and author;
the sources in full where they ground something, and under **Approvals**, one line each, the ones that only approve
declarations (a "yes, go" is not a description); a Mermaid graph of concepts, projections and questions — sources are
not drawn. Read-only; `--out FILE` writes it as Markdown, `--html FILE` as one self-contained page whose graph draws
in any browser with no network and nothing installed — anywhere but the record or a registered file. Derived:
regenerate it rather than edit it; a project that keeps the page in git (to show the graph on GitHub) runs `report
--check FILE`, which exits 1 when the page is behind the record

### `/mangsang:retire`

Drop a relation, keeping it and the reason in retired/

### `/mangsang:reconfirm`

A human re-read stale relations and they still hold: `seen` becomes what the tree has now. Refused on a dead anchor
(retire) or when the evidence quote is gone from the text (`--evidence` gives the sentence that holds now)

## Files in your project

### `mangsang/registry.json`, `vocabulary.json`

Committed: yes.

what is watched; what a predicate means and which way it propagates

### `mangsang/concepts/<name>.json`

Committed: yes.

the net's nodes — one per file, each a name, its `means` sentence, who declared it, and under `history` every earlier
meaning a `revise` replaced

### every record file

Committed: yes.

`written_by: mangsang <version>` — a field, read as one: which mangsang wrote this object (`+g<sha>[-dirty]` when a
working source did; `check --findings` names a committed record so written as `unreleased-writer`)

### `mangsang/relations/<id>.json`, `mangsang/retired/<id>.json`

Committed: yes.

one relation per file, so relations added on different branches merge as distinct files; each carries `seen`, the
anchor fingerprints its confirmer saw; a `reconfirm` keeps what it replaces (`confirmed`, `seen`, `evidence`) under
`history`, so who first confirmed it and how often it was re-read stay in the file

### `mangsang/cq/<id>.json` (and legacy `cq.json`, kept only where it already exists)

Committed: yes.

one competency question per file: text for people, a verify spec for the engine, its author, and under `history` what
a `revise` replaced; retired questions keep the record

### `mangsang/people.json`

Committed: yes.

optional roster: `{"people": [names], "agents": [speaker prefixes]}` — when present, a `--by` or `--speaker` not on it
is refused. Run by an agent (Claude Code, Codex, a worker), `--by NAME` also needs `--approved-in source:ID` — a
source NAME spoke, where they approved — and records it; otherwise the agent signs `--delegated`

### `mangsang/sources/<id>.json`

Committed: yes.

what a person said or wrote, verbatim, with the speaker and where — one per file, never rewritten. Committed like
every record: in a public repository, their words are public

### `.mangsang/`

Committed: no.

this machine's baseline (for `observe` events, and for judging relations from before `seen`), events, impact

## Anchors, predicates, quotes

`file`, `file#Heading text` (Markdown; a section runs to the next heading of its level or higher — the title heading
only to the next heading of any level, since as a section it would be the whole file, a duplicate of `file`),
`file:symbol` (Python top-level def/class/constant), `concept:NAME` and
`source:ID` — concepts and sources pass through the same machinery as files, a concept's `means` sentence or a
source's
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

### Relations between concepts: what a question stands on

A project may add its own predicates between concepts to `mangsang/vocabulary.json` — `requires` (an activity needs a
fixture, `propagates: dst->src`), `is-a` (a kind, `propagates: none`), whatever its domain says. mangsang does not know
what they mean; it reads their `propagates`, the same rule `impact` judges staleness by:

- **A question stands on what its answer stands on.** `cq` follows, from each concept a question names, every relation
  between concepts along which a change travels toward it, and counts what it reaches as asked for (`through requires:
  …` in the output) — no longer `UNQUESTIONED`. When one of those concepts, or a relation on the way, moved since it was
  confirmed, the question is `FAILED`, naming the path. Relations to sections, code or sources are projections, not
  dependencies, and are not followed. A project with no relations between concepts sees no difference.
- **A coverage invariant can choose its targets by a relation.** `{"kind": "coverage", "predicate": "requires",
  "members": {"predicate": "is-a", "of": "fixture"}, "as": "dst"}` asks that every concept that is-a fixture (followed
  transitively along is-a) be the `dst` of some `requires` — every fixture needed by something. Kinds are concepts, with
  a meaning and a ground like any other; mangsang has no classification of its own.

## Limits

- Never proposes a relation and never judges meaning — not even between two sources that disagree; that is a person's
  question, asked with both quotes. A stale relation is a question for a human (or a judge role); the answer is
  `retire` or `reconfirm`, after reading.
- Optional for a project. Absent, what it would have watched is a non-claim.
- The judge is a proposal: still-true is applied as a delegation (`confirmed: {delegated: "judge …"}`), never as a
  person's confirmation; drifted is a quote a person acts on. The old product's judge measured recall 1.00 /
  specificity 1.00 on planted drift; this port is not re-measured.
- `report --html` inlines mermaid 11.17.2, vendored unmodified under `vendor/mermaid/` (MIT; provenance and hash in
  `SOURCE.md`) — the one piece of code here not written for mangsang, pinned so that it changes only with a mangsang
  version.
- Not built yet: repair candidates after a rename, other languages' symbols.

- `judge_worker.py` starts its host session through `hostcall.py` — one host call for every worker of this family (hunsu's judge, mangsang's judge, dwitbuk's eyes,
  hacheong's members), vendored: the same file in each plugin, since a plugin imports no other plugin. The umbrella checkout's `tools/same-file.py` says when the copies drift.

- mangsang declares `records: ["mangsang/", ".mangsang/"]` in its plugin.json; hunsu's lock carries it as `record-paths`, so the
  runner, the builder and the eyes leave the record alone without naming it.

## Versioning

Semver, and a version names one content: every change to the source — code, skill or command text, hooks, this README
— bumps
the version in all three manifests (`plugin.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`) and the
marketplace entries before it is used anywhere. Hosts copy a plugin at install and do not look again while the version
stands,
so an unbumped edit is a copy nobody can tell from the old one. **patch**: behavior or wording, every interface
unchanged.
**minor**: a new command, skill, field, hook or artifact key; what exists keeps working. **major**: an artifact type,
lock or
record that other products read changes shape. hunsu's `check` fails a linked plugin whose source differs from the
installed
copy under one version; `hunsu install --refresh <plugin>` recopies after the bump.

## Self-check

`python test_mangsang.py` — a temp project; every rejection and every kind of staleness fires once. No model calls.

`python test_properties.py` — the design's rules, tried against situations a machine makes up
([Hypothesis](https://hypothesis.readthedocs.io/),
a developer's dependency only: `pip install hypothesis`; without it every property is SKIPped, never passed). A
section edit
moves exactly that section's anchors; a stale relation names the end that changed and only when it propagates; `impact
--show`
finds the earlier text wherever the target sits in a repository; any sequence of `reconfirm`, `revise`, `rename` keeps
every
earlier judgment and never makes a question unanswerable; coverage and projection are functions of the net and never
get
worse from another relation. Four of the seven defects a day on a playground found (2026-09-24) were of this kind — in
situations nobody had written an example for.
