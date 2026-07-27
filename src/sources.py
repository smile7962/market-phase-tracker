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


def _investor_pykrx(as_of):
    """KRX 계정(KRX_ID/KRX_PW)이 있을 때 pykrx로 수집. 실패/무자격이면 None.

    ⚠ 데이터 스파이크 발견(2026-07): 자격증명이 없는 egress IP에서 KRX
    data.krx.co.kr 이 로그인 세션을 요구(403/"LOGOUT")해 pykrx가 실패한다.
    """
    kid, kpw = os.getenv("KRX_ID"), os.getenv("KRX_PW")
    if not (kid and kpw):
        return None
    try:
        from pykrx import stock
        d = as_of.strftime("%Y%m%d")
        df = stock.get_market_trading_value_by_investor(d, d, "KOSPI")
        col = "순매수" if "순매수" in df.columns else df.columns[-1]
        return {
            "foreign": float(df.loc["외국인", col]),
            "institution": float(df.loc["기관합계", col]) if "기관합계" in df.index
                            else float(df.loc["기관", col]),
            "individual": float(df.loc["개인", col]),
        }
    except Exception:
        return None


def _investor_naver(as_of):
    """Naver Finance 투자자별 매매동향(키 불필요) 폴백.

    finance.naver.com/sise/investorDealTrendDay.naver — KOSPI(sosok=01) 일별
    순매수 표(단위: 억원). as_of 날짜 행을 찾고, 없으면 최신 행을 쓴다.
    반환: {"foreign","institution","individual","source":"naver","as_of":...}
    (값은 원 단위로 환산: 억원 × 1e8)
    """
    import re
    import requests

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    url = ("https://finance.naver.com/sise/investorDealTrendDay.naver"
           f"?bizdate={as_of.strftime('%Y%m%d')}&sosok=01")
    try:
        r = requests.get(url, headers={"User-Agent": ua}, timeout=20)
        html = r.content.decode("euc-kr", errors="replace")
    except Exception:
        return None

    m = re.search(r"<table.*?</table>", html, re.S)
    if not m:
        return None
    cells = [re.sub(r"<[^>]+>", "", c).strip()
             for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(0), re.S)]
    cells = [c for c in cells if c]

    # 헤더: 날짜 개인 외국인 기관계 ... → 데이터 행은 'YY.MM.DD' 로 시작
    def num(s):
        return float(s.replace(",", "").replace("&nbsp;", "") or 0)

    want = as_of.strftime("%y.%m.%d")
    rows = []
    for i, c in enumerate(cells):
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{2}", c):
            rows.append((c, cells[i + 1:i + 4]))  # 개인, 외국인, 기관계
    if not rows:
        return None
    date, vals = next((r for r in rows if r[0] == want), rows[0])
    try:
        indiv, foreign, inst = (num(vals[0]), num(vals[1]), num(vals[2]))
    except Exception:
        return None
    return {
        "foreign": foreign * 1e8, "institution": inst * 1e8, "individual": indiv * 1e8,
        "source": "naver", "as_of": "20" + date.replace(".", ""),
    }


def investor_net(as_of):
    """주체별(외국인/기관/개인) 순매수. KRX 계정이 있으면 pykrx, 없으면 Naver 폴백."""
    return _investor_pykrx(as_of) or _investor_naver(as_of)
