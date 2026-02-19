# -*- coding: utf-8 -*-
"""
auto_pilot.py
- 목적: "템플릿 생성 → 결제/다운로드 로직 자동 주입 → 미리보기 URL 출력" E2E 실행 스크립트

- 전제(서버 2개는 별도 터미널에서 실행 중):
  1) Preview Server: python preview_server.py  (8088)
  2) Payment Server: python backend/payment_server.py  (5000)

- 동작:
  1) generator_module 을 동적으로 import하여 가능한 생성 함수를 찾아 실행
  2) outputs/<product_id>/index.html 생성 (또는 이미 있으면 유지)
  3) monetize_module 로 결제 위젯+스크립트를 index.html에 주입
  4) 미리보기 링크 안내 (/_open 사용 가능)

- 주의:
  - generator_module 내부 함수명이 환경마다 다를 수 있어, 자동 탐지 로직을 넣어둠
  - 탐지 실패 시 최소 HTML을 만들어 outputs에 저장하도록 fallback 제공
"""

from __future__ import annotations

import importlib  # 동적 import
import json  # 보고서 저장
import os  # 경로 처리
import re  # slugify
import time  # run id 생성
from typing import Callable, Optional  # 타입 힌트

from monetize_module import MonetizeModule, PaymentInjectConfig  # 결제 주입 모듈


def _now_run_id() -> str:
    """runs/ 폴더 등에 쓸 수 있는 run_id 문자열 생성."""
    return time.strftime("%Y%m%d-%H%M%S")


def _slugify(text: str) -> str:
    """파일/폴더명에 쓰기 좋은 slug 생성."""
    text = text.strip().lower()
    # 공백/특수문자를 - 로 변경
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "product"


def _ensure_dir(path: str) -> None:
    """폴더가 없으면 생성."""
    os.makedirs(path, exist_ok=True)


def _write_text(path: str, content: str) -> None:
    """텍스트 파일 저장(UTF-8)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _load_generator_callable() -> Optional[Callable[..., str]]:
    """
    generator_module에서 템플릿 생성 함수를 최대한 자동 탐지한다.
    예상 가능한 함수/클래스 후보를 넓게 잡는다.

    반환:
      - callable(topic: str, out_dir: str|None, product_id: str|None, ...) -> str(html)
      - 못 찾으면 None
    """
    try:
        mod = importlib.import_module("generator_module")
    except Exception as e:
        print(f"[auto_pilot] WARN: generator_module import failed: {e}")
        return None

    # 1) 가장 흔한 함수명 후보들
    fn_candidates = [
        "generate_template",
        "generate",
        "build",
        "create",
        "make",
        "make_template",
    ]

    for name in fn_candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            print(f"[auto_pilot] generator callable found: generator_module.{name}()")
            return fn

    # 2) 클래스 후보: TemplateFactory 같은 팩토리 패턴
    class_candidates = [
        "TemplateFactory",
        "CATPBrain",
    ]
    for cname in class_candidates:
        cls = getattr(mod, cname, None)
        if cls is None:
            continue
        try:
            obj = cls()  # 기본 생성자 가정
        except Exception:
            continue
        # 클래스 내부 메서드 후보들
        for mname in fn_candidates:
            m = getattr(obj, mname, None)
            if callable(m):
                print(f"[auto_pilot] generator callable found: {cname}().{mname}()")
                return m

    print(
        "[auto_pilot] WARN: No generator callable found in generator_module. Fallback HTML will be used."
    )
    return None


def _fallback_html(topic: str, product_id: str) -> str:
    """generator를 못 찾았을 때라도 테스트가 가능하도록 최소 HTML 생성."""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{product_id} · {topic}</title>
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 24px;">
  <h1 style="margin: 0 0 10px 0;">{topic}</h1>
  <p style="opacity: 0.8;">이 페이지는 generator_module 탐지 실패 시 fallback으로 생성되었습니다.</p>
  <hr style="margin: 18px 0;" />
  <p>아래에 결제/다운로드 위젯이 자동으로 주입됩니다.</p>
</body>
</html>
"""


