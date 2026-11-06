# mangsang — source repository

mangsang is the net-shaped (網狀) coherence model of a project: named concepts, the documents, code and tests that
realize them, relations a person confirmed between them, and which of those went stale when one end changed. What it
does and how to use it is [plugin/README.md](plugin/README.md) — the user documentation, shipped with every
installation. This page is about the repository: installing it versus working on it.

Navigation: [Install](#install) · [Clone and develop](#clone-and-develop) · [Developer setup](#developer-setup) ·
[Versioning](#versioning) · [Self-check](#self-check)

## Install

Python **3.11 or later** is required on both hosts.

```
claude plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang
claude plugin install mangsang@mangsang
```

Codex: `codex plugin marketplace add guinjaaaaaaaaaaaaaaaaaaaaakeop/mangsang`, `codex plugin add mangsang@mangsang`
(the skill is `$mangsang:operate`).

Both catalogs at this root — [Claude](.claude-plugin/marketplace.json) and [Codex](.agents/plugins/marketplace.json) —
select `./plugin`: a host copies that directory and nothing else. Installing never brings this repository's suites,
maintenance guide or agent environment into a consuming project.

## Clone and develop

A clone is for working on mangsang. Its layout:

- [`plugin/`](plugin/) — the installed payload and the one copy of the runtime: the engine `mangsang.py`, `anchors.py`,
  `judge_worker.py`, the vendored `hostcall.py`, the Claude [command adapters](plugin/commands/), the shared
  [skill](plugin/skills/operate/SKILL.md), the vendored mermaid ([provenance](plugin/vendor/mermaid/SOURCE.md)), the
  three manifests ([`plugin.json`](plugin/plugin.json), [Claude](plugin/.claude-plugin/plugin.json),
  [Codex](plugin/.codex-plugin/plugin.json)), the user [README](plugin/README.md) and [LICENSE](plugin/LICENSE). It runs
  when copied alone: nothing in it imports from, or points into, the rest of the checkout, and it holds no symlink.
- this root — development and self-management: the maintenance guide [AGENTS.md](AGENTS.md) (which
  [CLAUDE.md](CLAUDE.md) imports), the suites (`test_*.py`, below), this checkout's own agent environment
  ([hunsu.json](hunsu.json), [hunsu.lock.json](hunsu.lock.json), [hunsu-judgments.json](hunsu-judgments.json); the local
  overlay and run and review records are not committed), the two catalogs, the repository's
  [LICENSE](LICENSE) (the same text as `plugin/LICENSE`), and the source entrypoints `mangsang.py` and `judge_worker.py`.
- the source model — a bounded mangsang model of this repository's core contracts in `mangsang/` (committed, written by
  the released engine), its scope and non-claims in [MODEL.md](MODEL.md), and its guard [check_model.py](check_model.py)
  with [test_model_guard.py](test_model_guard.py) (below). Maintaining it is part of a change to a file it registers;
  [AGENTS.md](AGENTS.md) says who does what.

The root `mangsang.py` and `judge_worker.py` keep a clone's source entrypoints, as wrappers, never second copies:
run (`python3 mangsang.py <command> ... --target <project>`, `python3 judge_worker.py --request ... --response ...`, or
`--help`), each runs its `plugin/` file exactly as `python3 plugin/<file>` would; imported from a clone
(`import mangsang`, `import judge_worker`), each makes the name the runtime module of `plugin/` itself — one instance,
with `anchors` and `hostcall` from `plugin/` too. Installed hosts call `<plugin root>/mangsang.py` and
`<plugin root>/judge_worker.py` and never see the wrappers. Records written from this checkout are stamped
`mangsang <version>+g<sha>` (`-dirty` with uncommitted changes) — a working source never passes for the release. The
engine counts as a working source when its directory is its git work tree's toplevel, or when that toplevel's own Claude
or Codex catalog maps `mangsang` to it (here: `./plugin`); a directory merely named `plugin/` in another repository is
not, and an installed, standalone or vendored copy of `plugin/` stamps `mangsang <version>`. A host or tool linked to a
local clone links `plugin/`, not this root.

### Developer setup

First decide which you are doing.

- **Using mangsang** in another project: install it from the marketplace ([Install](#install)) and stop. This
  checkout's `hunsu.json`, `hunsu.lock.json`, `hunsu-judgments.json` and local overlay describe the environment for
  developing mangsang itself; do not apply them to the consuming project or copy anything from this root into it.
- **Modifying mangsang**: clone this repository, then prepare the environment it declares:
  1. Read [hunsu.json](hunsu.json) together with `hunsu.local.json` when this machine has one (the uncommitted overlay:
     local links, hooks and settings). `hunsu.lock.json` is one machine's resolution of that declaration, not the
     declaration — do not set up from the lock alone.
  2. Install the released hunsu that `hunsu.json` pins (its `source` and `marketplace`) through the host's plugin
     workflow, then let it prepare the declared plugins from this root: its `install` followed by `check`, or its
     `compose`, which stops at each decision that is the owner's. Repeat `check` until it reports no errors here.
  3. Scope that to the host you are using and to the hosts of the roles your work actually hires. `hunsu.json`'s
     `roles` run the implementer and newbie on Codex and the nitpick, quibble and verifier on Claude; do not install or
     start the other host only for coverage. Never silently replace a declared role, host or model: if a provider cannot
     run here, say so, and make any substitution a recorded decision or the owner's.
  4. Keep machine-local, secret and authentication configuration local: `hunsu.local.json`,
     `.claude/settings.local.json`, the generated `.codex/hooks.json`, host logins and API keys are never committed or
     copied into `plugin/`.

  The suites ([Self-check](#self-check)) need only Python 3.11 or later, and Hypothesis for the property suite; they do
  not need the development plugins.

## Versioning

Semver, and a version names one content: every change to the source — code, skill or command text, hooks, either README
— bumps
the version in all three manifests (`plugin/plugin.json`, `plugin/.claude-plugin/plugin.json`,
`plugin/.codex-plugin/plugin.json`) and the marketplace entries before it is used anywhere. Hosts copy a plugin at install and do not look again while the version
stands,
so an unbumped edit is a copy nobody can tell from the old one. **patch**: behavior or wording, every interface
unchanged.
**minor**: a new command, skill, field, hook or artifact key; what exists keeps working. **major**: an artifact type,
lock or
record that other products read changes shape, or a supported Python or host version is dropped (a raised `engines`
floor) — an installation that ran yesterday stops running. 2.0.0 is such a release: it raised the Python floor to
`>=3.11` in all three manifests, dropping 3.9 and 3.10, which 1.19.3 and earlier declared (`>=3.9` in `plugin.json`
and `.claude-plugin/plugin.json`).
2.1.0 is minor: the distribution changed shape — the catalogs select `./plugin`, so a host installs only that directory,
and the checkout gained its root source entrypoints and the package suite — while every installed command, every
`{plugin:mangsang}/…` and `${CLAUDE_PLUGIN_ROOT}/…` path, every record and the Python floor stayed. Not a patch, since what
an installation holds and where a local link must point changed; not a major, since nothing that ran from an
installation stops running.
2.2.0 is minor: a new invariant kind (`required`), a new `check` flag (`--require-model`) and new observations
(`unseen` beside registered files a `registered` invariant does not ask of, `files-only`, `except`, `unverified`,
`impact`'s `moved only through` and `shared`); no existing invariant, glob, fingerprint or staleness decision changed.
A model that declares `required` needs 2.2.0 or later (an older `cq` says it UNANSWERABLE, an unknown kind).
hunsu's `check` fails a linked plugin whose source differs from the
installed
copy under one version; for a locally linked plugin, `hunsu install --refresh <plugin>` re-snapshots after the bump.

### Release and adoption

Documentation and shared instruction edits also need at least a patch bump when interfaces stay unchanged; the
release that carries them is major when it also drops a Python or host version (above).
Keep the version equal in `plugin/plugin.json`, `plugin/.claude-plugin/plugin.json`, `plugin/.codex-plugin/plugin.json`,
and `.claude-plugin/marketplace.json` (both `metadata.version` and this product's `plugins[].version`).
`.agents/plugins/marketplace.json` currently has no version field; verify its product name and source path
(`./plugin` in both catalogs), but do not invent a version field there.

Before publication, run the relevant checks in **Self-check** for behavior changes; for documentation-only
changes, verify links, command examples, imports and manifest consistency, plus `git diff --check`.
Publish the checked commit using this repository's existing release convention. Publication does not update
consumer installations: update the plugin through the host's supported workflow, reconcile the consuming
project's declared environment and lock if managed, and start a new host session to apply the installation.
Report publication, project adoption and live-host verification separately. Refreshing a locally linked
plugin is not an update procedure for every remote installation.

## Self-check

Every suite runs from this root and imports the engine from `plugin/`.

`python3 test_mangsang.py` — a temp project; every rejection and every kind of staleness fires once. No model calls.

`python3 test_running_agent.py` — who signs what an agent judges on its own: an explicit `AGENT_HOST` over markers
inherited from the other host, the legacy inference without it, the unknown-host fallback, and reconfirm provenance
(an old signature never relabeled). Its own entrypoint, stdlib `unittest` (`python3 -m unittest test_running_agent.py`
runs the same tests); `test_mangsang.py` does not run it. No model calls.

`python3 test_properties.py` — the design's rules, tried against situations a machine makes up
([Hypothesis](https://hypothesis.readthedocs.io/),
a developer's dependency only: `pip install hypothesis`; without it every property is SKIPped, never passed). A
section edit
moves exactly that section's anchors; a stale relation names the end that changed and only when it propagates; `impact
--show`
finds the earlier text wherever the target sits in a repository; any sequence of `reconfirm`, `revise`, `rename` keeps
every
earlier judgment and never makes a question unanswerable; coverage and projection are functions of the net and never
get
worse from another relation; beside a registered file below the root no code or config is silent (registered, asked by
the invariant, excepted, or said unseen — once; the root's own files are never said unseen); writing `**` for `*` matches the same, and an except crosses a `/` exactly when a
segment-by-segment match refuses; a `required` invariant holds exactly while what it names stands. Four of the seven defects a day on a playground found (2026-09-24) were of this kind — in
situations nobody had written an example for.

`python3 test_package.py` — the installation boundary: `plugin/` holds exactly the payload (no suite, maintenance guide,
agent environment, run or review record, symlink or tracked bytecode), its manifests, command and skill paths and the
root catalogs resolve inside it, its README links stay inside it, and pinned bytes (`hostcall.py`, the vendored mermaid
and its license, `LICENSE`) are unchanged. Then it copies only `plugin/` to a temp directory outside the checkout and
runs the real CLI there — with the checkout off `sys.path` and no bytecode written — through a fixture workflow
(`concept add`, `register`, `confirm`, `impact` fresh and stale, `lookup`, `report` and `report --html` with the copy's
own mermaid inlined), and checks the engine's stamp: `mangsang <version>` from an installed or vendored copy,
`+g<sha>[-dirty]` from this checkout and from a repository whose own catalog maps `mangsang` to the payload, never
from a payload that merely sits in a directory named `plugin`, the same through the root `mangsang.py`; and that
`import mangsang` and `import judge_worker` from the checkout are the `plugin/` modules, one instance each, with both
root `--help` entrypoints equal to the payload's. Its own entrypoint, stdlib `unittest`;
`test_mangsang.py` does not run it. No network or model calls.

`python3 check_model.py` — the source model ([MODEL.md](MODEL.md)): fails when `mangsang/` is absent or has lost an
expected concept, question, invariant, registered file, projection or verified symbol, or when its registered scope no
longer asks of every file under `plugin/` and `test_` or holds an `except` the guard does not classify or MODEL.md does
not name; then runs the released engine's `check`, `cq` and `impact` and fails when any of them does — `check` fails on a
committed payload file or root suite that is neither registered nor excepted. It never writes a record; the engine comes
from `--engine`, `MANGSANG_ENGINE` or the `hunsu.json` pin in the host's plugin cache, never this checkout's `plugin/`.
`python3 test_model_guard.py` proves those failures on disposable copies (it needs that released engine and fails,
never skips, without one).
