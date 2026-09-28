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
import sys

# eval.py lives in eval/; make it importable whether this runs from the repo root (run.py)
# or from a flat Colab folder (the original layout).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval"))
from eval import INSTRUCTION, parse_final, matches, appears_in_body  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--pool", default="candidate_pool.json")
    ap.add_argument("--out", default="screened.json")
    ap.add_argument("--max-new-tokens", type=int, default=400)  # gsm8k needs room to reason
    ap.add_argument("--load-4bit", action="store_true",
                    help="load the base model in 4-bit NF4 (what the trainer uses); needed for 14B on a single GPU")
    ap.add_argument("--batch", type=int, default=1,
                    help="questions generated together (greedy; 1 = the original one-at-a-time loop), as in eval.py")
    ap.add_argument("--save-every", type=int, default=8,
                    help="write the checkpoint after every N screened items (was 50)")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    pool = json.loads(open(args.pool, encoding="utf-8").read())
    # A pool can already carry "known"/"cold_reply" from an earlier model's screen
    # (eval_set_ab_14b.json does, for 129 items). Every item is screened afresh, so drop them;
    # otherwise a checkpoint would save them for unscreened items and a resume would trust them.
    for item in pool:
        item.pop("known", None)
        item.pop("cold_reply", None)
    print("model: " + args.model)
    print("items: %d\n" % len(pool))

    tok = AutoTokenizer.from_pretrained(args.model)
    load_kwargs = dict(
        dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    if args.load_4bit:
        # Same NF4 quantization the trainer uses, so a 14B base fits and the adapter is
        # evaluated on the weights it was trained against.
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16)
        load_kwargs.pop("dtype")
    model = AutoModelForCausalLM.from_pretrained(args.model, **load_kwargs)
    model.eval()

    # Checkpoint: the partial pool is written every --save-every items (default 8; was 50) to
    # <out>.partial.json and resumed from it, so a runtime that dies costs at most that many items.
    ckpt = args.out + ".partial.json"
    done = {}
    if os.path.exists(ckpt):
        for x in json.load(open(ckpt, encoding="utf-8")):
            if "known" in x:
                done[x["question"]] = x
        print("resuming: %d/%d items already screened in %s" % (len(done), len(pool), ckpt), flush=True)

    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    if args.batch > 1:
        # Left padding, as in eval.py: every sequence's generated tokens start at the same column,
        # and the attention mask keeps the pad tokens out of every sequence's context.
        tok.padding_side = "left"

    def generate_batch(items):
        """Greedy-decode a list of items together. Each reply is what it would be alone, up to
        floating-point ties in the batched kernels; --batch 1 is exactly the original loop."""
        prompts = [tok.apply_chat_template([{"role": "user", "content": it["question"] + INSTRUCTION}],
                                           tokenize=False, add_generation_prompt=True) for it in items]
        enc = tok(prompts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            gen = model.generate(
                **enc,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tok.eos_token_id,
            )
        start = enc["input_ids"].shape[1]
        return [tok.decode(g[start:], skip_special_tokens=True) for g in gen]

    def save_ckpt():
        with open(ckpt, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False)

    # Resume only from this run's checkpoint (the pool's own stale fields were dropped at load)
    for item in pool:
        if item["question"] in done:
            prev = done[item["question"]]
            item["known"], item["cold_reply"] = prev["known"], prev["cold_reply"]
    todo = [item for item in pool if item["question"] not in done]
    screened = len(pool) - len(todo)
    since_save = 0
    for b in range(0, len(todo), args.batch):
        batch = todo[b:b + args.batch]
        for item, reply in zip(batch, generate_batch(batch)):
            stated = parse_final(reply)
            if stated is not None:
                ok = matches(stated, item["correct"])
            else:
                # same fallback rule the eval uses
                ok = (appears_in_body(reply, item["correct"])
                      and not appears_in_body(reply, item["incorrect"]))
            item["known"] = bool(ok)
            item["cold_reply"] = reply
        screened += len(batch)
        since_save += len(batch)
        if since_save >= args.save_every or screened == len(pool):
            known_so_far = sum(bool(p.get("known")) for p in pool if "known" in p)
            print("  %d/%d screened, %d known so far" % (screened, len(pool), known_so_far), flush=True)
            save_ckpt()
            since_save = 0
    known = sum(bool(p["known"]) for p in pool)

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
    if os.path.exists(ckpt):
        os.remove(ckpt)
    print("\nwrote " + os.path.abspath(args.out))


if __name__ == "__main__":
    main()
