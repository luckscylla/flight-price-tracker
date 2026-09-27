# ============================================================
# flight-price-tracker
# 定時查詢機票價格，低於目標價時透過 LINE 通知
# ============================================================

import datetime
import logging
import sys

from tracker.config import BASE_DIR, load_config
from tracker.history import append_record
from tracker.notify import build_message, notify
from tracker.search import (
    SearchError,
    find_cheapest,
    google_flights_url,
    parse_price,
    search_flights,
)
from tracker.settings import apply_settings_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flight-price-tracker")


def check_dates(cfg: dict) -> int | None:
    """檢查出發／回程日期是否已過期，回傳錯誤訊息或 None。"""
    s = cfg["search"]
    today = datetime.date.today()
    problems = []
    for label, key in (("出發", "departure_date"), ("回程", "return_date")):
        raw = s.get(key)
        if not raw:
            continue
        try:
            day = datetime.date.fromisoformat(str(raw))
        except ValueError:
            logger.warning("%s日期格式非 YYYY-MM-DD：%s", label, raw)
            continue
        if day < today:
            problems.append(f"{label}日期 {raw} 已過期（今天 {today}）")
    if not problems:
        return None
    for p in problems:
        logger.error("%s", p)
    logger.error("請用 LINE 的 /set 更新日期，或修改 config.yaml 後重新執行")
    return 1


def run() -> int:
    cfg = apply_settings_file(load_config())
    s = cfg["search"]
    target = s.get("target_price", 0)
    logger.info(
        "開始查詢 %s → %s，日期 %s，目標價 NT$ %s",
        s["origin"], s["destination"], s["departure_date"], target,
    )

    if (expired := check_dates(cfg)) is not None:
        return expired

    try:
        results = search_flights(cfg)
    except SearchError as exc:
        logger.error("查詢失敗：%s", exc)
        return 1
    except Exception as exc:  # 爬蟲套件可能拋出各種例外
        logger.error("查詢發生例外：%s", exc)
        return 1

    if not results:
        logger.warning("查無結果，請確認日期是否超過可訂範圍")
        return 1

    cheapest = find_cheapest(cfg, results)
    if cheapest is None:
        logger.warning("所有結果皆無價格資訊")
        return 1

    price = parse_price(cheapest.get("price", ""))
    cheapest["url"] = google_flights_url(cfg)
    logger.info("最低價：%s（NT$ %s）", cheapest.get("price"), price)

    notified = False
    if price is not None and price <= target:
        message = build_message(cfg, cheapest, price)
        notified = notify(cfg, message)
        if notified:
            logger.info("已送出降價通知")
    else:
        logger.info("目前價格高於目標價，未發通知")

    append_record(cfg, cheapest, price, notified)
    return 0


if __name__ == "__main__":
    sys.exit(run())
