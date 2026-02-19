# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import base64
import json

from src.utils import get_logger

logger = get_logger(__name__)

class ImageAnalyzer:
    def __init__(self):
        try:
            from google import genai
            from google.genai import types
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.warning("GEMINI_API_KEY not found. Image analysis will be disabled.")
                self.client = None
            else:
                self.client = genai.Client(api_key=api_key)
        except ImportError:
            logger.warning("google-genai library not found. Install it with: pip install google-genai")
            self.client = None

    def analyze_image(self, image_path: str, prompt: str = "Analyze this image and describe its contents for a product description.") -> str:
        if not self.client:
            return "Image analysis unavailable: API key or library missing."
            
        path = Path(image_path)
        if not path.exists():
            return f"Image not found: {image_path}"
            
        try:
            # Read image
            with open(path, "rb") as f:
                image_bytes = f.read()
                
            # Call Gemini Vision
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=self._get_mime_type(path))
                ]
            )
            
            return response.text
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return f"Error analyzing image: {str(e)}"

    def _get_mime_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in ['.jpg', '.jpeg']: return 'image/jpeg'
        if suffix == '.png': return 'image/png'
        if suffix == '.webp': return 'image/webp'
        return 'image/jpeg' # Default

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python image_analyzer.py <image_path> [prompt]")
        sys.exit(1)
        
    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Describe this image."
    
    analyzer = ImageAnalyzer()
    print(analyzer.analyze_image(image_path, prompt))
