# 개발 계획 — market-phase-tracker

> 이 문서는 앱 완성까지의 실행 계획이다. 원칙·아키텍처의 근거는 [`CLAUDE.md`](../CLAUDE.md)에 있고,
> 이 문서는 그 §8 빌드 순서를 **구체적 산출물·의사결정·리스크**로 확장한다.

## 확정된 결정
- **배포**: GitHub Pages (같은 저장소에서 Actions·Pages 통합, 서버리스 전제에 가장 단순).
- **데이터 소스 순서**: **키 불필요 소스(pykrx · FinanceDataReader)부터** 구현하고,
  ECOS·FRED는 **API 키 발급 후 연결**한다 (발급 안내는 이 문서 부록 참조).
- **상태 저장**: 별도 DB 없음. `data/data.json`(당일 스냅샷) + `data/history.json`(이력 누적).

## 현재 위치
- ✅ **Phase 0** — 학습 탭 프로토타입(`market-study-tab.html`), 저장소 초기화, 이 계획 문서.
- 🟡 **Phase 1 진행 중** — `collect.py`로 키 불필요 6개 지표 수집 + 첫 `data.json`/`history.json` 생성 성공.
- ⏭️ **다음** — Phase 1-B(키 발급 후 국채3년·미국채10년), 그리고 투자자 순매수 대안 결정.

### Phase 1 데이터 스파이크 발견 (2026-07)
| 지표 | 소스 | 결과 |
|---|---|---|
| 코스피·코스닥·삼성·하이닉스·환율·WTI | FinanceDataReader (키 불필요) | ✅ 정상 수집 |
| 미국채 10년 | FRED `DGS10` | ✅ **연결 완료** — requests 직접 호출. 미국장 D-1 지연(as_of보다 1영업일 앞설 수 있음). 키는 Secrets `FRED_API_KEY` |
| 국채 3년 | ECOS | ✅ **연결 완료** — 통계 `817Y002`(시장금리 일별)/항목 `010200000`(국고채 3년), 단위 연%. 키는 Secrets `ECOS_API_KEY` |
| 투자자 순매수(외인/기관/개인) | pykrx (KRX) → **Naver 폴백** | ✅ **Naver Finance로 해결**(키 불필요). KRX 직접 스크래핑은 이 환경에서 차단(403/"LOGOUT")이라 `investorDealTrendDay.naver`(sosok=01, 단위 억원)로 우회 |

- **패키지명 주의**: PyPI 배포명은 `finance-datareader`(하이픈), import는 `FinanceDataReader`.
- **투자자 순매수 결정 완료**: Naver Finance 폴백 구현(`src/sources._investor_naver`). KRX_ID/KRX_PW가 있으면 pykrx를 먼저 시도하고, 없으면 Naver로 폴백 → 자동화 환경에서도 키 없이 동작.

---

## Phase 1 — 데이터 스파이크
> 목적: "10개 지표를 실제로 한 번에 긁을 수 있는가?"를 증명. 코드 품질보다 **실측 검증**이 목표.

**진행 방식 (키 없음 반영):**
1. **1-A (키 불필요, 먼저)** — pykrx·FinanceDataReader로 수집:
   - 코스피·코스닥 지수, 삼성전자(005930)·SK하이닉스(000660) 종가·거래량
   - 주체별 순매수 — `pykrx.get_market_trading_value_by_investor` **반환 컬럼·부호 규약 실측**
   - WTI(`CL=F`) · 원달러(우선 FDR로 대체 수집)
2. **1-B (키 발급 후)** — ECOS 국채 3년, FRED 미국채 10년(DGS10) 연결. 통계표코드·결측·시차 실측.
3. `collect.py` 최소 버전으로 원시값 콘솔 출력 → 검증되면 첫 `data.json` 생성.

**3대 실측 포인트 (CLAUDE.md가 지목):**
- `get_market_trading_value_by_investor`의 반환 형식과 순매수 부호
- ECOS 국채3년 통계표코드·갱신 지연(D+1?)
- FRED DGS10 무료 키 응답·결측 처리

**리스크 & 대응:**
- 주말/장중 호출 시 빈 프레임 → "최근 유효 거래일" 폴백.
- ECOS 통계코드 오지정 → 발급 후 응답 샘플로 확정.
- 미국 지표 KST 시차 → `as_of`를 한국 거래일 기준으로 통일, 미국 지표는 직전 종가 사용.

---

## 제안 파일 구조
```
market-phase-tracker/
├─ CLAUDE.md
├─ docs/PLAN.md            # 이 문서
├─ collect.py              # 수집 진입점
├─ src/
│  ├─ sources/             # 소스별 fetch (pykrx / fdr / ecos / fred)
│  ├─ engine.py            # 국면 점수 계산
│  └─ schema.py            # data.json 검증
├─ data/
│  ├─ data.json            # 당일 스냅샷
│  └─ history.json         # 이력 누적
├─ web/                    # 정적 PWA (Pages 배포 대상)
│  ├─ index.html           # 3탭 셸
│  ├─ tabs/                # 국면 · 지표 · 학습(프로토타입 이식)
│  ├─ app.js  styles.css
│  ├─ manifest.webmanifest  sw.js
│  └─ data.json            # data/ 산출물 복사·참조
├─ .github/workflows/collect.yml
├─ requirements.txt
└─ .gitignore  .env.example
```

