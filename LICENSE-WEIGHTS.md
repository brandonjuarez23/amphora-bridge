# Weights license: CC BY-SA 4.0

The adapter weights in this project (`adapter_model.safetensors` and `adapter_config.json`,
for every run) are released under the Creative Commons Attribution-ShareAlike 4.0
International license: https://creativecommons.org/licenses/by-sa/4.0/

The code in this repository is under the GNU General Public License v3.0 (see LICENSE).
The weights are licensed separately because the GPL is written for source code and its terms
do not map cleanly onto model weights. CC BY-SA carries the same intent, attribution plus
share-alike, in a license built for non-software works. It also honors the share-alike terms
of the ARC dataset, part of the training and evaluation data, without taking a position on
whether those terms legally reach trained weights, which is unsettled.

Derivative weights must credit this repository and be released under CC BY-SA 4.0.

Training and evaluation data sources:
- ARC (AI2 Reasoning Challenge), Allen Institute for AI, CC BY-SA 4.0
- GSM8K, OpenAI, MIT
- Synthetic arithmetic items generated in this repository

Base model: Qwen2.5-1.5B-Instruct (Alibaba Cloud), Apache-2.0. The adapter does not include
base weights.
