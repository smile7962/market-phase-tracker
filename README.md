# market-phase-tracker

매크로 지표 10종을 매일 자동 수집하고, 지표 간 인과관계를 근거로 **Risk-on/off 시장 국면**을
진단해 보여주는 **서버리스 모바일 웹앱(PWA)**.

> 원칙·아키텍처: [`CLAUDE.md`](CLAUDE.md) · 개발 계획: [`docs/PLAN.md`](docs/PLAN.md)

## 구조 (서버 없음)
```
GitHub Actions cron(평일 20:00 KST)
  → collect.py (pykrx·FinanceDataReader·ECOS·FRED)
  → data/data.json · history.json 커밋 + web/ 복사
  → GitHub Pages 정적 배포 → 스마트폰에서 열람·설치(PWA)
```

## 로컬 실행
```bash
pip install -r requirements.txt
python collect.py                 # 최신 영업일 (또는 --date 2026-07-24)
python -m http.server -d web 8000 # http://localhost:8000
```
키 없이도 **9/11 지표**가 수집된다 — 코스피·코스닥·삼성·하이닉스·환율·WTI(FDR) +
외국인/기관/개인 순매수(Naver Finance 폴백). `ECOS_API_KEY`(국채3년)와
`FRED_API_KEY`(미국채10년)를 넣으면 **11/11 전 지표**가 채워진다.

## 앱 탭
- **국면** — 오늘의 국면 배지 + −100~+100 게이지 + 한 줄 흐름 + 신뢰도
- **지표** — 지표 카드(현재값·전일대비·스파크라인, Risk 방향 색)
- **학습** — 인과 사슬 다이어그램 + Risk-on/off 토글 + 인사이트

## 배포 (GitHub Pages)
1. Settings → Pages → **Source: GitHub Actions**.
2. (선택) Settings → Secrets → Actions 에 `FRED_API_KEY`, `ECOS_API_KEY`,
   (그리고 KRX 계정 쓰면 `KRX_ID`/`KRX_PW`) 등록.
3. `.github/workflows/collect.yml` 이 평일 20:00 KST 에 수집·커밋·배포.
   (cron은 기본 브랜치에서만 발화 — 병합 후 자동. 그 전엔 Actions 탭에서 수동 실행.)

## 상태
- [x] Phase 0 학습 탭 프로토타입
- [x] Phase 1 데이터 스파이크 (`collect.py`, 첫 `data.json`)
- [x] Phase 2 3탭 웹앱 (`web/index.html`)
- [~] Phase 3 인과 사슬 뷰 + 국면 타임라인 완료 · 엔진 가중치 튜닝만 남음
- [x] Phase 4 PWA(manifest·service worker) + GitHub Actions 자동화

자세한 내용과 데이터 스파이크 발견(예: 이 실행환경에서 KRX 차단)은 `docs/PLAN.md` 참조.
