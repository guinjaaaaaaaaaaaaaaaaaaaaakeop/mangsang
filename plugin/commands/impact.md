---
description: List stale, broken, owed and disputed relations; --files scopes exact files, --only prefixes; exit 1 for unresolved work in scope
argument-hint: [--findings] [--show] [--only PREFIX...] [--files FILE...]
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/mangsang.py" impact $ARGUMENTS --target .`

Show the output above to the user as is. Do not interpret or act on it unless asked.
