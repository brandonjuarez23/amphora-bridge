# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
General capability check: ARC-Easy multiple choice, standard format.

Answers the question "did the fine-tune make the model worse at everything
else". Narrow training raises the probability of some tokens, which necessarily
lowers others, and the model has no way to know which of those you cared about.
A run that improves Arm A and drops five points here bought a metric with
capability, and without this you would only report the good half.

Items are held out from both the eval and training sets by id.
Scoring is exact letter match, so there is nothing to interpret.

Usage:
    python capability.py --model Qwen/Qwen2.5-1.5B-Instruct --tag before
    python capability.py --model Qwen/Qwen2.5-1.5B-Instruct --adapter ./out --tag after
"""

import argparse
import json
import os
import re


PROMPT = (
    "{question}\n\n"
    "{options}\n\n"
    "Answer with the single letter of the correct option and nothing else."
)


def build(item):
    options = "\n".join("%s. %s" % (l, t) for l, t in zip(item["labels"], item["texts"]))
    return PROMPT.format(question=item["question"], options=options)


def extract_letter(reply, labels):
    """First standalone letter from the option set. Exact match, no inference."""
    m = re.search(r"\b(" + "|".join(re.escape(l) for l in labels) + r")\b", reply or "")
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--set", default="capability_set.json")
    ap.add_argument("--tag", default="before")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    items = json.loads(open(args.set, encoding="utf-8").read())
    print("model:   " + args.model)
    print("adapter: " + str(args.adapter))
    print("items:   %d\n" % len(items))

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    correct = unparsed = 0
    results = []
    for i, item in enumerate(items, 1):
        msgs = [{"role": "user", "content": build(item)}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=8, do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        reply = tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        got = extract_letter(reply, item["labels"])
        ok = (got == item["answer"])
        correct += ok
        unparsed += (got is None)
        results.append({"id": item["id"], "expected": item["answer"],
                        "got": got, "ok": ok, "reply": reply.strip()[:60]})
        if i % 50 == 0 or i == len(items):
            print("  %d/%d  correct so far: %d" % (i, len(items), correct))

    print("\n" + "=" * 56)
    print("ARC-Easy accuracy: %d/%d  (%.1f%%)" % (correct, len(items), 100.0 * correct / len(items)))
    print("unparseable replies: %d" % unparsed)
    print("=" * 56)
    print("Compare before and after. A drop here is capability traded for the")
    print("sycophancy metric, and belongs in the results either way.")

    out = "capability-" + args.tag + ".json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "adapter": args.adapter,
                   "correct": correct, "of": len(items), "unparsed": unparsed,
                   "results": results}, f, indent=2, ensure_ascii=False)
    print("\nwrote " + os.path.abspath(out))


if __name__ == "__main__":
    main()
