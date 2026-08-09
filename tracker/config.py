# ============================================================
# flight-price-tracker 設定載入
# 讀取 config.yaml 與 .env（Token 等機密不寫入 Git）
# ============================================================

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def load_config(config_path: str | Path = BASE_DIR / "config.yaml") -> dict:
    """讀取 config.yaml 並載入 .env 到環境變數。"""
    load_dotenv(BASE_DIR / ".env")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def get_env_var(name: str) -> str:
    """取得環境變數，若不存在則回傳空字串。"""
    return os.getenv(name, "").strip()


def resolve_secret(cfg: dict, key: str) -> str:
    """依設定中指定的環境變數名稱取出機密值。

    讀取 notification.<provider> 區塊，故 provider 換成 line/telegram 皆可。
    """
    provider = cfg["notification"].get("provider", "line")
    env_name = cfg["notification"].get(provider, {}).get(key)
    if not env_name:
        return ""
    return get_env_var(env_name)
