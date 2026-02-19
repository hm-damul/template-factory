
import json
import sys

try:
    with open('data/audit_report.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=== Broken Products ===")
    for item in data['details']:
        if item['type'] == 'product' and item['issues']:
            print(f"Product ID: {item['product_id']}")
            print(f"Status: {item['status']}")
            for issue in item['issues']:
                print(f"  - {issue}")
            print("-" * 20)
            
    print("\n=== Broken Promotions ===")
    for item in data['details']:
        if item['type'].startswith('promotion') and item['issues']:
            print(f"Product ID: {item['product_id']}")
            print(f"Type: {item['type']}")
            for issue in item['issues']:
                print(f"  - {issue}")
            print("-" * 20)
            
except Exception as e:
    print(e)
