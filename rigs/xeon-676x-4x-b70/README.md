# Xeon 676X workstation + 4× Arc Pro B70

intelinside.ai rig: [/rigs/18](https://www.intelinside.ai/rigs/18)

| Part | Detail |
|---|---|
| Board | ASUS Pro WS W890E-SAGE SE (W890 chipset), BIOS 0603 (2026-07-08) |
| CPU | Intel Xeon 676X — 32 cores / 64 threads, 4.9 GHz max, 144 MB L3, 275 W base power; one NUMA node |
| Memory | 8× 32 GB DDR5-6400 ECC RDIMM (256 GB), running at 6400 MT/s |
| GPUs | 4× Intel Arc Pro B70 (32 GB GDDR6 each, Battlemage G31, PCI id 8086:e223) |
| GPU links | Each card on its own CPU-attached PCIe Gen5 x16 link (32 GT/s x16, read at the card's onboard switch upstream port) |
| GPU PCI addresses | `0000:0d:00.0`, `0000:64:00.0`, `0000:90:00.0`, `0000:a6:00.0` |
| Display | Onboard BMC graphics; the B70s are compute-only |
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-43-generic, kernel parameter `intel_iommu=off` |
| Container runtime | Docker 29.9.3; each runtime's GPU user-space stack ships inside its image (see [`builds/`](../../builds/)) |

## Notes

- About 30.3 GiB of each card's 32 GB is usable for model weights and KV cache.
- Cards are passed into containers by PCI path, so a configuration always uses the same physical slots.
- No power caps were applied to the cards for the runs published so far, and no power or thermal logging
  was running unless a run says so.
