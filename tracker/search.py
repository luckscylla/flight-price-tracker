# ============================================================
# 票價查詢：透過 google-flights-search 查 Google Flights
# 回傳 gf_search.search() 的結果，並提供價格解析與最低價挑選
# ============================================================

import re

from .config import BASE_DIR

try:
    from gf_search import search as _gf_search
    from gf_search import build_tfs as _build_tfs
except ImportError:  # pragma: no cover
    _gf_search = None
    _build_tfs = None


class SearchError(RuntimeError):
    """查詢失敗時拋出。"""


def search_flights(cfg: dict) -> list[dict]:
    """依設定查詢 Google Flights，回傳航班結果清單。

    註：PyPI 版 google-flights-search 固定以 TWD 計價（hl=zh-TW），
    故 currency 參數僅作為顯示用途。
    """
    if _gf_search is None:
        raise SearchError(
            "未安裝 google-flights-search，請先執行：pip install -r requirements.txt"
        )

    s = cfg["search"]
    results = _gf_search(
        origin=s["origin"],
        destination=s["destination"],
        departure_date=s["departure_date"],
        return_date=s.get("return_date") or None,
        adults=s.get("adults", 1),
        travel_class="economy",
        max_results=s.get("max_results", 5),
    )
    return results or []


_PRICE_RE = re.compile(r"([\d,]+)")


def parse_price(price_str: str) -> float | None:
    """把價格字串（如 "TWD 8,900"）解析成數字，失敗回傳 None。"""
    if not price_str:
        return None
    match = _PRICE_RE.search(str(price_str))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def find_cheapest(cfg: dict, results: list[dict]) -> dict | None:
    """從結果中挑出最低價的航班。"""
    priced = [r for r in results if parse_price(r.get("price", "")) is not None]
    if not priced:
        return None
    return min(priced, key=lambda r: parse_price(r["price"]))


def google_flights_url(cfg: dict) -> str:
    """產生對應的 Google Flights 查詢網址（方便點開確認）。"""
    s = cfg["search"]
    if _build_tfs is not None:
        tfs = _build_tfs(
            origin=s["origin"],
            destination=s["destination"],
            departure_date=s["departure_date"],
            return_date=s.get("return_date") or None,
            adults=s.get("adults", 1),
        )
        return f"https://www.google.com/travel/flights/search?tfs={tfs}&hl=zh-TW"
    date = s["departure_date"].replace("-", "")
    return (
        f"https://www.google.com/travel/flights?curr={s.get('currency', 'TWD')}"
        f"&hl=zh-TW#flt={s['origin']}.{s['destination']}.{date}"
    )
