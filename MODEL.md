# mangsang's own model — scope

This repository keeps a small mangsang model of itself in `mangsang/`. It is a bounded core-contract model: five
concepts that carry what mangsang promises about relations, each tied to the user documentation, the engine code and
the example suite that express it. It is a source-maintenance aid, not part of the installed plugin: nothing here or
in `mangsang/` ships in `plugin/`.

The records are written by the installed, released mangsang engine (the version `hunsu.json` pins), never by this
checkout's `plugin/` runtime. Every meaning, question and relation is an agent's judgment, signed `--delegated` under
the owner's Stage 1 model-application task (and the registered scope under the owner's 2026-11-06 Stage A request); no
person approved the wording, and no conversation or transcript is a source of this model.

## Covered contracts

- `evidence-gate` — what must hold before a relation is stored (question `cq-relation-stored`).
- `staleness-against-seen` — when a relation is stale or broken, judged against what its confirmer saw
  (question `cq-stale-or-broken`).
- `same-file-reads` — which edits beyond an anchor's own lines change its fingerprint (question `cq-edit-reach`).
- `living-answer` — when a domain question counts as answered, and what that does not claim
  (question `cq-question-answered`).
- `owed-reread` — what retiring a concept's projection leaves owing, and what clears it
  (question `cq-retired-projection`).

Each concept is realized in a section of `plugin/README.md`, a symbol of `plugin/mangsang.py` or `plugin/anchors.py`,
and a function of `test_mangsang.py`, each with a quote the engine found in that anchor's text; each test `verifies` the
symbol it exercises (`cmd_confirm`, `compute_impact`, `anchors.parts`, `answer_health`, `owe_for`). This file names all
five concepts, and `AGENTS.md`'s rule to preserve evidence and freshness checks names `evidence-gate` and
`staleness-against-seen`, by `references`, which never goes stale. `concept show NAME` and `lookup PATH` print the
relations.

Registered files, all and only: `plugin/mangsang.py`, `plugin/anchors.py`, `plugin/README.md`, `test_mangsang.py`,
`AGENTS.md`, `MODEL.md`. Invariants (`check`): the registered scope (`inv-registered-scope`) — every file git tracks
under the prefixes `plugin/` (the payload, every subdirectory included) and `test_` (the root suites), and `AGENTS.md`
and `MODEL.md`, is registered unless an `except` under [Not claimed](#not-claimed) names it, so a new file committed
there fails `check` until it is registered and related or classified there with its reason; every concept realized in
doc (`plugin/README.md`), code (`plugin/mangsang.py`, `plugin/anchors.py`) and test (`test_mangsang.py`); no relation
on a dead anchor; each of the five verified symbols the `dst` of a `verifies`.

## Not claimed

- Whole-source coverage. Most of `plugin/mangsang.py` and `plugin/anchors.py` is related to nothing: an edit there makes
  nothing stale unless it changes a related symbol or something that symbol reads in its file. A green model says only
  that these five contracts still stand on the anchors related to them.
- The scanners beyond the sample: anchor extraction for JS/TS, CSS, HTML and components, SQL, schemas, Dockerfiles and
  config files, and every Python or Markdown rule the selected anchors do not reach, is outside the model.
- The other commands and records: `move`, `judge` and `judge_worker.py`, `source` and the transcript importer, the
  people roster and agent signing, `lookup`, `report`, `check`'s observations (unseen — with a `registered` invariant
  or without — unrelated, gone, ungrounded, files-only, except, unverified), the `required` invariant kind and
  `check --require-model`, what `impact` says of a stale relation beyond its staleness (`--show`, `moved only through`,
  `shared`), drift, the vendored `hostcall.py`, the command adapters, the skill, the manifests and the packaging. The
  suites exercise them; no relation here makes an edit to them stale.
- The rest of the payload and the other suites. Each is an `except` of the registered scope, named exactly or by a glob
  whose reason covers every file it can match now or later; a file under `plugin/` or `test_` that none of them names
  fails `check`:
  - `plugin/.claude-plugin/plugin.json`, `plugin/.codex-plugin/plugin.json`, `plugin/plugin.json` — the three
    manifests: host integration and packaging, which `test_package.py` checks.
  - `plugin/LICENSE` — the license text.
  - `plugin/commands/*.md` — the Claude command adapters. Each is a Markdown prompt that runs a documented CLI command
    whose semantics stay in `plugin/mangsang.py`, and an adapter may not invent a second workflow, so a later `.md`
    there is one more adapter; a file of any other kind there is not excepted.
  - `plugin/skills/operate/SKILL.md` — the operate skill: installed operation, not engine semantics. A new skill is not
    excepted.
  - `plugin/hostcall.py` — vendored, kept in step with the other copies.
  - `plugin/judge_worker.py` — the judge's worker; `judge` is not claimed.
  - `plugin/vendor/mermaid/*` — the vendored third-party mermaid: its bundle, license and `SOURCE.md`. Every file in
    that directory belongs to that copy, which mangsang does not author; another vendored library is not excepted.
  - `test_package.py`, `test_properties.py`, `test_running_agent.py` — the other suites.
  - `test_model_guard.py` — the regression suite of `check_model.py`, which guards this model, not a mangsang contract.
- Files outside the registered scope. The registered scope asks nothing of the rest of the root — the source-checkout
  launchers `mangsang.py` and `judge_worker.py`, `check_model.py`, the catalogs and settings, `README.md` and the hunsu
  environment — so a new root file whose name does not start with `test_` does not fail `check`, and a new top-level
  directory of code or config is only said as unseen, never red.
- Truth. The engine checks that each quote appears in its anchor and that the anchors have not moved; whether a
  sentence is right is the signer's judgment, and here that signer is an agent.

## Maintenance

Before editing a registered file, run `lookup PATH` with the released engine and size the work as the edit plus the
relations it stales. The owning or orchestrating session makes those model updates within the same change; a bounded
worker reports the anchors and relations its edit affects and writes no record unless its task contract authorizes it. Re-read a stale relation before `reconfirm`; change the projection, `retire` it with a reason, or
`concept revise` when the sentence no longer holds; never reconfirm unread. Before calling covered work complete, run
`python3 check_model.py` — it fails when the model is absent or has lost an expected concept, question, invariant,
registered file, projection or verified symbol, when the registered scope no longer asks of `plugin/`, `test_`,
`AGENTS.md` and `MODEL.md`, or when it holds an `except` that `check_model.py` does not classify or
[Not claimed](#not-claimed) does not name, then runs the released engine's `check`, `cq` and `impact` and fails when any
of them does — and `python3 test_model_guard.py`, which proves those failures on disposable copies. Classifying another
file is a change to both: its reason under Not claimed and its entry in `check_model.py`. Neither
writes, regenerates or reconfirms a record; the engine comes from `--engine`, `MANGSANG_ENGINE` or the `hunsu.json` pin.
