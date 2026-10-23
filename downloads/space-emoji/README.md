# Space Emoji Merge — 正式成品

[下載 30 秒 MP4](https://raw.githubusercontent.com/ntuxnkust-create/bouncing-ball-video/feature/space-emoji-merge/downloads/space-emoji/emoji-space-merge.mp4)

**1080 × 1920、9:16、30 FPS、900 影格、30 秒、H.264 yuv420p、AAC 48 kHz 立體聲、faststart。** 全片影音已完整解碼驗證。僅實際碰撞／合併事件音效，沒有背景音樂或人聲。

正式背景使用上傳的 `霓虹玻璃实验烧瓶.png`，原樣保存到 `assets/glass-container.png`，兩份檔案完全一致。已校正內壁碰撞描線；入口雙導軌連到下方玻璃球，沒有橫向碰撞線或替換容器。Emoji 與音效沿用現有系統。

當次模擬：73 顆投放、44 次合併，第 24.975 秒出現火箭。音軌含 436 個經節流保留的同步事件聲音。31 項測試通過，原汽車版本及宇宙模擬／音效程式保留。

- [`emoji-space-merge.mp4`](emoji-space-merge.mp4)：正式成品，約 6.6 MB。
- [`space-emoji-merge-source.zip`](space-emoji-merge-source.zip)：完整原始碼、正式背景 PNG、七張 Emoji 素材、物理幾何、測試及執行說明；不包含生成的下載媒體，以免封裝遞迴。
- [`emoji-space-merge.report.json`](emoji-space-merge.report.json)：當次正式影片規格、完整解碼、物理與音效驗證。
- [`emoji-space-merge.events.json`](emoji-space-merge.events.json)：實際碰撞及合併事件。
- [`emoji-space-merge.effects.m4a`](emoji-space-merge.effects.m4a)：從正式 MP4 原樣擷取的 AAC 音軌，供獨立試聽。
- [`glass-collision-overlay.png`](glass-collision-overlay.png)：原圖上的校正描線診斷圖，沒有混入正式影片。
- [`test-results.txt`](test-results.txt)：31 項測試通過的完整紀錄。
- [`delivery-status.json`](delivery-status.json)：來源 commit、檔案 SHA-256 與完整交付狀態。

重新渲染：

```bash
bash scripts/setup.sh
.venv/bin/python -m space_emoji
```

輸出 `outputs/emoji-space-merge.mp4`。若已有同名輸出，請改用其他 `--output` 路徑，或明確加入 `--overwrite`。完整說明見 [`SPACE_EMOJI.md`](../../SPACE_EMOJI.md)。

Emoji artwork: Twemoji 14.0.2, © Twitter, Inc. and other contributors, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Scaled, rotated and softly shadowed in the video. See [`assets/emoji/README.md`](../../assets/emoji/README.md) for attribution; please retain credit when publishing (for example in the post description). Sound effects are original procedural synthesis.
