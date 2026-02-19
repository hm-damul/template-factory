# patch_validate.py
# 목적: generator_module.py 안의 _validate_html()를 "줄 시작 코드펜스만 차단" 버전으로 강제 교체

import os  # 파일 경로 처리
import re  # 정규식으로 함수 블록 찾기/교체

# 현재 폴더의 generator_module.py를 대상으로 함
TARGET = os.path.join(os.getcwd(), "generator_module.py")

# 파일 존재 확인
if not os.path.exists(TARGET):
    raise SystemExit(f"[ERROR] generator_module.py not found at: {TARGET}")

# 원본 읽기
with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

# 교체할 새 _validate_html 함수 (이 블록을 그대로 파일에 넣음)
new_func = r'''
def _validate_html(html: str) -> None:
    """
    배포 실패/버튼 미동작을 유발하는 요소를 강제 검증.
    - 문장 속 기호는 허용
    - "줄 시작 코드펜스" 형태만 차단 (진짜 마크다운 래핑 가능성)
    """
    # 줄 시작에 ``` 가 나오면 차단
    if re.search(r"(^|\n)\s*```", html):
        raise RuntimeError("Generated HTML appears to contain markdown code fences at line start (```), aborting.")

    # 최소 골격 체크
    must_have = ["<!doctype html>", "<html", "<head", "<body", "</html>"]
    lower = html.lower()
    for token in must_have:
        if token not in lower:
            raise RuntimeError(f"Generated HTML missing required token: {token}")
'''.lstrip("\n")

# 기존 _validate_html 함수 블록을 정규식으로 찾기
pattern = r"def _validate_html\s*\(.*?\)\s*:\s*\n(?:[ \t].*\n)+"

m = re.search(pattern, src)
if not m:
    raise SystemExit(
        "[ERROR] Could not find _validate_html() function block to replace."
    )

# 교체 실행
patched = src[: m.start()] + new_func + src[m.end() :]

# 혹시 구버전 에러 문구가 파일에 남아 있으면(다른 곳에 텍스트로 있을 수도 있음) 제거/무해화
patched = patched.replace(
    'raise RuntimeError("Generated HTML contains markdown code fences (```), which breaks Vercel rendering. Aborting.")',
    'raise RuntimeError("Generated HTML appears to contain markdown code fences at line start (```), aborting.")',
)

# 백업 파일 생성
backup = TARGET + ".bak"
with open(backup, "w", encoding="utf-8") as f:
    f.write(src)

# 패치 파일 저장
with open(TARGET, "w", encoding="utf-8") as f:
    f.write(patched)

print("[OK] Patched _validate_html() in generator_module.py")
print("[OK] Backup created:", backup)
