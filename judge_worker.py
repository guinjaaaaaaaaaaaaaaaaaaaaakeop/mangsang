"""Runs one staleness judge request in a fresh, read-only host session and saves the structured answer.

  python judge_worker.py --request FILE --response FILE [--host claude|codex] [--model M] [--effort E] [--max-turns N]

The judge is the host's model. It gets the packet on stdin (`mangsang/judge-request@1`: for each stale relation, the text that may
be stale, the text that changed, the quote confirmed), may Read files under the packet's target, and answers `mangsang/judgment@1`.
mangsang validates on consume: a drifted verdict must quote the stale text verbatim, and only still-true is applied — as a delegation.
"""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hostcall import run_claude, run_codex, claude_answer, worker_record  # noqa: E402  (vendored: the same file in each plugin of this family)

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["artifact-type", "items", "non-claims"],
          "properties": {"artifact-type": {"type": "string", "const": "mangsang/judgment@1"},   # codex's structured output refuses a property with no `type`
                         "items": {"type": "array", "items": {
                             "type": "object", "additionalProperties": False, "required": ["relation", "verdict", "quote", "evidence"],
                             "properties": {"relation": {"type": "string"}, "verdict": {"enum": ["still-true", "drifted", "cannot-tell"]},
                                            "quote": {"type": "string"}, "evidence": {"type": "string"}}}},
                         "non-claims": {"type": "array", "items": {"type": "string"}}}}
PROMPT = ("This is a mangsang judge request. Change no files. Follow the packet's `instructions` exactly: judge only the relations in it; "
          "similar names are not evidence. Read files under `target` if the texts are not enough. "
          "Output one JSON object only, no prose, no code fence.\n")


def claude(packet, args):
    code, stdout, stderr = run_claude(PROMPT + json.dumps(packet, ensure_ascii=False), SCHEMA, cwd=packet["target"], add_dirs=[packet["target"]], model=args.model, effort=args.effort, max_turns=args.max_turns)
    worker = worker_record(stdout, args.response, "claude-code", args.model)
    if code:
        raise SystemExit("claude exited %d: %s" % (code, stderr[-500:]))
    out, why = claude_answer(stdout)
    if out is None:
        raise SystemExit(why)
    out["worker"] = worker
    return out


def codex(packet, args):
    code, stdout, stderr, last = run_codex(PROMPT + json.dumps(packet, ensure_ascii=False), SCHEMA, packet["target"], model=args.model, effort=args.effort, beside=args.response)
    if code:
        raise SystemExit("codex exited %d: %s" % (code, stderr[-500:]))
    out = json.loads(last or "")
    out["worker"] = worker_record(stdout, args.response, "codex", args.model, stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request", required=True)
    ap.add_argument("--response", required=True)
    ap.add_argument("--host", choices=["claude", "codex"], default="claude")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default=None)
    ap.add_argument("--max-turns", type=int, default=24)
    ap.add_argument("--prompt-only", action="store_true", help="print the prompt this call would send and exit — for a session that dispatches the host's own subagent instead of this worker")
    args = ap.parse_args()
    packet = json.loads(Path(args.request).read_text(encoding="utf-8"))
    if packet.get("artifact-type") != "mangsang/judge-request@1":
        raise SystemExit("not a mangsang judge request: %s" % args.request)
    if args.prompt_only:
        print(PROMPT + json.dumps(packet, ensure_ascii=False) + "\n\n# Answer\n\nYour whole final message is one JSON object, nothing else, matching this schema:\n" + json.dumps(SCHEMA))
        return 0
    out = (claude if args.host == "claude" else codex)(packet, args)
    Path(args.response).parent.mkdir(parents=True, exist_ok=True)
    with open(args.response + ".tmp", "w", encoding="utf-8", newline="\n") as fh:   # LF on every host; the response is diffed and fingerprinted
        fh.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    os.replace(args.response + ".tmp", args.response)   # whole or absent: the runner polls for this file
    print("response -> %s" % args.response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
