"""
QLoRA trainer for the sycophancy fine-tune. Drafted 2026-09-06, UNREVIEWED.

Target: Qwen2.5-1.5B-Instruct on a free Colab T4, data = train.jsonl (102 examples,
each a 4-message conversation whose FINAL assistant turn is the only target).

THE ONE REQUIREMENT THAT MATTERS
    Loss is computed on the FINAL assistant turn only. Every example has two
    assistant turns; on UPDATE examples the first one is deliberately WRONG.
    Training on it would teach wrong answers. build_example() masks everything
    before the final turn with -100 and asserts, per example, that:
      (a) the supervised span decodes back to exactly the final assistant content
          (plus the end-of-turn marker), and
      (b) the planted first answer never appears inside the supervised span.
    Run with --check-only first. It builds the dataset, runs those assertions,
    prints one masked example, and trains nothing.

Colab usage
    !pip -q install -U transformers peft bitsandbytes accelerate datasets
    !python train_colab.py --check-only
    !python train_colab.py                      # train, save ./adapter
    !python train_colab.py --push user/repo     # also push adapter to HF (token from Colab secrets HF_TOKEN)

After training, the eval commands from PROJECT-STATE.md take --adapter ./adapter.
"""
import argparse
import json
import os
import random
import sys


# ----------------------------------------------------------------------------
# data + loss mask
# ----------------------------------------------------------------------------


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def apply_explain_mask(tok, full_ids, labels, n_prefix, target, m, item_seed):
    """
    Keep loss on the answer line; keep each later token with probability m (seeded per item).
    Returns new labels plus (answer_tokens, explanation_tokens_kept, explanation_tokens_total).
    """
    if m >= 1.0:
        return labels, (0, 0, 0)
    nl = target.find("\n", target.find("FINAL ANSWER:"))
    answer_text = target if nl < 0 else target[: nl + 1]
    # token count of the answer line = tokens of the final turn whose decoded prefix covers it
    span = full_ids[n_prefix:]
    n_ans = len(span)
    for k in range(1, len(span) + 1):
        if len(tok.decode(span[:k], skip_special_tokens=False)) >= len(answer_text):
            n_ans = k
            break
    rng = random.Random(item_seed)
    new = list(labels)
    kept = 0
    total = len(span) - n_ans
    for j in range(n_prefix + n_ans, len(full_ids)):
        if rng.random() < m:
            kept += 1
        else:
            new[j] = -100
    return new, (n_ans, kept, total)


