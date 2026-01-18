#!/usr/bin/env python3
"""
validate_config.py - Validate pipeline configuration against JSON schema

Usage:
    python scripts/validate_config.py <config.yaml>
    python scripts/validate_config.py --schema  # Print schema location

Exit codes:
    0 - Valid configuration
    1 - Invalid configuration or error
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    print("ERROR: jsonschema is required. Install with: pip install jsonschema")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent.resolve()
APP_DIR = SCRIPT_DIR.parent
SCHEMA_PATH = APP_DIR / "config" / "schema" / "pipeline.schema.json"


def load_schema() -> dict:
    """Load the JSON schema file."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(config_path: Path) -> dict:
    """Load and parse a YAML configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML syntax: {e}")


def format_validation_error(error: ValidationError) -> str:
    """Format a validation error into a readable message."""
    path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
    return f"  ✗ [{path}] {error.message}"


def validate_config(config: dict, schema: dict) -> list[str]:
    """
    Validate configuration against schema.
    Returns list of error messages (empty if valid).
    """
    validator = Draft7Validator(schema)
    errors = []
    
    for error in sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path)):
        errors.append(format_validation_error(error))
    
    return errors


def validate_config_file(config_path: Path, verbose: bool = False) -> bool:
    """
    Validate a configuration file.
    Returns True if valid, False otherwise.
    """
    print(f"Validating: {config_path}")
    print(f"Schema:     {SCHEMA_PATH}")
    print()
    
    try:
        schema = load_schema()
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return False
    
    if config is None:
        print("ERROR: Config file is empty")
        return False
    
    errors = validate_config(config, schema)
    
    if errors:
        print(f"Validation FAILED with {len(errors)} error(s):\n")
        for err in errors:
            print(err)
        print()
        return False
    
    print("✓ Configuration is valid!")
    
    if verbose:
        print("\nConfig summary:")
        print(f"  Project:    {config.get('project', {}).get('name', 'N/A')}")
        print(f"  Type:       {config.get('generation', {}).get('type', 'N/A')}")
        
        topics = config.get('topics', {})
        print(f"  Topics:     strategy={topics.get('strategy', 'auto')}, count={topics.get('count', 30)}")
        
        i18n = config.get('i18n', {})
        if i18n.get('enabled'):
            print(f"  Languages:  {', '.join(i18n.get('languages', []))}")
        
        publish = config.get('publish', {})
        print(f"  Publish:    enabled={publish.get('enabled', True)}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Validate pipeline configuration against JSON schema"
    )
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print schema location and exit"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show config summary after validation"
    )
    
    args = parser.parse_args()
    
    if args.schema:
        print(f"Schema location: {SCHEMA_PATH}")
        sys.exit(0)
    
    if not args.config:
        parser.print_help()
        sys.exit(1)
    
    success = validate_config_file(args.config, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
