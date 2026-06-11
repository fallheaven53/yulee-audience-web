# -*- coding: utf-8 -*-
"""관객통계 — 구글 시트 동기화"""

import gspread
from google.oauth2.service_account import Credentials

# yulee-common 가용 시 인증·시트 접근을 공통 모듈로 위임 (#2026-070 3단계).
# 가용 안 할 시 기존 로컬 코드 폴백 — 마이그레이션 직후 1개월 안전망.
try:
    from yulee_common import GSheetClient
    _USE_YULEE_COMMON = True
except ImportError:
    _USE_YULEE_COMMON = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class AudienceSheetSync:
    """관객통계 ↔ 구글 스프레드시트 양방향 동기화"""

    def __init__(self, credentials_path=None, credentials_dict=None,
                 spreadsheet_id=""):
        if _USE_YULEE_COMMON:
            self._client = GSheetClient(
                credentials_dict=credentials_dict,
                credentials_path=credentials_path,
                spreadsheet_id=spreadsheet_id)
            self.gc = self._client.gc
            self.sh = self._client.sh
            return

        self._client = None
        if credentials_dict:
            creds = Credentials.from_service_account_info(
                credentials_dict, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(spreadsheet_id)

    # ── 시트 가져오기 (없으면 생성) ──
    def _ws(self, title, rows=200, cols=20):
        if self._client is not None:
            return self._client.ws(title, rows=rows, cols=cols)
        try:
            return self.sh.worksheet(title)
        except gspread.WorksheetNotFound:
            return self.sh.add_worksheet(title, rows=rows, cols=cols)

    # ── 업로드 ──
    def upload_all(self, dm):
        """DataManager → 구글 시트"""
        # 회차기본
        ws1 = self._ws("회차기본")
        data1 = [["회차", "공연일", "출연단체", "장르", "날씨"]]
        for rnd in sorted(dm.rounds.keys()):
            d = dm.rounds[rnd]
            pub = d.get("공연일", "")
            if hasattr(pub, "strftime"):
                pub = pub.strftime("%Y-%m-%d")
            data1.append([rnd, str(pub), d.get("출연단체", ""),
                          d.get("장르", ""), d.get("날씨", "")])
        ws1.clear()
        if data1:
            ws1.update(data1, value_input_option="RAW")

        # 관객수
        ws2 = self._ws("관객수")
        data2 = [["회차", "공연관객수", "체험참여수", "총방문객수", "카운트방법", "비고"]]
        for rnd in sorted(dm.audience.keys()):
            d = dm.audience[rnd]
            data2.append([rnd, d.get("공연관객수", 0), d.get("체험참여수", 0),
                          d.get("총방문객수", 0), d.get("카운트방법", ""),
                          d.get("비고", "")])
        ws2.clear()
        if data2:
            ws2.update(data2, value_input_option="RAW")

        # 관객구성
        ws3 = self._ws("관객구성")
        data3 = [["회차", "연령_아동청소년", "연령_청년", "연령_중장년",
                  "연령_어르신", "외국인", "장애인"]]
        for rnd in sorted(dm.composition.keys()):
            d = dm.composition[rnd]
            data3.append([rnd, d.get("연령_아동청소년", 0), d.get("연령_청년", 0),
                          d.get("연령_중장년", 0), d.get("연령_어르신", 0),
                          d.get("외국인", 0), d.get("장애인", 0)])
        ws3.clear()
        if data3:
            ws3.update(data3, value_input_option="RAW")

        # 방문경로
        ws4 = self._ws("방문경로")
        data4 = [["회차"] + dm.route_items]
        for rnd in sorted(dm.routes.keys()):
            d = dm.routes[rnd]
            data4.append([rnd] + [d.get(item, 0) for item in dm.route_items])
        ws4.clear()
        if data4:
            ws4.update(data4, value_input_option="RAW")

    # ── 다운로드 ──
    def download_all(self, dm):
        """구글 시트 → DataManager"""
        # 회차기본
        try:
            ws1 = self.sh.worksheet("회차기본")
            rows = ws1.get_all_values()
            dm.rounds = {}
            for row in rows[1:]:
                if not row[0]:
                    continue
                rnd = int(row[0])
                dm.rounds[rnd] = {
                    "공연일": row[1] if len(row) > 1 else "",
                    "출연단체": row[2] if len(row) > 2 else "",
                    "장르": row[3] if len(row) > 3 else "",
                    "날씨": row[4] if len(row) > 4 else "",
                }
        except Exception:
            pass

        # 관객수
        try:
            ws2 = self.sh.worksheet("관객수")
            rows = ws2.get_all_values()
            dm.audience = {}
            for row in rows[1:]:
                if not row[0]:
                    continue
                rnd = int(row[0])
                dm.audience[rnd] = {
                    "공연관객수": int(row[1]) if len(row) > 1 and row[1] else 0,
                    "체험참여수": int(row[2]) if len(row) > 2 and row[2] else 0,
                    "총방문객수": int(row[3]) if len(row) > 3 and row[3] else 0,
                    "카운트방법": row[4] if len(row) > 4 else "",
                    "비고": row[5] if len(row) > 5 else "",
                }
        except Exception:
            pass

        # 관객구성
        try:
            ws3 = self.sh.worksheet("관객구성")
            rows = ws3.get_all_values()
            dm.composition = {}
            for row in rows[1:]:
                if not row[0]:
                    continue
                rnd = int(row[0])
                dm.composition[rnd] = {
                    "연령_아동청소년": int(row[1]) if len(row) > 1 and row[1] else 0,
                    "연령_청년": int(row[2]) if len(row) > 2 and row[2] else 0,
                    "연령_중장년": int(row[3]) if len(row) > 3 and row[3] else 0,
                    "연령_어르신": int(row[4]) if len(row) > 4 and row[4] else 0,
                    "외국인": int(row[5]) if len(row) > 5 and row[5] else 0,
                    "장애인": int(row[6]) if len(row) > 6 and row[6] else 0,
                }
        except Exception:
            pass

        # 방문경로
        try:
            ws4 = self.sh.worksheet("방문경로")
            rows = ws4.get_all_values()
            dm.routes = {}
            if rows:
                headers = rows[0]
                for row in rows[1:]:
                    if not row[0]:
                        continue
                    rnd = int(row[0])
                    d = {}
                    for i, h in enumerate(headers[1:], 1):
                        if h and len(row) > i:
                            d[h] = int(row[i]) if row[i] else 0
                    dm.routes[rnd] = d
        except Exception:
            pass

        if hasattr(dm, "save"):
            dm.save()
