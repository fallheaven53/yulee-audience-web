# -*- coding: utf-8 -*-
"""
율이공방 — 관객통계 웹앱
토요상설공연 관객통계 등록·조회·분석
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(
    page_title="율이공방 — 관객통계",
    page_icon="📊",
    layout="wide",
)

from data_manager import AudienceManager, GENRES
from cross_sync import load_satisfaction_all, clear_satisfaction_cache

# ══════════════════════════════════════════════════════════════
#  데이터 연결
# ══════════════════════════════════════════════════════════════

@st.cache_resource
def get_dm():
    gsheet = None
    try:
        from gsheet_sync import AudienceSheetSync
        if "gcp_service_account" in st.secrets:
            gsheet = AudienceSheetSync(
                credentials_dict=dict(st.secrets["gcp_service_account"]),
                spreadsheet_id=st.secrets["spreadsheet_id"],
            )
    except Exception as e:
        st.sidebar.warning(f"구글 시트 연결 실패: {e}")
    return AudienceManager(gsheet_sync=gsheet)


def reload_dm():
    get_dm.clear()
    st.rerun()


def load_target_dates():
    """정산관리 구글 시트에서 출연단체 정보 참조"""
    if "target_dates" in st.session_state:
        return st.session_state["target_dates"]
    result = {}
    target_list = []
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        if "gcp_service_account" not in st.secrets:
            return result
        if "settlement_spreadsheet_id" not in st.secrets or not st.secrets["settlement_spreadsheet_id"]:
            return result
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(st.secrets["settlement_spreadsheet_id"])

        cur_year = str(datetime.now().year)
        ws1 = sh.worksheet("단체정보")
        rows = ws1.get_all_values()
        id_to_name = {}
        for row in rows[1:]:
            if row[0] and row[1]:
                id_to_name[row[0].strip()] = row[1].strip()

        ws2 = sh.worksheet("출연이력")
        rows2 = ws2.get_all_values()
        for row in rows2[1:]:
            if len(row) > 4 and row[2].strip() == cur_year:
                tid = row[1].strip()
                name = id_to_name.get(tid, "")
                rnd = row[3].strip()
                date_val = row[4].strip()
                if name and date_val:
                    result.setdefault(name, []).append((rnd, date_val))
                    if name not in target_list:
                        target_list.append(name)
    except Exception:
        pass
    st.session_state["target_dates"] = result
    st.session_state["target_list_db"] = sorted(target_list)
    return result


# ══════════════════════════════════════════════════════════════
#  탭 1: 관객통계 등록·관리
# ══════════════════════════════════════════════════════════════

def render_tab_records():
    dm = get_dm()
    target_dates = load_target_dates()
    db_targets = st.session_state.get("target_list_db", [])
    existing_targets = sorted({r.get("출연단체", "") for r in dm.get_records()
                               if r.get("출연단체", "")})
    all_targets = sorted(set(db_targets + existing_targets))

    # ── 입력 폼 ──
    edit_mode = st.session_state.get("edit_mode", False)
    edit_rnd = st.session_state.get("edit_rnd", None)

    form_title = f"✏ {edit_rnd}회차 수정" if edit_mode else "📝 관객통계 등록"

    with st.form("audience_form", clear_on_submit=not edit_mode):
        st.subheader(form_title)

        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        with c1:
            rnd_options = list(range(1, 25))
            default_rnd = rnd_options.index(edit_rnd) if edit_mode and edit_rnd in rnd_options else 0
            rnd = st.selectbox("회차", rnd_options, index=default_rnd,
                               key="form_rnd")

        # 자동 매칭: 회차 → 단체·공연일
        auto_target = ""
        auto_date = ""
        if target_dates:
            for name, entries in target_dates.items():
                for r, d in entries:
                    if str(r) == str(rnd):
                        auto_target = name
                        auto_date = d
                        break
                if auto_target:
                    break

        # 수정 모드 기본값
        if edit_mode and edit_rnd:
            rd = dm.rounds.get(edit_rnd, {})
            aud = dm.audience.get(edit_rnd, {})
            def_target = rd.get("출연단체", "")
            def_date = rd.get("공연일", "")
            def_genre = rd.get("장르", "")
            def_weather = rd.get("날씨", "")
            def_perf = aud.get("공연관객수", 0)
            def_exp = aud.get("체험참여수", 0)
            def_method = aud.get("카운트방법", "")
            def_note = aud.get("비고", "")
        else:
            def_target = auto_target
            def_date = auto_date
            def_genre = ""
            def_weather = ""
            def_perf = 0
            def_exp = 0
            def_method = ""
            def_note = ""

        with c2:
            if all_targets:
                target_idx = all_targets.index(def_target) if def_target in all_targets else 0
                target = st.selectbox("출연단체", [""] + all_targets,
                                      index=(target_idx + 1) if def_target else 0,
                                      key="form_target")
            else:
                target = st.text_input("출연단체", value=def_target, key="form_target")

        with c3:
            pub_date = st.text_input("공연일 (YYYY-MM-DD)", value=def_date,
                                     key="form_date")
        with c4:
            genre_opts = [""] + GENRES
            genre_idx = genre_opts.index(def_genre) if def_genre in genre_opts else 0
            genre = st.selectbox("장르", genre_opts, index=genre_idx,
                                 key="form_genre")

        c5, c6, c7, c8 = st.columns(4)
        with c5:
            weather_opts = ["", "맑음", "흐림", "비", "눈", "기타"]
            w_idx = weather_opts.index(def_weather) if def_weather in weather_opts else 0
            weather = st.selectbox("날씨", weather_opts, index=w_idx,
                                   key="form_weather")
        with c6:
            perf = st.number_input(
                "방문객수(공식)", min_value=0, value=def_perf,
                key="form_perf",
                help="경비일지·동구청 보고·결과보고서 공통 공식 숫자",
            )
        with c7:
            exp = st.number_input(
                "체험참여수", min_value=0, value=def_exp,
                key="form_exp",
                help="방문객 중 체험에 참여한 인원 (방문객수 이하)",
            )
        with c8:
            method_opts = ["", "수동카운트", "좌석기준", "추정"]
            m_idx = method_opts.index(def_method) if def_method in method_opts else 0
            method = st.selectbox("카운트방법", method_opts, index=m_idx,
                                  key="form_method")

        # 체험참여수 검증
        if exp > perf and perf > 0:
            st.warning(f"⚠ 체험참여수({exp})가 방문객수({perf})보다 큽니다. 확인해주세요.")

        note = st.text_input("비고", value=def_note, key="form_note")

        fc1, fc2 = st.columns(2)
        with fc1:
            submitted = st.form_submit_button(
                "수정 저장" if edit_mode else "등록",
                use_container_width=True, type="primary")
        with fc2:
            if edit_mode:
                cancel = st.form_submit_button("수정 취소", use_container_width=True)
            else:
                cancel = False

    if cancel:
        st.session_state["edit_mode"] = False
        st.session_state["edit_rnd"] = None
        st.rerun()

    if submitted:
        if not pub_date:
            st.error("공연일을 입력하세요.")
        else:
            save_rnd = edit_rnd if edit_mode else rnd
            round_info = {
                "공연일": pub_date,
                "출연단체": target if target else "",
                "장르": genre,
                "날씨": weather,
            }
            audience_info = {
                "공연관객수": perf,  # 내부 키(호환) — 화면엔 '방문객수(공식)'으로 표시
                "체험참여수": exp,
                "카운트방법": method,
                "비고": note,
            }
            dm.save_round(save_rnd, round_info, audience_info)
            if edit_mode:
                st.session_state["edit_mode"] = False
                st.session_state["edit_rnd"] = None
            st.success(f"{save_rnd}회차 {'수정' if edit_mode else '등록'} 완료!")
            st.rerun()

    # ── 필터 ──
    st.divider()
    fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 1])
    with fc1:
        f_rnd = st.selectbox("회차 필터", ["전체"] + [str(i) for i in range(1, 25)],
                             key="filter_rnd")
    with fc2:
        f_month = st.selectbox("월 필터",
                               ["전체"] + [f"{i}월" for i in range(1, 13)],
                               key="filter_month")
    with fc3:
        f_genre = st.selectbox("장르 필터", ["전체"] + GENRES,
                               key="filter_genre")
    with fc4:
        if st.button("필터 초기화", use_container_width=True):
            st.rerun()

    # ── 데이터 표시 ──
    records = dm.get_records()

    # 필터 적용
    if f_rnd != "전체":
        records = [r for r in records if str(r["회차"]) == f_rnd]
    if f_month != "전체":
        m = int(f_month.replace("월", ""))
        records = [r for r in records
                   if len(str(r["공연일"])) >= 7
                   and str(r["공연일"])[5:7] == f"{m:02d}"]
    if f_genre != "전체":
        records = [r for r in records if r["장르"] == f_genre]

    if records:
        df = pd.DataFrame(records)
        display_cols = ["회차", "공연일", "출연단체", "장르", "공연관객수",
                        "체험참여수", "비고"]
        df_show = df[[c for c in display_cols if c in df.columns]].rename(
            columns={"공연관객수": "방문객수(공식)"}
        )

        sel = st.dataframe(df_show, use_container_width=True, hide_index=True,
                           on_select="rerun", selection_mode="single-row",
                           key="rec_table")

        selected_rows = sel.get("selection", {}).get("rows", [])
        if selected_rows:
            sel_idx = selected_rows[0]
            if sel_idx >= len(records):
                st.rerun()
                return
            sel_rec = records[sel_idx]
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("수정", key="btn_edit", use_container_width=True):
                    st.session_state["edit_mode"] = True
                    st.session_state["edit_rnd"] = sel_rec["회차"]
                    st.rerun()
            with bc2:
                if st.button("삭제", key="btn_del", use_container_width=True,
                             type="primary"):
                    dm.delete_round(sel_rec["회차"])
                    st.success("삭제 완료!")
                    st.rerun()

            # ── 만족도분석기 연동 (읽기 전용) ──
            st.divider()
            st.markdown(f"**🔗 {sel_rec['회차']}회차 만족도분석기 연동**")
            sat_all = load_satisfaction_all()
            sat = sat_all.get(sel_rec["회차"])
            if sat is None:
                if sat_all:
                    st.warning("만족도 미실시")
                elif "satisfaction_sheet_id" in st.secrets and st.secrets.get("satisfaction_sheet_id"):
                    st.error("연동 데이터 불러오기 실패")
                else:
                    st.caption("만족도 시트 미연동 (secrets)")
            else:
                mc = st.columns(4)
                mc[0].metric("응답자 수", f"{sat.get('응답자수', 0):,}명")
                mc[1].metric("Q4 전반 만족(긍정률)", f"{sat.get('Q4_pos', 0)}%")
                mc[2].metric("Q16 재참여 의향", f"{sat.get('Q16_pos', 0)}%")
                mc[3].metric("Q17 추천 의향", f"{sat.get('Q17_pos', 0)}%")
                st.caption("※ 읽기 전용 — 값은 만족도분석기 웹앱에서 수정하세요.")

        # ── 상태바 ──
        s = dm.calc_summary(records)
        st.markdown(
            f"**표시: {s['total_cnt']}건 · "
            f"총 방문객수(공식): {s['total_aud']:,}명 · "
            f"평균: {s['avg_aud']:,}명**"
        )

        # ── 엑셀 내보내기 (총방문객수 제외, 방문객수(공식) 라벨 통일) ──
        buf = BytesIO()
        df_show.to_excel(buf, index=False, engine="openpyxl")
        st.download_button("📥 엑셀 다운로드", data=buf.getvalue(),
                           file_name=f"관객통계_{datetime.now():%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("해당 조건의 관객통계 데이터가 없습니다.")


# ══════════════════════════════════════════════════════════════
#  탭 2: 월별·연간 집계
# ══════════════════════════════════════════════════════════════

def render_tab_monthly():
    import plotly.graph_objects as go

    dm = get_dm()
    monthly = dm.calc_monthly()

    if not monthly:
        st.info("등록된 데이터가 없습니다.")
        return

    # 월별 집계 테이블
    st.subheader("📅 월별 관객수 집계")
    table_data = []
    for m in sorted(monthly.keys()):
        d = monthly[m]
        table_data.append({
            "월": f"{m}월",
            "공연 횟수": d["횟수"],
            "관객수 합계": d["합계"],
            "평균 관객수": d["평균"],
        })
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 연간 누적 차트
    st.subheader("📈 연간 관객수 추이")
    months = sorted(monthly.keys())
    month_labels = [f"{m}월" for m in months]
    values = [monthly[m]["합계"] for m in months]
    cumulative = []
    cum = 0
    for v in values:
        cum += v
        cumulative.append(cum)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=month_labels, y=values, name="월별 관객수",
        marker_color="#4FC3F7",
    ))
    fig.add_trace(go.Scatter(
        x=month_labels, y=cumulative, name="누적 관객수",
        line=dict(color="#FF7043", width=3),
        yaxis="y2",
    ))
    fig.update_layout(
        yaxis=dict(title="월별 관객수"),
        yaxis2=dict(title="누적 관객수", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.12),
        height=400,
        template="plotly_dark",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 합계 행
    total_cnt = sum(d["횟수"] for d in monthly.values())
    total_aud = sum(d["합계"] for d in monthly.values())
    avg_aud = round(total_aud / total_cnt, 1) if total_cnt > 0 else 0
    st.markdown(
        f"**연간 합계: {total_cnt}회 · {total_aud:,}명 · "
        f"평균 {avg_aud:,}명**"
    )


# ══════════════════════════════════════════════════════════════
#  탭 3: 장르별·단체별 통계
# ══════════════════════════════════════════════════════════════

def render_tab_analysis():
    import plotly.graph_objects as go

    dm = get_dm()

    # ── 장르별 ──
    st.subheader("🎭 장르별 관객수 비교")
    genre_data = dm.calc_by_genre()
    if genre_data:
        table_g = []
        for g in GENRES:
            if g in genre_data:
                d = genre_data[g]
                table_g.append({
                    "장르": g,
                    "공연 횟수": d["횟수"],
                    "관객수 합계": d["합계"],
                    "평균 관객수": d["평균"],
                })
        if table_g:
            df_g = pd.DataFrame(table_g)
            st.dataframe(df_g, use_container_width=True, hide_index=True)

            fig_g = go.Figure()
            fig_g.add_trace(go.Bar(
                x=[r["장르"] for r in table_g],
                y=[r["평균 관객수"] for r in table_g],
                marker_color=["#4FC3F7", "#81C784", "#FFB74D", "#CE93D8"],
            ))
            fig_g.update_layout(
                yaxis_title="평균 관객수",
                height=350,
                template="plotly_dark",
            )
            st.plotly_chart(fig_g, use_container_width=True)
    else:
        st.info("장르 데이터가 없습니다.")

    st.divider()

    # ── 단체별 ──
    st.subheader("🏢 단체별 관객수 순위")
    target_data = dm.calc_by_target()
    if target_data:
        table_t = []
        for t, d in sorted(target_data.items(),
                           key=lambda x: x[1]["합계"], reverse=True):
            table_t.append({
                "단체명": t,
                "공연 횟수": d["횟수"],
                "관객수 합계": d["합계"],
                "평균 관객수": d["평균"],
            })
        df_t = pd.DataFrame(table_t)
        st.dataframe(df_t, use_container_width=True, hide_index=True)

        # 상위 10개 차트
        top = table_t[:10]
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            x=[r["단체명"] for r in top],
            y=[r["관객수 합계"] for r in top],
            marker_color="#4FC3F7",
        ))
        fig_t.update_layout(
            yaxis_title="관객수 합계",
            height=350,
            template="plotly_dark",
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info("단체별 데이터가 없습니다.")


# ══════════════════════════════════════════════════════════════
#  탭 4: 통합 대시보드 (관객통계 × 만족도분석기)
# ══════════════════════════════════════════════════════════════

def render_tab_integrated():
    import plotly.graph_objects as go

    dm = get_dm()
    sat_all = load_satisfaction_all()
    records = dm.get_records()

    if not records:
        st.info("등록된 관객통계가 없습니다.")
        return

    if not sat_all:
        if "satisfaction_sheet_id" in st.secrets and st.secrets.get("satisfaction_sheet_id"):
            st.error("연동 데이터 불러오기 실패")
        else:
            st.warning("만족도 시트 ID가 secrets에 등록되지 않았습니다. "
                       "Streamlit Cloud Advanced settings → Secrets 에 "
                       "`satisfaction_sheet_id = \"1IUxzdOIyXV8Meej9tgkkPe66b7Mq7ix6UeRphpKCnok\"` 를 추가하세요.")
        return

    # ── 통합 테이블: 회차별 방문객수(공식) 대비 응답률 ──
    st.subheader("📊 회차별 방문객수(공식) × 만족도 응답률")
    rows_int = []
    for r in records:
        rnd = r["회차"]
        sat = sat_all.get(rnd, {})
        aud = r["공연관객수"] or 0
        resp = sat.get("응답자수", 0)
        rate = round(resp / aud * 100, 1) if aud > 0 else 0
        rows_int.append({
            "회차": rnd,
            "공연일": r["공연일"],
            "출연단체": r["출연단체"],
            "방문객수(공식)": aud,
            "만족도 응답자수": resp,
            "응답률(%)": rate,
            "Q4 긍정률(%)": sat.get("Q4_pos", 0),
            "Q16 재참여(%)": sat.get("Q16_pos", 0),
            "Q17 추천(%)": sat.get("Q17_pos", 0),
            "Q2 신규비율(%)": sat.get("Q2_신규비율", 0),
        })
    df_int = pd.DataFrame(rows_int)
    st.dataframe(df_int, use_container_width=True, hide_index=True)

    st.divider()

    # ── 방문객수 × Q4 긍정률 이중축 ──
    st.subheader("📈 방문객수(공식) × Q4 전반 만족도 긍정률 추이")
    rnd_axis = [r["회차"] for r in rows_int]
    aud_vals = [r["방문객수(공식)"] for r in rows_int]
    q4_vals = [r["Q4 긍정률(%)"] for r in rows_int]

    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=rnd_axis, y=aud_vals, name="방문객수(공식)",
        marker_color="#4FC3F7",
    ))
    fig1.add_trace(go.Scatter(
        x=rnd_axis, y=q4_vals, name="Q4 긍정률(%)",
        line=dict(color="#FF7043", width=3),
        mode="lines+markers",
        yaxis="y2",
    ))
    fig1.update_layout(
        xaxis=dict(title="회차"),
        yaxis=dict(title="방문객수(공식)"),
        yaxis2=dict(title="Q4 긍정률(%)", overlaying="y", side="right",
                    range=[0, 100]),
        legend=dict(orientation="h", y=1.12),
        height=420,
        template="plotly_dark",
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # ── 신규 유입 추세: Q2 '처음이에요' 비율 × 방문객수 ──
    st.subheader("🆕 신규 유입 추세 (Q2 ‘처음이에요’ 비율 × 방문객수)")
    new_vals = [r["Q2 신규비율(%)"] for r in rows_int]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=rnd_axis, y=aud_vals, name="방문객수(공식)",
        marker_color="#81C784",
    ))
    fig2.add_trace(go.Scatter(
        x=rnd_axis, y=new_vals, name="신규 관객 비율(%)",
        line=dict(color="#CE93D8", width=3),
        mode="lines+markers",
        yaxis="y2",
    ))
    fig2.update_layout(
        xaxis=dict(title="회차"),
        yaxis=dict(title="방문객수(공식)"),
        yaxis2=dict(title="신규 비율(%)", overlaying="y", side="right",
                    range=[0, 100]),
        legend=dict(orientation="h", y=1.12),
        height=420,
        template="plotly_dark",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── 요약 지표 ──
    st.divider()
    st.subheader("📋 통합 요약")
    valid_rate = [r["응답률(%)"] for r in rows_int if r["응답률(%)"] > 0]
    valid_q4 = [r["Q4 긍정률(%)"] for r in rows_int if r["Q4 긍정률(%)"] > 0]
    mc = st.columns(4)
    mc[0].metric("총 방문객수(공식)", f"{sum(aud_vals):,}명")
    mc[1].metric("총 응답자수", f"{sum(r['만족도 응답자수'] for r in rows_int):,}명")
    mc[2].metric("평균 응답률",
                 f"{round(sum(valid_rate)/len(valid_rate), 1) if valid_rate else 0}%")
    mc[3].metric("평균 Q4 긍정률",
                 f"{round(sum(valid_q4)/len(valid_q4), 1) if valid_q4 else 0}%")


# ══════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════

def main():
    st.title("📊 율이공방 — 관객통계")
    st.caption("2026 토요상설공연 관객통계 등록·분석")

    # 사이드바: 구글 시트 새로고침 + 연동 상태
    with st.sidebar:
        st.header("설정")
        if st.button("🔄 구글 시트 새로고침", use_container_width=True):
            clear_satisfaction_cache()
            reload_dm()
        if st.button("🔄 만족도 연동 새로고침", use_container_width=True):
            clear_satisfaction_cache()
            st.rerun()
        _sat = load_satisfaction_all()
        if _sat:
            st.success(f"🔗 만족도 연동: {len(_sat)}회차")
        elif "satisfaction_sheet_id" in st.secrets and st.secrets.get("satisfaction_sheet_id"):
            st.warning("🔗 만족도 연동 실패")
        else:
            st.caption("🔗 만족도 미연동 (secrets)")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 관객통계 등록·관리",
        "📅 월별·연간 집계",
        "📊 장르별·단체별 통계",
        "🔗 통합 대시보드",
    ])

    with tab1:
        render_tab_records()
    with tab2:
        render_tab_monthly()
    with tab3:
        render_tab_analysis()
    with tab4:
        render_tab_integrated()


if __name__ == "__main__":
    main()
