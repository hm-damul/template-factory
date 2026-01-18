# template-factory-app

A config-driven API wrapper for the [template-factory](../template-factory) engine.

## Overview

This project provides a **configuration-driven interface** to the template-factory engine, enabling:

- **Declarative configuration** via YAML files
- **Schema validation** for configuration correctness
- **Multiple generation modes** (blog, youtube, digital_product, generic)
- **Selective pipeline execution** based on config settings
- **Future extensibility** for CLI and HTTP API exposure

## Quick Start

### Run with Default Settings

```bash
./template-factory-app/scripts/run_generate
```

### Run with YAML Configuration

```bash
./template-factory-app/scripts/run_generate --config config/examples/digital_product.yaml
```

### Validate Configuration Only

```bash
./template-factory-app/scripts/run_generate --validate-only config/examples/blog.yaml
```

### Dry Run (Preview Steps)

```bash
./template-factory-app/scripts/run_generate --config config/examples/youtube.yaml --dry-run
```

## Config-Driven API Concept

The wrapper transforms YAML configurations into pipeline executions:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌────────────┐
│ YAML Config │ ──▶ │  Validation  │ ──▶ │ Step Selection  │ ──▶ │  Pipeline  │
│   (input)   │     │   (schema)   │     │   (mapping)     │     │ (execution)│
└─────────────┘     └──────────────┘     └─────────────────┘     └────────────┘
```

### Configuration Schema

The schema (`config/schema/pipeline.schema.json`) defines:

| Section | Description |
|---------|-------------|
| `project` | Project metadata (name, description, author, tags) |
| `generation` | Generation type and dry-run toggle |
| `topics` | Topic strategy, count, categories, targets |
| `templates` | Output formats, validation rules, styling |
| `bundling` | Bundle size, strategy, categories |
| `pricing` | Currency, base price, discounts |
| `i18n` | Internationalization languages |
| `platforms` | Target platforms (Etsy, Gumroad) |
| `publish` | Output directory and site settings |
| `pipeline` | Fine-grained step control |

### Example Configuration

```yaml
version: "1.0"

project:
  name: "My Digital Products"
  
generation:
  type: digital_product

topics:
  strategy: auto
  count: 30
  categories: [budget, habit, meal]

bundling:
  enabled: true
  size: 5
  strategy: category

i18n:
  enabled: true
  languages: [fr, de, ja]

publish:
  enabled: true
  output_dir: output
```

## Available Examples

| Config | Use Case | Steps Enabled |
|--------|----------|---------------|
| `digital_product.yaml` | Etsy/Gumroad products | All 12 steps |
| `blog.yaml` | Blog content templates | 7 steps (no bundling/platform) |
| `youtube.yaml` | Video content outlines | 6 steps (minimal) |

## Directory Structure

```
template-factory-app/
├── README.md
├── scripts/
│   ├── run_generate         # Main CLI script
│   └── validate_config.py   # Schema validation
├── config/
│   ├── schema/
│   │   └── pipeline.schema.json  # JSON Schema
│   ├── examples/
│   │   ├── digital_product.yaml
│   │   ├── blog.yaml
│   │   └── youtube.yaml
│   └── pipeline.conf        # Legacy config (fallback)
├── output/                  # Generated output
└── .github/
    └── workflows/
        └── generate.yml     # GitHub Actions
