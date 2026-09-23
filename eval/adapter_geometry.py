# Copyright (c) 2026 Brandon Juarez-Romero. Part of amphora-bridge, GPL-3.0; see LICENSE.
"""
Direction of the weight change each adapter made, compared across adapters.

A LoRA adapter stores two matrices per module, A and B; the change it makes to the base
weights is their product, dW = B @ A. The pair is not unique (A -> RA with B -> BR^-1 leaves
dW alone) and every arm here started from the same seed-0 init, so comparing the stored A and
B tensors directly mostly measures the shared initialization. This script multiplies them out
and compares dW, which is the thing that acts on the model.

Each adapter's dW (all modules concatenated, or one projection type at a time) is treated as
one long vector. The output is the cosine between every pair and the angle in degrees, plus
each adapter's ||dW||. Two directions drawn at random in a space this large sit at about 90
degrees, so an angle near 90 means the two adapters changed the weights in near-independent
directions, not opposite ones (that would be 180).

Interpreting the angles needs a within-recipe yardstick: two seeds of the SAME recipe, whose
angle is the noise floor for every other comparison. Pass those as two of the adapters.

Usage:
    python eval/adapter_geometry.py --adapter m1.0=adapter_train_bridge_inv-e13-m1-s0-14b \
                                    --adapter m0.5=adapter_train_bridge_inv-e13-m0.5-eos-s0-14b \
                                    --adapter m0.0=adapter_train_bridge_inv-e13-m0-eos-s0-14b \
                                    --tag 14b-three-arms
Adapters must share a base model (same module names and shapes); the angles are not comparable
across base models, only within one.
"""

import argparse
import json
import math
import os
import re
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", action="append", required=True, metavar="LABEL=DIR",
                    help="repeat once per adapter; DIR holds adapter_model.safetensors")
    ap.add_argument("--tag", required=True, help="output goes to geometry-<tag>.json")
    ap.add_argument("--raw", action="store_true",
                    help="also report the cosine of the stored A/B tensors, which the shared "
                         "init inflates; for the record, not for reading")
    args = ap.parse_args()

    import torch
    from safetensors import safe_open

    labels, dirs = [], []
    for spec in args.adapter:
        lab, _, d = spec.partition("=")
        assert d, f"--adapter wants LABEL=DIR, got {spec!r}"
        labels.append(lab)
        dirs.append(d)
    n = len(labels)
    handles = {lab: safe_open(os.path.join(d, "adapter_model.safetensors"), framework="pt", device="cpu")
               for lab, d in zip(labels, dirs)}

    # module name -> {"A": key, "B": key}; the same modules must exist in every adapter
    mods = defaultdict(dict)
    for k in handles[labels[0]].keys():
        m = re.match(r"(.*)\.lora_([AB])\.weight$", k)
        if m:
            mods[m.group(1)][m.group(2)] = k
    names = sorted(k for k, v in mods.items() if "A" in v and "B" in v)
    for lab in labels[1:]:
        missing = [nm for nm in names if mods[nm]["A"] not in handles[lab].keys()]
        assert not missing, f"{lab} is missing {len(missing)} modules, e.g. {missing[:2]}"
    print(f"{len(names)} LoRA modules, {n} adapters")

    dot = torch.zeros(n, n, dtype=torch.float64)
    sq = torch.zeros(n, dtype=torch.float64)
    by_type = defaultdict(lambda: [torch.zeros(n, n, dtype=torch.float64), torch.zeros(n, dtype=torch.float64)])
    raw_dot = torch.zeros(n, n, dtype=torch.float64)
    raw_sq = torch.zeros(n, dtype=torch.float64)

    # one module at a time: a 14B dW is out x in, too big to hold for every module at once
    for name in names:
        rows = []
        for lab in labels:
            h = handles[lab]
            A = h.get_tensor(mods[name]["A"]).to(torch.float64)
            B = h.get_tensor(mods[name]["B"]).to(torch.float64)
            rows.append((B @ A).flatten())
        W = torch.stack(rows)
        g = W @ W.T
        s = W.pow(2).sum(1)
        dot += g
        sq += s
        t = name.split(".")[-1]          # q_proj, k_proj, ..., down_proj
        by_type[t][0] += g
        by_type[t][1] += s
        if args.raw:
            R = torch.stack([torch.cat([handles[lab].get_tensor(mods[name]["A"]).flatten(),
                                        handles[lab].get_tensor(mods[name]["B"]).flatten()]).to(torch.float64)
                             for lab in labels])
            raw_dot += R @ R.T
            raw_sq += R.pow(2).sum(1)

    def matrices(d, s):
        norm = s.sqrt()
        cos = (d / (norm[:, None] * norm[None, :])).clamp(-1.0, 1.0)
        deg = torch.rad2deg(torch.acos(cos))
        return cos, deg, norm

    def show(title, d, s):
        cos, deg, norm = matrices(d, s)
        print(f"\n--- {title} ---")
        print(f"{'':10}" + "".join(f"{l:>10}" for l in labels) + "      ||dW||")
        for i, l in enumerate(labels):
            print(f"{l:10}" + "".join(f"{cos[i, j].item():10.4f}" for j in range(n)) + f"  {norm[i].item():10.3f}")
        print("angles (deg): " + ", ".join(f"{labels[i]}/{labels[j]} {deg[i, j].item():.1f}"
                                           for i in range(n) for j in range(i + 1, n)))
        return {"cosine": cos.tolist(), "degrees": deg.tolist(), "norm": norm.tolist()}

    out = {"labels": labels, "adapters": dict(zip(labels, dirs)), "modules": len(names),
           "all": show("dW = B@A, all modules concatenated", dot, sq),
           "by_projection": {}}
    for t in sorted(by_type):
        out["by_projection"][t] = show(f"dW, {t} only", *by_type[t])
    if args.raw:
        out["raw_AB"] = show("stored A/B tensors (shared init inflates this; for the record)", raw_dot, raw_sq)

    path = f"geometry-{args.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote " + os.path.abspath(path))


if __name__ == "__main__":
    main()
