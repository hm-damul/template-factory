
import os
import sys

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

log_path = 'd:/auto/MetaPassiveIncome_FINAL/logs/product_factory.log'
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
        # Get count from command line if provided
        num_lines = 100
        if len(sys.argv) > 1:
            try:
                num_lines = int(sys.argv[1])
            except ValueError:
                pass
                
        for line in lines[-num_lines:]:
            print(line.strip())
else:
    print("Log file not found")
