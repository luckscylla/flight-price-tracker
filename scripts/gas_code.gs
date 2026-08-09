// ============================================================
// LINE 對話式設定接收器（Google Apps Script）
//
// 功能：
//   1. 接收 LINE webhook（訊息事件）
//   2. 對話式逐步設定：起點/終點/出發日期/單程來回/目標價
//   3. 透過 Reply API 即時回覆（不計入每月訊息額度）
//   4. 設定寫入 GitHub Gist，供 GitHub Actions 下載
//
// 部署步驟：
//   1. 填入下方 CONFIG 區塊的常數
//   2. 部署 → 網頁應用程式 → 執行身分：自己 / 存取權限：任何人 → 部署
//   3. 複製取得的 Web App 網址，並在結尾加上 ?key=<WEBHOOK_KEY>
//      例如：https://script.google.com/macros/s/XXXX/exec?key=mypassword
//   4. 把「含 ?key 的完整網址」填入 LINE Official Account 的 Webhook URL
//
// 注意：
//   - GAS Web App 無法讀取 request header（X-Line-Signature），
//     故以 Webhook URL 上的 ?key= 參數做存取控管，請自訂一組密碼。
//   - 每次改完程式碼記得「部署 → 管理部署 → 編輯 → 新版本 → 部署」。
// ============================================================

// ---------------- CONFIG 區塊（填入你的資料）----------------
var CHANNEL_ACCESS_TOKEN = '填入 LINE Channel Access Token';
var WEBHOOK_KEY = '填入自訂密碼';           // Webhook URL 尾端的 ?key=
var GH_PAT = '填入 GitHub PAT（僅需 gist 權限）';
var GIST_ID = '填入 Gist ID';               // 例如 abc123...（不含 raw 網址）
var GIST_FILENAME = 'settings.json';        // Gist 內的設定檔檔名
// ------------------------------------------------------------

var STATE_PREFIX = 'state_';

var STEPS = {
  ORIGIN: 'origin',
  DEST: 'dest',
  DATE: 'date',
  ROUND: 'round',
  RETURN: 'return',
  TARGET: 'target',
  CONFIRM: 'confirm',
};

var HELP_TEXT = [
  '✈️ 機票追蹤 Bot 指令：',
  '/set  — 開始設定航線',
  '/config — 顯示目前設定',
  '/cancel — 取消進行中的設定',
  '/help — 顯示說明',
].join('\n');

// ============================================================
// webhook 入口
// ============================================================
function doPost(e) {
  // 存取控管：檢查 URL 尾端的 key
  if (!e || e.parameter.key !== WEBHOOK_KEY) {
    return ContentService.createTextOutput('Unauthorized');
  }

  var body = JSON.parse(e.postData.contents);
  var events = body.events || [];
  for (var i = 0; i < events.length; i++) {
    handleEvent(events[i]);
  }
  return ContentService.createTextOutput('OK');
}

function handleEvent(event) {
  if (event.type !== 'message' || event.message.type !== 'text') return;
  if (!event.source || !event.source.userId) return;

  var userId = event.source.userId;
  var replyToken = event.replyToken;
  var text = String(event.message.text).trim();

  if (text.charAt(0) === '/') {
    handleCommand(userId, replyToken, text);
  } else {
    handleConversation(userId, replyToken, text);
  }
}

// ============================================================
// 指令
// ============================================================
function handleCommand(userId, replyToken, text) {
  var cmd = text.split(' ')[0].toLowerCase();
  if (cmd === '/set') {
    setState(userId, { step: STEPS.ORIGIN, data: {} });
    reply(replyToken, '開始設定機票追蹤，隨時可輸入 /cancel 取消。\n\n請輸入起點機場 IATA 代碼（如 TPE）：');
  } else if (cmd === '/config') {
    showConfig(userId, replyToken);
  } else if (cmd === '/cancel') {
    clearState(userId);
    reply(replyToken, '已取消本次設定。');
  } else {
    reply(replyToken, HELP_TEXT);
  }
}

// ============================================================
// 對話式設定
// ============================================================
function handleConversation(userId, replyToken, text) {
  var state = getState(userId);
  if (!state) {
    reply(replyToken, HELP_TEXT);
    return;
  }

  if (text.toLowerCase() === '/cancel') {
    clearState(userId);
    reply(replyToken, '已取消本次設定。');
    return;
  }

  var result = advance(state, text);
  if (result.error) {
    reply(replyToken, result.error);
    return;
  }

  if (result.finished) {
    // 最終確認 → 寫入 Gist
    clearState(userId);
    var ok = saveToGist(result.settings);
    if (ok) {
      reply(replyToken,
        '✅ 已更新設定並儲存到 Gist！\n\n' + formatSettings(result.settings) +
        '\n\n下次排程（每日 09:00 / 21:00）將以此設定查詢。');
    } else {
      reply(replyToken, '⚠️ 儲存失敗，請稍後再試或檢查 GAS 設定。');
    }
    return;
  }

  setState(userId, { step: result.step, data: result.data });
  reply(replyToken, result.ask);
}

