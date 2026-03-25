# Memory Behavior and Diagnostics on Raspberry Pi 5

How Potato OS measures and displays memory usage, and why the numbers might not match what you'd expect from `free` or `htop`.

## Why RAM usage looks weird on Pi

Linux uses free RAM for page cache aggressively. A Pi 5 running a 10 GB model via mmap will show ~97% RAM "used" but zero memory pressure — the kernel is just caching model pages from disk.

Three numbers that matter:
- **total - MemFree**: actual RAM occupied (includes cache)
- **MemAvailable**: kernel's estimate of reclaimable headroom
- **PSI (Pressure Stall Information)**: is anything actually waiting for memory?

The old psutil `used` metric excluded cache, showing 608 MB on an 8 GB Pi with a loaded model — technically correct but useless.

## Model sizing guidance

### 8 GB Pi 5 without NVMe SSD

The SD card is too slow for constant page faults from an oversized mmap'd model. Models that don't fit in RAM will load and technically work, but inference will be painfully slow (1-2 tok/s for a 30B model) because the kernel is constantly evicting and re-reading model pages from the SD card.

**The model must fit fully in RAM.** After accounting for the OS, llama-server heap, KV cache, and zram overhead (~1.5-2 GB), that leaves roughly 6-6.5 GB for the model file. Quantized models in the 3B-8B range at Q4/Q5 quantization are the sweet spot:

| Model | File size | llama RSS | tok/s | Verdict |
|-------|-----------|-----------|-------|---------|
| Qwen3-4B Q5_K_S | 4.74 GB | 4.87 GB | 4.44 | Good — fits in RAM, zero pressure |
| Qwen3.5-2B Q4_K_M | 2.66 GB | 3.76 GB | 9.34 | Great — plenty of headroom |
| Qwen3-30B IQ3_S | 10.0 GB | 7.63 GB | 1.91 | Too large — constant page faults from SD |

### 8 GB Pi 5 with NVMe SSD

NVMe is fast enough for mmap page faults to be tolerable. Larger models (8B-14B) become viable, though still slower than models that fit in RAM. The sweet spot shifts upward.

### 16 GB Pi 5

Most consumer models fit comfortably. A 30B Q3 model (10 GB file) loads with zero pressure and 14.9 GB MemAvailable. No special sizing considerations needed.

## mmap vs no-mmap loading

- **mmap (default)**: model file mapped into page cache. Shows up in RssFile. Kernel can evict and re-read pages on demand. Works for models larger than RAM (with performance penalty).
- **no-mmap / full_ram**: model loaded into anonymous memory. Shows up in RssAnon. Faster inference, but model must fit in RAM.

The runtime panel detects which mode is active and attributes model memory to the correct RSS bucket.

## Metrics reference

### PSI — /proc/pressure/memory

Primary signal for real memory pressure.

```
some avg10=2.31 avg60=1.05 avg300=0.42 total=123456789
full avg10=0.00 avg60=0.00 avg300=0.00 total=0
```

- `some`: at least one task stalled waiting for memory
- `full`: ALL non-idle tasks stalled (thrashing)
- `avg10/60/300`: percentage of wall-clock time, 10s/60s/5m windows
- Range: 0.00 to 100.00

Severity thresholds used in the UI:

| Signal | Normal | Warn | High | Critical |
|--------|--------|------|------|----------|
| full avg10 | 0 | — | >0 (sustained) | >10 |
| some avg10 | 0 | >10 | — | — |

Requires `psi=1` in `/boot/firmware/cmdline.txt`. Compiled into the Pi OS kernel but disabled at boot by default. No measurable performance cost.

### llama-server RSS — /proc/{pid}/status

Per-process memory breakdown:

- **VmRSS**: total physical RAM held by the process
- **RssAnon**: heap, KV cache, stack (and model in no-mmap mode)
- **RssFile**: mmap'd model pages currently in RAM
- **RssShmem**: shared memory (typically ~0)

Reading cost: microseconds (kernel counters, no page table walk).

### zram mm_stat — /sys/block/zram0/mm_stat

Nine space-separated integers:

```
orig_data_size compr_data_size mem_used_total mem_limit mem_used_max same_pages pages_compacted huge_pages huge_pages_since
```

Key derived metric:

- **compression_ratio** = orig_data_size / compr_data_size
  - 2-5x is healthy
  - Below 1.5x means incompressible data
  - Ratio is meaningless when orig_data_size is tiny (idle system)

### MemFree vs MemAvailable — /proc/meminfo

- **MemFree**: truly unused pages
- **MemAvailable**: free + reclaimable cache/slab (capped at 50% of low watermark). Overstates headroom for mmap workloads because evicting cached model pages means re-reading from disk.

## Real Pi 5 measurements

### 16 GB Pi — Qwen3-30B-A3B (2.66 GB file, mmap)

| Metric | Idle | Model loaded | During inference |
|--------|------|--------------|------------------|
| MemFree | 14.1 GB | 4.7 GB | 4.7 GB |
| MemAvailable | 15.4 GB | 14.9 GB | 14.9 GB |
| PSI some avg10 | 0.00 | 0.00 | 0.00 |
| PSI full avg10 | 0.00 | 0.00 | 0.00 |
| llama RSS | — | 1.55 GB | 1.55 GB |
| zram | idle | idle | idle |

Model fits easily. Zero pressure even during inference.

### 8 GB Pi — Qwen3-30B-A3B (2.69 GB IQ3_S, mmap)

| Metric | Model loaded | During inference |
|--------|--------------|------------------|
| RAM used | 8.20 GB (97%) | 8.20 GB (97%) |
| MemFree | 248 MB | 248 MB |
| PSI some avg10 | 8.25* | 0.00 |
| PSI full avg10 | 8.05* | 0.00 |
| llama RSS | 7.63 GB | 7.63 GB |
| RssFile (model) | 6.70 GB | 6.70 GB |
| zram | 249 MB (5.1x) | 249 MB (5.1x) |
| tok/s | — | 1.91 |

*PSI spikes during model load, settles to 0 once loaded. 97% RAM used but 0% pressure at steady state — high usage does not equal pressure. However, 1.91 tok/s is too slow for real conversations because the 10 GB model doesn't fit in 8 GB RAM and the SD card can't keep up with page faults.

### 8 GB Pi — Qwen3-4B Q5_K_S (4.74 GB, mmap)

| Metric | Steady state |
|--------|--------------|
| RAM used | 8.00 GB (95%) |
| PSI some avg10 | 0.00 |
| llama RSS | 4.87 GB (58%) |
| RssFile (model) | 3.63 GB |
| zram | 218 MB (5.4x) |
| tok/s | 4.44 |

Sweet spot for 8 GB Pi on SD card — good performance, zero pressure, model fits in RAM.

## Fallback behavior

When PSI is unavailable (no `psi=1` in cmdline):

- Pressure row shows `--`
- Memory severity uses relaxed percentage thresholds: >=95% critical, >=90% high, >=80% warn (vs old >=90/75/60)
- All other metrics (RAM used, llama RSS, zram) work normally
