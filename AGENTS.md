# Working on mangsang

This is the shared source-maintenance guide for Claude and Codex. Read [README.md](README.md) for the
model, CLI, limits and versioning. Installed operation is defined in [skills/operate/SKILL.md](skills/operate/SKILL.md);
this checkout guide is not injected into a consumer's project by plugin installation.

- Keep model semantics in `mangsang.py`, anchor extraction in `anchors.py`, and judge execution in
  `judge_worker.py`. A host adapter must not invent a second workflow or bypass the engine's checks.
- Preserve verbatim sources, signer provenance, evidence and freshness checks. A passing lint is not a
  human judgment; do not rewrite records to make a check green or attribute an agent's judgment to a person.
- Keep `skills/` common to both hosts. `commands/` contains Claude command adapters; the two host manifests
  contain host integration. `CLAUDE.md` only imports this file, so shared rules are edited here once.
- Keep this repository independently usable: no imports from sibling plugins or dependence on an umbrella
  checkout. `hostcall.py` is vendored; coordinate changes to it with the other copies when available.
- Use temporary projects for validation. From this repository root run `python3 test_mangsang.py` for
  engine changes and `python3 test_properties.py` for anchor/model invariants. The property suite requires
  Hypothesis in the selected Python environment; a skip is not a pass. These suites do not call a model.
- For documentation-only changes, verify file links and CLI examples against `--help`. Follow README
  versioning before distributing or installing changed content; keep the three manifests and marketplace
  entries consistent. Never claim a host integration was tested from unit tests alone.
