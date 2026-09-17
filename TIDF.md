# Target-Inverted Dispositional Fine-Tuning (TIDF-1.0.5)

Findings, Interpretation, and Application Standard

Copyright (c) 2026 Brandon Juarez-Romero. CC BY-SA 4.0. Reference implementation:
https://github.com/brandonjuarez23/amphora-bridge (D6c run series).

## 1. Scope, Executive Summary, and Purpose

This standard formalizes the empirical findings, procedural rules, and application guidelines
for Target-Inverted Dispositional Fine-Tuning (TIDF) based on the D6c experimental run series.

TIDF is a structured fine-tuning framework that reorders generation targets by placing a
decision commitment (`FINAL ANSWER: <value>`) before the post-hoc reasoning or explanatory
scaffold.

**Key empirical takeaways (D6c)**

- **Decision-line concentration.** Concentrating loss supervision exclusively on the decision
  line and its terminating end-of-sequence token (EOS) achieved the highest first-line decision
  hold under adversarial pushback.
- **Scaffold supervision and trade-offs.** Scaffold supervision did not improve first-line
  decision hold in the tested 1.5B configuration. It served a distinct behavioral function: it
  eliminated apologetic or deferential post-answer language during multi-turn interactions
  (0 apologetic replies), at the cost of refusing some valid user corrections (14 / 150 true
  corrections refused).
- **Role of EOS supervision.** Assigning the EOS token to the decision set ($T_{\text{Answer}}$)
  is strictly necessary to prevent run-on generation and produce an operational model.
- **Supervision allocation.** TIDF should be understood as a practical technique for
  controlling how supervision budget is split between decision commitment and post-answer
  conversational behavior, not as a claim that explanation scaffolds are inherently unnecessary.

## 2. Core TIDF Structure and Dataset Rules

TIDF training records follow a four-turn exchange designed to balance HOLD (resisting false
pushback) and UPDATE (accepting valid corrections) behaviors:

```text
<|im_start|>user
[Prompt] + suffix<|im_end|>
<|im_start|>assistant
FINAL ANSWER: [Planted answer]<|im_end|>            <- never supervised (-100)
<|im_start|>user
[Pushback] + suffix<|im_end|>
<|im_start|>assistant
FINAL ANSWER: [Verified answer]                      <- the ONLY supervised turn
Idea A Analysis: [...]
Idea B Analysis: [...]
The Bridge: [...]<|im_end|>
```

### 2.1 Set partitioning contract

Supervised tokens ($T_{\text{Supervised}}$), on the final assistant turn only, are partitioned
into two mutually exclusive sets:

$$T_{\text{Answer}} \cap T_{\text{Scaffold}} = \varnothing \quad \text{and} \quad T_{\text{Answer}} \cup T_{\text{Scaffold}} = T_{\text{Supervised}}$$

### 2.2 Mandatory procedural rules

- **Final assistant turn isolation.** Supervision is restricted exclusively to the final
  assistant turn. All prior turns (the prompt, the planted answer, and the user pushback) are
  completely masked out (`ignore_index = -100`).
- **Explicit EOS assignment.** The end-of-sequence token terminating the response must be
  explicitly assigned to the decision set: $\text{EOS} \in T_{\text{Answer}}$.
- **Hold versus update balance.** A conforming dataset balances two distinct multi-turn
  conditions:
  - HOLD examples: the planted answer is correct and the user pushback is false; the verified
    answer repeats the planted answer.
  - UPDATE examples: the planted answer is deliberately wrong and the user pushback is true;
    the verified answer replaces the planted answer with the true correction. The planted
    answer must never appear inside the supervised span of an UPDATE example.
- **Causal ordering constraint.** The sequence enforces
  $X_{\text{Prompt}} \rightarrow T_{\text{Answer}} \rightarrow T_{\text{Scaffold}}$. Within a
  single generation turn, scaffold tokens cannot causally influence the already-generated
  answer: $T_{\text{Scaffold}} \not\rightarrow T_{\text{Answer}}$.

## 3. Evaluated Supervision Profiles (D6c Implementation)

Scaffold supervision is controlled by a stochastic Bernoulli retention mask parameter
$m \in [0.0, 1.0]$. For each token $t \in T_{\text{Scaffold}}$, a mask bit
$z_t \sim \text{Bernoulli}(m)$ is sampled using a deterministic per-item seed.

The loss is the token-mean cross-entropy over the tokens receiving supervision:

$$\mathcal{L}_{\text{TIDF}} = \frac{\displaystyle\sum_{t \in T_{\text{Answer}}} \ell_t + \displaystyle\sum_{t \in T_{\text{Scaffold}}} z_t \ell_t}{|T_{\text{Answer}}| + \displaystyle\sum_{t \in T_{\text{Scaffold}}} z_t}$$

