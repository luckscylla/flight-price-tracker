# ============================================================
# 通知：LINE Messaging API
# 當票價低於目標價時，透過 Push API 推送訊息（計入每月免費額度）
# ============================================================

import logging

import requests

from .config import resolve_secret

logger = logging.getLogger(__name__)

LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"


def send_line(channel_access_token: str, user_id: str, text: str) -> bool:
    """發送 LINE Push 訊息，成功回傳 True。

    Push API 會計入每月訊息額度（免費方案 200 則/月）。
    """
    if not channel_access_token or not user_id:
        logger.warning("缺少 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，略過通知")
        return False
    try:
        resp = requests.post(
            LINE_PUSH_API,
            headers={
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json",
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": text}],
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("LINE 回傳失敗（%s）：%s", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as exc:
        logger.error("LINE 通知失敗：%s", exc)
        return False


def build_message(cfg: dict, cheapest: dict, price: float) -> str:
    """組出通知訊息內容（LINE 純文字格式）。"""
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
    channel_access_token = resolve_secret(cfg, "channel_access_token_env")
    user_id = resolve_secret(cfg, "user_id_env")
    return send_line(channel_access_token, user_id, message)
