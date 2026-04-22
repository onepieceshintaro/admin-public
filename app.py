"""管理者ダッシュボード（MVP）。

- パスワード認証（Streamlit Secrets の ADMIN_PASSWORD）
- ユーザーの**原文**（CBT思考・メモ・アサーションの場面など）は表示しない
- 表示するのは、ID単位の件数・日付・リスク判定などの**集計値のみ**
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from db import get_engine

st.set_page_config(
    page_title="Admin Dashboard",
    page_icon="🛠",
    layout="wide",
)


# ---------------- 認証 ----------------
def _require_password() -> None:
    if st.session_state.get("admin_authed"):
        return
    expected = None
    try:
        expected = st.secrets.get("ADMIN_PASSWORD")
    except Exception:
        expected = None

    st.markdown("## 🛠 Admin Dashboard")
    st.caption("管理者パスワードを入力してください。")

    with st.form("admin_login"):
        pw = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")

    if submitted:
        if not expected:
            st.error("ADMIN_PASSWORD が設定されていません（Secrets を確認）。")
            st.stop()
        if pw == expected:
            st.session_state.admin_authed = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()


_require_password()


# ---------------- データ取得 ----------------
@st.cache_data(ttl=300, show_spinner=False)
def load_mood() -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT user_id, log_date,
               CASE WHEN recovery IS NOT NULL AND length(trim(recovery)) > 0
                    THEN 1 ELSE 0 END AS has_recovery
        FROM mood_logs
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if not df.empty:
        df["log_date"] = pd.to_datetime(df["log_date"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_cbt() -> pd.DataFrame:
    eng = get_engine()
    q = text("SELECT user_id, created_at FROM cbt_thought_records")
    with eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_assertion() -> pd.DataFrame:
    eng = get_engine()
    q = text("SELECT user_id, created_at FROM assertion_records")
    with eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_nicknames() -> pd.DataFrame:
    eng = get_engine()
    q = text("SELECT user_id FROM user_nicknames WHERE nickname IS NOT NULL AND length(trim(nickname)) > 0")
    with eng.connect() as conn:
        return pd.read_sql(q, conn)


@st.cache_data(ttl=300, show_spinner=False)
def load_cbt_risk() -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT user_id, created_at, triggered
        FROM cbt_risk_scores
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_assertion_risk() -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT user_id, created_at, triggered, level
        FROM assertion_risk_scores
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


# ---------------- ヘッダー ----------------
st.markdown("## 🛠 Admin Dashboard")
st.caption(
    f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}　"
    "表示内容はすべて集計値で、ユーザーの原文（思考・メモなど）は含みません。"
)
col_reload, _ = st.columns([1, 6])
with col_reload:
    if st.button("🔄 キャッシュ更新"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

try:
    mood = load_mood()
    cbt = load_cbt()
    asr = load_assertion()
    nicks = load_nicknames()
    cbt_risk = load_cbt_risk()
    asr_risk = load_assertion_risk()
except Exception as e:
    st.error(f"DB 読み込み失敗: {e}")
    st.stop()


# ---------------- サマリーカード ----------------
mood_users = set(mood["user_id"]) if not mood.empty else set()
cbt_users = set(cbt["user_id"]) if not cbt.empty else set()
asr_users = set(asr["user_id"]) if not asr.empty else set()
all_users = mood_users | cbt_users | asr_users

cutoff_7 = pd.Timestamp.now().normalize() - pd.Timedelta(days=7)

active_users: set[str] = set()
if not mood.empty:
    active_users |= set(mood[mood["log_date"] >= cutoff_7]["user_id"])
if not cbt.empty:
    active_users |= set(cbt[cbt["created_at"] >= cutoff_7]["user_id"])
if not asr.empty:
    active_users |= set(asr[asr["created_at"] >= cutoff_7]["user_id"])

nick_users = set(nicks["user_id"]) if not nicks.empty else set()
nick_rate = (len(nick_users & all_users) / len(all_users) * 100) if all_users else 0.0

total_records = len(mood) + len(cbt) + len(asr)

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 総ユーザー数", len(all_users))
c2.metric("🟢 直近7日アクティブ", len(active_users))
c3.metric("🏷 ニックネーム設定率", f"{nick_rate:.0f}%")
c4.metric("📝 総記録数", total_records)

st.markdown("---")


# ---------------- 日次アクティビティ ----------------
st.subheader("📈 日次記録数（直近30日）")

cutoff_30 = pd.Timestamp.now().normalize() - pd.Timedelta(days=30)
frames = []
if not mood.empty:
    m = mood[mood["log_date"] >= cutoff_30].copy()
    m["date"] = m["log_date"].dt.normalize()
    m["app"] = "気分の記録"
    frames.append(m[["date", "app"]])
if not cbt.empty:
    c = cbt[cbt["created_at"] >= cutoff_30].copy()
    c["date"] = c["created_at"].dt.normalize()
    c["app"] = "思考の整理"
    frames.append(c[["date", "app"]])
if not asr.empty:
    a = asr[asr["created_at"] >= cutoff_30].copy()
    a["date"] = a["created_at"].dt.normalize()
    a["app"] = "伝え方"
    frames.append(a[["date", "app"]])

if frames:
    all_df = pd.concat(frames, ignore_index=True)
    agg = all_df.groupby(["date", "app"]).size().reset_index(name="count")
    fig = px.line(agg, x="date", y="count", color="app", markers=True)
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title=None, yaxis_title="件数")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("まだデータがありません。")

st.markdown("---")


# ---------------- ユーザーあたりの活動日数 ----------------
st.subheader("📊 ユーザーあたりの活動日数")
st.caption("ユーザーごとの「記録があった日数」の分布（全期間・3アプリ合計）")

user_days: dict[str, set] = {}
for df, col in [(mood, "log_date"), (cbt, "created_at"), (asr, "created_at")]:
    if df.empty:
        continue
    for uid, d in zip(df["user_id"], df[col].dt.normalize()):
        user_days.setdefault(uid, set()).add(d)

if user_days:
    days_per_user = pd.Series([len(v) for v in user_days.values()], name="days")
    bins = [0, 1, 3, 7, 14, 30, 10_000]
    labels = ["1日", "2〜3日", "4〜7日", "8〜14日", "15〜30日", "31日以上"]
    binned = pd.cut(days_per_user, bins=bins, labels=labels, right=True)
    counts = binned.value_counts().reindex(labels).fillna(0).astype(int).reset_index()
    counts.columns = ["活動日数", "ユーザー数"]
    fig = px.bar(counts, x="活動日数", y="ユーザー数")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("まだデータがありません。")

st.markdown("---")


# ---------------- 気分トラッカー: 良かったこと記入率 ----------------
st.subheader("✨ 気分の記録: 「良かったこと」記入率")
if not mood.empty:
    total = len(mood)
    with_rec = int(mood["has_recovery"].sum())
    rate = (with_rec / total * 100) if total else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("記入あり", with_rec)
    c2.metric("総記録数", total)
    c3.metric("記入率", f"{rate:.0f}%")
else:
    st.caption("まだデータがありません。")

st.markdown("---")


# ---------------- リスク検知 ----------------
st.subheader("🚨 リスク検知（triggered の件数）")
st.caption("セーフティスコアで triggered=true になった件数の集計。会話内容は表示しません。")

rc1, rc2 = st.columns(2)

with rc1:
    st.markdown("**CBT（思考の整理）**")
    if cbt_risk.empty:
        st.caption("データなし")
    else:
        total = len(cbt_risk)
        trig = int((cbt_risk["triggered"] == 1).sum() + (cbt_risk["triggered"] == True).sum())
        # triggered は bool/int いずれの可能性
        try:
            trig = int(cbt_risk["triggered"].astype(bool).sum())
        except Exception:
            pass
        users_trig = cbt_risk[cbt_risk["triggered"].astype(bool)]["user_id"].nunique()
        m1, m2, m3 = st.columns(3)
        m1.metric("評価総数", total)
        m2.metric("triggered", trig)
        m3.metric("対象ユーザー数", users_trig)

with rc2:
    st.markdown("**アサーション（伝え方）**")
    if asr_risk.empty:
        st.caption("データなし")
    else:
        total = len(asr_risk)
        try:
            trig = int(asr_risk["triggered"].astype(bool).sum())
        except Exception:
            trig = 0
        users_trig = asr_risk[asr_risk["triggered"].astype(bool)]["user_id"].nunique()
        m1, m2, m3 = st.columns(3)
        m1.metric("評価総数", total)
        m2.metric("triggered", trig)
        m3.metric("対象ユーザー数", users_trig)

        if "level" in asr_risk.columns:
            st.caption("level 内訳")
            lv = (
                asr_risk["level"].fillna("(null)").astype(str)
                .value_counts().reset_index()
            )
            lv.columns = ["level", "件数"]
            st.dataframe(lv, hide_index=True, use_container_width=True)

st.markdown("---")
st.caption(
    "※ プライバシー方針: ユーザーの入力原文（思考、メモ、会話、場面描写など）は"
    "この画面には一切表示しません。集計値のみを扱います。"
)