| Profile | Retention parameter $m$ | Decision supervision ($T_{\text{Answer}} \cup \{\text{EOS}\}$) | Scaffold supervision ($T_{\text{Scaffold}}$) | Primary behavioral role and observed metrics (1.5B, D6c) |
|---|---|---|---|---|
| TIDF-DECISION | 0.0 | full weight ($w_t = 1$) | 0% retained ($z_t = 0$) | Highest decision hold (147–150 / 150 forced, two seeds); 0–3 true corrections refused; answer line plus stop, with untrained base-model text sometimes following (7–19 replies). |
| TIDF-BRIDGE | 0.5 | full weight ($w_t = 1$) | ≈50% stochastically retained ($z_t \sim \text{Bernoulli}(0.5)$) | Retains the explanation; 147 / 150 held; 0 apologetic replies; 14 / 150 true corrections refused. |
| TIDF-BASELINE | 1.0 | full weight ($w_t = 1$) | 100% retained ($z_t = 1$) | Standard SFT control: full supervision of the entire final turn. Lowest decision hold under false pushback (128 / 150); 17 / 150 true corrections refused. |

Note: as established in D6c, $m = 0.5$ is stochastic subset retention at full token weight,
not a continuous 0.5 loss scalar across every scaffold token.

## 4. Findings Interpretation Framework

D6c results are interpreted across three distinct tiers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        1. OBSERVED BEHAVIOR                            │
│  Concentrated decision loss (m = 0.0) yields the highest first-line    │
│  hold. Scaffold retention (m = 0.5) eliminates apologetic post-answer  │
│  text at a cost in refused true corrections.                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      2. MECHANISTIC INTERPRETATION                     │
│  T_Scaffold ↛ T_Answer guarantees unidirectional sequence generation.  │
│  It does NOT prove complete internal feature decoupling inside MLPs.   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        3. PRACTICAL APPLICATION                        │
│  Use m = 0.0 when the decision matters and the explanation does not.   │
│  Use m = 0.5 when diagnostic explanations are required without         │
│  apologetic folding, accepting more refused corrections.               │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Observed behavior (D6c data)

- **Decision-line concentration.** Concentrating loss updates on $T_{\text{Answer}}$
  ($m = 0.0$) produced the highest decision hold under false user pushback (147–150 / 150).
- **Deference suppression and refusal cost.** Scaffold supervision ($m = 0.5$) completely
  suppressed apologetic post-answer text (0 apologetic replies) and carried a refusal rate of
  14 / 150 on true user corrections.
- **Convergence.** Free-generation and forced-prompting evaluations agree to within one to two
  items in every inverted arm: answer-first generation commits the model before any
  justification text is emitted.

### 4.2 Mechanistic limits and causal boundaries

- Sequence order guarantees $T_{\text{Scaffold}} \not\rightarrow T_{\text{Answer}}$ in
  left-to-right generation.
- Sequence order does not prove that internal activation states or attention heads are
  independent. Observed behavioral shifts may stem from changes in token exposure,
  optimization pressure balance, or loss gradient density during training.

## 5. Scope Boundaries, Seed Count, and Pre-Registration

### 5.1 Experimental scope boundaries and seeds

The empirical conclusions of TIDF-1.0.5 remain bounded by:

- **Model scale.** Evaluated on one 1.5B base model (Qwen2.5-1.5B-Instruct).
- **Dataset and task profile.** Multi-turn hold/update evaluation on factual, arithmetic, and
  grade-school word-problem items.
- **Seed count.** The TIDF-DECISION ($m = 0.0$) profile was evaluated on two random seeds
  (147 / 150 and 150 / 150 forced holds). Every other arm in the project, TIDF-BRIDGE and
  TIDF-BASELINE included, was evaluated on one seed.

### 5.2 Hypothesis for the 14B scaling run

The primary hypothesis for the next phase is that the empirical ordering observed at 1.5B
replicates at 14B:

$$\text{Decision holds:} \quad m_{0.0} \ge m_{0.5} > m_{1.0}$$

$$\text{Refusals on true corrections:} \quad m_{0.0} < m_{0.5} < m_{1.0}$$

The 1.5B reference values are 147–150 / 147 / 128 for holds and 0–3 / 14 / 17 for refusals.
These are observations, not predictions for 14B. The sealed pre-registration for the 14B run
states the ordering above together with what confirms it: endpoint separation on each metric
at or above the noise floor, with the middle arm permitted to tie the $m = 0.0$ endpoint on
holds as it did at 1.5B. The noise floor and pass floors are set from the 14B base model's own
screening and baseline evaluation, and are committed to the project record before training.
