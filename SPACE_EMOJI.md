# Space Emoji Merge

獨立的宇宙 Emoji 合併影片產生器。原有汽車版本 `main.py`、`config.py` 與 `bouncing_ball/` 保留原樣；新主題使用 `space_emoji/`，沿用原有碰撞事件音效與 MP4 驗證器。

**目前交付狀態：程式已建立，但對話中的背景圖片未以可讀取附件提供給雲端。`assets/glass-container.png` 尚缺，因此沒有正式 MP4，也尚未完成圖片內壁的實際對位驗證。不能將此版本稱為完成的影片。** `assets/glass-container.geometry.json` 是依對話可見參考圖建立的初始內壁描線，`reference_registration` 明確標示 `pending-original-png`。正式製作必須先取得原始 PNG，檢查及微調描線。

## 安裝與執行

Python 3.12、FFmpeg / FFprobe（`libx264`、`aac`）與 DejaVu Sans 字型。Linux 安裝步驟沿用原有腳本：

```bash
bash scripts/setup.sh
# 原圖可讀取後，實際保存到 assets，並啟動正式渲染：
.venv/bin/python -m space_emoji --import-background /path/to/original.png
```

已在 `assets/glass-container.png` 保存原圖後：

```bash
.venv/bin/python -m space_emoji
```

預設目標：`outputs/emoji-space-merge.mp4`，**1080 × 1920、30 FPS、900 影格、30 秒、H.264 yuv420p、立體聲 AAC 48 kHz、faststart**。成功完成全面解碼驗證才會將影片發布至最終檔名。另輸出 `.report.json`、`.events.json` 及四張 still。預設拒絕覆寫既有成品；可另給 `--output` 或明確 `--overwrite`。

## 原圖與物理對位

- 不生成、不重畫容器；以原始 PNG 當底圖，保留顏色、黑底、發光及連續導軌。
- 原檔整體等比例放入 1080 × 1920，絕不裁切或拉伸。原檔不改寫。
- 物理邊界為一條從左導軌繞過球形底部接到右導軌的連續折線；**不閉合入口、不放橫向碰撞線**。
- JSON 使用全畫面標準化座標，只保存左內壁；右側鏡射產生。若取得原檔後發現左右非對稱，需將幾何擴充為完整描線。
- 對位檢查圖是獨立診斷輸出，絕不混入正式畫面：

```bash
.venv/bin/python -m space_emoji --calibrate /tmp/glass-collision-overlay.png
```

需根據原圖確認所有點位落在**內壁**，包含入口轉彎及底部；完成檢查後更新 JSON 的 `reference_registration` 紀錄。原圖欠缺時，渲染器明確失敗，不偷偷替換背景。

## 模擬與視覺

⭐ → 🌙 → 🪐 → 🌍 → ☀️ → 🌌 → 🚀。使用已提交的 Twemoji 彩色 PNG，輕陰影與光暈，沒有厚球殼。署名及 CC BY 4.0 授權見 `assets/emoji/README.md`。標題放在玻璃球下方黑色留白，避免遮擋貫穿畫面頂部的入口及雙導軌。

Pymunk 固定 240 Hz，30 FPS 每影格八個子步進。只有相同等級真實接觸才能合併，碰撞回呼之後才處理；同一球僅能被消耗一次。新球保留質量及線動量，局部向內修正出生位置，若增大後會撞入第三顆球則等待安全空間。最高級不能再合併。半徑 35–102 px，通道只投放可容納的第 1–5 級；銀河與火箭均由合併產生。

投放機率隨影片進度解鎖，後期偏向等待配對的等級；沒有依時間強制合併，也不直接生成最終級。火箭出現後仍繼續投放，最後 0.8 秒停止新增，讓入口中的球自然落下。不同種子不保證出現最終級。

## 音效與驗證

所有音效從實際物理接觸／合併事件合成：玻璃 Tink、球體 Pop/Boing、升級 Pop+Ding、最終成功提示。碰撞力度控制音量、位置控制立體聲，具有每對冷卻、全域節流、最多八個聲部與柔和限幅。沒有背景音樂、人聲或下載的音效取樣。聲音時間補償一影格呈現偏移，合併特效取自相同事件。

```bash
# 完整測試：包含原汽車版本回歸測試、新主題及真實 FFmpeg 編解碼
.venv/bin/python -m unittest discover -s tests -v
# 不需要圖片的完整 30 秒物理模擬及聲音合成；這不代表影片已完成
.venv/bin/python -m space_emoji --audio-only
# 自訂輸出（原圖仍為必要條件）
.venv/bin/python -m space_emoji --seed 42 --output outputs/alternate.mp4
```

測試使用的純色 PNG 僅為隔離的短片編解碼測試 fixture，存於自動清除的暫存目錄；它不是替代背景或影片交付物。正式驗證會檢查影格數、解析度、FPS、H.264/AAC、音訊時長及整支影片完整解碼。

渲染以逐影格管線寫入 FFmpeg，記憶體不隨影片影格數增長；四個 CPU 編碼執行緒，不需 GPU、外部服務或 API Key。

## 本次實測結果

種子 42、投放間隔 0.40 秒：完整 900 影格物理模擬投放 **73 顆**、完成 **38 次合併**，首次火箭為 **25.1875 秒**。音軌保留 **429 個**事件聲音（67 撞壁、324 球碰撞、37 一般升級、1 次最終升級），峰值 0.518，最多同時 7 個聲部。30 項自動測試全數通過，包括原汽車版本回歸、完整 30 秒新主題模擬及短片 H.264/AAC 編解碼。

這些結果僅證明模擬、音效及編碼管線；玻璃原檔仍缺，**正式 1080 × 1920／30 秒 MP4 的影格與畫面驗證尚未執行**。正式渲染指令已實際嘗試，因缺少原始 PNG 以退出碼 1 結束。
