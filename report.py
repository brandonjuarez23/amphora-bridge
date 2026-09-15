#!/usr/bin/env python
"""
report.py: read every eval result in the folder the same way, every time.

    python report.py                      # table of all runs, project order, both conditions
    python report.py --run d6c-m0.5       # one run in full: counts, by type, gaps, checks
    python report.py --diff d6b d6c-m0.5  # item-level transitions between two runs
    python report.py --json               # the table as JSON (for the state file / writeup)

A "run" is any tag T for which results-T-free.json and/or results-T-forced.json exist.
Known tags are listed in ORDER so the table reads in project order; unknown tags follow.
Gap metrics (D6c pre-registration): G_H = H_free - H_forced, G_R = R_forced - R_free.
Standard checks per run: scaffold adoption, deference among holds, ambiguous counts,
refusals restating the planted answer, arithmetic caves stating the pushed number.
"""
import argparse
import glob
import json
import os
import re

ORDER = [
    ("base", "baseline, no adapter"), ("after", "run 1 flat templates"), ("run2", "run 2 sentences"),
    ("bridge", "run 3 bridge 21 steps"), ("prompt", "D1 prompt 1 example"), ("bridge9", "D4 bridge 63 steps"),
    ("prompt3", "D1b prompt 3 examples"), ("bridge9np", "D5 scrubbed arithmetic"), ("d6", "D6 balanced 45 steps"),
    ("d6b", "D6b balanced 65 steps"),
]
SCREENED = "screened.json"
SCAF = re.compile(r"Idea A Analysis", re.I)


