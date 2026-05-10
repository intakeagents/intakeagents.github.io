# Benchmark Report — 1,000 Referrals · Real Agent · Claude Sonnet
**Run:** 2026-05-07T19:46:28.958905
**Model:** claude-sonnet-4-6  |  **Workers:** 20 parallel

## Measured Results

| Metric | Value |
|---|---|
| Total referrals processed | 1000 |
| **Total wall-clock time** | **13.45 min (806.9 sec)** |
| Avg per referral (throughput) | 0.81 sec |
| Rate | 74 referrals/minute |

## Scale Projection

| Workers | 10,000 referrals |
|---|---|
| 20 workers (as run) | ~134.5 min |
| 50 workers | ~53.8 min |

**1,000 real referral PDFs · real Claude Sonnet extraction · real gap detection · real episode output**

*Note: Timing measured from episode file creation timestamps. All 1,000 episodes saved to output/.*