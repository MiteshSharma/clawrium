"""Clawrium - CLI tool for managing AI assistant fleets."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("clawrium")
except PackageNotFoundError:
    __version__ = "0.0.0"
