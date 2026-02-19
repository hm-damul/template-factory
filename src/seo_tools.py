import re
from collections import Counter
from typing import List

class SEOManager:
    """
    Simple SEO tool to extract keywords and generate tags from text.
    Does not require heavy NLP libraries to ensure compatibility.
    """
    
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "that", "this", "these", "those", "it", "its", "from", "by", "as", "at", "your", "we", "us",
        "can", "will", "should", "could", "would", "if", "then", "else", "when", "where", "why", "how",
        "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
    }

    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> List[str]:
        """
        Extracts top N keywords from the provided text.
        """
        if not text:
            return []
            
        # 1. Normalize text: lowercase and remove non-alphanumeric chars
        text = text.lower()
        # Replace non-word characters with spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        # 2. Tokenize
        words = text.split()
        
        # 3. Filter stop words and short words
        filtered_words = [
            w for w in words 
            if w not in SEOManager.STOP_WORDS and len(w) > 2
        ]
        
        # 4. Count frequency
        counter = Counter(filtered_words)
        
        # 5. Return top N
        return [word for word, count in counter.most_common(top_n)]

    @staticmethod
    def generate_tags(title: str, description: str, max_tags: int = 5) -> List[str]:
        """
        Generates tags based on title and description.
        Title keywords are weighted higher.
        """
        # Extract from title (high priority)
        title_keywords = SEOManager.extract_keywords(title, top_n=max_tags)
        
        # Extract from description (fill remaining)
        desc_keywords = SEOManager.extract_keywords(description, top_n=max_tags)
        
        # Combine, preserving order and uniqueness
        tags = []
        seen = set()
        
        for k in title_keywords + desc_keywords:
            if k not in seen:
                tags.append(k)
                seen.add(k)
                if len(tags) >= max_tags:
                    break
                    
        return tags

    @staticmethod
    def analyze_seo_score(title: str, content: str) -> dict:
        """
        Analyzes the SEO quality of the title and content.
        Returns a score (0-100) and feedback.
        """
        score = 100
        feedback = []
        
        # 1. Title Length (Ideal: 30-60 chars)
        if len(title) < 30:
            score -= 10
            feedback.append("Title is too short (aim for 30-60 chars)")
        elif len(title) > 60:
            score -= 10
            feedback.append("Title is too long (aim for 30-60 chars)")
            
        # 2. Content Length (Ideal: > 300 words)
        word_count = len(content.split())
        if word_count < 300:
            score -= 20
            feedback.append(f"Content is too short ({word_count} words). Aim for 300+ words.")
            
        # 3. Keyword presence in title
        keywords = SEOManager.extract_keywords(content, top_n=5)
        if keywords and not any(k in title.lower() for k in keywords):
            score -= 10
            feedback.append("Title does not contain top keywords from content.")
            
        return {
            "score": max(0, score),
            "feedback": feedback
        }

if __name__ == "__main__":
    # Test
    sample_title = "Automated Crypto Trading Bot with Python"
    sample_desc = """
    This project provides a full-stack automated trading solution using Python and Binance API.
    It includes real-time data analysis, backtesting, and secure API key management.
    Perfect for passive income generation.
    """
    
    print("Keywords:", SEOManager.extract_keywords(sample_desc))
    print("Tags:", SEOManager.generate_tags(sample_title, sample_desc))
