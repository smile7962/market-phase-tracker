"""데이터 소스별 수집 함수 (Phase 1).

설계 원칙
- **키 불필요 소스(FinanceDataReader) 우선.** 키가 필요한 소스(ECOS 국채3년,
  FRED 미국채10년)와 KRX 차단으로 막힌 투자자 순매수는 자격증명이 없으면
  조용히 `None`을 돌려주고, collect.py가 "미수집"으로 표시한다.
- 각 fetch 함수는 최근 N영업일 종가 시계열(pandas Series, index=날짜)을 돌려준다.
  이렇게 하면 engine이 전일대비·5/20일 이평을 일관되게 계산할 수 있다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import FinanceDataReader as fdr

LOOKBACK_DAYS = 40  # 20일 이평 계산에 충분한 여유


def _range(as_of: datetime) -> tuple[str, str]:
    start = as_of - timedelta(days=LOOKBACK_DAYS)
    return start.strftime("%Y-%m-%d"), as_of.strftime("%Y-%m-%d")


def _close_series(symbol: str, as_of: datetime, col: str = "Close") -> pd.Series | None:
    """FDR에서 종가 시계열을 가져온다. 실패 시 None."""
    s, e = _range(as_of)
    try:
        df = fdr.DataReader(symbol, s, e)
        if df is None or df.empty or col not in df.columns:
            return None
        ser = df[col].dropna()
        return ser if not ser.empty else None
    except Exception:
        return None


# ── 키 불필요 소스 (FinanceDataReader) ────────────────────────────────

def kospi(as_of):   return _close_series("KS11", as_of)
def kosdaq(as_of):  return _close_series("KQ11", as_of)
def samsung(as_of): return _close_series("005930", as_of)
def hynix(as_of):   return _close_series("000660", as_of)
def usdkrw(as_of):  return _close_series("USD/KRW", as_of)
def wti(as_of):     return _close_series("CL=F", as_of)


# ── 키 필요 / 차단됨 (자격증명 없으면 None) ────────────────────────────

def us10y(as_of):
    """미국채 10년 (FRED DGS10). FRED_API_KEY 없으면 None → Phase 1-B."""
    key = os.getenv("FRED_API_KEY")
    if not key:
        return None
    try:
        # fredapi 미설치 환경도 있으므로 지연 import
        from fredapi import Fred
        fred = Fred(api_key=key)
        s, e = _range(as_of)
        ser = fred.get_series("DGS10", observation_start=s, observation_end=e).dropna()
        return ser if not ser.empty else None
    except Exception:
        return None


def kr3y(as_of):
    """국채 3년 (한국은행 ECOS). ECOS_API_KEY 없으면 None → Phase 1-B.

    통계표코드/항목코드는 키 발급 후 ECOS 통계검색으로 확정한다(부록 참조).
    """
    key = os.getenv("ECOS_API_KEY")
    if not key:
        return None
    try:
        import requests
        s = (as_of - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
        e = as_of.strftime("%Y%m%d")
        # 817Y002 = 시장금리(일별), 010200000 = 국고채 3년 (발급 후 실측 검증 필요)
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100/"
            f"817Y002/D/{s}/{e}/010200000"
        )
        r = requests.get(url, timeout=20)
        rows = r.json().get("StatisticSearch", {}).get("row", [])
        if not rows:
            return None
        idx = pd.to_datetime([x["TIME"] for x in rows])
        vals = [float(x["DATA_VALUE"]) for x in rows]
        return pd.Series(vals, index=idx).dropna()
    except Exception:
        return None


def investor_net(as_of):
    """주체별(외국인/기관/개인) 순매수 거래대금.

    ⚠ 데이터 스파이크 발견(2026-07): 이 실행 환경의 egress IP에서 KRX
    data.krx.co.kr 이 로그인 세션을 요구(403 / "LOGOUT")해 pykrx가 실패한다.
    KRX_ID/KRX_PW 가 있으면 pykrx 로그인으로 재시도한다. 없으면 None.
    (대안: Naver Finance 스크래핑 — 별도 결정 필요.)

    반환: {"foreign": float, "institution": float, "individual": float} (순매수 원)
    """
    kid, kpw = os.getenv("KRX_ID"), os.getenv("KRX_PW")
    if not (kid and kpw):
        return None
    try:
        from pykrx import stock
        d = as_of.strftime("%Y%m%d")
        df = stock.get_market_trading_value_by_investor(d, d, "KOSPI")
        # 반환 형식은 로그인 성공 후 실측으로 컬럼명 확정 필요
        col = "순매수" if "순매수" in df.columns else df.columns[-1]
        return {
            "foreign": float(df.loc["외국인", col]),
            "institution": float(df.loc["기관합계", col]) if "기관합계" in df.index
                            else float(df.loc["기관", col]),
            "individual": float(df.loc["개인", col]),
        }
    except Exception:
        return None
