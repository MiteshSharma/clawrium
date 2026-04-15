#!/usr/bin/env python3
"""Verify openclaw.json configuration against expected values.

This script is called by Ansible to verify the configuration file
was rendered correctly. It reads the actual and expected config files
and validates critical fields match.
"""

import json
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: verify_config.py <config_file> <expected_config_file>", file=sys.stderr)
        sys.exit(1)

    config_file = sys.argv[1]
    expected_file = sys.argv[2]

    # Verify config file exists
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at {config_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in {config_file}", file=sys.stderr)
        sys.exit(1)

    # Load expected config
    try:
        with open(expected_file, "r") as f:
            expected_config = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Expected config file not found at {expected_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in {expected_file}", file=sys.stderr)
        sys.exit(1)

    errors = []

    # Verify model is set if provider configured
    # W2 fix: Use exact equality instead of substring matching
    if expected_config.get("provider", {}).get("default_model"):
        model = config.get("agents", {}).get("defaults", {}).get("model")
        expected_model = expected_config["provider"]["default_model"]
        if not model:
            errors.append(
                f"Model not found in agents.defaults.model, expected '{expected_model}'"
            )
        elif str(model) != expected_model:
            errors.append(
                f"Model mismatch: expected '{expected_model}', got '{model}'"
            )

    # Verify gateway port
    if expected_config.get("gateway", {}).get("port"):
        gateway_port = config.get("gateway", {}).get("port")
        expected_port = expected_config["gateway"]["port"]
        if gateway_port != expected_port:
            errors.append(
                f"Gateway port mismatch: expected {expected_port}, got {gateway_port}"
            )

    # Verify gateway bind
    if expected_config.get("gateway", {}).get("bind"):
        gateway_bind = config.get("gateway", {}).get("bind")
        expected_bind = expected_config["gateway"]["bind"]
        if gateway_bind != expected_bind:
            errors.append(
                f"Gateway bind mismatch: expected {expected_bind}, got {gateway_bind}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    print("Configuration verified successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
