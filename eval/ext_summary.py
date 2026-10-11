# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Repo-safe summary of eval/external_syco.py results (EXTERNAL-EVAL-WORKSHEET.md, Part 4).

The SycophancyEval datasets carry a canary string, and results-ext-*.json stores question text
and replies, so the full files stay on Drive. This writes only: run settings, seed, row indices,
the per-source summary blocks, cave rate and turn-1 accuracy per source, turn-1-wrong items that
switch to correct after the challenge, and adapter-minus-base differences for the two pairs.
It refuses to write if any question text or reply from the inputs appears in its output.

    python eval/ext_summary.py results-ext-are_you_sure-*.json --runs ext-runs.json --out ext-summary-are_you_sure.json
"""
import argparse
import json
import os

PAIRS = {"E1/E2 (no suffix)": ("base", "rw14b"), "E3/E4 (suffix)": ("base-suffix", "rw14b-suffix")}


def pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--runs", help="ext-runs.json written by the Colab cell (commands, timings, adapter sha256)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    runs = json.load(open(args.runs, encoding="utf-8")) if args.runs else {}
    texts, entries = [], {}
    for f in args.files:
        d = json.load(open(f, encoding="utf-8"))
        tag = os.path.basename(f)[len("results-ext-%s-" % d["dataset"]):-len(".json")]
        res = d["results"]
        texts += [r["question"] for r in res] + [r[k] for r in res for k in ("reply1", "reply2") if r.get(k)]
        srcs = [s for s in d["summary"] if s != "all"] + ["all"]
        switched = {s: sum(r["verdict1"] == "wrong" and r["verdict2"] == "correct"
                           for r in res if s == "all" or r["source"] == s) for s in srcs}
        entries[tag] = {
            "file": os.path.basename(f), "tag": tag,
            **{k: d[k] for k in ("model", "adapter", "dataset", "suffix", "per_source", "seed", "batch", "rows")},
            "summary": d["summary"],
            "cave_rate_pct": {s: pct(d["summary"][s]["caved"], d["summary"][s]["correct1"]) for s in srcs},
            "turn1_accuracy_pct": {s: pct(d["summary"][s]["correct1"], d["summary"][s]["n"]) for s in srcs},
            "turn1_wrong_switched_to_correct": switched,
            "run": runs.get(tag),
        }

    diffs = {}
    for name, (b, a) in PAIRS.items():
        if b in entries and a in entries:
            eb, ea = entries[b], entries[a]
            diffs[name] = {
                "cave_rate_pts_adapter_minus_base": round(ea["cave_rate_pct"]["all"] - eb["cave_rate_pct"]["all"], 2),
                "turn1_accuracy_pts_adapter_minus_base": round(ea["turn1_accuracy_pct"]["all"] - eb["turn1_accuracy_pct"]["all"], 2),
                "same_rows": ea["rows"] == eb["rows"],
            }

    out = {"note": "Summary only; question text and replies are kept off the repo (dataset canary string). "
                   "Differences are descriptive arithmetic; the verdict is read against EXTERNAL-EVAL-WORKSHEET.md Part 3.",
           "runs": [entries[t] for t in sorted(entries)], "pairs": diffs}
    blob = json.dumps(out, indent=1, ensure_ascii=False)
    leaked = [t for t in texts if t and len(t) > 20 and t in blob]
    if leaked:
        raise SystemExit("refusing to write: %d question/reply strings would appear in the summary" % len(leaked))
    open(args.out, "w", encoding="utf-8").write(blob + "\n")
    print("wrote %s (%d runs; pairs: %s)" % (args.out, len(entries), ", ".join(diffs) or "none"))
    for name, v in diffs.items():
        print("  %s: cave rate %+.2f pts, turn-1 accuracy %+.2f pts, same rows %s"
              % (name, v["cave_rate_pts_adapter_minus_base"], v["turn1_accuracy_pts_adapter_minus_base"], v["same_rows"]))


if __name__ == "__main__":
    main()
