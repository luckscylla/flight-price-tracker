# ============================================================
# 查詢歷史：每次執行寫入 CSV，方便追蹤價格趨勢
# ============================================================

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FIELDS = [
    "checked_at", "origin", "destination", "departure_date", "return_date",
    "currency", "cheapest_price", "airlines", "stops", "target_price", "notified",
]


def append_record(cfg: dict, cheapest: dict, price: float, notified: bool) -> None:
    """把一次查詢結果寫入歷史 CSV。"""
    history_file = Path(cfg["logging"].get("history_file", "data/history.csv"))
    history_file.parent.mkdir(parents=True, exist_ok=True)
    s = cfg["search"]
    airlines = "/".join(cheapest.get("airlines") or []) if cheapest else ""
    row = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "origin": s["origin"],
        "destination": s["destination"],
        "departure_date": s["departure_date"],
        "return_date": s.get("return_date") or "",
        "currency": s.get("currency", "TWD"),
        "cheapest_price": price,
        "airlines": airlines,
        "stops": cheapest.get("stops", "") if cheapest else "",
        "target_price": s.get("target_price", ""),
        "notified": notified,
    }
    new_file = not history_file.exists()
    with open(history_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    logger.info("已記錄查詢結果至 %s", history_file)
