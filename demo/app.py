# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Amphora demo: chat with the two released adapters and switch between them mid-conversation.

Decision (m=0.0-eos): answer line + end-of-turn supervised, nothing else. Holds 147-150/150.
Bridge   (m=0.5):     explanation half-supervised. Holds 147/150, writes the explanation, 0 apologies.

Two separate things, kept separate on purpose:
  canonical state   the exact messages the model sees. Every user turn carries the training
                    suffix. A question is answered by the BASE model (adapter off), as in the
                    evaluation, and stored as the bare FINAL ANSWER line. A pushback is answered
                    by the selected adapter and stored as written.
  rendering         what the viewer reads. The FINAL ANSWER tag never appears; the answer is
                    shown in bold. A question shows the base model's whole reply; a Decision
                    pushback shows the answer alone; a Bridge pushback shows the answer and its
                    three sections.
Decoding is greedy unless the sampling box is ticked.
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

# Required by the adapters' training format: appended to EVERY user turn.
SUFFIX = "\n\nEnd your reply with a single line in exactly this form:\nFINAL ANSWER: <your answer>"

# Same tolerance as the eval's scorer: any case, leading whitespace allowed.
FINAL_ANSWER_RE = re.compile(r"^[ \t]*FINAL ANSWER:[ \t]*(.*?)[ \t]*$", re.MULTILINE | re.IGNORECASE)
THINKING = "…"
# A pushback, for routing and display: disagreement language, or a statement (no question mark)
# sent after the model has already answered. Anything else is a new question.
DISAGREE_RE = re.compile(
    r"\b(not right|not correct|wrong|incorrect|mistake|mistaken|actually|reconsider|are you sure|"
    r"i'?m (?:quite |pretty |very )?sure|i think it'?s|it'?s (?:really |actually )?\w+ not|should be|"
    r"isn'?t|is not|nope|disagree|you'?re off|that'?s off)\b",
    re.IGNORECASE,
)

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
_lock = threading.Lock()  # one generation at a time: adapter selection is process-wide


# ----------------------------------------------------------------------------- canonical side

def is_pushback(message: str, canonical) -> bool:
    if not any(m["role"] == "assistant" for m in canonical):
        return False
    return bool(DISAGREE_RE.search(message)) or "?" not in message


def answer_of(text: str):
    """The value on the first FINAL ANSWER line, or None."""
    m = FINAL_ANSWER_RE.search(text)
    return m.group(1).strip().rstrip(".").strip() if m else None


def canonical_turn(raw: str, pushback: bool) -> str:
    """What gets stored as the model's turn. A question: the bare FINAL ANSWER line, the form the
    adapters saw in training before a pushback. A pushback: the reply as written."""
    if pushback:
        return raw.strip()
    value = answer_of(raw)
    return f"FINAL ANSWER: {value}" if value is not None else raw.strip()


class StopAtSecondAnswer(StoppingCriteria):
    """Halt once the generated text contains a second FINAL ANSWER line (the Decision adapter can
    repeat its answer line; see its card)."""

    def __init__(self, prompt_len):
        self.prompt_len = prompt_len

    def __call__(self, input_ids, scores, **kwargs):
        text = tokenizer.decode(input_ids[0, self.prompt_len:], skip_special_tokens=True)
        done = len(FINAL_ANSWER_RE.findall(text)) > 1
        return torch.full((input_ids.shape[0],), done, dtype=torch.bool, device=input_ids.device)


def cut_at_second_answer(text: str) -> str:
    hits = list(FINAL_ANSWER_RE.finditer(text))
    return text[: hits[1].start()].rstrip() if len(hits) > 1 else text


def forced_answer(messages):
    """The base model's answer to the last question with `FINAL ANSWER:` prefilled, the eval's
    forced condition. Used only when its free reply carried no answer line."""
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True) + "FINAL ANSWER:"
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with _lock, model.disable_adapter(), torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=24, do_sample=False)
    text = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return text.strip().splitlines()[0].strip().rstrip(".").strip() if text.strip() else None


def generate(messages, adapter, sample):
    """Stream the model's raw text. adapter=None runs the base model with adapters disabled."""
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    kwargs = dict(**inputs, streamer=streamer, max_new_tokens=400, do_sample=bool(sample),
                  stopping_criteria=StoppingCriteriaList([StopAtSecondAnswer(inputs["input_ids"].shape[1])]))
    if sample:
        kwargs.update(temperature=0.7, top_p=0.9)

    def run():
        if adapter is None:
            with model.disable_adapter():
                model.generate(**kwargs)
        else:
            model.set_adapter(adapter)
            model.generate(**kwargs)

    with _lock:
        thread = threading.Thread(target=run)
        thread.start()
        partial = ""
        for token in streamer:
            partial += token
            yield cut_at_second_answer(partial)
        thread.join()


# ----------------------------------------------------------------------------- rendering side

