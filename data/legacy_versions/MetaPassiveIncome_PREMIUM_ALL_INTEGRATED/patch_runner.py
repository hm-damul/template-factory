# -*- coding: utf-8 -*-
"""
AI PATCH RUNNER
패치 명령(JSON)을 읽어 프로젝트 파일을 자동 수정하는 시스템

사용법:
1) patches 폴더에 패치 파일(.json) 넣기
2) python patch_runner.py 실행
"""

import json
import os
import shutil
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PATCH_DIR = os.path.join(PROJECT_ROOT, "patches")


# -------------------------------
# 유틸
# -------------------------------


def backup_file(path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{path}.bak_{timestamp}"
    shutil.copy2(path, backup_path)
    print(f"[BACKUP] {backup_path}")


def find_file(filename):
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
# 패치 적용 로직
# -------------------------------


def apply_patch(patch):
    """패치 적용 엔진(업그레이드 버전)

    지원 action:
      - replace_function: 파일 내 함수 블록 교체
      - insert_before: anchor 앞에 코드 삽입
      - replace_text: 텍스트 치환
      - create_file: 파일 생성/덮어쓰기
      - grep_project: 프로젝트 전체에서 키워드 탐색(파일/라인 출력)

    주의:
      - 모든 변경은 백업 후 수행
      - 파일은 PROJECT_ROOT 기준으로 탐색
    """

    import os

    action = patch.get("action")

    # ---- 1) create_file: 새 파일 생성/덮어쓰기 ----
    if action == "create_file":
        rel_path = patch.get("path")
        content = patch.get("content", "")
        if not rel_path:
            print("[ERROR] create_file requires path")
            return

        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # 기존 파일이 있으면 백업
        if os.path.exists(abs_path):
            backup_file(abs_path)

        write_file(abs_path, content)
        print(f"[CREATE] File written: {rel_path}")
        return

    # ---- 2) grep_project: 프로젝트 전체 키워드 스캔 ----
    if action == "grep_project":
        keywords = patch.get("keywords") or []
        exts = patch.get("exts") or [".py", ".html", ".js", ".json", ".md"]
        max_hits = int(patch.get("max_hits") or 200)

        if not keywords:
            print("[ERROR] grep_project requires keywords")
            return

        hits = []
        for root, _, files in os.walk(PROJECT_ROOT):
            for fn in files:
                if not any(fn.lower().endswith(e) for e in exts):
                    continue
                fp = os.path.join(root, fn)
                try:
                    text = read_file(fp)
                except Exception:
                    continue

                lines = text.splitlines()
                for i, line in enumerate(lines, start=1):
                    for kw in keywords:
                        if kw and kw in line:
                            rel = os.path.relpath(fp, PROJECT_ROOT)
                            hits.append((rel, i, line.strip()))
                            if len(hits) >= max_hits:
                                break
                    if len(hits) >= max_hits:
                        break
                if len(hits) >= max_hits:
                    break
            if len(hits) >= max_hits:
                break

        if not hits:
            print("[GREP] No hits found.")
            return

        print(f"[GREP] Found {len(hits)} hit(s):")
        for rel, ln, s in hits:
            print(f" - {rel}:{ln} | {s}")
        return

    # ---- 이하: 기존 3종 액션(파일 탐색 기반) ----
    filename = patch.get("file")
    if not filename:
        print("[ERROR] patch requires file field")
        return

    path = find_file(filename)
    if not path:
        print(f"[ERROR] File not found: {filename}")
        return

    content = read_file(path)

    # ---- replace_function ----
    if action == "replace_function":
        func_name = patch.get("function")
        new_code = patch.get("code", "")

        if not func_name or not new_code:
            print("[ERROR] replace_function requires function and code")
            return

        # 함수 시작점 찾기(정확도 향상: 라인 시작 def)
        marker = f"def {func_name}("
        start = content.find(marker)
        if start == -1:
            print(f"[SKIP] Function {func_name} not found in {filename}")
            return

        # 함수 끝점 찾기: 다음 최상위 def/class 또는 EOF
        rest = content[start:]
        end = None
        m = None
        # 다음 'def ' 또는 'class '가 줄 시작에서 등장하는 지점
        import re

        m = re.search(r"\n(def|class)\s+", rest)
        if m:
            end = start + m.start() + 1
        else:
            end = len(content)

        backup_file(path)
        updated = content[:start] + new_code.strip() + "\n\n" + content[end:]
        write_file(path, updated)
        print(f"[PATCH] Function replaced: {func_name} in {filename}")
        return

    # ---- insert_before ----
    if action == "insert_before":
        anchor = patch.get("anchor")
        snippet = patch.get("code", "")

        if not anchor or not snippet:
            print("[ERROR] insert_before requires anchor and code")
            return

        if snippet in content:
            print(f"[SKIP] Snippet already exists in {filename}")
            return

        if anchor not in content:
            print(f"[WARN] Anchor not found in {filename}: {anchor}")
            return

        backup_file(path)
        updated = content.replace(anchor, snippet + "\n" + anchor)
        write_file(path, updated)
        print(f"[PATCH] Inserted snippet before '{anchor}' in {filename}")
        return

    # ---- replace_text ----
    if action == "replace_text":
        old = patch.get("old", "")
        new = patch.get("new", "")

        if not old:
            print("[ERROR] replace_text requires old")
            return

        if old not in content:
            print(f"[SKIP] Text not found in {filename}")
            return

        backup_file(path)
        write_file(path, content.replace(old, new))
        print(f"[PATCH] Text replaced in {filename}")
        return

    print(f"[ERROR] Unknown action: {action}")


def main():
    if not os.path.exists(PATCH_DIR):
        print("[INFO] No patches folder found.")
        return

    files = [f for f in os.listdir(PATCH_DIR) if f.endswith(".json")]
    if not files:
        print("[INFO] No patch files found.")
        return

    print(f"=== APPLYING {len(files)} PATCH(ES) ===")

    for fname in files:
        path = os.path.join(PATCH_DIR, fname)
        print(f"\n[PATCH FILE] {fname}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            for patch in data:
                apply_patch(patch)
        else:
            apply_patch(data)

        # 적용 완료 후 패치 파일 이동
        done_dir = os.path.join(PATCH_DIR, "applied")
        os.makedirs(done_dir, exist_ok=True)
        shutil.move(path, os.path.join(done_dir, fname))

    print("\n=== PATCH COMPLETE ===")


if __name__ == "__main__":
    main()
