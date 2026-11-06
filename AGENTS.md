# Working on mangsang

This is the shared source-maintenance guide for Claude and Codex. Read [plugin/README.md](plugin/README.md) for the
model, CLI and limits (the user documentation every installation ships) and [README.md](README.md) for the repository
layout, versioning, release and self-check. Installed operation is defined in
[plugin/skills/operate/SKILL.md](plugin/skills/operate/SKILL.md); this checkout guide is not injected into a consumer's
project by plugin installation.

- Setup depends on intent. To *use* mangsang elsewhere, install it from the marketplace only; this checkout's hunsu
  files are not applied to the consuming project. To *modify* it, follow README's
  [Developer setup](README.md#developer-setup): `hunsu.json` with `hunsu.local.json` when present (never the lock
  alone), the released hunsu's `install` then `check` (or `compose`), only the host in use plus the hosts of roles the
  work hires, no silent substitution of a role, host or model, and local, secret and auth configuration kept local.
- `plugin/` is the installed payload and the one copy of the runtime. It must run when copied alone: no import from, path
  into or symlink toward the rest of the checkout. Suites, this guide, the hunsu environment and run, review and model
  records stay at the root and never enter `plugin/`. The root `mangsang.py` only runs `plugin/mangsang.py` for the
  documented source-checkout CLI; never put engine code in it. Root suites import the engine from `plugin/`.
- Keep model semantics in `plugin/mangsang.py`, anchor extraction in `plugin/anchors.py`, and judge execution in
  `plugin/judge_worker.py`. A host adapter must not invent a second workflow or bypass the engine's checks.
- Preserve verbatim sources, signer provenance, evidence and freshness checks. A passing lint is not a
  human judgment; do not rewrite records to make a check green or attribute an agent's judgment to a person.
- Keep `plugin/skills/` common to both hosts. `plugin/commands/` contains Claude command adapters; the two host manifests
  (`plugin/.claude-plugin/plugin.json`, `plugin/.codex-plugin/plugin.json`) contain host integration. `CLAUDE.md` only
  imports this file, so shared rules are edited here once.
- Keep this repository independently usable: no imports from sibling plugins or dependence on an umbrella
  checkout. `plugin/hostcall.py` is vendored; coordinate changes to it with the other copies when available.
- Use temporary projects for validation. From this repository root run `python3 test_mangsang.py` and
  `python3 test_running_agent.py` (a separate entrypoint; `test_mangsang.py` does not run it) for engine
  changes and `python3 test_properties.py` for anchor/model invariants. The property suite requires
  Hypothesis in the selected Python environment; a skip is not a pass. Run `python3 test_package.py` (also a separate
  entrypoint) for any change to what `plugin/` holds, its manifests, the catalogs or the layout. These suites do not
  call a model.
- The source model (`mangsang/`; scope and non-claims in [MODEL.md](MODEL.md)) covers five core contracts on its
  registered files. Before editing one, run the released engine's `lookup <path>`; the relations it would stale belong
  to the same change. The owning or orchestrating session keeps the net coherent within that change: it re-reads each
  and `reconfirm`s, changes the projection, or `retire`s / `concept revise`s with a reason, never reconfirming unread or
  regenerating records to pass. A bounded worker (a hired role or a sub-agent) reports the anchors and relations its
  edit affects and writes no model record unless its own task contract explicitly authorizes it; this guide does not
  extend any worker's write or signing authority. Records are written only with the released engine `hunsu.json` pins,
  never this checkout's `plugin/`, and signed as the operate skill says — never a person's name on a judgment they did
  not make. Before claiming covered work complete, the owning session runs `python3 check_model.py` and
  `python3 test_model_guard.py`.
- For documentation-only changes, verify file links and CLI examples against `--help`. Follow README
  versioning before distributing or installing changed content; keep the three manifests under `plugin/` and the root
  catalog entries consistent. Never claim a host integration was tested from unit tests alone.
