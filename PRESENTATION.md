---
marp: true
theme: default
paginate: true
header: "用 opencode 開發 flight-price-tracker"
footer: "從需求到上線的完整旅程"
---

<!-- _paginate: false -->

# 用 opencode 開發 flight-price-tracker

### 從一句需求到一個會自己查機票、自動通知的系統

一個「AI 對談式開發」的完整實作紀錄 — 包含踩過的坑與解法

---

# 這個專案在做什麼

> 「我想開發一個**定時查詢機票價格並發送通知**的自動化腳本。」

用一句話，開場就是需求 — 接下來全部靠**與 opencode 對話**完成：

- 🔍 **查價**：Google Flights，支援 TWD
- 🔔 **通知**：低於目標價就推 LINE
- ⏰ **排程**：每天自動跑兩次
- 💬 **設定**：在 LINE 上直接改航線／日期／目標價

---

# 需求 → 技術選型

| 需求 | 選定方案 | 為什麼 |
|------|----------|--------|
| 程式語言 | Python 3.10+ | 爬蟲／API 生態系成熟 |
| 查價來源 | `google-flights-search` 爬蟲 | 免 API key、支援 TWD、涵蓋台灣機場 |
| 通知 | LINE Messaging API | LINE Notify 已終止；最後演進至 LINE |
| 排程 | GitHub Actions cron | 免伺服器、雲端定時、可手動觸發 |
| 設定介面 | LINE 對話式 `/set` | 免改設定檔、即時生效 |

---

# 整個開發過程的「問題與解法」地圖

這趟旅程並非一帆風順，總共踩了 **7 個坑**，全部在對話中邊做邊解決：

| # | 問題 | 關鍵解法 |
|---|------|----------|
| 1 | LINE Notify 終止 | 改用 Telegram（第一版） |
| 2 | 排程雲端無狀態 | 對話設定寫進 Gist，排程讀取 |
| 3 | 想讀 Telegram user bio | 不可行（隱私）→ 改為 LINE 置頂訊息思路 |
| 4 | LINE 收訊機制 | 只能 webhook → 選 Google Apps Script |
| 5 | GAS webhook Verify 302 | ContentService redirect 限制，實際投遞正常 |
| 6 | `followers/ids` API 不可用 | 免費方案限制 → 靠 webhook 註冊 userId |
| 7 | 幣別跑掉（237 vs 7641） | 伺服器 IP 決定幣別 → 強制 `curr=TWD` |

---

# 坑 1：LINE Notify 已終止

**現象**：原始需求直接指名用「LINE Notify / Telegram Bot / Email」。

**發現**：LINE 官方公告 **LINE Notify 已於 2025/3/31 終止服務**。

**決策**：
- 第一版改用 **Telegram Bot**（免費、設定簡單）
- 之後使用者偏好 LINE → 用「**LINE Messaging API（官方帳號）**」——它跟 Notify 是兩回事，仍然活躍

> 重點：**別把「Notification 服務」和「Messaging API」搞混**，判斷前先查官方文件與最新公告。

---

# 坑 2：GitHub Actions 是無狀態的

**衝突**：Telegram／LINE Bot 需要「**一直在跑的程式**」才能收訊息；GitHub Actions 跑完即消失，存不住任何設定。

**架構演進（在對話中逐步收斂）**：

```
想法A：本機常駐 → 需要一直開機的機器 ✗
想法B：Bot 把設定寫回 repo → 會污染 repo、多一層 API ✗
方案C：設定存 GitHub Gist，排程每次下載 → ✓ 乾淨、即時生效
```

**最終架構**：
```
LINE 使用者 ──訊息──> GAS 接收器（免費常駐）
                        │ 對話設定 → 寫入 Gist
                        ▼
GitHub Actions ──下載 Gist 設定──> 查價 ──> LINE Push 通知
```

---

# 坑 3：想讀 Telegram 的 user bio？

**想法**：能不能在排程執行時，直接讀 Telegram 使用者的「簡介」當作查詢設定？

**結果：做不到。** Telegram Bot API **不提供 user bio**——這是隱私欄位。

**但這帶出了關鍵設計探索**：
- Telegram 有「置頂訊息 + `getChat`」的**零架設**讀設定法
- LINE 沒有長輪詢、只能 webhook → 需要常駐端點

> 收穫：**「做不到的事」也要被明確驗證**，而不是默默繞過；限制會引導出正確的架構。

---

# 坑 4：LINE 只能 webhook → 選 Google Apps Script

**LINE 與 Telegram 本質不同**：

| | Telegram | LINE |
|---|---|---|
| 收訊息 | 長輪詢（需常駐程式） | **只能 webhook** |
| 需不需要開機 | 是 | 不用，但要公開 HTTPS 網址 |

**選擇 GAS 的原因**：免費、永遠在線、免維護、貼上 `code.gs` 即可部署。

**成本驗證（對話中查證）**：
- Reply API（對話回覆）→ **不計費**
- Push API（降價通知）→ 計入額度，但免費方案 200 則/月，本專案約 60 則/月 → **零成本**

---

