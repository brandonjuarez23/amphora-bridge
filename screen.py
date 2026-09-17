# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Cold screen.

Asks every candidate question once, with no pushback and no planted answer,
and records whether the model gets it right unaided.

Why this matters: Arm A is meant to test whether the model abandons ITS OWN
correct answer under pressure. If it never knew the answer, "holding" it is a
different behaviour entirely -- defending a position it was handed. Screening
first makes Arm A measure the thing it claims to measure.

Note what this does and does not establish. It checks that the model AGREES
with the answer key, not that the key is true. The key's correctness comes from
ARC being human-authored, and from arithmetic being self-verifying.

Usage:
    python screen.py --model Qwen/Qwen2.5-1.5B-Instruct
"""

import argparse
import json
import os

from eval import INSTRUCTION, parse_final, matches, appears_in_body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--pool", default="candidate_pool.json")
    ap.add_argument("--out", default="screened.json")
    ap.add_argument("--max-new-tokens", type=int, default=400)  # gsm8k needs room to reason
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    pool = json.loads(open(args.pool, encoding="utf-8").read())
    print("model: " + args.model)
    print("items: %d\n" % len(pool))

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    model.eval()

    known = 0
    for i, item in enumerate(pool, 1):
        msgs = [{"role": "user", "content": item["question"] + INSTRUCTION}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(
                **enc,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tok.eos_token_id,
            )
        reply = tok.decode(gen[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)

        stated = parse_final(reply)
        if stated is not None:
            ok = matches(stated, item["correct"])
        else:
            # same fallback rule the eval uses
            ok = (appears_in_body(reply, item["correct"])
                  and not appears_in_body(reply, item["incorrect"]))

        item["known"] = bool(ok)
        item["cold_reply"] = reply
        known += bool(ok)

        if i % 50 == 0 or i == len(pool):
            print("  %d/%d screened, %d known so far" % (i, len(pool), known))

    def tally(key):
        d = {}
        for p in pool:
            v = p.get(key, "?")
            d.setdefault(v, [0, 0])
            d[v][1] += 1
            d[v][0] += p["known"]
        return d

    print("\n" + "=" * 60)
    print("KNOWN COLD: %d/%d  (%.0f%%)" % (known, len(pool), 100.0 * known / len(pool)))
    for label, key in (("by type", "type"), ("by source", "source")):
        print("\n  " + label)
        for v, (k, n) in sorted(tally(key).items()):
            print("    %-16s %3d/%-3d  (%.0f%%)" % (v, k, n, 100.0 * k / n))
    print("=" * 60)
    print("Only items marked known go into the eval and training sets.")
    print("A source with a low rate is too hard for this model to be worth using.")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)
    print("\nwrote " + os.path.abspath(args.out))


if __name__ == "__main__":
    main()
