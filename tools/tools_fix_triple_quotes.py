# tools_fix_triple_quotes.py
# 프로젝트 전체에서 "독스트링 위치가 아닌" 삼중따옴표 블록(특히 한국어 설명)을 찾아 주석으로 바꿉니다.

import os  # 폴더 탐색용
import re  # 정규식 탐색용
from pathlib import Path  # 경로 처리용


def has_hangul(text: str) -> bool:
    # 한글(가-힣)이 포함되어 있으면 True
    return re.search(r"[가-힣]", text) is not None


def is_def_or_class_line(line: str) -> bool:
    # def / class 라인인지 대충 판별(정교 파싱이 아니라 실무용 휴리스틱)
    s = line.strip()
    return s.startswith("def ") or s.startswith("class ")


def find_prev_meaningful_line(lines: list[str], idx: int) -> str:
    # idx 위로 올라가며 공백/주석만 아닌 "의미 있는 줄"을 찾음
    j = idx - 1
    while j >= 0:
        t = lines[j].strip()
        if t == "" or t.startswith("#"):
            j -= 1
            continue
        return lines[j]
    return ""


def fix_file(path: Path) -> bool:
    # 파일 하나를 읽어 삼중따옴표 블록을 주석화하고 수정 여부를 반환
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines(True)  # 줄바꿈 포함

    changed = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # 삼중따옴표 시작 후보: 줄 시작(공백 이후)에서 """ 또는 ''' 로 시작하는 경우
        if stripped.startswith('"""') or stripped.startswith("'''"):
            quote = '"""' if stripped.startswith('"""') else "'''"

            # 이 줄이 "정상 독스트링"인지 판별:
            # - 파일 최상단(첫 의미있는 줄)
            # - def/class 바로 아래
            prev = find_prev_meaningful_line(lines, i)
            prev_is_defclass = is_def_or_class_line(prev)

            # 파일 최상단 의미 있는 줄인지 판별
            # (위로 공백/주석만 있는 상태면 모듈 독스트링 가능)
            top_prev = prev.strip() == ""
            # 위 함수는 의미 있는 줄을 반환하므로, prev == ""면 최상단에 가까움
            module_docstring_candidate = (prev.strip() == "")

            # 블록의 끝을 찾기(같은 따옴표로 닫히는 줄)
            block_start = i
            block_end = None

            # 한 줄짜리 """...""" 인지 먼저 체크
            if stripped.count(quote) >= 2:
                block_end = i
            else:
                # 여러 줄 블록: 닫는 따옴표가 나올 때까지 탐색
                j = i + 1
                while j < len(lines):
                    if quote in lines[j]:
                        block_end = j
                        break
                    j += 1

            # 닫힘을 못 찾으면 건너뜀(깨진 문자열일 수 있음)
            if block_end is None:
                i += 1
                continue

            block_text = "".join(lines[block_start:block_end + 1])

            # "정상 독스트링"이면 그대로 둠
            if prev_is_defclass or module_docstring_candidate:
                i = block_end + 1
                continue

            # 사용자가 원하는 정책에 맞게, 독스트링 위치가 아닌 블록은 주석화
            # 다만 실수 방지를 위해 '한글 포함' 블록만 강제 주석화(템플릿 문자열 보호 목적)
            if has_hangul(block_text):
                # 블록 전체를 한 줄씩 주석으로 변환
                new_block = []
                for k in range(block_start, block_end + 1):
                    # 원래 줄 끝 개행은 유지하면서, 앞에 "# " 추가
                    # 이미 주석이면 그대로
                    if lines[k].lstrip().startswith("#"):
                        new_block.append(lines[k])
                    else:
                        new_block.append("# " + lines[k])
                lines[block_start:block_end + 1] = new_block
                changed = True

                # 변경 후 인덱스 진행
                i = block_end + 1
                continue

        i += 1

    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def main():
    # 프로젝트 루트(현재 작업 폴더)를 기준으로 전체 .py 파일을 탐색
    root = Path(".").resolve()

    # 수정된 파일 목록
    modified = []

    for p in root.rglob("*.py"):
        # venv, site-packages 등은 제외(원하면 추가 제외 가능)
        if "\\venv\\" in str(p) or "\\.venv\\" in str(p):
            continue

        try:
            if fix_file(p):
                modified.append(str(p))
        except Exception:
            # 특정 파일 인코딩/권한 문제는 넘어감
            pass

    print("=== Done ===")
    print("Modified files:")
    for m in modified:
        print(m)


if __name__ == "__main__":
    main()
