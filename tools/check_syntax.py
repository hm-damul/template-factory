import compileall
import sys
import os

root_dir = os.getcwd()
print(f"Checking syntax in {root_dir}...")

# List of directories to check
dirs = ["api", "backend", "src", "."]

has_error = False

for d in dirs:
    path = os.path.join(root_dir, d)
    if os.path.exists(path):
        print(f"Checking {d}...")
        if not compileall.compile_dir(path, quiet=1):
            has_error = True
            print(f"Syntax error found in {d}")
        else:
            print(f"{d} OK")

if has_error:
    sys.exit(1)
else:
    sys.exit(0)