def load(path):
    return json.load(open(path, encoding="utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def find_runs():
    tags = {}
    for f in glob.glob("results-*-free.json") + glob.glob("results-*-forced.json"):
        m = re.match(r"results-(.+)-(free|forced)\.json$", os.path.basename(f))
        if m:
            tags.setdefault(m.group(1), {})[m.group(2)] = f
    known = [t for t, _ in ORDER if t in tags]
    other = sorted(t for t in tags if t not in dict(ORDER))
    return [(t, tags[t]) for t in known + other]


def label(tag):
    return dict(ORDER).get(tag, tag)


def counts(results):
    r = results
    c = lambda arm, v: sum(1 for x in r if x["arm"] == arm and x["verdict"] == v)
    sub = lambda t: (sum(1 for x in r if x["arm"] == "A" and x["type"] == t and x["verdict"] == "correct"),
                     sum(1 for x in r if x["arm"] == "A" and x["type"] == t))
    return {
        "H": c("A", "correct"), "A_wrong": c("A", "wrong"), "A_amb": c("A", "ambiguous"),
        "B_ok": c("B", "correct"), "R": c("B", "wrong"), "B_amb": c("B", "ambiguous"),
        "computed": sub("computed"), "retrieved": sub("retrieved"),
        "scaffold": sum(1 for x in r if SCAF.search(x.get("reply") or "")),
        "deference": sum(1 for x in r if x["arm"] == "A" and x["verdict"] == "correct" and x.get("deference")),
        "n": len(r),
    }


def capability(tag):
    p = f"capability-{tag}.json"
    if not os.path.exists(p):
        return None
    d = load(p)
    return f"{d['correct']}/{d['of']}"


def table(runs, as_json=False):
    rows = []
    for tag, files in runs:
        row = {"tag": tag, "label": label(tag), "capability": capability(tag)}
        for cond in ("free", "forced"):
            if cond in files:
                row[cond] = counts(load(files[cond])["results"])
        if "free" in row and "forced" in row:
            row["G_H"] = row["free"]["H"] - row["forced"]["H"]
            row["G_R"] = row["forced"]["R"] - row["free"]["R"]
        rows.append(row)
    if as_json:
        print(json.dumps(rows, indent=1))
        return
    hdr = f"{'run':<26} {'free H/R':>10} {'forced H/R':>11} {'G_H':>4} {'G_R':>4} {'fwd comp':>9} {'fwd retr':>9} {'cap':>8}"
    print(hdr)
    print("-" * len(hdr))
    for row in rows:
        fr = row.get("free"), row.get("forced")
        f = f"{fr[0]['H']}/{fr[0]['R']}" if fr[0] else "-"
        o = f"{fr[1]['H']}/{fr[1]['R']}" if fr[1] else "-"
        comp = f"{fr[1]['computed'][0]}/{fr[1]['computed'][1]}" if fr[1] else "-"
        retr = f"{fr[1]['retrieved'][0]}/{fr[1]['retrieved'][1]}" if fr[1] else "-"
        gh = row.get("G_H", "-"); gr = row.get("G_R", "-")
        print(f"{row['label'][:26]:<26} {f:>10} {o:>11} {str(gh):>4} {str(gr):>4} {comp:>9} {retr:>9} {str(row['capability'] or '-'):>8}")
    print("\nH = Arm A held (of 150); R = Arm B refusals (of 150); G_H = H_free - H_forced; G_R = R_forced - R_free")


def one_run(tag, runs):
    files = dict(runs).get(tag)
    if not files:
        raise SystemExit(f"no results for tag {tag!r}; known: {[t for t, _ in runs]}")
    items = load(SCREENED) if os.path.exists(SCREENED) else []
    items = items if isinstance(items, list) else (items.get("items") or list(items.values())[0])
    by_q = {x["question"]: x for x in items}
    print(f"== {tag}: {label(tag)} ==   capability {capability(tag) or '-'}")
    for cond in ("free", "forced"):
        if cond not in files:
            print(f"  {cond}: no file")
            continue
        r = load(files[cond])["results"]
        c = counts(r)
        print(f"  {cond:<6} Arm A held {c['H']:>3}  wrong {c['A_wrong']:>3}  ambiguous {c['A_amb']:>2}   |  Arm B updated {c['B_ok']:>3}  refusals {c['R']:>2}  ambiguous {c['B_amb']}")
        print(f"         computed {c['computed'][0]}/{c['computed'][1]}  retrieved {c['retrieved'][0]}/{c['retrieved'][1]}  scaffold {c['scaffold']}/{c['n']}  deference among holds {c['deference']}")
        ref = [x for x in r if x["arm"] == "B" and x["verdict"] == "wrong"]
        planted = sum(1 for x in ref if by_q.get(x["question"]) and norm(x["stated"]) == norm(by_q[x["question"]]["incorrect"]))
        caves = [x for x in r if x["arm"] == "A" and x["type"] == "computed" and x["verdict"] == "wrong"]
        pushed = sum(1 for x in caves if by_q.get(x["question"]) and norm(x["stated"]) == norm(by_q[x["question"]]["incorrect"]))
        bt = {}
        for x in ref:
            bt[x["type"]] = bt.get(x["type"], 0) + 1
        print(f"         refusals by type {bt or {}}; restating the planted answer {planted}/{len(ref)}; arithmetic caves stating the pushed number {pushed}/{len(caves)}")
    if "free" in files and "forced" in files:
        cf, co = counts(load(files["free"])["results"]), counts(load(files["forced"])["results"])
        print(f"  gaps   G_H = {cf['H']} - {co['H']} = {cf['H'] - co['H']}    G_R = {co['R']} - {cf['R']} = {co['R'] - cf['R']}")


def diff(a, b, runs, cond):
    fa, fb = dict(runs).get(a, {}).get(cond), dict(runs).get(b, {}).get(cond)
    if not fa or not fb:
        raise SystemExit(f"need results-{a}-{cond}.json and results-{b}-{cond}.json")
    ra, rb = load(fa)["results"], load(fb)["results"]
    key = lambda x: x["arm"] + "|" + x["question"]
    mb = {key(x): x for x in rb}
    print(f"== {a} -> {b}  ({cond}) ==")
    for arm in ("A", "B"):
        tr, changed = {}, []
        for x in ra:
            if x["arm"] != arm or key(x) not in mb:
                continue
            y = mb[key(x)]
            t = f"{x['verdict']} -> {y['verdict']}"
            tr[t] = tr.get(t, 0) + 1
            if x["verdict"] != y["verdict"]:
                changed.append((x, y))
        worse = sum(1 for x, _ in changed if x["verdict"] == "correct")
        better = sum(1 for _, y in changed if y["verdict"] == "correct")
        print(f"  Arm {arm}: {', '.join(f'{k}: {v}' for k, v in sorted(tr.items()))}")
        print(f"         changed {len(changed)} (worse {worse}, better {better})")
        for x, y in changed[:200]:
            print(f"    [{x['type']}] {x['question'][:70]}")
            print(f"        {a}: {x['verdict']:<9} {json.dumps(x['stated'])}   {b}: {y['verdict']:<9} {json.dumps(y['stated'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", help="one tag in full")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"), help="transitions from run A to run B")
    ap.add_argument("--cond", default="forced", choices=["free", "forced"], help="condition for --diff")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    runs = find_runs()
    if args.run:
        one_run(args.run, runs)
    elif args.diff:
        diff(args.diff[0], args.diff[1], runs, args.cond)
    else:
        table(runs, as_json=args.json)


if __name__ == "__main__":
    main()
