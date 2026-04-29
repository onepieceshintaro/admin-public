"""管理者ダッシュボード（MVP）。

- パスワード認証（Streamlit Secrets の ADMIN_PASSWORD）
- 「📊 サービス全体」タブ：ユーザーの**原文**は表示せず集計値のみ
- 「🪞 マイレポート」タブ：自分のuser_idを入力して、自分のデータを月次で振り返る
"""
from __future__ import annotations

import json
import os
from collections import Counter
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


# --- マイレポート用：本人IDだけのデータを取る（content付き） ---
@st.cache_data(ttl=300, show_spinner=False)
def load_my_mood(user_id: str) -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT log_date, mood, sleep_hours, energy, note, tags, recovery
        FROM mood_logs WHERE user_id = :uid
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn, params={"uid": user_id})
    if not df.empty:
        df["log_date"] = pd.to_datetime(df["log_date"])
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_my_cbt(user_id: str) -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT id, created_at, event_datetime, situation, emotion_name,
               intensity_before, intensity_after, automatic_thought,
               distortions, balanced_thought
        FROM cbt_thought_records WHERE user_id = :uid
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn, params={"uid": user_id})
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_my_assertion(user_id: str) -> pd.DataFrame:
    eng = get_engine()
    q = text("""
        SELECT id, created_at, event_datetime, mode, situation,
               chosen_script, todo, insight
        FROM assertion_records WHERE user_id = :uid
    """)
    with eng.connect() as conn:
        df = pd.read_sql(q, conn, params={"uid": user_id})
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
    return df


# ---------------- ヘッダー ----------------
st.markdown("## 🛠 Admin Dashboard")
st.caption(
    f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}　"
    "「サービス全体」タブは集計値のみ。「マイレポート」タブは入力した user_id 本人のデータのみ表示。"
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


tab_overview, tab_myreport = st.tabs(["📊 サービス全体", "🪞 マイレポート"])


# =================================================================
# タブ1: サービス全体（既存の集計ダッシュボード）
# =================================================================
with tab_overview:
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
            try:
                trig = int(cbt_risk["triggered"].astype(bool).sum())
            except Exception:
                trig = 0
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


# =================================================================
# タブ2: マイレポート（自分のuser_idで横断振り返り + 歪み深堀り）
# =================================================================
def _normalize_distortions(raw) -> list[dict]:
    """旧（list[str]）/新（list[dict{name, evidence}]）両対応。"""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if not isinstance(raw, list):
        return []
    out = []
    for it in raw:
        if isinstance(it, dict) and it.get("name"):
            out.append({"name": it["name"], "evidence": it.get("evidence", "")})
        elif isinstance(it, str):
            out.append({"name": it, "evidence": ""})
    return out


def _get_anthropic_key() -> str | None:
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY")
        if k:
            return k
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


def _summarize_distortion_with_haiku(distortion_name: str, thoughts: list[str]) -> str:
    """選択された歪みについて、自動思考のリストをHaikuで要約。失敗時は空文字。"""
    key = _get_anthropic_key()
    if not key or not thoughts:
        return ""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=key)
        sample = "\n".join(f"- {t}" for t in thoughts[:20])
        prompt = f"""以下は、ある人が認知行動療法の記録で「{distortion_name}」と判定された自動思考のリストです。
これらに共通して見えるパターン（どんな状況で・どんな相手に対して・どう感じやすいか）を、
本人の振り返り用に**3〜5行のmarkdown箇条書き**で要約してください。
本人の言葉を尊重し、断定せず、「〜の傾向が見えそう」と控えめに書いてください。

# 自動思考のリスト
{sample}

# 出力
- 共通点や傾向（最大5項目）
- 本人が読んで「ハッとできる」表現を心がける
- 説明文や前置きは不要、箇条書きのみ
"""
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip() if resp.content else ""
    except Exception as e:
        return f"（要約失敗: {e}）"


