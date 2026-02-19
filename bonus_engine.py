# -*- coding: utf-8 -*-
"""
bonus_engine.py

목적:
- 상품별 보너스 패키지를 자동 생성하여 zip으로 묶는다.
- 언어별 보너스(프롬프트/이메일/매크로/숏폼/FAQ/워크시트/캘린더) 제공.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def _write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _prompt_library(topic: str, n: int = 100) -> str:
    items = []
    for i in range(1, n + 1):
        items.append(
            f"{i:03d}. ({topic}) 실전 실행 프롬프트: 목표/대상/제약/출력형식을 명확히 하고 결과를 체크리스트로 산출하라."
        )
    return "# Prompt Library (100+)\\n\\n" + "\\n".join(items) + "\\n"


def _email_templates(topic: str) -> str:
    return f"""# Email Templates\\n\\n## 1) 런치 안내\\n- 제목: [{topic}] 출시 안내\\n- 본문: (문제→해결→증거→CTA) 구조로 180~220자\\n\\n## 2) 리마인드\\n- 제목: [{topic}] 마감 전 리마인드\\n- 본문: 혜택 3개 + 마감 시각 + CTA\\n\\n## 3) 후기 요청\\n- 제목: [{topic}] 사용 후기를 부탁드립니다\\n- 본문: 3문항 설문 + 답장 요청\\n"""


def _support_macros(topic: str) -> str:
    return """# Support Macros\\n\\n## 결제 확인 지연\\n- 고객님, 결제 네트워크 확인 중입니다. 10~20분 내 반영됩니다.\\n\\n## 다운로드 토큰 만료\\n- 재다운로드 링크를 재발급해 드렸습니다.\\n\\n## 사용 방법 문의\\n- Quick Start를 따라 1)설치 2)설정 3)실행 순으로 진행해 주세요.\\n"""


def _short_scripts(topic: str) -> str:
    return f"""# Short-form Scripts\\n\\n## 15초 훅\\n- “{topic} 때문에 매달 X를 잃고 있다면…”\\n\\n## 30초 구조\\n- 문제(5초) → 해결(10초) → 증거(10초) → CTA(5초)\\n\\n## 60초 구조\\n- Before/After + 데모 포인트 3개 + CTA\\n"""


def _pricing_faq(topic: str) -> str:
    return """# Pricing & FAQ Blocks\\n\\n## 가격 앵커\\n- 기본: $19\\n- 프로: $49 (보너스 + 업데이트)\\n- 번들: $99\\n\\n## FAQ\\n1) 결제는 어떤 코인을 지원하나요? (NOWPayments 기준)\\n2) 환불 정책은?\\n3) 재다운로드는?\\n"""


def _worksheets(topic: str) -> str:
    return """# Worksheets\\n\\n## 목표 정의\\n- 목표 KPI: ____\\n- 현재 수치: ____\\n- 30일 목표: ____\\n\\n## 실행 계획\\n- 주간 작업 5개: ____\\n\\n## 리스크\\n- 상위 리스크 3개와 대응: ____\\n"""


def _promo_calendar(topic: str) -> str:
    lines = ["# 30-day Promotion Calendar\\n"]
    for d in range(1, 31):
        lines.append(f"- Day {d:02d}: {topic} 관련 1포인트 콘텐츠(훅→핵심→CTA) 게시")
    return "\\n".join(lines) + "\\n"


def generate_bonus_pack(output_dir: Path, topic: str, lang: str = "en") -> Path:
    bonus_dir = output_dir / "bonuses" / lang
    bonus_dir.mkdir(parents=True, exist_ok=True)

    _write(
        bonus_dir / "execution_checklist.md",
        "# Execution Checklist\\n\\n- [ ] 목표 정의\\n- [ ] 환경 세팅\\n- [ ] 실행\\n- [ ] 검증\\n- [ ] 개선\\n",
    )
    _write(bonus_dir / "prompt_library.md", _prompt_library(topic, 100))
    _write(bonus_dir / "email_templates.md", _email_templates(topic))
    _write(bonus_dir / "support_macros.md", _support_macros(topic))
    _write(bonus_dir / "short_scripts.md", _short_scripts(topic))
    _write(bonus_dir / "pricing_faq.md", _pricing_faq(topic))
    _write(bonus_dir / "worksheets.md", _worksheets(topic))
    _write(bonus_dir / "promotion_calendar.md", _promo_calendar(topic))

    zip_path = output_dir / f"bonus_{lang}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in bonus_dir.rglob("*"):
            if p.is_file():
                z.write(p, arcname=str(p.relative_to(output_dir)))
    return zip_path
