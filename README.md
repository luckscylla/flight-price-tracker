# flight-price-tracker

定時查詢機票價格，當票價低於目標價時，透過 **LINE**（Messaging API）發送通知。使用 **Google Flights** 作為資料來源，以 **GitHub Actions** 每天自動執行兩次（台灣時間 09:00 / 21:00），並可透過 **LINE 對話**即時修改查詢航線、日期與目標價。

---

## 架構

```
LINE 使用者 ──訊息──> LINE Messaging API ──webhook──> GAS 接收器（免費、零管理）
   ▲                                                    │ 對話式設定（Reply API，不計費）
   │  Push API（~60 則/月，免費 200 額度內）             │ 寫入 GitHub Gist
   │                                                    ▼
   └────── GitHub Actions（每日 09:00/21:00）──下載 Gist 設定──> 查 Google Flights
```

- **查價排程**：GitHub Actions（免費、雲端、免開機）
- **LINE 對話設定**：Google Apps Script 接收器（免費、永遠在線、免維護）
- **設定儲存**：GitHub Gist（Actions 每次執行下載最新版）

---

## 開發過程紀錄

### 需求演進
1. 原始需求：定時查詢機票價格並發送通知。
2. 第一版：固定 `config.yaml` 設定、Telegram 通知、GitHub Actions 排程。
3. 演進版（現況）：改用 **LINE**，可透過 LINE 對話（`/set`）即時修改起點／終點／日期／單程來回／目標價，設定存於 Gist，排程每次讀取最新設定後再查價。

### 決策紀錄

| 決策 | 說明 |
|------|------|
| 捨棄 LINE Notify | LINE 官方公告 Notify 已於 **2025/3/31 終止**，改採仍活躍的 **LINE Messaging API（官方帳號）** |
| 捨棄 Telegram | 使用者偏好統一使用 LINE |
| 資料來源 Google Flights 爬蟲 | 免 API key、支援 TWD、涵蓋台灣機場 |
| 排程 GitHub Actions | 免伺服器、雲端定時、可手動觸發 |
| 對話接收器 Google Apps Script | 免費、Web App 常駐、不需開機；LINE 只支援 webhook，GAS 符合此機制 |
| 設定存 GitHub Gist | 不污染 repo、Actions 以 `curl` 下載 raw 即可 |

### 計費說明
- LINE 對話回覆（Reply API）：**不計費**
- 降價通知（Push API）：計入每月訊息額度，免費方案 200 則/月，本專案約 60 則/月 → **零成本**
- GAS 與 GitHub Actions：免費額度內

---

## 專案結構

```
flight-price-tracker/
├── config.yaml                          # 預設設定（LINE 對話設定會覆蓋 search 區塊）
├── .env.example                         # LINE 憑證範本
├── .gitignore
├── requirements.txt
├── main.py                              # 主程式：合併設定 → 查價 → 比價 → 通知 → 記錄
├── scripts/
│   └── gas_code.gs                      # LINE 對話式設定接收器（貼到 Google Apps Script）
├── tracker/
│   ├── config.py                        # 讀取 config.yaml + .env
│   ├── settings.py                      # 合併 settings.json（LINE 設定覆蓋預設值）
│   ├── search.py                        # Google Flights 查價
│   ├── notify.py                        # LINE Push 通知
│   └── history.py                       # 寫入查詢歷史 CSV
├── .github/workflows/flight-check.yml   # 每日兩次排程（下載 Gist 設定後執行）
└── data/history.csv                     # 查詢歷史（執行後產生，不提交）
```

---

## 環境需求

- Python 3.10+（本機測試用）
- 一個 GitHub 帳號（排程 + Gist）
- 一個 LINE 帳號 + LINE 官方帳號（收通知與對話）
- 一個 Google 帳號（部署 GAS 接收器）

---

## 一次性的帳號設定

> 完整逐步操作請見 [CHECKLIST.md](CHECKLIST.md)（從零到上線的打勾清單）。

### 1. LINE 官方帳號（Messaging API）

