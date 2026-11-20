# Qwen3.8-Flash-Next (125B MoE) on Arc Pro B70 + Xeon 676X with XeStrata, 2026-11-06

Rig: [`xeon-676x-4x-b70`](../../rigs/xeon-676x-4x-b70/) · intelinside.ai [/rigs/18](https://www.intelinside.ai/rigs/18)
Runtime: [XeStrata xe0.2.2-1](../../builds/xestrata-xe0.2.2-1/) · intelinside.ai [custom build 30](https://www.intelinside.ai/runtimes/strata/custom/30) · Scope: one 10-minute soak per configuration
(114 and 121 requests), one request at a time, card power and temperature logged.

**This is a CPU + GPU result.** The model's most-used experts sit in GPU memory; the others are computed on the Xeon
from system RAM. **Decoding is always speculative** (MTP, 4 drafts per step): XeStrata cannot run these packs without
it, so there is no non-speculative baseline. Speed therefore depends on the text being generated, and each result
gives the range.

## Weights

[ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF @ ed59f920](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/tree/ed59f92082b1e93c0e96d60a8b11aab089b52f09), `IQ3_S/` (two shards, 83.6 GB):

| file | bytes | sha256 (= Hugging Face LFS id) |
|---|---|---|
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` | 54,817,524,224 | `4c1eb2ceb4915e1192f4f386021897bde56a97f40a0bb78bb86465e0f7d2aca3` |
| `Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` | 28,800,138,432 | `316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113` |

## Posted results

| Configuration | GPUs | Decode, 1 request (median) | range (per request) | TTFT, short prompt | Posted |
|---|---|---|---|---|---|
| [`xestrata-iq3s-1c`](xestrata-iq3s-1c/) | 1× B70 (`0d:00.0`) + CPU | **89.1 tok/s** | 72.4 – 128.6 | 269 ms | [/results/378](https://www.intelinside.ai/results/378) |
| [`xestrata-iq3s-2c-k24`](xestrata-iq3s-2c-k24/) | 2× B70 (`0d:00.0`, `90:00.0`), layers split at 24 + CPU | **94.7 tok/s** | 74.3 – 126.5 | 286 ms | [/results/379](https://www.intelinside.ai/results/379) |

Per prompt (median decode, tok/s), showing how much the text matters:

| prompt | output tokens (median) | 1 card | 2 cards |
|---|---|---|---|
| `fix_bug` (short code fix) | 120 / 83 | 89.1 | 94.7 |
| `parse_iso` (write a function + tests) | 869 / 772 | 102.0 | 106.5 |
| `invoice_extract` (text → JSON) | 167 | 126.7 | 126.3 |
| `incident_log` (summarise a 7,667-token log) | 328 / 323 | 82.7 | 85.9 |
| `transistor_history` (300-word essay) | 451 / 448 | 76.9 | 79.2 |

Draft acceptance over the soak: 68.1% (1 card), 74.3% (2 cards).

Prompt processing, from the needle test in the same session (one request per size, nothing cached, needle found 4/4):

| input tokens | TTFT, 1 card | prompt tok/s, 1 card | TTFT, 2 cards | prompt tok/s, 2 cards |
|---|---|---|---|---|
| 7,822 | 4.35 s | 1,798 | 4.66 s | 1,678 |
| 31,896 | 13.16 s | 2,424 | 13.35 s | 2,389 |
| 63,856 | 26.58 s | 2,402 | 20.21 s | 3,160 |
| 89,615 | 38.13 s | 2,350 | 26.25 s | 3,414 |

Card power over the 10-minute soak (from the cards' energy counters): 226.3 W on the single card (it sat at its
230 W limit, peak 94 °C); 155.3 W + 166.7 W on the two cards. CPU power was not measured, and in this setup the CPU
does real work. Unused cards idled at about 45 W.

## How it was measured

`harness/xetest.py` (the exact file used, sha256 `bf44da09…`):

- `soak --duration 600 --effort none`: rotates five fixed prompts (see the table above) through
  `/v1/chat/completions`, streamed, thinking off (`reasoning_effort: "none"`; no request produced reasoning text),
  temperature 0.6 / top_p 0.95 / top_k 20 with a per-request seed, the server's default presence penalty (1.5 for
  this model with thinking off), up to 1024 output tokens (reached by 7 of 114 and 4 of 121 requests). A greedy
  canary runs every 5 minutes.
- Decode per request = `completion_tokens / (total time − time to first token)`, measured at the client
  ("wire"). The server's own per-request figure (`predicted_per_second` in `logs/soak.jsonl`) agrees within 2%
  (median 87.75 and 93.2).
- `needle`: a unique document per size (so no prompt cache can help) with a code planted at 63% depth.

A later version of `xetest.py` changed two lines so it can also parse vLLM's final `"choices": []` chunk. XeStrata never
sends that chunk, so the change does not affect these runs; it lives in [`harness/`](../../harness/).

## What is in each configuration folder

| File | Content |
|---|---|
| `engine-config.json` | XeStrata's engine arguments for this configuration (paths are inside the container). |
| `harness/xetest.py` | The test script. |
| `logs/soak.jsonl` | One record per request: timings, token counts, the server's timings, the model's answer. |
| `logs/soak-summary.json`, `logs/summary.txt` | The script's own summary. |
| `logs/needle.jsonl` | Prompt-processing records. |
| `logs/*-meta.json` | Arguments and the server's `/v1/status` at the start (engine `xe0.2.2-1`, context 262,144). |
| `logs/engine-startup.log` | Engine start lines: GPU, KV placement, expert cache size, engine version. |
| `logs/gpu-telemetry.csv` | Per-card energy, fan and temperatures every 5 s. |
| `result.json` | The body submitted to intelinside.ai and the id it returned. |

## Not posted

- Earlier XeStrata releases and GPU driver versions from the same campaign (superseded by this one).
- Runs with thinking on, and the UD-Q4_K_XL quantisation: measured with a different, engine-reported method.
