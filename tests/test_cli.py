"""Tests for CLI commands."""
import pytest
from click.testing import CliRunner
from modelhop.cli.main import cli
from modelhop.cli.commands.welcome import welcome


class TestCLI:
    """Tests for CLI entry points."""

    def test_version(self):
        """Test --version flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "modelhop" in result.output.lower() or "1.0" in result.output

    def test_help(self):
        """Test --help flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output or "modelhop" in result.output

    def test_welcome_command(self):
        """Test welcome command."""
        runner = CliRunner()
        result = runner.invoke(welcome)
        assert result.exit_code == 0
        assert "ModelHop" in result.output or "Welcome" in result.output

    def test_welcome_via_main(self):
        """Test that bare 'modelhop' shows welcome."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0


class TestCLICommands:
    """Tests for specific CLI commands."""

    def test_providers_help(self):
        """Test providers command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["providers", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self):
        """Test stats command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_history_help(self):
        """Test history command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--help"])
        assert result.exit_code == 0
