# -*- coding: utf-8 -*-
import json
import os
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import sys

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from promotion_factory import generate_promotions
from promotion_dispatcher import dispatch_publish

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def contains_korean(text: str) -> bool:
    return bool(re.search('[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', text))

def translate_to_english(text: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return text
    
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        # 더 강력하고 명확한 프롬프트 사용
        # 예시를 명확하게 주고, 한글이 포함된 문장을 영어로 바꿀 때 한글 단어의 의미를 영어로 번역하도록 지시
        prompt = f"""Task: Translate the following text into professional marketing English.
CRITICAL: YOUR RESPONSE MUST BE 100% ENGLISH ONLY.
DO NOT INCLUDE ANY KOREAN CHARACTERS IN YOUR OUTPUT.

Examples:
- Input: "Unlock Your Passive Income with AI 툴 베타" -> Output: "Unlock Your Passive Income with AI Tool Beta"
- Input: "개인 링크 인 바이오 (Link-in-Bio) 페이지" -> Output: "Personal Link-in-Bio Page"
- Input: "프리랜서/컨설턴트 서비스 소개 랜딩 페이지" -> Output: "Freelancer/Consultant Service Introduction Landing Page"

Now translate this text:
Input: {text}
English Output:"""
        
        response = client.models.generate_content(
                    model="gemini-pro-latest",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=150
                    )
                )
        
        translated = response.text.strip() if response.text else ""
        logger.info(f"Gemini Raw Translation: '{text}' -> '{translated}'")
        
        # Markdown backticks 및 불필요한 기호 제거
        translated = re.sub(r'```[a-z]*\n?', '', translated)
        translated = translated.replace('```', '').strip()
        translated = re.sub(r'["\']', '', translated) # 따옴표 제거
        
        # 2단계: 여전히 한글이 있으면 강제 제거
        if contains_korean(translated):
            # 한글 문자를 제거하기 전에 로그 출력
            logger.info(f"Regex removing Korean from: {translated}")
            translated = re.sub('[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', '', translated).strip()
        
        # 3단계: 연속된 공백 및 특수문자 정리
        translated = re.sub(r'\s+', ' ', translated)
        translated = re.sub(r'^[^\w]+|[^\w]+$', '', translated) # 앞뒤 특수문자 제거
        
        if not translated or len(translated) < 3:
            translated = "Premium Digital Asset"
            
        return translated
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        # 에러 발생 시 한글 제거 후 추가 정리하여 반환
        fallback = re.sub('[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', '', text).strip()
        fallback = re.sub(r'\s+', ' ', fallback)
        fallback = re.sub(r'^[^\w]+|[^\w]+$', '', fallback)
        return fallback or "Premium Asset"

def translate_all_strings(obj):
    """객체 내의 모든 문자열을 재귀적으로 번역한다."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = translate_all_strings(value)
    elif isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = translate_all_strings(obj[i])
    elif isinstance(obj, str):
        if contains_korean(obj):
            return translate_to_english(obj)
    return obj

def is_ugly_title(text: str) -> bool:
    """공백이 너무 많거나 특수문자만 남은 경우 등을 체크"""
    if not text: return True
    if "    " in text: return True
    if text.strip() == "/": return True
    if len(text.strip()) < 3: return True
    return False

def fix_korean_products():
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        logger.error("outputs directory not found.")
        return

    product_dirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    logger.info(f"Checking {len(product_dirs)} products...")

    for p_dir in product_dirs:
        product_id = p_dir.name
        manifest_path = p_dir / "manifest.json"
        schema_path = p_dir / "product_schema.json"
        
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                title = m.get("title", "")
                topic = m.get("topic", "")
                
                needs_update = False
                if contains_korean(title) or is_ugly_title(title):
                    m["title"] = translate_to_english(title)
                    needs_update = True
                
                if contains_korean(topic) or is_ugly_title(topic):
                    m["topic"] = translate_to_english(topic)
                    needs_update = True
                
                if needs_update:
                     # Clean up product_id if it has too many dashes
                     if "---" in m.get("product_id", ""):
                         m["product_id"] = re.sub(r'-+', '-', m["product_id"]).strip("-")
                     
                     manifest_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
                     logger.info(f"[{product_id}] Metadata fully translated and cleaned.")

                     # 3. 프로모션 재생성
                     new_title = m.get("title", "Premium Digital Asset")
                     new_topic = m.get("topic", "High Quality Template")
                     price_usd = m.get("metadata", {}).get("final_price_usd", 29.0)
                     
                     try:
                        generate_promotions(
                            product_dir=p_dir,
                            product_id=product_id,
                            title=new_title,
                            topic=new_topic,
                            price_usd=price_usd
                        )
                        logger.info(f"[{product_id}] Promotions regenerated in English.")
                     except Exception as e:
                        logger.error(f"[{product_id}] Promotion regeneration failed: {e}")
            except Exception as e:
                logger.error(f"[{product_id}] Error updating manifest: {e}")

if __name__ == "__main__":
    fix_korean_products()
