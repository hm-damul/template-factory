import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.key_manager import apply_keys


def main() -> int:
    before, after = apply_keys(project_root, write=True, inject=True)
    print("=== KEY MANAGER SUMMARY ===")
    print(f"- project_root: {project_root}")
    print(f"- before_count: {len(before)}")
    print(f"- after_count: {len(after)}")
    missing = [k for k in sorted(set(after.keys())) if not after.get(k)]
    if missing:
        print(f"- missing_values ({len(missing)}): {', '.join(missing)}")
    else:
        print("- missing_values: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
