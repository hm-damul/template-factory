# -*- coding: utf-8 -*-
"""
ai_web_researcher.py

AI가 웹을 통해 실시간 정보를 수집하고 분석하는 모듈입니다.
DuckDuckGo HTML 검색을 통해 검색 결과를 수집하고,
페이지 콘텐츠를 추출하여 AI 프롬프트에 컨텍스트로 제공합니다.
"""

import time
import random
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from .utils import get_logger, ProductionError

logger = get_logger(__name__)

class AIWebResearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def search(self, query: str, max_results: int = 5) -> list:
        """
        Uses duckduckgo_search library for robust search results.
        Falls back to HTML scraping if library fails.
        """
        results = []
        
        # Method 1: Try duckduckgo_search library (Preferred)
        # Retry logic for rate limits (429)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Web Searching (DDGS) [Attempt {attempt+1}/{max_retries}]: {query}")
                with DDGS() as ddgs:
                    ddgs_gen = ddgs.text(query, max_results=max_results)
                    for r in ddgs_gen:
                        results.append({
                            "title": r.get('title', ''),
                            "link": r.get('href', ''),
                            "snippet": r.get('body', '')
                        })
                
                if results:
                    return results
                
                # If no results but no error, break to fallback
                break
                    
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Too Many Requests" in error_str:
                    wait_time = (attempt + 1) * 10 + random.uniform(2, 5) # Progressive backoff: 10s, 20s, 30s
                    logger.warning(f"DDGS Rate limit hit (429). Waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"DDGS library search failed: {e}. Falling back to HTML scraping.")
                    break # Non-rate-limit error, try fallback immediately

        # Method 2: Fallback to HTML Scraping
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            logger.info(f"Web Searching (Fallback): {query}")
            time.sleep(random.uniform(1.0, 2.0))
            
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a', class_='result__a', limit=max_results)
            
            for link in links:
                title = link.get_text(strip=True)
                href = link.get('href')
                # Snippet extraction from HTML is tricky, try to find next sibling or parent's sibling
                snippet = ""
                
                if href:
                    results.append({
                        "title": title,
                        "link": href,
                        "snippet": snippet
                    })
            
            if not results:
                logger.warning(f"No results found (Fallback) for: {query}")
                
            return results

        except Exception as e:
            logger.error(f"Web search failed completely for '{query}': {e}")
            return []

    def fetch_page_content(self, url: str, max_chars: int = 3000) -> str:
        """
        URL의 본문 텍스트를 추출합니다.
        """
        try:
            logger.info(f"Fetching content from: {url}")
            time.sleep(random.uniform(0.5, 1.0))
            
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.extract()
            
            # Get text
            text = soup.get_text(separator='\n', strip=True)
            
            # Basic cleaning
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = '\n'.join(lines)
            
            return cleaned_text[:max_chars]
            
        except Exception as e:
            logger.warning(f"Failed to fetch content from {url}: {e}")
            return ""

    def research_topic_trends(self, topic: str) -> str:
        """
        토픽에 대한 최신 트렌드를 검색하고 요약 컨텍스트를 반환합니다.
        """
        search_query = f"{topic} trends 2025 market analysis"
        results = self.search(search_query, max_results=3)
        
        context_parts = []
        for res in results:
            content = self.fetch_page_content(res['link'], max_chars=1500)
            if content:
                context_parts.append(f"Source: {res['title']} ({res['link']})\nContent:\n{content}\n---")
        
        if not context_parts:
            return "No web research data available."
            
        return "\n".join(context_parts)

    def check_visibility(self, keyword: str, target_url_substring: str) -> dict:
        """
        특정 키워드로 검색했을 때 대상 URL이 노출되는지 확인합니다.
        """
        results = self.search(keyword, max_results=20)
        found_rank = -1
        found_entry = None
        
        for idx, res in enumerate(results):
            if target_url_substring in res['link']:
                found_rank = idx + 1
                found_entry = res
                break
        
        return {
            "keyword": keyword,
            "visible": found_rank != -1,
            "rank": found_rank,
            "entry": found_entry
        }

# Global instance
web_researcher = AIWebResearcher()
