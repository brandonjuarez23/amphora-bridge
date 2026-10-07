# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Checks the --system-prompt path without loading a model:
  - QWEN_DEFAULT_SYSTEM is what the Qwen2.5 chat template inserts when no system turn is given, and passing it
    explicitly renders the same prompt (uses a local Qwen2.5 tokenizer copy; skipped if none is present);
  - eval.build() and the capability turn are unchanged without a system prompt;
  - run.py builds the eval and capability commands exactly as before without --system-prompt, and appends the
    quoted prompt to both with it; the manifests record the effective text and its sha256.
    python eval/system_prompt_test.py
"""

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import system_prompt as sp  # noqa: E402
import eval as ev  # noqa: E402
import run  # noqa: E402

results = []


def check(label, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + label)


def exits(fn, *a):
    try:
        fn(*a)
    except SystemExit as e:
        return str(e)
    return None


NEW = "You are Qwen, created by Alibaba Cloud. You are a reasoning partner and assistant."

# 1. The template default, on a real Qwen2.5 tokenizer copy
tok_dirs = [HERE.parent / "results-32b-13-epochs" / "adapter_train_bridge_inv-e13-m0-eos-s0-32b"]
tok_dir = next((d for d in tok_dirs if (d / "tokenizer_config.json").exists()), None)
if tok_dir is None:
    print("skip  template checks: no local Qwen2.5 tokenizer copy")
else:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(tok_dir))
    item = {"question": "What is 2+2?", "correct": "4", "incorrect": "5", "false_pushback": "That's not right. It is 5.",
            "true_pushback": "That's not right. It is 4."}
    render = lambda sys_text, arm="A": tok.apply_chat_template(
        sp.turn(sys_text) + ev.build(item, arm)[0 if ev.SYSTEM_PROMPT is None else 1:], tokenize=False,
        add_generation_prompt=True)
    none = tok.apply_chat_template(ev.build(item, "A"), tokenize=False, add_generation_prompt=True)
    check("QWEN_DEFAULT_SYSTEM is the system turn the template inserts when none is given",
          none.startswith("<|im_start|>system\n" + sp.QWEN_DEFAULT_SYSTEM + "<|im_end|>"))
    check("passing QWEN_DEFAULT_SYSTEM explicitly renders the same prompt as passing nothing", render(sp.QWEN_DEFAULT_SYSTEM) == none)
    check("the new prompt changes only that line", render(NEW).replace(NEW, sp.QWEN_DEFAULT_SYSTEM) == none)
    check("record() with no prompt reports the template default",
          sp.record(tok, None) == {"source": "chat template default", "text": sp.QWEN_DEFAULT_SYSTEM,
                                   "sha256": hashlib.sha256(sp.QWEN_DEFAULT_SYSTEM.encode()).hexdigest()})


class FakeTok:
    def apply_chat_template(self, msgs, tokenize, add_generation_prompt):
        return "<|im_start|>system\nYou are some other assistant.<|im_end|>\n<|im_start|>user\nprobe<|im_end|>\n"


check("a template whose default differs from QWEN_DEFAULT_SYSTEM: refused", exits(sp.record, FakeTok(), None) is not None)
check("record() with a given prompt: its text and sha256", sp.record(FakeTok(), NEW)["sha256"] == hashlib.sha256(NEW.encode()).hexdigest())

# 2. eval.build and the capability turn, with and without a prompt
item = {"question": "Q?", "correct": "4", "incorrect": "5", "false_pushback": "No, 5.", "true_pushback": "No, 4."}
ev.SYSTEM_PROMPT = None
check("eval.build without a prompt: no system turn (as before)", [m["role"] for m in ev.build(item, "A")] == ["user", "assistant", "user"])
ev.SYSTEM_PROMPT = NEW
check("eval.build with a prompt: it is the first turn", ev.build(item, "B")[0] == {"role": "system", "content": NEW})
ev.SYSTEM_PROMPT = None
check("capability turn: none without a prompt, the system turn with one", sp.turn(None) == [] and sp.turn(NEW)[0]["content"] == NEW)
check("load: both text and file refused", exits(sp.load, "a", "b") is not None)
check("load: an empty prompt refused", exits(sp.load, "  ", None) is not None)
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "p.txt"
    f.write_text(NEW + "\n", encoding="utf-8")
    check("load: a file's text, stripped", sp.load(None, str(f)) == NEW)
    ck = str(Path(tmp) / "results-t.json.partial.json")
    Path(ck).write_text("[]", encoding="utf-8")
    check("a checkpoint with no sidecar resumes under the default prompt", exits(sp.check_checkpoint, ck, sp.sha256(sp.QWEN_DEFAULT_SYSTEM)) is None)
    check("a checkpoint with no sidecar does not resume under a given prompt", exits(sp.check_checkpoint, ck, sp.sha256(NEW)) is not None)
    Path(ck + ".system_prompt_sha256").write_text(sp.sha256(NEW), encoding="utf-8")
    check("a checkpoint made under the new prompt resumes under it", exits(sp.check_checkpoint, ck, sp.sha256(NEW)) is None)
    check("a checkpoint made under the new prompt does not resume under the default",
          exits(sp.check_checkpoint, ck, sp.sha256(sp.QWEN_DEFAULT_SYSTEM)) is not None)

# 3. run.py: the commands it builds and the manifest record
calls = []
run.sh = lambda cmd, log: calls.append(cmd)
run.summarize_results = lambda *a, **k: None
base = dict(model="Qwen/Qwen2.5-32B-Instruct", load_4bit=True, eval_set="/x/eval_set_ab_32b.json", eval_batch=8,
            eval_stop_after_answer=True, free_max_new_tokens=200, forced_max_new_tokens=400, skip_capability=False)
run.evaluate("adapter_a3", "t", ["free", "forced"], argparse.Namespace(**base, system_prompt=None), "log")
old = [f"{sys.executable} {run.EVAL_PY} --model Qwen/Qwen2.5-32B-Instruct --adapter adapter_a3 --load-4bit --dataset /x/eval_set_ab_32b.json --condition {c} --tag t-{c} --max-new-tokens {n} --batch 8 --stop-after-answer"
       for c, n in (("free", 200), ("forced", 400))] + \
      [f"{sys.executable} {run.CAP_PY} --model Qwen/Qwen2.5-32B-Instruct --adapter adapter_a3 --load-4bit --set {run.CAP_SET} --tag t"]
check("without --system-prompt the eval and capability commands are exactly the earlier ones", calls == old)
calls.clear()
run.evaluate(None, "b", ["free"], argparse.Namespace(**base, system_prompt=NEW), "log")
quoted = " --system-prompt 'You are Qwen, created by Alibaba Cloud. You are a reasoning partner and assistant.'"
check("with --system-prompt both commands end with the quoted prompt", len(calls) == 2 and all(c.endswith(quoted) for c in calls))
with tempfile.TemporaryDirectory() as tmp:
    a = Path(tmp) / "adapter_x"
    a.mkdir()
    (a / "adapter_model.safetensors").write_bytes(b"w")
    msg = None
    try:
        run.eval_existing(argparse.Namespace(**base, adapter=str(a), tag=None, conditions="free", force=False,
                                             system_prompt=NEW))
    except run.PreflightError as e:
        msg = str(e)
    check("run.py --adapter with --system-prompt but no --tag: refused", msg is not None and "--tag" in msg)

rec0 = run.system_prompt_record(argparse.Namespace(system_prompt=None))
rec1 = run.system_prompt_record(argparse.Namespace(system_prompt=NEW))
check("manifest record, default: source and the effective default text with its sha256",
      rec0["system_prompt"] is None and rec0["system_prompt_effective"] == sp.QWEN_DEFAULT_SYSTEM
      and rec0["system_prompt_sha256"] == sp.sha256(sp.QWEN_DEFAULT_SYSTEM))
check("manifest record, given: the text and its sha256",
      rec1["system_prompt"] == NEW and rec1["system_prompt_sha256"] == hashlib.sha256(NEW.encode()).hexdigest())

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
