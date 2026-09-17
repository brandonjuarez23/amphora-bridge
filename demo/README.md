---
title: Amphora
emoji: 🌉
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.6.0
app_file: app.py
pinned: false
license: cc-by-sa-4.0
---

# Amphora demo

Interactive chat with the two released adapters on Qwen2.5-1.5B-Instruct, switchable mid-conversation:
[Amphora-1.5B-Decision](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Decision) (answer line only
supervised) and [Amphora-1.5B-Bridge](https://huggingface.co/brandonjuarez23/Amphora-1.5B-Bridge)
(explanation half-supervised). Both hold a correct answer under false user pushback and accept a true
correction; they differ in what comes after the answer.

`app.py` runs as a Hugging Face Space or locally (`python app.py`, needs a GPU for comfortable speed).
`colab_demo.ipynb` is the same app as a Colab notebook that prints a shareable public link.

Faithful to the published evaluation: every user turn carries the training suffix, assistant turns are
fed back without display markup, and decoding is greedy unless the sampling box is ticked.

Project and full record: https://github.com/brandonjuarez23/amphora-bridge
