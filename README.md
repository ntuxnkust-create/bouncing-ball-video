# Bouncing Ball Merge

可直接產生直式汽車品牌彈跳合併短影音的 Python 專案。預設輸出 **1080 × 1920、30 FPS、60 秒、H.264 / AAC MP4**，包含原創合成配樂與立體聲碰撞／合併音效，不需要視窗、GPU、付費服務或 API Key。

## 直接執行

需求：Python **3.12**（已驗證）、FFmpeg / FFprobe（須支援 `libx264` 與 `aac`）。Linux、macOS 可用以下指令；Ubuntu 可先安裝 `sudo apt-get install python3-venv ffmpeg fonts-dejavu-core`。

```bash
git clone https://github.com/ntuxnkust-create/bouncing-ball-video.git
cd bouncing-ball-video
bash scripts/setup.sh
.venv/bin/python main.py
```

已設定好的 Codex 雲端環境，直接執行：

```bash
cd /workspace/bouncing-ball-video
.venv/bin/python main.py
```

成品：`output/bouncing-ball-merge.mp4`。若檔案已存在，預設保護既有檔案；要重新產生請加 `--overwrite`。在 Windows，可使用 `python -m venv .venv`、`.venv\Scripts\python -m pip install -r requirements.txt`、`.venv\Scripts\python main.py`（須自行安裝並加入 FFmpeg 至 PATH；目前驗證平台為 Linux）。

## 成品設計

- 純黑背景、連續彩虹漸層圓形場地與柔光；上方實體雙導軌及入口。
- 英文標題：**Will They Merge Into The Final Form?**
- Pymunk / Chipmunk 固定 **120 Hz** 物理步進：重力、圓形碰撞、旋轉、摩擦與反彈；影片 30 FPS。
- **相同等級實際接觸才合併**，在物理步進結束後處理，避免同一球被重複合併。合併保留線動量，質量逐級加倍。
- 八個等級：Renault → Ford → Mercedes-Benz → BMW → Ferrari → Lamborghini → Bugatti → **APEX 最終型態**。APEX 為本專案原創終極徽章。
- 合併具有光暈、擴散光環、粒子及彈性縮放；高等級強化特效，最終型態有專屬揭幕與琶音。
- 後半段提高進階球的生成機率，並偏向場內尚待配對的高等級；**不直接生成最終球、不依照時間強制合併**。預設種子 42 已實測在約 **52.64 秒**合併到第八級，最後停止投球供觀賞。其他種子或自訂規則不保證同樣結果。
- 碰撞音根據接觸時間及位置同步，並以聲像表現左右位置；高頻接觸節流，避免堆積成雜音。
- 無 Instagram 介面、愛心、留言圖示或外部素材下載依賴。

內建車標是程式繪製的精緻圖形／品牌文字替代版，並非官方提供的 PNG。Ferrari 與 Lamborghini 採用盾牌字樣。沒有收到參考截圖，故依照文字需求設計構圖。

## 常用設定

重要參數集中於 [`config.py`](config.py)：影片規格、種子、色彩、品牌順序、球半徑、場地、重力、彈性、摩擦、生成間隔、升級生成速度、配對偏好、合併開關、編碼品質與音訊。

```bash
# 完整 60 秒預設成品（覆寫）
.venv/bin/python main.py --overwrite

# 改輸出路徑、影片長度與種子
.venv/bin/python main.py --duration 90 --seed 123 --output output/custom.mp4

# 小尺寸輸出（仍然保持 9:16；常用於快速檢查）
.venv/bin/python main.py --width 540 --height 960 --duration 10 --output output/small.mp4

# 保留碰撞音效、關閉原創背景配樂
.venv/bin/python main.py --no-score --output output/effects-only.mp4

# 加入你有使用權的外部音樂；音樂自動循環、淡入淡出並限制音量
.venv/bin/python main.py --no-score --music /path/to/music.wav --music-gain 0.18

# 不渲染影格，執行完整物理模擬並輸出報表
.venv/bin/python main.py --simulate-only
```

