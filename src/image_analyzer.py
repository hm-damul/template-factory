# -*- coding: utf-8 -*-
"""
image_analyzer.py

Uses Google Gemini Vision to analyze images for content, context, and quality.
Useful for validating generated images or analyzing competitor assets.
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from .utils import get_logger

logger = get_logger(__name__)

class ImageAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = "gemini-1.5-flash" # Use a fast, vision-capable model
        
        if HAS_GENAI and self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("Google GenAI not available or API key missing. Image analysis disabled.")

    def analyze_image(self, image_path_or_url: str, prompt: str = "Describe this image in detail.") -> Dict[str, Any]:
        """
        Analyzes an image using Gemini Vision.
        """
        if not HAS_GENAI or not self.api_key:
            return {"error": "GenAI not configured"}

        try:
            # Load image
            image_data = None
            if image_path_or_url.startswith("http"):
                # Download temp
                import requests
                from PIL import Image
                from io import BytesIO
                
                resp = requests.get(image_path_or_url, timeout=10)
                resp.raise_for_status()
                image_data = Image.open(BytesIO(resp.content))
            else:
                from PIL import Image
                if os.path.exists(image_path_or_url):
                    image_data = Image.open(image_path_or_url)
                else:
                    return {"error": "File not found"}

            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([prompt, image_data])
            
            return {
                "description": response.text,
                "metadata": response.usage_metadata if hasattr(response, "usage_metadata") else {}
            }

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"error": str(e)}

    def verify_product_image_quality(self, image_path: str) -> Dict[str, Any]:
        """
        Verifies if a product image is high quality and relevant.
        """
        prompt = """
        Analyze this product image. 
        1. Is it high quality/resolution?
        2. Is it professional looking?
        3. Describe the main subject.
        4. Give a score from 1-10 for e-commerce suitability.
        
        Output JSON:
        {
            "is_high_quality": bool,
            "is_professional": bool,
            "subject": "string",
            "score": int,
            "feedback": "string"
        }
        """
        result = self.analyze_image(image_path, prompt)
        # Parse JSON from text if needed, or just return text
        return result

image_analyzer = ImageAnalyzer()
