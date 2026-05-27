# 研究檢核點 v1：可驗證視覺編碼器

日期：2026-05-27  
專案：RRKAL Visual Compressor  
範圍：時間序列與 2D 曲線預覽層（尚未進入完整 3D 流程）

## 1) 核心研究主張

本階段只驗證一個主張：

> 一個高規模且有結構的視覺訊號，可以用「主模型 `F`」加上可控的「殘差層 `R`」表示，
> 並在可度量條件下得到更低的傳輸/互動成本。

這是「可證明」取向，不是萬用保證。

## 2) 現行假設

1. 單獨使用全域 Fourier 在跳躍訊號上不足夠。
2. 分段方法（piecewise Fourier、多項式、Haar）可降低局部外洩。
3. 非均勻 x 軸必須明確記錄與編碼，否則會出現時間軸漂移。
4. 多通道壓縮要先做通道關聯降維（例如 PCA baseline）。
5. 透過自適應殘差閾值可抑制雜訊下的 payload 膨脹。

## 3) 檢核規則

每筆 `scripts/run_defensible_research_sweep.py` 的報表列都要通過：

- `R2 >= r2_gate`（建議值 `0.99`）
- 局部外洩門檻依 `locality-mode` 決定：
  - `strict`（預設）：detrended 與 piecewise Fourier 兩者都要低於門檻。
  - `any`：兩者其中一個低於門檻即可。
- 可選：`--include-piecewise-polynomial` 時可加入 polynomial 作為第三候選。
- `adaptive_keep_ratio <= max_adaptive_keep_ratio`（建議值 `0.45`）

同時符合者才標記 `defensible = true`。

我們另外追蹤 `defensible_rdp_rows` 作為輔助探索指標：
`rdp_prefilter_fourier` 的 `r2 >= r2_gate` 次數。

## 4) 固定實驗集

資料集與參數固定如下：

- `steps`
- `spikes`
- `irregular`
- `multiscale`
- `smooth`

參數：

- `--terms 16,32,64`

此組合會固定使用，直到連續兩次檢核皆穩定通過。

## 5) 前進 / 回退判準

符合以下條件才可進到下一輪：

- 可重複產生 JSON/MD 報表；
- `steps`、`spikes`、`irregular` 各至少各有一筆可接受 pass；
- 相同輸入下 `defensible_rows / rows_with_gate_fields` 重複執行保持穩定。

若連續兩次未達標，回到前一版本修正。

## 6) 下一步

檢核成功後，接著加入：

- 收窄 gate 門檻；
- 像素（DPI）視窗預算上限實驗；
- decode 時間與雜訊下 payload 成長率量測。

研究順序保持：

1. 可量測正確性
2. 可控 payload 與可驗證報表
3. 視口級渲染效率研究
