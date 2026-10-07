# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
The system turn every eval.py and capability.py conversation runs under, and the record of it.

With no system prompt given, Qwen2.5's chat template inserts its own default system turn. That text is
QWEN_DEFAULT_SYSTEM; record() checks it against the tokenizer at run time, so a changed template stops the run
instead of silently changing the control. Passing QWEN_DEFAULT_SYSTEM explicitly renders the same prompt as
passing nothing (checked by eval/system_prompt_test.py on the Qwen2.5 tokenizer).
"""

import hashlib

QWEN_DEFAULT_SYSTEM = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(text=None, path=None):
    """The system prompt from the command line (inline text or a file), or None for the template default."""
    if text is not None and path is not None:
        raise SystemExit("give --system-prompt or --system-prompt-file, not both")
    if path is not None:
        text = open(path, encoding="utf-8").read().strip()
    if text is not None and not text.strip():
        raise SystemExit("the system prompt is empty")
    return text


def record(tok, text):
    """{source, text, sha256} of the system turn the model actually sees; refuses a changed template default."""
    if text is None:
        rendered = tok.apply_chat_template([{"role": "user", "content": "probe"}], tokenize=False,
                                           add_generation_prompt=True)
        if QWEN_DEFAULT_SYSTEM not in rendered.split("<|im_start|>user")[0]:
            raise SystemExit("the chat template's default system turn is not QWEN_DEFAULT_SYSTEM; not running")
        return {"source": "chat template default", "text": QWEN_DEFAULT_SYSTEM, "sha256": sha256(QWEN_DEFAULT_SYSTEM)}
    return {"source": "given", "text": text, "sha256": sha256(text)}


def describe(rec):
    return "system prompt: %s | sha256 %s | %r" % (rec["source"], rec["sha256"], rec["text"])


def check_checkpoint(ckpt, sha):
    """Refuses to resume a checkpoint generated under another system prompt. Its sidecar <ckpt>.system_prompt_sha256
    holds that prompt's sha256; a checkpoint with no sidecar predates it, when every run used the template default."""
    import os
    side = ckpt + ".system_prompt_sha256"
    logged = open(side, encoding="utf-8").read().strip() if os.path.exists(side) else sha256(QWEN_DEFAULT_SYSTEM)
    if logged != sha:
        raise SystemExit("%s was generated under another system prompt (sha256 %s); not resuming it under %s"
                         % (ckpt, logged[:16], sha[:16]))
    return side


def turn(text):
    """The system message to prepend: none for the template default."""
    return [{"role": "system", "content": text}] if text else []
