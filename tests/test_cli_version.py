"""Tests for clm --version command."""

from pathlib import Path

from typer.testing import CliRunner

from clawrium import __version__
from clawrium.cli.main import app

runner = CliRunner()


class TestCliVersion:
    """Tests for the --version flag."""

    def test_version_flag_shows_version(self) -> None:
        """Running clm --version should show the version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_output_format(self) -> None:
        """Version output should be in 'clm <version>' format."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"clm {__version__}" in result.output

    def test_version_works_without_config(self, isolated_config: Path) -> None:
        """Version should work even without configuration."""
        assert not isolated_config.exists()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "clm" in result.output

    def test_version_is_valid_semver(self) -> None:
        """Version should be a valid semver-like string."""
        # Version should have at least major.minor format
        parts = __version__.split(".")
        assert len(parts) >= 2
        # First two parts should be numeric
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    def test_short_v_flag_not_version(self) -> None:
        """-v should NOT trigger --version (reserved for verbose on ps)."""
        result = runner.invoke(app, ["-v"])
        # -v at top level without a command should fail or show help, not version
        # because -v is not registered as a --version alias
        assert "clm" not in result.output or result.exit_code != 0

    def test_ps_verbose_still_works(self) -> None:
        """ps -v should trigger verbose mode, not version."""
        result = runner.invoke(app, ["ps", "-v"])
        # Should work (verbose output or no agents found message)
        # Should NOT show version string
        assert f"clm {__version__}" not in result.output
