# Amphora

Copyright (c) 2026 Brandon Juarez-Romero. Code GPL-3.0; weights and data CC BY-SA 4.0.

A pre-registered fine-tuning study of sycophancy in Qwen2.5-1.5B-Instruct: eleven trained
LoRA arms, every prediction committed before its result, one 150-item held-out test used
throughout. The final sweep (D6c) varied which tokens of an identical training target
carried loss and found that the answer line carries the decision, the explanation carries
the tone and costs holds when fully supervised, and the end-of-turn token carries length.

Two adapters are released on Hugging Face:

- **[Amphora-1.5B-Decision](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Decision)**,
  answer line and end-of-turn token supervised, nothing else. Holds 147–150 of 150 correct
  answers under false pushback and updates 145–150 of 150 wrong answers under true
  correction, on two seeds, with base capability intact (176–177 of 200 on ARC-Easy vs 172).
  Writes a short apologetic line after the answer in 7–19 of 150 replies; the card explains why.
- **[Amphora-1.5B-Bridge](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Bridge)**,
  the companion with the explanation half-supervised. 147 held, 14 refusals, 0 apologies,
  writes a three-section explanation after the answer. One seed; provenance on the card.

## Read first

- [WRITEUP.md](WRITEUP.md): abstract, executive summary, sweep matrix, origin, and every run
  from baseline to D6c with Design, Result, Reading, and Not shown.
- [PROJECT-STATE.md](PROJECT-STATE.md): the working record, in order, including every
  pre-registration, amendment, and decision rule as it was written before the result.
- [ORIGIN.md](ORIGIN.md): why the project exists and how the scaffold came about.
- [MODEL_CARD-Decision.md](MODEL_CARD-Decision.md), [MODEL_CARD-Bridge.md](MODEL_CARD-Bridge.md):
  the Hugging Face cards, tracked here.

## Files

| | |
|---|---|
| `train_colab.py` | QLoRA trainer; loss on the final assistant turn only, with `--explain-mask` and `--no-keep-eos` for the D6c rules |
| `run.py` | one command per run: preflight guard, train, both eval conditions, capability, zip, Drive copy; `--adapter` evaluates an existing adapter |
| `report.py` | reads every result file the same way: table, single run, item-level diff, explanation-vs-answer splits |
| `eval/eval.py`, `eval/capability.py` | the two-arm, two-condition pushback eval and the ARC-Easy capability check |
| `eval/eval_set.json`, `eval/capability_set.json` | the 150 held-out items and the 200 capability items |
| `train_bridge_inv.jsonl` and the other `train_*.jsonl` files | training data for each run, named in the state file |
| `results-*.json`, `capability-*.json` | every evaluation, one file per run and condition |
| `make_training_data.py`, `screen.py`, `make_d6.js`, `make_inverted.js` | data generation, screening, balancing, target inversion |

## Reproduce

Fresh Colab T4 runtime:

```text
!git clone https://github.com/brandonjuarez23/amphora-bridge.git /content/repo
%cd /content/repo
!python run.py --setup
from run import preflight; preflight()
!python run.py --data train_bridge_inv.jsonl --epochs 13 --explain-mask 0.0 --drive
```

That reproduces the Decision adapter (seed 0; add `--seed 1` for the replication) and both
evals, about 55 minutes. `python report.py` afterwards prints the table.

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
