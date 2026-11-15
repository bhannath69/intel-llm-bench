# llama.cpp b12314, SYCL backend

Stock llama.cpp: upstream release tag built without code changes.

| | |
|---|---|
| Source | [ggml-org/llama.cpp tag b12314](https://github.com/ggml-org/llama.cpp/releases/tag/b12314) = commit [`e1f7593c32e8dd782fc7addb908d0911260511ae`](https://github.com/ggml-org/llama.cpp/commit/e1f7593c32e8dd782fc7addb908d0911260511ae) (2026-11-12) |
| Build recipe | Upstream [`.devops/intel.Dockerfile`](https://github.com/ggml-org/llama.cpp/blob/e1f7593c32e8dd782fc7addb908d0911260511ae/.devops/intel.Dockerfile), target `full` |
| Local image | `llamacpp-sycl:e1f7593c`, image id `cc76dbe06d4a` (built locally, not pushed to a registry) |
| oneAPI | deep-learning-essentials 2026.2.0 |
| GPU user-space in image | compute-runtime (NEO) 26.40.40196.8, IGC 2.42.6, gmmlib 22.10.2, Level Zero loader 1.34.0 |

## Rebuild

```sh
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
git checkout b12314
docker build -f .devops/intel.Dockerfile --target full -t llamacpp-sycl:e1f7593c .
```

## Used by

- [`runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/llamacpp-q4km-layer`](../../runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/llamacpp-q4km-layer/)
