"""Tests for CLI commands."""

from click.testing import CliRunner

from modelhop.cli.main import cli


class TestCLI:
    """Tests for CLI entry points."""

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "modelhop" in result.output.lower() or "1.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_welcome_via_main(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "ModelHop" in result.output or "Welcome" in result.output


class TestCLICommands:
    """Tests for specific CLI commands."""

    def test_providers_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["providers", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_history_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--help"])
        assert result.exit_code == 0

    def test_cheat(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cheat"])
        assert result.exit_code == 0
        assert "ModelHop" in result.output

    def test_welcome(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["welcome"])
        assert result.exit_code == 0

    def test_example(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["example"])
        assert result.exit_code == 0
