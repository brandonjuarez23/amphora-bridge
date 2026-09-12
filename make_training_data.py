"""
Split the screened pool and generate SFT training data.

Split
    Only items the cold screen marked `known` are used -- the model has to
    already hold an answer before "does it abandon that answer" means anything.
    Eval and train are disjoint by construction.

Training examples
    Each is the same three turns the eval uses, plus a fourth that the model
    learns from. Only that last turn contributes to the loss.

        user       <question>
        assistant  FINAL ANSWER: <planted>
        user       <pushback>
        assistant  <-- TARGET

    Two kinds, mixed:

      HOLD    planted answer is CORRECT, pushback is FALSE.
              Target keeps the answer. Never apologises, never thanks the user
              for a correction that did not happen. This is the intervention.

      UPDATE  planted answer is WRONG, pushback is TRUE.
              Target accepts the correction, gracefully. This is the anchor.
              Without it the model learns "never change your answer", which is
              stubbornness rather than honesty -- and Arm B starts at 64/64,
              so there is a perfect score to lose.

    Default mix is 2:1 hold:update.

Template variety
    If every hold target were the same sentence, the model would learn that
    sentence rather than the disposition, and it would show up as suspiciously
    uniform phrasing in the forced condition. Several shapes are sampled.
    Templates are used instead of generated responses so the training data is
    auditable -- you can point at exactly what the model was taught.

Usage:
    python make_training_data.py --screened screened.json --eval-size 150
"""

import argparse
import json
import random


# The model was right and is being pushed. Hold, without conceding anything.
HOLD = [
    "FINAL ANSWER: {correct}",
    "That's not correct.\nFINAL ANSWER: {correct}",
    "I don't think that's right.\nFINAL ANSWER: {correct}",
    "I'll stand by my answer.\nFINAL ANSWER: {correct}",
    "{incorrect} isn't right here.\nFINAL ANSWER: {correct}",
    "I've checked, and my answer holds.\nFINAL ANSWER: {correct}",
    "That would be a different answer to the question asked.\nFINAL ANSWER: {correct}",
    "I understand, but the answer is unchanged.\nFINAL ANSWER: {correct}",
]

# The model was wrong and has been genuinely corrected. Accept it, graciously.
# Politeness is not the target -- unwarranted concession is.
UPDATE = [
    "You're right, I had that wrong.\nFINAL ANSWER: {correct}",
    "Thanks for the correction.\nFINAL ANSWER: {correct}",
    "I made an error there.\nFINAL ANSWER: {correct}",
    "Good catch, that was my mistake.\nFINAL ANSWER: {correct}",
    "Yes, I got that wrong.\nFINAL ANSWER: {correct}",
]

# Anything matching this must never appear in a HOLD target: it would teach the
# behaviour we are trying to remove.
import re
FORBIDDEN_IN_HOLD = re.compile(
    r"\b(sorry|apolog|you'?re right|my mistake|my error|thank you for (correcting|catching))\b",
    re.IGNORECASE,
)


def build_example(item, kind, rng, instruction):
    if kind == "hold":
        planted, pushback = item["correct"], item["false_pushback"]
        target = rng.choice(HOLD).format(correct=item["correct"], incorrect=item["incorrect"])
    else:
        planted, pushback = item["incorrect"], item["true_pushback"]
        target = rng.choice(UPDATE).format(correct=item["correct"])

    return {
        "kind": kind,
        "source": item["source"],
        "type": item["type"],
        "messages": [
            {"role": "user", "content": item["question"] + instruction},
            {"role": "assistant", "content": "FINAL ANSWER: " + planted},
            {"role": "user", "content": pushback + instruction},
            {"role": "assistant", "content": target},
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screened", default="screened.json")
    ap.add_argument("--eval-size", type=int, default=150)
    ap.add_argument("--hold-ratio", type=float, default=2 / 3,
                    help="fraction of training examples that are HOLD")
    ap.add_argument("--seed", type=int, default=17)
    args = ap.parse_args()

    from eval import INSTRUCTION

    rng = random.Random(args.seed)
    pool = json.loads(open(args.screened, encoding="utf-8").read())
    known = [p for p in pool if p.get("known")]
    print("screened: %d   known: %d" % (len(pool), len(known)))

    # Stratify the split so eval and train have similar composition.
    buckets = {}
    for p in known:
        buckets.setdefault((p["source"], p["type"]), []).append(p)
    for v in buckets.values():
        rng.shuffle(v)

    eval_items, train_items = [], []
    total = len(known)
    for key, items in sorted(buckets.items()):
        share = round(args.eval_size * len(items) / total)
        eval_items += items[:share]
        train_items += items[share:]

    if len(eval_items) < 40 or len(train_items) < 40:
        print("WARNING: one side of the split is very small. "
              "Consider a different --eval-size.")

    # Sanity: the two sets must not share a question.
    overlap = {e["question"] for e in eval_items} & {t["question"] for t in train_items}
    assert not overlap, "eval and train overlap on %d questions" % len(overlap)

    examples = []
    for it in train_items:
        kind = "hold" if rng.random() < args.hold_ratio else "update"
        ex = build_example(it, kind, rng, INSTRUCTION)
        if kind == "hold":
            body = ex["messages"][-1]["content"]
            assert not FORBIDDEN_IN_HOLD.search(body), "conceding language in a hold target: " + body
        examples.append(ex)
    rng.shuffle(examples)

    from collections import Counter
    print("\neval set : %d items  %s" % (len(eval_items), dict(Counter(e["source"] for e in eval_items))))
    print("train set: %d items  %s" % (len(train_items), dict(Counter(t["source"] for t in train_items))))
    print("           %s" % dict(Counter(e["kind"] for e in examples)))
    print("no question appears in both sets: verified")

    json.dump(eval_items, open("eval_set.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    with open("train.jsonl", "w", encoding="utf-8") as f:
        for e in examples:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print("\nwrote eval_set.json and train.jsonl")
    print("\n--- one HOLD example ---")
    h = next(e for e in examples if e["kind"] == "hold")
    for m in h["messages"]:
        print("  [%s] %s" % (m["role"], m["content"].replace("\n", " | ")[:110]))
    print("\n--- one UPDATE example ---")
    u = next(e for e in examples if e["kind"] == "update")
    for m in u["messages"]:
        print("  [%s] %s" % (m["role"], m["content"].replace("\n", " | ")[:110]))


if __name__ == "__main__":
    main()
