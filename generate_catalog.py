import os
import json
import glob
from pathlib import Path

OUTPUTS_DIR = Path("d:/auto/MetaPassiveIncome_FINAL/outputs")
PUBLIC_DIR = Path("d:/auto/MetaPassiveIncome_FINAL/public")
PUBLIC_INDEX = PUBLIC_DIR / "index.html"

def load_products():
    products = []
    # Find all product_schema.json files
    schema_files = glob.glob(str(OUTPUTS_DIR / "*/product_schema.json"))
    
    print(f"Found {len(schema_files)} products...")
    
    for schema_file in schema_files:
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            product_id = data.get("product_id")
            if not product_id:
                # Fallback to folder name
                product_id = Path(schema_file).parent.name
            
            # Check if index.html exists
            index_path = Path(schema_file).parent / "index.html"
            if not index_path.exists():
                print(f"Skipping {product_id}: No index.html")
                continue
                
            # Extract info
            title = data.get("title", "Untitled Product")
            desc = data.get("value_proposition") or data.get("sections", {}).get("hero", {}).get("subheadline", "")
            price = data.get("sections", {}).get("pricing", {}).get("price", "$0.00")
            
            # Try to find a cover image
            cover_img = "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?auto=format&fit=crop&q=80&w=2000"
            assets_cover = Path(schema_file).parent / "assets" / "cover.jpg"
            if assets_cover.exists():
                # We can't link to D:/... directly.
                # In Vercel, outputs/ID/assets/cover.jpg is accessible.
                cover_img = f"/outputs/{product_id}/assets/cover.jpg"
            
            products.append({
                "id": product_id,
                "title": title,
                "desc": desc,
                "price": price,
                "image": cover_img,
                "link": f"/outputs/{product_id}/index.html",
                "date": product_id.split("-")[0] # approximate date from ID
            })
        except Exception as e:
            print(f"Error loading {schema_file}: {e}")
            
    # Sort by date descending (newest first)
    products.sort(key=lambda x: x["id"], reverse=True)
    return products

def generate_html(products):
    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MetaPassiveIncome | Digital Product Catalog</title>
  <meta name="description" content="Browse our collection of premium digital products, templates, and tools." />
  <style>
    :root {
      --bg: #070b12;
      --panel: rgba(255,255,255,0.06);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --accent: #8b5cf6;
      --accent2: #00b4ff;
      --line: rgba(255,255,255,0.12);
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 20px;
    }
    header {
      text-align: center;
      margin-bottom: 60px;
    }
    h1 {
      font-size: 3rem;
      margin: 0 0 16px 0;
      background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    p.sub {
      font-size: 1.2rem;
      color: var(--muted);
      max-width: 600px;
      margin: 0 auto;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 30px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s;
      display: flex;
      flex-direction: column;
    }
    .card:hover {
      transform: translateY(-4px);
      box-shadow: 0 20px 40px rgba(0,0,0,0.4);
      border-color: var(--accent);
    }
    .card-img {
      height: 180px;
      background-size: cover;
      background-position: center;
      background-color: #222;
    }
    .card-body {
      padding: 20px;
      flex: 1;
      display: flex;
      flex-direction: column;
    }
    .card h3 {
      margin: 0 0 10px 0;
      font-size: 1.2rem;
      line-height: 1.3;
    }
    .card p {
      margin: 0 0 20px 0;
      font-size: 0.95rem;
      color: var(--muted);
      flex: 1;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: auto;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }
    .price {
      font-weight: 700;
      font-size: 1.1rem;
      color: var(--accent2);
    }
    .btn {
      display: inline-block;
      padding: 8px 16px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.9rem;
      transition: background 0.2s;
    }
    .btn:hover {
      background: #7c3aed;
    }
    .search-bar {
      margin-bottom: 40px;
      display: flex;
      justify-content: center;
    }
    .search-input {
      width: 100%;
      max-width: 500px;
      padding: 12px 20px;
      border-radius: 50px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.1);
      color: white;
      font-size: 1rem;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--accent);
      background: rgba(255,255,255,0.15);
    }
    footer {
      text-align: center;
      margin-top: 80px;
      padding-top: 40px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.9rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Digital Products Catalog</h1>
      <p class="sub">Discover premium tools, templates, and guides to accelerate your growth.</p>
    </header>
    
    <div class="search-bar">
      <input type="text" class="search-input" placeholder="Search products..." id="searchInput">
    </div>

    <div class="grid" id="productGrid">
      <!-- Products -->
      {products_html}
    </div>
    
    <footer>
      <p>&copy; 2026 MetaPassiveIncome. All rights reserved.</p>
    </footer>
  </div>

  <script>
    const searchInput = document.getElementById('searchInput');
    const grid = document.getElementById('productGrid');
    const cards = document.querySelectorAll('.card');

    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase();
      cards.forEach(card => {
        const title = card.querySelector('h3').textContent.toLowerCase();
        const desc = card.querySelector('p').textContent.toLowerCase();
        if (title.includes(term) || desc.includes(term)) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    });
  </script>
</body>
</html>
"""
    
    products_html = ""
    for p in products:
        products_html += f"""
        <div class="card">
            <div class="card-img" style="background-image: url('{p['image']}')"></div>
            <div class="card-body">
                <h3>{p['title']}</h3>
                <p>{p['desc']}</p>
                <div class="card-footer">
                    <div class="price">{p['price']}</div>
                    <a href="{p['link']}" class="btn">View Details</a>
                </div>
            </div>
        </div>
        """
    
    return html_template.replace("{products_html}", products_html)

def main():
    if not OUTPUTS_DIR.exists():
        print("Outputs directory not found!")
        return

    products = load_products()
    print(f"Loaded {len(products)} valid products.")
    
    html = generate_html(products)
    
    # Backup existing index.html if it exists and is not a catalog
    if PUBLIC_INDEX.exists():
        with open(PUBLIC_INDEX, "r", encoding="utf-8") as f:
            content = f.read()
            if "Digital Product Catalog" not in content:
                print("Backing up existing index.html to featured.html...")
                backup_path = PUBLIC_DIR / "featured.html"
                with open(backup_path, "w", encoding="utf-8") as bf:
                    bf.write(content)
            else:
                print("Existing index.html is already a catalog. Overwriting...")

    with open(PUBLIC_INDEX, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Catalog generated at {PUBLIC_INDEX}")

if __name__ == "__main__":
    main()
