# ============================================================
# 票價查詢：透過 google-flights-search 查 Google Flights
# 回傳 gf_search.search() 的結果，並提供價格解析與最低價挑選
# ============================================================

import datetime
import logging
import re

from .config import BASE_DIR

logger = logging.getLogger(__name__)

try:
    from gf_search import search as _gf_search
    from gf_search import build_tfs as _build_tfs
    from gf_search import fetcher as _gf_fetcher
except ImportError:  # pragma: no cover
    _gf_search = None
    _build_tfs = None
    _gf_fetcher = None


class SearchError(RuntimeError):
    """查詢失敗時拋出。"""


def _force_currency(currency: str) -> None:
    """強制套件的請求網址帶上 curr 參數。

    google-flights-search 只送 hl=zh-TW、不送 curr，Google 會依伺服器 IP
    地區決定幣別（GitHub Actions 在美國 → 美金）。注入 curr 可固定幣別。
    """
    if _gf_fetcher is None:
        return
    try:
        base = _gf_fetcher._GF_SEARCH_URL
        if "curr=" not in base:
            sep = "&" if "?" in base else "?"
            _gf_fetcher._GF_SEARCH_URL = f"{base}{sep}curr={currency}"
    except Exception:  # pragma: no cover
        pass


def search_flights(cfg: dict) -> list[dict]:
    """依設定查詢 Google Flights，回傳航班結果清單。

    註：google-flights-search 的幣別原本依伺服器 IP 而定（美國 IP 會回
    美金），這裡強制帶 curr 參數以固定為設定幣別（預設 TWD）。
    """
    if _gf_search is None:
        raise SearchError(
            "未安裝 google-flights-search，請先執行：pip install -r requirements.txt"
        )

    s = cfg["search"]
    _force_currency(s.get("currency", "TWD"))
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

WINDOW_TARGETS = ("departure", "return")


def _parse_date(value) -> datetime.date | None:
    """把字串轉成 date，格式不對回傳 None。"""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def _shift(day: datetime.date, offset: int) -> str:
    return (day + datetime.timedelta(days=offset)).isoformat()


def date_combos(cfg: dict) -> list[dict[str, str | None]]:
    """產生本次要查詢的日期組合。

    規格：去程與回程之中**只有一個**可設前後範圍（date_window_target），
    另一個固定，因此組合數 = 2 * date_window + 1；date_window = 0 時
    等同原本的單一組合，行為完全不變。

    會自動略過：回程早於出發、以及已經是過去日期的組合。
    """
    s = cfg["search"]
    window = max(0, int(s.get("date_window") or 0))
    target = (s.get("date_window_target") or "departure").strip().lower()
    if target not in WINDOW_TARGETS:
        logger.warning(
            "date_window_target=%s 不合法（應為 departure 或 return），改用 departure", target
        )
        target = "departure"

    dep_center = _parse_date(s.get("departure_date"))
    if dep_center is None:
        raise SearchError(
            f"出發日期格式不正確：{s.get('departure_date')!r}（需 YYYY-MM-DD）"
        )
    ret_center = _parse_date(s.get("return_date"))

    if window == 0:
        combos = [{"departure_date": dep_center.isoformat(),
                   "return_date": ret_center.isoformat() if ret_center else None}]
    elif target == "return" and ret_center is not None:
        combos = [
            {"departure_date": dep_center.isoformat(), "return_date": _shift(ret_center, off)}
            for off in range(-window, window + 1)
        ]
    else:
        if target == "return":
            logger.warning("date_window_target=return 但未設定回程日期，改以去程套用範圍")
        combos = [
            {"departure_date": _shift(dep_center, off),
             "return_date": ret_center.isoformat() if ret_center else None}
            for off in range(-window, window + 1)
        ]

    today = datetime.date.today()
    usable = []
    for c in combos:
        dep = _parse_date(c["departure_date"])
        ret = _parse_date(c["return_date"]) if c["return_date"] else None
        if dep < today or (ret is not None and ret < today):
            logger.info("略過已過期的組合：%s → %s", c["departure_date"], c["return_date"] or "—")
            continue
        if ret is not None and ret < dep:
            logger.info(
                "略過回程早於出發的組合：%s → %s", c["departure_date"], c["return_date"]
            )
            continue
        usable.append(c)

    cap = int(s.get("max_date_combos") or 15)
    if len(usable) > cap:
        step = len(usable) / cap
        sampled = [usable[int(i * step)] for i in range(cap)]
        logger.warning(
            "可查日期組合 %d 組，超過上限 %d 組， evenly 取樣 %d 組",
            len(usable), cap, len(sampled),
        )
        usable = sampled

    logger.info(
        "日期組合：%s %s ±%d 天，共 %d 組",
        s.get("departure_date"),
        "回程" if (target == "return" and ret_center) else "出發",
        window, len(usable),
    )
    return usable


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
    curr = s.get("currency", "TWD")
    if _build_tfs is not None:
        tfs = _build_tfs(
            origin=s["origin"],
            destination=s["destination"],
            departure_date=s["departure_date"],
            return_date=s.get("return_date") or None,
            adults=s.get("adults", 1),
        )
        return (
            f"https://www.google.com/travel/flights/search?tfs={tfs}"
            f"&hl=zh-TW&curr={curr}"
        )
    date = s["departure_date"].replace("-", "")
    return (
        f"https://www.google.com/travel/flights?curr={curr}"
        f"&hl=zh-TW#flt={s['origin']}.{s['destination']}.{date}"
    )
