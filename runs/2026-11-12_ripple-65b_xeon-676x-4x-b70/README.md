# Ripple-65B Preview on 4× Arc Pro B70 (Xeon 676X), 2026-11-12

Rig: [`xeon-676x-4x-b70`](../../rigs/xeon-676x-4x-b70/) · intelinside.ai [/rigs/18](https://www.intelinside.ai/rigs/18)
Scope: **smoke** — 2 measured runs per configuration, no power or thermal logging (see [METHODOLOGY](../../METHODOLOGY.md)).

The model (about 65B parameters) does not fit on one 32 GB card at 4-bit, so every configuration here
spreads it across all four cards.

## Posted results

| Configuration | Runtime | Weights | Decode, 1 request | TTFT (warm) | Posted |
|---|---|---|---|---|---|
| [`vllm-gptq-tp4`](vllm-gptq-tp4/) | vLLM 0.34.0rc1.dev270 ([build](../../builds/vllm-xpu-0.34.0rc1.dev270-3bc0f430/)), tensor parallel ×4 | [ModelCloud/Ripple-65B-Preview-GPTQ-W4A16-v2 @ cd5a62d7](https://huggingface.co/ModelCloud/Ripple-65B-Preview-GPTQ-W4A16-v2/tree/cd5a62d7c6bfde0b9752e2857dbd6b281a2f1778) | **43.6 tok/s** | 186 ms | [/results/359](https://www.intelinside.ai/results/359) |
| [`llamacpp-q4km-layer`](llamacpp-q4km-layer/) | llama.cpp b12314 SYCL ([build](../../builds/llamacpp-sycl-b12314/)), layer split ×4 | [AtomicChat/Ripple-65B-Preview-GGUF @ df550a71](https://huggingface.co/AtomicChat/Ripple-65B-Preview-GGUF/tree/df550a7178a87bbfb6ee2bdbd37603c553d536ee), Q4_K_M | **13.0 tok/s** | 271 ms | [/results/335](https://www.intelinside.ai/results/335) |

The two rows use different tests (forced-length synthetic vs realistic chat tasks — see
[METHODOLOGY](../../METHODOLOGY.md#two-kinds-of-decode-test)) and different quantisations, so they are
not a like-for-like runtime comparison. The large gap is mostly structural: tensor parallelism has all four
cards work on every token, while a layer split runs the cards one after another.

## What is in each configuration folder

| File | Content |
|---|---|
| `launch.yml` | The server configuration, as a Docker Compose service. |
| `harness/` | The exact test script used. |
| `logs/` | Raw script output (one line per measured run) and server log excerpts. |
| `result.json` | The body submitted to intelinside.ai and the id it returned. |

## How the numbers trace to the logs

**vllm-gptq-tp4** — `logs/perf.log`, `c=1` lines: 43.58 and 43.54 tok/s per stream (TPOT 22.9–23.0 ms),
posted as 43.6. TTFT 344 ms was the first (cold) request, 186 ms the warm one. Independent cross-check:
`logs/server-throughput-single-request.log` holds every 10-second server window with exactly one running
request in a separate session of the same build and configuration (`non-default args` identical); median
43.0 tok/s over 57 windows. Low values in that file (down to 9.3) are windows where a request started or
ended part-way through. `logs/server-startup.log` shows the version, the arguments, tensor-parallel world
size 4, 8.79 GiB of weights per card, and graph capture.

**llamacpp-q4km-layer** — `logs/realdecode.log`, `c=1` lines: 13.0 tok/s on both runs (446 and 350 tokens).
TTFT 18.8 s on the cold first request (first request after the server started; the cause was not
isolated); 271 ms warm.
`logs/server-startup.log` shows the server turning flash attention off for this split
(`Flash Attention over K/V rows not supported, set to disabled`).

## Not posted

- The `c=4` lines in both logs: several requests at once. Their aggregate figures are kept as raw data
  but are not single-request numbers and were not posted.
- Speculative decoding (DFlash) and pipeline-parallel runs from the same session: content-dependent or
  using patched builds, so held back until they can be published with full context.
