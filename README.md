# flight-price-tracker

定時查詢機票價格，當票價低於目標價（如 NT$ 15,000）時，透過 **Telegram Bot** 發送通知。使用 **Google Flights** 作為資料來源，並以 **GitHub Actions** 每天自動執行兩次（台灣時間 09:00 / 21:00）。

---

## 開發過程紀錄

### 需求分析
原始需求為「定時查詢機票價格並發送通知」，包含四大功能：

| 需求 | 選定方案 | 原因 |
|------|----------|------|
| 票價查詢 | Google Flights 爬蟲（`google-flights-search`） | 免 API key、支援 TWD、涵蓋台灣機場 |
| 通知 | Telegram Bot | LINE Notify 已終止服務，Telegram 免費且設定簡單 |
| 排程 | GitHub Actions cron | 免伺服器、雲端定時、可手動觸發 |
| 程式語言 | Python 3.10+ | 生態系成熟、爬蟲與通知套件齊全 |

### 決策紀錄

1. **捨棄 LINE Notify**：LINE 官方公告 LINE Notify 已於 **2025/3/31 終止服務**，2025/4/1 起所有 API（`notify-api.line.me`）皆無法使用，故改採 **Telegram Bot**。
2. **資料來源選 Google Flights 爬蟲**而非 Amadeus API：Amadeus 需註冊申請金鑰且有免費額度限制；`google-flights-search` 由台灣開發者維護、可直接以 TWD 計價，符合本專案需求。缺點是屬於非官方介面，Google 改版時可能需更新套件。
3. **排程採用 GitHub Actions** 而非本機 Cron / schedule 套件：不需常駐伺服器，免費且可於網頁手動觸發；Token 存放在 repo Secrets，不會洩漏到程式碼。

### 實作流程
1. 建立專案結構（`tracker/` 模組化設定、查價、通知、記錄四層）。
2. 以 `config.yaml` 集中管理航線／日期／目標價，機密（Telegram token）放 `.env`（被 `.gitignore` 排除）。
3. 撰寫 `tracker/search.py` 包裝 `gf_search.search()`，提供價格字串解析（`"TWD 8,900"` → `8900`）與最低價挑選。
4. 撰寫 `tracker/notify.py` 呼叫 Telegram `sendMessage` API，缺 token 時僅記錄警告、不中斷主流程。
5. 撰寫 `tracker/history.py` 將每次查詢結果寫入 `data/history.csv`，利於追蹤價格趨勢。
6. 撰寫 `.github/workflows/flight-check.yml`，以 cron `0 1,13 * * *`（UTC）每日 09:00 / 21:00（台灣時間）執行。
7. 本機以無 token 的「演練模式」驗證設定載入、價格解析、CSV 記錄與訊息組裝。

---

## 專案結構

```
flight-price-tracker/
├── config.yaml                          # 航線/日期/目標價/通知設定
├── .env.example                         # 環境變數範本
├── .gitignore
├── requirements.txt
├── main.py                              # 主程式：查價 → 比價 → 通知 → 記錄
├── tracker/
│   ├── config.py                        # 讀取 config.yaml + .env
│   ├── search.py                        # Google Flights 查價
│   ├── notify.py                        # Telegram 通知
│   └── history.py                       # 寫入查詢歷史 CSV
├── .github/workflows/flight-check.yml   # 每日兩次排程
└── data/history.csv                     # 查詢歷史（執行後產生）
```

---

## 環境需求

- Python 3.10+（本機測試用）
- 一個 GitHub 帳號（部署排程用）
- 一個 Telegram 帳號（收通知用）

---

## 安裝與本機測試

```bash
cd flight-price-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 設定

1. 複製設定檔與環境變數範本：

```bash
cp .env.example .env
```

2. 編輯 `config.yaml` 調整航線、日期、目標價：

```yaml
search:
  origin: TPE
  destination: NRT
  departure_date: "2026-10-01"
  target_price: 15000
```

3. 取得 Telegram 資訊填入 `.env`（教學見下節）。

### 執行

```bash
# 無 token 演練：仍會查價並寫入歷史，但不發通知
python main.py
```

---

## Telegram Bot 設定教學

1. 在 Telegram 搜尋 **@BotFather**，傳送 `/newbot`，依指示命名，取得 **Bot Token**。
2. 將新機器人加入好友，並傳送任一訊息給它。
3. 搜尋 **@userinfobot**，傳送 `/start`，畫面上顯示的 `Id` 即為 **Chat ID**。
4. 將兩者填入 `.env`：

```
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789
```

---

## 部署到 GitHub Actions

1. 在 GitHub 建立 repository，將本專案推送上去：

```bash
git init
git add .
git commit -m "flight price tracker"
git remote add origin https://github.com/<你>/<repo>.git
git push -u origin main
```

2. 到 repo 頁面 **Settings → Secrets and variables → Actions → New repository secret**：
   - `TELEGRAM_BOT_TOKEN` → 填入 Bot Token
   - `TELEGRAM_CHAT_ID` → 填入 Chat ID

3. 設定後即會依 cron 每天 09:00 / 21:00（台灣時間）自動執行；也可到 **Actions → Flight Price Check → Run workflow** 手動觸發測試。

> 注意：GitHub Actions 的 cron 排程約有數分鐘誤差，且 repository 若連續 **60 天沒有任何活動**，排程會自動停用（需重新推送或手動觸發一次）。

---

## 調整排程

修改 `.github/workflows/flight-check.yml` 中的 cron 即可。cron 使用 **UTC**，台灣時間 = UTC + 8：

| 台灣時間 | cron（UTC） |
|----------|-------------|
| 09:00 / 21:00（目前） | `0 1,13 * * *` |
| 08:00 / 20:00 | `0 0,12 * * *` |

也可改成本機執行：`crontab -e` 加入
```
0 1,13 * * * cd /path/to/flight-price-tracker && .venv/bin/python main.py
```

---

## 注意事項

- `google-flights-search` 是非官方介面，Google 可能隨時變更格式；套件本身內建重試，偶發查無結果屬正常。
- 目標價低於現價時不會發通知，但每次查詢仍會寫入 `data/history.csv`。
- Telegram token 屬機密資訊，務必只放在 `.env` 與 GitHub Secrets，勿提交到 Git。
- 機票價格隨時浮動，建議搭配較寬鬆的目標價（如低於常態價 15%）避免漏接。
