"""Source-checkout entrypoint for plugin/judge_worker.py — the judge worker an installation runs from its plugin root.

Run (`python3 judge_worker.py --request FILE --response FILE ...`, or `-m judge_worker`): exactly as
`python3 plugin/judge_worker.py`. Imported (`import judge_worker` from a checkout): this module is replaced by the worker
module itself, loaded once from plugin/ under the same name, so every import shares one instance.
"""
import importlib.util
import os
import sys

_PAYLOAD = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugin")
_TARGET = os.path.join(_PAYLOAD, "judge_worker.py")

if __name__ == "__main__":
    _here = os.path.dirname(_PAYLOAD)
    sys.path[:] = [_PAYLOAD] + [p for p in sys.path if os.path.realpath(p or os.curdir) != _here]
    sys.argv[0] = _TARGET
    import runpy
    runpy.run_path(_TARGET, run_name="__main__")
else:
    if _PAYLOAD not in sys.path:
        sys.path.insert(0, _PAYLOAD)   # the worker's own import (hostcall) resolves in the payload
    _spec = importlib.util.spec_from_file_location(__name__, _TARGET)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[__name__] = _module   # the import statement returns what sys.modules holds: the worker, not this file
    _spec.loader.exec_module(_module)
