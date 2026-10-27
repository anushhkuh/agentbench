from typer.testing import CliRunner
from agentbench.cli import app


def test_version():
    assert "0.3.0" in CliRunner().invoke(app, ["version"]).output
