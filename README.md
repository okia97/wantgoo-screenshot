# 玩股網 截圖自動化工具

每週日 12:00 自動截取印度 / 泰國 / 印尼 / 澳洲指數的日線、周線、月線圖，依日期儲存為 PNG。

## 資料夾結構

```
wantgoo-screenshot/
├── screenshot.py      ← 主程式
├── requirements.txt   ← 依賴套件
├── setup.sh           ← 一鍵安裝 + 設定排程
└── logs/              ← 執行記錄（自動建立）
```

截圖輸出至：`/Users/LIWEN/Documents/技術線/玩股網截圖/<YYYY-MM-DD>/`

---

## 快速安裝

```bash
bash setup.sh
```

安裝內容：
1. 建立 Python 虛擬環境 `.venv`
2. 安裝 `playwright`、`Pillow`
3. 下載 Chromium
4. 設定 macOS launchd 每週日 12:00 自動執行

---

## 手動執行

```bash
.venv/bin/python screenshot.py
```

---

## 常用指令

| 目的 | 指令 |
|------|------|
| 立即執行 | `.venv/bin/python screenshot.py` |
| 手動觸發排程 | `launchctl start com.user.sensex` |
| 查看排程狀態 | `launchctl list \| grep sensex` |
| 停用排程 | `launchctl unload ~/Library/LaunchAgents/com.user.sensex.plist` |

---

## 截圖輸出格式

每次執行會在輸出目錄下建立日期子資料夾，產生 12 張 PNG：

```
sensex_daily.png   set_daily.png   jci_daily.png   alo_daily.png
sensex_weekly.png  set_weekly.png  jci_weekly.png  alo_weekly.png
sensex_monthly.png set_monthly.png jci_monthly.png alo_monthly.png
```
