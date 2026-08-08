# ============================================================
# flight-price-tracker
# 定時查詢機票價格，低於目標價時透過 Telegram 通知
# ============================================================

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flight-price-tracker")


def run() -> int:
    cfg = load_config()
    s = cfg["search"]
    target = s.get("target_price", 0)
    logger.info(
        "開始查詢 %s → %s，日期 %s，目標價 NT$ %s",
        s["origin"], s["destination"], s["departure_date"], target,
    )

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
