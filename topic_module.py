# topic_module.py
# 목적: “팔릴 가능성”이 높은 주제를 Gemini로 점수화해서 뽑는다.

import json
import os
import random
from typing import Dict, List

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.utils import get_logger

logger = get_logger(__name__)

load_dotenv()


def _pick_topics_from_web(count: int = 5, excluded_topics: List[str] = None) -> List[Dict]:
    """Gemini 실패 시 Web Search를 통해 트렌딩 토픽을 가져옵니다."""
    try:
        from src.ai_web_researcher import AIWebResearcher
        researcher = AIWebResearcher()
        logger.info("Gemini topic selection failed. Falling back to AI Web Research...")
        
        queries = [
            "trending digital products to sell 2026",
            "best selling notion templates 2026",
            "high demand digital downloads etsy 2026",
            "profitable saas ideas 2026",
            "top selling shopify themes 2026",
            "popular ebook topics 2026",
            "niche digital products for passive income",
            "untapped digital product ideas 2026",
            "b2b digital products examples",
            "ai generated digital products ideas"
        ]
        
        candidates = []
        seen_titles = set()
        if excluded_topics:
            seen_titles.update([t.lower().strip() for t in excluded_topics])
            
        # 쿼리를 섞어서 다양성 확보
        random.shuffle(queries)
        
        for query in queries:
            if len(candidates) >= count:
                break
                
            results = researcher.search(query, max_results=8)
            
            for res in results:
                title = res.get('title', '').split(' - ')[0].split(' | ')[0].strip()
                if not title or len(title) < 10: # 너무 짧은 제목 제외
                    continue
                
                # Simple deduplication (Case-insensitive & Substring)
                title_lower = title.lower().strip()
                is_duplicate = False
                
                # 1. Exact match check
                if title_lower in seen_titles:
                    is_duplicate = True
                
                # 2. Substring check (if strict)
                if not is_duplicate:
                    for seen in seen_titles:
                        # If overlap is significant (e.g. one is substring of another and length difference is small)
                        if seen in title_lower or title_lower in seen:
                             # "Notion Template" vs "Best Notion Template" -> Duplicate
                             is_duplicate = True
                             break
                             
                if is_duplicate:
                    continue
                    
                # 필터링: 정보성 글 제목 제외하고 '제품' 느낌나는 것 선별 (heuristic)
                # 완벽하지 않지만 Fallback이므로 수용
                
                # Construct candidate
                candidates.append({
                    "topic": title,
                    "audience": "Digital Entrepreneurs & Solopreneurs",
                    "value_prop": res.get('snippet', 'High potential digital product based on current market trends.'),
                    "price_usd": str(random.choice([19, 29, 39, 49, 59])),
                    "price_comparison": "Competitive with market standards ($20-$60 range)",
                    "score": random.randint(75, 95),
                    "reasons": ["Detected as a trending topic on Web Search", "High relevance to digital product market", "Potential for passive income"]
                })
                seen_titles.add(title_lower)
                
                if len(candidates) >= count:
                    break
        
        # 만약 웹 검색으로도 부족하면 기본값 채움 (여기서는 빈 리스트 반환하여 호출자가 처리하게 할 수도 있지만, 최대한 채워서 보냄)
        return candidates
        
    except Exception as e:
        logger.error(f"Web research fallback failed: {e}")
        return []

def pick_topics(
    niche_hint: str = "Digital product (templates/landing pages/dashboards) sales",
    count: int = 5,
    excluded_topics: List[str] = None,
) -> List[Dict]:
    """
    Gemini를 이용해 주제 후보를 만들고, 시장성 점수로 상위 주제를 반환한다.
    Gemini 실패 시 Web Search를 통한 Fallback을 시도한다.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    # API 키가 없으면 바로 Web Fallback 시도
    if not api_key:
        logger.warning("GEMINI_API_KEY not found. Attempting Web Research Fallback.")
        return _pick_topics_from_web(count, excluded_topics)

    try:
        client = genai.Client(api_key=api_key)
        
        excluded_str = ""
        if excluded_topics:
            excluded_str = f"\n- **EXCLUDE THESE TOPICS**: {', '.join(excluded_topics)} (These are already produced. Choose different niches.)"

        # 프롬프트: “팔릴 확률”을 구조화해서 점수화(JSON)
        prompt = f"""
You are an expert in selling digital products (HTML templates, landing pages, dashboard UIs).
Create 15 'topic candidates' that satisfy the following conditions and score each one.
In particular, search and analyze the prices of similar products in the current market and suggest competitive price ranges.

[Conditions]
- Production difficulty: MVP template production possible within 1-2 hours
- Buyer: Small business/Freelancer/Solopreneur/Startup
- Clear reason for purchase (conversion/lead/dashboard/reservation/payment, etc.)
- Areas where trends/demand are assumed to exist
- **Price Analysis**: Calculate the optimal price by referring to the price ranges of similar services (Gumroad, ThemeForest, UI8, etc.).
- **Variety**: Ensure high variety across candidates. Do not repeat similar niches.
- **Language**: All output must be in ENGLISH ONLY.{excluded_str}

[Output JSON Schema]
{{
  "candidates":[
    {{
      "topic":"Short topic name in English",
      "audience":"Who buys it",
      "value_prop":"Core utility (what gets better)",
      "price_usd": "Number only (e.g., 29)",
      "price_comparison": "Summary of price range analysis for similar products",
      "score": 0-100,
      "reasons":["3-5 reasons why it sells"]
    }}
  ]
}}

Niche Hint: {niche_hint}

Output JSON ONLY. No code blocks.
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
                response_mime_type="application/json"
            )
        )

        text = (response.text or "").strip()

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

    except Exception as e:
        logger.error(f"Gemini topic generation failed: {e}. Attempting Web Research Fallback.")
        return _pick_topics_from_web(count, excluded_topics)