## 데이터 스키마 초안 (`data/data.json`)
```jsonc
{
  "as_of": "2026-07-27",           // 기준 거래일(KST)
  "generated_at": "…KST",
  "indicators": {
    "usdkrw": { "value": 1380.5, "chg": 4.2, "ma5": 0, "ma20": 0, "signal": -1 },
    "kr3y":   { "…": "동일 구조" }, "us10y": {}, "wti": {},
    "foreign_net": { "value": -1.2e11, "signal": -1 },  // 기관/개인도 동일 구조
    "samsung": {}, "hynix": {},
    "kospi": {}, "kosdaq": {}
  },
  "phase": { "score": -34, "label": "경계", "color": "amber", "confidence": 6, "total": 8 },
  "narrative": "…"                 // 학습 탭 서사 자동 생성
}
```
`data/history.json` = `[{ as_of, score, label, indicators요약 }]` 누적 → 국면 타임라인·스파크라인 소스.

---

## Phase 2 — 정적 국면/지표 화면 (data.json 소비)
- `web/index.html` 3탭 셸 + **학습 탭에 기존 프로토타입 이식**.
- **국면 탭**: 국면 배지 + −100~+100 게이지 + 한 줄 요약(narrative).
- **지표 탭**: 지표 카드 그리드(현재값·전일대비·스파크라인, Risk 방향별 색) + 히스토리 차트(Chart.js).
- 하드코딩 없이 `data.json` fetch만으로 렌더.

## Phase 3 — 국면 엔진 고도화 + 뷰 (뷰 완료, 튜닝 남음)
**완료**: `web/index.html` 국면 탭에 ① **실시간 인과 사슬**(5계층을 오늘 신호로 색칠) + ② **국면 타임라인**(`history.json`의 최근 20거래일 점수, 국면 밴드 배경). 20거래일 백필로 실데이터 분포 확보(점수 −50~+41).
**남은 것 (튜닝)**: 일간 점수가 다소 whippy — 전일대비 방향의 데드밴드(미세 변동 무시)나 점수 EMA 스무딩을 실데이터로 검증 후 도입. 도메인 검증 없이 과적합 금지.

| 지표 | Risk-on(+) 조건 | 제안 가중 |
|---|---|---|
| 외인 순매수 | 순매수 | **25** |
| 반도체(삼성·하이닉스) | 상승 / 상대강도 | **20** |
| 원달러 | 하락(원화강세) | **20** |
| 금리(한미차 · KR3Y 안정) | 급등 아님 | 15 |
| WTI | 급등 아님 | 10 |
| 지수(코스피·코스닥) | 상승(확인용) | 10 |

- 각 지표 신호 = **전일 대비 방향 + 5/20일 이평 대비 추세** → +1 / 0 / −1.
- 가중 합산 → −100~+100 정규화 → 4국면(위험선호 확장·중립·경계·위험회피 = 초록·노랑·주황·빨강).
- **신뢰도** = 순점수 부호와 같은 방향을 가리키는 지표 수.
- ⚠️ 임계값·가중치는 **실데이터 분포를 며칠 모아 본 뒤 튜닝**. 처음엔 단순 규칙.

## Phase 4 — PWA + 자동화 (배포: GitHub Pages)
- `manifest` + service worker(오프라인 캐시), 설치 가능화.
- `.github/workflows/collect.yml`: 평일 20:00 KST cron → `collect.py` → `data/` 커밋 → Pages 재배포.
- Secrets(ECOS·FRED) 주입. Pages는 저장소 Settings → Pages에서 브랜치/`web` 지정.

---

## 부록 — API 키 발급 안내 (Phase 1-B 진입 시)
**FRED (미국채 10년, DGS10)**
1. https://fredaccount.stlouisfed.org 가입 → "API Keys"에서 무료 키 발급.
2. 로컬은 `.env`의 `FRED_API_KEY`, 배포는 GitHub Secrets `FRED_API_KEY`.

**ECOS (한국은행 · 환율·국채3년)**
1. https://ecos.bok.or.kr → "Open API" → 인증키 신청(무료).
2. 필요한 통계표코드(원달러 환율, 국채수익률 3년)를 통계검색에서 확인해 확정.
3. 로컬 `.env`의 `ECOS_API_KEY`, 배포는 Secrets `ECOS_API_KEY`.

키는 절대 커밋하지 않는다 — `.env`는 `.gitignore`, 저장소에는 `.env.example`만.

---
**세션 재개 시**: 위 단계에서 미완료 최상단 항목부터 이어간다. 키가 준비되면 Phase 1-B를 바로 붙인다.
