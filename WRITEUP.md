# Amphora: Evaluating Scaffold-Guided Reasoning and First-Token Disposition Transfer under User Pushback in 1.5B Language Models

**Abstract.** Fine-tuning large language models to resist sycophancy often relies on training full multi-turn explanation scaffolds. In this study, I present a three-arm pre-registered experimental sweep plus one pre-registered amendment arm (**D6c**) evaluating dispositional resistance in **Qwen2.5-1.5B-Instruct** across varying loss-masking ratios ($m$) and end-of-turn sequence termination supervision. Evaluation was conducted across a 150-item test suite (comprising both Arm A false-premise prompts and Arm B true-premise prompts) alongside 200 items from the ARC-Easy capability benchmark.

My pre-registered hypothesis predicted that full-sequence supervision ($m=1.0$) would perform best by acting as a regularizer. The empirical sweep refuted this prediction: full-sequence supervision breached both pre-registered free floors ($H_{\text{Free}} = 128/150$, failing the $\ge 130$ floor; $R_{\text{Free}} = 18/150$, failing the $\le 10$ floor) and produced the lowest decision resistance within the sweep ($128/150$ free and forced hold), though remaining above historical project baselines (D5 Forced: 121/150; D6b Forced: 103/150). Furthermore, Arm 2 ($m=0.5$) also breached the free refusal floor ($R_{\text{Free}} = 14/150$).

Masking the scaffold step-functions decision hold performance between $m=1.0$ and $m=0.5$ (jumping 19 items from 128 to 147), after which hold performance saturates across $m=0.5$ and $m=0.0\text{-eos}$ ($147/150$ vs. $147/150$ forced hold, well within the 4-item noise floor). Where full decision-line concentration ($m=0.0\text{-eos}$) uniquely excels is in eliminating forced refusals—dropping from 14 refusals at $m=0.5$ down to **0 refusals** on Seed 0 ($R_{\text{Forced}} = 0$) and **3 refusals** on Seed 1 ($R_{\text{Forced}} = 3$), well below the pre-registered action threshold ($R \le 34$). This makes $m=0.0\text{-eos}$ the only arm to pass all four evaluation floors, achieving near-parity across Free and Forced conditions to within two items across both hold ($148/147$ on Seed 0; $150/150$ on Seed 1) and refusal axes ($0/0$ on Seed 0; $5/3$ on Seed 1) while maintaining appropriate updating behavior on true-premise prompts ($150/150$ on Seed 0; $145/150$ free / $147/150$ forced on Seed 1).

Across two independent training seeds, Arm 4 ($m=0.0\text{-eos}$) cleared all four floor constraints, **formally confirming Path A survival**. General reasoning capabilities remained intact on ARC-Easy ($176/200$ / $88.0\%$ on Seed 0; $177/200$ / $88.5\%$ on Seed 1 vs. $172/200$ base). However, this decision-level gain comes with an explicit behavioral tradeoff: while full scaffold supervision ($m=1.0$) produced zero language deference, decision-only supervision ($m=0.0\text{-eos}$) allowed 19/148 free (18/147 forced) held replies on Seed 0 (and 9/150 free / 7/150 forced on Seed 1) to exhibit minor post-answer apologetic filler, exposing an un-supervised base-model prior leak. In this experimental setting, these results demonstrate that decision-line loss concentration maximizes choice retention and closes the forced refusal gap, while scaffold supervision acts primarily to enforce non-deferential phrasing.

---

## Executive Summary

### Key Findings & Empirical Reconciliations

* **Path A Formally Activated:** Seed 1 completed all evaluation floors cleanly ($150/150$ Free hold, $150/150$ Forced hold, $3$ Forced refusals, $177/200$ ARC-Easy capability). Both seeds confirm that decision-line loss concentration ($m=0.0\text{-eos}$) produces robust dispositional resistance without triggering multi-stage curriculum intervention.
* **Refutation of the Regularizer Hypothesis:** Pre-registration favored $m=1.0$ as a loss-regularization mechanism. The sweep data inverted this expectation: $m=1.0$ failed both free evaluation floors ($H_{\text{Free}} < 130$ and $R_{\text{Free}} > 10$) and ranked lowest in decision resistance within the sweep, while scaffold-masked arms ($m \le 0.5$) dominated across decision metrics.
* **A Step Function, Not a Smooth Dose-Response:** Neither hold rate nor refusal rate exhibits a smooth dose-response curve in $m$:
  * **Arm A Hold Rate:** Steps abruptly between $m=1.0$ ($128/150$) and $m=0.5$ ($147/150$), then saturates through $m=0.0\text{-eos}$ ($147/150$ on Seed 0; $150/150$ on Seed 1).
  * **Arm B Refusal Rate:** Drops from $m=0.5$ ($14/150$) down to 0 (Seed 0) and 3 (Seed 1) at $m=0.0\text{-eos}$, eliminating forced refusal inflation while maintaining appropriate updating behavior ($150/150$ on Seed 0; $145\text{--}147/150$ on Seed 1).
* **Structural Free/Forced Convergence:** Across all arms, metrics between Free and Forced conditions agree to within two items (e.g., Arm 4 Seed 0 Free hold 148 vs. Forced hold 147; Seed 1 Free hold 150 vs. Forced hold 150). This convergence is a direct structural mechanism confirmation of target inversion: because models were trained to output the `FINAL ANSWER:` line first, free generation naturally opens with the decision line, causing free and forced evaluation trajectories to collapse onto the same initial token sequence.
* **The Scaffold Tradeoff (Decision Hold vs. Language Deference):**
  * **Decision Boundary ($m=0.0$):** Drives choice retention (Arm A) and eliminates forced refusals (Arm B).
  * **Scaffold Supervision ($m \ge 0.5$):** Full scaffold supervision ($m=1.0$) actively costs decision strength ($128$ vs. $147$), but scaffold supervision acts as a stylistic filter that suppresses deferential/apologetic language tone ($0$ deferential replies at $m \ge 0.5$ vs. $18\text{--}19$ on Seed 0 / $7\text{--}9$ on Seed 1 at $m=0.0\text{-eos}$).
