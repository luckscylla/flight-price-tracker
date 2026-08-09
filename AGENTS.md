# AGENTS.md

本檔提供 opencode（AI 程式助手）在處理本專案時需要的專案知識與環境限制，請在動工前先讀過。

## 專案概要

- **flight-price-tracker**：定時查詢機票價格（資料來源 Google Flights），低於目標價時透過 **LINE Messaging API** 發通知。
- 排程靠 **GitHub Actions**（每日 09:00 / 21:00 台灣時間，`0 1,13 * * *` UTC），手動可用 workflow_dispatch。
- LINE 對話式設定（`/set`）由 **Google Apps Script（GAS）** 接收器處理，設定寫入公開 **Gist**，Actions 每次執行用 `curl` 下載。
- 語言：程式碼註解、README、簡報皆為**繁體中文**，沿用此慣例。
- 文件與詳細流程見 `README.md`、`CHECKLIST.md`；GitHub Pages 未啟用，repo 為私有。

## 專案結構

```
main.py                          # 主程式：合併設定 → 查價 → 比價 → 通知 → 記錄
config.yaml                      # 預設設定（LINE 設定會覆蓋 search 區塊）
.env.example                     # LINE 憑證範本（真憑證只放 .env，勿提交）
tracker/
  config.py                      # 讀取 config.yaml + .env
  settings.py                    # 合併 settings.json（LINE 設定覆蓋預設值）
  search.py                      # Google Flights 查價（含 TWD 幣別修正）
  notify.py                      # LINE Push 通知
  history.py                     # 寫入 data/history.csv
scripts/
  gas_code.gs                    # LINE 對話接收器（貼到 Google Apps Script）
  build_slides.py                # 把 PRESENTATION.md 轉成 presentation.html
.github/workflows/flight-check.yml
PRESENTATION.md                  # Marp 簡報（開發旅程紀錄）
presentation.html                # 由 build_slides.py 產生的可分享 HTML 簡報
data/                            # gitignored（history.csv 執行後產生）
settings.json                    # gitignored（Actions 下載的 LINE 設定快取）
```

## 常用指令

```bash
# 安裝依賴（本機測試）
pip install -r requirements.txt

# 本機執行一次查價（未填 LINE 憑證時會略過通知，仍查價並寫 history.csv）
cp .env.example .env   # 填好 LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID
python main.py

# 重新產生簡報 HTML（改過 PRESENTATION.md 後執行）
python3 scripts/build_slides.py
```

## 環境陷阱（重要，都是實際踩過的問題）

1. **WSL 內不能用 `npx`**：PATH 上的 `npx` 是 Windows 版（會報 `/bin/sh^M: bad interpreter`）。要跑 npm 工具時改用 Windows：
   ```bash
   cmd.exe /c "cd /d D:\AI\flight-price-tracker && npx --yes @marp-team/marp-cli --version"
   ```
   （路徑要用 Windows 格式 `D:\...`。）
2. **Windows Node 是 v10.15.3**，跑不動 marp-cli（需 Node 16+）。**不要**嘗試用 marp CLI 轉檔，請用 `python3 scripts/build_slides.py`。
3. **本機沒有 Docker、沒有 `gh`**，不要假設它們可用。
4. **簡報轉 PPTX/PDF 需要 Chrome/Chromium**（本機未安裝）；Marp 原始檔 `PRESENTATION.md` 保留為可編輯來源，`presentation.html` 可直接分享／列印成 PDF。
5. **GitHub Pages 免費方案只限公開 repo**；本 repo 為私有，故未啟用 Pages。分享簡報用 `presentation.html` 檔案或 htmlpreview（公開 repo 才有效）。

## 程式碼重點

- **幣別強制 TWD**：`tracker/search.py` 的 `_force_currency()` 會把 `curr=` 注入 `gf_search.fetcher._GF_SEARCH_URL`，`google_flights_url()` 產生的連結也帶 `curr`。兩處需保持同步；改動幣別邏輯時兩個函式都要檢查。
- 通知金額來自 `parse_price()`（解析 `"TWD 8,900"` 這類字串）；最低價挑選在 `find_cheapest()`。
- 設定覆蓋順序：`config.yaml` → `settings.json`（LINE 設定）→ 執行時實際生效。

## 部署與機密

- GitHub Secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`、`SETTINGS_GIST_RAW_URL`。
- 機密只能放 `.env` 與 GitHub Secrets；`.env`、`data/`、`settings.json` 已在 `.gitignore`。
- GAS 的 `?key=` 是 webhook 存取密鑰；改 GAS 程式碼後要重新部署新版本。
- Actions cron 使用 UTC；repo 連續 60 天無活動時排程會停用。
- push 走 SSH：`origin = git@github.com:luckscylla/flight-price-tracker.git`。

## opencode session 續接

- 開發旅程的完整對話記錄在本地 `~/.local/share/opencode/opencode.db`。
- 續接上次對話：`opencode --continue`；續接指定：`opencode --session <ID>`；列出：`opencode session list`；備份：`opencode export <ID>`。
- 本專案主要開發 session（2026-08 建立）：`ses_01f2e857cffeQ8oHdPPqXRhMBK` 與 `ses_01f3d3813ffeORIlnV8L6ErHTv`。
