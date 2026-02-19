# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Any

class PromotionValidationResult:
    def __init__(self, passed: bool, score: float, feedback: List[str], schema_errors: List[str]):
        self.passed = passed
        self.score = score  # 0.0 to 1.0
        self.feedback = feedback
        self.schema_errors = schema_errors

    def to_dict(self):
        return {
            "passed": self.passed,
            "score": self.score,
            "feedback": self.feedback,
            "schema_errors": self.schema_errors
        }

class PromotionValidator:
    """워드프레스 홍보글의 품질 및 스키마를 검증하는 클래스 (SEO 및 전환 최적화)"""
    
    # 필수 섹션 정의 (9개 핵심 요소)
    REQUIRED_SECTIONS = {
        "H1_TITLE": r"^# .*",
        "META_DESCRIPTION": r"(?i)Meta Description:",
        "KEY_TAKEAWAYS": r"(?i)(Key Takeaways|Executive Summary)",
        "PROBLEM_STATEMENT": r"## .*",
        "SOLUTION_ARCHITECTURE": r"(##|###) .*",
        "VISUAL_PROOF": r"!\[.*?\]\(.*?\)",
        "FAQ_SECTION": r"(?i)(FAQ|Frequently Asked Questions)",
        "TRUST_SECURITY": r"(?i)(Trust|Security|Verified|Certainty|Risk-Free)",
        "CTA_CONVERSION": r"(?i)(Grab|Download|Buy|Join|Get Started|Link|🚀)"
    }
    
    # 판매 및 SEO 핵심 키워드 (가중치 부여 가능)
    SALES_KEYWORDS = [
        "instant", "deterministic", "secure", "privacy", "blueprint", 
        "automated", "revenue", "passive income", "exclusive", "limited",
        "conversion", "architecture", "fulfillment", "settlement",
        "turnkey", "scalability", "monetization", "edge", "advantage"
    ]

    @staticmethod
    def verify_image_links(content: str) -> List[str]:
        """
        Verifies that all images in the content are accessible.
        Returns a list of error messages for broken images.
        """
        import requests
        import os
        from pathlib import Path
        
        errors = []
        # Markdown images: ![alt](url "title") or ![alt](url)
        # Extract URL part, handling optional title
        md_matches = re.findall(r"!\[.*?\]\((.*?)\)", content)
        md_urls = []
        for m in md_matches:
            # url is the first part before space (if title exists)
            # e.g. "http://... "title""
            parts = m.split(maxsplit=1)
            if parts:
                md_urls.append(parts[0])

        # HTML images
        html_urls = re.findall(r'<img[^>]+src="([^">]+)"', content)
        
        all_images = set(md_urls + html_urls)
        
        for url in all_images:
            url = url.strip()
            if not url or url.startswith("data:"): 
                continue
            
            if url.startswith("http"):
                try:
                    # Fake user agent to avoid blocking
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                    r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                    if r.status_code >= 400:
                        # Some servers block HEAD, try GET with stream
                        r = requests.get(url, headers=headers, stream=True, timeout=5)
                        r.close()
                        if r.status_code >= 400:
                            errors.append(f"Broken image link: {url} (Status: {r.status_code})")
                except Exception as e:
                    errors.append(f"Error checking image {url}: {e}")
            else:
                # Local path
                # Handle absolute and relative paths
                if not os.path.exists(url):
                    # Check if it's relative to PROJECT_ROOT?
                    # We assume absolute paths or CWD relative
                    errors.append(f"Missing local image file: {url}")
                    
        return errors

    @staticmethod
    def validate_blog_post(content: str, title: str) -> PromotionValidationResult:
        feedback = []
        schema_errors = []
        score = 0.0
        
        if not content:
            return PromotionValidationResult(False, 0.0, ["Content is empty"], ["Empty content"])

        # 1. 스키마 구조 검증 (Structure & SEO)
        sections_found = {}
        for section_name, pattern in PromotionValidator.REQUIRED_SECTIONS.items():
            found = re.search(pattern, content)
            sections_found[section_name] = bool(found)
            if not found:
                schema_errors.append(f"Missing Section: {section_name.replace('_', ' ').title()}")

        # 제목 포함 여부 별도 체크
        if sections_found["H1_TITLE"] and f"# {title}" not in content and title.lower() not in content.lower():
            feedback.append("H1 Title exists but does not match product title closely.")

        # 이미지 및 Alt Text 심층 검사
        images = re.findall(r"!\[(.*?)\]\((.*?)\)", content)
        if images:
            alt_texts = [alt.strip() for alt, url in images if len(alt.strip()) > 5]
            if len(alt_texts) < len(images):
                schema_errors.append("Some images have weak or missing Alt Text (SEO impact).")
        
        # 2. 품질 및 가독성 점수 (Score Calculation)
        # 길이 (Length) - 1500자 이상 권장
        content_len = len(content)
        if content_len >= 2000: score += 0.3
        elif content_len >= 1500: score += 0.2
        elif content_len >= 1000: score += 0.1
        else: feedback.append(f"Content is too short ({content_len} chars). SEO performance may be limited.")

        # 키워드 밀도 (Keyword Density)
        found_keywords = [kw for kw in PromotionValidator.SALES_KEYWORDS if kw.lower() in content.lower()]
        keyword_ratio = len(found_keywords) / len(PromotionValidator.SALES_KEYWORDS)
        score += min(0.4, keyword_ratio * 0.5) # Max 0.4
        
        if keyword_ratio < 0.5:
            feedback.append(f"Low sales keyword density ({int(keyword_ratio*100)}%). Enhance persuasive language.")

        # 3. 전환 유도 (CTA Effectiveness)
        cta_patterns = [
            r"\[.*?\]\(https?://.*?\)", # Active Markdown links
            r"(?i)Grab (your|this) .* now",
            r"(?i)Instant access",
            r"(?i)Click (here|to get)",
            r"(?i)Get started (today|now)"
        ]
        cta_hits = sum(1 for pat in cta_patterns if re.search(pat, content))
        if cta_hits >= 2: score += 0.3
        elif cta_hits == 1: score += 0.15
        else: feedback.append("Weak CTA. No direct links or strong urgency detected.")

        # 4. 언어 및 정책 검증 (Policy)
        # 영문 전용 정책 (한글 포함 시 감점 및 오류)
        has_korean = any(0xAC00 <= ord(c) <= 0xD7A3 for c in content)
        if has_korean:
            schema_errors.append("Language Violation: Korean characters detected (English only required).")
            score = max(0.0, score - 0.5)

        # 최종 판정
        # 스키마 오류가 없고, 점수가 0.5 이상이어야 통과 (기존 0.7에서 완화, 짧은 글도 통과 가능하게)
        passed = (len(schema_errors) == 0) and (score >= 0.5)
        
        # 가점: 스키마가 완벽하고 키워드가 풍부하면 추가 점수
        if passed and keyword_ratio > 0.8:
            score = min(1.0, score + 0.1)

        return PromotionValidationResult(passed, round(score, 2), feedback, schema_errors)
