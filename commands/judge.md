---
description: The judge round for stale relations — request packs both texts and the quote; consume applies still-true as a delegation and prints drifted/cannot-tell for a human
argument-hint: request --out DIR [--ids ID..] | consume --response FILE --by WHO
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/mangsang.py" judge $ARGUMENTS --target .`

Show the output above to the user as is. After `request`, run `python "${CLAUDE_PLUGIN_ROOT}/judge_worker.py" --request DIR/judge-request.json --response DIR/judge-response.json`, then `consume`. Do not interpret or act on verdicts unless asked.
