# ============================================================
# flight-price-tracker
# 定時查詢機票價格，低於目標價時透過 LINE 通知
#
# 支援「日期彈性」：可指定只有去程或回程其中一個日期，
# 接受前後 N 天（date_window），逐一查詢後取全區間最低價。
# ============================================================

import logging
import sys

from tracker.config import BASE_DIR, load_config
from tracker.history import append_record
from tracker.notify import build_message, notify
from tracker.search import (
    SearchError,
    date_combos,
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


def _label(combo: dict) -> str:
    out = combo.get("departure_date") or "?"
    return out + (f" / {combo['return_date']}" if combo.get("return_date") else "（單程）")


def search_window(cfg: dict, combos: list[dict]) -> tuple[float, dict, dict] | None:
    """逐一查詢各日期組合，回傳全區間最低價 (price, 命中組合的設定, 結果)。

    全部查無結果時回傳 None。
    """
    s = cfg["search"]
    best: tuple[float, dict, dict] | None = None
    hit_count = 0

    for idx, combo in enumerate(combos, 1):
        combo_cfg = {**cfg, "search": {**s, **combo}}
        logger.info("[%d/%d] 查詢 %s", idx, len(combos), _label(combo))
        try:
            results = search_flights(combo_cfg)
        except SearchError as exc:
            logger.error("[%d/%d] 查詢失敗：%s", idx, len(combos), exc)
            continue
        except Exception as exc:  # 爬蟲套件可能拋出各種例外
            logger.error("[%d/%d] 查詢發生例外：%s", idx, len(combos), exc)
            continue

        if not results:
            logger.info("[%d/%d] 查無結果", idx, len(combos))
            continue

        cheapest = find_cheapest(combo_cfg, results)
        if cheapest is None:
            logger.info("[%d/%d] 所有結果皆無價格資訊", idx, len(combos))
            continue

        price = parse_price(cheapest.get("price", ""))
        if price is None:
            continue
        hit_count += 1
        logger.info("[%d/%d] 最低 %s", idx, len(combos), cheapest.get("price"))
        if best is None or price < best[0]:
            best = (price, combo_cfg, cheapest)

    if hit_count == 0:
        logger.warning(
            "所有 %d 組日期都查無結果，請確認日期是否在可訂範圍內", len(combos)
        )
    return best


def run() -> int:
    cfg = apply_settings_file(load_config())
    s = cfg["search"]
    target = s.get("target_price", 0)
    logger.info(
        "查詢 %s → %s，目標價 NT$ %s（指定日期 %s）",
        s["origin"], s["destination"], target, s.get("departure_date"),
    )

    try:
        combos = date_combos(cfg)
    except SearchError as exc:
        logger.error("%s", exc)
        return 1

    if not combos:
        logger.error(
            "日期 %s 前後 %s 天內已無未來日期，請用 LINE 的 /set 或 config.yaml 更新",
            s.get("departure_date"), s.get("date_window") or 0,
        )
        return 1

    best = search_window(cfg, combos)
    if best is None:
        return 1

    price, best_cfg, cheapest = best
    cheapest["url"] = google_flights_url(best_cfg)
    logger.info(
        "區間最低價：%s（%s）",
        cheapest.get("price"),
        _label({k: best_cfg["search"][k] for k in ("departure_date", "return_date")}),
    )

    notified = False
    if price <= target:
        notified = notify(best_cfg, build_message(best_cfg, cheapest, price, len(combos)))
        if notified:
            logger.info("已送出降價通知")
    else:
        logger.info("目前價格高於目標價，未發通知")

    append_record(best_cfg, cheapest, price, notified)
    return 0


if __name__ == "__main__":
    sys.exit(run())
