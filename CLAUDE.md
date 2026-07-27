# CLAUDE.md — market-phase-tracker

> **공통 규칙 로드 (Method B)**: 세션 시작 시 아래를 먼저 fetch해 규칙을 로드할 것.
> `curl -s https://raw.githubusercontent.com/smile7962/claude-rules/main/base.md`
> base.md의 원칙(간결·검증·실데이터 우선)이 이 프로젝트에도 그대로 적용된다.

---

## 1. What we're building
매크로 지표 10종을 **매일 자동 수집**하고, 지표 간 인과관계를 근거로 **Risk-on/off 시장 국면**을 진단해 보여주는 **모바일 웹앱(PWA)**.
사용자는 상시 PC가 없고 스마트폰 중심 → **서버리스 전제**가 핵심 제약.

## 2. Architecture (서버 없음)
```
[GitHub Actions cron · 평일 16:30 KST]
  → Python 수집 (pykrx + FinanceDataReader + ECOS/FRED)
  → 국면 점수 계산
  → data.json / history.json 커밋
        ↓
[정적 PWA · GitHub Pages 또는 Vercel] ← 스마트폰에서 열람·설치
```
- 별도 DB 없음. 상태는 `data.json`(당일 스냅샷) + `history.json`(이력 누적).
- API 키(ECOS·FRED)는 **GitHub Secrets**로 주입, 로컬 키는 `.gitignore`. (기존 DART API 키 처리 방식과 동일하게 갈 것.)

## 3. 10개 지표 & 데이터 소스
| 지표 | 소스 | 메모 |
|---|---|---|
| 코스피·코스닥 지수 | pykrx / FinanceDataReader | |
| 외인순매수·주체별(외국인/기관/개인) 순매수 | pykrx `get_market_trading_value_by_investor` | 반환 형식 실측 필요 |
| 삼성전자(005930)·SK하이닉스(000660) | pykrx | 종가·거래량 |
| 원달러 환율 | 한국은행 ECOS API (또는 FDR) | ECOS 공식 |
| 국채 3년 금리 | 한국은행 ECOS API | pykrx엔 없음 — ECOS 통계코드 확인 필요 |
| 미국채 10년 금리 | FRED API (DGS10) | 무료 키 |
| WTI 선물 | FinanceDataReader (CL=F) | |

## 4. 인과 사슬 (앱의 지적 근거)
```
매크로(US10Y·WTI) → 환율·금리(USD/KRW·KR3Y) → 수급(외인/기관/개인) → 반도체(삼성·하이닉스) → 지수(코스피·코스닥)
```
- Risk-off: US10Y↑ + WTI↑ → 달러강세 → 환율↑ → 외인 순매도 → 반도체↓ → 코스피↓
- Risk-on: 그 역방향. 코스닥은 사슬에서 다소 벗어나 개인 수급·국내 유동성을 별도 반영.

## 5. 국면 엔진 (핵심 차별점 — 승패를 가르는 부분)
- 각 지표를 신호화: **전일 대비 변화 + 추세(5·20일 이평 대비)** → 방향 (+1/0/-1).
- 방향 정의: 환율↓·금리 안정·외인 매수·반도체 강세 = Risk-on(+) / 반대 = Risk-off(-).
- **가중 합산 → 종합 점수 −100 ~ +100.** 외인수급·반도체·환율에 높은 가중.
- 4국면: `위험선호 확장 → 중립 → 경계 → 위험회피` (신호등: 초록/노랑/주황/빨강).
- **신뢰도** = 같은 방향으로 동조하는 지표 수. 함께 노출.
- ⚠ 임계값·가중치는 실데이터 범위를 본 뒤 튜닝. 처음엔 단순 규칙으로 시작.

## 6. 앱 탭 구성
- **국면**: 오늘의 국면 배지 + 종합 점수 게이지 + 한 줄 요약.
- **지표**: 지표 카드 그리드(현재값·전일대비·스파크라인, Risk 방향별 색) + 상세 히스토리 차트.
- **학습**: 인과 사슬 다이어그램 + Risk-on/off 토글 + 인사이트 5개. → `market-study-tab.html` 로 프로토타입 완성됨.

## 7. 파일 맵
- `market-study-tab.html` — 학습 탭 프로토타입 (완성, 정적).  *← 앱에 통합 예정*
- `data.json` / `history.json` — 수집 산출물 (아직 없음).
- `collect.py` — 데이터 수집 스크립트 (아직 없음).
- `.github/workflows/*.yml` — 일일 cron (아직 없음).

## 8. 빌드 순서 & 현재 상태
> 상세 실행 계획(산출물·스키마·엔진 규격·API 키 발급 안내): [`docs/PLAN.md`](docs/PLAN.md).
> 확정 결정 — 배포는 **GitHub Pages**, 데이터는 **키 불필요 소스(pykrx·FDR) 우선** 후 ECOS/FRED 연결.

- [x] Phase 0 — 학습 탭 프로토타입 (`market-study-tab.html`)
- [ ] **Phase 1 (NEXT) — 데이터 스파이크**: 10개 지표를 한 번에 긁어 `data.json` 생성 확인. *가장 불확실한 부분이라 여기부터.* 특히 ECOS 국채3년·FRED 미국채10년·pykrx 주체별 순매수의 실제 반환값 검증.
- [ ] Phase 2 — 정적 국면/지표 화면 (data.json 소비)
- [ ] Phase 3 — 국면 엔진 고도화(가중치·추세·신뢰도) + 인과 사슬 뷰 + 국면 타임라인
- [ ] Phase 4 — PWA화(설치·오프라인) + GitHub Actions 자동화

## 9. Stack
Python(pykrx·FinanceDataReader·requests) · GitHub Actions + GitHub Pages/Vercel · 프론트 바닐라 JS + Chart.js + PWA · 저장은 JSON 파일.

---
**세션 시작 시**: 위 §8의 현재 상태를 확인하고, 체크 안 된 가장 위 항목부터 이어간다.
