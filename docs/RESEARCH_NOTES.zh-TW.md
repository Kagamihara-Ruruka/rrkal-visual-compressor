# 研究筆記：可辯護壓縮方向（RRKAL Visual Compressor）

日期：2026-05-27  
專案：`rrkal-visual-compressor`

## 1) 目前先研究的方向

目前已有穩定的基礎：

- 時序傅立葉壓縮
- 通道模型（中心線 + band）
- 稀疏 / 傅立葉殘差層
- x 軸儲存模式（`stored_x` / `linear_plus_rdp_delta` / `linspace`）

最新質疑成立：**單一全域傅立葉會有局部性問題**（類似 Gibbs 擴散），在尖峰、突變、非均勻取樣或噪訊情境下，會影響誤差行為的可控性。

## 2) 四個主要風險與測試

### 風險 A：全域傅立葉的局部洩漏

假設：
`global` 傅立葉會把局部尖峰/不連續擴散到鄰近區域。

本輪新增實驗：
- `src/vizcompress/research.py` 的 `locality_leakage_metric`
- 用人工步階式資料，比較：
  - 跳變附近的殘差
  - 離開跳變區域的殘差
  - 斷點切分後的分段傅立葉結果

若分段法能降低 far 區域殘差，表示是可行的局部化修正方向。

### 風險 B：非均勻 x-axis

目前狀態：
- 套件層面已支援 `domains.py` 的 x 軸壓縮/保存。
- 策略層面仍需決定，在何種誤差約束下自動切 `preserve/compressed`。

### 風險 C：多通道關聯未建模

目前狀態：
- 先做單變量壓縮，切到穩定實作。
- 之後要進入多通道 PCA / 共享潛在空間。

### 風險 D：殘差層成本失控

目前狀態：
- 已有殘差分類（傅立葉/稀疏/統計雜訊）策略。
- 尚缺明確 payload 上限（例如 `max_payload_ratio`）。

## 3) 本輪落地內容

- `src/vizcompress/research.py`
  - `detect_jump_breakpoints`
  - `compress_fourier_piecewise`
  - `locality_leakage_metric`
- `tests/test_research.py`
  - 不連續資料的重建穩定性
  - 有限性與 shape 不變檢查
  - 噪訊與乾淨訊號的一致性比較

## 4) 執行方式

```bash
python -m pytest tests/test_research.py -q
```

## 5) 下一步判斷

不是所有資料都天然函數化；實務目標是：

- 在目標資料與預算下，函數族是否能提供更好的「誤差-大小」折衷。

如果某類資料長期無法勝出，先暫緩列入正式範疇。

## 6) 下一步行動

1. 固定「斷點偵測 + 分段傅立葉」作為局部化修正試點。  
2. 為 x-domain 補齊誤差門檻策略與自動模式選擇。  
3. 規劃多通道合成資料，測 PCA / SVD 的壓縮收益。  
4. 加入殘差層明確 payload 限制規則。
