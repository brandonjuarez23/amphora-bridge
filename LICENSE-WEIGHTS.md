Copyright (c) 2026 Brandon Juarez-Romero.
Code: GNU General Public License v3.0 (LICENSE). Weights and data files: CC BY-SA 4.0 (this file).
Attribution under either license is to Brandon Juarez-Romero and to
https://github.com/brandonjuarez23/amphora-bridge.

# Weights and data license: CC BY-SA 4.0

The training and evaluation data files in this repository are released under CC BY-SA 4.0.

The adapter weights (`adapter_model.safetensors` and `adapter_config.json`, for every run)
are released under the same license, Creative Commons Attribution-ShareAlike 4.0
International: https://creativecommons.org/licenses/by-sa/4.0/

The code in this repository is under the GNU General Public License v3.0 (see LICENSE).
The weights are licensed separately because the GPL is written for source code and its terms
do not map cleanly onto model weights. CC BY-SA carries the same intent, attribution plus
share-alike, in a license built for non-software works. It also honors the share-alike terms
of the ARC dataset, part of the training and evaluation data, without taking a position on
whether those terms legally reach trained weights, which is unsettled.

Derivative weights must credit Brandon Juarez-Romero and this repository and be released under CC BY-SA 4.0.

Training and evaluation data sources:

- ARC (AI2 Reasoning Challenge), Allen Institute for AI, CC BY-SA 4.0
- GSM8K, OpenAI, MIT
- Synthetic arithmetic items generated in this repository

Base model: Qwen2.5-1.5B-Instruct (Alibaba Cloud), Apache-2.0. The adapter does not include
base weights.

# Third-party licenses

## GSM8K (grade-school-math), OpenAI — MIT License

Copyright (c) 2021 OpenAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
