
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

try:
    from image_analyzer import ImageAnalyzer
    print("ImageAnalyzer imported successfully.")
    
    analyzer = ImageAnalyzer()
    print(f"ImageAnalyzer initialized. Client available: {analyzer.client is not None}")
    
    if analyzer.client:
        print("Gemini client is ready.")
    else:
        print("Gemini client is NOT ready (API key missing?).")

except Exception as e:
    print(f"Error: {e}")
