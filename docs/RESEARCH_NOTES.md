# Research Notes: Defensible Compression Directions (RRKAL Visual Compressor)

Date: 2026-05-27  
Project: `rrkal-visual-compressor`

## 1) What we are testing now

This project currently has strong baseline coverage for:

- time-series Fourier compression
- channel model + residual bands
- sparse / Fourier residual layers
- x-domain storage modes (`stored_x`, `linear_plus_rdp_delta`, `linspace`)

The latest criticism is valid: a **single global Fourier expansion has locality defects** (Gibbs-like spread), and this can hurt both fidelity stability and acceptance in irregular or noisy real data.

## 2) Hardest risks and practical tests

### Risk A: Global Fourier locality defects (Gibbs-like spread)

Hypothesis:
`global` Fourier tends to spread a local sharp event into neighbors.

Test added:
- `locality_leakage_metric` in `src/vizcompress/research.py`
- Build a manual step-like discontinuity series.
- Compare:
  - global Fourier reconstruction error near jump neighborhoods
  - global Fourier error in far regions
  - piecewise-Fourier (jump-aware segmentation) far-region error

Interpretation:
- If local-to-far ratio is materially lower for piecewise, this is evidence that segmented basis expansion is a practical fix path.

### Risk B: Irregular x-domain

Current status:
- already implemented in package encoding/decoding (`domains.py`) and benchmark profile.
- still unresolved: model-level policy should switch between `preserve/compressed` based on explicit error budget.

### Risk C: Multichannel dependency ignored

Current status:
- single-variable compressor is intentionally the first milestone.
- Next phase must add coupling across channels (PCA / shared latent coefficients) before broad claims.

### Risk D: Residual layer budget blow-up

Current status:
- residual profile already classifies (`fourier`, `sparse`, `statistical`)
- missing explicit payload caps, e.g. `max_payload_ratio`.

## 3) New research code path now implemented

- `src/vizcompress/research.py`
  - `detect_jump_breakpoints`
  - `compress_fourier_piecewise`
  - `locality_leakage_metric`
- `tests/test_research.py`
  - discontinuity reconstruction stability
  - finite/shape invariants
  - noisy vs clean leakage consistency

## 4) How to run research now

```bash
python -m pytest tests/test_research.py -q
```

## 5) Interpretation and next decision

The practical question is:

- **Given a fidelity budget, does a restricted functional family produce better
  error/size trade-offs than baselines for the target data class?**

If a class of data repeatedly fails break-even tests, it should wait for phase-2.

## 6) 下一步

1. 固定「斷點偵測 + 分段傅立葉」為局部化修正策略做試點。  
2. 補齊 x-domain 的誤差門檻策略，讓壓縮器可自動選擇。  
3. 規劃多通道實驗（PCA / SVD）看共享潛在空間的收益。  
4. 為殘差層加入明確 payload 上限政策。