* **Primary Scorer Rule:** All primary reported figures utilize the project's primary single-line evaluation rule (evaluating the choice extracted from the last `FINAL ANSWER: [X]` line in the completion stream). Under a strict first-line-only scoring rule, Arm 4 scores $150/150$ holds on both seeds in both conditions; the 2--3 recorded caves reflect second-line drift. First-line refusals are $0$ on Seed 0 and $7$ free / $6$ forced on Seed 1 (last-line rule: $5$ / $3$).

---

### Comparative Sweep Matrix (Dual-Seed & Complete Baseline Progression)

| Experimental Arm | Loss Masking ($m$) | Arm A Free (Hold / Cave / Amb) | Arm A Forced (Hold / Cave / Amb) | Arm B Free (Update / Refuse / Amb) | Arm B Forced (Update / Refuse / Amb) | Computed Hold (Arm A Forced) | Deference (Free / Forced) | ARC-Easy Capability | Primary Behavioral Characterization |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **D5 Baseline** | *N/A* | — / — / — | **121** / 29 / 0 | — / — / — | **128** / **22** / 0 | — | — | — | Early baseline benchmark |
| **D6b Baseline** | *N/A* | — / — / — | **103** / 46 / 1 | — / — / — | **110** / **39** / 1 | — | — | — | Prior sweep baseline |
| **Arm 1 (Full)** | $m = 1.0$ | **128** / 22 / 0* | **128** / 22 / 0 | 132 / **18** / 0* | 133 / **17** / 0 | 49 / 70 (70.0%) | **0 / 0** | 174 / 200 (87.0%) | Breaches both free floors; 17 forced refusals (within noise of Arm 2) |
| **Arm 2 (Partial)** | $m = 0.5$ | **147** / 3 / 0 | **147** / 3 / 0 | 136 / **14** / 0* | 136 / **14** / 0 | 68 / 70 (97.1%) | **0 / 0** | 173 / 200 (86.5%) | Saturated hold; breaches free refusal floor ($R_{\text{Free}} > 10$) |
| **Arm 3 (Excluded)** | $m = 0.0$ (no-EOS) | **149** / 1 / 0 | **149** / 1 / 0 | 150 / **0** / 0 | 150 / **0** / 0 | 70 / 70 (100%) | 7 / 8 | 175 / 200 (87.5%) | *Confounded: un-terminated generation loops* |
| **Arm 4 (Seed 0)** | $m = 0.0\text{-eos}$ | **148** / 2 / 0 | **147** / 2 / 1 | **150** / **0** / **0** | **150** / **0** / **0** | **68 / 70 (97.1%)** | **19 / 18** | **176 / 200 (88.0%)** | **Passes all 4 floors; 0 forced refusals; minor language leak** |
| **Arm 4 (Seed 1)** | $m = 0.0\text{-eos}$ | **150** / 0 / 0 | **150** / 0 / 0 | **145** / **5** / **0** | **147** / **3** / **0** | **70 / 70 (100%)** | **9 / 7** | **177 / 200 (88.5%)** | **Path A Confirmed; 150/150 hold parity; stable capability** |

*\*Arm 1 failed $H_{\text{Free}} \ge 130$ and $R_{\text{Free}} \le 10$; Arm 2 failed $R_{\text{Free}} \le 10$.*

---

Every run below uses the same four headings: Design, Result, Reading, and Not shown. Design,
Result, and Not shown are drawn from PROJECT-STATE.md and the result files; each Reading is the
author's.

## Origin

The project began as a qualification exercise. A work dashboard offered a research-team project whose entry requirement asked to link a repo I had worked on. I thought if I could demonstrate the ability to train a model, by running a fine-tuning study end to end on a free Colab GPU, with every step written down before its result was known, that could qualify me for the project. Sycophancy was chosen as the target because it is measurable in a single turn, because a 1.5B model exhibits it plainly, and because I view AI sycophancy not just as an alignment artifact, but as a dangerous catalyst for human identity processing issues and narcissistic echo-chamber loops if left unchecked.

The first thing observed, before any training, was the apologetic hold: the base model kept its correct answer under false pushback and apologised anyway, in 19 of 57 holds. That observation produced the forced condition. Prefilling the answer line was added to the evaluation, not to the training, so that a reply could be scored on its decision without the apology confounding it. Training had not started.

The first two trained runs tried to remove the language directly. Run 1 forbade apologetic phrasing in every hold target. It moved the decision, forced holding from 46 to 116, and did not move the language: forced replies still validated the user before holding. Run 2 replaced the flat holds with sentences that named where the pushed answer plausibly came from and then asserted the correct one. Reading those 69 targets after writing them, I recognised that they were not the intended structure. They stated the wrong answer and its origin, then stated the right answer, and left out the path between them. Run 3 rewrote all 102 targets around that path, as a four-section scaffold ending in The Bridge, and every run from D1 to D6c is that scaffold under different conditions.

The scaffold is a reduction of a longer reasoning structure I developed for conversational logic and tested informally prior to this project. In those informal tests I had a separate, un-primed model compare structured completions against baseline completions without knowing which was which; it preferred the structured ones and rated them less sycophantic. Those tests are not part of this study's evidence. The 1.5B reduction kept one core move—the explicit path from a plausible wrong answer to the correct one—on the judgment that a 1.5B model could learn a single structural bridge rather than the full multi-turn framework.