with tab_myreport:
    st.markdown("### 🪞 マイレポート")
    st.caption(
        "自分の user_id を入れると、その user_id 本人の気分・思考の整理・伝え方の記録を月次で横断的に見られます。"
        "他人の user_id を入れても全く同じように出るので、運用上は自分用にしか使わない前提のタブです。"
    )

    # クエリパラメータ ?u=... を初期値に
    q_uid = st.query_params.get("u", "")
    uid_raw = st.text_input(
        "user_id",
        value=q_uid,
        placeholder="例: ab12cd34ef56...",
        help="気分トラッカー等のサイドバーに表示されているID",
    )
    # コピペ時の空白・改行混入をはじく
    uid_input = (uid_raw or "").strip()

    # 月選択
    today = pd.Timestamp.now().normalize()
    default_month = today.strftime("%Y-%m")
    month_str = st.text_input(
        "対象月（YYYY-MM）", value=default_month,
        help="その月（1日〜末日）の記録を集計します",
    ).strip()

    if not uid_input or not month_str:
        st.info("user_id と対象月を入力するとレポートが表示されます。")
        st.stop()

    try:
        month_start = pd.Timestamp(month_str + "-01")
        month_end = (month_start + pd.offsets.MonthEnd(0)).normalize()
    except Exception:
        st.error("対象月は YYYY-MM の形式で入力してください（例: 2026-04）")
        st.stop()

    # 本人データを取得
    try:
        my_mood = load_my_mood(uid_input)
        my_cbt = load_my_cbt(uid_input)
        my_asr = load_my_assertion(uid_input)
    except Exception as e:
        st.error(f"データ取得失敗: {e}")
        st.stop()

    # ID検証用：このIDに紐づく全期間の記録数を表示（月フィルタ前）
    total_mood = len(my_mood)
    total_cbt = len(my_cbt)
    total_asr = len(my_asr)
    if total_mood == 0 and total_cbt == 0 and total_asr == 0:
        st.warning(
            f"このuser_id（先頭8文字: `{uid_input[:8]}`）に紐づく記録が"
            "**1件も見つかりませんでした**。IDの貼り間違いや、"
            "気分トラッカー等で別のIDで記録している可能性があります。"
        )
        st.caption(f"入力された全長: {len(uid_input)} 文字（通常32文字）")
        st.stop()
    else:
        st.caption(
            f"📦 このIDの全期間記録：気分 {total_mood}日 / "
            f"思考の整理 {total_cbt}件 / 伝え方 {total_asr}件"
        )

    # 月で絞り込み
    def _slice_month(df: pd.DataFrame, col: str) -> pd.DataFrame:
        if df.empty:
            return df
        d = df.copy()
        return d[(d[col] >= month_start) & (d[col] <= month_end + pd.Timedelta(days=1))]

    mood_m = _slice_month(my_mood, "log_date")
    # CBT/アサーションは event_datetime 優先（NULL の行は created_at で拾う）
    if not my_cbt.empty:
        ev_in = my_cbt["event_datetime"].between(month_start, month_end + pd.Timedelta(days=1))
        cr_in = my_cbt["created_at"].between(month_start, month_end + pd.Timedelta(days=1))
        cbt_m = my_cbt[ev_in.fillna(False) | cr_in]
    else:
        cbt_m = my_cbt
    if not my_asr.empty:
        ev_in_a = my_asr["event_datetime"].between(month_start, month_end + pd.Timedelta(days=1))
        cr_in_a = my_asr["created_at"].between(month_start, month_end + pd.Timedelta(days=1))
        asr_m = my_asr[ev_in_a.fillna(False) | cr_in_a]
    else:
        asr_m = my_asr

    # 月内のデータが全くない場合は別メッセージで案内
    if mood_m.empty and cbt_m.empty and asr_m.empty:
        st.info(
            f"{month_str} の記録は0件でした。"
            "全期間にはデータがあるので、別の月（YYYY-MM）を入れてみてください。"
        )
        st.stop()

    # ---------------- 月次サマリー（横断） ----------------
    st.markdown(f"#### 📅 {month_str} のサマリー")
    s1, s2, s3, s4 = st.columns(4)

    if not mood_m.empty:
        avg_mood = float(pd.to_numeric(mood_m["mood"], errors="coerce").dropna().mean())
        s1.metric("気分 平均", f"{avg_mood:.1f}", help=f"記録 {len(mood_m)}日")
    else:
        s1.metric("気分 平均", "—", help="記録なし")

    s2.metric("気分 記録日数", len(mood_m))
    s3.metric("思考の整理 件数", len(cbt_m) if not cbt_m.empty else 0)
    s4.metric("伝え方 件数", len(asr_m) if not asr_m.empty else 0)

    # ---------------- 気分の月次推移 ----------------
    if not mood_m.empty:
        st.markdown("##### 📈 気分の推移")
        m_plot = mood_m[["log_date", "mood"]].dropna().sort_values("log_date")
        if not m_plot.empty:
            fig_m = px.line(m_plot, x="log_date", y="mood", markers=True)
            fig_m.update_yaxes(range=[0, 10])
            fig_m.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                                xaxis_title=None, yaxis_title="気分")
            st.plotly_chart(fig_m, use_container_width=True)

    # ---------------- CBT 歪み Top と深掘り ----------------
    if not cbt_m.empty:
        st.markdown("##### 🧠 認知の歪み（今月）")
        # 集計
        counter: Counter = Counter()
        records_with: list[tuple[str, str]] = []  # (歪み名, 自動思考)
        for _, row in cbt_m.iterrows():
            ds = _normalize_distortions(row["distortions"])
            at = (row.get("automatic_thought") or "").strip()
            for d in ds:
                counter[d["name"]] += 1
                if at:
                    records_with.append((d["name"], at))

        if not counter:
            st.caption("今月、判定された歪みはありません。")
        else:
            top = counter.most_common(10)
            top_df = pd.DataFrame(top, columns=["歪み", "件数"])
            total = sum(counter.values())
            top_df["割合"] = (top_df["件数"] / total * 100).round(1).astype(str) + "%"
            fig_d = px.bar(top_df, x="件数", y="歪み", orientation="h", text="割合")
            fig_d.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                                yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_d, use_container_width=True)

            # ---- 深掘り（5E） ----
            st.markdown("##### 🔍 歪みの深掘り（記事化用ドラフト）")
            chosen = st.selectbox(
                "深掘りしたい歪みを選択",
                [name for name, _ in top],
                key="myreport_distortion_pick",
            )
            related_thoughts = [t for d, t in records_with if d == chosen]
            st.caption(f"「{chosen}」に該当した自動思考: {len(related_thoughts)}件")

            with st.expander("自動思考の一覧（本人のみ閲覧）"):
                for i, t in enumerate(related_thoughts, 1):
                    st.markdown(f"{i}. {t}")

            if st.button(f"🤖 「{chosen}」の傾向をHaikuで要約", key="myreport_summarize"):
                with st.spinner("要約中..."):
                    summary = _summarize_distortion_with_haiku(chosen, related_thoughts)
                if summary:
                    st.session_state["myreport_summary"] = summary
                    st.session_state["myreport_summary_target"] = chosen

            if st.session_state.get("myreport_summary_target") == chosen:
                summary_text = st.session_state.get("myreport_summary", "")
                if summary_text:
                    st.markdown("**要約**")
                    st.markdown(summary_text)

                    # markdownエクスポート
                    md = (
                        f"# {month_str} マイレポート — 「{chosen}」深掘り\n\n"
                        f"- 該当件数: {len(related_thoughts)}件\n"
                        f"- 全歪み中の割合: "
                        f"{counter[chosen] / total * 100:.1f}%\n\n"
                        f"## 傾向の要約\n{summary_text}\n\n"
                        f"## 自動思考のサンプル（最大10件）\n"
                        + "\n".join(f"- {t}" for t in related_thoughts[:10])
                    )
                    st.download_button(
                        "📥 Markdownでダウンロード",
                        data=md.encode("utf-8"),
                        file_name=f"myreport_{month_str}_{chosen}.md",
                        mime="text/markdown",
                    )

    st.markdown("---")
    st.caption(
        "🔒 このタブは入力された user_id 本人のデータを表示します。"
        "他人のデータをのぞき見しないよう、自分のIDだけを入れてください。"
    )
