"""Registry loading and claw manifest management.

This module provides functions to discover available claw types from bundled
manifests and extract their requirements and platform compatibility.
"""

import logging
from pathlib import Path
from typing import TypedDict

import yaml
from packaging.version import Version
from packaging.specifiers import SpecifierSet

logger = logging.getLogger(__name__)


class Requirements(TypedDict):
    """Claw requirements specification."""

    min_memory_mb: int
    gpu_required: bool
    dependencies: dict[str, str]


class ManifestEntry(TypedDict):
    """Single platform entry in a claw manifest."""

    version: str
    os: str
    os_version: str
    arch: str
    requirements: Requirements


class ClawManifest(TypedDict):
    """Complete claw manifest with all platform entries."""

    name: str
    description: str
    entries: list[ManifestEntry]


class CompatibilityResult(TypedDict):
    """Result of compatibility check between host and claw."""

    compatible: bool
    matched_entry: ManifestEntry | None
    reasons: list[str]


class ManifestNotFoundError(Exception):
    """Raised when a claw manifest is not found."""

    pass


class ManifestParseError(Exception):
    """Raised when a manifest YAML is malformed."""

    pass


def load_manifest(claw_name: str) -> ClawManifest:
    """Load claw manifest from bundled registry.

    Args:
        claw_name: Name of the claw (e.g., "openclaw")

    Returns:
        Parsed ClawManifest dictionary

    Raises:
        ManifestNotFoundError: If claw directory doesn't exist
        ManifestParseError: If YAML is invalid
    """
    try:
        # Use importlib.resources to read manifest from package
        from importlib.resources import files

        registry_package = files("clawrium.platform.registry")
        claw_dir = registry_package / claw_name

        # Check if claw directory exists
        if not claw_dir.is_dir():
            raise ManifestNotFoundError(f"Claw '{claw_name}' not found in registry")

        manifest_file = claw_dir / "manifest.yaml"

        # Read and parse manifest
        manifest_text = manifest_file.read_text()
        manifest_data = yaml.safe_load(manifest_text)

        if not isinstance(manifest_data, dict):
            raise ManifestParseError(
                f"Manifest for '{claw_name}' is not a valid YAML dict"
            )

        # Validate basic structure
        if "name" not in manifest_data or "entries" not in manifest_data:
            raise ManifestParseError(
                f"Manifest for '{claw_name}' missing required fields (name, entries)"
            )

        return manifest_data

    except FileNotFoundError as e:
        raise ManifestNotFoundError(f"Claw '{claw_name}' not found in registry") from e
    except yaml.YAMLError as e:
        raise ManifestParseError(
            f"Failed to parse manifest for '{claw_name}': {e}"
        ) from e


def list_claws() -> list[str]:
    """List all available claw types in the registry.

    Returns:
        Sorted list of claw names
    """
    try:
        from importlib.resources import files

        registry_package = files("clawrium.platform.registry")

        # List subdirectories that contain manifest.yaml
        claws = []
        for item in registry_package.iterdir():
            if item.is_dir():
                manifest_file = item / "manifest.yaml"
                try:
                    # Check if manifest exists by trying to read it
                    _ = manifest_file.read_text()
                    claws.append(item.name)
                except (FileNotFoundError, AttributeError):
                    # Skip directories without manifest.yaml
                    continue

        return sorted(claws)

    except Exception as e:
        logger.error("Failed to list claws: %s", e)
        return []


def get_claw_info(claw_name: str) -> dict:
    """Get summary information about a claw.

    Args:
        claw_name: Name of the claw

    Returns:
        Dictionary with: name, description, latest_version, supported_platforms

    Raises:
        ManifestNotFoundError: If claw doesn't exist
    """
    manifest = load_manifest(claw_name)

    # Find latest version (highest semver)
    versions = [Version(entry["version"]) for entry in manifest["entries"]]
    latest_version = str(max(versions))

    # Build supported platforms list
    platforms = []
    for entry in manifest["entries"]:
        platform = f"{entry['os']} {entry['os_version']} {entry['arch']}"
        if platform not in platforms:
            platforms.append(platform)

    return {
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "latest_version": latest_version,
        "supported_platforms": sorted(platforms),
    }


