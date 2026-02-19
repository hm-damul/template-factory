# topic_module.py
# 목적: “팔릴 가능성”이 높은 주제를 Gemini로 점수화해서 뽑는다.

import json
import os
from typing import Dict, List

from dotenv import load_dotenv
from google import genai

load_dotenv()


def pick_topics(
    niche_hint: str = "디지털 제품(템플릿/랜딩페이지/대시보드) 판매",
    count: int = 5,
) -> List[Dict]:
#     """
#     Gemini를 이용해 주제 후보를 만들고, 시장성 점수로 상위 주제를 반환한다.
#     반환 형식: [{topic, audience, value_prop, price_range, score, reasons[]}, ...]
#     """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 .env에 없습니다.")

    client = genai.Client(api_key=api_key)

    # 프롬프트: “팔릴 확률”을 구조화해서 점수화(JSON)
    prompt = f"""
너는 디지털 제품(HTML 템플릿/랜딩페이지/대시보드 UI)을 판매하는 전문가다.
아래 조건을 만족하는 '주제 후보'를 15개 만들고, 각각을 점수화해라.

[조건]
- 제작 난이도: 1~2시간 내 MVP 템플릿 제작 가능
- 구매자: 소규모 비즈니스/프리랜서/1인기업/스타트업
- 구매 이유가 명확(전환/리드/대시보드/예약/결제 등)
- 트렌드/수요가 존재한다고 가정할 수 있는 영역

[출력 JSON 스키마]
{{
  "candidates":[
    {{
      "topic":"짧은 주제명",
      "audience":"누가 사는가",
      "value_prop":"무엇이 좋아지는가(핵심 효용)",
      "price_range_usd":"예: 9~29",
      "score": 0~100,
      "reasons":["왜 팔리는지 3~5개 근거"]
    }}
  ]
}}

니치 힌트: {niche_hint}

JSON만 출력해라. 코드블록 금지.
"""

    res = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=prompt,
    )

    text = (res.text or "").strip()

    # JSON 파싱(깨졌을 때를 대비해 간단 복구)
    try:
        data = json.loads(text)
    except Exception:
        # 흔한 오류: 앞뒤에 잡문이 섞임 → 가장 바깥 {} 추출
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise RuntimeError("Gemini가 JSON을 반환하지 않았습니다:\n" + text)
        data = json.loads(text[start : end + 1])

    candidates = data.get("candidates", [])
    # score 기준 정렬
    candidates.sort(key=lambda x: int(x.get("score", 0)), reverse=True)

    # 상위 count개 반환
    return candidates[:count]
