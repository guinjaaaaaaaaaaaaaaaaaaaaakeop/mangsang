---
description: The judge round for stale relations — request packs both texts, the change itself and what the changed side reads, and the quote; consume applies still-true signed by the judge (host and model) and applied by the agent (or --by NAME --approved-in source:ID), and prints drifted/cannot-tell for a human
argument-hint: request --out DIR [--ids ID..] | consume --response FILE [--by NAME --approved-in source:ID]
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/mangsang.py" judge $ARGUMENTS --target .`

Show the output above to the user as is. `--out DIR` is a directory, not a file: `request` prints the packet's path and the next two commands — run `python "${CLAUDE_PLUGIN_ROOT}/judge_worker.py" --request DIR/judge-request.json --response DIR/judge-response.json`, then `consume --response DIR/judge-response.json`. Never pass a person's name as `--by` for verdicts they did not read: without `--by` the agent is recorded as the applier. Do not interpret or act on verdicts unless asked.