def _check_dependency_version(required: str, installed: str | None) -> bool:
    """Check if installed version satisfies requirement.

    Args:
        required: Version specifier string (e.g., ">=20.0.0")
        installed: Installed version string or None if not installed

    Returns:
        True if installed version satisfies requirement, False otherwise
    """
    if installed is None:
        return False
    try:
        spec = SpecifierSet(required)
        return Version(installed) in spec
    except Exception:
        return False


def check_compatibility(
    claw_name: str,
    hardware: dict,
    version: str | None = None,
) -> CompatibilityResult:
    """Check if host hardware is compatible with a claw.

    This implements sparse matrix matching - only explicitly supported
    combinations (OS, version, arch) are valid. All requirements must
    be met for compatibility.

    Args:
        claw_name: Name of the claw (e.g., "openclaw")
        hardware: HardwareInfo dict from host (see hardware.py)
        version: Optional specific version to check (default: any version)

    Returns:
        CompatibilityResult with:
            - compatible: True if host matches any manifest entry
            - matched_entry: The ManifestEntry that matched, or None
            - reasons: List of failure reasons (empty if compatible)

    Raises:
        ManifestNotFoundError: If claw manifest doesn't exist
    """
    manifest = load_manifest(claw_name)

    # Filter entries by version if specified
    entries = manifest["entries"]
    if version:
        entries = [e for e in entries if e["version"] == version]
        if not entries:
            return {
                "compatible": False,
                "matched_entry": None,
                "reasons": [f"Version {version} not found in manifest"],
            }

    # Collect all failure reasons across all entries
    all_reasons = []

    # Try each entry in order
    for entry in entries:
        reasons = []

        # Check OS match
        if entry["os"] != hardware.get("os"):
            reasons.append(
                f"Requires {entry['os']} {entry['os_version']}, "
                f"host has {hardware.get('os', 'unknown')} {hardware.get('os_version', 'unknown')}"
            )

        # Check OS version match
        elif entry["os_version"] != hardware.get("os_version"):
            reasons.append(
                f"Requires {entry['os']} {entry['os_version']}, "
                f"host has {hardware.get('os')} {hardware.get('os_version', 'unknown')}"
            )

        # Check architecture match
        if entry["arch"] != hardware.get("architecture"):
            reasons.append(
                f"Requires {entry['arch']}, host has {hardware.get('architecture', 'unknown')}"
            )

        # Check memory requirement
        min_memory = entry["requirements"]["min_memory_mb"]
        host_memory = hardware.get("memtotal_mb", 0)
        if host_memory < min_memory:
            reasons.append(
                f"Requires {min_memory}MB RAM, host has {host_memory}MB"
            )

        # Check GPU requirement
        if entry["requirements"]["gpu_required"]:
            gpu = hardware.get("gpu", {})
            if not gpu.get("present"):
                reasons.append("Requires GPU, host has none")

        # Check dependencies (if any)
        dependencies = entry["requirements"].get("dependencies", {})
        for dep_name, dep_version in dependencies.items():
            # For now, we don't have installed dependency info in hardware dict
            # This would need to be added in future phases
            # For v1, we'll skip dependency checking
            pass

        # If this entry matches all requirements, return success
        if not reasons:
            return {
                "compatible": True,
                "matched_entry": entry,
                "reasons": [],
            }

        # Collect reasons from this entry
        all_reasons.extend(reasons)

    # No entry matched - return failure with all collected reasons
    # Deduplicate reasons while preserving order
    unique_reasons = []
    seen = set()
    for r in all_reasons:
        if r not in seen:
            unique_reasons.append(r)
            seen.add(r)

    return {
        "compatible": False,
        "matched_entry": None,
        "reasons": unique_reasons,
    }