1. 前往 [LINE Developers Console](https://developers.line.biz/console/) 登入。
2. 建立 **Provider** → 建立 **Messaging API channel**（LINE Official Account）。
3. 在 Channel 設定頁取得：
   - **Channel Secret**
   - **Channel Access Token**（`Messaging API` 頁籤，可 Issuing）
4. 記下後續在 LINE 對話的 **user id**（GAS 接收器可在訊息事件中取得）。

> 申請與費用規則以 LINE 官方為準；免費方案即可滿足本專案。

### 2. GitHub Gist

1. 建立一個 **公開 Gist**，內含一個檔名為 `settings.json` 的檔案，內容範例：
   ```json
   {
     "search": {
       "origin": "TPE",
       "destination": "NRT",
       "departure_date": "2026-10-01",
       "return_date": "",
       "target_price": 15000
     }
   }
   ```
2. 複製 Gist 的 **Raw 網址**（`https://gist.githubusercontent.com/<user>/<id>/raw/<file>`）與 **Gist ID**。

### 3. GitHub PAT

1. GitHub → Settings → Developer settings → Personal access tokens → Generate new token（**僅勾選 `gist`** 權限）。
2. 此 token 給 GAS 用（寫入 Gist）。

### 4. 部署 GAS 接收器

1. 開啟 [script.google.com](https://script.google.com) 建立新專案。
2. 把 `scripts/gas_code.gs` 內容貼入，並填寫上方 CONFIG 區塊：
   - `CHANNEL_ACCESS_TOKEN`、自訂的 `WEBHOOK_KEY`、`GH_PAT`、`GIST_ID`
3. 部署 → **網頁應用程式** → 執行身分：自己／存取權限：**任何人** → 部署。
4. 複製 Web App 網址，結尾加上 `?key=<WEBHOOK_KEY>`，作為 **LINE Webhook URL**。

### 5. 串接 LINE

1. LINE Developers Console → 你的 Channel → **Messaging API** 頁籤。
2. 將「含 `?key=` 的 GAS 網址」填入 **Webhook URL** → 啟用 **Use webhook**。
3. 用 LINE 掃描官方帳號的 QR Code 加為好友，傳 `/help` 測試。

---

## 本機測試

```bash
cd flight-price-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 填入 LINE_CHANNEL_ACCESS_TOKEN 與 LINE_USER_ID
python main.py
```

> 未填入 LINE 憑證時會略過通知，但仍會查價並寫入 `data/history.csv`。

## 在 LINE 對話使用的指令

| 指令 | 說明 |
|------|------|
| `/set` | 開始對話式設定：起點 → 終點 → 出發日期 → 單程/來回 →（回程）→ 目標價 → 確認 |
| `/config` | 顯示目前有效設定 |
| `/cancel` | 取消進行中的設定 |
| `/help` | 顯示指令說明 |

設定完成後會寫入 Gist，下一次排程（或手動觸發 workflow）即以新設定查詢。

---

## 部署到 GitHub Actions

1. 建立 repository 並推送：
   ```bash
   git init
   git add .
   git commit -m "flight price tracker (LINE)"
   git remote add origin https://github.com/<你>/<repo>.git
   git push -u origin main
   ```

2. 到 repo 頁面 **Settings → Secrets and variables → Actions → New repository secret**：
   - `LINE_CHANNEL_ACCESS_TOKEN` → Channel Access Token
   - `LINE_USER_ID` → 你的 LINE user id
   - `SETTINGS_GIST_RAW_URL` → Gist 的 Raw 網址

3. 到 **Actions → Flight Price Check → Run workflow** 手動觸發測試；之後每日 09:00 / 21:00（台灣時間）自動執行。

> 注意：GitHub Actions 的 cron 排程約有數分鐘誤差，且 repository 若連續 **60 天沒有任何活動**，排程會自動停用（需重新推送或手動觸發一次）。

---

## 調整排程

修改 `.github/workflows/flight-check.yml` 中的 cron 即可。cron 使用 **UTC**，台灣時間 = UTC + 8：

| 台灣時間 | cron（UTC） |
|----------|-------------|
| 09:00 / 21:00（目前） | `0 1,13 * * *` |
| 08:00 / 20:00 | `0 0,12 * * *` |

---

## 注意事項

- `google-flights-search` 是非官方介面，Google 可能隨時變更格式；偶發查無結果屬正常。
- 目標價低於現價時不會發通知，但每次查詢仍會寫入 `data/history.csv`。
- LINE 憑證與 GitHub PAT 屬機密，務必只放在 `.env` 與 GitHub Secrets，勿提交。
- GAS 的 `?key=` 是 Webhook 的存取密鑰（GAS 無法讀取 header），請用不易猜測的字串。
- 每次修改 GAS 程式碼後，需重新部署一個新版本。
- 機票價格隨時浮動，建議搭配較寬鬆的目標價（如低於常態價 15%）避免漏接。
