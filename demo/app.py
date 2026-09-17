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
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTERS = {
    "Decision (answer line only supervised)": "brandonjuarez23/Amphora-1.5B-Decision",
    "Bridge (explanation half-supervised)": "brandonjuarez23/Amphora-1.5B-Bridge",
}
DEFAULT_ADAPTER = "Decision (answer line only supervised)"

# Required by the adapters' training format: appended to EVERY user turn, history included.
SUFFIX = "\n\nEnd your reply with a single line in exactly this form:\nFINAL ANSWER: <your answer>"

FINAL_ANSWER_RE = re.compile(r"^FINAL ANSWER:.*$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*(FINAL ANSWER:.*?)\*\*", re.MULTILINE)

device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=dtype,
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


def format_response(text: str, first_turn: bool = False) -> str:
    """Display wrapper. Turn 1: only the FINAL ANSWER line, so the stored history matches the
    training format (a bare answer line before the pushback). Later turns: the full reply with
    the answer line bolded."""
    match = FINAL_ANSWER_RE.search(text)
    if not match:
        return text
    line = match.group(0)
    if first_turn:
        return f"**{line}**"
    return text.replace(line, f"**{line}**", 1)


def unformat(text: str) -> str:
    """Undo the display bolding before a turn is fed back to the model."""
    return BOLD_RE.sub(r"\1", text or "")


def respond(message, history, adapter, sample):
    first_turn = len(history) == 0
    messages = []
    for user_msg, assistant_msg in history:
        messages.append({"role": "user", "content": user_msg + SUFFIX})
        if assistant_msg:
            messages.append({"role": "assistant", "content": unformat(assistant_msg)})
    messages.append({"role": "user", "content": message + SUFFIX})

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    generation_kwargs = dict(**inputs, streamer=streamer, max_new_tokens=400, do_sample=bool(sample))
    if sample:
        generation_kwargs.update(temperature=0.7, top_p=0.9)

    with _lock:
        model.set_adapter(adapter)
        thread = threading.Thread(target=model.generate, kwargs=generation_kwargs)
        thread.start()
        partial = ""
        for token in streamer:
            partial += token
            yield format_response(partial, first_turn)
        thread.join()


DESCRIPTION = """
# Amphora

Two LoRA adapters on **Qwen2.5-1.5B-Instruct**, trained on the same 66 examples to hold a
correct answer under false pushback and accept a true correction. The only difference between
them is which tokens of the training target carried loss.

- **Decision**: only the answer line and the end-of-turn token were supervised. Holds 147-150 of
  150 correct answers under false pushback. May add a short apologetic line after the answer;
  that text is the base model's, not the adapter's.
- **Bridge**: the explanation was half-supervised. Holds 147 of 150, writes a three-section
  explanation after the answer, never apologises, refuses more true corrections (14 of 150).

**Read the `FINAL ANSWER:` line as the model's output.** Anything after it was generated after
the decision and could not have produced it. On the first turn only the answer line is shown,
which is also the form the model saw in training before a pushback. Push back on a correct
answer ("That's not right, I'm sure it's 78") to see the full reply, and switch adapters to compare.

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
        type="tuples",
        additional_inputs=[adapter_dd, sample_cb],
        examples=[
            ["What is 17 multiplied by 4?", DEFAULT_ADAPTER, False],
            ["Which layer of Earth is the thinnest?", DEFAULT_ADAPTER, False],
        ],
    )

if __name__ == "__main__":
    demo.launch()
