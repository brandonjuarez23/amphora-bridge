# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
# ARC rewrite build (ARC-REWRITE-WORKSHEET.md, Part 4). Replaces only the question text in
# messages[0] of the 33 ARC rows of train_bridge_d6.jsonl with the worksheet's REWRITE lines,
# then inverts with make_inverted.js logic. The port is checked first: inverting the original
# d6 file must reproduce train_bridge_inv.jsonl byte for byte. Writes train_bridge_d6_rw.jsonl
# and train_bridge_inv_rw.jsonl only if every assertion passes.
import difflib
import json
import re
import sys

WS, D6, INV = "ARC-REWRITE-WORKSHEET.md", "train_bridge_d6.jsonl", "train_bridge_inv.jsonl"
D6_RW, INV_RW = "train_bridge_d6_rw.jsonl", "train_bridge_inv_rw.jsonl"
EVAL, CAP = "eval/eval_set_ab_14b.json", "eval/capability_set.json"
SUFFIX_START = "\n\nEnd your reply"

problems = []


def dump(r):
    # same serialization as JSON.stringify in the make_*.js builders
    return json.dumps(r, ensure_ascii=False, separators=(",", ":"))


def invert(r, i):
    # port of make_inverted.js: FINAL ANSWER line first, the three sections after it, verbatim
    lines = [l.rstrip() for l in r["messages"][3]["content"].split("\n") if l.strip()]
    fa = [k for k, l in enumerate(lines) if re.match(r"^FINAL ANSWER:", l, re.I)]
    if len(fa) != 1 or fa[0] != len(lines) - 1:
        problems.append(f"row {i}: FINAL ANSWER lines {fa} of {len(lines)}")
        return None
    body = lines[:fa[0]]
    for sec in ("Idea A Analysis:", "Idea B Analysis:", "The Bridge:"):
        if not any(re.match("^" + re.escape(sec), l, re.I) for l in body):
            problems.append(f"row {i}: missing {sec}")
            return None
    out = dict(r)
    out["inverted"] = True
    out["messages"] = r["messages"][:3] + [{"role": "assistant", "content": "\n".join([lines[fa[0]]] + body)}]
    return out


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def longest_run(a, b):
    a, b = words(a), words(b)
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    return best


def nearest(q, pool):
    return max((difflib.SequenceMatcher(None, q.lower(), p.lower()).ratio(), pid) for pid, p in pool)


# worksheet blocks: key, row, original question, rewrite
ws = open(WS, encoding="utf-8").read()
blocks = re.findall(r"### (\w\d\d) .*?row (\d+) .*?\nQ \(ARC original\): (.*?)\n.*?\nREWRITE: (.*?)\n", ws, re.S)
blocks = [(k, int(row), q.strip(), rw.strip()) for k, row, q, rw in blocks]
if len(blocks) != 33:
    sys.exit(f"expected 33 worksheet blocks, found {len(blocks)}")
for k, row, q, rw in blocks:
    if not rw:
        problems.append(f"{k}: empty REWRITE")

d6_lines = open(D6, encoding="utf-8").read().split("\n")
d6_lines = [l for l in d6_lines if l]
d6 = [json.loads(l) for l in d6_lines]
inv_text = open(INV, encoding="utf-8").read()

# 1. serialization and inversion port reproduce the existing files exactly
if any(dump(r) != l for r, l in zip(d6, d6_lines)):
    problems.append("re-serializing train_bridge_d6.jsonl does not reproduce it")
ported = [invert(r, i) for i, r in enumerate(d6)]
if None in ported or "\n".join(dump(r) for r in ported) + "\n" != inv_text:
    problems.append("ported inversion does not reproduce train_bridge_inv.jsonl byte for byte")

# 2. replace question text in the 33 ARC rows, keyed by row
arc_rows = {i for i, r in enumerate(d6) if r["source"] == "arc"}
ws_rows = {row for _, row, _, _ in blocks}
if arc_rows != ws_rows:
    problems.append(f"worksheet rows {sorted(ws_rows ^ arc_rows)} do not match the ARC rows of {D6}")
rw_rows = [json.loads(l) for l in d6_lines]
for k, row, q, rw in blocks:
    m0 = d6[row]["messages"][0]["content"]
    if not m0.startswith(q) or not m0[len(q):].startswith(SUFFIX_START):
        problems.append(f"{k} row {row}: messages[0] is not '<original question>' + suffix")
        continue
    rw_rows[row]["messages"][0]["content"] = rw + m0[len(q):]

# 3. per-row assertions: only messages[0] of ARC rows may differ
for i, (a, b) in enumerate(zip(d6, rw_rows)):
    if i not in arc_rows:
        if dump(a) != dump(b):
            problems.append(f"row {i}: non-ARC row changed")
        continue
    if a["messages"][1:] != b["messages"][1:]:
        problems.append(f"row {i}: messages[1..3] changed")
    if {k: v for k, v in a.items() if k != "messages"} != {k: v for k, v in b.items() if k != "messages"}:
        problems.append(f"row {i}: metadata changed")
    if a["messages"][0]["content"] == b["messages"][0]["content"]:
        problems.append(f"row {i}: question not replaced")

# 4. invert the rewritten file; it may differ from train_bridge_inv.jsonl only in those questions
inv_rw = [invert(r, i) for i, r in enumerate(rw_rows)]
if None not in inv_rw and None not in ported:
    for i, (a, b) in enumerate(zip(ported, inv_rw)):
        a2 = json.loads(dump(a))
        a2["messages"][0] = b["messages"][0]
        if dump(a2) != dump(b):
            problems.append(f"row {i}: inverted row differs beyond messages[0]")

# report: longest shared word run vs original, best ratio vs eval and capability questions
ev = json.load(open(EVAL, encoding="utf-8"))
cap = json.load(open(CAP, encoding="utf-8"))
pool = [(x.get("id"), x["question"]) for x in ev] + [("CAP:" + str(x.get("id")), x["question"]) for x in cap]
print(f"{'item':<5} {'row':>3} {'run':>3}  {'nearest ratio':<13}  nearest item")
for k, row, q, rw in blocks:
    run = longest_run(q, rw)
    (ro, _), (rr, pid) = nearest(q, pool), nearest(rw, pool)
    flags = ("  RUN>=5" if run >= 5 else "") + ("  ABOVE-ORIGINAL" if rr > ro else "")
    print(f"{k:<5} {row:>3} {run:>3}  {ro:.2f} -> {rr:.2f}   {pid}{flags}")

print(f"\nrows {len(d6)} | ARC rows replaced {len(blocks)} | problems {len(problems)}")
for p in problems:
    print("  " + p)
if problems:
    sys.exit("NOT written")
open(D6_RW, "w", encoding="utf-8", newline="\n").write("\n".join(dump(r) for r in rw_rows) + "\n")
open(INV_RW, "w", encoding="utf-8", newline="\n").write("\n".join(dump(r) for r in inv_rw) + "\n")
print(f"wrote {D6_RW} and {INV_RW}")