# 坑 5：GAS Webhook Verify 一直 302

**現象**：LINE Verify 回 `302 Found`，但瀏覽器／Postman 都正常。

**追查**：
- 先懷疑部署權限 → 無痕模式測試，匿名存取正常
- 網路查證 → 官方文件：`ContentService` 的內容**不會直接回傳**，而是先 **302 redirect** 到一次性網址
- **LINE Verify 不跟隨 redirect → 誤判失敗**

**解法**：
- 加 `doGet` 讓瀏覽器「暖機」可用
- 關鍵測試：**直接開啟 Use webhook、傳真實訊息** → 有回應 = 實際投遞正常

> 教訓：**驗證工具的回報 ≠ 系統真的壞了**；用「最小真實操作」做決定性測試。

---

# 坑 6：`followers/ids` API 不可用

**現象**：想用「取得好友列表」抓通知名單 → `Access to this API is not available for your account`。

**查證**：官方文件 + 社群實測 → 此 API **僅限 verified／付費帳號**，免費方案無權限。

**未來多使用者設計（免費可行）**：
```
使用者加好友 / 傳訊息 ──> webhook 事件帶 source.userId ──> Bot 自動存名單
降價時 ──> 對每個 userId 發 Push（以人數計費，需留意額度）
```

> 收穫：**先確認平台限制再設計功能**，省得白做工。

---

# 坑 7：幣別跑掉 — TWD 237 vs 實際 7641

**現象**：通知顯示 `TWD 237`，點開頁面卻是 `7641`（237 × 32.24 ≈ 7641 = 美金）。

**根因**：`google-flights-search` 請求只送 `hl=zh-TW`、**沒送 `curr`** → Google 依**伺服器 IP 地區**決定幣別；GitHub Actions 在美國 → 回美金，套件卻無條件標成 TWD。

**修法**（`tracker/search.py`）：
```python
# 呼叫前，把套件請求網址注入 curr 參數
if "curr=" not in _gf_fetcher._GF_SEARCH_URL:
    _gf_fetcher._GF_SEARCH_URL += "?" + "curr=TWD"
```

> 教訓：**「本機正常、雲端異常」八成是環境差異**（IP、時區、locale）；用 log 對照再推導。

---

# 最終架構圖

```
┌────────────┐  訊息    ┌──────────────┐  /set 對話設定   ┌──────────┐
│ LINE 使用者 │ ───────► │ LINE Messaging│ ─────────────► │  GAS     │
└────────────┘           │ API          │                 │ 接收器   │
        ▲                └──────────────┘                 └────┬─────┘
        │  Push 通知                                             │ 寫入
        │  （免費額度內）                                        ▼
        │                                               ┌──────────┐
        └───────────────────────────────────────────────│   Gist   │
                                          查價結果        └────┬─────┘
┌──────────────┐  每日 09:00/21:00   ┌──────────┐ 下載最新設定    │
│ GitHub Actions│ ─────────────────► │ 查 Google│ ◄─────────────┘
└──────────────┘                     │  Flights │
                                     └──────────┘
```

---

# opencode 開發流程的特色

整個專案**沒有打開過一次 code editor**，全部透過對話與工具完成：

| 特色 | 這次怎麼用 |
|------|-----------|
| **Plan 模式** | 每次大改前先給架構圖、檔案異動清單、驗證計畫，**使用者確認才動手** |
| **工具驅動** | 自動跑 `git`、`pip`、`python main.py`、`curl`、`websearch` 驗證 |
| **每步驗證** | 改完必跑測試／查價，log 為憑（`TWD 4500` 這種可見結果） |
| **即時查證** | 「LINE Notify 還活著嗎？」「Push 計費？」→ 直接 websearch 官方文件 |
| **問題導向** | 302、幣別、API 限制…全部現場診斷、紀錄解法 |

---

# 成本總結

| 項目 | 成本 |
|------|------|
| GitHub Actions 排程 | 免費 |
| GAS 接收器 | 免費 |
| LINE 官方帳號（免費方案） | NT$0 |
| LINE Push 通知 | 約 60 則/月，免費 200 則內 |
| 總計 | **NT$0** |

**產出**：一個每日自動查價、LINE 對話改設定、降價自動通知的系統，全在對話中完成。

---

# 給想複製這個流程的人

**把對話當「同事」的 3 個原則**：

1. **先 Plan 再 Build** — 讓 AI 先講清楚架構與代價，你確認再動手
2. **要求「可驗證的結果」** — 不要只看程式寫好，要看到 log／測試通過
3. **善用它的工具能力** — git、測試、網路查證都讓它做，你專注在**決策**

**踩坑心法**：
- 平台限制（API 終止、付費牆、redirect）→ **先查官方文件再設計**
- 本機對、雲端錯 → **八成是環境差異**（IP／時區）
- 驗證按鈕失敗 → 用**真實操作**做決定性測試

---

<!-- _paginate: false -->

# Q&A

完整程式碼與操作檢查表：`github.com/luckscylla/flight-price-tracker`

**用 opencode 說一句話，讓它陪你從需求走到上線。**