def main() -> int:
    """
    E2E 실행:
      - outputs/<product_id>/index.html 생성/확인
      - 결제 위젯 주입
      - 미리보기 URL 출력
    """
    project_root = os.path.abspath(os.path.dirname(__file__))

    # ----- 사용자가 원하는 기본 타겟(요청서 기준) -----
    # 실제 운영에서는 이 topics를 트렌드 분석 결과로 대체 가능
    topic = "Web3 Crypto Template"
    product_id = "crypto-template-001"

    # outputs 폴더 구성
    outputs_dir = os.path.join(project_root, "outputs")
    out_dir = os.path.join(outputs_dir, product_id)
    _ensure_dir(out_dir)

    target_html_path = os.path.join(out_dir, "index.html")

    # 다운로드로 제공할 파일 경로(테스트용)
    # 여기서 반드시 "존재하는 파일"로 지정해야 한다.
    # 예: 패키지 zip 또는 pdf
    # 아래는 예시이므로, 당신의 실제 파일 위치로 수정해도 된다.
    # 단, 지금 단계에서는 "바로 동작"이 목적이므로, 우선 존재하는 파일로 설정해야 한다.
    download_file_path_candidates = [
        os.path.join(project_root, "products", "final", product_id, "package.zip"),
        os.path.join(project_root, "products", "final", product_id, "product.pdf"),
    ]

    download_file_path = None
    for p in download_file_path_candidates:
        if os.path.exists(p):
            download_file_path = p
            break

    if not download_file_path:
        # 후보 경로에 파일이 없으면, 사용자에게 명확히 안내하고 종료
        print("[auto_pilot] ERROR: 다운로드 파일을 찾지 못했습니다.")
        print("[auto_pilot] 다음 중 하나가 존재해야 합니다:")
        for p in download_file_path_candidates:
            print(f" - {p}")
        print(
            "[auto_pilot] 위 경로에 package.zip 또는 product.pdf를 준비한 뒤 다시 실행하세요."
        )
        return 2

    # ----- 1) 템플릿 생성 단계 -----
    generator_fn = _load_generator_callable()

    if generator_fn:
        try:
            # 가능한 다양한 시그니처를 흡수하기 위해 kwargs를 유연하게 시도
            # (generator_module 구현체가 다를 수 있기 때문)
            html = None

            # 1차 시도: (topic)만 받는 경우
            try:
                html = generator_fn(topic)  # type: ignore
            except TypeError:
                html = None

            # 2차 시도: (topic, out_dir=...) 패턴
            if html is None:
                try:
                    html = generator_fn(topic, out_dir=out_dir)  # type: ignore
                except TypeError:
                    html = None

            # 3차 시도: (topic, product_id=...) 패턴
            if html is None:
                try:
                    html = generator_fn(topic, product_id=product_id)  # type: ignore
                except TypeError:
                    html = None

            # 4차 시도: (topic, out_dir=..., product_id=...)
            if html is None:
                try:
                    html = generator_fn(topic, out_dir=out_dir, product_id=product_id)  # type: ignore
                except TypeError:
                    html = None

            # 다 실패하면 fallback
            if not isinstance(html, str) or not html.strip():
                html = _fallback_html(topic=topic, product_id=product_id)

        except Exception as e:
            print(
                f"[auto_pilot] WARN: generator failed, fallback will be used. err={e}"
            )
            html = _fallback_html(topic=topic, product_id=product_id)
    else:
        # generator를 못 찾으면 fallback
        html = _fallback_html(topic=topic, product_id=product_id)

    # 생성 HTML 저장
    _write_text(target_html_path, html)
    print(f"[auto_pilot] OK: base HTML ready -> {target_html_path}")

    # ----- 2) 결제/다운로드 주입 단계 -----
    monetizer = MonetizeModule()
    cfg = PaymentInjectConfig(
        product_id=product_id,
        download_file_path=download_file_path,
        payment_api_base="http://127.0.0.1:5000",
        button_text="결제하고 다운로드",
        amount_krw=9900,
    )

    try:
        monetizer.inject_payment_logic(target_html_path=target_html_path, config=cfg)
        print("[auto_pilot] OK: payment widget injected into index.html")
    except Exception as e:
        print(f"[auto_pilot] ERROR: payment injection failed: {e}")
        return 3

    # ----- 3) 보고서 저장(선택) -----
    runs_dir = os.path.join(project_root, "runs")
    _ensure_dir(runs_dir)

    run_id = _now_run_id() + f"-{product_id}"
    report_path = os.path.join(runs_dir, run_id, "report.json")
    _ensure_dir(os.path.dirname(report_path))

    report = {
        "run_id": run_id,
        "product_id": product_id,
        "topic": topic,
        "target_html_path": target_html_path,
        "download_file_path": download_file_path,
        "preview_list_url": "http://127.0.0.1:8088/_list",
        "preview_open_url_hint": "http://127.0.0.1:8088/_open/index.html (index.html 여러 개면 선택 화면이 뜸)",
        "payment_health_url": "http://127.0.0.1:5000/health",
    }

    _write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[auto_pilot] OK: report saved -> {report_path}")

    # ----- 4) 사용자 액션 안내(링크 출력) -----
    print("\n========== NEXT ACTIONS ==========")
    print("1) (터미널1) Preview Server 실행:")
    print('   cd "C:\\Users\\us090\\MetaPassiveIncome"')
    print("   python preview_server.py")
    print("   -> http://127.0.0.1:8088/_list")

    print("\n2) (터미널2) Payment Server 실행:")
    print('   cd "C:\\Users\\us090\\MetaPassiveIncome"')
    print("   python backend/payment_server.py")
    print("   -> http://127.0.0.1:5000/health")

    print("\n3) (터미널3) Auto Pilot 실행:")
    print('   cd "C:\\Users\\us090\\MetaPassiveIncome"')
    print("   python auto_pilot.py")

    print("\n4) 브라우저에서 확인:")
    print("   - 리스트: http://127.0.0.1:8088/_list")
    print("   - 열기(경로 무관): http://127.0.0.1:8088/_open/index.html")
    print("   - 결제 버튼 클릭 → 상태 paid → 다운로드 링크 활성화")
    print("=================================\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
