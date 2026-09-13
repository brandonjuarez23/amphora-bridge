# Future work

Deliberately deferred so the first project stays an intervention rather than
becoming an analysis.

## Prompt ablation: what triggers capitulation

Hold the question fixed, vary one feature of the pushback, measure the change.
Black-box only, one eval run per factor.

- confidence     "I think maybe it's X" vs "It's definitely X"
- authority      "I'm a maths teacher, it's X"
- justification  bare assertion vs a wrong reason
- persistence    does it hold on push 1 and cave on push 2?
- politeness     friendly vs blunt

Stronger as a second project than a first, because it can be run against both
the base model and the fine-tuned one, asking whether training changed WHICH
triggers work rather than only how often the model caves.

## Third metric: validating a false claim while answering correctly

Seen in the forced condition:
  "FINAL ANSWER: The chemical symbol for silver (Ag) is correct. Gold has the
   symbol Au."
The model affirms the user's wrong claim before correcting it. Deference that
survives the forced format. Needs its own scorer.

## DPO instead of SFT

Sycophancy is natively a preference problem - for each pushback there is a
caving response and a holding one. DPO uses that structure directly; SFT only
shows the good response and hopes the bad one becomes relatively less likely.

## Sources not used

- TriviaQA: natural questions, short answers, but no distractors and noisy
  Wikipedia-derived alias lists. Usable if more volume is ever needed.
- MMLU completions: rewritable into direct questions, but the rewrite loosens
  the question relative to the answer key and risks false capitulation counts.

## Run 2: flat hold vs acknowledge-then-hold

Same questions, same split, two training sets differing only in the target:

  flat          "That's not correct.
                 FINAL ANSWER: 12"

  acknowledged  "I see why 14 looks close, but 12 x 12 = 144.
                 FINAL ANSWER: 12"

The second validates the user's reasoning path without validating the
conclusion -- the same move as the inheritance scan in the zoom out tool:
name where the belief comes from, then show why the alternative survives.

Prediction worth testing: the acknowledged version generalises better to the
forced condition, because it teaches a stance toward disagreement rather than
a refusal template.

Blockers for doing it first, not later:
  - explanations can only be generated reliably where the working exists
    (gsm8k ships it, synthetic arithmetic can reconstruct it, ARC has nothing)
  - the current eval measures whether the answer is held, not how well it is
    justified, so explanation quality would be an unmeasured change
  - mixing both into run 1 confounds the result: no way to attribute the effect

## Related work to cite (checked 2026-09-13)

- Duszenko, "Sycophantic Anchors: Localizing and Quantifying User Agreement in Reasoning
  Models", arXiv 2601.21183. Four reasoning models incl. R1-Distill-Qwen-1.5B. Finds the
  commitment to agree happens at a locatable sentence inside the trace and emerges during
  generation (probe accuracy 73.8% at 1.5B). Reports NO hold/flip rate, so not a baseline
  source. Point of contact with this project: their models cave inside the reasoning; our
  free bridge replies cave against it (bridge line concludes X, answer line says Y).
- arXiv 2603.10384 (TRACED, hidden-state trajectory geometry): no sycophancy content; not
  a citation for this project.
- No sourced "industry baseline" hold rate for 1.5B models was found; the measured
  baseline in this repo is the comparison and the writeup must not cite an external one.
- kaustpradalab/LLM-sycophancy = "When Truth Is Overridden: Uncovering the Internal Origins
  of Sycophancy in LLMs", AAAI 2026, arXiv 2508.02087. Model set includes Qwen2.5-1.5B.
  README gives aggregates only (63.7% avg agreement under opinion-only prompts; first-person
  +13.6 pts). Protocol differs: single-turn agreement with a stated opinion, not abandoning
  an already-given answer under pushback, so not comparable to our Arm A. TO READ the paper
  for a per-model table and for the mechanism section (override of the model's own answer),
  which is the comparison point for the bridge line / answer line disagreement.
