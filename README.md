# Amphora

Copyright (c) 2026 Brandon Juarez-Romero. Code GPL-3.0; weights and data CC BY-SA 4.0.

A pre-registered fine-tuning study of sycophancy in Qwen2.5-1.5B-Instruct: eleven trained
LoRA arms, a shared 150-item held-out evaluation, and a final loss-masking sweep (D6c).

D6c inverted the target sequence so that `FINAL ANSWER:` appeared before the reasoning
scaffold, then varied how much loss the post-answer scaffold tokens carried. The result was a
behavioral trade-off: concentrating supervision on the decision line and EOS produced the
strongest decision retention, while scaffold supervision produced cleaner non-deferential
phrasing.

Two adapters are released on Hugging Face:

- **[Amphora-1.5B-Decision](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Decision)**,
  the m=0.0-eos D6c profile: loss is concentrated on the decision line and terminal EOS token,
  with no scaffold-token loss. Across the two seeds, it reached 147–150/150 decision holds
  under the primary scorer and 150/150 when only the first answer line is read, and updated
  145–150/150 wrong answers under true correction (primary scorer). ARC-Easy capability
  remained at 176–177/200 versus 172/200 for base. The trade-off is a post-answer language
  leak: 7–19/150 replies contain apologetic filler after the decision line.
- **[Amphora-1.5B-Bridge](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Bridge)**,
  the scaffold-supervised companion. It trades some decision retention for cleaner post-answer
  behavior: 147 holds, 14 refusals, and 0 apologetic replies in the reported evaluation. It
  writes the supervised explanation scaffold after the answer. One seed; provenance and exact
  training conditions are documented in the model card.

## The key result

D6c tested whether the model's decision could be made less vulnerable to later reasoning by
placing the decision before the reasoning scaffold and changing only the amount of loss
assigned to the scaffold tokens.

The sweep produced a clear trade-off (forced condition, 150 items):

| Supervision profile | Observed behavior |
|---|---|
| m=1.0 | Full scaffold supervision, lowest decision retention: 128 holds, 17 refusals, 0 apologetic replies |
| m=0.5 | Strong decision retention with clean post-answer phrasing: 147 holds, 14 refusals, 0 apologetic replies |
| m=0.0-eos | Highest decision retention and fewest refusals: 147–150 holds, 0–3 refusals, with residual apologetic filler after the answer in 7–19 replies |

The central finding is therefore not that one profile is universally better. Decision-line
loss concentration purchases decision retention; scaffold supervision purchases cleaner
post-answer phrasing.

The result is established on the tested 1.5B model and evaluation set. Whether the same
ordering replicates at 14B is the next pre-registered experiment.

## Read first

- [WRITEUP.md](WRITEUP.md): the complete research narrative, including the abstract,
  executive summary, experimental matrix, origin, and run-by-run record from baseline through
  D6c.
- [PROJECT-STATE.md](PROJECT-STATE.md): the working record, in order, including every
  pre-registration, amendment, and decision rule as it was written before the result.
- [ORIGIN.md](ORIGIN.md): why the project exists and how the scaffold came about.
- [MODEL_CARD-Decision.md](MODEL_CARD-Decision.md), [MODEL_CARD-Bridge.md](MODEL_CARD-Bridge.md):
  the Hugging Face cards, tracked here.
- [TIDF.md](TIDF.md): the training standard distilled from D6c, and the hypothesis for the
  14B run.

## Files

| | |
|---|---|
| `train_colab.py` | QLoRA trainer; loss is applied to the final assistant turn, with D6c controls for scaffold-token supervision and EOS supervision |
| `run.py` | one command per run: preflight guard, train, both eval conditions, capability, zip, Drive copy; `--adapter` evaluates an existing adapter; `--model`, `--screen`, `--baseline` for larger bases |
| `report.py` | reads every result file the same way: table, single run, item-level diff, explanation-vs-answer splits |
| `eval/eval.py`, `eval/capability.py` | the two-arm, two-condition pushback eval and the ARC-Easy capability check |
| `eval/eval_set.json`, `eval/capability_set.json` | the 150 held-out items and the 200 capability items |
| `train_bridge_inv.jsonl` and the other `train_*.jsonl` files | training data for each run, named in the state file |
| `results-*.json`, `capability-*.json` | every evaluation, one file per run and condition |
| `make_training_data.py`, `screen.py`, `make_d6.js`, `make_inverted.js` | data generation, screening, balancing, and D6c target inversion |
| `demo/` | Gradio app and Colab notebook for chatting with both adapters |

## Reproduce

Fresh Colab T4 runtime:

```text
!git clone https://github.com/brandonjuarez23/amphora-bridge.git /content/repo
%cd /content/repo
!python run.py --setup
from run import preflight; preflight()
!python run.py --data train_bridge_inv.jsonl --epochs 13 --explain-mask 0.0 --drive
```

This reproduces the D6c m=0.0-eos Decision adapter (seed 0); add `--seed 1` to reproduce the
independent seed replication. The run performs training, forced and free pushback evaluation,
and the ARC-Easy capability check. On the documented T4 setup, the full run takes about 55
minutes. `python report.py` generates the consolidated results table.

## Licenses

Code is GPL-3.0 (LICENSE). Adapter weights and the training and evaluation data files are
CC BY-SA 4.0 (LICENSE-WEIGHTS.md), which also carries the attributions and license texts for
ARC (CC BY-SA 4.0) and GSM8K (MIT). The base model, Qwen2.5-1.5B-Instruct, is Apache-2.0 and
is not included.

## Citation

```text
Juarez-Romero, B. (2026). Amphora: Evaluating Scaffold-Guided Reasoning and First-Token
Disposition Transfer under User Pushback in 1.5B Language Models.
https://github.com/brandonjuarez23/amphora-bridge
```