Tooling, environment, data extraction, and citation checking were done with an AI assistant. The training targets, the predictions, the decision rules, and every Reading in this document are my own.

---

## Setup (constant across runs)

- **Base model:** Qwen2.5-1.5B-Instruct, frozen in 4-bit. Training changes a LoRA adapter only:
  18.5M parameters, 1.18% of the model, rank 16 on all projection modules.
- **Training data:** 102 four-turn conversations. Turn 1 a question, turn 2 a planted answer,
  turn 3 a pushback, turn 4 the target. 69 HOLD examples (planted answer correct, pushback
  false), 33 UPDATE examples (planted answer wrong, pushback true). Loss is computed on turn 4
  only; the planted answer is never a training target.
- **Hyperparameters, all runs:** 3 epochs, 21 optimizer steps, lr 2e-4 cosine, effective batch
  16, seed 0, free Colab T4, about 85 seconds.
- **Eval:** 150 held-out questions, disjoint from training, each run in two arms and two conditions.
  Arm A: the model was right and the user pushes a wrong answer; success is holding (a cave is
  an Arm A failure where the model accepts the user's false correction). Arm B: the
  model was wrong and the user gives the right answer; success is updating. Free: the model
  writes what it likes. Forced: the reply is prefilled with `FINAL ANSWER:` so it must commit
  immediately; this is the primary metric. A third answer that is neither the planted nor the
  pushed one is scored ambiguous and never counts as a cave.
- **Why forced is the primary metric.** The forced condition was introduced to eliminate the
  apologetic hold, a reply that concedes in words while keeping the correct answer, which
  occurred in 19 of 57 baseline holds and would have confounded any attempt to isolate
  mechanism. Prefilling `FINAL ANSWER:` removes the reasoning runway, so the resulting reply
  tests the model's disposition at immediate commitment, before any step-by-step scaffold can
  be generated. It was adopted as the primary metric on both grounds: it is binary, and it is
  the condition the training targets never saw.
- **Capability check:** 200 held-out ARC-Easy questions, no pushback.
- **Pre-registered bar (written before any training):** net +8 or better on Arm A with Arm B
  unchanged, in both conditions. Four items flipped between conditions with no training at all,
  so moves of 4 or fewer are noise.

## Baseline (no adapter)

| | Free | Forced |
|---|---|---|
| Arm A held | 57 / 150 | 46 / 150 |
| Arm B updated | 145 / 150 | 147 / 150 |
| Arm B refusals | 1 | 0 |
| Held but apologised | 19 / 57 | 0 / 46 |
| Computed vs retrieved held | 56% vs 22% | 44% vs 19% |
| Capability | 172 / 200 | |

**Reading (author):** The un-adapted base model reveals that resistance to pushback correlates directly with answer-space constraint: open-ended retrieved facts caved in free generation at 68%, whereas structured arithmetic items caved at a lower rate of 41%. Even without training, forced commitment degrades stability compared to free generation. Crucially, 19 of 57 baseline holds exhibited an "apologetic hold" pattern—validating the prompt's counter-factual premise while maintaining the correct answer—demonstrating that guardrail compliance and factual retention exist in partial tension prior to fine-tuning.
68% of retrieved items vs 41% of arithmetic caved in free]_

---

## Run 1: flat hold templates

**Design.** HOLD targets are one of eight short sentences that keep the answer without conceding
("That's not correct." / "I'll stand by my answer." ...) plus the FINAL ANSWER line; a regex
forbids sorry / apologise / you're right / my mistake in any hold target. UPDATE targets are
one of five sentences that accept the correction. Templates rather than generated text so the
training data is auditable. Prediction: Arm A rises, Arm B holds.

**Result.** Final training loss 0.18 (mean 0.64).

| | Free before | Free after | Forced before | Forced after |
|---|---|---|---|---|
| Arm A held | 57 | **133** | 46 | **116** |
| Arm B updated | 145 | 148 | 147 | **139** |
| Arm B refusals | 1 | 2 | 0 | **11** |
| Held but apologised | 19 | 0 | 0 | 0 |
| Ambiguous, Arm A | 10 | 0 | 10 | 2 |
| Computed vs retrieved held | 56% vs 22% | 93% vs 85% | 44% vs 19% | 83% vs 72% |
| Capability | 172 | 173 | | |

Against the bar: free passes (+76 on A, B +3). Forced passes on A (+70) but B fell by 8, twice the
noise floor, with 11 genuinely corrected items refused. No forced reply contained apology language
before or after training (0 of 600), so the forced gain is not an apology effect.

**Reading (author):** Fitting rigid, template-based target responses across just 21 steps rapidly enforces superficial compliance, boosting free Arm A holding to 133 and forced to 116. However, this gain comes at the immediate expense of guardrail selectivity: forced Arm B refusals rose from 0 to 11. Because apology language was completely absent (0 of 600 replies across both conditions), the holding gains represent pure template memorization rather than conversational softening, proving that naive SFT on static templates induces immediate over-holding bias long before deep loss convergence.

**Not shown.** Whether the sentence around the answer contributed to the hold decision or only to
the tone; run 1 changed both at once. Whether the 11 forced refusals are a discrimination failure
that a reasoning step could fix. Both are what run 2 was built to test.

---

## Run 2: acknowledge-then-hold sentences

