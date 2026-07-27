"""국면 엔진 (Phase 1 잠정판).

각 지표를 Risk-on(+1)/중립(0)/Risk-off(-1) 신호로 바꾸고, 가중 합산해
-100~+100 종합 점수와 4국면을 낸다. 임계값·가중치는 실데이터 분포를 며칠
모아 본 뒤 Phase 3에서 튜닝한다(지금은 단순 규칙).
"""
from __future__ import annotations

import pandas as pd

# 지표별 가중치 (docs/PLAN.md Phase 3 표) — 외인·반도체·환율에 높은 가중
WEIGHTS = {
    "foreign": 25,
    "samsung": 10, "hynix": 10,     # 반도체 20
    "usdkrw": 20,
    "us10y": 8, "kr3y": 7,          # 금리 15
    "wti": 10,
    "kospi": 5, "kosdaq": 5,        # 지수 10 (확인용)
}


def _stats(ser: pd.Series) -> dict | None:
    """전일대비·5/20일 이평 요약."""
    if ser is None or len(ser) < 2:
        return None
    ser = ser.astype(float)
    value = float(ser.iloc[-1])
    prev = float(ser.iloc[-2])
    chg = value - prev
    chg_pct = (chg / prev * 100) if prev else 0.0
    ma5 = float(ser.tail(5).mean()) if len(ser) >= 5 else None
    ma20 = float(ser.tail(20).mean()) if len(ser) >= 20 else None
    return {"value": round(value, 4), "chg": round(chg, 4),
            "chg_pct": round(chg_pct, 3), "ma5": ma5 and round(ma5, 4),
            "ma20": ma20 and round(ma20, 4),
            "spark": [round(float(x), 4) for x in ser.tail(20)]}


def _trend(st: dict) -> int:
    """추세: 5일 이평이 20일 이평 위면 +1, 아래면 -1, 없으면 0."""
    if not st or st["ma5"] is None or st["ma20"] is None:
        return 0
    if st["ma5"] > st["ma20"]:
        return 1
    if st["ma5"] < st["ma20"]:
        return -1
    return 0


def _dir(st: dict) -> int:
    """전일대비 방향."""
    if not st:
        return 0
    return 1 if st["chg"] > 0 else (-1 if st["chg"] < 0 else 0)


def _signal(raw: int) -> int:
    return 1 if raw > 0 else (-1 if raw < 0 else 0)


# Risk-on(+1) 관점 부호 규약: 지표 상승이 Risk-on이면 +1, 아니면 -1을 곱한다.
RISK_SIGN = {
    "kospi": +1, "kosdaq": +1, "samsung": +1, "hynix": +1,  # 상승 = Risk-on
    "usdkrw": -1,   # 환율 하락(원화 강세) = Risk-on
    "us10y": -1, "kr3y": -1,  # 금리 급등 = Risk-off
    "wti": -1,      # 유가 급등 = 인플레 → Risk-off
}


def indicator_signal(key: str, st: dict) -> int:
    """방향+추세를 합쳐 Risk-on 관점 신호(-1/0/+1)."""
    if not st:
        return 0
    raw = _dir(st) + _trend(st)      # -2..+2
    return _signal(raw) * RISK_SIGN.get(key, +1)


def score_and_phase(signals: dict[str, int]) -> dict:
    """사용 가능한 신호만으로 가중 평균 → -100~+100 점수와 4국면."""
    avail = {k: s for k, s in signals.items() if k in WEIGHTS}
    wsum = sum(WEIGHTS[k] for k in avail)
    if not wsum:
        return {"score": 0, "label": "중립", "color": "yellow",
                "confidence": 0, "total": 0}
    raw = sum(WEIGHTS[k] * s for k, s in avail.items())
    score = round(100 * raw / wsum)

    if score > 30:
        label, color = "위험선호 확장", "green"
    elif score > 0:
        label, color = "중립", "yellow"
    elif score >= -30:
        label, color = "경계", "amber"
    else:
        label, color = "위험회피", "red"

    sign = 1 if score > 0 else (-1 if score < 0 else 0)
    confidence = sum(1 for s in avail.values() if s == sign and s != 0)
    return {"score": score, "label": label, "color": color,
            "confidence": confidence, "total": sum(1 for s in avail.values() if s != 0)}


def narrative(phase: dict) -> str:
    if phase["score"] > 0:
        return ("미국 금리 안정 + 원화 강세 → 외인 순매수 → 반도체 매수 → "
                "삼성·하이닉스 상승 → 코스피 상승 우호")
    if phase["score"] < 0:
        return ("미국채·유가 상승 → 달러 강세 → 원달러 상승 → 외인 순매도 → "
                "삼성·하이닉스 하락 → 코스피 하락 압력")
    return "지표 신호가 엇갈려 뚜렷한 방향이 없는 중립 국면"
