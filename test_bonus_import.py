
try:
    from premium_bonus_generator import build_bonus_package
    print("SUCCESS: premium_bonus_generator imported successfully")
except Exception as e:
    print(f"FAILURE: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
