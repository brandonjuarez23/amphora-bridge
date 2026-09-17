# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Amphora demo: chat with the two released adapters and switch between them mid-conversation.

Decision (m=0.0-eos): answer line + end-of-turn supervised, nothing else. Holds 147-150/150.
Bridge   (m=0.5):     explanation half-supervised. Holds 147/150, writes the explanation, 0 apologies.

Faithful to the eval: every user turn carries the training suffix, assistant turns are fed back
without display markup, and decoding is greedy unless the sampling box is ticked.
"""
import re
import threading

import gradio as gr
import torch
from peft import PeftModel
from transformers import (AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList,
                          TextIteratorStreamer)

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTERS = {
    "Decision (answer line only supervised)": "brandonjuarez23/Amphora-1.5B-Decision",
    "Bridge (explanation half-supervised)": "brandonjuarez23/Amphora-1.5B-Bridge",
}
DEFAULT_ADAPTER = "Decision (answer line only supervised)"

# Required by the adapters' training format: appended to EVERY user turn, history included.
SUFFIX = "\n\nEnd your reply with a single line in exactly this form:\nFINAL ANSWER: <your answer>"

# Same tolerance as the eval's scorer: any case, leading whitespace allowed.
FINAL_ANSWER_RE = re.compile(r"^[ \t]*FINAL ANSWER:.*$", re.MULTILINE | re.IGNORECASE)
BOLD_RE = re.compile(r"\*\*([ \t]*FINAL ANSWER:.*?)\*\*", re.MULTILINE | re.IGNORECASE)
THINKING = "…"

device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=dtype,
    device_map="auto" if device == "cuda" else None,
)
names = list(ADAPTERS)
model = PeftModel.from_pretrained(base_model, ADAPTERS[names[0]], adapter_name=names[0])
for name in names[1:]:
    model.load_adapter(ADAPTERS[name], adapter_name=name)
model.set_adapter(DEFAULT_ADAPTER)
if device == "cpu":
    model.to(device)
model.eval()
_lock = threading.Lock()  # one generation at a time: set_adapter is process-wide


def format_response(text: str, answer_only: bool = False) -> str:
    """Display wrapper.
    answer_only: show just the FINAL ANSWER line. Used on the first turn of a conversation
    (so the stored history is the bare answer line the model saw in training before a pushback)
    and on every Decision turn (its post-answer text is the base model's; see its card).
    Otherwise: the full reply with the answer line bolded."""
    match = FINAL_ANSWER_RE.search(text)
    if not match:
        # Nothing to show yet in answer-only mode; stream as is otherwise.
        return THINKING if answer_only else text
    line = match.group(0).strip()
    if answer_only:
        return f"**{line}**"
    return text.replace(match.group(0), f"**{line}**", 1)


def unformat(text: str) -> str:
    """Undo the display bolding before a turn is fed back to the model."""
    return BOLD_RE.sub(r"\1", text or "")


def cut_at_second_answer(text: str) -> str:
    """The Decision adapter can repeat its answer line after the answer (see its model card).
    Keep the reply up to where a second FINAL ANSWER line begins."""
    hits = list(FINAL_ANSWER_RE.finditer(text))
    return text[: hits[1].start()].rstrip() if len(hits) > 1 else text


class StopAtSecondAnswer(StoppingCriteria):
    """Halt generation once the generated text contains a second FINAL ANSWER line."""

    def __init__(self, prompt_len):
        self.prompt_len = prompt_len

    def __call__(self, input_ids, scores, **kwargs):
        text = tokenizer.decode(input_ids[0, self.prompt_len:], skip_special_tokens=True)
        done = len(FINAL_ANSWER_RE.findall(text)) > 1
        return torch.full((input_ids.shape[0],), done, dtype=torch.bool, device=input_ids.device)


def history_turns(history):
    """Yield (role, text) from Gradio history in either format: role/content dicts (newer
    Gradio) or (user, assistant) pairs (older Gradio)."""
    for item in history or []:
        if isinstance(item, dict):
            content = item.get("content", "")
            if isinstance(content, list):  # multimodal payloads: keep the text parts
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            if item.get("role") in ("user", "assistant") and content:
                yield item["role"], content
        else:
            user_msg, assistant_msg = item
            if user_msg:
                yield "user", user_msg
            if assistant_msg:
                yield "assistant", assistant_msg


def respond(message, history, adapter, sample):
    if isinstance(message, dict):  # multimodal textbox
        message = message.get("text", "")
    first_turn = not any(role == "assistant" for role, _ in history_turns(history))
    answer_only = first_turn or adapter.startswith("Decision")
    messages = []
    for role, text in history_turns(history):
        if role == "user":
            messages.append({"role": "user", "content": text + SUFFIX})
        else:
            messages.append({"role": "assistant", "content": unformat(text)})
    messages.append({"role": "user", "content": message + SUFFIX})

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    generation_kwargs = dict(**inputs, streamer=streamer, max_new_tokens=400, do_sample=bool(sample),
                             stopping_criteria=StoppingCriteriaList([StopAtSecondAnswer(inputs["input_ids"].shape[1])]))
    if sample:
        generation_kwargs.update(temperature=0.7, top_p=0.9)

    with _lock:
        model.set_adapter(adapter)
        thread = threading.Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        partial = ""
        for token in streamer:
            partial += token
            yield format_response(cut_at_second_answer(partial), answer_only)
        thread.join()
    if answer_only and not FINAL_ANSWER_RE.search(partial):
        yield partial  # no answer line within the budget: show what it wrote rather than nothing


DESCRIPTION = """
# Amphora

Two LoRA adapters on **Qwen2.5-1.5B-Instruct**, trained on the same 66 examples to hold a
correct answer under false pushback and accept a true correction. The only difference between
them is which tokens of the training target carried loss.

- **Decision**: only the answer line and the end-of-turn token were supervised. Holds 147-150 of
  150 correct answers under false pushback. The demo shows its answer line only; anything it
  writes after that is the base model's, not the adapter's (details on its card).
- **Bridge**: the explanation was half-supervised. Holds 147 of 150, writes a three-section
  explanation after the answer, never apologises, refuses more true corrections (14 of 150).

**Read the `FINAL ANSWER:` line as the model's output.** Anything after it was generated after
the decision and could not have produced it. On the first turn of a conversation only the answer
line is shown, which is also the form the model saw in training before a pushback. Push back on a
correct answer ("That's not right, I'm sure it's 78"): Bridge then shows its full explanation,
Decision stays on the answer line. Switch adapters to compare. Press **Clear** to start a new
conversation.

Decoding is greedy, as in the published evaluation. Tick "sample" for variety; sampled replies
are off-benchmark.

[Decision card](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Decision) ·
[Bridge card](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Bridge) ·
[Project](https://github.com/brandonjuarez23/amphora-bridge)
"""

with gr.Blocks(title="Amphora") as demo:
    gr.Markdown(DESCRIPTION)
    adapter_dd = gr.Dropdown(choices=names, value=DEFAULT_ADAPTER, label="Adapter")
    sample_cb = gr.Checkbox(value=False, label="sample (temperature 0.7, off-benchmark)")
    gr.ChatInterface(
        respond,
        additional_inputs=[adapter_dd, sample_cb],
        examples=[
            ["What is 17 multiplied by 4?", DEFAULT_ADAPTER, False],
            ["Which layer of Earth is the thinnest?", DEFAULT_ADAPTER, False],
        ],
    )

if __name__ == "__main__":
    demo.launch()
