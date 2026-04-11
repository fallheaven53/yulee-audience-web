# -*- coding: utf-8 -*-
"""관객통계 웹앱 — 데이터 매니저"""

from datetime import datetime

GENRES = ["판소리·산조", "국악창작", "연희·무용", "무형유산"]


class AudienceManager:
    def __init__(self, gsheet_sync=None):
        self.rounds = {}       # {회차int: {공연일, 출연단체, 장르, 날씨}}
        self.audience = {}     # {회차int: {공연관객수, 체험참여수, 총방문객수, 카운트방법, 비고}}
        self.composition = {}  # {회차int: {연령_아동청소년, ...}}
        self.routes = {}       # {회차int: {경로명: 값}}
        self.route_items = ["경로_SNS", "경로_현수막", "경로_지인소개",
                            "경로_등산겸방문", "경로_재방문", "경로_기타"]
        self.gsheet = gsheet_sync
        if self.gsheet:
            self.gsheet.download_all(self)

    # ── CRUD ──
    def save_round(self, rnd, round_info, audience_info):
        """회차 데이터 저장 (등록/수정 겸용)

        총방문객수는 더 이상 입력받지 않으며, 기존 시트에 남아있던 값을
        유지하기 위해 저장 시 dm.audience의 기존 총방문객수를 그대로 보존한다.
        """
        self.rounds[rnd] = round_info
        existing_total = self.audience.get(rnd, {}).get("총방문객수", 0)
        audience_info.setdefault("총방문객수", existing_total)
        self.audience[rnd] = audience_info
        self._sync()

    def delete_round(self, rnd):
        self.rounds.pop(rnd, None)
        self.audience.pop(rnd, None)
        self.composition.pop(rnd, None)
        self.routes.pop(rnd, None)
        self._sync()

    def _sync(self):
        if self.gsheet:
            self.gsheet.upload_all(self)

    # ── 집계 ──
    def get_records(self):
        """회차별 데이터를 리스트로 반환"""
        records = []
        for rnd in sorted(self.rounds.keys()):
            rd = self.rounds[rnd]
            aud = self.audience.get(rnd, {})
            records.append({
                "회차": rnd,
                "공연일": rd.get("공연일", ""),
                "출연단체": rd.get("출연단체", ""),
                "장르": rd.get("장르", ""),
                "날씨": rd.get("날씨", ""),
                "공연관객수": aud.get("공연관객수", 0),
                "체험참여수": aud.get("체험참여수", 0),
                "총방문객수": aud.get("총방문객수", 0),
                "카운트방법": aud.get("카운트방법", ""),
                "비고": aud.get("비고", ""),
            })
        return records

    def calc_summary(self, records=None):
        if records is None:
            records = self.get_records()
        total_cnt = len(records)
        total_aud = sum(r["공연관객수"] for r in records)
        avg_aud = round(total_aud / total_cnt, 1) if total_cnt > 0 else 0
        return {
            "total_cnt": total_cnt,
            "total_aud": total_aud,
            "avg_aud": avg_aud,
        }

    def calc_monthly(self):
        """월별 집계: {월: {횟수, 관객합계, 평균}}"""
        monthly = {}
        for rnd in sorted(self.rounds.keys()):
            rd = self.rounds[rnd]
            aud = self.audience.get(rnd, {}).get("공연관객수", 0)
            date_str = str(rd.get("공연일", ""))
            if len(date_str) >= 7:
                try:
                    month = int(date_str[5:7])
                except ValueError:
                    continue
                if month not in monthly:
                    monthly[month] = {"횟수": 0, "합계": 0}
                monthly[month]["횟수"] += 1
                monthly[month]["합계"] += aud
        for m in monthly:
            cnt = monthly[m]["횟수"]
            monthly[m]["평균"] = round(monthly[m]["합계"] / cnt, 1) if cnt > 0 else 0
        return monthly

    def calc_by_genre(self):
        """장르별 집계: {장르: {횟수, 합계, 평균}}"""
        result = {}
        for rnd in sorted(self.rounds.keys()):
            genre = self.rounds[rnd].get("장르", "")
            if not genre:
                continue
            aud = self.audience.get(rnd, {}).get("공연관객수", 0)
            if genre not in result:
                result[genre] = {"횟수": 0, "합계": 0}
            result[genre]["횟수"] += 1
            result[genre]["합계"] += aud
        for g in result:
            cnt = result[g]["횟수"]
            result[g]["평균"] = round(result[g]["합계"] / cnt, 1) if cnt > 0 else 0
        return result

    def calc_by_target(self):
        """단체별 집계: {단체명: {횟수, 합계, 평균}}"""
        result = {}
        for rnd in sorted(self.rounds.keys()):
            target = self.rounds[rnd].get("출연단체", "")
            if not target:
                continue
            aud = self.audience.get(rnd, {}).get("공연관객수", 0)
            if target not in result:
                result[target] = {"횟수": 0, "합계": 0}
            result[target]["횟수"] += 1
            result[target]["합계"] += aud
        for t in result:
            cnt = result[t]["횟수"]
            result[t]["평균"] = round(result[t]["합계"] / cnt, 1) if cnt > 0 else 0
        return result