// 依目前步驟驗證輸入並推進；回傳 {error} | {finished, settings} | {step, data, ask}
function advance(state, text) {
  var data = state.data || {};
  var step = state.step;

  if (step === STEPS.CONFIRM) {
    if (/^(確認|是|好|yes|y|1)$/i.test(text)) {
      return {
        finished: true,
        settings: { search: buildSearch(data) },
      };
    }
    return {
      error: '未確認，設定未儲存。可輸入 /set 重新開始，或輸入「確認」儲存。',
    };
  }

  switch (step) {
    case STEPS.ORIGIN:
      if (!isIata(text)) return { error: '機場代碼需為 3 碼英文字母（如 TPE），請重新輸入：' };
      data.origin = text.toUpperCase();
      return { step: STEPS.DEST, data: data, ask: '請輸入終點機場 IATA 代碼（如 NRT）：' };

    case STEPS.DEST:
      if (!isIata(text)) return { error: '機場代碼需為 3 碼英文字母（如 NRT），請重新輸入：' };
      data.destination = text.toUpperCase();
      return { step: STEPS.DATE, data: data, ask: '請輸入出發日期（格式 YYYY-MM-DD，如 2026-10-01）：' };

    case STEPS.DATE:
      if (!isDate(text)) return { error: '日期格式需為 YYYY-MM-DD，請重新輸入：' };
      data.departure_date = text;
      return { step: STEPS.ROUND, data: data, ask: '單程或來回？（輸入「單程」或「來回」）：' };

    case STEPS.ROUND:
      if (/^單程$/i.test(text) || /^one-way$/i.test(text)) {
        data.return_date = '';
        return { step: STEPS.TARGET, data: data, ask: '請輸入目標價（NT$，低於此價即通知）：' };
      }
      if (/^來回$/i.test(text) || /^round$/i.test(text)) {
        return { step: STEPS.RETURN, data: data, ask: '請輸入回程日期（格式 YYYY-MM-DD）：' };
      }
      return { error: '請輸入「單程」或「來回」：' };

    case STEPS.RETURN:
      if (!isDate(text)) return { error: '日期格式需為 YYYY-MM-DD，請重新輸入：' };
      data.return_date = text;
      return { step: STEPS.TARGET, data: data, ask: '請輸入目標價（NT$，低於此價即通知）：' };

    case STEPS.TARGET:
      var price = parsePrice(text);
      if (price === null) return { error: '目標價需為正整數（如 15000），請重新輸入：' };
      data.target_price = price;
      return {
        step: STEPS.CONFIRM,
        data: data,
        ask: '請確認以下設定，輸入「確認」即儲存：\n\n' + formatSettings({ search: buildSearch(data) }),
      };
  }
  return { error: '發生不明錯誤，請輸入 /cancel 重來。' };
}

function buildSearch(data) {
  return {
    origin: data.origin,
    destination: data.destination,
    departure_date: data.departure_date,
    return_date: data.return_date || '',
    target_price: data.target_price,
  };
}

function formatSettings(settings) {
  var s = settings.search;
  return (
    '起點：' + s.origin +
    '\n終點：' + s.destination +
    '\n出發：' + s.departure_date +
    '\n回程：' + (s.return_date || '（單程）') +
    '\n目標價：NT$ ' + s.target_price.toLocaleString()
  );
}

// ============================================================
// 顯示目前設定（讀 Gist）
// ============================================================
function showConfig(userId, replyToken) {
  try {
    var settings = fetchFromGist();
    reply(replyToken, '目前設定：\n\n' + formatSettings(settings));
  } catch (err) {
    reply(replyToken, '尚無設定（或讀取失敗）。請輸入 /set 開始設定。');
  }
}

// ============================================================
// GitHub Gist 存取
// ============================================================
function gistHeaders() {
  return {
    Authorization: 'token ' + GH_PAT,
    'User-Agent': 'line-flight-bot',
    Accept: 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
  };
}

function saveToGist(settings) {
  try {
    var url = 'https://api.github.com/gists/' + GIST_ID;
    var payload = {
      files: {},
    };
    payload.files[GIST_FILENAME] = { content: JSON.stringify(settings, null, 2) };
    var resp = UrlFetchApp.fetch(url, {
      method: 'patch',
      headers: gistHeaders(),
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    return resp.getResponseCode() === 200;
  } catch (err) {
    return false;
  }
}

function fetchFromGist() {
  var url = 'https://api.github.com/gists/' + GIST_ID;
  var resp = UrlFetchApp.fetch(url, {
    headers: gistHeaders(),
    muteHttpExceptions: true,
  });
  if (resp.getResponseCode() !== 200) throw new Error('gist fetch failed');
  var gist = JSON.parse(resp.getContentText());
  var content = gist.files[GIST_FILENAME].content;
  return JSON.parse(content);
}

// ============================================================
// LINE Reply API（不計入每月訊息額度）
// ============================================================
function reply(replyToken, text) {
  var payload = {
    replyToken: replyToken,
    messages: [{ type: 'text', text: text }],
  };
  var options = {
    method: 'post',
    headers: {
      Authorization: 'Bearer ' + CHANNEL_ACCESS_TOKEN,
      'Content-Type': 'application/json',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/reply', options);
}

// ============================================================
// 狀態管理（PropertiesService）
// ============================================================
function getState(userId) {
  var raw = PropertiesService.getScriptProperties().getProperty(STATE_PREFIX + userId);
  return raw ? JSON.parse(raw) : null;
}

function setState(userId, state) {
  PropertiesService.getScriptProperties().setProperty(STATE_PREFIX + userId, JSON.stringify(state));
}

function clearState(userId) {
  PropertiesService.getScriptProperties().deleteProperty(STATE_PREFIX + userId);
}

// ============================================================
// 驗證工具
// ============================================================
function isIata(text) {
  return /^[a-zA-Z]{3}$/.test(text);
}

function isDate(text) {
  return /^\d{4}-\d{2}-\d{2}$/.test(text);
}

function parsePrice(text) {
  var n = Number(String(text).replace(/[,\s]/g, ''));
  return isFinite(n) && n > 0 ? n : null;
}
