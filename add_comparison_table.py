
import os
import sys
import glob
import re
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.ledger_manager import LedgerManager
from src.config import Config

COMPARISON_TEMPLATE = """
<!-- ======= COMPARISON SECTION ======= -->
<section id="comparison" style="padding: 60px 0; background: #f9f9f9;">
  <div class="container" style="max-width: 800px; margin: 0 auto; padding: 0 20px;">
    <h2 style="text-align: center; margin-bottom: 40px; font-size: 2.5rem; color: #333;">Why Choose Us?</h2>
    <div style="overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden;">
        <thead>
          <tr style="background: #333; color: #fff;">
            <th style="padding: 15px; text-align: left;">Feature</th>
            <th style="padding: 15px; text-align: center; background: #0070f3;">Our Product</th>
            <th style="padding: 15px; text-align: center;">DIY (Do It Yourself)</th>
            <th style="padding: 15px; text-align: center;">Hiring an Agency</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 15px; font-weight: bold;">Cost</td>
            <td style="padding: 15px; text-align: center; color: #0070f3; font-weight: bold;">${price} (One-time)</td>
            <td style="padding: 15px; text-align: center;">Free (but hidden costs)</td>
            <td style="padding: 15px; text-align: center;">$500 - $2,000+</td>
          </tr>
          <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 15px; font-weight: bold;">Time to Value</td>
            <td style="padding: 15px; text-align: center; color: #0070f3; font-weight: bold;">Instant Download</td>
            <td style="padding: 15px; text-align: center;">Weeks or Months</td>
            <td style="padding: 15px; text-align: center;">2 - 4 Weeks</td>
          </tr>
          <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 15px; font-weight: bold;">Quality</td>
            <td style="padding: 15px; text-align: center; color: #0070f3; font-weight: bold;">Professional & Verified</td>
            <td style="padding: 15px; text-align: center;">Variable / Amateur</td>
            <td style="padding: 15px; text-align: center;">High (if lucky)</td>
          </tr>
          <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 15px; font-weight: bold;">Updates</td>
            <td style="padding: 15px; text-align: center; color: #0070f3; font-weight: bold;">Included</td>
            <td style="padding: 15px; text-align: center;">Manual</td>
            <td style="padding: 15px; text-align: center;">Paid Extra</td>
          </tr>
          <tr>
            <td style="padding: 15px; font-weight: bold;">Support</td>
            <td style="padding: 15px; text-align: center; color: #0070f3; font-weight: bold;">24/7 AI + Email</td>
            <td style="padding: 15px; text-align: center;">None</td>
            <td style="padding: 15px; text-align: center;">Business Hours Only</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
<!-- ======= END COMPARISON SECTION ======= -->
"""

def inject_comparison():
    lm = LedgerManager(Config.DATABASE_URL)
    files = glob.glob("outputs/*/index.html")
    print(f"Found {len(files)} index.html files.")
    
    count = 0
    for file_path in files:
        path_obj = Path(file_path)
        product_id = path_obj.parent.name
        
        # Get product info from DB for status check later
        p_info = lm.get_product(product_id)
        
        # Get price
        price_usd = 29.0  # Default fallback
        
        # [Priority 1] Try product_schema.json first (Source of Truth)
        schema_path = path_obj.parent / "product_schema.json"
        if schema_path.exists():
            try:
                s = json.loads(schema_path.read_text(encoding="utf-8"))
                # 1. Try pricing section
                p_val = s.get("sections", {}).get("pricing", {}).get("price", "")
                if p_val:
                    price_usd = float(p_val.replace('$', '').replace(',', ''))
                # 2. Fallback to market_analysis
                elif "market_analysis" in s:
                     p_val = s["market_analysis"].get("our_price")
                     if p_val:
                         price_usd = float(p_val)
            except Exception as e:
                print(f"Error reading schema for {product_id}: {e}")
        else:
            # [Priority 2] Fallback to DB
            if p_info:
                meta = p_info.get("metadata", {})
                if isinstance(meta, str):
                    try: meta = json.loads(meta)
                    except: meta = {}
                price_usd = float(meta.get("final_price_usd", 29.0))
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Prepare template with correct price
        section_html = COMPARISON_TEMPLATE.replace("${price}", f"${price_usd:.2f}")

        if "id=\"comparison\"" in content:
            print(f"[{product_id}] Comparison section already exists. Updating...")
            # Regex to replace existing comparison section
            # Assuming it starts with <!-- ======= COMPARISON SECTION ======= --> and ends with <!-- ======= END COMPARISON SECTION ======= -->
            pattern = r'<!-- ======= COMPARISON SECTION ======= -->.*?<!-- ======= END COMPARISON SECTION ======= -->'
            new_content = re.sub(pattern, section_html, content, flags=re.DOTALL)
            
            if new_content == content:
                 print(f"[{product_id}] Regex failed to match existing section. Appending new one (might duplicate if format changed).")
                 # Fallback to insertion logic if regex fails, but we need to be careful not to duplicate
                 # If regex failed but id="comparison" exists, maybe the comments are missing?
                 # Let's try to match by ID
                 pattern_id = r'<section id="comparison".*?</section>'
                 new_content = re.sub(pattern_id, section_html, content, flags=re.DOTALL)
            
            if new_content != content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"[{product_id}] Updated comparison section (Price: ${price_usd}).")
                count += 1
            continue
            
        # Inject before footer or FAQ
        # Priority: Before "Frequently Asked Questions" -> Before Footer -> End of Body
        
        insert_point = -1
        
        # 1. Try before FAQ
        faq_markers = ['<section id="faq"', 'id="faq"', '>Frequently Asked Questions<']
        for marker in faq_markers:
            idx = content.find(marker)
            if idx != -1:
                # Find the start of the section containing this marker if possible
                # But simple injection before the marker is usually safe if it's a section tag
                if marker.startswith('<section'):
                    insert_point = idx
                    break
                else:
                    # Search backwards for <section from this point? Too complex.
                    # Let's just look for <footer
                    pass

        # 2. Try before Footer
        if insert_point == -1:
            footer_idx = content.find('<footer')
            if footer_idx != -1:
                insert_point = footer_idx
        
        # 3. Fallback: Before </body>
        if insert_point == -1:
            insert_point = content.find('</body>')
            
        if insert_point != -1:
            # Prepare template with correct price
            section_html = COMPARISON_TEMPLATE.replace("${price}", f"${price_usd}")
            
            new_content = content[:insert_point] + section_html + "\n" + content[insert_point:]
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            print(f"[{product_id}] Injected comparison section (Price: ${price_usd}).")
            
            # Update product status to WAITING_FOR_DEPLOYMENT so daemon picks it up
            # Only if it was PUBLISHED or similar. If it's already waiting, no need.
            # But let's force update to be safe, or just rely on the user to ask for redeploy?
            # User said "make it run when bot activates".
            # The daemon picks up WAITING_FOR_DEPLOYMENT.
            if p_info and p_info['status'] == 'PUBLISHED':
                 lm.update_product_status(product_id, "WAITING_FOR_DEPLOYMENT")
                 print(f"  -> Status updated to WAITING_FOR_DEPLOYMENT")
            
            count += 1
        else:
            print(f"[{product_id}] Could not find insertion point.")

    print(f"Injected comparison table into {count} files.")

if __name__ == "__main__":
    inject_comparison()
