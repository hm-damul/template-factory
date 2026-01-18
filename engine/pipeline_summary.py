#!/usr/bin/env python3
"""
pipeline_summary.py - Generate final pipeline execution summary

This module collects all step summaries and creates a comprehensive report.

Input: generated/*/summary.json
Output: generated/pipeline_summary.json, output/pipeline_report.md
"""

import os
import json
import glob
from datetime import datetime

GENERATED_DIR = "generated"
OUTPUT_DIR = "output"
SUMMARY_FILE = f"{GENERATED_DIR}/pipeline_summary.json"
REPORT_FILE = f"{OUTPUT_DIR}/pipeline_report.md"


def collect_summaries() -> dict:
    """Collect all step summaries."""
    summaries = {}
    
    # Look for summary.json in all subdirectories
    for summary_path in glob.glob(f"{GENERATED_DIR}/**/summary.json", recursive=True):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            step = data.get("step", os.path.dirname(summary_path))
            summaries[step] = {
                "file": summary_path,
                "data": data
            }
        except Exception as e:
            print(f"Warning: Could not read {summary_path}: {e}")
    
    return summaries


def count_products() -> dict:
    """Count products by state."""
    product_dir = f"{GENERATED_DIR}/products"
    states = {}
    
    if os.path.exists(product_dir):
        for fn in os.listdir(product_dir):
            if fn.endswith(".json"):
                try:
                    with open(f"{product_dir}/{fn}", "r", encoding="utf-8") as f:
                        product = json.load(f)
                    state = product.get("state", "UNKNOWN")
                    states[state] = states.get(state, 0) + 1
                except:
                    pass
    
    return states


def count_files(directory: str) -> dict:
    """Count files by type in a directory."""
    counts = {}
    
    if os.path.exists(directory):
        for fn in os.listdir(directory):
            ext = os.path.splitext(fn)[1].lower() or "no_ext"
            counts[ext] = counts.get(ext, 0) + 1
    
    return counts


def generate_report(summaries: dict, product_states: dict, ts: str) -> str:
    """Generate markdown report."""
    lines = [
        "# Pipeline Execution Report",
        "",
        f"**Generated:** {ts}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    
    # Product counts
    total_products = sum(product_states.values())
    verified = product_states.get("VERIFIED", 0)
    lines.append(f"| Total Products | {total_products} |")
    lines.append(f"| Verified | {verified} |")
    
    for state, count in sorted(product_states.items()):
        if state != "VERIFIED":
            lines.append(f"| {state} | {count} |")
    
    # Step summaries
    lines.extend([
        "",
        "## Pipeline Steps",
        "",
    ])
    
    step_order = [
        "design_tokens_generator",
        "template_scaffolder",
        "template_validator",
        "template_qa",
        "digital_file_generator",
        "preview_generator",
        "readme_generator",
        "zip_bundle_generator",
        "platform_metadata_generator",
        "bundle_optimizer",
        "bundle_generator",
        "i18n_generator",
        "site_publisher"
    ]
    
    lines.append("| Step | Status | Details |")
    lines.append("|------|--------|---------|")
    
    for step in step_order:
        if step in summaries:
            data = summaries[step]["data"]
            status = data.get("status", "unknown")
            status_emoji = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"
            
            # Get relevant stats
            stats = data.get("stats", {})
            if stats:
                details = ", ".join(f"{k}={v}" for k, v in stats.items())
            else:
                details = "-"
            
            lines.append(f"| {step} | {status_emoji} {status} | {details} |")
        else:
            lines.append(f"| {step} | ⏭️ skipped | - |")
    
    # Output files
    lines.extend([
        "",
        "## Output Structure",
        "",
        "```",
        "generated/",
        "├── design/           # Design tokens and themes",
        "├── products/         # Product metadata (JSON)",
        "├── templates/        # Generated HTML templates",
        "├── previews/         # Preview HTML and SVG thumbnails",
        "├── qa/               # QA reports",
        "├── readme/           # README generation summary",
        "├── bundles/          # Bundle metadata",
        "├── platform/         # Platform-specific metadata",
        "└── pipeline_summary.json",
        "",
        "docs/",
        "├── downloads/        # Downloadable files per product",
        "│   └── {pid}/",
        "│       ├── template.csv",
        "│       ├── printable.html",
        "│       ├── instructions.txt",
        "│       ├── README.md",
        "│       └── bundle.zip",
        "├── products/         # Product detail pages",
        "├── bundles/          # Bundle pages",
        "└── index.html        # Site index",
        "```",
        "",
        "## Next Steps",
        "",
        "1. Review QA report for any failed checks",
        "2. Generate PNG previews from preview HTML files",
        "3. Upload to marketplace (Etsy, Gumroad)",
        "4. Test download links",
        "",
        "---",
        f"*Report generated at {ts}*"
    ])
    
    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    print("=" * 50)
    print("  Pipeline Summary")
    print("=" * 50)
    
    # Collect all summaries
    summaries = collect_summaries()
    print(f"Found {len(summaries)} step summaries")
    
    # Count products
    product_states = count_products()
    total_products = sum(product_states.values())
    print(f"Total products: {total_products}")
    for state, count in sorted(product_states.items()):
        print(f"  - {state}: {count}")
    
    # File counts
    template_counts = count_files(f"{GENERATED_DIR}/templates")
    preview_counts = count_files(f"{GENERATED_DIR}/previews")
    
    # Build comprehensive summary
    pipeline_summary = {
        "timestamp": ts,
        "status": "complete",
        "products": {
            "total": total_products,
            "by_state": product_states
        },
        "files": {
            "templates": template_counts,
            "previews": preview_counts
        },
        "steps": {}
    }
    
    for step, info in summaries.items():
        pipeline_summary["steps"][step] = {
            "status": info["data"].get("status", "unknown"),
            "timestamp": info["data"].get("timestamp"),
            "stats": info["data"].get("stats", {})
        }
    
    # Write JSON summary
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(pipeline_summary, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Summary: {SUMMARY_FILE}")
    
    # Generate markdown report
    report = generate_report(summaries, product_states, ts)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✓ Report: {REPORT_FILE}")
    
    print()
    print(f"pipeline_complete=true products={total_products}")


if __name__ == "__main__":
    main()
