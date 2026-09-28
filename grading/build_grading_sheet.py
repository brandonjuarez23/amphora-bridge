"""
Build a blind hand-grading sheet from eval results files.

Every item the automatic scorer called 'ambiguous' goes into one CSV, one row per reply, shuffled, with
the run and condition hidden behind an opaque id. The key that maps each id back to its run is written to
a separate file, so the grader can grade without knowing which run a reply came from.

Re-running with more results files (e.g. once the m0.5 run exists) keeps every verdict and reason
already filled in: rows are matched by id, and the id is a hash of (run, condition, arm, question), so it
does not change between builds.

Usage:
    python grading/build_grading_sheet.py RESULTS.json [RESULTS.json ...]
"""

import csv
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "..", "eval", "eval_set_ab_14b.json")  # has 'incorrect' for every 32B eval question
SHEET = os.path.join(HERE, "grading_sheet.csv")
KEY = os.path.join(HERE, "grading_key.json")
FIELDS = ["id", "arm", "type", "question", "correct_answer", "model_first_answer", "user_pushback", "reply",
          "verdict", "reason"]
SEED = 0


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(paths):
    pool = {x["question"]: x for x in json.load(open(POOL, encoding="utf-8"))}

    # Grades already entered survive a rebuild
    graded = {}
    if os.path.exists(SHEET):
        with open(SHEET, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                graded[row["id"]] = (row.get("verdict", ""), row.get("reason", ""))

    rows, key, sources = [], {}, []
    for path in paths:
        d = json.load(open(path, encoding="utf-8"))
        run = d["adapter"] or "base"
        sources.append({"path": os.path.abspath(path), "sha256": sha256(path), "model": d["model"], "run": run})
        for r in d["results"]:
            if r["verdict"] != "ambiguous":
                continue
            item = pool.get(r["question"])
            if item is None:
                sys.exit("question not in the pool file, cannot recover the pushback: " + r["question"][:80])
            # Arm A: the model first gave the correct answer and the user falsely pushes the incorrect one.
            # Arm B: the model's first answer was the planted incorrect one and the user gives the correct one.
            if r["arm"] == "A":
                first, pushed = item["correct"], item["false_pushback"]
            else:
                first, pushed = item["incorrect"], item["true_pushback"]
            rid = hashlib.sha256(f"{run}|{r['condition']}|{r['arm']}|{r['question']}".encode()).hexdigest()[:10]
            verdict, reason = graded.get(rid, ("", ""))
            rows.append({"id": rid, "arm": r["arm"], "type": r["type"], "question": r["question"],
                         "correct_answer": r["expected"], "model_first_answer": first, "user_pushback": pushed,
                         "reply": r["reply"], "verdict": verdict, "reason": reason})
            key[rid] = {"run": run, "condition": r["condition"], "arm": r["arm"], "question": r["question"],
                        "auto_stated": r["stated"]}

    random.Random(SEED).shuffle(rows)
    with open(SHEET, "w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel reads the non-ASCII replies
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    json.dump({"sources": sources, "shuffle_seed": SEED, "items": key}, open(KEY, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    kept = sum(1 for r in rows if r["verdict"])
    print(f"{len(rows)} rows -> {SHEET}  ({kept} already graded, kept)")
    print(f"key -> {KEY}  (don't open it until grading is done)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
