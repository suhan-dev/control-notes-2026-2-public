#!/usr/bin/env python3
r"""노트 소스에서 "몇 회차까지 반영됐는지" 를 읽어 manifest 조각으로 찍는다.

publish.sh 가 부른다.  성공하면 stdout 에 한 줄:

    {"count":10,"last":"2026-10-07"}

count 는 마지막 강의의 회차 번호, last 는 그 강의 날짜(ISO).

회차 번호는 노트가 스스로 매긴 번호를 그대로 쓴다 — control_notes_KR.tex 머리의
회차↔절 대응표에 있는 "제N강" 이 그것이고, 영문판은 같은 표의 첫 칸 숫자다.

여러 강의를 한 단위로 묶어 정리한 곳은 표의 한 행과 본문의 구분선 하나가 그
범위 전체를 맡는다.  그런 행에서는 범위의 끝 번호와 끝 날짜를 읽는다.

    국문표    제7$\sim$10강 & 2026.\,09.\,23 (수) $\sim$ 10.\,07 (수) & ...
              -> (10, 2026-10-07)   끝 날짜의 연도는 앞 날짜의 것
    영문표    7--10 & Wed, 23 Sep -- Wed, 7 Oct 2026 & ...
              -> (10, 2026-10-07)   연도는 줄 끝의 것
    구분선    \lecturebreak{제7$\sim$10강}{2026년 9월 23일$\sim$10월 7일}
              -> (10, 2026-10-07)

단일 강의 행(제6강 & 2026.\,09.\,21 ..., 6 & Mon, 21 Sep 2026 & ...,
\lecturebreak{제6강}{2026년 9월 21일})도 그대로 읽는다.

본문의 \lecturebreak 구분선도 같은 표와 대조한다.  구분선 하나가 여러 강의를
맡을 수 있으므로 개수는 세지 않고, 마지막 구분선의 (끝 번호, 끝 날짜) 가 회차표
마지막 행의 (끝 번호, 끝 날짜) 와 같은지만 본다.  어긋나면 stderr 로 경고만 내고,
찍는 값과 종료 코드는 건드리지 않는다.

표를 못 읽으면 아무것도 찍지 않고 1 로 끝낸다 — publish.sh 는 그때
lectures 필드를 빼고 나머지 manifest 를 정상으로 만든다.  배포를 깨뜨리지
않는 것이 우선이다.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KO = os.path.join(HERE, "control_notes_KR.tex")
EN = os.path.join(HERE, "control_notes_EN.tex")

MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

# 국문판:  제6강 & 2026.\,09.\,21 (월) & ...
#          제7$\sim$10강 & 2026.\,09.\,23 (수) $\sim$ 10.\,07 (수) & ...
# 그룹: 시작 번호, 끝 번호?, 연, 월, 일, 끝 월?, 끝 일?
KO_ROW = re.compile(
    r"^[ \t]*제\s*(\d+)(?:\s*\$\\sim\$\s*(\d+))?\s*강\s*&"
    r"\s*(\d{4})\.\s*\\,\s*(\d{1,2})\.\s*\\,\s*(\d{1,2})"
    r"(?:\s*\([^)&]*\))?"
    r"(?:\s*\$\\sim\$\s*(\d{1,2})\.\s*\\,\s*(\d{1,2}))?", re.M)
# 국문판 본문:  \lecturebreak{제6강}{2026년 9월 21일}
#              \lecturebreak{제7$\sim$10강}{2026년 9월 23일$\sim$10월 7일}
# 그룹: 시작 번호, 끝 번호?, 연, 월, 일, 끝 월?, 끝 일?
KO_BREAK = re.compile(
    r"\\lecturebreak\{\s*제\s*(\d+)(?:\s*\$\\sim\$\s*(\d+))?\s*강\s*\}"
    r"\s*\{\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"
    r"(?:\s*\$\\sim\$\s*(?:(\d{1,2})월\s*)?(\d{1,2})일)?\s*\}")
# 영문판:  6 & Mon, 21 Sep 2026 & ...
#          7--10 & Wed, 23 Sep -- Wed, 7 Oct 2026 & ...
# 그룹: 시작 번호, 끝 번호?, 일, 월, 끝 일?, 끝 월?, 연
EN_ROW = re.compile(
    r"^[ \t]*(\d+)(?:\s*--\s*(\d+))?\s*&"
    r"\s*\w{3},\s*(\d{1,2})\s+([A-Z][a-z]{2})\w*"
    r"(?:\s*--\s*\w{3},\s*(\d{1,2})\s+([A-Z][a-z]{2})\w*)?"
    r"\s+(\d{4})\s*&", re.M)


def ko_end(m):
    """국문 회차표 행이나 구분선 하나 -> (끝 번호, 끝 날짜 ISO)."""
    n0, n1, y, mm, dd, emm, edd = m
    n = int(n1 or n0)
    if edd:
        mm, dd = (emm or mm), edd
    return n, "%04d-%02d-%02d" % (int(y), int(mm), int(dd))


def warn(msg):
    sys.stderr.write("!! lectures.py: %s\n" % msg)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_ko():
    rows = KO_ROW.findall(read(KO))
    if not rows:
        return None
    return ko_end(rows[-1])


def parse_en():
    rows = EN_ROW.findall(read(EN))
    if not rows:
        return None
    n0, n1, dd, mon, edd, emon, y = rows[-1]
    if edd:
        dd, mon = edd, emon
    if mon not in MONTHS:
        return None
    return int(n1 or n0), "%04d-%02d-%02d" % (int(y), MONTHS[mon], int(dd))


def check_ko_breaks(ko):
    """국문판 본문의 \\lecturebreak 들을 머리의 회차표와 대조해 경고만 낸다."""
    try:
        src = read(KO)
    except OSError as e:
        warn("국문판을 다시 읽지 못해 구분선 대조를 건너뜁니다: %s" % e)
        return
    breaks = KO_BREAK.findall(src)
    if not breaks:
        warn("국문판 본문에서 \\lecturebreak 를 찾지 못해 구분선 대조를 건너뜁니다.")
        return
    # 구분선 하나가 여러 강의를 맡을 수 있으므로 개수는 비교하지 않는다.
    last = ko_end(breaks[-1])
    if last != ko:
        warn("마지막 구분선 %r 이 회차표 마지막 행 %r 과 다릅니다." % (last, ko))


def main():
    try:
        ko = parse_ko()
    except OSError as e:
        warn("국문판을 읽지 못했습니다: %s" % e)
        return 1
    if ko is None:
        warn("control_notes_KR.tex 의 회차 대응표에서 '제N강' 행을 찾지 못했습니다 "
             "— lectures 필드를 뺍니다.")
        return 1

    # 영문판은 대조용이다.  어긋나도 배포는 멈추지 않고 국문판 값을 쓴다.
    try:
        en = parse_en()
    except OSError as e:
        en = None
        warn("영문판을 읽지 못해 대조를 건너뜁니다: %s" % e)
    if en is None:
        warn("control_notes_EN.tex 의 회차 대응표를 읽지 못해 대조를 건너뜁니다.")
    elif en != ko:
        warn("국문판과 영문판의 회차가 다릅니다 — ko=%r en=%r. 국문판 값을 씁니다."
             % (ko, en))

    check_ko_breaks(ko)

    sys.stdout.write('{"count":%d,"last":"%s"}\n' % ko)
    return 0


if __name__ == "__main__":
    sys.exit(main())
