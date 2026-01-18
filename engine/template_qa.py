#!/usr/bin/env python3
"""
template_qa.py - Quality assurance checks for generated templates

This module performs:
- HTML structure linting
- Print layout validation
- Duplication detection (similar content)
- Accessibility checks (alt text, headings)
- Size and completeness checks

Input: generated/templates/*.html, generated/products/*.json
Output: generated/qa/report.json, updates product state
"""

import os
import json
import re
import hashlib
from datetime import datetime
from collections import defaultdict

PRODUCT_DIR = "generated/products"
TEMPLATE_DIR = "generated/templates"
OUT_DIR = "generated/qa"
REPORT_FILE = f"{OUT_DIR}/report.json"


class QAChecker:
    """Quality assurance checker for templates."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_failed = 0
    
    def add_issue(self, severity: str, code: str, message: str, details: dict = None):
        item = {"severity": severity, "code": code, "message": message}
        if details:
            item["details"] = details
        if severity == "error":
            self.issues.append(item)
            self.checks_failed += 1
        else:
            self.warnings.append(item)
        
    def check_pass(self):
        self.checks_passed += 1
    
    def get_result(self) -> dict:
        return {
            "passed": self.checks_passed,
            "failed": self.checks_failed,
            "issues": self.issues,
            "warnings": self.warnings,
            "status": "pass" if self.checks_failed == 0 else "fail"
        }


def lint_html_structure(html: str, checker: QAChecker):
    """Check HTML structure for common issues."""
    
    # Check DOCTYPE
    if not html.strip().lower().startswith("<!doctype html"):
        checker.add_issue("error", "MISSING_DOCTYPE", "Missing DOCTYPE declaration")
    else:
        checker.check_pass()
    
    # Check essential elements
    required_tags = ["<html", "<head>", "<title>", "<body>", "</html>", "</body>"]
    for tag in required_tags:
        if tag.lower() not in html.lower():
            checker.add_issue("error", "MISSING_TAG", f"Missing required tag: {tag}")
        else:
            checker.check_pass()
    
    # Check meta charset
    if 'charset="utf-8"' not in html.lower() and "charset=utf-8" not in html.lower():
        checker.add_issue("warning", "MISSING_CHARSET", "Missing UTF-8 charset declaration")
    else:
        checker.check_pass()
    
    # Check for empty title
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        if not title_match.group(1).strip():
            checker.add_issue("error", "EMPTY_TITLE", "Empty title tag")
        else:
            checker.check_pass()
    
    # Check heading hierarchy
    h1_count = len(re.findall(r"<h1[\s>]", html, re.IGNORECASE))
    if h1_count == 0:
        checker.add_issue("warning", "NO_H1", "No H1 heading found")
    elif h1_count > 1:
        checker.add_issue("warning", "MULTIPLE_H1", f"Multiple H1 headings found ({h1_count})")
    else:
        checker.check_pass()


def check_print_layout(html: str, checker: QAChecker):
    """Check print-specific layout issues."""
    
    # Check for print media query
    if "@media print" in html:
        checker.check_pass()
    else:
        checker.add_issue("warning", "NO_PRINT_STYLES", "No print-specific styles found")
    
    # Check for reasonable content length
    content_length = len(html)
    if content_length < 1000:
        checker.add_issue("warning", "SHORT_CONTENT", 
                         f"Template content seems short ({content_length} chars)")
    elif content_length > 100000:
        checker.add_issue("warning", "LONG_CONTENT", 
                         f"Template content is very long ({content_length} chars)")
    else:
        checker.check_pass()
    
    # Check for tables (expected in templates)
    if "<table" in html.lower():
        checker.check_pass()
        
        # Check table has headers
        if "<th" not in html.lower():
            checker.add_issue("warning", "TABLE_NO_HEADERS", "Table found without header cells")
    else:
        checker.add_issue("warning", "NO_TABLE", "No table element found in template")


def check_accessibility(html: str, checker: QAChecker):
    """Check basic accessibility requirements."""
    
    # Check for lang attribute
    if re.search(r'<html[^>]*lang=', html, re.IGNORECASE):
        checker.check_pass()
    else:
        checker.add_issue("warning", "NO_LANG", "Missing lang attribute on html element")
    
    # Check images have alt text
    images = re.findall(r"<img[^>]*>", html, re.IGNORECASE)
    for img in images:
        if 'alt=' not in img.lower():
            checker.add_issue("warning", "IMG_NO_ALT", "Image missing alt attribute", 
                            {"tag": img[:50]})
        else:
            checker.check_pass()
    
    # Check for skip-to-content or main landmark
    if "<main" in html.lower() or 'role="main"' in html.lower():
        checker.check_pass()
    else:
        checker.add_issue("info", "NO_MAIN", "No main element or role found")


def compute_content_hash(html: str) -> str:
    """Compute hash of template content for duplication detection."""
    # Remove dynamic content (timestamps, IDs)
    cleaned = re.sub(r"Generated:.*?<", "<", html)
    cleaned = re.sub(r"ID:.*?·", "", cleaned)
    cleaned = re.sub(r"[a-f0-9]{10}", "", cleaned)  # Remove hash-like IDs
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return hashlib.md5(cleaned.encode()).hexdigest()


def check_duplicates(templates: dict) -> list:
    """Find templates with similar content."""
    hash_groups = defaultdict(list)
    
    for pid, data in templates.items():
        content_hash = data.get("content_hash", "")
        if content_hash:
            hash_groups[content_hash].append(pid)
    
    duplicates = []
    for hash_val, pids in hash_groups.items():
        if len(pids) > 1:
            duplicates.append({
                "hash": hash_val,
                "templates": pids,
                "count": len(pids)
            })
    
    return duplicates


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  Template QA")
    print("=" * 50)
    
    if not os.path.exists(TEMPLATE_DIR):
        print("ERROR: Template directory not found")
        return
    
    results = {}
    templates_data = {}
    total_passed = 0
    total_failed = 0
    qa_passed = 0
    qa_failed = 0
    
    # Check each template
    for fn in os.listdir(TEMPLATE_DIR):
        if not fn.endswith(".html"):
            continue
        
        pid = fn.replace(".html", "")
        template_path = f"{TEMPLATE_DIR}/{fn}"
        
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                html = f.read()
            
            checker = QAChecker()
            
            # Run checks
            lint_html_structure(html, checker)
            check_print_layout(html, checker)
            check_accessibility(html, checker)
            
            result = checker.get_result()
            result["template_id"] = pid
            result["file"] = template_path
            result["size_bytes"] = len(html.encode('utf-8'))
            
            # Compute content hash for duplication check
            content_hash = compute_content_hash(html)
            result["content_hash"] = content_hash
            templates_data[pid] = {"content_hash": content_hash}
            
            results[pid] = result
            total_passed += result["passed"]
            total_failed += result["failed"]
            
            if result["status"] == "pass":
                qa_passed += 1
                print(f"✓ {pid}: {result['passed']} checks passed")
            else:
                qa_failed += 1
                print(f"✗ {pid}: {result['failed']} issues found")
            
            # Update product state if QA failed
            product_path = f"{PRODUCT_DIR}/{pid}.json"
            if os.path.exists(product_path):
                with open(product_path, "r", encoding="utf-8") as f:
                    product = json.load(f)
                
                product["qa_status"] = result["status"]
                product["qa_issues"] = len(result["issues"])
                product["qa_warnings"] = len(result["warnings"])
                
                # Don't reject on warnings, only on errors
                if result["failed"] > 0 and result["issues"]:
                    product["state"] = "QA_FAILED"
                
                with open(product_path, "w", encoding="utf-8") as f:
                    json.dump(product, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            results[pid] = {
                "template_id": pid,
                "status": "error",
                "error": str(e)
            }
            qa_failed += 1
            print(f"✗ {pid}: Error - {e}")
    
    # Check for duplicates
    duplicates = check_duplicates(templates_data)
    if duplicates:
        print(f"\n⚠ Found {len(duplicates)} groups of similar templates")
    
    # Write report
    report = {
        "step": "template_qa",
        "timestamp": ts,
        "summary": {
            "templates_checked": len(results),
            "qa_passed": qa_passed,
            "qa_failed": qa_failed,
            "total_checks_passed": total_passed,
            "total_checks_failed": total_failed,
            "duplicate_groups": len(duplicates)
        },
        "duplicates": duplicates,
        "results": results
    }
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"qa_passed={qa_passed} qa_failed={qa_failed} duplicates={len(duplicates)}")
    print(f"report={REPORT_FILE}")
    
    # Exit with error if any critical failures
    if qa_failed > 0:
        print("\n⚠ Some templates failed QA checks")


if __name__ == "__main__":
    main()
