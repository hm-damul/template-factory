
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from src.publisher import Publisher
from src.ledger_manager import LedgerManager

lm = LedgerManager("sqlite:///data/ledger.db")
pub = Publisher(lm)

product_id = "20260215-014951-automated-crypto-tax-reporting"
output_dir = Path(f"outputs/{product_id}").resolve()

print(f"Scanning {output_dir}...")
files = pub._collect_static_files(output_dir)

print(f"Found {len(files)} files.")
found_index = False
for f, c in files:
    if f == "index.html":
        found_index = True
        print(f"FOUND: {f} ({len(c)} bytes)")
    elif f.endswith(".html"):
        print(f"Other HTML: {f}")

if not found_index:
    print("ERROR: index.html NOT FOUND in collected files!")
else:
    print("SUCCESS: index.html is in the list.")
