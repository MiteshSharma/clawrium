"""Init command for Clawrium."""

import typer
from rich.console import Console

from clawrium.core.config import init_config_dir

__all__ = ["init"]

console = Console()


def init() -> None:
    """Initialize Clawrium configuration directory.

    Creates the configuration directory at ~/.config/clawrium/
    (or XDG_CONFIG_HOME/clawrium/ if set).
    """
    config_dir = init_config_dir()
    console.print(f"[green]Clawrium initialized![/green]")
    console.print(f"Config directory: {config_dir}")
