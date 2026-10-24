# Space Emoji Merge — 正式成品

[下載 30 秒 MP4](https://raw.githubusercontent.com/ntuxnkust-create/bouncing-ball-video/feature/space-emoji-merge/downloads/space-emoji/emoji-space-merge.mp4)

**1080 × 1920、9:16、30 FPS、900 影格、30 秒、H.264 yuv420p、AAC 48 kHz 立體聲、faststart。** 全片影音已完整解碼驗證。僅實際碰撞／合併事件音效，沒有背景音樂或人聲。

正式背景使用上傳的 `霓虹玻璃实验烧瓶.png`，原樣保存到 `assets/glass-container.png`，兩份檔案完全一致。已校正內壁碰撞描線；入口雙導軌連到下方玻璃球，沒有橫向碰撞線或替換容器。Emoji 與音效沿用現有系統。

修正版已移除「擁擠就取消同級合併」的判斷；地球接觸即升級為太陽，再用不增加速度的位置修正分開周圍球體，持續保持在玻璃內壁內。新生球不再略過同級碰撞，Emoji 輪廓也已對齊圓形碰撞範圍。

當次模擬：73 顆投放、51 次合併，其中 8 次地球升級為太陽，擁擠取消合併為 0 次；第 24.5583 秒出現火箭。音軌含 397 個經節流保留的同步事件聲音。35 項測試通過，包含逐次稽核完整 900 影格的同級接觸，以及擁擠地球、靠壁升級、輪廓對位與重複合併回歸測試。原汽車版本、玻璃圖與音效合成器保留。

- [`emoji-space-merge.mp4`](emoji-space-merge.mp4)：正式成品，約 6.4 MB。
- [`space-emoji-merge-source.zip`](space-emoji-merge-source.zip)：完整原始碼、正式背景 PNG、七張 Emoji 素材、物理幾何、測試及執行說明；不包含生成的下載媒體，以免封裝遞迴。
- [`emoji-space-merge.report.json`](emoji-space-merge.report.json)：當次正式影片規格、完整解碼、物理與音效驗證。
- [`emoji-space-merge.events.json`](emoji-space-merge.events.json)：實際碰撞及合併事件。
- [`emoji-space-merge.effects.m4a`](emoji-space-merge.effects.m4a)：從正式 MP4 原樣擷取的 AAC 音軌，供獨立試聽。
- [`glass-collision-overlay.png`](glass-collision-overlay.png)：原圖上的校正描線診斷圖，沒有混入正式影片。
- [`test-results.txt`](test-results.txt)：35 項測試通過的完整紀錄。
- [`delivery-status.json`](delivery-status.json)：來源 commit、檔案 SHA-256 與完整交付狀態。

重新渲染：

```bash
bash scripts/setup.sh
.venv/bin/python -m space_emoji
```

輸出 `outputs/emoji-space-merge.mp4`。若已有同名輸出，請改用其他 `--output` 路徑，或明確加入 `--overwrite`。完整說明見 [`SPACE_EMOJI.md`](../../SPACE_EMOJI.md)。

Emoji artwork: Twemoji 14.0.2, © Twitter, Inc. and other contributors, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Scaled, rotated and softly shadowed in the video. See [`assets/emoji/README.md`](../../assets/emoji/README.md) for attribution; please retain credit when publishing (for example in the post description). Sound effects are original procedural synthesis.
