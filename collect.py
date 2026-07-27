#!/usr/bin/env python3
"""market-phase-tracker 데이터 수집 진입점 (Phase 1).

10개 지표를 수집해 data/data.json(당일 스냅샷)과 data/history.json(이력 누적)을
만든다. 키 불필요 소스(FinanceDataReader)는 바로 수집되고, 키가 필요하거나
차단된 소스(국채3년·미국채10년·투자자 순매수)는 자격증명이 없으면 "미수집"으로
표시된다.

사용법:
    python collect.py                # 최신 영업일 기준
    python collect.py --date 2026-07-24
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from src import sources, engine

DATA_DIR = Path(__file__).parent / "data"

# (키, 라벨, fetch함수) — 시계열 지표
SERIES_SPEC = [
    ("us10y", "미국채 10년", sources.us10y),
    ("wti", "WTI 유가", sources.wti),
    ("usdkrw", "원달러 환율", sources.usdkrw),
    ("kr3y", "국채 3년", sources.kr3y),
    ("samsung", "삼성전자", sources.samsung),
    ("hynix", "SK하이닉스", sources.hynix),
    ("kospi", "코스피", sources.kospi),
    ("kosdaq", "코스닥", sources.kosdaq),
]


def collect(as_of: datetime) -> dict:
    indicators: dict[str, dict] = {}
    signals: dict[str, int] = {}
    missing: list[str] = []

    # 시계열 지표
    for key, label, fn in SERIES_SPEC:
        ser = fn(as_of)
        st = engine._stats(ser)
        if st is None:
            indicators[key] = {"label": label, "status": "missing"}
            missing.append(key)
            continue
        sig = engine.indicator_signal(key, st)
        signals[key] = sig
        indicators[key] = {"label": label, "status": "ok", "signal": sig, **st}

    # 투자자 순매수 (외국인/기관/개인)
    inv = sources.investor_net(as_of)
    if inv is None:
        for k, lbl in [("foreign", "외국인 순매수"), ("institution", "기관 순매수"),
                       ("individual", "개인 순매수")]:
            indicators[k] = {"label": lbl, "status": "missing"}
            missing.append(k)
    else:
        for k, lbl in [("foreign", "외국인 순매수"), ("institution", "기관 순매수"),
                       ("individual", "개인 순매수")]:
            val = inv[k]
            sig = engine._signal(val)  # 순매수(+) = Risk-on
            if k == "foreign":
                signals["foreign"] = sig
            indicators[k] = {"label": lbl, "status": "ok", "signal": sig,
                             "value": round(val)}

    phase = engine.score_and_phase(signals)
    # 실제 기준 거래일 = 코스피 시계열의 마지막 날짜(있으면)
    as_of_str = indicators.get("kospi", {}).get("value") and as_of.strftime("%Y-%m-%d")

    return {
        "as_of": as_of_str or as_of.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "indicators": indicators,
        "phase": phase,
        "narrative": engine.narrative(phase),
        "missing": missing,
    }


def update_history(snapshot: dict) -> None:
    path = DATA_DIR / "history.json"
    history = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            history = []
    entry = {
        "as_of": snapshot["as_of"],
        "score": snapshot["phase"]["score"],
        "label": snapshot["phase"]["label"],
        "confidence": snapshot["phase"]["confidence"],
    }
    history = [h for h in history if h.get("as_of") != entry["as_of"]]
    history.append(entry)
    history.sort(key=lambda h: h["as_of"])
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="기준일 YYYY-MM-DD (기본: 오늘)")
    args = ap.parse_args()
    as_of = datetime.strptime(args.date, "%Y-%m-%d") if args.date else datetime.now()

    DATA_DIR.mkdir(exist_ok=True)
    snapshot = collect(as_of)
    (DATA_DIR / "data.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    update_history(snapshot)

    # 정적 웹(web/)이 fetch로 바로 읽도록 복사 — GitHub Pages 배포 대상
    web_dir = Path(__file__).parent / "web"
    if web_dir.exists():
        for name in ("data.json", "history.json"):
            (web_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")

    p = snapshot["phase"]
    ok = sum(1 for v in snapshot["indicators"].values() if v.get("status") == "ok")
    total = len(snapshot["indicators"])
    print(f"as_of={snapshot['as_of']}  수집 {ok}/{total}  "
          f"국면={p['label']}({p['score']})  신뢰도={p['confidence']}/{p['total']}")
    if snapshot["missing"]:
        print("미수집:", ", ".join(snapshot["missing"]))


if __name__ == "__main__":
    main()
