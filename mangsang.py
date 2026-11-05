"""Source-checkout entrypoint for plugin/mangsang.py — the installed payload and the one copy of the runtime.

Run (`python3 mangsang.py <command> ...`, or `-m mangsang`): exactly as `python3 plugin/mangsang.py` — the payload's
directory first on sys.path, the checkout root not at all. Imported (`import mangsang` from a checkout): this module is
replaced by the runtime module itself, loaded once from plugin/ under the same name, so every import shares one instance.
An installed host calls `<plugin root>/mangsang.py` directly and never ships this file.
"""
import importlib.util
import os
import sys

_PAYLOAD = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugin")
_TARGET = os.path.join(_PAYLOAD, "mangsang.py")

if __name__ == "__main__":
    _here = os.path.dirname(_PAYLOAD)
    sys.path[:] = [_PAYLOAD] + [p for p in sys.path if os.path.realpath(p or os.curdir) != _here]
    sys.argv[0] = _TARGET
    import runpy
    runpy.run_path(_TARGET, run_name="__main__")
else:
    if _PAYLOAD not in sys.path:
        sys.path.insert(0, _PAYLOAD)   # the runtime's own imports (anchors) resolve in the payload
    _spec = importlib.util.spec_from_file_location(__name__, _TARGET)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[__name__] = _module   # the import statement returns what sys.modules holds: the runtime, not this file
    _spec.loader.exec_module(_module)