使用 `--help` 查看所有選項。更高品質可用 `--crf 16 --preset slow`；預設 CRF 18 / fast。FPS 須可整除 120（例如 24、30、60）。非整數時長會取最接近的完整影格。

### 換成 PNG Logo

把透明 PNG 放進 `assets/logos/` 即會自動替換，支援混合使用 PNG 與內建圖形，無須修改程式。檔名及等級對照見 [`assets/logos/README.md`](assets/logos/README.md)。也可以使用 `--logos-dir /path/to/logos`。圖片保留長寬比與透明度，建議使用 512 × 512 以上。

### 自訂碰撞與物理

修改 `Config` 中的 `gravity`、`elasticity`、`friction`、`spawn_interval`。`merge_equal_levels=False` 可關閉合併。修改 `BRANDS` 可調整名稱、色彩、大小和替換圖檔；新增的高等級使用最終徽章替代圖形，亦可提供 PNG。更換整組規則後請執行物理模擬及測試，確認影片進度符合需求。

## 自動化驗證

```bash
.venv/bin/python -m unittest discover -s tests -v
```

測試涵蓋真實接觸合併、不同級別不能合併、不可重複使用同球、質量守恆、合併開關、兩次完整 60 秒模擬的重現性／邊界／最終型態、音效跨區塊與立體聲、PNG 替換及真實 FFmpeg 編碼／解碼。GitHub Actions 會執行相同測試。

每次正式渲染還會自動驗證 **1800 影格、尺寸、幀率、H.264 yuv420p、立體聲 AAC、影音時長及完整串流解碼**。驗證失敗會以非零狀態結束，不發布不完整 MP4。成功後同時輸出：

```text
output/
  bouncing-ball-merge.mp4           # 含音訊、faststart，可直接播放／上傳
  bouncing-ball-merge.report.json   # 物理統計、音訊峰值／RMS、媒體驗證及設定
  bouncing-ball-merge.events.json   # 真實接觸與合併時間紀錄
  bouncing-ball-merge-stills/       # 當次影片的四張截圖
```

報表中的音訊峰值為編碼前原創合成音軌；有外部音樂時，外部音樂由 FFmpeg 混音與限幅。`full_decode: passed` 表示當次輸出已完整解碼驗證，不表示 GitHub CI 已經執行。

## 效能與可靠性

影片逐格寫入 FFmpeg stdin，**不將整支影片影格放入記憶體**；圖形預先快取，音訊以一秒區塊寫入 WAV，物理事件只記錄小型資料。FFmpeg 預設使用四個編碼執行緒。實際耗時視 CPU 而異。

渲染暫存檔與目的檔放在相同檔案系統；僅在完整檢查通過後原子替換 MP4。中止或錯誤會移除暫存資料。建議預留至少 1 GB 可用磁碟空間，長影片需要更多。

一般接觸由 Chipmunk 解算；合併瞬間新球半徑增加時，會限制生成位置，並使用圓形連續接觸修正與速度上限，防止深度重疊造成穿牆。這類修正次數會記錄於報表，不用隱藏傳送來製造升級。

## 專案結構

```text
config.py                     集中參數與品牌等級
main.py                       CLI 入口
bouncing_ball/simulation.py   固定步進物理與合併事件
bouncing_ball/graphics.py     品牌球、場景、HUD 與粒子
bouncing_ball/audio.py        原創立體聲合成
bouncing_ball/render.py       逐格渲染、編碼與原子輸出
bouncing_ball/verify.py       FFprobe／完整解碼驗證
tests/test_project.py         自動測試
scripts/setup.sh              可重複執行的安裝腳本
```

原創合成配樂與音效不含下載音樂或第三方取樣。品牌名稱及標誌屬於各自權利人；本專案無品牌合作或背書。替換素材與外部音樂請使用你有權發布的版本。