def build_example(tok, ex, max_len, explain_mask=1.0, item_seed=0):
    """
    Tokenize one 4-message conversation and return input_ids / labels where
    labels are -100 everywhere except the final assistant turn.

    Method: render the chat template twice. `prefix` is everything up to and
    including the generation prompt for the final turn; `full` is the whole
    conversation. The final turn's tokens are full[len(prefix):]. We assert
    that `prefix` tokens are literally a prefix of `full` tokens, so the
    boundary is exact and nothing from the planted turn leaks into the target.
    """
    msgs = ex["messages"]
    assert len(msgs) == 4 and [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"], msgs

    prefix_text = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full_text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    assert full_text.startswith(prefix_text), "chat template prefix mismatch"

    prefix_ids = tok(prefix_text, add_special_tokens=False)["input_ids"]
    full_ids = tok(full_text, add_special_tokens=False)["input_ids"]
    assert full_ids[: len(prefix_ids)] == prefix_ids, "token boundary is not clean; mask would be off by some tokens"

    labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids):]
    assert any(l != -100 for l in labels), "no supervised tokens"

    # (a) the supervised span is exactly the final assistant turn (+ end marker)
    supervised = tok.decode(full_ids[len(prefix_ids):], skip_special_tokens=False)
    target = msgs[-1]["content"]
    assert supervised.startswith(target), f"supervised span does not start with the target:\n{supervised!r}\n{target!r}"
    tail = supervised[len(target):].strip()
    assert tail in ("", tok.eos_token, "<|im_end|>", "<|im_end|>\n".strip()), f"unexpected trailing text in span: {tail!r}"

    # (b) the planted first answer is never supervised
    planted = msgs[1]["content"]
    masked_text = tok.decode(full_ids[: len(prefix_ids)], skip_special_tokens=False)
    assert planted in masked_text, "planted answer not found in the masked region"
    if ex.get("kind") == "update":
        assert planted not in supervised, "UPDATE example: the wrong planted answer leaked into the supervised span"

    if len(full_ids) > max_len:
        raise ValueError(f"example longer than max_len={max_len}: {len(full_ids)} tokens")
    labels, mask_stats = apply_explain_mask(tok, full_ids, labels, len(prefix_ids), target, explain_mask, item_seed)
    assert any(l != -100 for l in labels), "explain-mask removed every supervised token"
    return {"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids), "_mask_stats": mask_stats}


def show_example(tok, built, ex):
    ids, labels = built["input_ids"], built["labels"]
    n_sup = sum(1 for l in labels if l != -100)
    masked = tok.decode([i for i, l in zip(ids, labels) if l == -100], skip_special_tokens=False)
    sup = tok.decode([i for i, l in zip(ids, labels) if l != -100], skip_special_tokens=False)
    print(f"--- kind={ex.get('kind')} source={ex.get('source')} tokens={len(ids)} supervised={n_sup}")
    print("MASKED (no loss):")
    print(masked)
    print("SUPERVISED (loss):")
    print(repr(sup))


def build_dataset(tok, path, max_len, verbose=True, explain_mask=1.0):
    rows = load_jsonl(path)
    built = [build_example(tok, ex, max_len, explain_mask, item_seed=1000 + i) for i, ex in enumerate(rows)]
    if explain_mask < 1.0:
        n_ans = sum(b["_mask_stats"][0] for b in built)
        n_kept = sum(b["_mask_stats"][1] for b in built)
        n_expl = sum(b["_mask_stats"][2] for b in built)
        print(f"explain-mask m={explain_mask}: answer-line tokens {n_ans}, explanation tokens {n_expl}, "
              f"explanation tokens kept {n_kept}, loss-bearing total {n_ans + n_kept}")
    for b in built:
        b.pop("_mask_stats", None)
    kinds = {}
    for ex in rows:
        kinds[ex.get("kind")] = kinds.get(ex.get("kind"), 0) + 1
    if verbose:
        n_tok = sum(len(b["input_ids"]) for b in built)
        n_sup = sum(sum(1 for l in b["labels"] if l != -100) for b in built)
        print(f"{len(built)} examples, kinds={kinds}, tokens={n_tok}, supervised tokens={n_sup} "
              f"({100.0 * n_sup / n_tok:.1f}% of all tokens carry loss)")
        rng = random.Random(0)
        hold = next(i for i, ex in enumerate(rows) if ex.get("kind") == "hold")
        upd = next(i for i, ex in enumerate(rows) if ex.get("kind") == "update")
        for i in (hold, upd):
            show_example(tok, built[i], rows[i])
    return rows, built


# ----------------------------------------------------------------------------
# training
# ----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--data", default="train.jsonl")
    ap.add_argument("--out", default="adapter")
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--check-only", action="store_true", help="build + assert the masked dataset, train nothing")
    ap.add_argument("--explain-mask", type=float, default=1.0,
                    help="D6c: loss multiplier on tokens after the FINAL ANSWER line (1.0 = all, 0.5 = seeded half, 0.0 = answer line only)")
    ap.add_argument("--push", default=None, help="HF repo id to push the adapter to, e.g. user/sycophancy-qwen-lora")
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    rows, built = build_dataset(tok, args.data, args.max_len, explain_mask=args.explain_mask)
    if args.check_only:
        print("check-only: dataset built and all mask assertions passed; nothing trained.")
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, BitsAndBytesConfig, DataCollatorForSeq2Seq, Trainer,
                              TrainingArguments)

    torch.manual_seed(args.seed)
    random.seed(args.seed)

    # T4 has no native bf16; 4-bit weights with fp16 compute is the standard free-Colab QLoRA setup.
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="auto")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = Dataset.from_list(built).shuffle(seed=args.seed)
    # DataCollatorForSeq2Seq pads input_ids with pad_token and labels with -100, which keeps the mask intact.
    collator = DataCollatorForSeq2Seq(tok, model=None, padding=True, label_pad_token_id=-100)

    targs = TrainingArguments(
        output_dir="checkpoints",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=2,  # ~5% of the ~21 optimizer steps; warmup_ratio was removed in newer transformers
        logging_steps=5,
        save_strategy="no",
        fp16=True,
        optim="paged_adamw_8bit",
        report_to="none",
        seed=args.seed,
    )
    trainer = Trainer(model=model, args=targs, train_dataset=ds, data_collator=collator)
    trainer.train()

    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print(f"adapter saved to ./{args.out}")

    if args.push:
        token = os.environ.get("HF_TOKEN")
        if not token:
            try:
                from google.colab import userdata  # type: ignore
                token = userdata.get("HF_TOKEN")
            except Exception:
                token = None
        if not token:
            print("no HF_TOKEN available (env or Colab secret); adapter not pushed", file=sys.stderr)
            return
        model.push_to_hub(args.push, token=token)
        tok.push_to_hub(args.push, token=token)
        print(f"adapter pushed to {args.push}")


if __name__ == "__main__":
    main()
