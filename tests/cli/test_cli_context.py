import pytest
from tests.conftest import InvokeCli
from typer import Context, Typer
from typer.testing import CliRunner, Result

from communex.cli._common import make_custom_context
from communex.cli.root import app

context_test_app = Typer(no_args_is_help=True)

@context_test_app.command()
def confirmation(ctx: Context):
    """
    Transfer amount to destination using key
    """
    context = make_custom_context(ctx)

    if context.confirm("Do you want to proceed?"):
        context.output("Proceeded :P")
    else:
        context.info("Aborted :O")


app.add_typer(context_test_app, name="context", help="Testing the custom context general behaviour")

@pytest.fixture()
def invoke_cli() -> InvokeCli:
    runner = CliRunner()

    def invoke(command: list[str], input: str | None = None) -> Result:
        return runner.invoke(app, command, input, env={"COLUMNS": "200"})

    return invoke


def test_cli_context_yes_to_all_enable_y(invoke_cli: InvokeCli):
    cmd = ["-y", "context", "confirmation"]

    result = invoke_cli(cmd)

    assert result.exit_code == 0
    assert result.stdout == "Do you want to proceed? (--yes)\nProceeded :P\n"


def test_cli_context_yes_to_all_enable_yes(invoke_cli: InvokeCli):
    cmd = ["--yes", "context", "confirmation"]

    result = invoke_cli(cmd)

    assert result.exit_code == 0
    assert result.stdout == "Do you want to proceed? (--yes)\nProceeded :P\n"


def test_cli_context_yes_to_all_disable_y(invoke_cli: InvokeCli):
    cmd = ["context", "confirmation"]
    input = "y"

    result = invoke_cli(cmd, input)

    assert result.exit_code == 0
    assert result.stdout == "Do you want to proceed? [y/N]: y\nProceeded :P\n"


def test_cli_context_yes_to_all_disable_n(invoke_cli: InvokeCli):
    cmd = ["context", "confirmation"]
    input = "n"

    result = invoke_cli(cmd, input)

    assert result.exit_code == 0
    assert result.stdout == "Do you want to proceed? [y/N]: n\nAborted :O\n"
