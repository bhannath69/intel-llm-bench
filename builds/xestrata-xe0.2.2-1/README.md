# XeStrata xe0.2.2-1 (SYCL / Level Zero), Intel compute-runtime 26.40

[XeStrata](https://github.com/MistVVK/XeStrata) is a SYCL port of [Strata](https://github.com/Niko1221/Strata) for
Intel GPUs. It runs Qwen3.8-Flash-Next (125B MoE, about 6B active per token) by keeping the most-used experts in GPU
memory and computing the rest on the CPU from system RAM, with a multi-token-prediction (MTP) draft head for
speculative decoding.

Upstream release used without changes. On intelinside.ai this is a custom build on the `strata` base runtime.

| | |
|---|---|
| Release | [xe0.2.2-1](https://github.com/MistVVK/XeStrata/releases/tag/xe0.2.2-1) (2026-10-24), tag commit [`ad821cdf1a4c50cc0bb92d2b8dc152f76daba61b`](https://github.com/MistVVK/XeStrata/commit/ad821cdf1a4c50cc0bb92d2b8dc152f76daba61b) |
| Package | `xestrata-contrib-cuda13.1_0.2.2-1_amd64.deb`, sha256 `9acc2d6824a17a533167091d204a3db0d40fc7d9b098d234970259f6fc55923c` (matches the release asset digest). The asset name is upstream's; the engine runs on the Arc GPU through SYCL / Level Zero |
| Engine reported | `session is up (engine xe0.2.2-1)`; the server's `/v1/status` reports `"engine": "xe0.2.2-1"` |
| Container base | `ubuntu:26.04@sha256:6a06111c3b0a8600feadb270aec771dc239bf407b25625f93f44ab00e11f4d3c` |
| oneMKL | `intel-oneapi-mkl-sycl-blas-2026.2` |
| Intel GPU user-space | from Intel's GitHub releases, sha256-checked: compute-runtime 26.40.40196.8, IGC 2.42.6, gmmlib 22.10.2, Level Zero loader 1.34.0 |
| Local image | `xestrata:xe0.2.2-1-gfx2640` (built locally, not pushed to a registry) |

## Notes

- XeStrata keeps Strata's device naming in its logs, so the Arc GPUs appear as `CUDA0`, `CUDA1`. The line before
  shows the actual device: `GPU Intel(R) Arc(TM) Pro B70 Graphics, 256 compute units`.
- Speculative decoding cannot be switched off: the engine refuses `--spec 0` for these model packs. Every decode
  number from this runtime includes MTP drafts (4 per step here).
- Setup (`--setup`) converts the GGUF into XeStrata's own expert packs and MTP files; those derived files are not
  published.

## Used by

- [`runs/2026-11-06_qwen3-8-flash-next_xeon-676x-4x-b70`](../../runs/2026-11-06_qwen3-8-flash-next_xeon-676x-4x-b70/)
