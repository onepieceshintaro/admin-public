"""DB接続（読み取り専用の想定）。共有 Supabase に接続する。"""
import os
from functools import lru_cache

import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _get_database_url() -> str:
    try:
        url = st.secrets.get("DATABASE_URL")
        if url:
            return url
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    raise RuntimeError(
        "DATABASE_URL が見つかりません。"
        "Streamlit Secrets または環境変数を設定してください。"
    )


def _normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        _normalize_url(_get_database_url()),
        pool_pre_ping=True, future=True,
    )
