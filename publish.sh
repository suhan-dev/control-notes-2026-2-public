#!/usr/bin/env bash
#
# 강의노트 빌드 & 배포 스크립트
#   - 영문/국문 모두 xelatex 로 컴파일한다 (controlnotes.sty 가 fontspec + xetexko 를 쓴다)
#   - 결과 PDF 를 docs/ 로 복사하고 docs/manifest.json 갱신
#   - 보조 파일 정리 후, git remote 가 있을 때만 커밋/푸시
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

DOCS="$HERE/docs"
mkdir -p "$DOCS"

EN_BASE="control_notes_EN"
KO_BASE="control_notes_KR"

# 빌드 시작 시각 기준점 (PDF 가 실제로 새로 나왔는지 판정용)
STAMP="$(mktemp -t ctrlpublish)"
trap 'rm -f "$STAMP"' EXIT

# build <engine> <basename> -> PDF 를 컴파일하고, 새 PDF 가 안 나오면 종료
build() {
  local engine="$1" base="$2"
  # 3회 돌린다. 이 문서는 목차가 수렴하는 데 3패스가 필요하다:
  #   1패스 = .toc 없음(목차가 아무것도 차지하지 않음) → 한 쪽씩 낮은 쪽번호로 .toc 기록
  #   2패스 = 그 틀린 .toc 를 읽어 조판(목차 쪽번호가 전부 -1), 올바른 .toc 기록
  #   3패스 = 올바른 .toc 로 조판
  # 아래에서 .toc 를 지우므로 매 빌드가 1패스 상태에서 시작한다 — 2회면 목차가 한 쪽씩 밀린다.
  local pass
  for pass in 1 2 3; do
    echo "==> ${engine} ${base}.tex (${pass}/3)"
    "$engine" -interaction=nonstopmode "${base}.tex" >/dev/null 2>&1 || true
  done

  if [[ ! -f "$HERE/${base}.pdf" ]] || [[ ! "$HERE/${base}.pdf" -nt "$STAMP" ]]; then
    echo "" >&2
    echo "!! 빌드 실패: ${base}.pdf 가 생성되지 않았습니다." >&2
    echo "!! ${base}.log 의 마지막 오류를 확인하세요:" >&2
    grep -n -m 5 -E '^(!|l\.[0-9]+)' "$HERE/${base}.log" >&2 || true
    exit 1
  fi
  echo "    ok: ${base}.pdf"
}

pagecount() {
  pdfinfo "$1" | awk '/^Pages:/ { print $2; exit }'
}

# ---- 영문판(xelatex): 필수 --------------------------------------------------
if [[ ! -f "$HERE/${EN_BASE}.tex" ]]; then
  echo "!! ${EN_BASE}.tex 가 없습니다. 저장소 루트에서 실행하고 있는지 확인하세요." >&2
  exit 1
fi
build xelatex "$EN_BASE"
cp -f "$HERE/${EN_BASE}.pdf" "$DOCS/${EN_BASE}.pdf"
EN_PAGES="$(pagecount "$DOCS/${EN_BASE}.pdf")"

# ---- 국문판(xelatex): 아직 없으면 건너뜀 ------------------------------------
KO_PAGES="null"
if [[ -f "$HERE/${KO_BASE}.tex" ]]; then
  build xelatex "$KO_BASE"
  cp -f "$HERE/${KO_BASE}.pdf" "$DOCS/${KO_BASE}.pdf"
  KO_PAGES="$(pagecount "$DOCS/${KO_BASE}.pdf")"
else
  echo "==> ${KO_BASE}.tex 없음 — 국문판 건너뜀 (pages.ko = null)"
  rm -f "$DOCS/${KO_BASE}.pdf"
fi

# ---- 회차 ------------------------------------------------------------------
# lectures.py 가 회차↔절 대응표에서 "제N강 / 그 날짜" 를 읽어
# {"count":6,"last":"2026-09-21"} 을 찍는다. 허브가 이걸로 "6강 · 9/21 수업까지"
# 를 표시한다. 표를 못 읽으면 아무것도 안 찍고 경고만 내므로, 그때는 lectures 를
# 빼고 나머지 manifest 를 그대로 만든다 — 배포가 회차 파싱 때문에 멈추지 않는다.
LECTURES="$(python3 "$HERE/lectures.py" || true)"
LEC_FIELD=""
if [[ -n "$LECTURES" ]]; then
  LEC_FIELD=",\"lectures\":$LECTURES"
  echo "==> 회차: $LECTURES"
else
  echo "==> 회차를 읽지 못해 manifest 의 lectures 를 생략합니다"
fi

# ---- manifest ---------------------------------------------------------------
# 파일명은 KR 이지만 뷰어가 읽는 manifest 키는 ko 다.
VERSION="$(date +%s)"
UPDATED="$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M') KST"
printf '{"version":"%s","updated":"%s","pages":{"en":%s,"ko":%s}%s}\n' \
  "$VERSION" "$UPDATED" "$EN_PAGES" "$KO_PAGES" "$LEC_FIELD" > "$DOCS/manifest.json"
echo "==> docs/manifest.json: $(cat "$DOCS/manifest.json")"

# ---- 보조 파일 정리 ---------------------------------------------------------
rm -f "$HERE"/*.aux "$HERE"/*.log "$HERE"/*.out "$HERE"/*.toc
echo "==> aux/log/out/toc 정리 완료"

# ---- git: remote 가 있을 때만 -----------------------------------------------
if git -C "$HERE" rev-parse --git-dir >/dev/null 2>&1 && [[ -n "$(git -C "$HERE" remote)" ]]; then
  git -C "$HERE" add -A
  if git -C "$HERE" diff --cached --quiet; then
    echo "==> 변경 사항 없음 — 커밋 생략"
  else
    git -C "$HERE" commit -m "notes: update $(date +%F)"
    git -C "$HERE" push
    echo "==> push 완료"
  fi
else
  echo ""
  echo "==> git remote 가 없어 배포를 건너뜁니다. docs/ 는 최신 상태입니다."
  echo "    배포하려면 저장소 루트에서:"
  echo "      git init && git add -A && git commit -m 'init'"
  echo "      git remote add origin <GitHub 저장소 URL>"
  echo "      git push -u origin main"
  echo "    그 뒤 GitHub 저장소 Settings > Pages 에서 Source = main 브랜치 /docs 로 지정."
  exit 0
fi
