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

The engine runs up to 12 steps based on configuration:

| # | Step | Config Control |
|---|------|----------------|
| 1 | topic_generator | `pipeline.steps.topic_generator` |
| 2 | topic_evaluator | `pipeline.steps.topic_evaluator` |
| 3 | product_builder | `pipeline.steps.product_builder` |
| 4 | template_generator | `pipeline.steps.template_generator` |
| 5 | template_validator | `pipeline.steps.template_validator` |
| 6 | digital_file_generator | `pipeline.steps.digital_file_generator` |
| 7 | zip_bundle_generator | `bundling.enabled` |
| 8 | platform_metadata_generator | `platforms.enabled` |
| 9 | bundle_optimizer | `bundling.enabled` |
| 10 | bundle_generator | `bundling.enabled` |
| 11 | i18n_generator | `i18n.enabled` |
| 12 | site_publisher | `publish.enabled` |

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
