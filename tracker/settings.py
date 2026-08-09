# ============================================================
# 設定合併
# LINE 對話設定會寫入 GitHub Gist，GitHub Actions 下載後存成
# settings.json；此模組負責載入並覆蓋 config.yaml 的 search 區塊。
# ============================================================

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SEARCH_FIELDS = [
    "origin",
    "destination",
    "departure_date",
    "return_date",
    "adults",
    "currency",
    "max_results",
    "target_price",
]


def load_settings(path: str | Path) -> dict:
    """讀取 settings.json，不存在或格式錯誤時回傳空 dict。"""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("settings.json 格式錯誤：不是 JSON 物件")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("讀取 settings.json 失敗：%s", exc)
        return {}


def merge_settings(cfg: dict, settings: dict) -> dict:
    """把 settings 中的 search 欄位覆蓋到 cfg（優先於 config.yaml）。

    回傳新的設定 dict；settings 缺少的欄位保留原值。
    """
    merged = {k: v for k, v in cfg.items()}
    search = settings.get("search") or {}
    if isinstance(search, dict):
        new_search = {k: v for k, v in cfg["search"].items()}
        for field in SEARCH_FIELDS:
            if field in search and search[field] is not None:
                new_search[field] = search[field]
        merged["search"] = new_search
    return merged


def apply_settings_file(cfg: dict, path: str | Path = "settings.json") -> dict:
    """從檔案載入設定並合併，回傳最終設定。"""
    settings = load_settings(path)
    if settings:
        logger.info("套用 LINE 設定覆蓋：%s", path)
        return merge_settings(cfg, settings)
    return cfg
