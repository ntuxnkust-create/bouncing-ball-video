# Space Emoji Merge — delivery status

**正式 MP4 尚未產生。** 對話中看得到玻璃容器圖片，但原始 PNG 未掛載為可讀取檔案；正式渲染實際執行後因缺圖失敗。沒有使用其他背景替代，也沒有把測試影片當成品。

- `space-emoji-merge-source.zip`：完整原始碼，包括原汽車版本及獨立 Space Emoji 模組、七張彩色 Emoji 素材、初步內壁描線、測試及執行說明。**尚不包含無法讀取的玻璃 PNG。**
- `emoji-space-merge.effects.m4a`：完整 30 秒立體聲 AAC 純音效，可獨立試聽；依完整物理事件合成，沒有背景音樂或人聲。這是音軌，不是影片。
- `emoji-space-merge.simulation.json`：當次完整 900 影格物理模擬及音訊混音報告。
- `emoji-space-merge.events.json`：全部實際碰撞及升級事件。
- `test-results.txt`：30 項測試通過的完整輸出；其中短片編碼 fixture 不代表正式影片驗證。
- `delivery-status.json`：當次完整狀態、來源 commit、實際渲染失敗原因及未執行的正式驗證。

取得原始 PNG 後，先實際檢查內壁描線與原圖對齊，再執行：

```bash
bash scripts/setup.sh
.venv/bin/python -m space_emoji --import-background /path/to/original.png
```

預設成品路徑：`outputs/emoji-space-merge.mp4`。執行說明：[`../../SPACE_EMOJI.md`](../../SPACE_EMOJI.md)。
