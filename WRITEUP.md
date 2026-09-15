# Amphora: Evaluating Scaffold-Guided Reasoning and First-Token Disposition Transfer under User Pushback in 1.5B Language Models

**Abstract.** This project investigates fine-tuning methods to mitigate sycophantic caving and
false-positive guardrail refusals in Qwen2.5-1.5B-Instruct under single-turn false user pushback.
Using The Bridge structural reasoning scaffold and target-scrubbed training items, we evaluate
performance across free-form generation (scaffold-guided reasoning) and forced pre-fill commitment
(immediate first-token disposition). Results demonstrate that while target scrubbing and token-mass
balancing achieve the strongest guardrail of the trained runs in free generation (138 held,
6 refusals on D6b), forced first-token commitment reveals first-token fragility when the reasoning
runway is removed. D5 stands as the project's primary forced performance benchmark (121 held /
22 refusals), while D6b serves as the frozen-set baseline anchor (~91.1k tokens, 0.09 loss) for
subsequent runs on the frozen set.

Every run below uses the same four headings: Design, Result, Reading, and Not shown. Design,
Result, and Not shown are drawn from PROJECT-STATE.md and the result files; each Reading is the
author's.

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
