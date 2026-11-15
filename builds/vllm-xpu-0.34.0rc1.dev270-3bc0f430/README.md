# vLLM 0.34.0rc1.dev270 for Intel XPU (upstream main 3bc0f430)

Stock vLLM: upstream source built without code changes.

| | |
|---|---|
| Source | [vllm-project/vllm@3bc0f430883c575d4076280d8d10d77cd4bfc07c](https://github.com/vllm-project/vllm/commit/3bc0f430883c575d4076280d8d10d77cd4bfc07c) (main, 2026-11-11) |
| Reported version | `0.34.0rc1.dev270+g3bc0f4308` |
| Build recipe | Upstream [`docker/Dockerfile.xpu`](https://github.com/vllm-project/vllm/blob/3bc0f430883c575d4076280d8d10d77cd4bfc07c/docker/Dockerfile.xpu) at that commit, default target, no build arguments changed |
| Local image | `vllm-xpu-main:3bc0f430`, image id `07b20bcd5fdc` (built locally, not pushed to a registry) |
| PyTorch | 2.15.0+xpu |
| vllm-xpu-kernels | 0.1.17 |
| oneCCL | 2022.1.2 |
| Triton (XPU) | 3.9.0 |
| GPU user-space in image | compute-runtime (NEO) 26.31.39395.16, Level Zero loader 1.32.0 |

## Rebuild

```sh
git clone https://github.com/vllm-project/vllm && cd vllm
git checkout 3bc0f430883c575d4076280d8d10d77cd4bfc07c
docker build -f docker/Dockerfile.xpu -t vllm-xpu-main:3bc0f430 .
```

## Used by

- [`runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/vllm-gptq-tp4`](../../runs/2026-11-12_ripple-65b_xeon-676x-4x-b70/vllm-gptq-tp4/)
