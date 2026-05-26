# 學術與技術參考來源

本文件收集 RRKAL Visual Compressor 目前概念可對應的學術與技術來源。這些來源不是說本 repo 已完整實作所有方法，而是說明專案路線與既有研究的關係。

## Functional Data Analysis

對應本專案：

- time series 被視為函數觀測。
- 以 basis expansion 表示主信號。
- smoothing 與 residual 拆層。

參考：

- Ramsay, J. O.; Silverman, B. W. *Functional Data Analysis*. Springer.  
  https://link.springer.com/book/10.1007/978-1-4757-7107-7

## Fourier Descriptors / Shape Descriptors

對應本專案：

- Roadmap Phase 4 的 2D closed contour。
- parametric Fourier：`x(t), y(t)`。
- radial Fourier：`r(theta)`。

參考：

- Granlund, G. H. "Fourier Preprocessing for Hand Print Character Recognition." *IEEE Transactions on Computers*, 1972.  
  https://liu.diva-portal.org/smash/record.jsf?pid=diva2%3A241553
- J-GLOBAL metadata page for the same paper.  
  https://jglobal.jst.go.jp/en/detail?JGLOBAL_ID=201602018534299110

## Wavelet / Multiresolution

對應本專案：

- future LOD / progressive reconstruction。
- 多尺度 basis + residual。
- 將局部細節延後載入或以較高解析度重建。

參考：

- Mallat, S. G. "A Theory for Multiresolution Signal Decomposition: The Wavelet Representation." *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 1989.  
  https://cir.nii.ac.jp/crid/1363670320509695744
- University of Pennsylvania repository page for the same paper.  
  https://repository.upenn.edu/handle/20.500.14332/7614
- Mallat, "Multiresolution approximation and wavelet orthonormal bases of L2", AMS, 1989.  
  https://www.ams.org/journal-getitem?pii=S0002-9947-1989-1008470-5

## SDF / Implicit Geometry / Level Sets

對應本專案：

- future 2D SDF。
- implicit function package。
- branch/domain/topology constraints。

參考：

- Osher and Sethian level set method context, listed by Sethian's publications page.  
  https://math.berkeley.edu/~sethian/Publications/hold_publications.html
- Level sets and distance functions discussion, SpringerLink.  
  https://link.springer.com/chapter/10.1007/3-540-45054-8_38

## NeRF / Continuous Scene Functions

對應本專案：

- 連續函數表示不是本專案獨創，但本專案應用在 visual asset compression。
- 可作為「連續表示重新成為主流研究方向」的旁證。

參考：

- Mildenhall et al. "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis." arXiv, 2020.  
  https://arxiv.org/abs/2003.08934
- Communications of the ACM article on NeRF.  
  https://cacm.acm.org/research/nerf/

## Unreal Engine / Nanite / Distance Fields

對應本專案：

- Unreal 可作為 future renderer consumer。
- Nanite 與本專案同樣關心 geometry representation 與 streaming，但不能簡化成 SDF。
- Unreal 的 distance field 技術可作為 future SDF/volume rendering 的參考方向。

參考：

- Epic documentation: Nanite Virtualized Geometry.  
  https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine
- Epic documentation: Nanite Technical Details.  
  https://dev.epicgames.com/documentation/unreal-engine/nanite-technical-details
- Epic documentation: Mesh Distance Fields.  
  https://dev.epicgames.com/documentation/unreal-engine/mesh-distance-fields-in-unreal-engine

## 建議引用原則

對外匯報時，建議使用以下保守表述：

```text
本專案與 Functional Data Analysis、Fourier descriptors、multiresolution analysis、
implicit geometry 等研究方向相容，並把這些思想落到可驗證的 visual asset package。
```

避免使用以下過度表述：

```text
本專案已顛覆圖形學。
Nanite 底層核心就是 SDF。
所有資料都可以靠高維函數壓縮。
```
