# quality_module.py
# 목적: 생성된 HTML을 “체크리스트 기반 점수(JSON)”로 평가하고 개선 지시를 만든다.

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from google import genai

load_dotenv()


def evaluate_html_quality(html: str) -> Dict[str, Any]:
    """
    Gemini로 HTML 품질 평가(JSON)를 수행한다.
    반환 예:
    {
      "score": 0~100,
      "checks": {...},
      "issues":[...],
      "fix_instructions":[...]
    }
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 .env에 없습니다.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
너는 “웹 템플릿 상품 QA”다.
아래 HTML을 평가해서 점수와 개선 지시를 JSON으로만 출력해라.

[평가 기준(각 0~10)]
- visual_design: 시각적 완성도/여백/타이포
- mobile_responsive: 모바일 반응형
- copywriting: 카피/혜택 전달/설득력
- conversion_cta: CTA 명확성/버튼/폼 구성
- trust_elements: 신뢰요소(FAQ, 후기, 보안/환불 등)
- seo_structure: title/meta/heading 구조
- performance: 불필요한 무거운 요소 최소화
- accessibility: 대비/aria/키보드 탐색 등 기본

[출력 JSON 스키마]
{{
  "score": 0~100,
  "subscores": {{
    "visual_design":0~10,
    "mobile_responsive":0~10,
    "copywriting":0~10,
    "conversion_cta":0~10,
    "trust_elements":0~10,
    "seo_structure":0~10,
    "performance":0~10,
    "accessibility":0~10
  }},
  "issues":[
    "문제점 5~10개"
  ],
  "fix_instructions":[
    "개선 지시 5~12개 (HTML에 바로 반영 가능한 수준으로 구체)"
  ]
}}

JSON만 출력. 코드블록 금지.

[HTML]
{html}
# """
# 
#     res = client.models.generate_content(
#         model="gemini-flash-latest",
#         contents=prompt,
#     )
# 
#     text = (res.text or "").strip()
# 
#     try:
#         return json.loads(text)
#     except Exception:
#         start = text.find("{")
#         end = text.rfind("}")
#         if start == -1 or end == -1:
#             raise RuntimeError("Gemini 품질평가 JSON 파싱 실패:\n" + text)
#         return json.loads(text[start : end + 1])
# 
# 
# def improve_html_with_instructions(html: str, fix_instructions: list) -> str:
#     """
#     개선 지시를 바탕으로 HTML을 리라이트한다.
#     """
#     api_key = os.getenv("GEMINI_API_KEY", "").strip()
#     if not api_key:
#         raise RuntimeError("GEMINI_API_KEY가 .env에 없습니다.")
# 
#     client = genai.Client(api_key=api_key)
# 
#     instructions_text = "\n".join([f"- {x}" for x in fix_instructions])
# 
#     prompt = f"""
# 너는 프론트엔드 템플릿 리라이터다.
# 아래 HTML에 대해 '개선 지시'를 반영해 품질을 높여라.
# 
# [개선 지시]
# {instructions_text}
# 
# [요구사항]
# - 단일 HTML 파일 유지
# - 외부 라이브러리 최소화
# - 모바일 반응형 강화
# - CTA/FAQ/신뢰요소 강화
# - SEO(title/meta/heading) 개선
# - 결과는 "HTML 전체"만 출력 (코드블록 금지)
# 
# [원본 HTML]
# {html}
# """
# 
#     res = client.models.generate_content(
#         model="models/gemini-2.5-flash",
#         contents=prompt,
#     )
# 
#     return (res.text or "").strip()
