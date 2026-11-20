# intel-llm-bench

Evidence for local LLM inference results measured on Intel hardware — mostly Intel Arc Pro B70 GPUs —
and posted to [intelinside.ai](https://www.intelinside.ai/users/bhannath69).

Each posted result links here. The folder it links to holds everything needed to understand and check
that one number: the launch configuration, the exact test script, the raw measurement lines, the
relevant server log excerpts, and the request body that was submitted.

## How to read this repo

| Folder | What it holds |
|---|---|
| [`runs/`](runs/) | One folder per test session, named `<date>_<model>_<rig>`. Inside it, one sub-folder per posted configuration. **Start here if you came from a result page.** |
| [`rigs/`](rigs/) | The machines: board, CPU, memory, GPUs, PCIe links, firmware and OS. |
| [`builds/`](builds/) | The runtime builds (vLLM, llama.cpp, …): upstream commit, how the image was built, and its component versions. |
| [`harness/`](harness/) | The latest version of each test script. Every run keeps its own copy of the exact script it used. |
| [`METHODOLOGY.md`](METHODOLOGY.md) | What the numbers mean and how they were measured. |
| [`REDACTION.md`](REDACTION.md) | What was removed from published logs and configs, and why. |

Links from intelinside.ai point at a specific commit, so what a result cites cannot change afterwards.
Corrections are added as new notes, never by rewriting a published run.

## Results

| Date | Model | Rig | Configuration | Decode, 1 request | intelinside.ai |
|---|---|---|---|---|---|
| 2026-11-12 | Ripple-65B Preview GPTQ 4-bit | Xeon 676X + 4× Arc Pro B70 | [vLLM, tensor parallel ×4](runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/vllm-gptq-tp4/) | 43.6 tok/s | [/results/359](https://www.intelinside.ai/results/359) |
| 2026-11-12 | Ripple-65B Preview Q4_K_M | Xeon 676X + 4× Arc Pro B70 | [llama.cpp SYCL, layer split ×4](runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/llamacpp-q4km-layer/) | 13.0 tok/s | [/results/335](https://www.intelinside.ai/results/335) |
| 2026-11-06 | Qwen3.8-Flash-Next IQ3_S | Xeon 676X + 1× Arc Pro B70 (CPU + GPU) | [XeStrata, MTP speculative](runs/2026-11-06_qwen3-8-flash-next_xeon-676x-4x-b70/xestrata-iq3s-1c/) | 89.1 tok/s (median; 72–129) | [/results/378](https://www.intelinside.ai/results/378) |
| 2026-11-06 | Qwen3.8-Flash-Next IQ3_S | Xeon 676X + 2× Arc Pro B70 (CPU + GPU) | [XeStrata, layer split ×2, MTP speculative](runs/2026-11-06_qwen3-8-flash-next_xeon-676x-4x-b70/xestrata-iq3s-2c-k24/) | 94.7 tok/s (median; 74–127) | [/results/379](https://www.intelinside.ai/results/379) |

## Ground rules

- Only results measured on our own hardware. No numbers copied from vendors, reviews or other people.
- Intel hardware only.
- Decode speed is reported for **one request at a time** unless a result says otherwise. Throughput from
  several concurrent requests is never presented as a single-stream number.
- Every caveat that moves a number — speculative decoding, cache settings, split mode, flash attention —
  is stated in the result's flags and notes.

## Questions and corrections

Open an [issue](https://github.com/bhannath69/intel-llm-bench/issues). Pull requests are welcome for
typos and broken links; measurements are only changed by a new run.

## Licence

Scripts and tools: [MIT](LICENSE). Data, logs and documentation: [CC BY 4.0](LICENSE-DATA).
Model names and trademarks belong to their owners.
