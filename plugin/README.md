# mangsang

The net-shaped (網狀) coherence model of a project. The net is primary: named concepts are its nodes, declared once
(`concept add NAME --means "..."`) and living at the anchor `concept:NAME`; documents, code and tests are projections
of them (`realizes`), and prose is one projection of the net, not the source of truth. A concept survives any rename
of the files and sections that realize it; revising what it *means* stales every projection — on purpose. Relations
also tie artifacts to each other (`documents`, `verifies`); each is signed by whoever judged it — a person, a delegation citing that person’s recorded words,
or the agent itself with its reason — fingerprinted, and reported
stale when an end changed. Machines keep the net because the next agent has no memory and nobody can read everything.

A model can also start from people rather than from a plan: what was said in a planning talk or an interview — by the
person and by the agent they talked to — is kept verbatim as a source (`source:ID`), an answer with the turn it
answers;
a concept is grounded in it by a quote, and what the talk asked but did not answer is kept as an open question until
something does.

Navigation: [Install](#install) · [Shared guidance](#shared-claude-and-codex-guidance) · [Commands](#commands) ·
[Project records](#files-in-your-project) · [Model rules](#anchors-predicates-quotes) ·
[Invariants and questions](#invariants-and-competency-questions) · [Limits](#limits) · [Versions](#versions)

## Install

Python **3.11 or later** is required on both hosts. Ensure `python3` on the host's PATH meets this floor;
the engine and command adapters use that executable.

```
claude plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang
claude plugin install mangsang@mangsang
```

Codex: `codex plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang`, `codex plugin add mangsang@mangsang`
(the skill is `$mangsang:operate`).

What a host installs is this directory alone — the engine, its command adapters, the skill, the vendored mermaid, the
manifests, this README and the LICENSE. The source repository's development material (its suites, maintenance guide and
agent environment) stays in the repository and is not part of an installation.

## Shared Claude and Codex guidance

The installed workflow for both hosts is [skills/operate/SKILL.md](skills/operate/SKILL.md).
The host manifests ([Claude](.claude-plugin/plugin.json), [Codex](.codex-plugin/plugin.json)) expose that same
skill directory. The [Claude command adapters](commands/) retain the individual command behavior described below;
they are not separate copies of the workflow. Host invocation syntax differs, but both use the same Python engine:
`python3 "/path/to/plugin/mangsang.py" <command> --target "/path/to/project"` with the real paths and command
(`--help` lists its arguments). Consult the shared skill for the operation and this README for command and host details.
The source repository's maintenance guide (`AGENTS.md`, which its `CLAUDE.md` imports) is not part of an installation
and is never loaded into a consuming project.

## Commands

The `/mangsang:*` entries below are Claude command adapters; `move`, `vocabulary`, `outcomes` and `review` are CLI-only (no command adapter). Both hosts can call every
engine command through Python. `python3 mangsang.py --help` lists commands; `<command> --help` lists arguments.

### `/mangsang:register`

Watch these files (anchors: file; file#heading for Markdown; file:symbol for code, styles, markup, schemas and Dockerfiles; file:key for JSON, YAML, TOML, INI and .env files — the table under Anchors)

### `/mangsang:source`

Keep what was said or written, verbatim, as the anchor `source:ID` (`add ID --file F|- --speaker WHO [--locator WHERE]
[--replies-to ID]`; `-` reads stdin — or `--from-transcript SESSION.jsonl --match "phrase" [--kind
person|agent|question|answer]`, which takes the one turn containing the phrase from the host's own session record,
verbatim, the agent's turn under its model's name, the locator filled in; `--turn ID` names the turn by the host's id when
a phrase cannot — a short approval recurs — and the ids are listed, latest last, when `--match` finds several). An
answer is the person's turn after the agent's turn it replies to: a choice picked in a question, or a reply typed
("ㄱㄱ", "1번") — a typed reply right after the agent's turn matches `--kind person` and `--kind answer` both, and its
locator names the turn it answers; an agent's text turn that asks the person (a line of it ends with `?`) matches
`--kind agent` and `--kind question` both — a question is not only a question-form call. The person's turn needs no
`--speaker` when `people.json` lists exactly one person: it is theirs, and the line says so. A choice picked in a question form is only what the person picked or typed (and
a note they typed beside it) — never the tool's wrapper ("Your questions have been answered: …"): each question of a
form is its own answer turn (`ID#1`, `ID#2`, … when the form asked several; `--turn ID` lists them), its locator names
the question it answers, and it replies to the form's source when that is kept. `--kind answer` finds an answer by what
it answers too: a phrase of its question (`--match "1/6"`), or the form's own id (`--turn` the question's id). When nothing matches, the error says what is there: turns of another kind that
contain the phrase, or where in the record it is (the agent's thinking, a tool call, a tool's output — none of it said)
and the turns around it, each with the id to pass as `--turn`. Both sides of a conversation are sources,
and an answer is kept with the turn it answers. `--excerpt "sentence"` (repeatable) keeps only those sentences of the turn —
whole sentences, verbatim, a cut mid-sentence refused, parts that sat side by side keeping their spacing — when a turn clearly splits into what the record needs and what
it does not (an approval followed by a new request); the source says it is an excerpt, and its locator names the whole
turn. The same id with other text is refused — a correction is a new source.
`--from-transcript` currently parses Claude Code JSONL only; it does not parse Codex session JSONL.
Either host can run the importer on a Claude transcript. For a Codex turn, supply the exact original text with
`--file -`, an explicit roster-admitted `--speaker` (for example `Codex (thread <thread id>)`), and a `--locator`
identifying the original session and turn. Do not reconstruct missing words or identify a Codex turn as Claude's.

A message the person sent while the agent was working is a person turn too: Claude Code keeps it as a
`queued_command` attachment, not a user record. The importer keeps the prompt verbatim, never the host's rendered
wrapper, under the attachment record's own id; its locator says "sent mid-turn". A subagent's hand-back (`isMeta`
at the record or inside the attachment, or an origin other than human), a task notification, the host's queue
(`queue-operation`) and its copy of a request to the model (`api-request-blob`) are not turns. Those last two repeat
the words; a phrase found only in these records is a miss that names where it is, never a traceback (2.4.0 died with
a TypeError there). A turn whose record has no id is refused: keep it with `--file -`, `--speaker` and `--locator`.

`list` shows what each source grounds

### `/mangsang:concept`

The net's own nodes: `add NAME --means "..."` declares one (signed by a person, a source delegation, or the agent itself with `--why`); `revise` changes its
meaning and stales every projection; `reaffirm` says the sentence still holds after a projection of it was retired
(or after it was marked drifted); `drift NAME --why "..."` marks a sentence known not to hold whose revision waits;
`rename` moves the name under every relation and every question that names it, in one command; `list` shows each
concept with its projections, and what it owes; `show NAME` is one concept whole — its meaning and signer, every
relation on it in and out with its state now, quote and signer (`lookup concept:NAME`'s lines), what it owes, the
questions it answers or that ask about it (with their state) and the sources that ground it; `list --brief` is the net as a map in a line or two — `N concept(s):
a, b, … ; M open question(s)` (names cut to fit ~300 characters), then how many relations are stale or broken, and how
many concepts owe a re-read, when any do, and how many tracked files the net cannot see — `64 tracked file(s) unseen
(plan/ 2 changed after the net, lexicons/ 8 changed after the net, write/* 1, … +13)`, the recently changed first, as
`check` groups them — and how many registered files nothing relates to (`23 registered file(s) nothing relates to
(lexicons/com/…/ 8 changed after the net, …)`) — what a reader shows an agent at session start; an empty net
prints nothing.

`add`, `revise`, `reaffirm` and `drift` use the signatures and reasons below. `reaffirm NAME --why
"what was compared and why the sentence still holds"` always needs a reason; its history entry's `reaffirmed`
keeps `read: {means_sha256, realized_by: [{anchor, fp}], lost: [{id, anchor}]}`: the sentence's SHA-256,
every current realizing source and the projections it owed. When relations on the concept were stale before the
judgment, `revise` adds `outcome: revised` and their ids as `stale` to its history entry; `drift` adds
`outcome: drifted` and `stale` to its mark. Neither adds an outcome when none was stale.

A concept's sentence is affirmed over the projections it had. Retiring one leaves the concept owing a re-read (`owes`):
the questions it answers are FAILED until `revise` gives it a new sentence or `reaffirm` (signed) says the old one still
holds — reconfirming the projections that remain does not answer it, since each reconfirm asks only "does this still
realize the concept?". `impact` counts each such concept in `unresolved_total` (an `owed` line with both commands; exit 1),
and `check` says it beside its invariants. Nothing is owed for adding a projection, for a `move`, for a projection still there in another
form (the same file under a narrower anchor, the same name in another file — a refactoring done by hand), or for a
source. The re-read hints name `concept revise NAME --means "..."` if it no longer holds and
`concept reaffirm NAME --why "..."` if it does.

A sentence that no longer says what the project does, while its revision waits (a later stage, a person's word), is
marked: `concept drift NAME --why "..."` — signed `--by`, `--delegated`, or, with neither, as the agent's own. Until
`revise` (or `reaffirm`, when the old sentence holds after all) clears it: `cq` says DRIFTED for every question the
concept answers or that stands on it (exit 1); `concept list`, `list --brief`, `lookup` and the report show the mark
beside the sentence; `impact` puts its stale relations on one line; `reconfirm`, `confirm` and `move` of a relation on
it are refused, and the judge is not asked about them. A question that also fails for another reason says both.

### `/mangsang:confirm`

Store proposed relations after checking anchors, vocabulary, evidence (a quote that appears in one anchor's text —
paraphrase is rejected) and duplicates. The confirmed leave the proposals file; the rejected stay in it, each with
`rejected: <why>` — a file in the tree that is not registered named with its `register` command — so the route is to fix
them and run the same `confirm FILE --why "..."` again (the file is removed when nothing was rejected).

Sign as a person (`--by NAME`, with `--approved-in source:ID` when run by an agent), a delegation
(`--delegated source:ID`), or the running agent (neither flag). A proposal's own `why` takes precedence over
batch `--why`; an agent or delegation needs one for each relation. A missing reason leaves that proposal rejected
with its fields preserved; the others proceed. `confirmed` stores `why`, UTC `at`, and `read`, two entries in
src/dst order: `{anchor, fp, text_sha256}`. The SHA-256 covers the anchor's full text, including its same-file
reads (defined under reconfirm). An agent's confirm is its own judgment, which no person read.

### `/mangsang:observe`

Fingerprint every anchor; `--reset` takes a new baseline, `--reset --at REV` takes it from git (a merge base)

### `/mangsang:impact`

Report stale and broken relations, and the concepts that owe a re-read (`owed`: a projection retired, every question
the concept answers failing in `cq` until `concept revise` or `concept reaffirm`); exit 1 when anything is unresolved. Broken relations whose file is gone from the
tree (and whose symbol or section is in no other registered file) are grouped by that file, with the one `retire --gone
FILE.. --why WHY` that disposes of them. `--only ANCHOR-PREFIX..` judges only the
relations touching those prefixes: `--only a.py` also selects `a.pyx`. Use `--files` for exact files;
the whole-tree invariant belongs to the merge and goal checks.
`--findings` prints `dwitbuk/findings@1` (stale, broken, `owed-reread`, and — as `delegated`, an observation — relations re-confirmed
with no person reading them: by delegation, by a judge's verdict applied, or by an agent on its own). `--show` prints,
for each stale relation, what changed: the anchor's text as it was when the relation was confirmed (from git, the
matching commit found by the earlier-text search described under reconfirm) against now; `reconfirm` prints the same before it records. A stale relation
whose anchor's own text is what was confirmed — it moved only through same-file reads — and one of whose moved reads
at least is the end of no relation of its own (a helper, a constant, an import) says so under its line, with `--show`
and in `--findings`, naming every read that moved (a related one as `related itself`): reconfirming re-reads the
related concept against the anchor, not that read's own contract — read it, then relate it or say whose detail it is. A read like that which staled relations of two or more concepts is said once more as
`shared` (`unmodeled-read`, an observation, in `--findings`): a candidate shared contract. It is said only where git holds what the confirmer saw — a version of the anchor's parts fingerprints to its `seen`.

A `verifies` stale through its test side whose record a release before 2.4.0 wrote says, under its stale line
and in `--findings`: "before mangsang 2.4.0 a verifies did not go stale when its test changed, so this change has not
been re-read; read whether the test still calls DST and asserts on what it does; `reconfirm` if it does, change or
`retire` it if not" — with its destination anchor in place of DST.

Under a broken relation that `move` would carry — the same key in another registered file, or a heading renamed
in place — a line names `mangsang move <id> --why "..."` (with the appropriate signature) and the new anchor: "the same key there"
or "renamed: only its title changed since it was confirmed". `--findings` appends the same to that broken finding.
Nothing turns fresh by itself: the relation stays broken until `move` runs.

`impact --files [FILE ...]` checks exactly relations with a file end equal to one of the given paths; `a.py`
never selects `a.pyx`, `a.py.bak` or `dir/a.py`. Paths normalize separators, leading `./`, and absolute paths
under the target. Concept and source ends are not files. The scope includes owed concepts whose lost projection
is in those files and disputed relations in scope. It begins `scope: N file(s), K relation(s) stand on them`;
unregistered input files are informational. Empty `--files` means nothing in scope and exits 0. Otherwise exit 1
exactly for a stale, broken or disputed-unrevised relation or an owed concept in scope; exit 0 otherwise.
`--only` intersects this scope; `--show` and `--findings`, including delegation observations, honour it.

A task's coherence role can use
`["python3", "{plugin:mangsang}/mangsang.py", "impact", "--target", ".", "--files", "{files}"]`.
Keep `--files` last: the runner substitutes zero or more file arguments. No base revision is needed;
staleness is judged against each relation's `seen`.

An unrevised rejection prints `disputed R-...` with the relation, person, source and reason, asking for revision
(change the projection, then reconfirm) or retirement. It counts in `unresolved_total`, exits 1, and is a
`disputed` finding. A revised rejection is listed as awaiting the person's review and is not counted.

### `/mangsang:judge`

The judge round for stale relations: `request` packs, per relation, the text that may be stale, the text that changed,
the change itself (the diff since the confirming commit, when git has it) with the declarations the changed side reads
now — a function stale because its constant moved shows the constant, not two unchanged texts — and the quote confirmed;
when the stale side is a concept, the item is marked and the sentence under judgment is the concept's whole meaning, the
quote only context. `--out DIR` is a directory (an existing one is used as is; a name ending in `.json` is refused, since
the packet is written into it): the packet is `DIR/judge-request.json`, and `request` prints its path, the response's,
and the two commands to run next. An earlier round's `judge-request.*` and `judge-response.*` there are moved aside first,
named by their time (`judge-response.20261012T093038Z.json`), and said — so the `next:` line never points at an older
round's verdicts — and `consume` refuses a response older than
the request beside it. Each response must copy the packet’s `request-id`; the worker does this automatically, and
`--prompt-only` asks the host subagent to return it. Consumption also checks the target, relation, predicate definition,
full anchor and dependency text (including comments), and dependency fingerprints against the request. If any changed, the relation remains stale and needs
a fresh request and judgment. Older packets without this binding must be regenerated. Git commits alone do not invalidate
a judgment of unchanged content. `judge_worker.py` runs it in a fresh read-only session; `consume` validates (drifted must
quote the stale text verbatim) and applies only still-true, recorded on the relation as
`{judge, applied-by, why, at, read, outcome}`: the judge’s whole evidence as `why`, UTC `at`,
the same comparison entries as reconfirm, and an engine-decided `outcome` when stale. The application is reported to the reviewer. The
judgment's author is the judge — the model, from the response's worker record (`--judge "<host> <model>"` when there is
none, e.g. a host subagent answered `--prompt-only`); who applied it is a second fact: the agent running `consume` by
default, or `--by NAME`. A person's name there, at an agent's hand, needs `--approved-in source:ID`, the turn where that
person read the verdicts. Drifted and cannot-tell wait for a person

### `/mangsang:cq`

Ask the domain questions (`answered-by`: a concept's `means` carries the answer); audit that answers are alive, both
directions (see below). `add`/`revise`/`retire` declare questions and invariants alike. `--findings` prints the red as
`dwitbuk/findings@1`. Declarations use the signatures below; an agent signs as itself with `--why`.
`cq retire ID --why "..."` keeps the signer, reason and UTC `at`; unsigned retirement remains allowed at a
person's terminal. CQ retirement has no relation `was` or staleness `outcome`.

### `/mangsang:check`

Ask the net's invariants (`coverage`/`projection`/`resolved`/`registered`/`required`) — its health, not its
questions. `--findings` prints the red as `dwitbuk/findings@1`, the observations (below), plus two facts of the record
that never fail the check: `unreleased-writer` (a committed record written by a build that is no release) and
`agent-proposed` (an observation: declarations signed in a person's name on their yes to the agent's own proposal —
`approval-of`). `--require-model`: the project keeps its model — FAILED when `mangsang/` is absent or holds no concept,
no active relation or no active invariant (`model-required` in `--findings`). Without it nothing changes: for a project
that declares nothing, an absent model is a non-claim

For a `registered` invariant, each object `except` entry prints under its line as `except GLOB hides N: WHY`.
N counts the tracked files the registry does not hold that the glob matches (the products' records are left out),
including 0. An object's `except` observation ends with its reason; with `--findings`, the `except-crosses`
text carries it too. A string entry prints as before. A malformed `except` is UNASKABLE, never a crash; the
accepted shapes and their limits are below.

A `vocabulary` observation says when `mangsang/vocabulary.json` stores an entry this engine reads differently:
today, the 2.3 `verifies` entry read as propagates both, or entries not stored at all in an empty `{}` file, read as
the defaults. One line per entry names both readings ("does not store" for an absent entry) and
`mangsang vocabulary --write`. `--findings` adds `vocabulary-read-differently`, an observation; the exit code does
not change. A non-empty file is read as it is apart from the legacy migration, with no defaults merged, so a
project's own entries are never reported.

`unrecorded-delegation N` counts standing relation confirmations, concept declarations and active CQ declarations
with old free-text or `{ref: ...}` delegations; new delegations cite `source:ID`. History is not rewritten.
For every concept realized in code that no test's `verifies` reaches, `unverified` says it has test relations
but none proves its code, or `untested` says no test relates to it. These observations appear regardless of
invariants, even when the vocabulary has no `verifies` (said in the line); they never change the exit code.
When any relation exists, `person-review` says `reviewed by a person: N of M relation(s); K changed since review;
D disputed; meanings signed by a person: a of b`. Review progress never fails `check`; no invariant yet requires it.

### `/mangsang:lookup`

Before touching a file: the confirmed relations standing on it, and which ones the edit would make stale — size the
task as the edit plus those relations. Grouped by what each relation reaches: a concept's meaning once, then each
relation with its anchor, predicate, the confirmed quote, who confirmed it (`by NAME`, `judged by <host> <model>, applied by
WHO`, `by the agent NAME, on its own`, or `delegated:` and the reason's first clause) and whether it is fresh, stale or broken now — what an agent otherwise opens `concepts/` and `relations/`
for by hand. A file with nothing on it says which case it is: not registered (and, when git tracks it beside
registered files, that the net cannot see it and how to register it), registered with no relations, or not in the
tree. A tracked, unregistered file an active `registered` invariant's except keeps out of the net instead says
`FILE is excepted by INVARIANT (GLOB) — WHY` (`no reason recorded` for a bare glob string), without NOT REGISTERED
or advice to register it. Read-only. It also takes `concept:NAME` (the meaning, then what stands on it), an artifact
anchor (`file:symbol`, `file#heading`, `file:key`), or a relation id: that relation whole, its concept's meaning,
its state, quote and signer (a retired one says so, with why).

A relation on a Markdown heading says on its line that renaming the heading breaks it and that `mangsang move`
carries a rename while the rest of its section is unchanged. A broken relation that move would carry names the
move command and the new anchor.

For an artifact anchor, after the relations on the anchor itself, lookup lists every relation on another anchor
of the same file that an edit inside it can stale and that propagates from that end: an anchor that reads it,
transitively (the test that raises a class, the function that compares a constant), the file itself or a section/key
that holds it, or a subsection inside it. Each line says `reads FILE:KEY`, `holds FILE:KEY` or `lies inside FILE:KEY`.
Lookup's prediction and impact's verdict use one closure (`edit_reach`, what a fingerprint hashes): what lookup
lists for an edit inside the anchor is what impact can then report. An enclosing anchor lists potential edits;
not every edit inside it changes every subsection. On one product, mangsang 2.3.0's `lookup test_example.py:Skip`
said nothing stood on it, but changing Skip's base class staled 10 relations through tests that read it. 2.4.0 lists
14 there, and that edit stales exactly those 14 — the 10 and four `verifies` now judged from their test side.

`lookup PATH --brief` gives at most two lines at edit time. The first says how many relations stand on the file
or anchor (including closure), up to three concepts they reach (stale first, drifted marked), how many more,
and stale/broken and disputed counts when present; without concepts it counts other ends. It says that editing
here stales those relations and re-reading them belongs to the same task, with the full `lookup PATH` command.
The second, only when relations stand on existing Markdown headings, warns that renaming breaks them and
`mangsang move` carries a title-only rename (up to three headings and ids, then `+N more`).
A registered file with no relation says `registered, but no relation stands on it — impact never sees an edit here`
and points to `check`'s unrelated observation. An unregistered tracked file covered by a `registered` invariant
says `check` fails on it, names the invariant and prefix, and asks to register and relate or except with a reason.
Other unregistered and excepted files retain their one-line explanation; a path absent from the tree prints nothing.
`concept:NAME --brief` is unchanged. Full lookup and relation-id lookup also show person review state:
never reviewed, reviewed, reviewed at an earlier text, or disputed with the person's reason and whether revised.

### `move` (Python CLI)

There is no `/mangsang:move` command adapter. Use `python3 "/path/to/plugin/mangsang.py" move --why "what was compared and why it holds at its new home" --target "/path/to/project"`
(the agent signs as itself; use `--by NAME` or `--delegated source:ID` for those signatures;
`--dry-run` previews and needs neither signature nor reason). After a refactoring moved symbols or sections: every broken relation whose dead `file:symbol` / `file#heading` has
exactly one new home among the registered files is retired (`why: moved …`) and re-confirmed on the new anchor with
the same evidence (`moved-from` names the old id) — the evidence must still be a quote there, or that relation is
left; two homes or none are left too, named. `--dry-run` reports only. A site's refactoring moved 21 relations by hand
in four tasks and missed three; this is one command.
`move` leaves a disputed relation not revised since rejection, naming who disputed it; revise and review it again, or retire it.

A new home can be the same key in another registered file of the same kind, or a heading renamed in its own file:
the old title must be gone, and there must be exactly one heading whose section, with only its title put back to
the dead one, fingerprints exactly to the relation's `seen`. Any other change in that section — a word, a line of
a subsection it holds, or its heading level — leaves the relation broken for a person. Two matching headings,
or a matching heading plus the same key in another file, are ambiguous and left. The evidence must still be a
quote there. The title is the one change `move` judges: the signer sees old -> new, the retired record
says it, and the new relation's `moved-from` names the old id. A section renamed while being edited still needs
retire-and-propose.

The new relation keeps the old `seen` for its unmoved end and transfers the old end's `seen` to the moved end.
Changed text at either end therefore stays stale where it propagates: re-read it with `reconfirm NEW --why "..."`.
Only a heading renamed in place takes the current fingerprint, since the section is identical but for its title.
The new `confirmed` keeps the signature, `why`, `at` and `read`: one entry per moved end with `anchor`,
`moved_from`, old `seen`, `now`, and either `title: "#Old -> #New"` or `same_key: true`; when the latter's
fingerprint differs it also keeps reconfirm's diff fields (or `earlier`). The old relation is retired with the
signer, `at`, `why: "moved: ...; <reason>"`, `was: broken` and `outcome: moved`.

### `vocabulary` (Python CLI)

There is no command adapter. `python3 "/path/to/plugin/mangsang.py" vocabulary --target "/path/to/project"` lists
each predicate as this engine reads it; under an entry stored differently, it says what is stored and that
`--write` writes the reading above. It writes nothing.

`vocabulary --write` rewrites only `mangsang/vocabulary.json`, as the engine reads it — the bytes `register` would
have written, a one-entry diff for the 2.3 `verifies` entry — and prints each entry written (stored -> read).
It writes nothing when nothing differs ("nothing to write") or when there is no `vocabulary.json`. No signature:
it writes the engine's reading, not a judgment. This is the direct way to commit the migrated entry that 2.4.0
left on disk until a registry-saving command ran.

### `outcomes` (Python CLI)

`outcomes [--since REV|DATE] [--json] --target DIR` reads the record without writing it. The engine, not a flag,
decides each class: stale re-reads are `other-end-updated` when both ends changed, otherwise `re-quoted` when
the quote changed, otherwise `held`; broken moves are `moved`; stale/broken retirements are `retired`; concept
revision or drift over stale relations is `revised` or `drifted`, one event per id in `stale`.
Both ends changing cannot tell which changed first.

For active and retired relations, confirmation history then the current confirmation is read oldest first;
the initial confirm or move is not a re-read event. Later confirmations and retirement objects without both
`outcome` and `at` are `unknown` (before outcomes existed); dated entries with no outcome were not handling
staleness and are omitted. Concept history and drift marks count only recorded outcomes, never unknown meanings.
Events belong to the first concept end (src before dst), or `(between artifacts)`; concept events belong to that concept.

Without `--since`, the whole record counts. A git revision selects events added since its records: confirmation
entries beyond the old count (looking in relations/ and retired/), new retirements, new concept history and drift
marks with different `at`. Uncommitted records count as now. A date (`YYYY-MM-DD` or ISO time) resolves to the
newest commit before it; no such commit means the whole history. `--since` without git is refused, exit 2.
Output gives classes per concept and totals, always including `unknown` and open stale/broken counts and owed
re-reads. `led to a change: X of Y handled with a known outcome` counts re-quoted, other-end-updated, retired,
revised and drifted as X; Y includes held and moved too, excludes unknown. It is a measurement, exit 0 except
usage errors. `--json` emits `mangsang/outcomes@1` with `since` (revision/date or null), `classes`, `concepts`,
`total`, `changed` and `known`; each group has class counts and `open: {stale, broken, owed}`.

### `review` (Python CLI)

A person can review a part at a time: `review queue [--concept NAME] [--limit N] [--markdown | --json] --target DIR`
(default limit 15, counting both meanings and relations). Show the packets to them, then keep their words:
`review accept ID... --by NAME --approved-in source:ID [--why "..."]` or
`review reject ID... --by NAME --approved-in source:ID --why "..."`.
Only a person in `people.json` may review, and a kept source spoken by that person is required even at a terminal.
Relation ids are case-insensitive; accept also takes `concept:NAME`. Rejecting a concept instead uses
`concept drift NAME --why "..." --by NAME --approved-in source:ID`.

An unknown id, retired or broken relation, an end differing from `seen`, a quote no longer in either text, or
rejection without a reason refuses the whole batch without writing. Re-read changed relations first with
`reconfirm ID --why "..."`, then the person reviews that text. Even a fresh relation can be reviewed: only its
`reviews` list is appended, not `seen`, `confirmed` or `history`. Each entry is
`{by, approved-in, at, verdict: accepted|rejected, seen: {src-anchor: fp, dst-anchor: fp}, evidence, why?}`.
A concept acceptance stores `means` instead of `seen`/`evidence`. Rejection remains disputed until revision and
another person review, or retirement. `concept rename` keeps every review, re-keying each review's `seen`
along with the relation's so no review state changes. `move` leaves a relation disputed and not revised since
rejection, naming who disputed it — it must be revised and reviewed again, or retired.

Person-signed confirmations (including history, with their own seen/quote) also count as reviews. Latest means
newest `at`; undated entries are older, confirmations in their order before explicit reviews. States are `never`,
`reviewed` (accepted at current fingerprints and quote), `reviewed-earlier` (accepted at other text),
`disputed-unrevised` (latest review rejected, current seen and quote still equal that rejection), or
`disputed-revised` (either changed since rejection; the person's turn again). A meaning is person-signed when its
current declaration is by a person or an acceptance's `means` equals the current sentence.

Queue order is fixed:

1. Meanings no person signed, by name: the whole sentence, declarer, waiting relation count and commands to accept
   the sentence or `concept revise` to the person's wording. Their relations are held and counted per concept;
   `--concept NAME` shows that meaning and its relations regardless of signature.
2. Relations under signed meanings: groups by latest person approval of the meaning (newest first, undated last),
   then total re-read count descending, then name. Within a group: disputed-revised, never, reviewed-earlier;
   ties by re-read count descending, then id. Reviewed and disputed-unrevised are omitted; the latter are counted
   as awaiting revision or retirement.
3. Relations between artifacts, with the same tiers.

Each relation packet gives id, endpoints/predicate, state, whole concept meaning, current artifact excerpts
(whitespace collapsed, at most 240 characters, centred on the quote or starting at the beginning), the quote,
signer and first 200 characters of why, changes since the earlier review (changed ends and old → new quote),
rejection reason when present, and accept/reject commands. Markdown has a title, concept headings and list entries;
JSON is `mangsang/review-queue@1` with `entries`, `held`, `disputed`, `total`, carrying the same facts.
`review status [--concept NAME]` counts relations, reviewed, at an earlier text, never and disputed per concept
and in total, and says whether a person signed each meaning. Queue and status are read-only, exit 0.
`check` observes review progress but never fails on it; a project cannot yet require person review with an invariant.

### `/mangsang:report`

The net on one page for a person: each concept with its meaning, who declared it and on what (`by NAME (approved in
source:…, answering the agent's source:…)` or `delegated: why`), and what realizes it (fresh, stale or broken, with
the confirmed quote, who confirmed it, how many times it was re-confirmed); each question with its state and author;
the sources in full where they ground something, and under **Approvals**, one line each, the ones that only approve
declarations (a "yes, go" is not a description); a Mermaid graph of concepts, projections and questions — sources are
not drawn. Read-only; `--out FILE` writes it as Markdown, `--html FILE` as one self-contained page whose graph draws
in any browser with no network and nothing installed — anywhere but the record or a registered file. Derived:
regenerate it rather than edit it; a project that keeps the page in git (to show the graph on GitHub) runs `report
--check FILE`, which exits 1 when the page is behind the record

### `/mangsang:retire`

Drop a relation, keeping it and the reason in retired/. `retire --gone FILE.. --why WHY` (or `--deleted`) is for files
deleted on purpose: every relation with an anchor in them is retired with the one reason (each kept in retired/ with
`gone` naming the file), the files leave the registry, and the concepts that lost a projection with them owe a re-read
(the `owes` rule). A path still in the tree is refused; a deleted directory names every file under it the net knew.
`impact` groups such broken relations by the deleted file and prints the command. A dead symbol or section that is in another
registered file now is a rename, not a deletion: `move` it first.

Use a person, source delegation or the running agent's own signature, always with `--why`. At a person's terminal,
retirement with neither signer flag is allowed: it remains unsigned. The `retired` object stores the signer when
present, `why`, UTC `at`, and `was: stale|broken|fresh`. Only stale or broken retirements get `outcome: retired`.

### `/mangsang:reconfirm`

Someone re-read stale relations and they still hold: `seen` becomes what the tree has now. Refused on a dead anchor
(retire) or when the evidence quote is gone from the text (`--evidence` gives the sentence that holds now).
A relation already fresh — both ends what its confirmer saw — records nothing and says `already fresh`; a diagnostic
reconfirm used to append an identical signed entry each time. Still recorded: a stale relation, a new `--evidence`
quote, a person's own `--by` re-read of a relation someone else (or an agent, or a delegation) last signed, and a `seen`
in an older fingerprint shape, upgrading it as promised below.

`reconfirm ID --why "what was compared and why the relation still holds"` always requires a reason, for every
signature. `confirmed` keeps that `why`, UTC `at`, and `read`: entries for changed ends (missing `seen` counts),
in src/dst order; `[]` if neither moved. Each is `{anchor, seen, now, against, text_sha256: {seen, now}, diff, cut}`:
`against` is the full commit SHA whose text fingerprints to the old `seen`; `diff` is the unified diff of the
changed parts, as `impact --show` prints, capped at 4000 characters including a marker line (`cut: true`).
Full text is the anchor's own text followed by each same-file part it reads, in `anchors.parts` order, joined
with `\x01` (a concept uses `means`); `text_sha256` hashes its UTF-8 bytes.

The earlier-text search tries newest-first commits that wrote the relation in relations/ or retired/ (at most 20),
then commits touching the anchor's file or concept file (at most 20). It accepts only a version matching `seen`
under the current or supported older fingerprint rule. For `moved-from`, it also tries the retired relation's old
end. Paths are relative to the target, so a project inside a larger repository works. If reconstruction fails,
the entry has `{anchor, seen, now, earlier}` instead: `no git history here`, `a shallow clone: ...`, or
`git holds no version that fingerprints to what the confirmer saw`; it never substitutes a guessed diff.
This search also supplies `impact --show`, judge request's `because_changed`, and reconfirm's printed diff.

When the relation was stale, the engine records `outcome`: `other-end-updated` if both ends differ from old `seen`,
otherwise `re-quoted` if the evidence changed, otherwise `held`. A re-read that was not stale records no outcome.

## Files in your project

### `mangsang/registry.json`, `vocabulary.json`

Committed: yes.

what is watched; what a predicate means and which way it propagates

### `mangsang/concepts/<name>.json`

Committed: yes.

the net's nodes — one per file, each a name, its `means` sentence, who declared it, `owes` (retired projections not yet
answered by a `revise` or `reaffirm`), `drift` (the sentence marked as known wrong: why, when, who), and under `history` every earlier meaning a `revise` replaced and every
`reaffirm`, each with what it answered; `reviews` keeps person acceptances of the exact `means` sentence

### every record file

Committed: yes.

`written_by: mangsang <version>` — a field, read as one: which mangsang wrote this object (`+g<sha>[-dirty]` when a
working source did; `check --findings` names a committed record so written as `unreleased-writer`). It names who wrote
the content: a newer build re-saving a record it did not change leaves the file, stamp and all, as it was. The three
`--findings` documents (`impact`, `check`, `cq`) say `"standing": true` — they read the model as it is now, so a finding
they stop reporting is gone.

### `mangsang/relations/<id>.json`, `mangsang/retired/<id>.json`

Committed: yes.

one relation per file, so relations added on different branches merge as distinct files; each carries `seen`, the
anchor fingerprints its confirmer saw; a `reconfirm` keeps what it replaces (`confirmed`, `seen`, `evidence`) under
`history`, so who first confirmed it and how often it was re-read stay in the file. `confirmed` carries the
signer and `why`, `at`, `read`, and `outcome` when handling staleness; `reviews` keeps person verdicts with the
text fingerprints and quote they read. `retired` carries `by|delegated|agent` when signed, `why`, `at`, `was`
(stale/broken/fresh) and `outcome` for stale/broken retirement or a move.

### `mangsang/cq/<id>.json` (and legacy `cq.json`, kept only where it already exists)

Committed: yes.

one competency question per file: text for people, a verify spec for the engine, its author, and under `history` what
a `revise` replaced; retired questions keep the record

### `mangsang/people.json`

Committed: yes.

roster (required for a delegation and for a review): `{"people": [names], "agents": [speaker prefixes]}` — when present, a `--by` or `--speaker` not on it
is refused. mangsang never writes it. For both hosts, use `"agents": ["Claude (", "Codex ("]`: these are
speaker prefixes, admitting names such as `Claude (<model>)` and `Codex (thread <thread id>)`.
Use the actual host and known identity, never an invented model. A bare name such as `--speaker Claude` is refused
with that roster. On a Claude transcript turn, omit `--speaker` to use the model recorded by the importer;
Codex turns use the explicit-file path described above. An entry that names nobody (empty, not a string — an empty prefix would
admit every speaker) is left out and said, with the repair. Run by an agent (Claude Code, Codex, a worker), `--by NAME` also needs `--approved-in source:ID` — a
source NAME spoke, where they approved — and records it; otherwise the agent signs its own judgment with `--why`, or cites an actual hand-off with `--delegated source:ID --why "..."`

### `mangsang/sources/<id>.json`

Committed: yes.

what a person said or wrote, verbatim, with the speaker and where — one per file, never rewritten. Committed like
every record: in a public repository, their words are public

### `.mangsang/`

Committed: no. One file, `baseline.json`: the anchors as this machine last saw them, for `observe` to print what moved
since — a working aid, not a judgment. Staleness is judged against `seen` in each relation, so a fresh clone with no
`.mangsang/` answers `impact`, `check` and `cq` exactly as the machine that confirmed did. The one thing the baseline
decides: a relation from before `seen` existed has nothing else to be judged by, and is `unjudged` until
`observe --reset --at REV` takes a baseline from the revision it was confirmed at. (`events.json` and `impact.json` were
written here until 1.12.1 and read by nothing — what a command prints is its record.)

## Anchors, predicates, quotes

`file`, `file#Heading text` (Markdown; a section runs to the next heading of its level or higher — the title heading
only to the next heading of any level, since as a section it would be the whole file, a duplicate of `file`),
`file:symbol` (a declaration of a code, style, markup or schema file), `file:key` (a key of a JSON, YAML, TOML, INI or
`.env` file), `concept:NAME` and `source:ID` — concepts and sources pass through the same machinery as files, a
concept's `means` sentence or a source's words as the anchor's text. The separator is the leftmost `#` or `:`, so a
key may hold both (`styles.css:#hero`, `plan.md#Q1: add`).

One rule cuts every kind of file (`anchors.py` holds it, one scanner per kind):

- **A declaration is an anchor**: something named at the file's top level. What that is, per kind:

  | kind | anchors (`file:…`) | reads (what the fingerprint follows in the same file) |
  |---|---|---|
  | Python | `def`/`async def`/`class`; an assignment or annotated assignment (`LIMIT: int = 10`, `a, b = …`), also under a top-level `if`/`try`; a registration — a call statement whose first argument is a string, named `callee("string")` (`app.add_url_rule("/users")`) | `ast.Name` loads: other declarations, import bindings |
  | JS/TS (`.js .mjs .cjs .jsx .ts .tsx .mts .cts`) | `function`, `class`, `const`/`let`/`var` (destructured names too), `interface`, `type`, `enum`, `namespace`, `export default` (as `default`), `module.exports`/`exports.x`; a registration — `app.get("/users")`, `router.post("/login")`, `describe("auth")`, `it("rejects a bad password")` (inside a registration's callbacks too, each by its own string) | identifiers not after `.`, not before `:`: declarations, import bindings |
  | CSS/SCSS (`.css .scss .sass .less`) | a rule per selector (`.btn`, `.nav a`; `a, b` is two anchors with the same text; a rule inside `@media` is the same selector's anchor — `.nav a` holds its mobile branch); at-rules by prelude (`@media (max-width: 600px)`, `@keyframes fade`, `@font-face`, `@mixin card`); custom properties and SCSS variables (`--color-primary`, `$gutter`) | `var(--x)`, `$x`, `@include m` → `@mixin m`, `@extend`, `animation: fade` → `@keyframes fade` |
  | HTML (`.html .htm`) and components (`.astro .vue .svelte`) | elements with an `id` (`#hero`, the element's text), `title`; whatever inline `<style>`/`<script>` and an Astro frontmatter declare, by their own scanners | an element reads its classes' rules (`class="card"` → `.card`) |
  | JSON, YAML, TOML | keys, nested to depth 3 as dotted paths — `package.json:scripts.test`, `compose.yaml:services.web`, `openapi.yaml:paths./users/{id}`, `pyproject.toml:project.dependencies`; a YAML list item's keys and a block scalar's lines are content, not keys | — |
  | INI/cfg, `.env*` | sections; `KEY=` lines (with the comment lines above the key — its documentation, quotable) | — |
  | SQL | `CREATE`/`ALTER`/`DROP` statements by object (`schema.sql:users` is the table and every ALTER on it; an index, a function) | `REFERENCES t`, `ON t` |
  | Prisma, GraphQL, protobuf (`.prisma .graphql .gql .proto`) | named blocks (`model User`, `type Query`, `enum Role`, `message Ping`, `service Echo`), `extend type` merged; nameless by keyword (`datasource`) | the blocks its fields name |
  | Dockerfile (`Dockerfile*`, `*.dockerfile`) | instructions by kind (`FROM`, `ENV`, `EXPOSE`, `CMD`…), continuations joined | `$VAR` → the `ARG`/`ENV` that declares it |
  | Markdown (`.md .mdx`) | `file#Heading` sections | — |

  Methods, nested functions, an `rpc` inside a `service`, keys below depth 3 are inside the declaration that holds
  them, not anchors of their own. A name declared twice (an `if`/`else` pair, a table and its ALTERs, a selector and
  its `@media` branch) is one anchor holding both texts. `@import`/`@use`, `export { a as b }`, an `INSERT`,
  `console.log("…")` declare nothing and fall to the file anchor.
- **Its extent runs to its body's end**: in JS/TS a function's body is the `{` after its generics, parameters and return
  type, any of which may hold braces of their own (`function f(env: Env): Promise<{ rows: unknown[] }> { … }` — before
  1.19 cut at the return type's `{`, so the body was neither fingerprinted nor quotable; a relation confirmed on such a
  function then reads stale once, its body now in the fingerprint); a class's or interface's after `<…>` and `extends Base<{ … }>`.
- **Its extent starts at its first attachment**: a decorator, `export`/`async`/`declare`, the comment lines above an
  env key. `@require_admin` is what the function does before its body does anything; a fingerprint of the `def` lines
  alone read its removal as nothing. A registration's extent is the statement — the route and its handler, the `it`
  and its body.
- **Its fingerprint covers what it reads in its file**: the free names of the declaration that resolve, in the same
  file, to another declaration or to an import binding — transitively. Raise `LIMIT = 10` to `999`, change the helper
  a function calls, swap `from auth import guard` for `from noauth import guard`: every function that reads them is
  stale, though its own lines did not move; `impact --show` names and diffs the part that did (`p.py:LIMIT, read by
  p.py:handle`). The reading is lexical — a name that appears, `ast.Name` loads in Python, identifier tokens not after
  `.` and not before `:` in JS/TS — so it over-includes (a parameter that shadows a module name) and never
  under-includes. An anchor that reads nothing has the fingerprint of its own text, as before. A `main` that calls
  everything reads everything: relate to the narrowest declaration that carries the meaning, not to the dispatcher.
- **What stops at the file.** A declaration that reads another *file* — an import's target, a value in a config file,
  a subclass in another module, the call sites that make a function dead code, the CSS cascade (which rule wins is
  order and specificity across the sheet, not a read) — is not followed: `seen` must be
  reproducible from what the confirmer had open, and a fingerprint reaching across files would tie a relation to
  text nobody read. Across files the net is the mechanism: register the other file and relate the anchor that is
  read — `config.yaml:limits realizes concept:rate-limit` beside `api.py:handle realizes concept:rate-limit`; or add
  a predicate that says it (`depends-on`, `propagates: dst->src`) to `vocabulary.json`. Tests (`verifies`) remain the
  last line: a behavior change no fingerprint can see is one a test fails on.
- **The file is an anchor too** (`""`): side effects, unnamed statements, `export { a as b }`, whatever a scanner
  cannot name — noisy to relate to, never blind. A source never changes, so a relation on it goes stale only from its other end: revise the
concept a conversation grounded, and someone must re-read the words against the new sentence. In a `projection`
invariant `source:` is a medium like any prefix — `{"said": ["source:"]}` asks that every concept be grounded in
something someone said.
`documents` propagates `dst->src` (when the code changes, the section may be stale). `verifies` propagates both ways:
when the code changes the test may be stale, and when the test changes it may no longer call the code or assert on
what it does — a test rewritten to `assert True` used to keep its `verifies` fresh for good. `realizes`
propagates both ways (a revised meaning stales the projection; a changed projection may have outgrown the meaning);
`references` propagates nothing.

On adoption, a `verifies` entry in `vocabulary.json` exactly as 2.3 and earlier wrote it is read as the new one by every
command at once and written to `vocabulary.json` (a one-entry diff) the next time a command saves the registry and
vocabulary: `register`, `confirm`, `retire` (including `retire --gone`), `move`, or a `concept` subcommand that changes
a concept. `reconfirm`, `judge consume`, `cq add/revise/retire` and `source add` write only their own record files and
leave `vocabulary.json` as it is. A project that only reconfirms its newly stale relations still holds the 2.3 entry
on disk until then; its verdicts are already the new ones. `check` now says when that entry is still on disk
(the `vocabulary` line), and `mangsang vocabulary --write` writes it directly; registry-saving commands still
write it too. A project's own `verifies` entry and its propagation are
kept. Under the new rule, every `verifies` whose test side changed since its last confirmation
or re-confirmation goes stale at once, each saying the migration line under `/mangsang:impact` above while its record
was last written by a release before 2.4.0; a reconfirm under 2.4.0 ends that notice. A `verifies` whose test is what
its confirmer saw stays fresh unless its code side changed — nothing goes stale wholesale, and no other predicate's
decision changed.

A relation id is the hash of (src, predicate, dst); the same relation proposed twice is a duplicate.

A relation's `evidence` is a **quote**: the machine checks that it appears in one anchor's text — for a concept, that
it quotes its `means` — not that it is true; truth is the confirmer's.
A relation is stale when an anchor it propagates from differs from what its confirmer saw (`seen`) — the same verdict
on every machine and across a merge. Broken when an anchor is gone.
Fingerprints are per anchor, LF-normalized, of *content*: Python and JS/TS anchors hash the token stream (comments and
formatting out; strings, regexes and template literals in — Python by token *name*, the same across 3.9–3.12, whose
numeric token types were renumbered), CSS and SQL and schema blocks their comment-free whitespace-collapsed text, HTML
its comment-free collapsed text, JSON anchors the canonical value (key order and spacing are not content),
YAML/TOML/INI/env/Dockerfile anchors their comment-free stripped lines, Markdown and unknown files their text: in prose,
wording *is* the content — a Markdown section without its trailing blank lines, which belong to the layout of what follows.
Spacing and comment marks *inside* content stay in all of them: a YAML block scalar's lines (its blank and `#` lines
too), TOML multi-line strings, SQL, CSS, Prisma, GraphQL and proto strings and a CSS `url(…)`, an HTML `<pre>` or
`<textarea>` body, a quoted attribute value; a `<script>` body and a component's frontmatter are read as JS/TS tokens and
a `<style>` body as CSS, so their strings are content and their formatting is not — 1.15–1.19.0 collapsed or stripped
all of these, so a changed string could hash the same and its relations stayed fresh. A file with none of
these hashes as before; one with any comes up stale once after the upgrade, its bytes unchanged — read it and
`reconfirm`. An anchor that reads other declarations hashes its parts' fingerprints together. Older `seen`
shapes — a text hash, a numeric-token hash, an own-tokens-only hash — are still answered for compatibility (unchanged
bytes are not stale) and never written; such a record cannot see what its anchor reads until a `reconfirm` upgrades it.

### Signatures and reasons

Judgments (`confirm`, `reconfirm`, `move`, `retire`, concept add/revise/reaffirm/drift and CQ add/revise/retire)
use one signature: `--by NAME` for a person (roster checked; an agent also supplies `--approved-in source:ID`,
where that person read and approved it), `--delegated source:ID` for a hand-off in a person's kept words (a bare
ID also works), or neither flag for the running agent's own judgment. They store `{by, approved-in?, approval-of?}`,
`{delegated: {source: "source:ID", speaker: NAME}}`, or `{agent: NAME}` respectively. At a person's terminal,
an unsigned judgment is refused with `pass --by NAME`, except retire and CQ retire, which may remain unsigned.

`--why` is stored inside the signature, alongside UTC `at` (`YYYY-MM-DDTHH:MM:SSZ`). It is always required for
reconfirm, move (except `--dry-run`), concept reaffirm/drift, retire and CQ retire, and for any agent or delegation
judgment. Confirm may take each proposal's own `why` before the batch flag. For a person's confirm and
concept/CQ add or revise, a reason is optional and stored when given. A delegation's reason explains what was
handed off. A person's signature is only for what that person read.

A delegation needs `people.json` listing the person by the name they give — never derived from an account or email —
and their words kept with `source add ID ...` first. The source's stripped speaker must be in `people` and must
not match an `agents` prefix. Until those words can be kept, agents sign their own judgments with reasons.
Free-text delegations are refused: use `--delegated source:ID --why "..."`, or neither signer flag with `--why`
for your own judgment. A `D-...` id is also refused: mangsang cannot check another tool's record; record the person's
words with `source add` and cite that source. The D-id may be named inside `--why` as a note.
Existing free-text and `{ref: ...}` delegations remain history, read as before and never rewritten;
`check` counts standing ones as `unrecorded-delegation`.

For the agent's name, an explicit `AGENT_HOST` (surrounding
whitespace stripped, case-sensitive) takes precedence over inherited markers from the other host — `codex` gives
`Codex (thread <thread id>)` when `CODEX_THREAD_ID` is non-empty, otherwise `Codex`, ignoring Claude markers and its
session model; `claude-code` gives `Claude (<model>)` from its session record, or `Claude Code` when unavailable,
ignoring `CODEX_THREAD_ID` and not requiring `CLAUDECODE`; an unknown non-empty host gives `an agent worker` when
`AGENT_WORKER` is set, otherwise `an agent`, consulting neither the thread nor the session model. With `AGENT_HOST`
absent or empty after stripping, the legacy order is `CODEX_THREAD_ID`, then `CLAUDECODE` (the same Claude names),
then `AGENT_WORKER` (`an agent worker`), otherwise no agent (a person's terminal). The same identity is used by a judge round's `applied-by`.

## Invariants and competency questions

Two layers, two commands — they used to share one name, and the name lied: a lint is not a question.

**`check` asks the net's invariants** — its health, `git fsck` not code review. Verify kinds: `coverage` (anchors
matching a pattern each carry a relation — `*` matches across `.` too, so `compose.yaml:*` counts every nested key to
depth 3; name the level you mean, `compose.yaml:services.*`, or the keys themselves), `projection` (every concept has each named medium; `test` requires a `verifies`, as below), `resolved` (no relation on a dead anchor), `registered` (every file git tracks under `paths` is in the registry,
`except` globs aside — `{"kind": "registered", "paths": ["src/", "tests/", "db/"]}`; `paths` are prefixes, so give it
folders, not the files you registered: a list of files asks nothing of the next file beside them), `required` (what the
model keeps — `{"kind": "required", "concepts": [...], "questions": [...], "invariants": [...], "relations": [{"src":
"...", "predicate": "...", "dst": "..."}]}`, FAILED when a named concept is missing, marked drifted, owes a re-read or is
realized by no relation, a named question or invariant is missing, retired or of the other layer, or a named relation is
missing, retired or broken; staleness stays `impact`'s. It must hold when declared, and an unknown key or nothing named
is UNASKABLE. A model using it needs mangsang 2.2.0 or later: an older `check` does not ask it, and an older `cq` says
it UNANSWERABLE, an unknown kind). An `except` entry is a glob string or `{"glob": "...", "why": "..."}`:
the object carries the reason the net does not claim what the glob matches. Both match by fnmatch, whose `*` matches
`/` too: `src/gen/*` excepts
every file below `src/gen/` at any depth, now and later. So a `registered` line says how many files its excepts hide
(each wildcard glob's count), and a `*` that hides code or config only by crossing a `/` is said once per glob
(**except**, an observation) — name the files it means instead (any glob, at any level, also hides every file added
below it later), or write `**` (`src/gen/**`), which matches the same and says every depth is meant.

`cq add` and `cq revise` refuse an `except` that is not a list, an entry that is neither a non-empty string nor
an object with exactly `glob` and `why`, both non-empty strings, or a glob named twice. A `why` of spaces gives
no reason; a misspelt key such as `reason` is refused. `check` says UNASKABLE for these shapes, never crashes.
2.2.1 wrote any shape unvalidated: an object crashed `check` in fnmatch, and a bare string was read
character by character, its `*` excepting every file. A model using the object form needs mangsang 2.3.0 or later:
an older `check` stops with a TypeError on it, and an older `cq add` writes any shape unvalidated. The reason is
the declarer's judgment — the engine checks that one is there, never that it is true.

Three reds:
**FAILED** (the invariant does not hold — propose the missing relations), **UNASKABLE** (the net moved out from under it — its predicate or anchors are gone; revise it),
**UNWATCHED** (the net holds something no invariant watches — a used predicate, concepts without a projection
invariant; declare one or say why not).

Observations, never red: **unseen** — with no `registered` invariant, the tracked files beside registered ones that
are not registered,
and — invariant or not — each directory of tracked code or config that holds no registered file at all, with its count
(markdown and text there are content; hidden directories, lockfiles, declared record paths and what a
`registered` invariant's `except` globs leave out are left out; files directly in a directory whose registered files are
all deeper are said as `dir/*`; the root's own files are not — every project's manifests; six are named, the rest counted).
Both are grouped by directory, and a group changed since the net's record (`mangsang/`) last changed — or in the last 20
commits, in a history longer than that — is said first, with when (`lexicons/ 8 file(s) [changed 11 commits ago, after
the net's last change]`). Then `next`: why once (a file nothing relates to is invisible to impact), the exact `register`
for each directory nothing is registered in and each recently changed group beside registered files (three at most, the
recent first), and the step after it — relate what they carry (`realizes concept:NAME` with a quote) in a proposals.json,
confirm with the appropriate signature and reason. A statement, never a stop: `check`'s exit is what its invariants say. **unrelated** — a registered file no relation stands
on is as invisible to impact (an edit there makes nothing stale): said the same way, by directory, the recent first, and
`next` names its files to relate — so a group registered from `next` moves from unseen to unrelated instead of going
quiet. Left out, as registered on purpose or already asked: a file gone from the tree (`impact`'s), a document citing a
kept source by id (`source:ID` — registered as the evidence `ungrounded` reads) and a file a `coverage` invariant's
anchors reach (that invariant says FAILED itself). **gone** — those registry entries: a registered file gone from the tree that no relation stands on
(`impact` says a gone file only through the relations broken on it, and keeps doing so), one grouped line with the exact
`mangsang retire --gone FILE.. --why "..."` that drops them (it unregisters a file with no relation as well);
**ungrounded** — a person's words kept as a source that no relation uses, no signature cites (`approved-in`,
`approval-of`) and no registered document cites by id: a decision the model does not carry yet.

With a `registered` invariant declared, **unseen** still says the tracked code and config in a registered file's folder
below the root (the root's own files are never said unseen, invariant or not: every project's manifests and settings)
that no invariant's paths or excepts name, with the `register` for them and the `cq
revise` that gives the invariant their folder, so the next one is FAILED instead. **files-only**: an invariant whose
paths are all files, in a folder no other invariant asks of or at the root, said once, before any sibling exists — at
the root such an invariant is the one place a new file is asked, by a prefix the next one will share (`test_`).

Code and test have one definition. A projection invariant's named `code` and `test` prefixes decide its media;
check-wide observations use the union of each medium's prefixes across active projection invariants. A test-prefix
match takes precedence over code. When that medium is not named, the derived rule applies: a test file's basename
matches `test_*.py`, `*_test.py`, `conftest.py`, `*_test.go`, `*.test.<ext>` or `*.spec.<ext>`, or a path segment is
`test`, `tests`, `__tests__` or `spec`. Code is a non-test file whose anchor kind is python, js or component.
Concept and source anchors are neither. Styles, markup, SQL, schemas, Dockerfiles and config need explicit code
prefixes if a project wants them counted as code.

A projection invariant's `test` medium holds only through an active `TEST verifies TARGET` with a test source.
Targets are the concept's code projections (active `realizes` sources); if it has no code, its other non-test
artifact projections, such as a section or config key, are targets. With no such target it lacks test. Destination
must equal the target anchor: verifying a file does not verify a symbol in it. A test's `realizes` is navigation,
not proof, and cannot satisfy this medium; other media still use `realizes` prefix matches. The FAILED gap says
`NAME lacks test` and names what no `verifies` reaches. Relate a test only where it calls the symbol and asserts
on what it does, never where it merely names it.

**unverified** says a concept has code and test relations but no test's `verifies` reaches its code;
**untested** says it has code but no test relation. These are observations regardless of invariants (even with no
`verifies` in the vocabulary), not failures. `unrecorded-delegation` and `person-review` are observations too,
as described under `check`.

**`cq` asks the domain questions** — what the model can answer, after Grüninger & Fox. A domain CQ names its answer:
`{"kind": "answered-by", "concepts": ["NAME"]}` — the concept's `means` sentence carries the answer, and `cq` prints
it. The machine never judges whether the sentence answers the words (the declarer's signature carries that, like every
confirm); it audits that the answer is *alive*. Three reds: **FAILED** (the answering concept is realized nowhere, or
its projections moved since confirmation, or it owes a re-read for a retired projection — the promise's reality
shifted; re-read before trusting the sentence),
**UNANSWERABLE** (the concept a question names is gone: the model cannot answer this of the domain), **UNQUESTIONED**
(a concept no question names — the model holds a meaning nobody asks for; write the question or say why not).
A question may also be asked before anything answers it — `{"kind": "open"}`, naming no answer: `cq` lists it
**OPEN**, and `--findings` reports it as an observation, not a red. It may say what it asks about — `{"kind": "open",
"about": ["venue"]}` — and those concepts are questioned, not answered: a planning model starts with most of its
questions open, and without `about` every concept it holds read as UNQUESTIONED. When a concept carries the answer,
`cq revise` to `answered-by`.

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

- Outcomes cannot order two ends changed together; `other-end-updated` records only that both differ.
- Delegation ids from another tool are not read; only a kept person's source can support a new delegation.
- The derived test/code rule is a naming convention; explicit projection media can state the project's rule.
- No invariant yet requires person review; `check` reports progress without failing on it.

- Never proposes a relation and never judges meaning — not even between two sources that disagree; that is a person's
  question, asked with both quotes. A stale relation is a question for a human (or a judge role); the answer is
  `retire` or `reconfirm`, after reading.
- Optional for a project. Absent, what it would have watched is a non-claim. A project that keeps its model says so:
  `check --require-model` and a `required` invariant.
- Judges whether anchors moved since someone read them, not whether a sentence is true. The evidence gate proves that
  a quote appears in its anchor, not that the quotes support every clause of the meaning: a `means` saying a name
  resolves "on this machine" stayed green while the code read one host's registry only. Check each universal or
  boundary clause (every, only, never, any host, on this machine) against a projection that supports it — preferably a
  test that exercises the boundary — or narrow the sentence; `mangsang:operate` says it for agents.
- The judge is a proposal: still-true is applied as the judge's (`confirmed: {judge: "<host> <model>", applied-by: …}`),
  never as a person's confirmation; drifted is a quote a person acts on. The old product's judge measured recall 1.00 /
  specificity 1.00 on planted drift; this port is not re-measured.
- `report --html` inlines mermaid 11.17.2, vendored unmodified under `vendor/mermaid/` (MIT; provenance and hash in
  `SOURCE.md`) — the one piece of code here not written for mangsang, pinned so that it changes only with a mangsang
  version.
- The JS/TS scanner is a tokenizer and a statement walker, not a parser: it names top-level declarations and their extents
  by brackets and the ASI line rule; a regex is read where one can stand. Odd code (a statement ending in `)` continued
  on the next line by `(`) can mis-cut an extent — never lose a declaration, since the file anchor holds it all.
- The CSS, HTML, SQL, schema and Dockerfile scanners are regular expressions over comment-stripped text with bracket
  matching — enough to name declarations and their extents in files written by people and formatters; a minified sheet
  or a `$$` body with a `;` inside a string may be cut wrong, never lost (the file anchor holds it all). Tailwind classes
  and CSS-in-JS live inside the component's tokens: the component anchor moves, no rule anchor exists for them.
- Content inside a string or block is known by its syntax alone: an `.env` value quoted across lines, a Dockerfile
  heredoc, a delimiter inside a trailing comment or escaped, an element made `white-space: pre` by CSS elsewhere, and
  `.a :hover` against `.a:hover` are still read as formatting; a `<script>` of a template type is read as JS.
- A heading renamed in place with the rest of its section unchanged is carried by `move`. Not built yet: repair
  candidates for a symbol or key renamed in place, or a section renamed and edited together; methods, keys below depth 3 and object members (`tailwind.config.js`'s
  `theme.colors`) as anchors of their own; languages beyond these (a scanner returning `Scan(texts, deps, hidden)` in
  `anchors.py` is the whole of adding one); reads across files (see above — a relation, today).

- `judge_worker.py` starts its host session through the vendored `hostcall.py`; the installed payload imports no other plugin.

- mangsang declares `reads` in its plugin.json — what a reader runs, kind -> argv: `file` (`lookup {path}`),
  `decision` (`cq`), `note` (`lookup {path} --brief`: a line per fact at an agent's first look at a file) and `map`
  (`concept list --brief`: the net in a line or two at session start).

- mangsang declares `records: ["mangsang/", ".mangsang/"]` in its plugin.json; an environment lock can carry it as `record-paths`, so the
  runner, the builder and the eyes leave the record alone without naming it.

## Versions

Semver: a **patch** changes behavior or wording with every interface unchanged; a **minor** adds a command, skill, field,
hook or artifact key, or changes an existing one's contract (what a built-in predicate propagates, what a command
lists or records), while what exists keeps working; a **major** changes the shape of a record, lock or artifact other
products read, or drops a supported Python or host version. The version is the one in this
directory's three manifests. The full policy and the release procedure are kept with the source repository, not in an
installation.
