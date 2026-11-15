# Methodology

## Terms

| Term | Meaning here |
|---|---|
| **Decode tok/s** | Output tokens per second for one request, after the first token, measured at the client from the streamed response. The exact formula belongs to the script and is stated per script below (the two differ by one token, ≈ 0.25% at 400 output tokens). |
| **TTFT** | Time to first token: request sent → first output token received, measured at the client. Results report the warm value and mention the cold (first request after boot) value in the notes. |
| **Prompt tok/s** | Prompt (prefill) processing speed. Only reported when measured on purpose with a prompt long enough that fixed overhead does not dominate (≥ 2K tokens, unique so no prefix cache can help), or by `llama-bench -p 512`. Never back-calculated from a short-prompt TTFT. |
| **Concurrency** | Number of requests in flight. Posted decode numbers use concurrency 1 unless stated. |
| **Repeats** | Number of measured runs behind the posted number. |
| **Stock / custom runtime** | Stock = released or upstream source built without code changes, however configured. Any patch makes it a custom runtime, registered and named on intelinside.ai. |

## How runs are done

- The server is launched with the configuration in the run's `launch.yml`, on the cards listed in the rig.
- The test script in the run's `harness/` folder sends requests to the server's OpenAI-compatible API
  and prints one line per measured run. Those lines are kept verbatim in `logs/`.
- Where the server itself logs throughput, the relevant lines are kept as an independent cross-check.
- The submitted result body is kept as `result.json`, together with the id intelinside.ai returned.

## Two kinds of decode test

- **Forced-length synthetic** (`perf.py`): a fixed 420-token prompt of random words, exactly 256 output
  tokens (`min_tokens = max_tokens = 256`, `ignore_eos`), greedy. Content-independent, so it is the
  right test for runtimes without speculative decoding.
  Decode = `1 / TPOT`, with `TPOT = (end of stream − first token) / (output tokens − 1)`.
- **Realistic chat tasks** (`realdecode.py`): four fixed code and prose prompts through the chat API,
  streamed, temperature 0.6, top_p 0.95, up to 1500 output tokens. Used where decode speed could depend
  on content, and for runtimes whose chat template matters.
  Decode = `output tokens / (last token − first token)`, where output tokens is the server-reported
  `completion_tokens` and includes any reasoning tokens. Single-request runs use a different prompt per
  trial, so the two trials are not repeats of the same text.

Speculative decoding results depend heavily on content: the same setup can range several-fold between
prompts. They are only posted with that range stated, or not at all.

## Scope labels

Each run README states its scope. **Smoke scope** means a small number of repeats (usually 2) and no
power or thermal logging; treat those numbers as indicative, with a few percent of run-to-run noise.
