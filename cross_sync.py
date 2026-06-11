# -*- coding: utf-8 -*-
"""만족도분석기 시트 읽기 전용 연동 (관객통계 → 만족도분석기)"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# yulee-common 가용 시 인라인 인증을 get_client로 대체 (#2026-070 3단계).
try:
    from yulee_common import get_client as _yc_get_client
    _USE_YULEE_COMMON = True
except ImportError:
    _yc_get_client = None
    _USE_YULEE_COMMON = False

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

POSITIVE_LEVELS = ["매우 그렇다", "그렇다"]


def _pos_rate(dist):
    """{보기:값} → 긍정응답률(%)"""
    if not dist:
        return 0.0
    total = sum(v for v in dist.values() if v)
    if total <= 0:
        return 0.0
    pos = sum(v for k, v in dist.items() if k in POSITIVE_LEVELS)
    return round(pos / total * 100, 1)


def _ratio(dist, key):
    """{보기:값} → 특정 보기의 비율(%)"""
    if not dist:
        return 0.0
    total = sum(v for v in dist.values() if v)
    if total <= 0:
        return 0.0
    return round(dist.get(key, 0) / total * 100, 1)


@st.cache_data(ttl=300, show_spinner=False)
def load_satisfaction_all():
    """
    만족도 시트에서 회차별 요약을 읽어 dict로 반환.
    {회차(int): {응답자수, Q4_pos, Q16_pos, Q17_pos, Q2_신규비율}}
    실패 시 빈 dict.
    """
    if "gcp_service_account" not in st.secrets:
        return {}
    sheet_id = st.secrets.get("satisfaction_sheet_id", "")
    if not sheet_id:
        return {}
    try:
        if _USE_YULEE_COMMON:
            sh = _yc_get_client(spreadsheet_key="satisfaction_sheet_id",
                                slim_scope=True).sh
        else:
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(sheet_id)

        result = {}

        # 회차정보 (회차, 공연일, 출연단체, 장르, 응답자수, 보충여부)
        try:
            ws = sh.worksheet("회차정보")
            rows = ws.get_all_values()
            for row in rows[1:]:
                if not row or not row[0]:
                    continue
                try:
                    rnd = int(row[0])
                except ValueError:
                    continue
                try:
                    n = int(row[4]) if len(row) > 4 and row[4] else 0
                except ValueError:
                    n = 0
                result[rnd] = {
                    "응답자수": n,
                    "Q4_pos": 0.0, "Q16_pos": 0.0, "Q17_pos": 0.0,
                    "Q2_신규비율": 0.0,
                }
        except Exception:
            pass

        # 응답분포 (회차, Q코드, 보기, 값) → Q4/Q16/Q17 긍정률, Q2 "처음이에요" 비율
        try:
            ws = sh.worksheet("응답분포")
            rows = ws.get_all_values()
            by_round_q = {}  # {(rnd, q): {opt: val}}
            for row in rows[1:]:
                if not row or len(row) < 4 or not row[0]:
                    continue
                try:
                    rnd = int(row[0])
                except ValueError:
                    continue
                q_code = row[1]
                opt = row[2]
                try:
                    val = float(row[3]) if row[3] else 0
                except ValueError:
                    val = 0
                by_round_q.setdefault((rnd, q_code), {})[opt] = val

            for (rnd, q_code), dist in by_round_q.items():
                entry = result.setdefault(rnd, {
                    "응답자수": 0, "Q4_pos": 0.0,
                    "Q16_pos": 0.0, "Q17_pos": 0.0, "Q2_신규비율": 0.0,
                })
                if q_code == "Q4":
                    entry["Q4_pos"] = _pos_rate(dist)
                elif q_code == "Q16":
                    entry["Q16_pos"] = _pos_rate(dist)
                elif q_code == "Q17":
                    entry["Q17_pos"] = _pos_rate(dist)
                elif q_code == "Q2":
                    entry["Q2_신규비율"] = _ratio(dist, "처음이에요")
        except Exception:
            pass

        return result
    except Exception:
        return {}


def clear_satisfaction_cache():
    load_satisfaction_all.clear()
