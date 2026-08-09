# 從零到上線檢查表（LINE 版 flight-price-tracker）

照著打勾即可完成 LINE 對話設定 + GitHub Actions 排程查價。

---

## □ 前置準備
- [ ] 確認已有 GitHub 帳號（repo：`luckscylla/flight-price-tracker`）
- [ ] LINE 帳號（手機 App）
- [ ] Google 帳號

## □ Step 1：建立 LINE 官方帳號（Messaging API）
- [ ] 開啟 https://developers.line.biz/console/ 登入
- [ ] 建立 **Provider**（名稱隨意，如 `flight-tracker`）
- [ ] 建立 **Messaging API channel**（LINE Official Account，選免費方案）
- [ ] 進入 Channel 設定 → **Channel Secret** 記下
- [ ] **Messaging API 頁籤** → 按 **Issue** 產生 **Channel Access Token**，記下

> 這兩個值稍後填入 GAS 與 GitHub Secrets。

## □ Step 2：建立 GitHub Gist
- [ ] 登入 https://gist.github.com
- [ ] `Gist description` 填 `flight-price-tracker settings`
- [ ] `Filename including extension` 填 **`settings.json`**（檔名必須是這個）
- [ ] 內容貼上：
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
- [ ] 選 **Create public gist** → 按建立
- [ ] 記錄 **Gist ID**（網址 `.../gist.github.com/<你>/<ID>` 中的 `<ID>`）
- [ ] 按 **Raw** → 記錄 **Raw URL**（整串 `https://gist.githubusercontent.com/.../settings.json`）

## □ Step 3：建立 GitHub PAT（僅 gist 權限）
- [ ] GitHub → 右上大頭貼 → **Settings** → 最下方 **Developer settings**
- [ ] **Personal access tokens** → **Tokens (classic)** → **Generate new token**
- [ ] 勾選 **`gist`**（只要這一個）→ **Generate token** → 複製（只顯示一次）

> 此 token 只給 GAS 用，勿貼到 repo。

## □ Step 4：部署 GAS 接收器
- [ ] 開啟 https://script.google.com 登入
- [ ] 把編輯區預設內容清空
- [ ] 從 repo `scripts/gas_code.gs` 複製全部內容貼入
- [ ] 填 CONFIG 區塊（第 24–27 行）：
  - [ ] `CHANNEL_ACCESS_TOKEN` ← Step 1 的 Access Token
  - [ ] `WEBHOOK_KEY` ← 自訂密碼（如 `mypassword123`）
  - [ ] `GH_PAT` ← Step 3 的 PAT
  - [ ] `GIST_ID` ← Step 2 的 Gist ID
  - [ ] `GIST_FILENAME` 維持 `'settings.json'`
- [ ] 右上 **部署 → 網頁應用程式** → 執行身分：**自己**／存取權限：**任何人** → **部署**
- [ ] 複製出現的 **Web App 網址**
- [ ] 在網址尾端加上 `?key=<你的 WEBHOOK_KEY>`，存成「完整 Webhook 網址」

> 例：`https://script.google.com/macros/s/XXXX/exec?key=mypassword123`

## □ Step 5：串接 LINE Webhook
- [ ] LINE Developers Console → 你的 Channel → **Messaging API** 頁籤
- [ ] **Webhook URL** 貼上「完整 Webhook 網址」（含 `?key=`）
- [ ] 開啟 **Use webhook**（會彈出驗證，按驗證）
- [ ] 用 LINE 掃描官方帳號 QR Code **加為好友**
- [ ] 傳 `/help` → 若收到指令說明，代表 webhook + GAS 通了

> 若沒回應：檢查 GAS 是否重新部署、`WEBHOOK_KEY` 是否和網址尾端一致。

## □ Step 6：取得你的 LINE User ID（給 GitHub secret 用）
- [ ] 執行（把你的 Access Token 換進去）：
  ```bash
  curl -X GET "https://api.line.me/v2/bot/followers/ids?limit=100" \
       -H "Authorization: Bearer <你的 Channel Access Token>"
  ```
- [ ] 回應中的 `userIds` 陣列第一個即你的 **LINE User ID**，記下

## □ Step 7：LINE 對話設定實測
- [ ] 傳 `/set` → 依序輸入：起點(TPE) → 終點(NRT) → 日期 → 單程/來回 → 目標價
- [ ] 最後輸入「確認」
- [ ] 收到「✅ 已更新設定並儲存到 Gist」
- [ ] 回 https://gist.github.com 重新整理 → 確認 `settings.json` 內容已變更

## □ Step 8：設定 GitHub Actions Secrets
- [ ] 到 https://github.com/luckscylla/flight-price-tracker/settings/secrets/actions
- [ ] **New repository secret** 新增三個：
  - [ ] `LINE_CHANNEL_ACCESS_TOKEN` ← Step 1 的 Access Token
  - [ ] `LINE_USER_ID` ← Step 6 的 User ID
  - [ ] `SETTINGS_GIST_RAW_URL` ← Step 2 的 Raw URL

## □ Step 9：上線驗證
- [ ] 到 repo → **Actions** → **Flight Price Check** → **Run workflow** → 按綠色按鈕
- [ ] 展開 `check-price` → 確認 log 出現「套用 LINE 設定覆蓋」與最低價
- [ ] **測試通知**：在 LINE 用 `/set` 把目標價改成 `99999`（保證低於現價）→ 觸發 workflow → 應收到 LINE 降價通知
- [ ] 測試完再用 `/set` 把目標價改回 `15000`
- [ ] 之後每日 09:00 / 21:00 自動執行，完工
