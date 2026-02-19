
import sys

def check_import(name):
    try:
        __import__(name)
        print(f"{name}: OK")
    except ImportError as e:
        print(f"{name}: FAIL - {e}")

print("Checking Generative AI libraries...")
check_import("google.genai")
# check_import("google.generativeai") # Legacy removed
print("Done.")
