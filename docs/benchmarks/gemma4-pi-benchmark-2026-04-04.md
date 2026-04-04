# Gemma 4 Pi Benchmark — 2026-04-04

> **Status: Experimental.** Gemma 4 support on Potato OS is early-stage. The ik_llama runtime only supports 26B-A4B; E2B/E4B fall back to llama_cpp. Proper Gemma 4 support (including ByteShape quants and full ik_llama coverage) is pending upstream work.

Spike: #274

## Hardware

| Label | Board | RAM | Storage | Runtime |
|-------|-------|-----|---------|---------|
| Pi 5 16GB / SD | Raspberry Pi 5 Rev 1.1 | 16 GB | SD card | llama_cpp (a1cfb64) / ik_llama (9a0a4628) |
| Pi 5 8GB / SSD | Raspberry Pi 5 Rev 1.0 | 8 GB | NVMe SSD, 2 GB zram swap | llama_cpp (a1cfb64) / ik_llama (9a0a4628) |
| Pi 4 8GB / SD | Raspberry Pi 4 Rev 1.4 | 8 GB | SD card, 2 GB swap | llama_cpp (a1cfb64) |

## Models tested

| Model | Filename | Quant | Size |
|-------|----------|-------|------|
| E2B | gemma-4-E2B-it-Q4_K_M.gguf | Q4_K_M | 2.88 GiB |
| E4B | gemma-4-E4B-it-Q4_0.gguf | Q4_0 | 4.49 GiB |
| 26B-A4B | gemma-4-26B-A4B-it-UD-IQ4_NL.gguf | IQ4_NL | 12.48 GiB |

## Methodology

### Multi-turn chat benchmark
- 5-turn conversation with fixed prompts (quantum computing topic)
- 16k context, prompt caching enabled
- max_tokens=512 per turn, temperature=0.7, top_p=0.8
- ~2k–2.5k total generated tokens per run
- No parallel workloads during measurement

### llama-bench
- pp512 (prompt processing, 512 tokens) and tg128 (text generation, 128 tokens)
- 1 repetition, no concurrent workloads

## Results

### Pi 5 16GB / SD

| Model | Quant | Runtime | Chat gen t/s | Prompt t/s (T1 → T2+) | Chat tokens | pp512 t/s | tg128 t/s | Swap |
|-------|-------|---------|-------------|----------------------|-------------|-----------|-----------|------|
| E2B | Q4_K_M | llama_cpp | 6.5 | 26.1 → 29.5 | 2081 (5/5) | 28.02 | 6.71 | 669 MB |
| E4B | Q4_0 | llama_cpp | 3.7 | 18.7 → 21.9 | 2535 (5/5) | 18.46 | 3.48 | 669 MB |
| 26B-A4B | IQ4_NL | ik_llama | 3.0 | 9.4 → 16.3 | 2450 (5/5) | 6.38 | 2.54 | 442 MB |

### Pi 5 8GB / SSD

| Model | Quant | Runtime | Chat gen t/s | Prompt t/s (T1 → T2+) | Chat tokens | pp512 t/s | tg128 t/s | Swap |
|-------|-------|---------|-------------|----------------------|-------------|-----------|-----------|------|
| E2B | Q4_K_M | llama_cpp | 6.8 | 26.2 → 32.7 | 2079 (5/5) | 31.86 | 5.97 | 390 MB |
| E4B | Q4_0 | llama_cpp | 3.5 | 18.6 → 23.3 | 2536 (5/5) | 25.75 | 3.26 | 493 MB |
| 26B-A4B | IQ4_NL | ik_llama | 1.9 | 3.3 → 4.3 | 2522 (5/5) | OOM | OOM | 2047 MB (full) |

### Pi 4 8GB / SD

| Model | Quant | Runtime | Chat gen t/s | Prompt t/s (T1 → T2+) | Chat tokens | pp512 t/s | tg128 t/s | Swap |
|-------|-------|---------|-------------|----------------------|-------------|-----------|-----------|------|
| E2B | Q4_K_M | llama_cpp | 1.7 | 5.3 → 3.4 | 2077 (5/5) | 4.06 | 1.68 | 0 MB |
| E4B | Q4_0 | llama_cpp | timeout | timeout | timeout | 2.02 | 0.87 | — |

## Notes

- **Prompt t/s (T1 → T2+)**: T1 is the first turn (no cached context). T2+ is the average of turns 2–5, where prior conversation history is in KV cache. Higher T2+ reflects cache reuse, not a warmup effect.
- **ik_llama 26B-A4B only**: The ik_llama Gemma 4 WIP branch (upstream `ik/gemma4`) crashes on E2B/E4B with `GGML_ASSERT(ggml_can_repeat(b, a))`. Only 26B-A4B loads successfully. E2B/E4B fall back to llama_cpp.
- **Pi 5 8GB 26B OOM on llama-bench**: llama-bench OOM-kills on 26B with 8 GB RAM despite mmap=1. The `universal` llama_cpp profile appears to load model weights into anonymous memory rather than file-backed pages. The chat benchmark (via llama-server) completes because Potato manages memory differently, but at 1.9 t/s with full swap.
- **Pi 4 E4B timeout**: At 0.87 t/s generation, a single 512-token response takes ~10 minutes. The 600s per-turn timeout was exceeded.
- **Pi 4 prompt t/s decreases on later turns**: Unlike Pi 5, Pi 4 shows slower prompt processing on later turns (5.3 → 3.4 t/s). Likely memory bandwidth saturation as the KV cache grows on the older architecture.

## Open items

- Upstream ik_llama Gemma 4 support for E2B/E4B (tracked in #272)
- ByteShape quants for Gemma 4 (not yet available from upstream)
- Investigate mmap behavior with `universal` llama_cpp profile on 8 GB devices