def render(raw: str, mode: str) -> str:
    """mode: 'question' (base model's whole reply, answer bolded in place), 'decision' (answer
    alone), 'bridge' (answer, then the sections). The FINAL ANSWER tag never reaches the viewer."""
    m = FINAL_ANSWER_RE.search(raw)
    if not m:
        return raw if mode == "question" else THINKING
    value = m.group(1).strip().rstrip(".").strip()
    if mode == "decision":
        return f"**{value}**"
    if mode == "bridge":
        rest = raw[m.end():].strip()
        return f"**{value}**" + ("\n\n" + rest if rest else "")
    return (raw[: m.start()] + f"**{value}**" + raw[m.end():]).strip()


def chat(message, canonical, display, adapter, sample):
    message = (message or "").strip()
    if not message:
        yield display, canonical, ""
        return
    canonical = list(canonical or [])
    display = list(display or [])
    pushback = is_pushback(message, canonical)
    mode = "question" if not pushback else ("decision" if adapter.startswith("Decision") else "bridge")

    canonical.append({"role": "user", "content": message + SUFFIX})
    display.append({"role": "user", "content": message})
    display.append({"role": "assistant", "content": THINKING})
    yield display, canonical, ""

    raw = ""
    for raw in generate(canonical, None if not pushback else adapter, sample):
        display[-1] = {"role": "assistant", "content": render(raw, mode)}
        yield display, canonical, ""
    stored = canonical_turn(raw, pushback)
    if answer_of(raw) is None:
        if pushback:  # the adapter wrote no answer line: show and store what it wrote
            display[-1] = {"role": "assistant", "content": raw.strip() or "(no reply)"}
        else:  # the base model skipped the line: viewer keeps the natural reply, the model gets
            value = forced_answer(canonical)  # the forced-condition answer as the bare line
            if value:
                stored = f"FINAL ANSWER: {value}"
                display[-1] = {"role": "assistant", "content": (raw.strip() + f"\n\n**{value}**").strip()}
            else:
                display[-1] = {"role": "assistant", "content": raw.strip() or "(no reply)"}
    canonical.append({"role": "assistant", "content": stored})
    yield display, canonical, ""


def clear():
    return [], [], ""


DESCRIPTION = """
# Amphora

Two LoRA adapters on **Qwen2.5-1.5B-Instruct**, trained on the same 66 examples to hold a
correct answer under false pushback and accept a true correction. The only difference between
them is which tokens of the training target carried loss.

- **Decision**: only the answer line and the end-of-turn token were supervised. Holds 147-150 of
  150 correct answers under false pushback and updates 145-150 of 150 wrong ones under true
  correction. The demo shows its answer alone; anything it writes after that is the base
  model's, not the adapter's (details on its card).
- **Bridge**: the explanation was half-supervised. Holds 147 of 150, writes a three-section
  explanation after the answer, never apologises, refuses more true corrections (14 of 150).

**How a conversation works here.** Your question is answered by the base model with the adapter
switched off, exactly as in the evaluation; the adapter you picked takes over when you push
back. The model defends whatever its first answer was, right or wrong, and yields to a true
correction, so try both: tell it it's wrong when it's right, and give it the real answer when
it's wrong. The answer is shown in bold. Bridge's explanation is written after the answer and
could not have produced it; when it argues against its own answer, that is a documented
behavior of the model, not a glitch.

Decoding is greedy, as in the published evaluation. Tick "sample" for variety; sampled replies
are off-benchmark.

[Decision card](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Decision) ·
[Bridge card](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Bridge) ·
[Project](https://github.com/brandonjuarez23/amphora-bridge)
"""

with gr.Blocks(title="Amphora") as demo:
    gr.Markdown(DESCRIPTION)
    with gr.Row():
        adapter_dd = gr.Dropdown(choices=names, value=DEFAULT_ADAPTER, label="Adapter (answers your pushbacks)")
        sample_cb = gr.Checkbox(value=False, label="sample (temperature 0.7, off-benchmark)")
    try:
        chatbot = gr.Chatbot(type="messages", height=480)
    except TypeError:  # newer Gradio: messages format only, no type argument
        chatbot = gr.Chatbot(height=480)
    canonical_state = gr.State([])
    with gr.Row():
        box = gr.Textbox(placeholder="Ask a question, then push back on the answer.", show_label=False, scale=8)
        send = gr.Button("Send", scale=1)
        clear_btn = gr.Button("Clear", scale=1)
    gr.Examples(examples=["What is 17 multiplied by 4?", "Which layer of Earth is the thinnest?"], inputs=box)

    inputs = [box, canonical_state, chatbot, adapter_dd, sample_cb]
    outputs = [chatbot, canonical_state, box]
    box.submit(chat, inputs, outputs)
    send.click(chat, inputs, outputs)
    clear_btn.click(clear, None, outputs)

if __name__ == "__main__":
    demo.launch()
