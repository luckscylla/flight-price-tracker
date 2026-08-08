# ============================================================
# 通知：Telegram Bot
# 當票價低於目標價時，透過 sendMessage API 推送訊息
# ============================================================

import logging

import requests

from .config import resolve_secret

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """發送 Telegram 訊息，成功回傳 True。"""
    if not bot_token or not chat_id:
        logger.warning("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，略過通知")
        return False
    try:
        resp = requests.post(
            TELEGRAM_API.format(token=bot_token),
            data={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        ok = resp.json().get("ok", False)
        if not ok:
            logger.warning("Telegram 回傳失敗：%s", resp.text)
        return ok
    except requests.RequestException as exc:
        logger.error("Telegram 通知失敗：%s", exc)
        return False


def build_message(cfg: dict, cheapest: dict, price: float) -> str:
    """組出通知訊息內容。"""
    s = cfg["search"]
    airlines = "/".join(cheapest.get("airlines") or ["未知"])
    return (
        "✈️ 機票降價通知！\n"
        f"航線：{s['origin']} → {s['destination']}\n"
        f"日期：{s['departure_date']}"
        + (f" 回程 {s['return_date']}" if s.get("return_date") else "（單程）")
        + f"\n航空公司：{airlines}"
        + f"\n轉機：{cheapest.get('stops', '?')} 次"
        + f"\n\n價格：{cheapest.get('price', price)}"
        + f"\n目標價：NT$ {s['target_price']:,}"
        + f"\n\n查看：{cheapest.get('url', '')}"
    )


def notify(cfg: dict, message: str) -> bool:
    """依設定發送通知，回傳是否成功。"""
    bot_token = resolve_secret(cfg, "bot_token_env")
    chat_id = resolve_secret(cfg, "chat_id_env")
    return send_telegram(bot_token, chat_id, message)
