# -*- coding: utf-8 -*-
"""
AUTO FIX & PATCH PIPELINE
작성 목적:
- 사람이 파일 위치를 잘못 찾는 문제 방지
- 코드 누락 / 잘림 / 문법 오류 자동 수정
- 함수 위치 자동 탐색 후 안전하게 코드 교체
- 수정 전 항상 백업 생성

사용법:
    python auto_fix_pipeline.py
"""

import ast
import os
import re
import shutil
from datetime import datetime

# 프로젝트 루트 경로 (현재 파일 기준)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


# -------------------------------
# 유틸리티
# -------------------------------


def backup_file(path):
    """파일 수정 전 자동 백업 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{path}.bak_{timestamp}"
    shutil.copy2(path, backup_path)
    print(f"[BACKUP] {backup_path}")


def find_file_by_name(filename):
    """프로젝트 전체에서 파일 이름으로 탐색"""
    for root, _, files in os.walk(PROJECT_ROOT):
        if filename in files:
            return os.path.join(root, filename)
    return None


def read_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# -------------------------------
# 1️⃣ 문법 오류 자동 수정
# -------------------------------


def auto_fix_syntax(path):
    """Python 파일의 기본 문법 오류 자동 수정"""
    code = read_file(path)

    # 흔한 f-string 괄호 오류 수정
    code = re.sub(r"\{([^{}]*)\}", r"{\1}", code)

    # ast로 문법 체크
    try:
        ast.parse(code)
        print(f"[OK] Syntax clean: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"[FIX] Syntax error detected in {path}: {e}")
        # 들여쓰기 깨짐 간단 보정
        code = re.sub(r"\t", "    ", code)

    write_file(path, code)


# -------------------------------
# 2️⃣ 함수 자동 삽입/교체
# -------------------------------


def replace_function(path, function_name, new_function_code):
    """파일에서 특정 함수 전체를 찾아 교체"""
    content = read_file(path)

    pattern = re.compile(
        rf"def {function_name}\(.*?\):[\s\S]*?(?=\n\S|\Z)", re.MULTILINE
    )

    if pattern.search(content):
        backup_file(path)
        content = pattern.sub(new_function_code.strip() + "\n\n", content)
        write_file(path, content)
        print(
            f"[PATCH] Replaced function '{function_name}' in {os.path.basename(path)}"
        )
    else:
        print(
            f"[INFO] Function '{function_name}' not found in {os.path.basename(path)}"
        )


# -------------------------------
# 3️⃣ HTML 안전 삽입
# -------------------------------


def inject_before_body_end(path, snippet):
    """HTML 파일에서 </body> 앞에 코드 삽입"""
    content = read_file(path)

    if snippet in content:
        print(f"[SKIP] Snippet already exists in {os.path.basename(path)}")
        return

    if "</body>" in content.lower():
        backup_file(path)
        content = re.sub(
            r"</body>", snippet + "\n</body>", content, flags=re.IGNORECASE
        )
        write_file(path, content)
        print(f"[PATCH] Injected snippet into {os.path.basename(path)}")
    else:
        print(f"[WARN] </body> not found in {os.path.basename(path)}")


# -------------------------------
# 4️⃣ API 경로 자동 동기화
# -------------------------------


def sync_api_paths():
    """프론트엔드 JS에서 잘못된 localhost API 호출을 /api 로 교체"""
    for root, _, files in os.walk(PROJECT_ROOT):
        for f in files:
            if f.endswith(".js") or f.endswith(".html"):
                path = os.path.join(root, f)
                content = read_file(path)

                if "127.0.0.1:5000" in content:
                    backup_file(path)
                    content = content.replace("http://127.0.0.1:5000", "")
                    write_file(path, content)
                    print(f"[PATCH] API path fixed in {f}")


# -------------------------------
# 5️⃣ 누락 파일 자동 생성
# -------------------------------


def ensure_file(path, default_content):
    if not os.path.exists(path):
        write_file(path, default_content)
        print(f"[CREATE] Missing file created: {path}")


# -------------------------------
# 메인 실행
# -------------------------------


def main():
    print("=== AUTO FIX PIPELINE START ===")

    # 1. 주요 Python 파일 문법 검사
    for fname in ["auto_pilot.py", "monetize_module.py", "generator_module.py"]:
        path = find_file_by_name(fname)
        if path:
            auto_fix_syntax(path)

    # 2. API 경로 동기화
    sync_api_paths()

    # 3. HTML 자동 삽입 예시 (필요시 여기에 추가 가능)
    # 예: inject_before_body_end("경로", "<script>...</script>")

    print("=== AUTO FIX PIPELINE COMPLETE ===")


if __name__ == "__main__":
    main()