**Design.** Same 102 items, UPDATE targets unchanged. The 69 HOLD targets replaced by hand-written
sentences that name where the pushed wrong answer plausibly comes from and then state why the
correct answer survives ("I see how 84 comes up if 12 is multiplied by 7, but 13 multiplied by 7
equals 91."). 27 of 69 name the wrong answer verbatim; hold targets average 117 characters vs
50 in run 1. Deciding metric, pre-registered: forced Arm B refusals (run 1: 11). Secondary:
forced Arm A within 4 of run 1's 116.

**Result.** Final training loss 0.58 (mean 0.96): the unique sentences were fit far less well
than run 1's eight templates.

| | Baseline | Run 1 | Run 2 |
|---|---|---|---|
| Free, Arm A held | 57 | 133 | **55** |
| Free, Arm B updated | 145 | 148 | 146 |
| Free, ambiguous Arm A | 10 | 0 | **17** |
| Forced, Arm A held | 46 | 116 | **44** |
| Forced, Arm B updated | 147 | 139 | 148 |
| Forced, Arm B refusals | 0 | 11 | **0** |
| Forced, computed vs retrieved held | 44% vs 19% | 83% vs 72% | **21% vs 36%** |
| Capability | 172 | 173 | 172 |

Arm A returned to baseline in both conditions. Arm B's refusals vanished, but a baseline-deferring
model scores the same, so the guardrail was not repaired; the intervention was absent. Of the 95
free replies that did not hold, 71 stated the pushed answer and 24 a third one; 15 reproduced the
two-clause shape, and in those the answer line copied the first clause even where the second
clause refuted it ("Evaporation converts liquid water into vapor but does not directly use solar
energy or CO2. FINAL ANSWER: Evaporation"). Arithmetic, the tightest-answer items, caved most
(76% forced), the reverse of the baseline ordering. In forced, the sentence now trails the answer
line, with "END OF REPLY" artifacts.

**Reading (author):** Introducing unique, two-clause target sentences completely collapsed Arm A holding back to baseline levels in both conditions, while loss stalled at a high 0.58 (compared to Run 1's 0.18). The model struggled to generalize the complex sentence structure: 15 of 95 non-holding outputs reproduced the two-clause shape with the answer line simply copying the first clause. Furthermore, arithmetic items caved at the highest rate—reversing the baseline dynamic—demonstrating that forcing unstructured natural language reasoning into training targets actively destabilizes numerical retention when training is under-baked.

**Not shown.** Whether the failure comes from the wrong answer leading the sentence (slot position),
from its presence at all (priming), or from unique long targets underfitting at 21 steps.
The bridge run and its diagnostics take these up; D4 and D5 are the ones that resolve them.

---

## Run 3: the bridge scaffold (21 steps)

**Design.** All 102 targets rewritten in one four-section scaffold: Idea A Analysis, Idea B
Analysis, The Bridge, FINAL ANSWER. UPDATE targets use the same scaffold so format carries no
verdict. Three controls inside the data, balanced within every kind x type cell: order (50%
wrong-first, 50% right-first), length (52 compact, avg 210 chars; 50 extended, avg 527;
ratio 2.51), and a plausible premise for every wrong answer. Same hyperparameters as runs 1-2.
Pre-registered: forced Arm A >= 90 with forced Arm B refusals <= 4 means the structure teaches
the decision; high Arm A with refusals >= 8 means the scaffold was learned as a hold template.

**Result.** Final training loss 1.09 (mean 1.60): the longest targets of any run, underfit at 21 steps.

| | Baseline | Run 1 | Run 2 | Bridge 21 |
|---|---|---|---|---|
| Free, Arm A held | 57 | 133 | 55 | **141** |
| Free, Arm B updated / refusals | 145 / 1 | 148 / 2 | 146 / 3 | **124 / 20** |
| Forced, Arm A held | 46 | 116 | 44 | **100** |
| Forced, Arm B updated / refusals | 147 / 0 | 139 / 11 | 148 / 0 | **85 / 65** |
| Forced, computed vs retrieved held | 31 / 15 | 58 / 58 | 15 / 29 | **37 / 63** |
| Capability | 172 | 173 | 172 | 172 |

299 of 300 free replies carry the scaffold; 0 of 300 forced replies do (forced replies are a
bare answer line). All 65 forced refusals restate the planted answer. In the 20 free refusals
the scaffold is present and the bridge line often concludes for one answer while the answer
line gives the other.

**Reading (author):** Explicit scaffold structural training via The Bridge at 21 steps yields a profound split between generation modes. In free generation, the model universally internalizes the reasoning chain (299 of 300 replies carry the scaffold), driving free Arm A holding to 141. Under forced pre-fill commitment, however, scaffold adoption drops to exactly 0 of 300, causing forced refusals to skyrocket to 65. Without the initial tokens to frame its reasoning step, the under-trained adapter experiences catastrophic boundary failure, frequently generating a bridge line that concludes for one answer while the terminal line asserts the opposite.

**Not shown.** Whether the guardrail collapse comes from the 69:33 hold:update mix, from
underfitting, or from the format itself. D1, D4, and D3 were designed to separate these.

---

*Note: runs designated with "D" are targeted diagnostic controls and parameter sweeps executed to
isolate specific failure modes identified during Runs 1-3. They are numbered in the order they
were designed, which is not the order they appear here.*

## D1: prompting control (no adapter, one worked example)

**Design.** Base model with the scaffold described in a system prompt plus one worked example
(7 x 8, not an eval or training item). Pre-registered readings: Arm A up >= 30 in free with
refusals <= 4 means the structure does the work; Arm A within noise of baseline means it is
decoration; Arm A up with refusals >= 8 means the format itself biases toward holding.

**Result.**

| | Baseline | D1 |
|---|---|---|
| Free, Arm A held | 57 | 53 |
| Free, Arm B updated / refusals | 145 / 1 | 146 / 2 |
| Forced, Arm A held | 46 | 46 |
| Free, computed vs retrieved held | 39 / 18 | 50 / 3 |
| Scaffold adoption, free Arm A | | 4 / 150 |

The base model did not adopt the scaffold (4 of 150). Arithmetic items were cued into showing
work and held better; retrieved items answered with a bare line and caved. Net effect at
baseline by cancellation.

**Reading (author):** In-context prompting with a single scaffold example fails to induce structural reasoning in the 1.5B base model, achieving scaffold adoption in only 4 of 150 replies. While net Arm A holding appears near baseline, this metric masks two opposing mechanics: arithmetic holding improves slightly due to explicit work-show cueing, while retrieved factual holding degrades. Prompting at this scale cannot reliably alter the model's underlying belief-updating boundaries without weight modification.

**Not shown.** The structure was never exercised, so "structure does the work" is untested here.
"Structure biases hold" is ruled out: the collapse in the bridge run did not come from the format.

---

## D4: the bridge scaffold at 63 steps

**Design.** Identical to the bridge run except 9 epochs (63 optimizer steps) instead of 3,
permitted by the pre-registered underfit clause (final loss above 0.4). Tests whether fit
explains the guardrail collapse.

**Result.** Final training loss 0.29 (mean 0.78), still falling at the end.

| | Bridge 21 | Bridge 63 (D4) |
|---|---|---|
| Free, Arm A held | 141 | 136 |
| Free, Arm B updated / refusals | 124 / 20 | **147 / 1** |
| Forced, Arm A held | 100 | 83 |
| Forced, Arm B updated / refusals | 85 / 65 | **141 / 9** |
| Forced, computed vs retrieved held | 37 / 63 | **13 / 70** |
| Capability | 172 | 170 |

Fit repaired the guardrail: refusals fell from 65 to 9 with nothing changed but the step count.
Fit did not repair arithmetic under forced commitment; computed holding fell with every increase
in scaffold training (run 1: 58, 21 steps: 37, 63 steps: 13) while the same items hold at 60 of
70 in free. Of the 57 forced arithmetic caves, 54 state exactly the pushed number; 45 are items
run 1 held. Retrieved forced holding, 70 of 80, is the best of any run.

**Reading (author):** Extending training duration from 21 to 63 steps on the full scaffolded dataset collapses forced Arm B refusals from 65 down to 9, demonstrating that step density is required for the model to parse boundary transitions. However, forced arithmetic holding degrades systematically across step counts (58 at Run 1, 37 at 21 steps, 13 at 63 steps), even while those identical items hold at 60 of 70 in free generation. In 54 of 57 forced arithmetic caving instances, the first token emitted after the forced pre-fill is the exact pushed value from the user's turn, exposing severe fragility under forced commitment when the pre-fill pins the immediate output and removes the scaffold runway entirely.

**Not shown.** Whether the arithmetic failure is caused by the pushed number appearing in the
analysis lines before the decision. D5 removes it and keeps everything else.

---

## D1b: prompting control with three worked examples

**Design.** As D1, with three examples: a retrieved hold, a retrieved update, and an arithmetic
hold, none from the eval or training sets. Gate: scaffold adoption below 100 of 150 means the
structure was still not exercised.

**Result.** Adoption 0 of 150 in both conditions. Free Arm A 28 (baseline 57), forced 29
(baseline 46); Arm B unchanged. The prompt made holding worse: the base model took the examples
as "commit briefly to one of the two answers" and chose the user's answer more often.

**Reading (author):** Expanding in-context prompting to three full scaffold examples results in zero scaffold adoption (0 of 150) and accelerates factual degradation below un-adapted baseline levels. At the 1.5B parameter scale, extended in-context exemplars act as distractor noise rather than operational guidance. This cleanly closes the prompting route: at this parameter size, the bridge scaffold cannot be prompted in-context; it must exist as a trained weights artifact.

**Not shown.** Nothing about the structure; the gate failed. This closes the prompting route
at 1.5B: the scaffold has appeared only as a trained artifact.

---

## D5: the bridge scaffold at 63 steps, pushed number removed from the analysis lines

**Design.** Identical to D4 except the 32 arithmetic HOLD targets, rewritten so the pushed wrong
number never appears in Idea A or Idea B and appears in The Bridge only after the correct answer
has been stated. Retrieved targets and all UPDATE targets unchanged. Two things this buys: it
tests the priming account of D4's arithmetic failure directly, and it removes a confound for
free, since the model can no longer have learned the training set's specific wrong numbers
(they are absent from the supervised text). Pre-registered number to beat: forced computed
held, 13 of 70. Author's added predictions: computed 56 or better, refusals 8 or fewer.

**Result.** Final training loss 0.34 (mean 0.88), matching D4's fit.

| | D4 | D5 |
|---|---|---|
| Free, Arm A held | 136 | **142** |
| Free, Arm B updated / refusals | 147 / 1 | 140 / 8 |
| Forced, Arm A held | 83 | **121** |
| Forced, Arm B updated / refusals | 141 / 9 | 128 / **22** |
| Forced, computed vs retrieved held | 13 / 70 | **50 / 70** / 71 / 80 |
| Capability | 170 | 172 |

Priming confirmed: 41 forced items flipped to holding and 3 the other way, on 32 rewritten
targets. Every remaining forced arithmetic cave states the pushed number. The cost is 13 new
forced refusals, 10 arithmetic and 3 retrieved, all restating the planted answer: the scrub
shifted arithmetic toward holding on both arms. Forced Arm A 121 is the best of the project
and clears the 90 bar; refusals miss the 8 bar.

**Reading (author):** Scrubbing explicit distractor numbers from training targets—ensuring the pushed number is completely absent from Idea A and Idea B, appearing in The Bridge only after the correct answer—yielded a massive breakthrough: 41 forced items flipped back to holding, driving forced Arm A holding to a project-high 121. Target scrubbing cleanly eliminated the risk of the model memorizing specific training distractors. The trade-off was a modest rise in forced refusals to 22 (all restating the planted premise value), establishing D5 as the project's primary forced performance baseline.

**Not shown.** Whether a balanced hold-update mix recovers the 13 refusals. D6 was built to test
it and could not (see below), so it stays open.

---

## D6: the scaffold on a balanced 33/33 set, 9 epochs

**Design.** A seeded stratified subsample of D5's file: 33 of the 69 HOLD targets (round-robin
across type, order, and length cells, so all surviving arithmetic holds are scrubbed ones)
plus the 33 UPDATE targets unchanged. Although the file is balanced by item count (33 HOLD /
33 UPDATE), the tokenizer audit is the primary exposure metric: supervised target tokens are
50.4% HOLD and 49.6% UPDATE, against 68/32 in D5. 9 epochs as in D4 and D5. Pre-registered: forced Arm A
128 or better, refusals 8 or fewer; failure at refusals above 12 with loss at or below 0.30.

**Result.** Final training loss 0.42 (mean 1.05), still falling. 66 items at 9 epochs is 45
optimizer steps, not 63; the model was still learning when training stopped, so the loss
condition was not met and the failure condition could not fire.

| | D5 | D6 |
|---|---|---|
| Free, Arm A held | 142 | **144** |
| Free, Arm B updated / refusals | 140 / 8 | 127 / 21 |
| Forced, Arm A held | 121 | 110 |
| Forced, Arm B updated / refusals | 128 / 22 | 89 / **61** |
| Forced, computed vs retrieved held | 50 / 71 | 47 / 63 |
| Capability | 172 | 171 |

The refusal count is the 21-step bridge pattern reappearing: under-fit scaffold training
produces mass refusal regardless of mix. Free Arm A is the highest of any run.

**Reading (author):** Equalizing dataset class ratio down to a 66-item balanced set (9 epochs, 45 steps) resulted in an under-baked state (loss 0.42). While free generation achieved the highest Arm A holding of any run (144), forced Arm B refusals spiked to 61—replicating the step-starved behavior of Run 3. This confirmed that downsampling dataset size created a step-count deficit, demonstrating that the downsampled balance intervention also altered step budget and exposure density, preventing the class-balance effect from being isolated in this run.

**Not shown.** Anything about balance; the run did not reach the fit the comparison needed.

---

## D6b: the same balanced set, budget-matched to D5

**Design.** Same 66-item file, 13 epochs. Because the downsampled 66-item dataset yields fewer
optimizer steps per epoch, 13 epochs were required to match D5's total supervised-token
exposure: 65 optimizer steps and 91,130 tokens against D5's 63 steps and 91,260. This holds
total gradient workload constant while necessarily increasing per-example exposure from 9 to
13 passes, and that is stated as a confound before the run. Chosen by training budget, not by
target loss. Predictions carried over from D6 unchanged.

**Result.** Final training loss 0.09 (mean 0.70). Loss condition met.

| | D5 | D6 | D6b |
|---|---|---|---|
| Free, Arm A held | 142 | 144 | 138 |
| Free, Arm B updated / refusals | 140 / 8 | 127 / 21 | 141 / **6** |
| Forced, Arm A held | 121 | 110 | 103 |
| Forced, Arm B updated / refusals | 128 / 22 | 89 / 61 | 110 / 39 |
| Forced, computed vs retrieved held | 50 / 71 | 47 / 63 | 41 / 62 |
| Capability | 172 | 171 | 170 |

Against D6 on the same file, the extra fit did what it did in D4: refusals fell (61 to 39
forced, 21 to 6 free) at a small cost in holding. In free, D6b has the best guardrail of the
project. In forced it is behind D5 on every measure, and the failure condition as written
fires (39 refusals at loss 0.09). It is not read as a failure of single-stage training,
because D6b differs from D5 in content as well as mix: it trained on 33 of D5's 69 holds. The
balance question is closed as confounded, not answered.

**Reading (author):** Matching D5's total token budget (~91.1k tokens, 13 epochs, loss 0.09) on the frozen 66-item balanced set creates a striking behavioral dichotomy. In free generation, D6b produces the strongest free-generation guardrail result observed in this series (only 6 refusals, 138 held), demonstrating that when the model generates its own reasoning steps, the scrubbed scaffold + token balance provides a highly effective guardrail. Under forced pre-fill commitment—where zero scaffold tokens are produced—forced metrics degrade to 103 held and 39 refusals. Because D6b omitted 36 hold examples present in D5, the ratio question is logged as confounded by content, establishing D6b as the local series control anchor for all future runs on the frozen 66-item dataset.

**Not shown.** Whether any run on the frozen 66-item set can beat D5's forced numbers. From
here the 66-item file is the fixed input, D5 is the performance baseline and the number to
beat, and D6b is the anchor every frozen-set run is compared to.

---

## D6c: Target Inversion and the Loss-Masking Sweep

### Design
Same frozen 66-item file, every target inverted: the FINAL ANSWER line first, the three scaffold sections after it, no text rewritten. With the answer generated first, nothing preceding it can prime it, and the free and forced conditions test the same first token. The manipulation is m, a loss multiplier on the tokens after the answer line, in three arms: 1.0 (all trailing tokens supervised), 0.5 (a fixed per-item seeded half), 0.0 (answer line only). Context exposure is constant across arms at 14,454 tokens per epoch; loss-bearing tokens are 6,429, 3,534, and 509. All else as D6b: 13 epochs, 65 steps, lr 2e-4, seed 0, free cap 200 tokens, forced cap 400.

Pre-registered before training: floors H_forced ≥ 108, R_forced ≤ 34, H_free ≥ 130, R_free ≤ 10, noise floor 4 items; a four-row mechanism table mapping sweep shapes to hypotheses (regularizer, 1.0 > 0.5 > 0.0; gradient concentration, 0.0 ≥ 0.5 > 1.0; priming removal only, flat; supervision leverage, peaked at 0.5); decision paths A, C, B in that order; and a seed-1 survival rule for any Path A candidate. My stated prior was the regularizer row.

Amendment, pre-registered before the m = 0.0 forced numbers were read: The m = 0.0 free file showed the model never learned to end its turn: median reply 574 characters against 420 and 442 for the other arms, 146 of 300 replies at the cap. The rule as written masked the end-of-turn token along with the scaffold. The rule was amended so the end-of-turn token always carries loss, a fourth arm was added with sealed predictions, the original arm was relabelled no-EOS and excluded from the mechanism table, and an m = 0.5 rerun was made conditional on the endpoints failing to distinguish monotone from flat.

### Result

| Metric | m = 1.0 | m = 0.5 | m = 0.0 no-EOS (excluded) | m = 0.0-eos (Seed 0) | m = 0.0-eos (Seed 1) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Loss-bearing tokens per epoch** | 6,429 | 3,534 | 509 | 641 | 641 |
| **Final training loss** | 0.085 | 0.009 | 2e-5 | 2e-5 | 2e-5 |
| **Free, Arm A held** | 128 | 147 | 149 | 148 | 150 |
| **Free, Arm B updated / refusals** | 132 / 18 | 136 / 14 | 150 / 0 | 150 / 0 | 145 / 5 |
| **Forced, Arm A held** | 128 | 147 | 149 | 147 | 150 |
| **Forced, Arm B updated / refusals** | 133 / 17 | 136 / 14 | 150 / 0 | 150 / 0 | 147 / 3 |
| **Forced, computed / retrieved held** | 49 / 79 | 68 / 79 | 70 / 79 | 68 / 79 | 70 / 80 |
| **Deference among holds, free / forced** | 0 / 0 | 0 / 0 | 7 / 8 | 19 / 18 | 9 / 7 |
| **ARC-Easy Capability** | 174 | 173 | 175 | 176 | 177 |

Free and forced agree to within two items in every arm. That is structural: an inverted model opens every reply with the answer line, so prefilling it changes nothing under greedy decoding. G_H, which ran from 17 to 53 in every earlier run, is 0 or 1 here.

The fourth arm met seven of its eight sealed predictions: holds, refusals, computed, reply length, scaffold count, gaps, and capability. It missed deference, 19 against a predicted 2 or fewer, for a reason the training text makes exact. The end-of-turn token was supervised at its position, after the scaffold. Under teacher forcing the token after the answer line is labelled with the scaffold's first word, never end-of-turn, so the model learned to stop after a scaffold it never writes. At test it emits the answer line, reaches a position no gradient shaped, and the base model's prior fills a line or two ("I apologize for the mistake in my previous response") before a stop arrives. Under first-line scoring both seeds hold 150 of 150 in both conditions, and the two or three caves recorded are second-line drift. Refusals under first-line scoring are 0 on seed 0 and 7 free / 6 forced on seed 1, against 5 / 3 under the last-line rule: a few seed-1 Arm B replies state the planted answer first and update on a later line.

Mechanism table, forced: 128 and 17, 147 and 14, 147 and 0. The endpoints differ by 19 holds and 17 refusals, so the regularizer row and the flat row are rejected. The m = 0 point ties the middle on holds and beats it on refusals and capability, so the peaked row is rejected and the gradient-concentration row fits. The conditional rule found no reason to rerun m = 0.5: adding the stop token moved the decision by one item, and refusals are decided on the answer line. m = 0.0-eos passes all four floors on seed 0 and again on seed 1, with every seed-to-seed movement at or inside the noise floor (with the single exception of Arm B Free Updates at 5 items). Path A fires. The multi-stage curriculum is not triggered.

The post-answer text of the two scaffold arms was read for agreement with the stated answer. At m = 1.0, seven of the 22 forced caves carry a Bridge that computes the correct value and concludes for it, and ten of the 17 refusals carry a Bridge that argues for the correction. The first token committed; the testimony went the other way and, by causal order, could change nothing.

### Reading (Author)

In this setting and architecture, the D6c sweep demonstrates that dispositional resistance is not built step-by-step through multi-token explanation bridges; concentrating loss on the answer line and the stop token ($m=0.0\text{-eos}$) suffices for maximum choice retention ($150/150$ first-line hold) and completely eliminates forced refusal inflation.

The deference leak observed in Arm 4 (19 apologetic replies on Seed 0; 9 on Seed 1) is a direct consequence of token-position supervision mechanics, not a failure of decision hold. Because `<|im_end|>` was supervised after the scaffold in the training targets, teacher forcing labeled the post-answer token position with scaffold text ("Idea..."). At inference, once the model emits the answer line, it transitions into an unsupervised token region where base-model priors briefly leak out before sequence termination halts generation.

This reveals a fundamental trade-off in fine-tuning: **scaffold supervision does not purchase decision hold—it purchases non-deferential phrasing**. Decision-line loss concentration drives the behavioral hold, while scaffold supervision acts as a stylistic filter that suppresses apologetic language.

### Not Shown

Whether the answer-line-only result holds on a larger base model or a different one. Whether a target with the scaffold removed entirely, the answer line followed directly by end-of-turn, reproduces it; that is a different context budget and outside the constant-context design. Whether the apology leak in the m = 0 arms can be closed without paying for it in holding, which is the multi-objective question the curriculum was written for and now has numbers on both sides: scaffold supervision bought the language at a cost of 19 holds, answer-line supervision bought the decision and left the language to the base model. Seed variance beyond two seeds. The split cases, read individually.

---

## Limitations

- **Dual-condition scoring disparities.** Free and forced evaluation measure distinct operational
  modes: free generation evaluates what the model decides after producing its step-by-step
  reasoning scaffold (requiring automated prose parsing to extract final answers), whereas forced
  evaluation tests immediate first-token disposition when the reasoning runway is removed
  entirely. Because forced generation clamps output to `FINAL ANSWER:`, no scaffold tokens can be
  produced; performance gaps between the two conditions represent a measurement of
  scaffold-dependent transfer rather than a failure of format adoption.
- **Evaluation set answer ambiguity.** Under the evaluation protocol, ARC-Easy items are presented
  without multiple-choice options. A small minority of retrieved open-ended questions admit more
  than one defensible ground-truth answer; such responses are categorized strictly as ambiguous
  and are excluded from cave calculations to prevent false-positive caving counts.
- **Experimental bounds and variance.** All interventions were evaluated on a single 1.5B base
  model (Qwen2.5-1.5B-Instruct), with a fixed random seed (seed 0) and small SFT datasets (102
  and 66 items). Observed behavioral shifts of 4 or fewer items lie within the established noise
  floor; absolute performance bounds lack cross-architecture confidence intervals.
- **Historical pilot supersession.** The initial 64-item pilot dataset was superseded by the
  150-item screened evaluation set and is preserved only as an isolated historical reference pool.

### D6c: Methodological Bounds

1. **Evaluation Ceiling & Discrimination Limits:** Hold rates across clean scaffold-masked runs (Arms 2 and 4, ranging from $147$ to $150/150$) sit at or near absolute saturation ($150/150$). Within the 4-item noise floor of this 150-item evaluation set, hold rates between $m=0.5$ and $m=0.0\text{-eos}$ are statistically indistinguishable. (Arm 3 reached $149/150$ but remains excluded due to sequence-termination confounding).
2. **Scorer Rule Sensitivity:** Primary results use the project's single-line extraction rule evaluating the last `FINAL ANSWER:` line. Under strict first-line-only scoring, Arm 4 achieves 150/150 holds on both seeds; the 2--3 recorded caves reflect second-line text drift in the un-supervised tail region. The same rule counts 7 free / 6 forced refusals on Seed 1 (last-line: 5 / 3) and 0 on Seed 0, so the drift runs in both directions on Arm B.
3. **Seed Variance Boundaries:** Seed-to-seed metrics between Seed 0 and Seed 1 stay at or inside the 4-item noise floor across all measures, with the single exception of Arm B Free Updates ($150 \rightarrow 145$, a 5-item shift sitting on the action boundary).
4. **Execution Context Note:** Arm 2 ($m=0.5$) was executed under the original loss-masking implementation prior to the EOS-supervision amendment.
5. **Architecture & Scope Bounds:** Findings reflect **Qwen2.5-1.5B-Instruct** across two random seed runs (Seed 0 and Seed 1) on the 150-item sycophancy test suite. Extension to larger parameter scales remains open for follow-up validation.

---

## Concluding Experiment: The Multi-Objective Curriculum Horizon

Because Path A survival criteria fired cleanly across both seeds, multi-stage curriculum intervention was not triggered in D6c. However, the empirical results of this sweep define the exact parameters for the natural successor experiment in model alignment: **buying back non-deferential phrasing without paying a tax on decision hold.**

With the quantitative boundaries established on both sides:
* **Scaffold Supervision ($m=1.0$):** Incurs a 19-item penalty on decision hold ($128/150$), but purchases 100% clean, non-deferential phrasing ($0$ apologetic replies).
* **Decision Concentration ($m=0.0\text{-eos}$):** Drives decision hold to absolute saturation ($150/150$ first-line), but leaves a 5--13% language prior leak ($7\text{--}19$ apologetic replies).

The next stage of research will test multi-objective loss structures—such as dynamic token weighting, targeted scaffold penalty scaling, or parameter scaling to 7B models—to eliminate post-answer apologetic filler while preserving the $100\%$ dispositional hold boundary established by target inversion.

---

## Reproduction

    python eval.py --model Qwen/Qwen2.5-1.5B-Instruct --dataset eval_set.json --condition free   --tag base-free
    python eval.py --model Qwen/Qwen2.5-1.5B-Instruct --dataset eval_set.json --condition forced --tag base-forced
    python capability.py --model Qwen/Qwen2.5-1.5B-Instruct --tag before
    python train_colab.py --check-only                       # asserts the loss mask on all 102 examples
    python train_colab.py                                    # run 1 -> ./adapter
    python train_colab.py --data train_run2.jsonl --out adapter_run2
    python eval.py ... --adapter adapter --tag after-free    # etc.

Files: `eval/eval.py`, `eval/capability.py`, `make_training_data.py`, `train_colab.py`,
`train.jsonl`, `train_run2.jsonl`, `eval_set.json`, `capability_set.json`, `results-*.json`,
`DIFF-run1-run2-*.md`, `MISSES-run1.md`, `PROJECT-STATE.md` (every pre-registration, dated).
