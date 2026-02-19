import os

output_dir = 'outputs'
print(f"Listing directories in {output_dir} starting with '20260219':")
try:
    dirs = [d for d in os.listdir(output_dir) if d.startswith('20260219')]
    if not dirs:
        print("No matching directories found.")
    for d in dirs:
        print(d)
except FileNotFoundError:
    print(f"Directory {output_dir} not found.")