```

## Pipeline Steps

The engine runs up to **17 steps** for production-ready digital templates:

| # | Step | Description | Config Control |
|---|------|-------------|----------------|
| 1 | topic_generator | Generate template topic ideas | `pipeline.steps.topic_generator` |
| 2 | topic_evaluator | Score and price topics | `pipeline.steps.topic_evaluator` |
| 3 | product_builder | Create product metadata | `pipeline.steps.product_builder` |
| 4 | **design_tokens_generator** | Generate design tokens & themes | `design.enabled` |
| 5 | **template_scaffolder** | Create themed, category-specific templates | `pipeline.steps.template_scaffolder` |
| 6 | template_validator | Validate template structure | `pipeline.steps.template_validator` |
| 7 | **template_qa** | QA checks (lint, print, a11y, duplicates) | `qa.enabled` |
| 8 | digital_file_generator | Create CSV/TXT/HTML files | `pipeline.steps.digital_file_generator` |
| 9 | **preview_generator** | Generate preview HTML & SVG thumbnails | `preview.enabled` |
| 10 | **readme_generator** | Create product README/how-to-use docs | `readme.enabled` |
| 11 | zip_bundle_generator | Package files into ZIP | `bundling.enabled` |
| 12 | platform_metadata_generator | Generate Etsy/Gumroad metadata | `platforms.enabled` |
| 13 | bundle_optimizer | Optimize bundle pricing | `bundling.enabled` |
| 14 | bundle_generator | Create multi-product bundles | `bundling.enabled` |
| 15 | i18n_generator | Generate internationalized pages | `i18n.enabled` |
| 16 | site_publisher | Publish verified products to site | `publish.enabled` |
| 17 | **pipeline_summary** | Generate final summary report | `pipeline.steps.pipeline_summary` |

### New Production Steps (Steps 4, 5, 7, 9, 10, 17)

#### Design Tokens Generator (Step 4)
Generates a design system with:
- **Color palettes** per category (budget=green, habit=purple, meal=orange, study=blue)
- **Typography scales** (fonts, sizes, weights)
- **Spacing units** and border styles
- **Theme presets** for each template category

Output: `generated/design/tokens.json`, `generated/design/themes/*.json`

#### Template Scaffolder (Step 5)
Creates professional, print-ready templates with:
- **Category-specific layouts** (budget tracker tables, habit checklist grids, etc.)
- **Theme-aware styling** from design tokens
- **Print-optimized CSS** with `@media print` rules
- **Professional structure** (header, sections, tables, footer)

Output: `generated/templates/*.html`

#### Template QA (Step 7)
Performs quality assurance checks:
- **HTML linting** (DOCTYPE, required tags, structure)
- **Print layout validation** (content length, table headers)
- **Accessibility checks** (lang attribute, alt text, landmarks)
- **Duplication detection** (similar content hash)

Output: `generated/qa/report.json`

#### Preview Generator (Step 9)
Creates preview assets:
- **Preview HTML** with styled metadata overlay
- **SVG thumbnails** for marketplace listings
- **PNG generation instructions** (requires headless browser)

Output: `generated/previews/*.html`, `generated/previews/*.svg`

#### README Generator (Step 10)
Creates product documentation:
- **Usage instructions** (digital + print options)
- **Category-specific tips** (budgeting, habit tracking, etc.)
- **License information**
- **FAQ section**

Output: `docs/downloads/{pid}/README.md`

#### Pipeline Summary (Step 17)
Generates comprehensive execution report:
- **Step-by-step status** summary
- **Product counts** by state
- **Error aggregation** across steps
- **Markdown report** for review

Output: `generated/pipeline_summary.json`, `output/pipeline_report.md`

## CLI Reference

```
Usage: run_generate [OPTIONS]

Options:
  --config <path>       Path to YAML configuration file
  --validate-only       Validate config and exit
  --dry-run             Preview steps without execution
  --verbose             Enable verbose output
  --help                Show help message
```

## Validation

Validate any configuration file:

```bash
python scripts/validate_config.py config/examples/digital_product.yaml
```

With verbose output:

```bash
python scripts/validate_config.py -v config/examples/blog.yaml
```

## GitHub Actions

Trigger manually via GitHub Actions:

1. Go to **Actions** tab
2. Select **Generate Templates** workflow
3. Click **Run workflow**
4. Download artifacts after completion

## Future API Exposure

This config-driven architecture is designed for future extensibility:

### CLI API (Planned)

```bash
# Install as CLI tool
pip install template-factory-app

# Run with config
tfapp generate --config my-config.yaml

# List available presets
tfapp presets list

# Generate from preset
tfapp generate --preset digital_product
```

### HTTP API (Planned)

```bash
# Start API server
tfapp serve --port 8080

# POST configuration
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/yaml" \
  -d @config.yaml

# GET job status
curl http://localhost:8080/jobs/abc123
```

### Python SDK (Planned)

```python
from template_factory_app import Pipeline

# Load and run
pipeline = Pipeline.from_yaml("config.yaml")
result = pipeline.run()

# Programmatic configuration
pipeline = Pipeline(
    project={"name": "My Project"},
    generation={"type": "digital_product"},
    topics={"count": 20}
)
result = pipeline.run()
```

## Requirements

- Python 3.11+
- PyYAML (`pip install pyyaml`)
- jsonschema (`pip install jsonschema`)

Install dependencies:

```bash
pip install pyyaml jsonschema
```
