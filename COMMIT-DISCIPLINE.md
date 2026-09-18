# Commit Discipline for the Amphora Research Repository

Adopted 2026-09-18, at the start of the 14B run series.

## Current phase

Training and experimentation are active. Documentation organization is paused unless a change
is necessary for correctness, reproducibility, or preventing reader confusion.

The priority is now:
1. Preserve experimental integrity.
2. Avoid changing sealed historical records.
3. Document actual results without prematurely interpreting them.
4. Keep code, configurations, result files, and model cards synchronized.

## Commit rules

### 1. Preserve the research record
- Do not rewrite sealed preregistrations, historical results, or dated decisions for stylistic
  improvement.
- Do not silently correct historical wording or numbers.
- If a historical entry is inaccurate, append a dated correction or clarification.
- Preserve the distinction between what was planned, what was run, and what was observed.

### 2. Separate experiment changes from documentation changes
- Keep training-code changes separate from documentation-only changes when practical.
- Do not mix unrelated cleanup with experimental modifications.
- Each commit should have one clear purpose.
- Do not modify training parameters, datasets, evaluation logic, or scoring rules merely to
  improve presentation.

### 3. Verify before documenting
Before adding numerical claims:
- Inspect the actual result files.
- Confirm the run identifier, seed, dataset version, training configuration, and evaluation
  conditions.
- Distinguish measured results from derived calculations.
- Record missing, failed, or unrun evaluations explicitly.
- Never infer a result from an incomplete file, summary, or earlier assumption.

### 4. Use precise experimental language
Distinguish among:
- Hypothesis
- Preregistered prediction
- Experimental design
- Measured result
- Interpretation
- Limitation
- Follow-up question

Avoid causal claims when multiple variables changed.
Do not describe a dose-response relationship when the evidence shows a step function or
plateau.
Do not call a result a replication unless the relevant conditions and independent run are
verified.

### 5. Commit format

Use:

    [type]: concise purpose

Examples:
- `train: start D6c scale comparison`
- `results: record seed-1 evaluation outputs`
- `eval: preserve forced and free scoring outputs`
- `docs: append verified run results`
- `fix: correct evaluation artifact path`

The commit body should briefly state:
- What changed
- Why it changed
- Which files or experiment it affects
- Whether it changes training, evaluation, or only documentation
- Any known limitations or unresolved questions

### 6. Before every commit

Perform a research-integrity check:

- [ ] No sealed historical record was rewritten.
- [ ] No unplanned training or evaluation variable changed silently.
- [ ] Dataset and configuration versions are identified.
- [ ] Numbers are verified against source files.
- [ ] Free and forced evaluations are not conflated.
- [ ] Observations are separated from interpretations.
- [ ] The commit does not claim more than the evidence supports.
- [ ] `git diff` and `git status` have been reviewed.

If any item cannot be verified, flag it before committing.

## Collaboration behavior

Do not automatically agree with my proposed interpretation.
Check whether the evidence supports it.
If there is a disagreement, identify:
1. The specific claim.
2. The evidence supporting it.
3. The evidence that could weaken it.
4. Whether the disagreement affects the experiment, documentation, or only wording.

Prioritize accurate research history over polished narrative.
